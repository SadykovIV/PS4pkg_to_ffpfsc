from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from .dump_source import DumpSourceError, discover_dump_records
from .util import (
    atomic_write_json,
    content_id_parts,
    file_stat_identity,
    paths_overlap,
    sanitize_component,
    utc_now,
    validate_title_id,
    version_key,
)

LOG = logging.getLogger("ps4ffpsc")

PATCH_ROLE_ORDINARY = "ordinary"
PATCH_ROLE_ADDITIONAL_LAYER = "additional_layer"
_PATCH_ROLE_VALUES = {PATCH_ROLE_ORDINARY, PATCH_ROLE_ADDITIONAL_LAYER}
DLC_PACKAGE_TYPES = {"PSAC": 0x1B, "PSAL": 0x1C}
_ADDITIONAL_LAYER_FILENAME_MARKER = re.compile(
    r"""
    (
        (?<![a-z0-9])back(?:[-_ ]?port)(?![a-z0-9])
        |
        (?<![a-z0-9])fix[-_ ]*\d+(?:[._]\d+)+(?![a-z0-9])
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _numeric_version(value: Any) -> tuple[int, ...] | None:
    """Return a sortable numeric version, or ``None`` for invalid metadata."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return version_key(value)
    except (TypeError, ValueError):
        return None


def classify_patch_filename(path: Path) -> tuple[str, str]:
    """Classify an explicit same-version patch layer marker without trusting size."""
    marker = _ADDITIONAL_LAYER_FILENAME_MARKER.search(path.stem)
    if marker is None:
        return PATCH_ROLE_ORDINARY, "no_explicit_filename_marker"
    return (
        PATCH_ROLE_ADDITIONAL_LAYER,
        "filename_marker:" + marker.group(1).casefold(),
    )


def patch_role(package: dict[str, Any]) -> str:
    """Return a recorded patch role, with a compatible fallback for old inventories."""
    role = package.get("patch_role")
    if isinstance(role, str) and role in _PATCH_ROLE_VALUES:
        return role
    if package.get("kind") == "patch":
        return classify_patch_filename(Path(str(package.get("path", ""))))[0]
    return PATCH_ROLE_ORDINARY


def patch_role_reason(package: dict[str, Any]) -> str:
    reason = package.get("patch_role_reason")
    if isinstance(reason, str) and reason:
        return reason
    if package.get("kind") == "patch":
        return classify_patch_filename(Path(str(package.get("path", ""))))[1]
    return "not_a_patch"


def patch_order_key(package: dict[str, Any]) -> tuple[tuple[int, ...], int, str, str]:
    """Make patch layering deterministic, including an explicit same-version layer."""
    role_rank = (
        1 if patch_role(package) == PATCH_ROLE_ADDITIONAL_LAYER else 0
    )
    return (
        # Invalid patch metadata must remain visible in the inventory instead of
        # aborting the entire scan while the plan is being rendered.  Such a game
        # is made non-buildable by _group_games below.
        _numeric_version(package.get("app_version")) or (),
        role_rank,
        str(package.get("path", "")).casefold(),
        str(package.get("source_id") or package.get("scan_id") or "").casefold(),
    )


def ordered_patches(game: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the non-duplicate patch sequence used for extraction and overlay."""
    return sorted(
        (
            item
            for item in game.get("patches", [])
            if item.get("supported", True) and not item.get("duplicate_of")
        ),
        key=patch_order_key,
    )


def patch_build_plan(game: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe the exact patch sequence in a serializable, backward-compatible form."""
    return [
        {
            "order": index,
            "app_version": package.get("app_version", ""),
            "source_id": package.get("source_id") or package.get("scan_id"),
            "role": patch_role(package),
            "reason": patch_role_reason(package),
        }
        for index, package in enumerate(ordered_patches(game), start=1)
    ]


def find_extractor(root: Path, resources: Path | None = None) -> Path | None:
    resources = resources or root
    names = ("ps4_pkg_extract.exe", "ps4_pkg_extract")
    directories = [
        resources / "bin",
        resources / "build" / "tools" / "ps4_pkg_extract",
        resources / "build",
        root / "build" / "tools" / "ps4_pkg_extract",
        root / "build",
        root / "tools" / "ps4_pkg_extract" / "build",
    ]
    candidates = [directory / name for directory in directories for name in names]
    return next((path for path in candidates if path.is_file()), None)


def inspect_package(
    extractor: Path,
    path: Path,
    compute_sha256: bool = True,
) -> dict[str, Any]:
    command = [str(extractor), "inspect", str(path), "--json"]
    if not compute_sha256:
        command.append("--fast")
    process = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    if not lines:
        return {
            "path": str(path),
            "supported": False,
            "error": "unsupported_or_encrypted_pkg",
            "reason": process.stderr.strip() or "extractor returned no JSON",
        }
    try:
        record = json.loads(lines[-1])
    except json.JSONDecodeError:
        record = {
            "path": str(path),
            "supported": False,
            "error": "unsupported_or_encrypted_pkg",
            "reason": "extractor returned malformed JSON",
        }
    record["path"] = str(path.resolve())
    return record


def _validate_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not validate_title_id(record.get("title_id", "")):
        errors.append("invalid_title_id")
    app_version = record.get("app_version", "")
    if app_version and _numeric_version(app_version) is None:
        errors.append("invalid_app_version")
    content = record.get("content_id", "")
    parts = content_id_parts(content)
    if parts is None:
        errors.append("invalid_content_id")
    elif record.get("title_id") not in parts[1]:
        errors.append("content_id_title_mismatch")
    if record.get("kind") == "dlc" and not record.get("entitlement_label"):
        errors.append("invalid_entitlement_label")
    if record.get("kind") == "dlc" and (
        "pkg_content_type" in record or "dlc_package_type" in record
    ):
        dlc_package_type = record.get("dlc_package_type")
        expected_content_type = (
            DLC_PACKAGE_TYPES.get(dlc_package_type)
            if isinstance(dlc_package_type, str)
            else None
        )
        if expected_content_type is None or record.get(
            "pkg_content_type"
        ) != expected_content_type:
            errors.append("invalid_dlc_package_type")
    return errors


def _fast_duplicate_key(record: dict[str, Any]) -> tuple[Any, ...] | None:
    package_digest = str(record.get("package_digest") or "").lower()
    if (
        re.fullmatch(r"[0-9a-f]{64}", package_digest) is None
        or not package_digest.strip("0")
    ):
        return None
    return (
        package_digest,
        record.get("kind"),
        record.get("title_id"),
        record.get("category"),
        record.get("content_id"),
        record.get("app_version"),
        record.get("version"),
        record.get("system_version"),
        record.get("entitlement_label"),
        record.get("pkg_content_type"),
        record.get("dlc_package_type"),
        int(record.get("size", 0) or 0),
        tuple(sorted(str(flag) for flag in record.get("pkg_flags", []))),
    )


def _mark_fast_duplicates(packages: list[dict[str, Any]]) -> None:
    canonical_by_metadata: dict[tuple[Any, ...], dict[str, Any]] = {}
    for package in packages:
        key = _fast_duplicate_key(package)
        if key is None:
            continue
        canonical = canonical_by_metadata.get(key)
        if canonical is None:
            canonical_by_metadata[key] = package
            continue
        package["duplicate_of"] = canonical["path"]
        package["duplicate_match"] = "package_digest_metadata_and_size"


def _group_games(
    packages: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    games: dict[str, dict[str, Any]] = {}
    unsupported = [record for record in packages if not record.get("supported")]
    for record in packages:
        if not record.get("supported"):
            continue
        title_id = record["title_id"]
        game = games.setdefault(
            title_id,
            {
                "title_id": title_id,
                "title": record.get("title") or title_id,
                "directory_name": "",
                "base": [],
                "patches": [],
                "dlc": [],
                "unknown": [],
                "conflicts": [],
                "warnings": [],
                "patch_plan": [],
                "buildable": False,
            },
        )
        bucket = {
            "base": "base",
            "patch": "patches",
            "dlc": "dlc",
        }.get(record["kind"], "unknown")
        game[bucket].append(record)

    for title_id, game in games.items():
        title = game["title"] or title_id
        game["directory_name"] = (
            f"{title_id} - {sanitize_component(title, title_id)}"
        )
        for key in ("base", "patches", "dlc", "unknown"):
            _mark_fast_duplicates(game[key])

        unique_bases = [
            item for item in game["base"] if not item.get("duplicate_of")
        ]
        if len(unique_bases) > 1:
            game["conflicts"].append("conflicting_base_packages")
        if not unique_bases:
            game["warnings"].append("orphan_package")
        if game["unknown"]:
            game["warnings"].append("unknown_package_kind")

        base_content = (
            unique_bases[0].get("content_id", "")
            if len(unique_bases) == 1
            else ""
        )
        base_region = content_id_parts(base_content)
        for item in (
            package
            for package in game["patches"]
            if not package.get("duplicate_of")
        ):
            parts = content_id_parts(item.get("content_id", ""))
            if base_region and parts and parts[:2] != base_region[:2]:
                item.setdefault("validation_errors", []).append(
                    "region_or_content_mismatch"
                )
                game["conflicts"].append("incompatible_package")

        # DLC is optional and disabled by default.  An incompatible DLC source
        # must therefore remain visible and unselected without making an
        # otherwise valid base/patch set unbuildable.  Experimental embedding
        # performs a strict selected-DLC validation before extraction.
        for item in (
            package
            for package in game["dlc"]
            if not package.get("duplicate_of")
        ):
            parts = content_id_parts(item.get("content_id", ""))
            if base_region and parts and parts[:2] != base_region[:2]:
                errors = item.setdefault("validation_errors", [])
                if "region_or_content_mismatch" not in errors:
                    errors.append("region_or_content_mismatch")
                game["warnings"].append("incompatible_dlc_package")

        patches_by_version: dict[str, list[dict[str, Any]]] = {}
        invalid_patch_versions = False
        for patch in game["patches"]:
            if patch.get("duplicate_of"):
                continue
            if _numeric_version(patch.get("app_version")) is None:
                patch_errors = patch.setdefault("validation_errors", [])
                if "invalid_app_version" not in patch_errors:
                    patch_errors.append("invalid_app_version")
                invalid_patch_versions = True
            patches_by_version.setdefault(
                str(patch.get("app_version", "")), []
            ).append(patch)
        for version, same_version_patches in patches_by_version.items():
            ordinary = [
                patch
                for patch in same_version_patches
                if patch_role(patch) == PATCH_ROLE_ORDINARY
            ]
            additional = [
                patch
                for patch in same_version_patches
                if patch_role(patch) == PATCH_ROLE_ADDITIONAL_LAYER
            ]
            if len(same_version_patches) > 1 and not (
                len(same_version_patches) == 2
                and len(ordinary) == 1
                and len(additional) == 1
            ):
                game["conflicts"].append(
                    f"conflicting_patch_version:{version}"
                )
        if invalid_patch_versions:
            game["conflicts"].append("invalid_patch_app_version")
        game["patch_plan"] = patch_build_plan(game)
        game["conflicts"] = sorted(set(game["conflicts"]))
        game["warnings"] = sorted(set(game["warnings"]))
        game["buildable"] = len(unique_bases) == 1 and not game["conflicts"]
    return games, unsupported


def scan_dump_directories(
    root: Path,
    dump_dirs: tuple[Path, ...],
    unpacked_dir: Path,
) -> dict[str, Any]:
    if not dump_dirs:
        raise ValueError("at least one --dump-dir is required")
    selected = sorted(
        {path.expanduser().resolve() for path in dump_dirs},
        key=lambda path: str(path).casefold(),
    )
    LOG.info("scanning %d unpacked game source(s)", len(selected))
    packages: list[dict[str, Any]] = []
    for path in selected:
        if paths_overlap(path, unpacked_dir):
            raise DumpSourceError(
                "unpacked game source overlaps the application's unpacked "
                f"workspace; choose a different temporary directory: {path}"
            )
        LOG.info("inspecting unpacked game source: %s", path)
        for record in discover_dump_records(path):
            record["validation_errors"] = _validate_record(record)
            if record.get("kind") == "patch":
                role, reason = classify_patch_filename(Path(record["path"]))
                record["patch_role"] = role
                record["patch_role_reason"] = reason
            packages.append(record)

    games, unsupported = _group_games(packages)
    inventory = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "project_root": str(root),
        "pkg_dir": None,
        "source_mode": "dump_directories",
        "selected_pkg_files": [],
        "selected_dump_dirs": [str(path) for path in selected],
        "extractor": None,
        "shadps4_snapshot": None,
        "packages": packages,
        "games": games,
        "unsupported": unsupported,
    }
    atomic_write_json(unpacked_dir / "package_inventory.json", inventory)
    return inventory


def scan_packages(
    root: Path,
    pkg_dir: Path,
    unpacked_dir: Path,
    extractor: Path,
    pkg_files: tuple[Path, ...] = (),
) -> dict[str, Any]:
    if pkg_files:
        invalid = [
            path
            for path in pkg_files
            if not path.is_file() or path.suffix.lower() != ".pkg"
        ]
        if invalid:
            raise FileNotFoundError(
                "selected PKG does not exist or has the wrong extension: "
                + ", ".join(str(path) for path in invalid)
            )
        files = sorted(
            {path.resolve() for path in pkg_files},
            key=lambda path: str(path).casefold(),
        )
        source_mode = "selected_files"
    else:
        files = sorted(
            (
                path
                for path in pkg_dir.rglob("*")
                if path.is_file() and path.suffix.lower() == ".pkg"
            ),
            key=lambda path: str(path).casefold(),
        )
        source_mode = "recursive_directory"
    LOG.info("scanning %d PKG file(s)", len(files))
    packages: list[dict[str, Any]] = []
    for path in files:
        LOG.info("inspecting PKG: %s", path)
        record = inspect_package(extractor, path, compute_sha256=False)
        stat_result = path.stat()
        record.pop("sha256", None)
        record.pop("sha256_verified", None)
        record.pop("duplicate_of", None)
        record["source_id"] = file_stat_identity(path)
        record["size"] = stat_result.st_size
        record["source_mtime_ns"] = stat_result.st_mtime_ns
        record["validation_errors"] = _validate_record(record) if record.get("supported") else []
        if record.get("supported") and record.get("kind") == "patch":
            role, reason = classify_patch_filename(path)
            record["patch_role"] = role
            record["patch_role_reason"] = reason
        packages.append(record)
    games, unsupported = _group_games(packages)

    inventory = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "project_root": str(root),
        "pkg_dir": str(pkg_dir),
        "source_mode": source_mode,
        "selected_pkg_files": [str(path) for path in files] if pkg_files else [],
        "extractor": str(extractor),
        "shadps4_snapshot": "v.0.7.0 (archive commit 3b2c01272383e1fcd0b82c7873e1ebf1a641aada)",
        "packages": packages,
        "games": games,
        "unsupported": unsupported,
    }
    atomic_write_json(unpacked_dir / "package_inventory.json", inventory)
    return inventory

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from .util import (
    atomic_write_json,
    content_id_parts,
    file_stat_identity,
    sanitize_component,
    utc_now,
    validate_title_id,
    version_key,
)

LOG = logging.getLogger("ps4ffpsc")


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
    if app_version:
        try:
            version_key(app_version)
        except ValueError:
            errors.append("invalid_app_version")
    content = record.get("content_id", "")
    parts = content_id_parts(content)
    if parts is None:
        errors.append("invalid_content_id")
    elif record.get("title_id") not in parts[1]:
        errors.append("content_id_title_mismatch")
    if record.get("kind") == "dlc" and not record.get("entitlement_label"):
        errors.append("invalid_entitlement_label")
    return errors


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
    games: dict[str, dict[str, Any]] = {}
    unsupported: list[dict[str, Any]] = []
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
        if not record.get("supported"):
            unsupported.append(record)
            packages.append(record)
            continue
        packages.append(record)

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
                "buildable": False,
            },
        )
        bucket = {"base": "base", "patch": "patches", "dlc": "dlc"}.get(record["kind"], "unknown")
        game[bucket].append(record)

    for title_id, game in games.items():
        title = game["title"] or title_id
        game["directory_name"] = f"{title_id} - {sanitize_component(title, title_id)}"
        unique_bases = game["base"]
        if len(unique_bases) > 1:
            game["conflicts"].append("conflicting_base_packages")
        if not unique_bases:
            game["warnings"].append("orphan_package")
        if game["unknown"]:
            game["warnings"].append("unknown_package_kind")

        base_content = unique_bases[0].get("content_id", "") if len(unique_bases) == 1 else ""
        base_region = content_id_parts(base_content)
        for item in [*game["patches"], *game["dlc"]]:
            parts = content_id_parts(item.get("content_id", ""))
            if base_region and parts and parts[:2] != base_region[:2]:
                item.setdefault("validation_errors", []).append("region_or_content_mismatch")
                game["conflicts"].append("incompatible_package")

        versions: dict[str, str] = {}
        for patch in game["patches"]:
            version = patch.get("app_version", "")
            identity = patch["source_id"]
            previous = versions.get(version)
            if previous and previous != identity:
                game["conflicts"].append(f"conflicting_patch_version:{version}")
            versions[version] = identity
        game["conflicts"] = sorted(set(game["conflicts"]))
        game["warnings"] = sorted(set(game["warnings"]))
        game["buildable"] = len(unique_bases) == 1 and not game["conflicts"]

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

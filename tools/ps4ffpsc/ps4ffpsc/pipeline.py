from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .inventory import find_extractor, inspect_package, scan_packages
from .npbind import validate_npbind
from .runtime import (
    is_frozen,
    maximum_logical_cpu_count,
    validate_compression_worker_count,
)
from .sfo import build_param_json, choose_title, parse_sfo, validate_shadowmount_param_json
from .util import (
    atomic_write_json,
    ensure_within,
    file_stat_identity,
    iter_tree_files,
    read_json,
    safe_remove_tree,
    sha256_file,
    stage_file_atomic,
    tree_stat_manifest,
    tree_stat_signature,
    utc_now,
    validate_title_id,
    version_key,
)

LOG = logging.getLogger("ps4ffpsc")
PROGRESS_PREFIX = "PS4FFPSC_PROGRESS "
EXTRACTOR_REVISION = "aligned-np-metadata-ciphertext-v2"
EXTRACTION_STATE_SCHEMA_VERSION = 3
OUTPUT_FORMATS = {"ffpfsc", "exfat"}


@dataclass
class Settings:
    root: Path
    pkg_dir: Path
    unpacked_dir: Path
    output_dir: Path
    work_dir: Path
    temp_dir: Path
    compat: str = "current-smp"
    include_dlc: str = "auto"
    jobs: int = 2
    compression_level: int = 7
    compression_workers: int | None = None
    output_format: str = "ffpfsc"
    resume: bool = True
    force: bool = False
    dry_run: bool = False
    json_output: bool = False
    verbose: bool = False
    keep_inner_image: bool = False
    pkg_files: tuple[Path, ...] = ()
    console_log: bool = False
    resource_root: Path | None = None

    @classmethod
    def load(cls, root: Path, args: Any, resource_root: Path | None = None) -> "Settings":
        resources = resource_root or root
        config_path = resources / "ps4ffpsc.toml"
        config: dict[str, Any] = {}
        if config_path.exists():
            with config_path.open("rb") as stream:
                config = tomllib.load(stream)
        paths = config.get("paths", {})
        extract = config.get("extract", {})
        shadow = config.get("shadowmount", {})
        pack = config.get("pack", {})

        def resolve(option: str, default: str) -> Path:
            raw = getattr(args, option, None) or paths.get(option.removesuffix("_dir"), default)
            path = Path(raw).expanduser()
            return path.resolve() if path.is_absolute() else (root / path).resolve()

        temp_raw = getattr(args, "temp_dir", None)
        temp_path = Path(temp_raw).expanduser() if temp_raw else resolve("work_dir", "work") / "tmp"
        if not temp_path.is_absolute():
            temp_path = (root / temp_path).resolve()
        compression_level_value = getattr(args, "compression_level", None)
        if compression_level_value is None:
            compression_level_value = pack.get("compression_level", 7)
        compression_level = int(compression_level_value)
        if not 0 <= compression_level <= 9:
            raise ValueError("compression level must be within 0..9")
        output_format = str(
            getattr(args, "output_format", None) or pack.get("format", "ffpfsc")
        ).lower()
        if output_format not in OUTPUT_FORMATS:
            raise ValueError(
                "output format must be one of: " + ", ".join(sorted(OUTPUT_FORMATS))
            )
        compression_workers_value = getattr(args, "compression_workers", None)
        if compression_workers_value is None:
            compression_workers_value = pack.get("compression_workers")
        compression_workers = (
            None
            if compression_workers_value is None
            else validate_compression_worker_count(compression_workers_value)
        )
        keep_inner_image = bool(
            getattr(args, "keep_inner_image", False)
            or pack.get("keep_inner_image", False)
        )
        if output_format == "exfat" and keep_inner_image:
            raise ValueError(
                "--keep-inner-image applies only to FFPFSC output"
            )
        return cls(
            root=root,
            pkg_dir=resolve("pkg_dir", "pkg"),
            unpacked_dir=resolve("unpacked_dir", "unpacked"),
            output_dir=resolve("output_dir", "output"),
            work_dir=resolve("work_dir", "work"),
            temp_dir=temp_path,
            compat=getattr(args, "compat", None) or shadow.get("compatibility", "current-smp"),
            include_dlc=getattr(args, "include_dlc", None) or shadow.get("include_dlc", "auto"),
            jobs=max(1, int(getattr(args, "jobs", None) or extract.get("jobs", 2))),
            compression_level=compression_level,
            compression_workers=compression_workers,
            output_format=output_format,
            resume=bool(
                getattr(args, "resume", False)
                or (extract.get("resume", True) and not getattr(args, "no_resume", False))
            ),
            force=bool(getattr(args, "force", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
            json_output=bool(getattr(args, "json", False)),
            verbose=bool(getattr(args, "verbose", False)),
            keep_inner_image=keep_inner_image,
            pkg_files=tuple(
                Path(item).expanduser().resolve()
                for item in (getattr(args, "pkg_file", None) or [])
            ),
            console_log=bool(getattr(args, "console_log", False)),
            resource_root=resources,
        )


def configure_logging(settings: Settings, title_id: str | None = None) -> None:
    settings.root.joinpath("logs").mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.FileHandler(settings.root / "logs" / "ps4ffpsc.log", encoding="utf-8")
    ]
    if settings.console_log:
        handlers.append(logging.StreamHandler(sys.stderr))
    if title_id:
        timestamp = utc_now().replace(":", "").replace("+", "_")
        handlers.append(
            logging.FileHandler(
                settings.root / "logs" / f"{timestamp}-{title_id}.log", encoding="utf-8"
            )
        )
    logging.basicConfig(
        level=logging.DEBUG if settings.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )


def _gui_progress_enabled() -> bool:
    return os.environ.get("PS4FFPSC_GUI_PROGRESS") == "1"


def _emit_gui_progress(scope: str, **payload: Any) -> None:
    if not _gui_progress_enabled():
        return
    message = {"scope": scope, **payload}
    print(
        PROGRESS_PREFIX + json.dumps(message, ensure_ascii=False, separators=(",", ":")),
        file=sys.stderr,
        flush=True,
    )


def extractor_or_raise(settings: Settings) -> Path:
    extractor = find_extractor(settings.root, settings.resource_root)
    if extractor is None:
        raise RuntimeError("ps4_pkg_extract is not built; run scripts/build_macos.sh")
    return extractor


def inventory_path(settings: Settings) -> Path:
    return settings.unpacked_dir / "package_inventory.json"


def load_or_scan(settings: Settings, refresh: bool = False) -> dict[str, Any]:
    if not refresh and inventory_path(settings).exists():
        return read_json(inventory_path(settings))
    settings.unpacked_dir.mkdir(parents=True, exist_ok=True)
    return scan_packages(
        settings.root,
        settings.pkg_dir,
        settings.unpacked_dir,
        extractor_or_raise(settings),
        settings.pkg_files,
    )


def game_or_raise(inventory: dict[str, Any], title_id: str) -> dict[str, Any]:
    if not validate_title_id(title_id):
        raise ValueError(f"TITLE_ID must match CUSA + 5 digits: {title_id!r}")
    try:
        return inventory["games"][title_id]
    except KeyError as error:
        raise ValueError(f"TITLE_ID not found in inventory: {title_id}") from error


def game_root(settings: Settings, game: dict[str, Any]) -> Path:
    return settings.unpacked_dir / game["directory_name"]


def package_destination(root: Path, package: dict[str, Any]) -> Path:
    identity = (
        package.get("source_id")
        or package.get("scan_id")
        or package.get("sha256")
    )
    if not identity:
        raise RuntimeError(f"package has no identity: {package.get('path')}")
    short_hash = identity.removeprefix("stat-").removeprefix("scan-")[:12]
    kind = package["kind"]
    if kind == "base":
        return root / "packages" / "base" / short_hash
    if kind == "patch":
        return root / "packages" / "patches" / f"{package['app_version']}-{short_hash}"
    if kind == "dlc":
        label = package.get("entitlement_label") or f"UNKNOWN-{short_hash}"
        return root / "packages" / "dlc" / label / short_hash
    return root / "packages" / "unknown" / short_hash


def _disk_required(packages: list[dict[str, Any]], multiplier: float) -> int:
    return int(sum(int(item.get("size", 0)) for item in packages) * multiplier + 2 * 1024**3)


def check_disk_space(path: Path, required: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(path).free
    if free < required:
        raise OSError(
            28,
            f"insufficient disk space: required≈{required / 1024**3:.1f} GiB, "
            f"available={free / 1024**3:.1f} GiB; choose another --temp-dir",
        )


def _recover_state_from_manifest(root: Path) -> dict[str, Any] | None:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = read_json(manifest_path)
        if manifest.get("extractor_revision") != EXTRACTOR_REVISION:
            return None
        packages: dict[str, dict[str, Any]] = {}
        for record in manifest.get("extractions", []):
            source_id = record.get("source_id")
            destination_value = record.get("destination")
            if (
                record.get("status") != "verified"
                or not source_id
                or not destination_value
                or not record.get("tree_signature")
            ):
                continue
            destination = Path(destination_value)
            ensure_within(root, destination)
            if destination.is_dir():
                packages[str(source_id)] = dict(record)
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    if not packages:
        return None
    LOG.info(
        "recovered resumable extraction state from manifest: %d package(s)",
        len(packages),
    )
    return {
        "schema_version": EXTRACTION_STATE_SCHEMA_VERSION,
        "extractor_revision": EXTRACTOR_REVISION,
        "packages": packages,
        "updated_at": utc_now(),
    }


def _load_state(root: Path) -> dict[str, Any]:
    path = root / ".ps4ffpsc-state.json"
    if path.exists():
        try:
            state = read_json(path)
            if (
                state.get("schema_version") == EXTRACTION_STATE_SCHEMA_VERSION
                and state.get("extractor_revision") == EXTRACTOR_REVISION
                and isinstance(state.get("packages"), dict)
            ):
                return state
        except (AttributeError, OSError, TypeError, ValueError):
            LOG.warning("could not read extraction state; checking manifest: %s", path)
        recovered = _recover_state_from_manifest(root)
        if recovered is not None:
            _save_state(root, recovered)
            return recovered
        packages = root / "packages"
        if packages.exists():
            safe_remove_tree(packages, root)
        LOG.info(
            "discarded extraction state created by an older PKG extractor: %s",
            path,
        )
    else:
        recovered = _recover_state_from_manifest(root)
        if recovered is not None:
            _save_state(root, recovered)
            return recovered
        packages = root / "packages"
        if packages.exists():
            safe_remove_tree(packages, root)
            LOG.info(
                "discarded package trees without current extraction metadata: %s",
                packages,
            )
    return {
        "schema_version": EXTRACTION_STATE_SCHEMA_VERSION,
        "extractor_revision": EXTRACTOR_REVISION,
        "packages": {},
        "updated_at": utc_now(),
    }


def _save_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    atomic_write_json(root / ".ps4ffpsc-state.json", state)


def _refresh_package_source_identity(package: dict[str, Any]) -> str:
    source = Path(package["path"])
    current = file_stat_identity(source)
    previous = package.get("source_id") or package.get("scan_id")
    if previous and previous.partition("-")[2] != current.partition("-")[2]:
        raise RuntimeError(
            f"source PKG changed after scanning; scan again: {source}"
        )
    stat_result = source.stat()
    package["source_id"] = current
    package["size"] = stat_result.st_size
    package["source_mtime_ns"] = stat_result.st_mtime_ns
    package.pop("sha256", None)
    package.pop("sha256_verified", None)
    return current


def _verified_resumable_extraction(
    saved: dict[str, Any] | None,
    destination: Path,
) -> dict[str, Any] | None:
    if (
        not isinstance(saved, dict)
        or saved.get("status") != "verified"
        or not destination.is_dir()
        or not saved.get("tree_signature")
    ):
        return None
    saved_destination = saved.get("destination")
    if saved_destination:
        try:
            if Path(saved_destination).resolve() != destination.resolve():
                return None
        except OSError:
            return None
    try:
        if tree_stat_signature(destination) != saved.get("tree_signature"):
            return None
        npbind = destination / "sce_sys" / "npbind.dat"
        if npbind.is_file():
            validate_npbind(npbind)
    except (OSError, TypeError, ValueError):
        return None
    return saved


def unpack_game(settings: Settings, inventory: dict[str, Any], title_id: str) -> dict[str, Any]:
    game = game_or_raise(inventory, title_id)
    if not game["buildable"]:
        raise RuntimeError(f"{title_id} is not buildable: {', '.join(game['conflicts'] or game['warnings'])}")
    root = game_root(settings, game)
    root.mkdir(parents=True, exist_ok=True)
    candidates = [
        item
        for item in [*game["base"], *game["patches"], *game["dlc"]]
        if item.get("supported") and not item.get("duplicate_of")
    ]
    selected = candidates
    for package in selected:
        _refresh_package_source_identity(package)
    state = _load_state(root)
    LOG.info(
        "fast-checking temporary extraction metadata for %d package(s)",
        len(selected),
    )
    resumed: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    for package in selected:
        destination = package_destination(root, package)
        package["extracted_path"] = str(destination)
        source_id = package["source_id"]
        saved = state["packages"].get(source_id)
        reusable = (
            _verified_resumable_extraction(saved, destination)
            if settings.resume and not settings.force
            else None
        )
        if reusable is not None:
            resumed[source_id] = reusable
        else:
            pending.append(package)
    LOG.info(
        "resume preflight: %d verified package(s) reusable, %d package(s) pending",
        len(resumed),
        len(pending),
    )
    if pending:
        check_disk_space(settings.temp_dir, _disk_required(pending, 1.25))
    extractor = extractor_or_raise(settings) if pending else None
    results: list[dict[str, Any]] = []

    selected_total = len(selected)
    source_sizes = [max(0, int(item.get("size", 0))) for item in selected]
    source_total = max(sum(source_sizes), 1)
    completed_source = 0
    for package_index, package in enumerate(selected, start=1):
        package_source_size = source_sizes[package_index - 1]
        destination = package_destination(root, package)
        package["extracted_path"] = str(destination)
        source_id = package["source_id"]
        saved = state["packages"].get(source_id)
        reusable = resumed.get(source_id)
        if reusable is not None:
            results.append(reusable)
            LOG.info("resume: verified package already extracted: %s", package["path"])
            completed_source += package_source_size
            _emit_gui_progress(
                "extract",
                current=completed_source,
                total=source_total,
                package_index=package_index,
                package_total=selected_total,
                package_name=Path(package["path"]).name,
                package_bytes_current=package_source_size,
                package_bytes_total=package_source_size,
                package_source_size=package_source_size,
                resumed=True,
            )
            continue
        if settings.resume and saved and destination.exists():
            LOG.warning(
                "resume: extracted package failed verification and will be recreated: %s",
                destination,
            )
            safe_remove_tree(destination, root)
        if destination.exists() and not settings.force:
            raise FileExistsError(f"extraction destination exists; use --force: {destination}")
        partial = destination.with_name(f"{destination.name}.partial")
        if partial.exists():
            safe_remove_tree(partial, root)
        if destination.exists():
            safe_remove_tree(destination, root)
        if settings.dry_run:
            results.append({"source_id": source_id, "status": "dry_run"})
            continue
        partial.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(extractor),
            "extract",
            package["path"],
            "--output",
            str(partial),
            "--json-progress",
        ]
        LOG.info("extracting %s -> %s", package["path"], partial)

        def extraction_progress(line: str) -> None:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                return
            if not isinstance(event, dict) or event.get("event") not in {
                "extract_start",
                "extract_progress",
                "extract_complete",
            }:
                return
            event_name = str(event.get("event"))
            byte_current = int(
                event.get("bytes_current", event.get("current", 0)) or 0
            )
            byte_total = int(
                event.get("bytes_total", event.get("total", 0)) or 0
            )
            if event_name == "extract_complete":
                package_ratio = 1.0
            elif byte_total > 0:
                package_ratio = max(0.0, min(1.0, byte_current / byte_total))
            else:
                files_current = int(
                    event.get("files_current", event.get("files", 0)) or 0
                )
                files_total = int(event.get("files_total", 0) or 0)
                package_ratio = (
                    max(0.0, min(1.0, files_current / files_total))
                    if files_total > 0
                    else 0.0
                )
            weighted_current = completed_source + round(
                package_source_size * package_ratio
            )
            _emit_gui_progress(
                "extract",
                current=min(weighted_current, source_total),
                total=source_total,
                package_index=package_index,
                package_total=selected_total,
                package_name=Path(package["path"]).name,
                package_bytes_current=max(0, byte_current),
                package_bytes_total=max(0, byte_total),
                package_source_size=package_source_size,
                files_current=int(
                    event.get("files_current", event.get("files", 0)) or 0
                ),
                files_total=int(event.get("files_total", 0) or 0),
            )

        process = _run_captured(
            command,
            stdout_line_callback=extraction_progress,
            forward_stderr=True,
        )
        if process.returncode != 0:
            state["packages"][source_id] = {
                "status": "unsupported_or_encrypted_pkg"
                if process.returncode == 3
                else "failed",
                "path": package["path"],
                "stderr": process.stderr,
                "stdout": process.stdout,
            }
            _save_state(root, state)
            if partial.exists():
                safe_remove_tree(partial, root)
            raise RuntimeError(
                f"extractor failed ({process.returncode}) for {package['path']}: "
                f"{process.stdout.strip() or process.stderr.strip()}"
            )
        npbind_validation: dict[str, Any] | None = None
        extracted_npbind = partial / "sce_sys" / "npbind.dat"
        if extracted_npbind.is_file():
            try:
                npbind_validation = validate_npbind(extracted_npbind)
            except (OSError, ValueError) as error:
                state["packages"][source_id] = {
                    "status": "failed_validation",
                    "path": package["path"],
                    "error": str(error),
                }
                _save_state(root, state)
                safe_remove_tree(partial, root)
                raise RuntimeError(
                    "extracted PKG has invalid sce_sys/npbind.dat: "
                    f"{package['path']}: {error}"
                ) from error
            LOG.info(
                "validated extracted npbind.dat: entries=%d sha1=%s",
                npbind_validation["entry_count"],
                npbind_validation["sha1"],
            )
        manifest = tree_stat_manifest(partial)
        signature = tree_stat_signature(manifest)
        os.replace(partial, destination)
        record = {
            "status": "verified",
            "source_path": package["path"],
            "source_id": source_id,
            "source_size": package.get("size"),
            "source_mtime_ns": package.get("source_mtime_ns"),
            "destination": str(destination),
            "tree_signature": signature,
            "file_count": len(manifest),
            "total_size": sum(int(item["size"]) for item in manifest),
        }
        if npbind_validation is not None:
            record["npbind_validation"] = npbind_validation
        state["packages"][source_id] = record
        _save_state(root, state)
        results.append(record)
        completed_source += package_source_size

    manifest = {
        "schema_version": 1,
        "extractor_revision": EXTRACTOR_REVISION,
        "title_id": title_id,
        "title": game["title"],
        "original_title": game["title"],
        "directory_name": game["directory_name"],
        "packages": selected,
        "extractions": results,
        "updated_at": utc_now(),
    }
    atomic_write_json(root / "manifest.json", manifest)
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    atomic_write_json(reports / "package_inventory.json", game)
    atomic_write_json(inventory_path(settings), inventory)
    return manifest


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _align_existing_path_case(
    destination: Path,
    previous_relative: Path,
    relative: Path,
) -> None:
    if len(previous_relative.parts) != len(relative.parts):
        raise RuntimeError(
            "case-insensitive path collision has incompatible components: "
            f"{previous_relative.as_posix()!r} vs {relative.as_posix()!r}"
        )
    current = destination
    for previous_part, new_part in zip(previous_relative.parts, relative.parts, strict=True):
        previous_path = current / previous_part
        new_path = current / new_part
        ensure_within(destination, previous_path)
        ensure_within(destination, new_path)
        if previous_part != new_part and _path_exists(previous_path):
            if _path_exists(new_path):
                try:
                    same_entry = os.path.samefile(previous_path, new_path)
                except OSError:
                    same_entry = False
                if not same_entry:
                    raise RuntimeError(
                        "cannot apply case-only patch path because both spellings exist: "
                        f"{previous_relative.as_posix()!r} vs {relative.as_posix()!r}"
                    )
            os.rename(previous_path, new_path)
        current = new_path


def _copy_overlay(
    source: Path,
    destination: Path,
    package: dict[str, Any],
    changes: list[dict[str, Any]],
    case_map: dict[str, tuple[str, str]],
) -> dict[str, int]:
    linked = 0
    moved = 0
    copied = 0
    for relative, source_file in sorted(
        iter_tree_files(source), key=lambda item: item[0].as_posix()
    ):
        rel_text = relative.as_posix()
        if any(part == ".DS_Store" or part.startswith("._") for part in relative.parts):
            LOG.warning("ignoring macOS host metadata in extracted tree: %s", source_file)
            continue
        folded = rel_text.casefold()
        package_identity = (
            package.get("source_id")
            or package.get("scan_id")
            or package.get("sha256")
            or package.get("path", "")
        )
        previous = case_map.get(folded)
        case_renamed_from: str | None = None
        if previous is not None and previous[1] != rel_text:
            previous_package, previous_case = previous
            if package.get("kind") != "patch" or previous_package == package_identity:
                raise RuntimeError(
                    f"case-insensitive path collision: {previous_case!r} vs {rel_text!r}"
                )
            _align_existing_path_case(destination, Path(previous_case), relative)
            case_renamed_from = previous_case
            LOG.info(
                "applying patch case-only path replacement: %s -> %s",
                previous_case,
                rel_text,
            )
        case_map[folded] = (package_identity, rel_text)
        target = destination / relative
        ensure_within(destination, target)
        records_change = package.get("kind") != "base"
        previous_size = (
            target.stat().st_size if records_change and target.exists() else None
        )
        new_size = source_file.stat().st_size if records_change else None
        staging_mode = stage_file_atomic(
            source_file, target, consume_source=True
        )
        if staging_mode == "linked":
            linked += 1
        elif staging_mode == "moved":
            moved += 1
        else:
            copied += 1
        if records_change:
            change = {
                "path": rel_text,
                "previous_size": previous_size,
                "new_size": new_size,
                "source_package": package["source_id"],
                "source_app_version": package.get("app_version"),
            }
            if case_renamed_from is not None:
                change["case_renamed_from"] = case_renamed_from
            changes.append(change)
    return {"linked": linked, "moved": moved, "copied": copied}


def merge_game(
    settings: Settings, inventory: dict[str, Any], title_id: str, compat: str | None = None
) -> dict[str, Any]:
    game = game_or_raise(inventory, title_id)
    root = game_root(settings, game)
    manifest_path = root / "manifest.json"
    stale_extraction = (
        not manifest_path.exists()
        or read_json(manifest_path).get("extractor_revision") != EXTRACTOR_REVISION
    )
    if stale_extraction:
        unpack_game(settings, inventory, title_id)
    compat = compat or settings.compat
    base = [item for item in game["base"] if not item.get("duplicate_of")]
    if len(base) != 1 or game["conflicts"]:
        raise RuntimeError(f"{title_id} has no unambiguous base package")
    patches = sorted(
        (item for item in game["patches"] if not item.get("duplicate_of")),
        key=lambda item: version_key(item["app_version"]),
    )
    dlc = [item for item in game["dlc"] if not item.get("duplicate_of")]
    merged = root / "merged"
    app = merged / "app"
    if settings.dry_run:
        return {"title_id": title_id, "status": "dry_run"}
    if stale_extraction and merged.exists():
        safe_remove_tree(merged, root)
        LOG.info(
            "discarded merged data created by an older PKG extractor: %s",
            merged,
        )
    partial = merged / "app.partial"
    addcont = merged / "addcont"
    addcont_partial = merged / "addcont.partial"
    if app.exists() and not settings.force:
        raise FileExistsError(f"merged app exists; use --force: {app}")
    if partial.exists():
        safe_remove_tree(partial, root)
    if addcont_partial.exists():
        safe_remove_tree(addcont_partial, root)
    if app.exists():
        safe_remove_tree(app, root)
    if addcont.exists():
        safe_remove_tree(addcont, root)
    partial.mkdir(parents=True)
    changes: list[dict[str, Any]] = []
    case_map: dict[str, tuple[str, str]] = {}
    overlay_packages = [base[0], *patches, *dlc]
    overlay_total = len(overlay_packages)
    overlay_index = 0
    copy_stats = {"linked": 0, "moved": 0, "copied": 0}

    def merge_package(
        source: Path,
        target: Path,
        package: dict[str, Any],
        target_changes: list[dict[str, Any]],
        target_case_map: dict[str, tuple[str, str]],
    ) -> None:
        nonlocal overlay_index
        stats = _copy_overlay(
            source, target, package, target_changes, target_case_map
        )
        copy_stats["linked"] += stats["linked"]
        copy_stats["moved"] += stats["moved"]
        copy_stats["copied"] += stats["copied"]
        overlay_index += 1
        _emit_gui_progress(
            "merge_package",
            current=overlay_index,
            total=max(overlay_total, 1),
            linked=copy_stats["linked"],
            moved=copy_stats["moved"],
            copied=copy_stats["copied"],
        )

    merge_package(
        package_destination(root, base[0]),
        partial,
        base[0],
        changes,
        case_map,
    )
    for patch in patches:
        merge_package(
            package_destination(root, patch),
            partial,
            patch,
            changes,
            case_map,
        )

    eboot = partial / "eboot.bin"
    param_sfo = partial / "sce_sys" / "param.sfo"
    if not eboot.is_file() or not param_sfo.is_file():
        raise RuntimeError("merged app must contain root eboot.bin and sce_sys/param.sfo")
    values = parse_sfo(param_sfo)
    if values.get("TITLE_ID") != title_id:
        raise RuntimeError(f"merged param.sfo TITLE_ID mismatch: {values.get('TITLE_ID')!r}")
    expected_version = patches[-1]["app_version"] if patches else base[0].get("app_version", "01.00")
    warnings: list[str] = []
    if values.get("APP_VER") != expected_version:
        warnings.append(
            f"merged APP_VER {values.get('APP_VER')!r} does not match latest package {expected_version!r}"
        )
    generated_param_json = False
    normalized_param_json = False
    if compat == "current-smp":
        param_json = partial / "sce_sys" / "param.json"
        existing_param_json = param_json.read_bytes() if param_json.exists() else None
        shadowmount_param_json = build_param_json(
            title_id,
            choose_title(values),
            existing_param_json,
        )
        if existing_param_json != shadowmount_param_json:
            atomic_write_json(
                param_json,
                json.loads(shadowmount_param_json.decode("utf-8")),
            )
            generated_param_json = existing_param_json is None
            normalized_param_json = existing_param_json is not None
        validate_shadowmount_param_json(param_json.read_bytes(), title_id)
    elif compat != "patched-smp":
        raise ValueError(f"unsupported compatibility mode: {compat}")

    addcont_partial.mkdir(parents=True)
    dlc_reports: list[dict[str, Any]] = []
    dlc_labels: dict[str, dict[str, Any]] = {}
    for item in dlc:
        label = item.get("entitlement_label") or f"UNKNOWN-{item['source_id'][-12:]}"
        previous_dlc = dlc_labels.get(label)
        if previous_dlc is not None:
            raise RuntimeError(
                f"conflicting DLC entitlement label {label}: "
                f"{previous_dlc['path']} vs {item['path']}"
            )
        dlc_labels[label] = item
        source = package_destination(root, item)
        target = addcont_partial / label
        target.mkdir(parents=True)
        dlc_changes: list[dict[str, Any]] = []
        merge_package(source, target, item, dlc_changes, {})
        dlc_manifest = tree_stat_manifest(target)
        metadata = {
            "title_id": title_id,
            "content_id": item.get("content_id"),
            "entitlement_label": label,
            "name": item.get("title"),
            "version": item.get("app_version") or item.get("version"),
            "source_pkg_id": item["source_id"],
            "extracted_tree_signature": tree_stat_signature(dlc_manifest),
            "extracted_file_count": len(dlc_manifest),
            "runtime_support_status": "packaged_not_runtime_verified",
        }
        atomic_write_json(target / "ps4ffpsc-dlc.json", metadata)
        dlc_reports.append(metadata)

    os.replace(partial, app)
    os.replace(addcont_partial, addcont)
    report = {
        "schema_version": 1,
        "extractor_revision": EXTRACTOR_REVISION,
        "title_id": title_id,
        "title": game["title"],
        "compatibility": compat,
        "base_package": base[0]["source_id"],
        "patch_order": [
            {"app_version": item["app_version"], "source_id": item["source_id"]}
            for item in patches
        ],
        "latest_app_version": expected_version,
        "overlay_changes": changes,
        "staging_hardlinks": copy_stats["linked"],
        "staging_moves": copy_stats["moved"],
        "staging_copies": copy_stats["copied"],
        "tombstones_applied": False,
        "tombstone_reason": "No explicit deletion metadata was identified in shadPS4 0.7.0 extraction.",
        "delta_patch_warning": any("DELTA_PATCH" in item.get("pkg_flags", []) for item in patches),
        "generated_param_json": generated_param_json,
        "normalized_existing_param_json": normalized_param_json,
        "param_sfo_preserved": True,
        "static_shadowmount_compatible": compat == "current-smp",
        "static_shadowmount_checks_passed": compat == "current-smp",
        "ps5_runtime_verified": False,
        "dlc": dlc_reports,
        "dlc_packaged": bool(dlc_reports),
        "dlc_runtime_supported": False,
        "dlc_runtime_reason": (
            "ShadowMountPlus has no verified PS4 addcont registration/mount workflow."
            if dlc_reports
            else "No DLC packages found."
        ),
        "warnings": warnings,
        "merged_tree_signature": tree_stat_signature(app),
        "completed_at": utc_now(),
    }
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    atomic_write_json(reports / "merge_report.json", report)
    atomic_write_json(
        reports / "compatibility_report.json",
        {
            "compatibility": compat,
            "static_shadowmount_compatible": compat == "current-smp",
            "ps5_runtime_verified": False,
            "required_files": {
                "eboot.bin": eboot.is_file(),
                "sce_sys/param.sfo": param_sfo.is_file(),
                "sce_sys/param.json": (app / "sce_sys" / "param.json").is_file(),
            },
        },
    )
    return report


def _resume_merged_game(
    settings: Settings,
    game: dict[str, Any],
    title_id: str,
) -> dict[str, Any] | None:
    if not settings.resume or settings.force:
        return None
    root = game_root(settings, game)
    app = root / "merged" / "app"
    manifest_path = root / "manifest.json"
    report_path = root / "reports" / "merge_report.json"
    if not app.is_dir() or not manifest_path.is_file() or not report_path.is_file():
        return None
    try:
        manifest = read_json(manifest_path)
        report = read_json(report_path)
        if (
            report.get("title_id") != title_id
            or report.get("compatibility") != settings.compat
            or report.get("extractor_revision") != EXTRACTOR_REVISION
        ):
            return None
        saved_packages = {
            str(Path(item["path"]).resolve()): item
            for item in manifest.get("packages", [])
            if item.get("path")
            and (item.get("source_id") or item.get("scan_id"))
        }
        current_packages = [
            item
            for item in [*game["base"], *game["patches"], *game["dlc"]]
            if item.get("supported") and not item.get("duplicate_of")
        ]
        for package in current_packages:
            source = Path(package["path"]).resolve()
            saved = saved_packages.get(str(source))
            if saved is None:
                return None
            current_id = file_stat_identity(source)
            saved_id = saved.get("source_id") or saved.get("scan_id")
            if saved_id.partition("-")[2] != current_id.partition("-")[2]:
                return None
            stat_result = source.stat()
            package["source_id"] = current_id
            package["size"] = stat_result.st_size
            package["source_mtime_ns"] = stat_result.st_mtime_ns
            package.pop("sha256", None)
            package.pop("sha256_verified", None)
        if (
            not report.get("merged_tree_signature")
            or tree_stat_signature(app) != report.get("merged_tree_signature")
        ):
            return None
        values = parse_sfo(app / "sce_sys" / "param.sfo")
        if values.get("TITLE_ID") != title_id:
            return None
        if settings.compat == "current-smp":
            validate_shadowmount_param_json(
                (app / "sce_sys" / "param.json").read_bytes(), title_id
            )
    except (KeyError, OSError, TypeError, ValueError):
        return None
    LOG.info("resume: verified merged workspace reused: %s", app)
    return report


def _discard_extracted_packages(root: Path) -> None:
    packages = root / "packages"
    if packages.exists():
        safe_remove_tree(packages, root)
        LOG.info("removed extracted package trees after verified merge: %s", packages)


def _utf8_subprocess_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def mkpfs_command(settings: Settings) -> list[str]:
    if is_frozen():
        return [sys.executable, "--mkpfs"]
    candidates = [
        settings.root / ".venv" / "Scripts" / "python.exe",
        settings.root / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        process = subprocess.run(
            [str(candidate), "-X", "utf8", "-c", "import mkpfs; print(mkpfs.__file__)"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_utf8_subprocess_environment(),
        )
        if process.returncode == 0:
            return [str(candidate), "-X", "utf8", "-m", "mkpfs"]
    raise RuntimeError("official MkPFS is not installed; run scripts/bootstrap_macos.sh")


def mkpfs_compression_arguments(
    settings: Settings,
    worker_count: int | None = None,
) -> list[str]:
    level = int(settings.compression_level)
    if not 0 <= level <= 9:
        raise ValueError("compression level must be within 0..9")
    workers = validate_compression_worker_count(
        settings.compression_workers if worker_count is None else worker_count,
        maximum_logical_cpu_count(),
    )
    return [
        "--cpu-count",
        str(workers),
        "--compression-level",
        str(level),
    ]


def _run_captured(
    command: list[str],
    *,
    stdout_line_callback: Any = None,
    forward_stderr: bool = False,
) -> subprocess.CompletedProcess[str]:
    if not _gui_progress_enabled():
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_utf8_subprocess_environment(),
        )

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_utf8_subprocess_environment(),
        bufsize=1,
    )
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []

    def drain_stdout() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            stdout_chunks.append(line)
            if stdout_line_callback is not None:
                try:
                    stdout_line_callback(line)
                except Exception as error:
                    LOG.debug("progress callback failed: %s", error)

    def drain_stderr() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            stderr_chunks.append(line)
            if forward_stderr:
                try:
                    if sys.stderr is not None:
                        sys.stderr.write(line)
                        sys.stderr.flush()
                except OSError:
                    pass

    stdout_thread = threading.Thread(target=drain_stdout, daemon=True)
    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    return_code = process.wait()
    stdout_thread.join()
    stderr_thread.join()
    return subprocess.CompletedProcess(
        command,
        return_code,
        "".join(stdout_chunks),
        "".join(stderr_chunks),
    )


def _run_logged(command: list[str], log_path: Path) -> subprocess.CompletedProcess[str]:
    LOG.info("running: %s", " ".join(json.dumps(part) for part in command))
    process = _run_captured(
        command,
        forward_stderr=True,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(f"$ {' '.join(json.dumps(part) for part in command)}\n")
        stream.write(process.stdout)
        stream.write(process.stderr)
        stream.write(f"\nexit={process.returncode}\n")
    if process.returncode != 0:
        raise RuntimeError(
            f"command failed ({process.returncode}): {process.stdout[-2000:]}{process.stderr[-2000:]}"
        )
    return process


def _files_identical(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as left_stream, right.open("rb") as right_stream:
        while True:
            left_chunk = left_stream.read(4 * 1024 * 1024)
            right_chunk = right_stream.read(4 * 1024 * 1024)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True


def _verify_image(
    settings: Settings,
    image: Path,
    source_dir: Path | None,
    compat: str,
    required_files: list[str] | None = None,
    image_format: str | None = None,
) -> dict[str, Any]:
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    mkpfs = mkpfs_command(settings)
    log_path = settings.root / "logs" / "ps4ffpsc.log"
    verify_command = [*mkpfs, "verify", str(image)]
    if image_format is not None:
        verify_command += [
            "--format",
            "pfs" if image_format == "ffpfsc" else image_format,
        ]
    verify = _run_logged(verify_command, log_path)
    required = list(required_files) if required_files is not None else None
    if required is None:
        required = ["eboot.bin", "sce_sys/param.sfo"]
        if compat == "current-smp":
            required.append("sce_sys/param.json")
        if (
            source_dir is not None
            and (source_dir / "sce_sys" / "npbind.dat").is_file()
        ):
            required.append("sce_sys/npbind.dat")
    optional = (
        []
        if "sce_sys/npbind.dat" in required
        else ["sce_sys/npbind.dat"]
    )
    required_sizes: dict[str, int] = {}
    optional_validated: list[str] = []
    with tempfile.TemporaryDirectory(dir=settings.temp_dir) as temporary:
        extracted = Path(temporary) / "metadata"
        command = [
            *mkpfs,
            "unpack",
            str(image),
            str(extracted),
            "--deep",
            "--no-progress",
        ]
        if image_format is not None:
            command += [
                "--format",
                "pfs" if image_format == "ffpfsc" else image_format,
            ]
        for item in [*required, *optional]:
            command += ["--only", item]
        _run_logged(command, log_path)
        for item in required:
            extracted_file = extracted / item
            if not extracted_file.is_file():
                raise RuntimeError(f"deep unpack did not produce {item}")
            required_sizes[item] = extracted_file.stat().st_size
            if source_dir:
                source_file = source_dir / item
                if not source_file.is_file():
                    raise RuntimeError(f"source tree is missing required file: {item}")
                if source_file.stat().st_size != required_sizes[item]:
                    raise RuntimeError(f"required file size mismatch: {item}")
                if not _files_identical(source_file, extracted_file):
                    raise RuntimeError(
                        f"required file content mismatch: {item}"
                    )
            if item == "sce_sys/npbind.dat":
                try:
                    extracted_validation = validate_npbind(extracted_file)
                    if source_dir:
                        source_validation = validate_npbind(
                            source_dir / item
                        )
                except (OSError, ValueError) as error:
                    raise RuntimeError(
                        f"invalid npbind.dat in verified image: {error}"
                    ) from error
                if (
                    source_dir
                    and source_validation["sha1"]
                    != extracted_validation["sha1"]
                ):
                    raise RuntimeError(
                        "npbind.dat differs between source and verified image"
                    )
        for item in optional:
            extracted_file = extracted / item
            if not extracted_file.is_file():
                continue
            try:
                validate_npbind(extracted_file)
            except (OSError, ValueError) as error:
                raise RuntimeError(
                    f"invalid npbind.dat in verified image: {error}"
                ) from error
            optional_validated.append(item)
        if "sce_sys/param.sfo" in required:
            values = parse_sfo(extracted / "sce_sys" / "param.sfo")
            title_id = values.get("TITLE_ID", "")
            if not validate_title_id(title_id):
                raise RuntimeError("unpacked param.sfo has an invalid TITLE_ID")
            if "sce_sys/param.json" in required:
                validate_shadowmount_param_json(
                    (extracted / "sce_sys" / "param.json").read_bytes(),
                    title_id,
                )
        if "ps4ffpsc-dlc.json" in required:
            json.loads((extracted / "ps4ffpsc-dlc.json").read_text(encoding="utf-8"))
    return {
        "verified": True,
        "verification_mode": (
            "exfat_and_required_files"
            if image_format == "exfat"
            else "container_and_required_files"
        ),
        "mkpfs_output": verify.stdout.strip(),
        "required_files": required,
        "required_file_sizes": required_sizes,
        "optional_files_validated": optional_validated,
    }


def _artifact_extension(output_format: str) -> str:
    if output_format not in OUTPUT_FORMATS:
        raise ValueError(f"unsupported output format: {output_format}")
    return f".{output_format}"


def _artifact_sidecar_path(output: Path, suffix: str) -> Path:
    return output.with_name(f"{output.name}{suffix}")


def _detect_artifact_format(path: Path) -> str:
    with path.open("rb") as stream:
        header = stream.read(11)
    return "exfat" if header[3:11] == b"EXFAT   " else "ffpfsc"


def _pack_directory_command(
    settings: Settings,
    mkpfs: list[str],
    source: Path,
    destination: Path,
    compression_workers: int | None,
    *,
    require_game_files: bool = False,
) -> list[str]:
    if settings.output_format == "exfat":
        return [
            *mkpfs,
            "pack",
            "exfat",
            str(source),
            str(destination),
            "--cluster-size",
            "65536",
        ]
    if compression_workers is None:
        raise ValueError("FFPFSC packing requires a compression worker count")
    command = [
        *mkpfs,
        "pack",
        "folder",
        "--no-adjust-output-file-extension",
        "--version",
        "PS5",
        "--inode-bits",
        "32",
        *mkpfs_compression_arguments(settings, compression_workers),
        "--temp-folder",
        str(settings.temp_dir),
    ]
    if require_game_files:
        command.append("--require-game-files")
    return [*command, str(source), str(destination)]


def _pack_dlc_separate(
    settings: Settings,
    game: dict[str, Any],
    merged_root: Path,
    mkpfs: list[str],
    log_path: Path,
    compression_workers: int | None,
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for item in (entry for entry in game["dlc"] if not entry.get("duplicate_of")):
        label = item.get("entitlement_label") or f"UNKNOWN-{item['source_id'][-12:]}"
        source = merged_root / "addcont" / label
        if not source.is_dir():
            continue
        output = settings.output_dir / (
            f"{game['directory_name']} [DLC {label}]"
            f"{_artifact_extension(settings.output_format)}"
        )
        if output.exists() and not settings.force:
            raise FileExistsError(f"DLC output exists; use --force: {output}")
        partial = output.with_name(f"{output.name}.partial")
        if partial.exists():
            partial.unlink()
        command = _pack_directory_command(
            settings,
            mkpfs,
            source,
            partial,
            compression_workers,
        )
        _run_logged(command, log_path)
        verification = _verify_image(
            settings,
            partial,
            source,
            "patched-smp",
            required_files=["ps4ffpsc-dlc.json"],
            image_format=settings.output_format,
        )
        os.replace(partial, output)
        checksum_path = output.with_name(f"{output.name}.sha256")
        if checksum_path.exists():
            checksum_path.unlink()
        artifacts.append(
            {
                "path": str(output),
                "sha256": None,
                "checksum_generated": False,
                "entitlement_label": label,
                "runtime_supported": False,
                "output_format": settings.output_format,
                "compression_level": (
                    settings.compression_level
                    if settings.output_format == "ffpfsc"
                    else None
                ),
                "compression_workers": compression_workers,
                "verification": verification,
            }
        )
    return artifacts


def build_game(
    settings: Settings,
    title_id: str,
    inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if settings.output_format not in OUTPUT_FORMATS:
        raise ValueError(f"unsupported output format: {settings.output_format}")
    if settings.output_format == "exfat" and settings.keep_inner_image:
        raise ValueError("--keep-inner-image applies only to FFPFSC output")
    configure_logging(settings, title_id)
    LOG.info("build started: %s", title_id)
    if inventory is None:
        inventory = load_or_scan(settings, refresh=True)
    game = game_or_raise(inventory, title_id)
    if not game["buildable"]:
        raise RuntimeError(f"{title_id} skipped: {game['conflicts'] or game['warnings']}")
    root = game_root(settings, game)
    patches = sorted(
        (item for item in game["patches"] if not item.get("duplicate_of")),
        key=lambda item: version_key(item["app_version"]),
    )
    base = [item for item in game["base"] if not item.get("duplicate_of")]
    version = (
        patches[-1]["app_version"]
        if patches
        else base[0].get("app_version", "01.00")
    )
    filename = (
        f"{game['directory_name']} [v{version}]"
        f"{_artifact_extension(settings.output_format)}"
    )
    output = settings.output_dir / filename
    partial = output.with_name(f"{output.name}.partial")
    root_resolved = root.resolve(strict=False)
    output_resolved = output.resolve(strict=False)
    if output_resolved == root_resolved or root_resolved in output_resolved.parents:
        raise ValueError(
            "output directory must not be inside the temporary game workspace"
        )
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    if output.exists() and not settings.force:
        raise FileExistsError(f"output exists; use --force: {output}")

    LOG.info("stage 1/5: checking source metadata and extracting selected packages")
    merge_report = _resume_merged_game(settings, game, title_id)
    if merge_report is None:
        stale_merge = root / "merged"
        if settings.resume and not settings.force and stale_merge.exists():
            safe_remove_tree(stale_merge, root)
            LOG.warning("discarded an invalid resumable merge: %s", stale_merge)
        unpack_game(settings, inventory, title_id)
        LOG.info("stage 2/5: merging base and ordered patches")
        merge_report = merge_game(settings, inventory, title_id, settings.compat)
        if not settings.dry_run:
            _discard_extracted_packages(root)
    else:
        LOG.info("stage 2/5: reusing verified merged app")
    if settings.dry_run:
        return merge_report
    app = root / "merged" / "app"
    version = merge_report["latest_app_version"]
    if partial.exists():
        partial.unlink()
    mkpfs = mkpfs_command(settings)
    log_path = settings.root / "logs" / "ps4ffpsc.log"
    compression_workers: int | None = None
    compression_workers_mode = "not_applicable"
    compression_arguments: list[str] = []
    if settings.output_format == "ffpfsc":
        compression_workers = validate_compression_worker_count(
            settings.compression_workers,
            maximum_logical_cpu_count(),
        )
        compression_workers_mode = (
            "automatic_half_available_logical_cpus"
            if settings.compression_workers is None
            else "selected"
        )
        compression_arguments = mkpfs_compression_arguments(
            settings,
            compression_workers,
        )
        LOG.info(
            "MkPFS compression: level %d, workers %d (%s)",
            settings.compression_level,
            compression_workers,
            compression_workers_mode,
        )
    else:
        LOG.info("MkPFS output: uncompressed exFAT, cluster size 65536 bytes")
    inner_image: Path | None = None
    if settings.output_format == "ffpfsc" and settings.keep_inner_image:
        inner_image = output.with_name(f"{output.stem}.inner.exfat")
        if inner_image.exists() and not settings.force:
            raise FileExistsError(
                f"inner image exists; use --force: {inner_image}"
            )
        inner_partial = inner_image.with_name(f"{inner_image.name}.partial")
        if inner_partial.exists():
            inner_partial.unlink()
        _run_logged(
            [
                *mkpfs,
                "pack",
                "exfat",
                str(app),
                str(inner_partial),
                "--cluster-size",
                "65536",
                "--no-progress",
            ],
            log_path,
        )
        os.replace(inner_partial, inner_image)
        command = [
            *mkpfs,
            "pack",
            "file",
            "--no-adjust-output-file-extension",
            "--version",
            "PS5",
            "--inode-bits",
            "32",
            *compression_arguments,
            "--temp-folder",
            str(settings.temp_dir),
            str(inner_image),
            str(partial),
        ]
    else:
        command = _pack_directory_command(
            settings,
            mkpfs,
            app,
            partial,
            compression_workers,
            require_game_files=settings.compat == "current-smp",
        )
    LOG.info(
        "stage 3/5: %s",
        "creating compressed FFPFSC image"
        if settings.output_format == "ffpfsc"
        else "creating uncompressed exFAT image",
    )
    _run_logged(command, log_path)
    LOG.info("stage 4/5: verifying the image and required files")
    verification = _verify_image(
        settings,
        partial,
        app,
        settings.compat,
        image_format=settings.output_format,
    )
    os.replace(partial, output)
    dlc_artifacts: list[dict[str, Any]] = []
    if settings.include_dlc == "separate" and game["dlc"]:
        dlc_artifacts = _pack_dlc_separate(
            settings,
            game,
            root / "merged",
            mkpfs,
            log_path,
            compression_workers,
        )
    LOG.info("stage 5/5: publishing output and cleaning temporary files")
    checksum_path = output.with_name(f"{output.name}.sha256")
    if checksum_path.exists():
        checksum_path.unlink()
    artifact_manifest = {
        "schema_version": 1,
        "extractor_revision": EXTRACTOR_REVISION,
        "artifact": str(output),
        "sha256": None,
        "checksum_generated": False,
        "size": output.stat().st_size,
        "title_id": title_id,
        "title": game["title"],
        "app_version": version,
        "compatibility": settings.compat,
        "include_dlc": settings.include_dlc,
        "source_packages": [
            {
                "path": item["path"],
                "source_id": item["source_id"],
                "size": item.get("size"),
                "source_mtime_ns": item.get("source_mtime_ns"),
                "kind": item["kind"],
                "app_version": item.get("app_version"),
            }
            for item in [*game["base"], *game["patches"], *game["dlc"]]
            if not item.get("duplicate_of")
        ],
        "inner_filesystem": "exfat",
        "kept_inner_image": str(inner_image) if inner_image else None,
        "output_format": settings.output_format,
        "outer_container": (
            "compressed_pfs"
            if settings.output_format == "ffpfsc"
            else None
        ),
        "compression_level": (
            settings.compression_level
            if settings.output_format == "ffpfsc"
            else None
        ),
        "compression_workers": compression_workers,
        "compression_workers_mode": compression_workers_mode,
        "extra_top_level_directory": False,
        "verification": verification,
        "static_shadowmount_compatible": settings.compat == "current-smp",
        "ps5_runtime_verified": False,
        "dlc_packaged": bool(game["dlc"]),
        "dlc_in_main_ffpfsc": False,
        "dlc_in_main_artifact": False,
        "dlc_runtime_supported": False,
        "dlc_artifacts": dlc_artifacts,
        "dlc_runtime_reason": (
            "Separate DLC images are verified but PS4 addcont mount/registration is not."
            if dlc_artifacts
            else "Bundle mode requires a companion ShadowMountPlus implementation and was not emitted."
            if game["dlc"] and settings.include_dlc == "bundle"
            else "DLC was prepared during the verified merge; temporary staging was removed."
            if game["dlc"]
            else "No DLC packages found."
        ),
        "temporary_workspace_cleaned": False,
        "completed_at": utc_now(),
    }
    manifest_path = _artifact_sidecar_path(output, ".manifest.json")
    atomic_write_json(manifest_path, artifact_manifest)
    shadow_path = _artifact_sidecar_path(output, ".shadowmount.txt")
    shadow_path.write_text(
        "\n".join(
            [
                f"Title: {game['title']}",
                f"TITLE_ID: {title_id}",
                f"APP_VER: {version}",
                "PKG: "
                + ", ".join(
                    item["source_id"]
                    for item in [*game["base"], *game["patches"]]
                    if not item.get("duplicate_of")
                ),
                "DLC: "
                + (
                    ", ".join(item.get("entitlement_label") or "unknown" for item in game["dlc"])
                    or "none"
                ),
                f"Compatibility: {settings.compat}",
                f"Output format: {settings.output_format}",
                (
                    f"Compression level: {settings.compression_level}"
                    if settings.output_format == "ffpfsc"
                    else "Compression: not applicable (raw exFAT)"
                ),
                (
                    f"Compression workers: {compression_workers} "
                    f"({compression_workers_mode})"
                    if settings.output_format == "ffpfsc"
                    else "Compression workers: not applicable"
                ),
                "Recommended USB path: /mnt/usb0/ps4ffpsc/" + output.name,
                "manual.lst: /mnt/usb0/ps4ffpsc/" + output.name,
                "Expected ShadowMountPlus checks: nested exFAT mount, root sce_sys/param.json, "
                "titleId parse, appmeta staging",
                "static_shadowmount_compatible="
                + str(settings.compat == "current-smp").lower(),
                "ps5_runtime_verified=false",
                "DLC runtime support is not verified; temporary DLC staging is removed after success.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _emit_gui_progress("cleanup", current=0, total=1)
    safe_remove_tree(root, settings.unpacked_dir)
    artifact_manifest["temporary_workspace_cleaned"] = True
    atomic_write_json(manifest_path, artifact_manifest)
    _emit_gui_progress("cleanup", current=1, total=1)
    LOG.info("temporary game workspace removed after successful build: %s", root)
    LOG.info("build completed: %s", output)
    return artifact_manifest


def verify_artifact(settings: Settings, path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    image_format = _detect_artifact_format(path)
    result = _verify_image(
        settings,
        path,
        None,
        settings.compat,
        image_format=image_format,
    )
    result.update({"path": str(path), "sha256": sha256_file(path), "size": path.stat().st_size})
    return result


def doctor(settings: Settings) -> dict[str, Any]:
    extractor = find_extractor(settings.root, settings.resource_root)
    resources = settings.resource_root or settings.root
    shad_source = resources / "third_party" / "shadps4_pkg" / "core" / "file_format" / "pkg.cpp"
    checks: dict[str, Any] = {
        "python": {
            "ok": sys.version_info >= (3, 11),
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "architecture": {
            "ok": platform.machine() in {"arm64", "aarch64", "x86_64", "AMD64"},
            "value": platform.machine(),
        },
        "compiler": {
            "ok": is_frozen() or bool(shutil.which("clang++") or shutil.which("g++")),
            "required": not is_frozen(),
        },
        "cmake": {
            "ok": is_frozen() or bool(shutil.which("cmake")),
            "required": not is_frozen(),
        },
        "shadps4_source": {
            "ok": shad_source.is_file() or (is_frozen() and extractor is not None),
            "path": str(shad_source) if shad_source.is_file() else None,
            "embedded_snapshot": is_frozen(),
        },
        "extractor": {"ok": extractor is not None, "path": str(extractor) if extractor else None},
        "pkg_dir": {"ok": settings.pkg_dir.is_dir(), "path": str(settings.pkg_dir)},
        "free_space": {
            "ok": shutil.disk_usage(settings.root).free >= 2 * 1024**3,
            "bytes": shutil.disk_usage(settings.root).free,
        },
        "temp_dir": {"ok": False, "path": str(settings.temp_dir)},
        "long_files": {"ok": False},
        "mkpfs": {"ok": False},
    }
    try:
        settings.temp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=settings.temp_dir, prefix="ps4ffpsc-doctor-", delete=True):
            pass
        checks["temp_dir"]["ok"] = True
        sparse = settings.temp_dir / "ps4ffpsc-sparse-test"
        with sparse.open("wb") as stream:
            stream.seek(4 * 1024**3)
            stream.write(b"\0")
        checks["long_files"]["ok"] = sparse.stat().st_size > 4 * 1024**3
        sparse.unlink()
    except OSError as error:
        checks["temp_dir"]["error"] = str(error)
    try:
        mkpfs = mkpfs_command(settings)
        process = subprocess.run(
            [*mkpfs, "-V"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_utf8_subprocess_environment(),
        )
        checks["mkpfs"] = {
            "ok": process.returncode == 0,
            "version": (process.stdout or process.stderr).strip(),
            "command": mkpfs,
        }
    except RuntimeError as error:
        checks["mkpfs"]["error"] = str(error)
    return {"ok": all(value.get("ok", False) for value in checks.values()), "checks": checks}


def status(settings: Settings) -> dict[str, Any]:
    states: list[dict[str, Any]] = []
    if settings.unpacked_dir.exists():
        for path in settings.unpacked_dir.glob("*/.ps4ffpsc-state.json"):
            states.append({"path": str(path), "state": read_json(path)})
    partials = [
        str(path)
        for base in (settings.unpacked_dir, settings.output_dir, settings.work_dir)
        if base.exists()
        for path in base.rglob("*.partial")
    ]
    return {"states": states, "partials": partials}


def clean_work(settings: Settings) -> dict[str, Any]:
    if not settings.work_dir.exists():
        return {"removed": False, "path": str(settings.work_dir)}
    ensure_within(settings.root, settings.work_dir)
    if settings.work_dir == settings.root:
        raise ValueError("work directory cannot be the project root")
    safe_remove_tree(settings.work_dir, settings.root)
    return {"removed": True, "path": str(settings.work_dir)}

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
from .runtime import is_frozen
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
            resume=bool(
                getattr(args, "resume", False)
                or (extract.get("resume", True) and not getattr(args, "no_resume", False))
            ),
            force=bool(getattr(args, "force", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
            json_output=bool(getattr(args, "json", False)),
            verbose=bool(getattr(args, "verbose", False)),
            keep_inner_image=bool(
                getattr(args, "keep_inner_image", False) or pack.get("keep_inner_image", False)
            ),
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


def _load_state(root: Path) -> dict[str, Any]:
    path = root / ".ps4ffpsc-state.json"
    if path.exists():
        state = read_json(path)
        if state.get("schema_version") == 2:
            return state
        LOG.info("ignoring legacy hash-based extraction state: %s", path)
    return {"schema_version": 2, "packages": {}, "updated_at": utc_now()}


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
    check_disk_space(settings.temp_dir, _disk_required(selected, 1.25))
    extractor = extractor_or_raise(settings)
    state = _load_state(root)
    results: list[dict[str, Any]] = []

    selected_total = len(selected)
    for package_index, package in enumerate(selected, start=1):
        destination = package_destination(root, package)
        package["extracted_path"] = str(destination)
        source_id = package["source_id"]
        saved = state["packages"].get(source_id)
        if (
            settings.resume
            and saved
            and saved.get("status") == "verified"
            and destination.is_dir()
            and saved.get("tree_signature")
            and tree_stat_signature(destination) == saved.get("tree_signature")
        ):
            results.append(saved)
            LOG.info("resume: verified package already extracted: %s", package["path"])
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
            current = int(event.get("current", event.get("files", 0)) or 0)
            total = int(event.get("total", event.get("files", 0)) or 0)
            _emit_gui_progress(
                "extract",
                current=current,
                total=max(total, 1),
                package_index=package_index,
                package_total=selected_total,
                package_name=Path(package["path"]).name,
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
        manifest = tree_stat_manifest(partial)
        signature = tree_stat_signature(manifest)
        os.replace(partial, destination)
        record = {
            "status": "verified",
            "source_path": package["path"],
            "source_id": source_id,
            "destination": str(destination),
            "tree_signature": signature,
            "file_count": len(manifest),
            "total_size": sum(int(item["size"]) for item in manifest),
        }
        state["packages"][source_id] = record
        _save_state(root, state)
        results.append(record)

    manifest = {
        "schema_version": 1,
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
    if not manifest_path.exists():
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
    partial = merged / "app.partial"
    addcont = merged / "addcont"
    addcont_partial = merged / "addcont.partial"
    if app.exists() and not settings.force:
        raise FileExistsError(f"merged app exists; use --force: {app}")
    if settings.dry_run:
        return {"title_id": title_id, "status": "dry_run"}
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
    if compat == "current-smp":
        param_json = partial / "sce_sys" / "param.json"
        if param_json.exists():
            validate_shadowmount_param_json(param_json.read_bytes(), title_id)
        else:
            param_json.write_bytes(build_param_json(title_id, choose_title(values)))
            generated_param_json = True
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


def _verify_image(
    settings: Settings,
    image: Path,
    source_dir: Path | None,
    compat: str,
    required_files: list[str] | None = None,
) -> dict[str, Any]:
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    mkpfs = mkpfs_command(settings)
    log_path = settings.root / "logs" / "ps4ffpsc.log"
    verify_command = [*mkpfs, "verify", str(image)]
    verify = _run_logged(verify_command, log_path)
    required = required_files
    if required is None:
        required = ["eboot.bin", "sce_sys/param.sfo"]
        if compat == "current-smp":
            required.append("sce_sys/param.json")
    required_sizes: dict[str, int] = {}
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
        for item in required:
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
        "verification_mode": "container_and_required_files",
        "mkpfs_output": verify.stdout.strip(),
        "required_files": required,
        "required_file_sizes": required_sizes,
    }


def _pack_dlc_separate(
    settings: Settings,
    game: dict[str, Any],
    merged_root: Path,
    mkpfs: list[str],
    log_path: Path,
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for item in (entry for entry in game["dlc"] if not entry.get("duplicate_of")):
        label = item.get("entitlement_label") or f"UNKNOWN-{item['source_id'][-12:]}"
        source = merged_root / "addcont" / label
        if not source.is_dir():
            continue
        output = settings.output_dir / f"{game['directory_name']} [DLC {label}].ffpfsc"
        partial = output.with_name(f"{output.name}.partial")
        if partial.exists():
            partial.unlink()
        command = [
            *mkpfs,
            "pack",
            "folder",
            "--no-adjust-output-file-extension",
            "--version",
            "PS5",
            "--inode-bits",
            "32",
            "--cpu-count",
            str(settings.jobs),
            "--temp-folder",
            str(settings.temp_dir),
            str(source),
            str(partial),
        ]
        _run_logged(command, log_path)
        verification = _verify_image(
            settings,
            partial,
            source,
            "patched-smp",
            required_files=["ps4ffpsc-dlc.json"],
        )
        if output.exists():
            if not settings.force:
                raise FileExistsError(f"DLC output exists; use --force: {output}")
            output.unlink()
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
                "verification": verification,
            }
        )
    return artifacts


def build_game(
    settings: Settings,
    title_id: str,
    inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    filename = f"{game['directory_name']} [v{version}].ffpfsc"
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
    check_disk_space(settings.temp_dir, _disk_required([*game["base"], *game["patches"]], 2.2))
    mkpfs = mkpfs_command(settings)
    log_path = settings.root / "logs" / "ps4ffpsc.log"
    inner_image: Path | None = None
    if settings.keep_inner_image:
        inner_image = output.with_name(f"{output.stem}.inner.exfat")
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
        if inner_image.exists():
            if not settings.force:
                raise FileExistsError(f"inner image exists; use --force: {inner_image}")
            inner_image.unlink()
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
            "--cpu-count",
            str(settings.jobs),
            "--temp-folder",
            str(settings.temp_dir),
            str(inner_image),
            str(partial),
        ]
    else:
        command = [
            *mkpfs,
            "pack",
            "folder",
            "--no-adjust-output-file-extension",
            "--version",
            "PS5",
            "--inode-bits",
            "32",
            "--cpu-count",
            str(settings.jobs),
            "--temp-folder",
            str(settings.temp_dir),
        ]
        if settings.compat == "current-smp":
            command.append("--require-game-files")
        command += [str(app), str(partial)]
    LOG.info("stage 3/5: creating compressed FFPFSC image")
    _run_logged(command, log_path)
    LOG.info("stage 4/5: verifying the container and required files")
    verification = _verify_image(settings, partial, app, settings.compat)
    if output.exists():
        output.unlink()
    os.replace(partial, output)
    dlc_artifacts: list[dict[str, Any]] = []
    if settings.include_dlc == "separate" and game["dlc"]:
        dlc_artifacts = _pack_dlc_separate(settings, game, root / "merged", mkpfs, log_path)
    LOG.info("stage 5/5: publishing output and cleaning temporary files")
    checksum_path = output.with_name(f"{output.name}.sha256")
    if checksum_path.exists():
        checksum_path.unlink()
    artifact_manifest = {
        "schema_version": 1,
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
        "outer_container": "compressed_pfs",
        "extra_top_level_directory": False,
        "verification": verification,
        "static_shadowmount_compatible": settings.compat == "current-smp",
        "ps5_runtime_verified": False,
        "dlc_packaged": bool(game["dlc"]),
        "dlc_in_main_ffpfsc": False,
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
    manifest_path = output.with_suffix(".manifest.json")
    atomic_write_json(manifest_path, artifact_manifest)
    shadow_path = output.with_suffix(".shadowmount.txt")
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
    result = _verify_image(settings, path, None, settings.compat)
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

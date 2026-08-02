from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .dlc_license import entitlement_key_fingerprint, parse_dlc_license
from .self_format import SelfIdentity, unwrap_fake_self, wrap_fake_self
from .util import ensure_within, iter_tree_files, safe_remove_tree, stage_file_atomic


DLC_MODE_OFF = "off"
DLC_MODE_SINGLE_EXPERIMENTAL = "single-experimental"
DLC_MODES = {DLC_MODE_OFF, DLC_MODE_SINGLE_EXPERIMENTAL}
_MAXIMUM_DLC_COUNT = 2500
_MODULE_NAME = "dlcldr.prx"
LOG = logging.getLogger("ps4ffpsc")


@dataclass(frozen=True, slots=True)
class PlannedDlc:
    label: str
    package_type: str
    source_id: str
    source_tree: Path
    content_id: str
    entitlement_key: bytes = field(repr=False)
    key_fingerprint: str
    secret_was_encrypted: bool
    package_type_inferred: bool
    data_files: tuple[tuple[Path, Path], ...]
    data_size: int


class DlcEmbedError(RuntimeError):
    pass


def _package_type(item: dict[str, Any]) -> tuple[str, bool]:
    value = item.get("dlc_package_type")
    if value in {"PSAC", "PSAL"}:
        return str(value), False
    category = str(item.get("category") or item.get("original_category") or "").lower()
    if item.get("source_kind") == "dump_tree" and category in {"ac", "al"}:
        return ("PSAC" if category == "ac" else "PSAL"), True
    raise DlcEmbedError(
        "DLC package type is unavailable; rescan the source with the 0.2.8 "
        "extractor or use a dump whose param.sfo CATEGORY is ac/al"
    )


def _data_files(source: Path) -> tuple[tuple[Path, Path], ...]:
    result: list[tuple[Path, Path]] = []
    for relative, path in sorted(
        iter_tree_files(source), key=lambda item: item[0].as_posix()
    ):
        if relative.parts[0].casefold() == "sce_sys":
            continue
        if relative == Path("ps4ffpsc-dlc.json"):
            continue
        if any(part == ".DS_Store" or part.startswith("._") for part in relative.parts):
            continue
        result.append((relative, path))
    return tuple(result)


def plan_experimental_dlc(
    addcont_root: Path,
    dlc_items: list[dict[str, Any]],
) -> list[PlannedDlc]:
    planned: list[PlannedDlc] = []
    seen_labels: set[str] = set()
    selected = [item for item in dlc_items if not item.get("duplicate_of")]
    if len(selected) > _MAXIMUM_DLC_COUNT:
        raise DlcEmbedError(
            f"experimental single-image mode supports at most {_MAXIMUM_DLC_COUNT} DLC entries"
        )

    for item in selected:
        label = str(item.get("entitlement_label") or "")
        if len(label) != 16 or any(
            not (character.isascii() and (character.isupper() or character.isdigit() or character == "_"))
            for character in label
        ):
            raise DlcEmbedError(f"invalid DLC entitlement label: {label!r}")
        if label in seen_labels:
            raise DlcEmbedError(f"conflicting DLC entitlement label: {label}")
        seen_labels.add(label)

        package_type, inferred = _package_type(item)
        source = addcont_root / label
        ensure_within(addcont_root, source)
        if not source.is_dir():
            raise DlcEmbedError(f"merged DLC tree is missing: {source}")
        license_path = source / "sce_sys" / "license.dat"
        if not license_path.is_file():
            raise DlcEmbedError(f"DLC license.dat is missing for {label}")
        license_info = parse_dlc_license(
            license_path,
            expected_package_type=package_type,
            expected_content_id=str(item.get("content_id") or "") or None,
        )
        files = _data_files(source)
        if package_type == "PSAL" and files:
            raise DlcEmbedError(
                f"license-only DLC {label} unexpectedly contains game data"
            )
        planned.append(
            PlannedDlc(
                label=label,
                package_type=package_type,
                source_id=str(item.get("source_id") or ""),
                source_tree=source,
                content_id=license_info.content_id,
                entitlement_key=license_info.entitlement_key,
                key_fingerprint=entitlement_key_fingerprint(
                    license_info.entitlement_key
                ),
                secret_was_encrypted=license_info.secret_was_encrypted,
                package_type_inferred=inferred,
                data_files=files,
                data_size=sum(path.stat().st_size for _relative, path in files),
            )
        )

    planned.sort(
        key=lambda item: (
            0 if item.package_type == "PSAC" else 1,
            item.label,
            item.source_id,
        )
    )
    return planned


def find_dlc_helper(resource_root: Path) -> Path:
    override = os.environ.get("PS4FFPSC_DLC_HELPER")
    executable_name = "ps4-dlc-patch.exe" if sys.platform == "win32" else "ps4-dlc-patch"
    candidates = [
        Path(override).expanduser() if override else None,
        resource_root / "bin" / executable_name,
        resource_root / "build-release" / "dlc-helper" / executable_name,
        resource_root / "build-release-windows" / "dlc-helper" / executable_name,
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        path = candidate.resolve(strict=False)
        if path.is_file() and (sys.platform == "win32" or os.access(path, os.X_OK)):
            return path
    raise DlcEmbedError(
        "experimental DLC helper is unavailable; reinstall the complete 0.2.8 application"
    )


def _invoke_helper(
    helper: Path,
    elf_path: Path,
    output_dir: Path,
    planned: list[PlannedDlc],
) -> tuple[Path, Path, dict[str, Any]]:
    private_json = json.dumps(
        [
            {
                "label": item.label,
                "type": item.package_type,
                "key": item.entitlement_key.hex(),
            }
            for item in planned
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    process = subprocess.run(
        [
            str(helper),
            "--input",
            str(elf_path),
            "--output-dir",
            str(output_dir),
            "--dlc-json",
            "-",
        ],
        input=private_json,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    result: dict[str, Any] = {}
    for line in reversed(process.stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            result = candidate
            break
    if process.returncode != 0 or result.get("status") != "ok":
        code = result.get("code", "patch_failed")
        message = result.get(
            "message",
            "the game executable is not compatible with the strict experimental DLC method",
        )
        raise DlcEmbedError(f"experimental DLC transformation failed ({code}): {message}")

    def returned_file(key: str, expected_name: str) -> Path:
        raw = result.get(key)
        if not isinstance(raw, str):
            raise DlcEmbedError(f"experimental DLC helper omitted {key}")
        path = Path(raw).resolve(strict=True)
        ensure_within(output_dir, path)
        if path.name != expected_name or not path.is_file() or path.is_symlink():
            raise DlcEmbedError(f"experimental DLC helper returned an invalid {key}")
        return path

    return (
        returned_file("patched_elf", elf_path.name),
        returned_file("prx", _MODULE_NAME),
        result,
    )


def _stage_dlc_directories(
    layout_root: Path,
    planned: list[PlannedDlc],
) -> tuple[list[tuple[Path, Path]], list[dict[str, Any]]]:
    publications: list[tuple[Path, Path]] = []
    report_entries: list[dict[str, Any]] = []
    data_index = 0
    for index, item in enumerate(planned):
        mount_path: str | None = None
        staged_directory: Path | None = None
        if item.package_type == "PSAC":
            mount_name = f"dlc{index:02d}"
            mount_path = f"/app0/{mount_name}"
            staged_directory = layout_root / mount_name
            staged_directory.mkdir(parents=True, exist_ok=False)
            for relative, source_file in item.data_files:
                target = staged_directory / relative
                ensure_within(staged_directory, target)
                stage_file_atomic(source_file, target)
            data_index += 1
        report_entries.append(
            {
                "index": index,
                "label": item.label,
                "package_type": item.package_type,
                "package_type_inferred": item.package_type_inferred,
                "mount_path": mount_path,
                "content_id": item.content_id,
                "source_id": item.source_id,
                "data_file_count": len(item.data_files),
                "data_size": item.data_size,
                "key_present": True,
                "key_sha256": item.key_fingerprint,
                "license_secret_encrypted": item.secret_was_encrypted,
            }
        )
        if staged_directory is not None:
            publications.append((staged_directory, Path(staged_directory.name)))
    if data_index != sum(item.package_type == "PSAC" for item in planned):
        raise AssertionError("DLC data directory count mismatch")
    return publications, report_entries


def embed_experimental_dlc(
    app: Path,
    addcont_root: Path,
    dlc_items: list[dict[str, Any]],
    work_root: Path,
    resource_root: Path,
    *,
    helper_runner: Callable[
        [Path, Path, Path, list[PlannedDlc]], tuple[Path, Path, dict[str, Any]]
    ] = _invoke_helper,
) -> dict[str, Any]:
    """Embed selected DLC into one app tree using the strict experimental method."""

    planned = plan_experimental_dlc(addcont_root, dlc_items)
    if not planned:
        return {
            "mode": DLC_MODE_SINGLE_EXPERIMENTAL,
            "experimental": True,
            "applied": False,
            "dlc_count": 0,
            "runtime_verified": False,
            "entries": [],
        }

    eboot = app / "eboot.bin"
    if not eboot.is_file() or eboot.is_symlink():
        raise DlcEmbedError("merged app has no regular root eboot.bin")
    module_destination = app / _MODULE_NAME
    backup = app / ".eboot.bin.ps4ffpsc-dlc-backup"
    if module_destination.exists() or backup.exists():
        raise DlcEmbedError(
            "merged app already contains files reserved by experimental DLC mode"
        )

    helper = find_dlc_helper(resource_root)
    if work_root.exists():
        safe_remove_tree(work_root, work_root.parent)
    helper_output = work_root / "helper-output"
    layout_root = work_root / "layout"
    helper_output.mkdir(parents=True)
    layout_root.mkdir(parents=True)
    published_paths: list[Path] = []
    eboot_replaced = False
    try:
        source_self = eboot.read_bytes()
        source_elf, identity = unwrap_fake_self(source_self)
        if not isinstance(identity, SelfIdentity):
            raise DlcEmbedError("could not preserve executable identity")
        elf_path = work_root / "eboot.elf"
        elf_path.write_bytes(source_elf)
        patched_elf_path, module_path, helper_report = helper_runner(
            helper,
            elf_path,
            helper_output,
            planned,
        )
        patched_self = wrap_fake_self(patched_elf_path.read_bytes(), identity)
        staged_eboot = work_root / "eboot.bin"
        staged_eboot.write_bytes(patched_self)
        staged_module = work_root / _MODULE_NAME
        stage_file_atomic(module_path, staged_module)
        directory_publications, entries = _stage_dlc_directories(
            layout_root,
            planned,
        )

        for staged, relative_destination in directory_publications:
            destination = app / relative_destination
            ensure_within(app, destination)
            if destination.exists():
                raise DlcEmbedError(
                    f"merged app already contains reserved DLC directory {destination.name}"
                )

        os.replace(eboot, backup)
        os.replace(staged_eboot, eboot)
        eboot_replaced = True
        os.replace(staged_module, module_destination)
        published_paths.append(module_destination)
        for staged, relative_destination in directory_publications:
            destination = app / relative_destination
            os.replace(staged, destination)
            published_paths.append(destination)

        if addcont_root.exists():
            safe_remove_tree(addcont_root, addcont_root.parent)
        backup.unlink()
        return {
            "mode": DLC_MODE_SINGLE_EXPERIMENTAL,
            "experimental": True,
            "applied": True,
            "method": str(helper_report.get("method") or "strict_prx"),
            "dlc_count": len(planned),
            "data_dlc_count": sum(
                item.package_type == "PSAC" for item in planned
            ),
            "license_only_count": sum(
                item.package_type == "PSAL" for item in planned
            ),
            "module_path": f"/app0/{_MODULE_NAME}",
            "runtime_verified": False,
            "entries": entries,
        }
    except Exception as error:
        rollback_errors: list[Exception] = []
        try:
            if eboot_replaced:
                eboot.unlink(missing_ok=True)
            if backup.exists():
                os.replace(backup, eboot)
        except Exception as rollback_error:
            rollback_errors.append(rollback_error)
        for path in reversed(published_paths):
            try:
                if path.is_dir():
                    safe_remove_tree(path, app)
                else:
                    path.unlink(missing_ok=True)
            except Exception as rollback_error:
                rollback_errors.append(rollback_error)
        if rollback_errors:
            raise DlcEmbedError(
                "experimental DLC transformation failed and temporary app "
                "cleanup was incomplete"
            ) from error
        raise
    finally:
        if work_root.exists():
            # A failure to remove scratch files must not turn an already
            # committed app transformation into a reported build failure.  At
            # this point eboot.bin, the module and DLC directories may all be
            # published and the original backup may already be gone, so there
            # is no safe rollback left to perform.  The enclosing per-game
            # workspace cleanup gets another chance to remove this directory
            # after the verified image is published.
            try:
                safe_remove_tree(work_root, work_root.parent)
            except OSError as cleanup_error:
                LOG.warning(
                    "could not remove experimental DLC scratch directory %s: %s",
                    work_root,
                    cleanup_error,
                )

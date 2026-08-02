from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .sfo import choose_title, parse_sfo
from .util import (
    content_id_parts,
    tree_stat_manifest,
    tree_stat_signature,
    validate_title_id,
)

LOG = logging.getLogger("ps4ffpsc")


class DumpSourceError(ValueError):
    """Raised when a selected unpacked game tree is incomplete or ambiguous."""


def _text(values: dict[str, Any], key: str, default: str = "") -> str:
    value = values.get(key)
    return value.strip() if isinstance(value, str) else default


def _tree_record(
    path: Path,
    *,
    kind: str,
    layout: str,
    require_eboot: bool,
) -> dict[str, Any]:
    source = path.expanduser().resolve()
    if not source.is_dir():
        raise DumpSourceError(f"dump source directory does not exist: {source}")
    if require_eboot and not (source / "eboot.bin").is_file():
        raise DumpSourceError(f"dump source has no root eboot.bin: {source}")
    param_sfo = source / "sce_sys" / "param.sfo"
    if not param_sfo.is_file():
        raise DumpSourceError(f"dump source has no sce_sys/param.sfo: {source}")

    values = parse_sfo(param_sfo)
    title_id = _text(values, "TITLE_ID")
    if not validate_title_id(title_id):
        raise DumpSourceError(
            f"dump param.sfo has invalid TITLE_ID {title_id!r}: {param_sfo}"
        )
    content_id = _text(values, "CONTENT_ID")
    content_parts = content_id_parts(content_id)
    if content_id and content_parts is None:
        raise DumpSourceError(
            f"dump param.sfo has invalid CONTENT_ID {content_id!r}: {param_sfo}"
        )
    if content_parts is not None and title_id not in content_parts[1]:
        raise DumpSourceError(
            f"dump CONTENT_ID does not match TITLE_ID {title_id}: {param_sfo}"
        )

    LOG.info("reading unpacked game tree metadata: %s", source)
    manifest = tree_stat_manifest(source)
    if not manifest:
        raise DumpSourceError(f"dump source is empty: {source}")
    signature = tree_stat_signature(manifest)
    stat_result = source.stat()
    category = _text(values, "CATEGORY")
    localized_titles = {
        key: value
        for key, value in values.items()
        if key.startswith("TITLE_") and isinstance(value, str) and value.strip()
    }
    return {
        "path": str(source),
        "supported": True,
        "source_kind": "dump_tree",
        "source_layout": layout,
        "source_id": signature,
        "tree_signature": signature,
        "source_mtime_ns": stat_result.st_mtime_ns,
        "size": sum(int(item["size"]) for item in manifest),
        "file_count": len(manifest),
        "title_id": title_id,
        "title": choose_title(values),
        "category": category,
        "original_category": category,
        "content_id": content_id,
        "app_version": _text(values, "APP_VER", "01.00"),
        "version": _text(values, "VERSION", "01.00"),
        "system_version": values.get("SYSTEM_VER"),
        "pkg_flags": [],
        "kind": kind,
        "entitlement_label": content_parts[2] if kind == "dlc" and content_parts else "",
        "localized_titles": localized_titles,
        "validation_errors": [],
    }


def discover_dump_records(selected: Path) -> list[dict[str, Any]]:
    """Inspect a flat dump or an app/patch dumper container without reading payload data.

    Supported layouts are:

    * ``<selected>/eboot.bin`` plus ``<selected>/sce_sys/param.sfo``;
    * ``<selected>/app`` and optional ``<selected>/patch``;
    * optional immediate ``<selected>/addcont/<label>`` DLC trees.

    A flat tree is treated as an already consolidated application, even when its
    final overlay SFO has CATEGORY=gp. The original CATEGORY is retained in the
    record for diagnostics.
    """

    root = selected.expanduser().resolve()
    if not root.is_dir():
        raise DumpSourceError(f"dump source directory does not exist: {root}")

    records: list[dict[str, Any]] = []
    if (root / "eboot.bin").is_file() and (root / "sce_sys" / "param.sfo").is_file():
        records.append(
            _tree_record(
                root,
                kind="base",
                layout="consolidated",
                require_eboot=True,
            )
        )
        records[0]["selected_root"] = str(root)
        return records

    app = root / "app"
    if not app.is_dir():
        raise DumpSourceError(
            "selected dump must be a flat game root or contain an app directory: "
            f"{root}"
        )
    records.append(
        _tree_record(app, kind="base", layout="dumper_app", require_eboot=True)
    )

    patch = root / "patch"
    if patch.exists():
        records.append(
            _tree_record(
                patch,
                kind="patch",
                layout="dumper_patch",
                require_eboot=False,
            )
        )

    addcont = root / "addcont"
    if addcont.exists():
        if not addcont.is_dir():
            raise DumpSourceError(f"dump addcont path is not a directory: {addcont}")
        for child in sorted(addcont.iterdir(), key=lambda item: item.name.casefold()):
            if not child.is_dir():
                continue
            records.append(
                _tree_record(
                    child,
                    kind="dlc",
                    layout="dumper_addcont",
                    require_eboot=False,
                )
            )

    title_ids = {str(record["title_id"]) for record in records if record["kind"] != "dlc"}
    if len(title_ids) != 1:
        raise DumpSourceError(
            f"dump app and patch TITLE_ID values do not match: {sorted(title_ids)}"
        )
    title_id = next(iter(title_ids))
    for record in records:
        record["selected_root"] = str(root)
        if record["title_id"] != title_id:
            raise DumpSourceError(
                "dump DLC TITLE_ID does not match the selected game: "
                f"{record['path']}"
            )
    return records

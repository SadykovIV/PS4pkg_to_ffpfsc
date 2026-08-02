from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

TITLE_ID_RE = re.compile(r"^CUSA\d{5}$")
VERSION_RE = re.compile(r"^\d+(?:\.\d+)*$")
ENTITLEMENT_RE = re.compile(r"^[A-Z0-9_]{16}$")
INVALID_COMPONENT_RE = re.compile(r'[/\\:*?"<>|\x00-\x1f\x7f]')


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_file(
    path: Path,
    chunk_size: int = 4 * 1024 * 1024,
    progress: Callable[[int, int], None] | None = None,
) -> str:
    digest = hashlib.sha256()
    total = path.stat().st_size
    processed = 0
    if progress:
        progress(0, total)
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
            processed += len(chunk)
            if progress:
                progress(processed, total)
    return digest.hexdigest()


def file_stat_identity(path: Path) -> str:
    """Return a cheap identity derived from path, size and mtime, not file contents."""
    resolved = path.resolve()
    stat_result = resolved.stat()
    material = (
        f"{resolved}\0{stat_result.st_size}\0{stat_result.st_mtime_ns}"
    ).encode("utf-8", errors="surrogateescape")
    return "stat-" + hashlib.sha256(material).hexdigest()


def sanitize_component(value: str, fallback: str, max_chars: int = 120) -> str:
    normalized = unicodedata.normalize("NFC", value)
    normalized = INVALID_COMPONENT_RE.sub("_", normalized).rstrip(" .")
    if normalized in {"", ".", ".."}:
        normalized = fallback
    if len(normalized) > max_chars:
        suffix = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
        normalized = f"{normalized[: max_chars - 9]}-{suffix}"
    return normalized


def version_key(value: str) -> tuple[int, ...]:
    if not VERSION_RE.fullmatch(value):
        raise ValueError(f"invalid numeric version: {value!r}")
    return tuple(int(component) for component in value.split("."))


def validate_title_id(value: str) -> bool:
    return bool(TITLE_ID_RE.fullmatch(value))


def content_id_parts(value: str) -> tuple[str, str, str] | None:
    parts = value.split("-")
    if len(parts) != 3:
        return None
    region, title_part, label = parts
    if not region or not title_part or not ENTITLEMENT_RE.fullmatch(label):
        return None
    return region, title_part, label


def entitlement_label(value: str) -> str | None:
    parts = content_id_parts(value)
    return parts[2] if parts else None


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.partial")
    with partial.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(partial, path)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def ensure_within(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve(strict=False)
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise ValueError(f"path escapes destination: {candidate}")
    return candidate_resolved


def path_is_within(candidate: Path, parent: Path) -> bool:
    """Return whether candidate is parent itself or a descendant, after resolution."""
    candidate_resolved = candidate.expanduser().resolve(strict=False)
    parent_resolved = parent.expanduser().resolve(strict=False)
    return candidate_resolved == parent_resolved or parent_resolved in candidate_resolved.parents


def paths_overlap(first: Path, second: Path) -> bool:
    """Return whether two resolved paths contain one another."""
    return path_is_within(first, second) or path_is_within(second, first)


def iter_tree_files(root: Path) -> Iterable[tuple[Path, Path]]:
    if root.is_symlink():
        raise ValueError(f"symlink tree root is forbidden: {root}")
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in list(dirnames):
            child = directory_path / name
            if child.is_symlink():
                raise ValueError(f"directory symlink is forbidden: {child}")
        for name in filenames:
            path = directory_path / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
                raise ValueError(f"non-regular extracted entry is forbidden: {path}")
            relative = path.relative_to(root)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe relative path: {relative}")
            ensure_within(root, path)
            yield relative, path


def tree_manifest(root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    casefolded: dict[str, str] = {}
    for relative, path in sorted(
        iter_tree_files(root), key=lambda item: item[0].as_posix()
    ):
        if any(part == ".DS_Store" or part.startswith("._") for part in relative.parts):
            continue
        rel_text = relative.as_posix()
        folded = unicodedata.normalize("NFC", rel_text).casefold()
        previous = casefolded.get(folded)
        if previous is not None and previous != rel_text:
            raise ValueError(
                f"case-insensitive path collision: {previous!r} vs {rel_text!r}"
            )
        casefolded[folded] = rel_text
        result.append({"path": rel_text, "size": path.stat().st_size, "sha256": sha256_file(path)})
    return result


def tree_stat_manifest(root: Path) -> list[dict[str, Any]]:
    """Describe a tree without reading file payloads."""
    result: list[dict[str, Any]] = []
    casefolded: dict[str, str] = {}
    for relative, path in sorted(iter_tree_files(root), key=lambda item: item[0].as_posix()):
        if any(part == ".DS_Store" or part.startswith("._") for part in relative.parts):
            continue
        rel_text = relative.as_posix()
        folded = unicodedata.normalize("NFC", rel_text).casefold()
        previous = casefolded.get(folded)
        if previous is not None and previous != rel_text:
            raise ValueError(f"case-insensitive path collision: {previous!r} vs {rel_text!r}")
        casefolded[folded] = rel_text
        stat_result = path.stat()
        result.append(
            {
                "path": rel_text,
                "size": stat_result.st_size,
                "mtime_ns": stat_result.st_mtime_ns,
            }
        )
    return result


def tree_stat_signature(manifest_or_root: Iterable[dict[str, Any]] | Path) -> str:
    """Hash tree metadata only; file contents are never opened."""
    manifest = (
        tree_stat_manifest(manifest_or_root)
        if isinstance(manifest_or_root, Path)
        else manifest_or_root
    )
    digest = hashlib.sha256()
    for entry in manifest:
        digest.update(entry["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry["size"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(entry.get("mtime_ns", 0)).encode("ascii"))
        digest.update(b"\n")
    return "stat-" + digest.hexdigest()


def tree_sha256_from_manifest(manifest: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in manifest:
        digest.update(entry["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry["size"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(entry["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def tree_sha256(root: Path) -> str:
    return tree_sha256_from_manifest(tree_manifest(root))


def safe_remove_tree(path: Path, allowed_parent: Path) -> None:
    ensure_within(allowed_parent, path)
    if path == allowed_parent.resolve():
        raise ValueError("refusing to remove the allowed parent itself")
    if path.is_symlink():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def copy_file_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    ensure_within(destination.parents[len(destination.parents) - 1], destination)
    partial = destination.with_name(f"{destination.name}.partial")
    shutil.copy2(source, partial, follow_symlinks=False)
    os.replace(partial, destination)


def stage_file_atomic(
    source: Path,
    destination: Path,
    *,
    consume_source: bool = False,
) -> str:
    """Stage a file atomically using link, move, then copy as available."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f"{destination.name}.partial")
    if partial.exists():
        partial.unlink()
    try:
        os.link(source, partial, follow_symlinks=False)
        mode = "linked"
    except OSError:
        if consume_source:
            try:
                os.replace(source, partial)
                mode = "moved"
            except OSError:
                shutil.copy2(source, partial, follow_symlinks=False)
                mode = "copied"
        else:
            shutil.copy2(source, partial, follow_symlinks=False)
            mode = "copied"
    os.replace(partial, destination)
    return mode


def link_or_copy_file_atomic(source: Path, destination: Path) -> bool:
    """Atomically hardlink a file, falling back to a portable copy."""
    return stage_file_atomic(source, destination) == "linked"

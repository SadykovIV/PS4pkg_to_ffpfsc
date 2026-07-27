from __future__ import annotations

import json
from pathlib import Path

from ps4ffpsc import inventory as inventory_module
from ps4ffpsc.inventory import find_extractor, scan_packages


def _record(path: Path, sha: str, kind: str, title_id: str = "CUSA12345") -> dict:
    return {
        "path": str(path),
        "sha256": sha,
        "supported": True,
        "title_id": title_id,
        "title": f"Игра {title_id}",
        "category": {"base": "gd", "patch": "gp", "dlc": "ac"}[kind],
        "content_id": f"EP9000-{title_id}_00-ABCDEFGHIJKLMNOP",
        "app_version": "01.00" if kind == "base" else "01.10",
        "version": "01.00",
        "system_version": "0x02508000",
        "pkg_flags": ["CUMULATIVE_PATCH"] if kind == "patch" else [],
        "kind": kind,
        "entitlement_label": "ABCDEFGHIJKLMNOP",
        "size": 1024,
        "package_digest": sha,
        "localized_titles": {},
    }


def test_find_extractor_accepts_bundled_windows_executable(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    extractor = resources / "bin" / "ps4_pkg_extract.exe"
    extractor.parent.mkdir(parents=True)
    extractor.write_bytes(b"MZ")

    assert find_extractor(tmp_path, resources) == extractor


def test_fast_metadata_duplicate_is_unchecked_candidate_without_full_hashing(
    monkeypatch, tmp_path: Path
) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    files = [pkg / "a.pkg", pkg / "b.PKG"]
    for path in files:
        path.write_bytes(b"x")
    records = {str(path): _record(path, "a" * 64, "base") for path in files}
    monkeypatch.setattr(
        inventory_module,
        "inspect_package",
        lambda _extractor, path, compute_sha256=False: dict(records[str(path)]),
    )
    result = scan_packages(tmp_path, pkg, tmp_path / "unpacked", tmp_path / "helper")
    game = result["games"]["CUSA12345"]
    assert game["buildable"]
    assert game["conflicts"] == []
    assert "duplicate_of" not in game["base"][0]
    assert game["base"][1]["duplicate_of"] == str(files[0].resolve())
    assert (
        game["base"][1]["duplicate_match"]
        == "package_digest_metadata_and_size"
    )
    assert all("sha256" not in item for item in game["base"])
    assert all(item["source_id"].startswith("stat-") for item in game["base"])


def test_conflicting_bases_and_orphan_patch(monkeypatch, tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    inputs = {
        pkg / "a.pkg": _record(pkg / "a.pkg", "a" * 64, "base"),
        pkg / "b.pkg": _record(pkg / "b.pkg", "b" * 64, "base"),
        pkg / "orphan.pkg": _record(pkg / "orphan.pkg", "c" * 64, "patch", "CUSA54321"),
    }
    for path in inputs:
        path.write_bytes(b"x")
    monkeypatch.setattr(
        inventory_module,
        "inspect_package",
        lambda _extractor, path, compute_sha256=False: dict(inputs[path]),
    )
    result = scan_packages(tmp_path, pkg, tmp_path / "unpacked", tmp_path / "helper")
    assert "conflicting_base_packages" in result["games"]["CUSA12345"]["conflicts"]
    assert "orphan_package" in result["games"]["CUSA54321"]["warnings"]


def test_equal_metadata_and_size_with_different_package_digests_are_not_duplicates(
    monkeypatch, tmp_path: Path
) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    files = [pkg / "part1.pkg", pkg / "part2.pkg"]
    records = {
        str(files[0]): _record(files[0], "a" * 64, "base"),
        str(files[1]): _record(files[1], "b" * 64, "base"),
    }
    for path in files:
        path.write_bytes(b"x")
    monkeypatch.setattr(
        inventory_module,
        "inspect_package",
        lambda _extractor, path, compute_sha256=False: dict(records[str(path)]),
    )

    result = scan_packages(
        tmp_path,
        pkg,
        tmp_path / "unpacked",
        tmp_path / "helper",
    )

    game = result["games"]["CUSA12345"]
    assert not game["buildable"]
    assert "conflicting_base_packages" in game["conflicts"]
    assert all("duplicate_of" not in package for package in game["base"])


def test_explicit_pkg_files_override_recursive_directory(monkeypatch, tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    selected_dir = tmp_path / "selected"
    pkg.mkdir()
    selected_dir.mkdir()
    ignored = pkg / "ignored.pkg"
    selected = selected_dir / "selected.PKG"
    ignored.write_bytes(b"ignored")
    selected.write_bytes(b"selected")
    visited: list[Path] = []
    hash_modes: list[bool] = []

    def inspect(_extractor: Path, path: Path, compute_sha256: bool = False) -> dict:
        visited.append(path)
        hash_modes.append(compute_sha256)
        return _record(path, "d" * 64, "base")

    monkeypatch.setattr(inventory_module, "inspect_package", inspect)
    result = scan_packages(
        tmp_path,
        pkg,
        tmp_path / "unpacked",
        tmp_path / "helper",
        (selected,),
    )
    assert visited == [selected.resolve()]
    assert hash_modes == [False]
    assert result["source_mode"] == "selected_files"
    assert result["selected_pkg_files"] == [str(selected.resolve())]

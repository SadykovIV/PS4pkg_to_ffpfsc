from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ps4ffpsc import dlc_embed
from ps4ffpsc.dlc_embed import DlcEmbedError, embed_experimental_dlc, plan_experimental_dlc
from ps4ffpsc.self_format import SelfIdentity


DEBUG_KEY = bytes.fromhex("96c2268d69261c8b1e3b6bff2fe04e12")


def _license(content_id: str, content_type: int, key: bytes) -> bytes:
    data = bytearray(0x400)
    data[:4] = b"RIF\0"
    content_raw = content_id.encode("ascii").ljust(48, b"\0")
    data[0x20:0x50] = content_raw
    data[0x54:0x56] = content_type.to_bytes(2, "big")
    iv = bytes(range(16))
    data[0x260:0x270] = iv
    secret = bytearray(0x90)
    secret[:16] = hashlib.sha256(content_raw).digest()[16:32]
    secret[0x70:0x80] = key
    encryptor = Cipher(algorithms.AES(DEBUG_KEY), modes.CBC(iv)).encryptor()
    data[0x270:0x300] = encryptor.update(bytes(secret)) + encryptor.finalize()
    return bytes(data)


def _add_dlc(
    addcont: Path,
    index: int,
    package_type: str,
    *,
    with_data: bool,
) -> dict[str, object]:
    label = f"DLC{index:013d}"
    content_id = f"EP0000-CUSA12345_00-{label}"
    root = addcont / label
    (root / "sce_sys").mkdir(parents=True)
    (root / "sce_sys" / "license.dat").write_bytes(
        _license(
            content_id,
            0x1B if package_type == "PSAC" else 0x1C,
            index.to_bytes(16, "big"),
        )
    )
    (root / "sce_sys" / "param.sfo").write_bytes(b"metadata")
    (root / "ps4ffpsc-dlc.json").write_text("{}", encoding="utf-8")
    if with_data:
        (root / "songs").mkdir()
        (root / "songs" / f"track-{index}.bin").write_bytes(
            f"track {index}".encode("ascii")
        )
    return {
        "kind": "dlc",
        "source_id": f"stat-{index:04d}",
        "source_kind": "pkg",
        "entitlement_label": label,
        "content_id": content_id,
        "dlc_package_type": package_type,
        "pkg_content_type": 0x1B if package_type == "PSAC" else 0x1C,
    }


def test_plan_orders_psac_before_psal_and_excludes_metadata(tmp_path: Path) -> None:
    addcont = tmp_path / "addcont"
    psal = _add_dlc(addcont, 0, "PSAL", with_data=False)
    psac = _add_dlc(addcont, 1, "PSAC", with_data=True)

    plan = plan_experimental_dlc(addcont, [psal, psac])

    assert [item.package_type for item in plan] == ["PSAC", "PSAL"]
    assert [relative.as_posix() for relative, _path in plan[0].data_files] == [
        "songs/track-1.bin"
    ]
    assert plan[1].data_files == ()


def test_plan_supports_245_unique_entries_deterministically(tmp_path: Path) -> None:
    addcont = tmp_path / "addcont"
    items = [
        _add_dlc(addcont, index, "PSAC", with_data=False)
        for index in reversed(range(245))
    ]

    plan = plan_experimental_dlc(addcont, items)

    assert len(plan) == 245
    assert plan[0].label == "DLC0000000000000"
    assert plan[-1].label == "DLC0000000000244"


def test_empty_selection_is_an_explicit_noop(tmp_path: Path) -> None:
    app = tmp_path / "app"
    app.mkdir()
    result = embed_experimental_dlc(
        app,
        tmp_path / "addcont",
        [],
        tmp_path / "work",
        tmp_path,
    )
    assert result["applied"] is False
    assert result["experimental"] is True
    assert result["dlc_count"] == 0


def test_helper_receives_entitlement_data_only_through_stdin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    addcont = tmp_path / "addcont"
    item = _add_dlc(addcont, 9, "PSAC", with_data=True)
    planned = plan_experimental_dlc(addcont, [item])
    helper = tmp_path / "ps4-dlc-patch"
    helper.write_bytes(b"helper")
    elf = tmp_path / "eboot.elf"
    elf.write_bytes(b"elf")
    output = tmp_path / "output"
    output.mkdir()
    patched = output / "eboot.elf"
    module = output / "dlcldr.prx"
    patched.write_bytes(b"patched")
    module.write_bytes(b"module")
    observed: dict[str, object] = {}

    def fake_run(arguments, **kwargs):
        observed["arguments"] = arguments
        observed["input"] = kwargs.get("input")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "ok",
                    "patched_elf": str(patched),
                    "prx": str(module),
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(dlc_embed.subprocess, "run", fake_run)

    result = dlc_embed._invoke_helper(helper, elf, output, planned)

    assert result[0] == patched
    assert result[1] == module
    assert observed["arguments"][-2:] == ["--dlc-json", "-"]
    request = json.loads(str(observed["input"]))
    assert request == [
        {
            "label": "DLC0000000000009",
            "type": "PSAC",
            "key": (9).to_bytes(16, "big").hex(),
        }
    ]
    assert not list(output.parent.glob("dlc-*.json"))


def test_embed_builds_one_app_layout_without_persisting_raw_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "eboot.bin").write_bytes(b"original self")
    addcont = tmp_path / "addcont"
    psal = _add_dlc(addcont, 8, "PSAL", with_data=False)
    psac = _add_dlc(addcont, 7, "PSAC", with_data=True)
    helper = tmp_path / "ps4-dlc-patch"
    helper.write_bytes(b"helper")
    helper.chmod(0o755)
    monkeypatch.setattr(dlc_embed, "find_dlc_helper", lambda _root: helper)
    identity = SelfIdentity(0x3800000000000001, 1, 0x1000000000000, 0)
    monkeypatch.setattr(
        dlc_embed,
        "unwrap_fake_self",
        lambda source: (b"original elf", identity),
    )
    monkeypatch.setattr(
        dlc_embed,
        "wrap_fake_self",
        lambda source, preserved: b"patched self",
    )

    def fake_helper(_helper, elf_path, output_dir, planned):
        patched = output_dir / elf_path.name
        patched.write_bytes(b"patched elf")
        module = output_dir / "dlcldr.prx"
        module.write_bytes(b"configured module")
        return patched, module, {"status": "ok", "method": "strict_prx"}

    result = embed_experimental_dlc(
        app,
        addcont,
        [psal, psac],
        tmp_path / "work",
        tmp_path,
        helper_runner=fake_helper,
    )

    assert (app / "eboot.bin").read_bytes() == b"patched self"
    assert (app / "dlcldr.prx").read_bytes() == b"configured module"
    assert (app / "dlc00" / "songs" / "track-7.bin").is_file()
    assert not (app / "dlc00" / "sce_sys").exists()
    assert not (app / "dlc01").exists()
    assert not addcont.exists()
    assert not (tmp_path / "work").exists()
    assert result["data_dlc_count"] == 1
    assert result["license_only_count"] == 1
    serialized = str(result)
    assert bytes.fromhex("00" * 15 + "07").hex() not in serialized
    assert all(entry["key_present"] for entry in result["entries"])


def test_embed_rolls_back_eboot_when_reserved_directory_collides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "eboot.bin").write_bytes(b"original self")
    (app / "dlc00").mkdir()
    addcont = tmp_path / "addcont"
    item = _add_dlc(addcont, 3, "PSAC", with_data=True)
    helper = tmp_path / "ps4-dlc-patch"
    helper.write_bytes(b"helper")
    helper.chmod(0o755)
    monkeypatch.setattr(dlc_embed, "find_dlc_helper", lambda _root: helper)
    identity = SelfIdentity(0x3800000000000001, 1, 0x1000000000000, 0)
    monkeypatch.setattr(
        dlc_embed, "unwrap_fake_self", lambda source: (b"elf", identity)
    )
    monkeypatch.setattr(dlc_embed, "wrap_fake_self", lambda source, ident: b"new")

    def fake_helper(_helper, elf_path, output_dir, planned):
        patched = output_dir / elf_path.name
        patched.write_bytes(b"patched elf")
        module = output_dir / "dlcldr.prx"
        module.write_bytes(b"configured module")
        return patched, module, {"status": "ok"}

    with pytest.raises(DlcEmbedError, match="reserved DLC directory"):
        embed_experimental_dlc(
            app,
            addcont,
            [item],
            tmp_path / "work",
            tmp_path,
            helper_runner=fake_helper,
        )

    assert (app / "eboot.bin").read_bytes() == b"original self"
    assert not (app / "dlcldr.prx").exists()
    assert addcont.exists()
    assert not (tmp_path / "work").exists()


def test_embed_restores_eboot_when_addcont_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "eboot.bin").write_bytes(b"original self")
    addcont = tmp_path / "addcont"
    item = _add_dlc(addcont, 4, "PSAC", with_data=True)
    helper = tmp_path / "ps4-dlc-patch"
    helper.write_bytes(b"helper")
    helper.chmod(0o755)
    monkeypatch.setattr(dlc_embed, "find_dlc_helper", lambda _root: helper)
    identity = SelfIdentity(0x3800000000000001, 1, 0x1000000000000, 0)
    monkeypatch.setattr(
        dlc_embed,
        "unwrap_fake_self",
        lambda source: (b"original elf", identity),
    )
    monkeypatch.setattr(
        dlc_embed,
        "wrap_fake_self",
        lambda source, preserved: b"patched self",
    )

    def fake_helper(_helper, elf_path, output_dir, planned):
        patched = output_dir / elf_path.name
        patched.write_bytes(b"patched elf")
        module = output_dir / "dlcldr.prx"
        module.write_bytes(b"configured module")
        return patched, module, {"status": "ok", "method": "strict_prx"}

    original_remove = dlc_embed.safe_remove_tree

    def fail_addcont_cleanup(path: Path, boundary: Path) -> None:
        if path == addcont:
            raise OSError("simulated addcont cleanup failure")
        original_remove(path, boundary)

    monkeypatch.setattr(dlc_embed, "safe_remove_tree", fail_addcont_cleanup)

    with pytest.raises(OSError, match="simulated addcont cleanup failure"):
        embed_experimental_dlc(
            app,
            addcont,
            [item],
            tmp_path / "work",
            tmp_path,
            helper_runner=fake_helper,
        )

    assert (app / "eboot.bin").read_bytes() == b"original self"
    assert not (app / "dlcldr.prx").exists()
    assert not (app / "dlc00").exists()
    assert not (app / ".eboot.bin.ps4ffpsc-dlc-backup").exists()
    assert addcont.exists()
    assert not (tmp_path / "work").exists()


def test_embed_restores_eboot_before_reporting_incomplete_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "eboot.bin").write_bytes(b"original self")
    addcont = tmp_path / "addcont"
    item = _add_dlc(addcont, 5, "PSAC", with_data=True)
    helper = tmp_path / "ps4-dlc-patch"
    helper.write_bytes(b"helper")
    helper.chmod(0o755)
    monkeypatch.setattr(dlc_embed, "find_dlc_helper", lambda _root: helper)
    identity = SelfIdentity(0x3800000000000001, 1, 0x1000000000000, 0)
    monkeypatch.setattr(
        dlc_embed,
        "unwrap_fake_self",
        lambda source: (b"original elf", identity),
    )
    monkeypatch.setattr(
        dlc_embed,
        "wrap_fake_self",
        lambda source, preserved: b"patched self",
    )

    def fake_helper(_helper, elf_path, output_dir, planned):
        patched = output_dir / elf_path.name
        patched.write_bytes(b"patched elf")
        module = output_dir / "dlcldr.prx"
        module.write_bytes(b"configured module")
        return patched, module, {"status": "ok", "method": "strict_prx"}

    original_remove = dlc_embed.safe_remove_tree

    def fail_two_cleanups(path: Path, boundary: Path) -> None:
        if path == addcont:
            raise OSError("simulated addcont cleanup failure")
        if path == app / "dlc00":
            raise OSError("simulated published directory cleanup failure")
        original_remove(path, boundary)

    monkeypatch.setattr(dlc_embed, "safe_remove_tree", fail_two_cleanups)

    with pytest.raises(DlcEmbedError, match="cleanup was incomplete"):
        embed_experimental_dlc(
            app,
            addcont,
            [item],
            tmp_path / "work",
            tmp_path,
            helper_runner=fake_helper,
        )

    assert (app / "eboot.bin").read_bytes() == b"original self"
    assert not (app / ".eboot.bin.ps4ffpsc-dlc-backup").exists()
    assert not (app / "dlcldr.prx").exists()
    assert (app / "dlc00").is_dir()
    assert addcont.exists()
    assert not (tmp_path / "work").exists()


def test_committed_embed_is_not_reported_failed_when_scratch_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = tmp_path / "app"
    app.mkdir()
    (app / "eboot.bin").write_bytes(b"original self")
    addcont = tmp_path / "addcont"
    item = _add_dlc(addcont, 6, "PSAC", with_data=True)
    helper = tmp_path / "ps4-dlc-patch"
    helper.write_bytes(b"helper")
    helper.chmod(0o755)
    monkeypatch.setattr(dlc_embed, "find_dlc_helper", lambda _root: helper)
    identity = SelfIdentity(0x3800000000000001, 1, 0x1000000000000, 0)
    monkeypatch.setattr(
        dlc_embed,
        "unwrap_fake_self",
        lambda source: (b"original elf", identity),
    )
    monkeypatch.setattr(
        dlc_embed,
        "wrap_fake_self",
        lambda source, preserved: b"patched self",
    )

    def fake_helper(_helper, elf_path, output_dir, planned):
        patched = output_dir / elf_path.name
        patched.write_bytes(b"patched elf")
        module = output_dir / "dlcldr.prx"
        module.write_bytes(b"configured module")
        return patched, module, {"status": "ok", "method": "strict_prx"}

    work = tmp_path / "work"
    original_remove = dlc_embed.safe_remove_tree

    def fail_only_scratch_cleanup(path: Path, boundary: Path) -> None:
        if path == work:
            raise OSError("simulated scratch cleanup failure")
        original_remove(path, boundary)

    monkeypatch.setattr(dlc_embed, "safe_remove_tree", fail_only_scratch_cleanup)

    result = embed_experimental_dlc(
        app,
        addcont,
        [item],
        work,
        tmp_path,
        helper_runner=fake_helper,
    )

    assert result["applied"] is True
    assert (app / "eboot.bin").read_bytes() == b"patched self"
    assert (app / "dlcldr.prx").read_bytes() == b"configured module"
    assert (app / "dlc00" / "songs" / "track-6.bin").is_file()
    assert not addcont.exists()
    assert work.exists()

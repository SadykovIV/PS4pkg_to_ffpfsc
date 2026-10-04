# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parents[1]

HELPER = ROOT / "build" / "tools" / "ps4_pkg_extract" / "ps4_pkg_extract"
LOCALES = ROOT / "tools" / "ps4ffpsc" / "ps4ffpsc" / "locales"

hidden = collect_submodules("mkpfs") + [
    "isal.isal_zlib",
    "zlib_ng.zlib_ng",
]

a = Analysis(
    [str(ROOT / "packaging" / "linux" / "app_entry.py")],
    pathex=[
        str(ROOT / "tools" / "ps4ffpsc"),
        str(ROOT / "third_party" / "mkpfs"),
    ],
    binaries=[
        (str(HELPER), "bin"),
    ],
    datas=[
        (str(ROOT / "ps4ffpsc.toml"), "."),
        (str(ROOT / "LICENSE"), "."),
        (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
        (str(ROOT / "LICENSES"), "LICENSES"),
        (str(LOCALES), "ps4ffpsc/locales"),
    ],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

gui_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PS4 FFPFSC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

worker_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ps4ffpsc-worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    gui_exe,
    worker_exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PS4 FFPFSC",
)

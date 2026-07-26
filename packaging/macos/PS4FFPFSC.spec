# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parents[1]
HELPER = ROOT / "build-release" / "helper" / "tools" / "ps4_pkg_extract" / "ps4_pkg_extract"
ICON = ROOT / "build-release" / "AppIcon.icns"

hidden = collect_submodules("mkpfs") + [
    "isal.isal_zlib",
    "zlib_ng.zlib_ng",
]

a = Analysis(
    [str(ROOT / "packaging" / "macos" / "app_entry.py")],
    pathex=[
        str(ROOT / "tools" / "ps4ffpsc"),
        str(ROOT / "third_party" / "mkpfs"),
    ],
    binaries=[(str(HELPER), "bin")],
    datas=[
        (str(ROOT / "ps4ffpsc.toml"), "."),
        (str(ROOT / "LICENSE"), "."),
        (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
        (str(ROOT / "LICENSES"), "LICENSES"),
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

exe = EXE(
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
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PS4 FFPFSC",
)
app = BUNDLE(
    coll,
    name="PS4 FFPFSC.app",
    icon=str(ICON),
    bundle_identifier="com.sadykoviv.ps4pkg-to-ffpfsc",
    info_plist={
        "CFBundleDisplayName": "PS4 FFPFSC",
        "CFBundleName": "PS4 FFPFSC",
        "CFBundleShortVersionString": "0.2.2",
        "CFBundleVersion": "4",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "NSHumanReadableCopyright": "GPL-3.0-or-later; source: github.com/SadykovIV/PS4pkg_to_ffpfsc",
    },
)

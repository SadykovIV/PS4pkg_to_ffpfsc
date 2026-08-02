from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path

from ps4ffpsc import __version__
from ps4ffpsc.gui import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]
CURRENT_VERSION = "0.2.8"
RELEASE_VERSIONS = tuple(f"0.2.{patch}" for patch in range(9))


def test_current_version_is_consistent_across_application_and_packaging() -> None:
    project = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert project["project"]["version"] == CURRENT_VERSION
    assert project["project"]["requires-python"] == ">=3.11,<3.14"
    assert "cryptography==49.0.0" in project["project"]["dependencies"]
    assert "PySide6-Essentials==6.9.3" in project["project"]["dependencies"]
    assert "shiboken6==6.9.3" in project["project"]["dependencies"]
    assert __version__ == CURRENT_VERSION
    assert APP_VERSION == CURRENT_VERSION

    expected_references = {
        "scripts/build_release_macos_arm64.sh": (
            f'VERSION="{CURRENT_VERSION}"',
        ),
        "scripts/build_release_windows_x64.ps1": (
            f'$Version = "{CURRENT_VERSION}"',
        ),
        "packaging/macos/PS4FFPFSC.spec": (
            f'"CFBundleShortVersionString": "{CURRENT_VERSION}"',
            '"CFBundleVersion": "9"',
        ),
        "packaging/windows/version_info.txt": (
            "filevers=(0, 2, 8, 0)",
            "prodvers=(0, 2, 8, 0)",
            f"StringStruct('FileVersion', '{CURRENT_VERSION}')",
            f"StringStruct('ProductVersion', '{CURRENT_VERSION}')",
        ),
        "README.md": (
            f"PS4-FFPFSC-v{CURRENT_VERSION}-macos-arm64.zip",
            f"PS4-FFPFSC-v{CURRENT_VERSION}-windows-x64.zip",
        ),
        "README_EN.md": (
            f"PS4-FFPFSC-v{CURRENT_VERSION}-macos-arm64.zip",
            f"PS4-FFPFSC-v{CURRENT_VERSION}-windows-x64.zip",
        ),
        "docs/GUI.md": (
            f"PS4-FFPFSC-v{CURRENT_VERSION}-windows-x64.zip",
        ),
    }
    for relative, expected_values in expected_references.items():
        content = (ROOT / relative).read_text(encoding="utf-8")
        for expected in expected_values:
            assert expected in content


def test_every_release_has_the_same_bilingual_changelog_structure() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    required_release_headings = (
        "## Загрузки / Downloads",
        "## Русская версия",
        "### Добавлено",
        "### Исправлено",
        "### Проверено",
        "## English version",
        "### Added",
        "### Fixed",
        "### Verified",
    )

    for version in RELEASE_VERSIONS:
        assert f"### {version}" in changelog
        release_notes = (
            ROOT / "packaging" / "releases" / f"v{version}.md"
        ).read_text(encoding="utf-8")
        assert release_notes.startswith(f"# PS4 FFPFSC {version}\n")
        for heading in required_release_headings:
            assert heading in release_notes


def test_release_scripts_package_the_unified_current_release_notes() -> None:
    macos_script = (
        ROOT / "scripts" / "build_release_macos_arm64.sh"
    ).read_text(encoding="utf-8")
    windows_script = (
        ROOT / "scripts" / "build_release_windows_x64.ps1"
    ).read_text(encoding="utf-8")

    assert 'PYINSTALLER_CONFIG_DIR="${BUILD_ROOT}/pyinstaller-config"' in macos_script
    assert 'packaging/releases/v${VERSION}.md' in macos_script
    assert '"${BUNDLED_DLC_HELPER}" --check-template' in macos_script
    assert 'dlc-helper-template.json' in macos_script
    assert 'rm -rf "${BUILD_ROOT}" "${RELEASE_ROOT}"' not in macos_script
    assert r"packaging\releases\v$Version.md" in windows_script
    assert "& $BundledDlcHelper --check-template" in windows_script
    assert '"dlc-helper-template.json"' in windows_script
    assert "Remove-Item $ReleaseRoot -Recurse" not in windows_script


def test_experimental_dlc_build_inputs_are_pinned_and_attributed() -> None:
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "LICENSES/*.txt text eol=lf" in attributes

    csproj = (
        ROOT / "third_party" / "ps4_dlc_patch" / "ps4-dlc-patch.csproj"
    ).read_text(encoding="utf-8")
    assert "<TargetFramework>net8.0</TargetFramework>" in csproj
    assert "<RuntimeFrameworkVersion>8.0.26</RuntimeFrameworkVersion>" in csproj

    expected_licenses = {
        "dotnet-runtime-8.0.26-LICENSE.txt":
            "cfc21f5e8bd655ae997eec916138b707b1d290b83272c02a95c9f821b8c87310",
        "dotnet-runtime-8.0.26-THIRD-PARTY-NOTICES.txt":
            "97c1a7b3da6a4c6ad516448719f45114b41a4d4c5aa300a944476e2e4f5da438",
        "OpenOrbis-PS4-Toolchain-v0.5.4-GPL-3.0.txt":
            "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
        "Python-3.13.14.txt":
            "78b12c3a81360b357002334f0e70ea0e92eebf7a9b358805c03c48484945f3bb",
    }
    for name, expected_sha256 in expected_licenses.items():
        content = (ROOT / "LICENSES" / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected_sha256

    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for name in expected_licenses:
        assert f"`LICENSES/{name}`" in notices

    fetch_script = (
        ROOT / "scripts" / "fetch_openorbis_toolchain.sh"
    ).read_text(encoding="utf-8")
    assert 'VERSION="0.5.4"' in fetch_script
    assert (
        'ARCHIVE_SHA256="3c7cd5bb593ca74fa1c13fd59f3938dc0fc07985167f7275063019e63abe4526"'
        in fetch_script
    )

    for relative in (
        "docs/TESTING.md",
        "docs/GUI.md",
        "docs/ru/TESTING.md",
        "docs/ru/GUI.md",
    ):
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert ".NET SDK 8" in content
        assert "OpenOrbis" in content
        assert "PS4FFPSC_DLC_TEMPLATE" in content


def test_macos_13_release_inputs_and_audit_are_pinned() -> None:
    requirements = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    assert "PySide6-Essentials==6.9.3" in requirements
    assert "shiboken6==6.9.3" in requirements
    assert "6.11.1" not in requirements

    bootstrap = (ROOT / "scripts" / "bootstrap_macos.sh").read_text(
        encoding="utf-8"
    )
    assert 'PYTHON_VERSION="3.13.14"' in bootstrap
    assert (
        'PYTHON_SHA256="8e58affb218c155a1dfdc27b291f817129669f8760e7a297adb2e4439ba5d2e8"'
        in bootstrap
    )
    assert "pkgutil --expand-full" in bootstrap
    assert "sudo /usr/sbin/installer" not in bootstrap
    assert "python@3.14" not in bootstrap
    assert 'export DYLD_LIBRARY_PATH="${PYTHON_LIBRARY_ROOT}' in bootstrap
    assert "import platform, ssl, sys" in bootstrap

    cryptopp = (ROOT / "scripts" / "prepare_cryptopp_macos.sh").read_text(
        encoding="utf-8"
    )
    assert 'VERSION="8.9.0"' in cryptopp
    assert (
        'ARCHIVE_SHA256="4cc0ccc324625b80b695fcd3dee63a66f1a460d3e51b71640cdbfc4cd1a3779c"'
        in cryptopp
    )
    assert 'DEPLOYMENT_TARGET="13.0"' in cryptopp
    assert "-mmacosx-version-min=${DEPLOYMENT_TARGET}" in cryptopp
    assert "audit_static_archive" in cryptopp

    release_script = (
        ROOT / "scripts" / "build_release_macos_arm64.sh"
    ).read_text(encoding="utf-8")
    for expected in (
        'DEPLOYMENT_TARGET="13.0"',
        "prepare_cryptopp_macos.sh",
        "-DCMAKE_OSX_ARCHITECTURES=arm64",
        "-DCMAKE_OSX_DEPLOYMENT_TARGET=${DEPLOYMENT_TARGET}",
        'export MACOSX_DEPLOYMENT_TARGET="${DEPLOYMENT_TARGET}"',
        'export DYLD_LIBRARY_PATH="${PYTHON_LIBRARY_ROOT}',
        "import os, platform, ssl, sys",
    ):
        assert expected in release_script

    app_audit = (ROOT / "scripts" / "audit_macos_app.sh").read_text(
        encoding="utf-8"
    )
    assert 'max_minos="13.0"' in app_audit
    assert "LSMinimumSystemVersion" in app_audit
    assert "vtool -show-build" in app_audit

    workflow = (
        ROOT / ".github" / "workflows" / "build-windows-x64.yml"
    ).read_text(encoding="utf-8")
    assert 'python-version: "3.13.14"' in workflow

    windows_script = (
        ROOT / "scripts" / "build_release_windows_x64.ps1"
    ).read_text(encoding="utf-8")
    assert "sys.version_info[:3] == (3, 13, 14)" in windows_script
    assert "platform.machine().lower()" in windows_script
    assert "'PySide6-Essentials': '6.9.3'" in windows_script
    assert "'shiboken6': '6.9.3'" in windows_script

    for relative in (
        "docs/TESTING.md",
        "docs/GUI.md",
        "docs/ru/TESTING.md",
        "docs/ru/GUI.md",
    ):
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert "Python 3.13.14" in content
        assert "6.9.3" in content
        assert "macOS 13.0" in content
        assert "Python 3.14" not in content


def test_every_document_has_a_linked_russian_mirror() -> None:
    docs_root = ROOT / "docs"
    english_names = sorted(path.name for path in docs_root.glob("*.md"))
    russian_names = sorted(path.name for path in (docs_root / "ru").glob("*.md"))

    assert english_names == russian_names
    assert english_names
    for name in english_names:
        english = (docs_root / name).read_text(encoding="utf-8")
        russian = (docs_root / "ru" / name).read_text(encoding="utf-8")
        assert f"ru/{name}" in english
        assert f"../{name}" in russian
        assert "**Русский**" in russian

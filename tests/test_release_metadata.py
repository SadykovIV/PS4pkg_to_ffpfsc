from __future__ import annotations

import tomllib
from pathlib import Path

from ps4ffpsc import __version__
from ps4ffpsc.gui import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]
CURRENT_VERSION = "0.2.5"
RELEASE_VERSIONS = tuple(f"0.2.{patch}" for patch in range(6))


def test_current_version_is_consistent_across_application_and_packaging() -> None:
    project = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert project["project"]["version"] == CURRENT_VERSION
    assert __version__ == CURRENT_VERSION
    assert APP_VERSION == CURRENT_VERSION

    expected_references = {
        "scripts/build_release_macos_arm64.sh": f'VERSION="{CURRENT_VERSION}"',
        "scripts/build_release_windows_x64.ps1": (
            f'$Version = "{CURRENT_VERSION}"'
        ),
        "packaging/macos/PS4FFPFSC.spec": (
            f'"CFBundleShortVersionString": "{CURRENT_VERSION}"'
        ),
        "packaging/windows/version_info.txt": (
            f"StringStruct('ProductVersion', '{CURRENT_VERSION}')"
        ),
    }
    for relative, expected in expected_references.items():
        assert expected in (ROOT / relative).read_text(encoding="utf-8")


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

    assert 'packaging/releases/v${VERSION}.md' in macos_script
    assert r"packaging\releases\v$Version.md" in windows_script

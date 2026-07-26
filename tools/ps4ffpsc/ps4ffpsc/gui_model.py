from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from .runtime import temporary_workspace

PROGRESS_PREFIX = "PS4FFPSC_PROGRESS "
_SCAN_TOTAL_RE = re.compile(r"\bscanning (\d+) PKG file\(s\)")
_SCAN_ITEM_RE = re.compile(r"\binspecting PKG:")
_BUILD_STAGE_RE = re.compile(r"\bstage (\d+)/(\d+):")


def normalize_pkg_files(
    paths: Iterable[str | Path],
    language: str = "ru",
) -> tuple[Path, ...]:
    """Return unique absolute PKG paths while preserving the user's order."""
    result: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        key = str(path).casefold()
        if key in seen:
            continue
        if path.suffix.lower() != ".pkg":
            message = (
                f"selected file does not have a .pkg extension: {path}"
                if language == "en"
                else f"выбран файл без расширения .pkg: {path}"
            )
            raise ValueError(message)
        if not path.is_file():
            raise FileNotFoundError(path)
        seen.add(key)
        result.append(path)
    if not result:
        raise ValueError(
            "no PKG files selected"
            if language == "en"
            else "не выбрано ни одного PKG-файла"
        )
    return tuple(result)


def validate_source(
    mode: str,
    pkg_files: Iterable[str | Path],
    folder: str | Path | None,
    language: str = "ru",
) -> tuple[str, tuple[Path, ...], Path | None]:
    if mode == "files":
        return mode, normalize_pkg_files(pkg_files, language), None
    if mode == "folder":
        if folder is None or not str(folder).strip():
            raise ValueError(
                "PKG folder is not selected"
                if language == "en"
                else "не выбрана папка с PKG"
            )
        path = Path(folder).expanduser().resolve()
        if not path.is_dir():
            raise NotADirectoryError(path)
        return mode, (), path
    raise ValueError(
        f"unknown source mode: {mode}"
        if language == "en"
        else f"неизвестный режим источника: {mode}"
    )


def source_cli_arguments(
    mode: str,
    pkg_files: Iterable[str | Path],
    folder: str | Path | None,
    language: str = "ru",
) -> list[str]:
    normalized_mode, normalized_files, normalized_folder = validate_source(
        mode, pkg_files, folder, language
    )
    if normalized_mode == "folder":
        return ["--pkg-dir", str(normalized_folder)]
    arguments: list[str] = []
    for path in normalized_files:
        arguments.extend(["--pkg-file", str(path)])
    return arguments


def temporary_cli_arguments(temp_dir: str | Path) -> list[str]:
    workspace = temporary_workspace(Path(temp_dir))
    return [
        "--unpacked-dir",
        str(workspace / "unpacked"),
        "--work-dir",
        str(workspace / "work"),
        "--temp-dir",
        str(workspace / "tmp"),
    ]


def scan_inventory_path(payload: Any, temp_dir: str | Path) -> Path:
    if isinstance(payload, dict):
        reported = payload.get("inventory")
        if isinstance(reported, str) and reported.strip():
            return Path(reported)
    return temporary_workspace(Path(temp_dir)) / "unpacked" / "package_inventory.json"


def parse_progress_event(line: str) -> dict[str, Any] | None:
    marker = line.find(PROGRESS_PREFIX)
    if marker >= 0:
        raw = line[marker + len(PROGRESS_PREFIX) :].strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict):
            return {"kind": "worker", **payload}
        return None
    match = _SCAN_TOTAL_RE.search(line)
    if match:
        return {"kind": "scan_total", "total": int(match.group(1))}
    if _SCAN_ITEM_RE.search(line):
        return {"kind": "scan_item"}
    match = _BUILD_STAGE_RE.search(line)
    if match:
        return {
            "kind": "build_stage",
            "stage": int(match.group(1)),
            "total": int(match.group(2)),
        }
    return None


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def estimate_remaining_seconds(elapsed: float, percent: float) -> float | None:
    if elapsed < 0 or percent <= 0 or percent > 100:
        return None
    if percent >= 100:
        return 0.0
    return elapsed * (100.0 - percent) / percent


def inventory_summary(inventory: dict[str, Any]) -> dict[str, int]:
    games = inventory.get("games", {})
    return {
        "packages": len(inventory.get("packages", [])),
        "games": len(games),
        "buildable": sum(bool(game.get("buildable")) for game in games.values()),
        "unsupported": len(inventory.get("unsupported", [])),
        "conflicts": sum(bool(game.get("conflicts")) for game in games.values()),
    }


def build_error_text(
    payload: Any,
    title_id: str,
    exit_code: int,
    language: str = "ru",
) -> str:
    if isinstance(payload, dict):
        result = payload.get(title_id)
        if isinstance(result, dict):
            error = result.get("error") or result.get("reason")
            if isinstance(error, str) and error.strip():
                return error.strip()
    if language == "en":
        return f"exit code {exit_code}; see the log for details"
    return f"код {exit_code}; подробности находятся в журнале"


def package_version_text(package: dict[str, Any]) -> str:
    if package.get("kind") == "dlc":
        return str(package.get("entitlement_label") or package.get("app_version") or "—")
    return str(package.get("app_version") or "—")


def game_block_reason(game: dict[str, Any], language: str = "ru") -> str:
    reasons = [*game.get("conflicts", []), *game.get("warnings", [])]
    translated: list[str] = []
    for reason in reasons:
        if reason == "orphan_package":
            translated.append(
                "base PKG is missing (category gd); patch and DLC require the base game"
                if language == "en"
                else "нет base PKG (категория gd); patch и DLC без основной игры собрать нельзя"
            )
        elif reason == "conflicting_base_packages":
            translated.append(
                "multiple different base PKGs were found"
                if language == "en"
                else "найдено несколько разных base PKG"
            )
        elif reason == "incompatible_package":
            translated.append(
                "package region or CONTENT_ID does not match"
                if language == "en"
                else "регион или CONTENT_ID пакетов не совпадает"
            )
        elif reason == "unknown_package_kind":
            translated.append(
                "one or more PKG types were not recognized"
                if language == "en"
                else "тип одного или нескольких PKG не распознан"
            )
        elif reason.startswith("conflicting_patch_version:"):
            translated.append(
                (
                    "multiple different patches have version "
                    if language == "en"
                    else "несколько разных patch одной версии "
                )
                + reason.partition(":")[2]
            )
        else:
            translated.append(reason)
    fallback = "game is not ready to build" if language == "en" else "игра не готова к сборке"
    return "; ".join(translated) if translated else fallback

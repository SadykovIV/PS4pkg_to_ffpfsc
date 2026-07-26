from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


def normalize_pkg_files(paths: Iterable[str | Path]) -> tuple[Path, ...]:
    """Return unique absolute PKG paths while preserving the user's order."""
    result: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        key = str(path).casefold()
        if key in seen:
            continue
        if path.suffix.lower() != ".pkg":
            raise ValueError(f"выбран файл без расширения .pkg: {path}")
        if not path.is_file():
            raise FileNotFoundError(path)
        seen.add(key)
        result.append(path)
    if not result:
        raise ValueError("не выбрано ни одного PKG-файла")
    return tuple(result)


def validate_source(
    mode: str,
    pkg_files: Iterable[str | Path],
    folder: str | Path | None,
) -> tuple[str, tuple[Path, ...], Path | None]:
    if mode == "files":
        return mode, normalize_pkg_files(pkg_files), None
    if mode == "folder":
        if folder is None or not str(folder).strip():
            raise ValueError("не выбрана папка с PKG")
        path = Path(folder).expanduser().resolve()
        if not path.is_dir():
            raise NotADirectoryError(path)
        return mode, (), path
    raise ValueError(f"неизвестный режим источника: {mode}")


def source_cli_arguments(
    mode: str,
    pkg_files: Iterable[str | Path],
    folder: str | Path | None,
) -> list[str]:
    normalized_mode, normalized_files, normalized_folder = validate_source(
        mode, pkg_files, folder
    )
    if normalized_mode == "folder":
        return ["--pkg-dir", str(normalized_folder)]
    arguments: list[str] = []
    for path in normalized_files:
        arguments.extend(["--pkg-file", str(path)])
    return arguments


def inventory_summary(inventory: dict[str, Any]) -> dict[str, int]:
    games = inventory.get("games", {})
    return {
        "packages": len(inventory.get("packages", [])),
        "games": len(games),
        "buildable": sum(bool(game.get("buildable")) for game in games.values()),
        "unsupported": len(inventory.get("unsupported", [])),
        "conflicts": sum(bool(game.get("conflicts")) for game in games.values()),
    }


def build_error_text(payload: Any, title_id: str, exit_code: int) -> str:
    if isinstance(payload, dict):
        result = payload.get(title_id)
        if isinstance(result, dict):
            error = result.get("error") or result.get("reason")
            if isinstance(error, str) and error.strip():
                return error.strip()
    return f"код {exit_code}; подробности находятся в журнале"


def package_version_text(package: dict[str, Any]) -> str:
    if package.get("kind") == "dlc":
        return str(package.get("entitlement_label") or package.get("app_version") or "—")
    return str(package.get("app_version") or "—")


def game_block_reason(game: dict[str, Any]) -> str:
    reasons = [*game.get("conflicts", []), *game.get("warnings", [])]
    translated: list[str] = []
    for reason in reasons:
        if reason == "orphan_package":
            translated.append(
                "нет base PKG (категория gd); patch и DLC без основной игры собрать нельзя"
            )
        elif reason == "conflicting_base_packages":
            translated.append("найдено несколько разных base PKG")
        elif reason == "incompatible_package":
            translated.append("регион или CONTENT_ID пакетов не совпадает")
        elif reason == "unknown_package_kind":
            translated.append("тип одного или нескольких PKG не распознан")
        elif reason.startswith("conflicting_patch_version:"):
            translated.append(
                "несколько разных patch одной версии " + reason.partition(":")[2]
            )
        else:
            translated.append(reason)
    return "; ".join(translated) if translated else "игра не готова к сборке"

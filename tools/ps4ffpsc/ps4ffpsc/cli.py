from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from .inventory import inspect_package, ordered_patches
from .pipeline import (
    Settings,
    build_game,
    clean_work,
    configure_logging,
    doctor,
    extractor_or_raise,
    game_or_raise,
    inventory_path,
    load_or_scan,
    merge_game,
    status,
    unpack_game,
    verify_artifact,
)
from .runtime import (
    application_data_root,
    ensure_application_directories,
    join_windows_job_from_environment,
    maximum_logical_cpu_count,
    resource_root,
)

EXIT_GENERAL = 1
EXIT_CONFLICT = 2
EXIT_UNSUPPORTED = 3
EXIT_VERIFY = 4
EXIT_SPACE = 5


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pkg-dir")
    parser.add_argument(
        "--pkg-file",
        action="append",
        default=[],
        help="inspect this PKG; repeat to select multiple files (overrides --pkg-dir scanning)",
    )
    parser.add_argument(
        "--dump-dir",
        action="append",
        default=[],
        help=(
            "use an already unpacked game tree; accepts a flat game root or an "
            "app/patch directory produced by a game dumper"
        ),
    )
    parser.add_argument("--unpacked-dir")
    parser.add_argument("--output-dir")
    parser.add_argument("--work-dir")
    parser.add_argument("--temp-dir")
    parser.add_argument("--compat", choices=["current-smp", "patched-smp"])
    parser.add_argument(
        "--dlc-mode",
        choices=["off", "single-experimental"],
        help=(
            "DLC handling mode (default: off; single-experimental embeds "
            "selected DLC into the game image)"
        ),
    )
    parser.add_argument(
        "--include-dlc",
        choices=["auto", "bundle", "separate", "off"],
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--output-format",
        choices=["ffpfsc", "exfat"],
        help="output image format (default: ffpfsc; exfat is uncompressed)",
    )
    parser.add_argument("--keep-inner-image", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--console-log",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--jobs", type=int)
    parser.add_argument(
        "--compression-level",
        type=int,
        choices=range(0, 10),
        help="MkPFS zlib compression level (0=store, 1=fastest, 9=maximum; default: 7)",
    )
    maximum_workers = maximum_logical_cpu_count()
    parser.add_argument(
        "--compression-workers",
        type=int,
        choices=range(1, maximum_workers + 1),
        metavar=f"1..{maximum_workers}",
        help=(
            "MkPFS compression workers "
            "(default: half of available logical CPUs)"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ps4ffpsc",
        description=(
            "Convert supported, legally owned PS4 PKGs or an unpacked game tree "
            "to verified FFPFSC/exFAT artifacts."
        ),
    )
    sub = parser.add_subparsers(dest="command")
    for name, help_text in [
        ("doctor", "Check the local toolchain and storage"),
        ("scan", "Inspect every PKG recursively and write inventory"),
        ("list", "List grouped games, patches, DLC and conflicts"),
        ("status", "Show resumable state and partial files"),
    ]:
        child = sub.add_parser(name, help=help_text)
        _common(child)

    inspect_parser = sub.add_parser("inspect", help="Inspect one PKG")
    inspect_parser.add_argument("file", type=Path)
    _common(inspect_parser)

    unpack_parser = sub.add_parser("unpack", help="Extract selected packages")
    unpack_parser.add_argument("title_id", nargs="?")
    unpack_parser.add_argument("--all", action="store_true")
    _common(unpack_parser)

    merge_parser = sub.add_parser("merge", help="Merge base and ordered patches")
    merge_parser.add_argument("title_id")
    _common(merge_parser)

    build_command = sub.add_parser("build", help="Run scan, unpack, merge, pack and verify")
    build_command.add_argument("title_id", nargs="?")
    build_command.add_argument("--all", action="store_true")
    _common(build_command)

    verify_parser = sub.add_parser(
        "verify",
        help="Verify and inspect an FFPFSC or raw exFAT image",
    )
    verify_parser.add_argument("file", type=Path)
    _common(verify_parser)

    clean_parser = sub.add_parser("clean", help="Remove only temporary work data")
    clean_parser.add_argument("--work", action="store_true", required=True)
    _common(clean_parser)
    return parser


def _emit(value: Any, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
        return
    if isinstance(value, dict):
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(value)


def _print_list(inventory: dict[str, Any], json_output: bool) -> None:
    if json_output:
        _emit(inventory["games"], True)
        return
    if not inventory["games"]:
        print("No supported games found.")
    for title_id, game in sorted(inventory["games"].items()):
        state = "buildable" if game["buildable"] else "blocked"
        print(f"{title_id}  {game['title']}  [{state}]")
        print(f"  base={len(game['base'])} patches={len(game['patches'])} dlc={len(game['dlc'])}")
        for patch in ordered_patches(game):
            print(f"  patch {patch.get('app_version')}: {Path(patch['path']).name}")
        for item in game["dlc"]:
            print(f"  DLC {item.get('entitlement_label')}: {Path(item['path']).name}")
        for conflict in game["conflicts"]:
            print(f"  conflict: {conflict}")
        for warning in game["warnings"]:
            print(f"  warning: {warning}")
    if inventory["unsupported"]:
        print(f"unsupported_or_encrypted_pkg={len(inventory['unsupported'])}")


def _settings(args: argparse.Namespace) -> Settings:
    root = application_data_root()
    ensure_application_directories(root)
    return Settings.load(root, args, resource_root())


def main(argv: list[str] | None = None) -> int:
    if not join_windows_job_from_environment():
        print(
            "ps4ffpsc: could not join the GUI process job; "
            "the operation was not started",
            file=sys.stderr,
        )
        return EXIT_GENERAL
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    settings = _settings(args)
    configure_logging(settings)
    try:
        if args.command == "doctor":
            result = doctor(settings)
            _emit(result, settings.json_output)
            return 0 if result["ok"] else EXIT_GENERAL
        if args.command == "scan":
            inventory = load_or_scan(settings, refresh=True)
            _emit(
                {
                    "inventory": str(inventory_path(settings)),
                    "packages": len(inventory["packages"]),
                    "games": len(inventory["games"]),
                    "unsupported": len(inventory["unsupported"]),
                },
                settings.json_output,
            )
            return EXIT_UNSUPPORTED if inventory["unsupported"] else 0
        if args.command == "inspect":
            result = inspect_package(extractor_or_raise(settings), args.file.resolve())
            _emit(result, settings.json_output)
            return 0 if result.get("supported") else EXIT_UNSUPPORTED
        if args.command == "list":
            inventory = load_or_scan(settings)
            _print_list(inventory, settings.json_output)
            return EXIT_CONFLICT if any(game["conflicts"] for game in inventory["games"].values()) else 0
        if args.command == "unpack":
            inventory = load_or_scan(settings, refresh=True)
            title_ids = (
                sorted(inventory["games"])
                if args.all
                else [args.title_id]
                if args.title_id
                else []
            )
            if not title_ids:
                raise ValueError("provide TITLE_ID or --all")
            results: dict[str, Any] = {}
            failed = False
            for title_id in title_ids:
                try:
                    results[title_id] = unpack_game(settings, inventory, title_id)
                except Exception as error:
                    failed = True
                    results[title_id] = {"error": str(error)}
            _emit(results, settings.json_output)
            return EXIT_GENERAL if failed else 0
        if args.command == "merge":
            inventory = load_or_scan(settings, refresh=True)
            result = merge_game(settings, inventory, args.title_id)
            _emit(result, settings.json_output)
            return 0
        if args.command == "build":
            inventory = load_or_scan(settings, refresh=True)
            title_ids = (
                sorted(inventory["games"])
                if args.all
                else [args.title_id]
                if args.title_id
                else []
            )
            if not title_ids:
                raise ValueError("provide TITLE_ID or --all")
            results: dict[str, Any] = {}
            failed = False
            skipped = False
            for title_id in title_ids:
                game = game_or_raise(inventory, title_id)
                if not game["buildable"]:
                    skipped = True
                    results[title_id] = {"status": "skipped", "reason": game["conflicts"] or game["warnings"]}
                    continue
                try:
                    results[title_id] = build_game(settings, title_id, inventory)
                except Exception as error:
                    failed = True
                    results[title_id] = {"error": str(error)}
            _emit(results, settings.json_output)
            if failed:
                return EXIT_GENERAL
            return EXIT_CONFLICT if skipped else 0
        if args.command == "verify":
            result = verify_artifact(settings, args.file.resolve())
            _emit(result, settings.json_output)
            return 0
        if args.command == "status":
            _emit(status(settings), settings.json_output)
            return 0
        if args.command == "clean":
            _emit(clean_work(settings), settings.json_output)
            return 0
    except OSError as error:
        print(f"ps4ffpsc: {error}", file=sys.stderr)
        return EXIT_SPACE if error.errno == 28 else EXIT_GENERAL
    except Exception as error:
        print(f"ps4ffpsc: {error}", file=sys.stderr)
        return EXIT_VERIFY if args.command == "verify" else EXIT_GENERAL
    return EXIT_GENERAL


if __name__ == "__main__":
    raise SystemExit(main())

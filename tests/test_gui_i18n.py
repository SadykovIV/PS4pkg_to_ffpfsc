from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from ps4ffpsc import gui
from ps4ffpsc.gui import BUILD_STAGE_KEYS, MKPFS_PHASE_KEYS, TEXTS, MainWindow
from ps4ffpsc.runtime import maximum_logical_cpu_count


def test_translation_catalogs_have_identical_keys() -> None:
    assert set(TEXTS["ru"]) == set(TEXTS["en"])


def test_every_literal_translation_key_exists() -> None:
    tree = ast.parse(inspect.getsource(gui))
    referenced = {
        call.args[0].value
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr in {"_t", "_bind_text", "_set_stage", "_set_summary"}
        and call.args
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
    }
    referenced.update(BUILD_STAGE_KEYS.values())
    referenced.update(MKPFS_PHASE_KEYS.values())
    assert referenced <= set(TEXTS["ru"])


def test_language_switch_retranslates_static_and_live_progress(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("PS4 FFPFSC i18n test")
    app.setOrganizationName("ps4ffpsc-tests")
    settings = QSettings()
    settings.clear()
    settings.setValue("language", "ru")
    window = MainWindow(tmp_path, Path(__file__).resolve().parents[1])

    assert window.scan_button.text() == "Сканировать"
    window.language_combo.setCurrentIndex(1)
    assert window.language == "en"
    assert window.scan_button.text() == "Scan"
    assert window.build_button.text() == "Check readiness"
    assert "No PKG" in window.source_label.text()

    window.build_total_count = 1
    window.current_build_title = "CUSA12878"
    window._begin_progress("build")
    window.current_build_stage = 3
    window._handle_worker_progress(
        {
            "scope": "mkpfs",
            "phase": "compress",
            "current": 50,
            "total": 100,
        }
    )
    assert "stage 3/5" in window.stage_label.text()
    assert "compress" in window.stage_label.text()
    assert window.time_label.text().startswith("Elapsed ")

    window.language_combo.setCurrentIndex(0)
    assert "этап 3/5" in window.stage_label.text()
    assert "сжатие" in window.stage_label.text()
    assert window.time_label.text().startswith("Прошло ")
    window.progress_timer.stop()
    window.close()
    settings.clear()


def test_inventory_shows_pkg_and_game_sizes_and_byte_based_extraction_eta(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("PS4 FFPFSC size test")
    app.setOrganizationName("ps4ffpsc-tests")
    settings = QSettings()
    settings.clear()
    settings.setValue("language", "ru")
    window = MainWindow(tmp_path, Path(__file__).resolve().parents[1])
    base = {
        "path": str(tmp_path / "base.pkg"),
        "size": 1024**3,
        "supported": True,
        "kind": "base",
        "app_version": "01.00",
    }
    patch = {
        "path": str(tmp_path / "patch.pkg"),
        "size": 512 * 1024**2,
        "supported": True,
        "kind": "patch",
        "app_version": "01.10",
    }
    duplicate_patch = {
        **patch,
        "path": str(tmp_path / "patch-copy.pkg"),
        "duplicate_of": str(tmp_path / "patch.pkg"),
    }
    window.inventory = {
        "packages": [base, patch, duplicate_patch],
        "unsupported": [],
        "games": {
            "CUSA12878": {
                "title": "Beat Saber",
                "base": [base],
                "patches": [patch, duplicate_patch],
                "dlc": [],
                "unknown": [],
                "buildable": True,
                "conflicts": [],
                "warnings": [],
            }
        },
    }
    window._populate_inventory()

    top = window.games_tree.topLevelItem(0)
    assert window.games_tree.columnCount() == 7
    assert window.games_tree.headerItem().text(6) == "Размер"
    assert top.text(6) == "≈ 1.5 GiB"
    assert top.child(0).text(6) == "1.0 GiB"
    assert top.child(1).text(6) == "512.0 MiB"
    assert top.child(0).checkState(0) == Qt.CheckState.Checked
    assert top.child(1).checkState(0) == Qt.CheckState.Checked
    assert top.child(2).checkState(0) == Qt.CheckState.Unchecked
    assert window._checked_package_paths(top) == (
        Path(base["path"]),
        Path(patch["path"]),
    )
    assert "выбрано ≈ 1.5 GiB" in window.summary_label.text()

    top.child(0).setCheckState(0, Qt.CheckState.Unchecked)
    top.child(1).setCheckState(0, Qt.CheckState.Unchecked)
    assert "выбрано ≈ 0 B" in window.summary_label.text()
    top.child(0).setCheckState(0, Qt.CheckState.Checked)
    top.child(1).setCheckState(0, Qt.CheckState.Checked)

    window.build_total_count = 1
    window.current_build_title = "CUSA12878"
    window._begin_progress("build")
    window.current_build_stage = 1
    window._handle_worker_progress(
        {
            "scope": "extract",
            "current": 768 * 1024**2,
            "total": 1536 * 1024**2,
            "package_index": 1,
            "package_total": 2,
            "package_bytes_current": 512 * 1024**2,
            "package_bytes_total": 1024**3,
        }
    )
    assert "50%" in window.stage_label.text()
    assert "512.0 MiB / 1.0 GiB" in window.stage_label.text()
    assert window.byte_progress_started_at is not None
    window.byte_progress_started_at -= 10
    assert window.progress_started_at is not None
    window.progress_started_at -= 10
    window.byte_progress_start = 0
    window._update_elapsed_time()
    assert "до конца распаковки" in window.time_label.text()

    window.language_combo.setCurrentIndex(1)
    top = window.games_tree.topLevelItem(0)
    assert window.games_tree.headerItem().text(6) == "Size"
    assert "selected ≈ 1.5 GiB" in window.summary_label.text()
    assert "extraction remaining" in window.time_label.text()
    assert top.child(2).checkState(0) == Qt.CheckState.Unchecked
    window.progress_timer.stop()
    window.close()
    settings.clear()


def test_compression_level_is_selectable_persistent_and_passed_to_worker(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("PS4 FFPFSC compression test")
    app.setOrganizationName("ps4ffpsc-tests")
    settings = QSettings()
    settings.clear()
    settings.setValue("language", "ru")
    window = MainWindow(tmp_path, Path(__file__).resolve().parents[1])

    assert window.compression_combo.count() == 10
    assert [
        window.compression_combo.itemData(index)
        for index in range(window.compression_combo.count())
    ] == list(range(10))
    assert window.compression_combo.currentData() == 7
    assert str(maximum_logical_cpu_count()) in window.compression_threads_label.text()
    assert "автоматически" in window.compression_threads_label.text()

    window.compression_combo.setCurrentIndex(
        window.compression_combo.findData(9)
    )
    window.source_mode = "folder"
    window.source_folder = tmp_path
    arguments = window._base_arguments()

    level_index = arguments.index("--compression-level")
    assert arguments[level_index + 1] == "9"
    assert arguments[arguments.index("--compat") + 1] == "current-smp"
    assert arguments[arguments.index("--include-dlc") + 1] == "auto"
    assert not hasattr(window, "compat_combo")
    assert not hasattr(window, "dlc_combo")
    assert settings.value("compression_level", type=int) == 9

    window.language_combo.setCurrentIndex(1)
    assert "maximum" in window.compression_combo.currentText()
    assert "automatic maximum" in window.compression_threads_label.text()
    window.close()

    restored = MainWindow(tmp_path, Path(__file__).resolve().parents[1])
    assert restored.compression_combo.currentData() == 9
    restored.close()
    settings.clear()


def test_about_text_contains_author_and_repository_in_both_languages() -> None:
    repository = "https://github.com/SadykovIV/PS4pkg_to_ffpfsc"

    assert "ShadowMountPlus Playstation 5" in TEXTS["ru"]["about_body"]
    assert "Автор: Ильдар Садыков" in TEXTS["ru"]["about_body"]
    assert repository in TEXTS["ru"]["about_body"]
    assert "ShadowMountPlus PlayStation 5" in TEXTS["en"]["about_body"]
    assert "Author: Ildar Sadykov" in TEXTS["en"]["about_body"]
    assert repository in TEXTS["en"]["about_body"]


def test_legacy_application_data_temp_setting_migrates_to_system_temp(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("PS4 FFPFSC temp migration test")
    app.setOrganizationName("ps4ffpsc-tests")
    settings = QSettings()
    settings.clear()
    settings.setValue("temp_dir", str(tmp_path))

    window = MainWindow(tmp_path, Path(__file__).resolve().parents[1])

    assert window.temp_dir != tmp_path
    assert settings.value("temp_dir", type=str) == str(window.temp_dir)
    window.close()
    settings.clear()

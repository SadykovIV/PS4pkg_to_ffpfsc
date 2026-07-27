from __future__ import annotations

import json
import os
import shutil
import tempfile
import sys
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .gui_model import (
    build_error_text,
    estimate_remaining_seconds,
    format_duration,
    game_block_reason,
    inventory_summary,
    package_version_text,
    parse_progress_event,
    scan_inventory_path,
    source_cli_arguments,
    temporary_cli_arguments,
    validate_source,
)
from .runtime import (
    application_data_root,
    default_temporary_directory,
    ensure_application_directories,
    is_frozen,
    resource_root,
    temporary_workspace,
    worker_executable,
)


APP_NAME = "PS4 FFPFSC"
APP_VERSION = "0.2.2"
CREATE_NO_WINDOW = 0x08000000
BUILD_STAGE_START = {1: 2.0, 2: 30.0, 3: 55.0, 4: 88.0, 5: 96.0}
BUILD_STAGE_KEYS = {
    1: "stage_sources",
    2: "stage_merge",
    3: "stage_compress",
    4: "stage_verify",
    5: "stage_checksum_cleanup",
}
MKPFS_PHASE_KEYS = {
    "scan": "phase_scan",
    "exfat": "phase_exfat",
    "compress": "phase_compress",
    "write": "phase_write",
    "verify": "phase_verify",
    "compare": "phase_compare",
}
TEXTS = {
    "ru": {
        "subtitle": "Подготовка проверенных образов для ShadowMountPlus — локально и без изменения исходных PKG",
        "about": "О программе",
        "source_section": "1. Исходные пакеты",
        "choose_pkg": "Выбрать PKG-файлы…",
        "choose_folder": "Выбрать папку…",
        "clear": "Очистить",
        "scan": "Сканировать",
        "storage_section": "2. Папки хранения",
        "output_files": "Готовые FFPFSC",
        "temp_files": "Временные файлы (по умолчанию /tmp)",
        "reset_tmp": "Сбросить /tmp",
        "games_section": "3. Найденные игры",
        "summary_initial": "Сначала выберите источник и запустите сканирование",
        "header_build": "Собрать",
        "header_type": "TITLE_ID / тип",
        "header_name": "Название / файл",
        "header_version": "Версия",
        "log": "Журнал",
        "clear_log": "Очистить журнал",
        "compatibility": "Совместимость:",
        "compat_current": "Текущий ShadowMountPlus",
        "compat_patched": "ShadowMountPlus с патчем",
        "dlc": "DLC:",
        "dlc_auto": "Авто (подготовить, не встраивать)",
        "dlc_separate": "Отдельные образы (экспериментально)",
        "dlc_off": "Не включать",
        "resume": "Продолжать прерванное",
        "force": "Пересобрать существующее",
        "keep_inner": "Сохранить внутренний exFAT",
        "ready": "Готово",
        "timing_idle": "Прошло 00:00 · осталось —",
        "timing_calculating": "Прошло 00:00 · осталось: рассчитывается…",
        "timing": "Прошло {elapsed} · осталось {remaining}",
        "calculating": "рассчитывается…",
        "cancel": "Отменить",
        "reveal": "Открыть папку результата",
        "build_selected": "Собрать выбранные",
        "check_readiness": "Проверить готовность",
        "choose_pkg_title": "Выберите PS4 PKG",
        "pkg_filter": "PlayStation 4 PKG (*.pkg *.PKG);;Все файлы (*)",
        "choose_source_folder": "Выберите папку с PKG (подпапки будут просканированы)",
        "choose_output": "Куда сохранять FFPFSC",
        "choose_temp": "Папка для временных файлов",
        "free_space": "свободно {gib:.1f} GiB",
        "directory_will_create": "каталог будет создан при сборке",
        "source_not_selected": "Источник не выбран",
        "source_empty": "PKG-файлы или папка ещё не выбраны",
        "source_recursive": "будут просмотрены все подпапки",
        "and_more": "… и ещё {count}",
        "stage_word": "этап",
        "stage_sources": "проверка метаданных и извлечение PKG",
        "stage_merge": "объединение base и patch",
        "stage_compress": "сжатие FFPFSC",
        "stage_verify": "проверка контейнера и обязательных файлов",
        "stage_checksum_cleanup": "публикация результата и очистка",
        "phase_scan": "анализ файлов",
        "phase_exfat": "создание exFAT",
        "phase_compress": "сжатие",
        "phase_write": "запись образа",
        "phase_verify": "проверка блоков",
        "phase_compare": "сверка данных",
        "processing": "обработка",
        "game": "Игра",
        "extract_pkg": "извлечение PKG",
        "merge_pkg": "объединение PKG",
        "cleanup_temp": "очистка временных файлов",
        "stage_status": "{title} · этап {stage}/{total}: {action}",
        "pkg_status": "{title} · этап 1/5: {action} {current}/{total} · {percent}%",
        "merge_status": "{title} · этап 2/5: объединение PKG {current}/{total}",
        "phase_status": "{title} · этап {stage}/5: {action} · {percent}%",
        "cleanup_status": "{title} · этап 5/5: очистка временных файлов",
        "scan_none": "Сканирование: PKG не найдены",
        "scan_progress": "Сканирование PKG: {current}/{total}",
        "scanning": "Сканирование…",
        "scan_log": "Сканирование PKG и чтение метаданных…",
        "source_missing_title": "Источник не выбран",
        "pkg_select_error": "Не удалось выбрать PKG",
        "no_buildable": "Нет игры, готовой к сборке.\n\n{details}",
        "select_buildable": "Отметьте хотя бы одну готовую к сборке игру.",
        "build_unavailable": "Сборка пока невозможна",
        "check_paths": "Проверьте пути",
        "build_started": "Запущена сборка: {titles}. Исходные PKG не изменяются.",
        "build_preparing": "{title} · подготовка к сборке",
        "build_flow": "──── {title}: извлечение → объединение → FFPFSC → проверка",
        "worker_missing": "Не найден рабочий модуль",
        "environment_unready": "Окружение не готово",
        "venv_missing": "Не найден .venv. Один раз запустите scripts/bootstrap_macos.sh.",
        "cli_missing": "Не найден CLI",
        "process_start_error": "Не удалось запустить процесс",
        "scan_error": "Ошибка сканирования",
        "scan_failed_title": "Сканирование завершилось с ошибкой",
        "exit_details": "Код {code}. Подробности находятся в журнале.",
        "build_success_log": "{title}: сборка и проверка успешно завершены.",
        "build_error_log": "{title}: ошибка — {error}",
        "cancelled_log": "Операция отменена пользователем; временные данные можно продолжить позже.",
        "process_error": "Ошибка процесса: {error}",
        "read_results_error": "Ошибка чтения результатов",
        "inventory_read_error": "Не удалось прочитать инвентарь",
        "scan_complete": "Сканирование завершено",
        "found_log": "Найдено: PKG {packages}, игр {games}, готово к сборке {buildable}, неподдерживаемых {unsupported}.",
        "patches_tooltip": "Будут применены патчи: {patches}",
        "none": "нет",
        "duplicate": "Дубликат: {path}",
        "unsupported": "Неподдерживаемые или зашифрованные PKG: {count}",
        "inventory_summary": "Игр: {games} · к сборке: {buildable} · неподдерживаемых: {unsupported}",
        "cancelled": "Отменено",
        "completed_errors": "Завершено с ошибками",
        "unknown_error": "неизвестная ошибка",
        "not_all_built": "Не все образы собраны",
        "success_count": "Успешно: {count}.\n\n{details}",
        "all_ready": "Все выбранные образы готовы",
        "build_complete_title": "Сборка завершена",
        "build_complete_message": "Успешно собрано и проверено: {count}.\n\n{path}",
        "cancelling": "Отмена…",
        "cancel_requested": "Запрошена отмена. Процесс будет остановлен безопасно.",
        "about_title": "О программе {app}",
        "about_body": "GUI для локального конвейера PS4 PKG → FFPFSC. Поддерживаются только законно полученные PKG, которые может прочитать приложенный shadPS4 0.7.0. Исходные файлы не изменяются.<br><br>Готовый образ создаётся MkPFS и проходит автоматическую проверку.",
        "operation_running": "Операция выполняется",
        "close_running": "Остановить текущую операцию и закрыть программу?",
    },
    "en": {
        "subtitle": "Build verified ShadowMountPlus images locally without modifying source PKGs",
        "about": "About",
        "source_section": "1. Source packages",
        "choose_pkg": "Choose PKG files…",
        "choose_folder": "Choose folder…",
        "clear": "Clear",
        "scan": "Scan",
        "storage_section": "2. Storage folders",
        "output_files": "Completed FFPFSC files",
        "temp_files": "Temporary files (default: system temp)",
        "reset_tmp": "Reset to system temp",
        "games_section": "3. Discovered games",
        "summary_initial": "Select a source and start scanning",
        "header_build": "Build",
        "header_type": "TITLE_ID / type",
        "header_name": "Title / file",
        "header_version": "Version",
        "log": "Log",
        "clear_log": "Clear log",
        "compatibility": "Compatibility:",
        "compat_current": "Current ShadowMountPlus",
        "compat_patched": "Patched ShadowMountPlus",
        "dlc": "DLC:",
        "dlc_auto": "Auto (prepare, do not embed)",
        "dlc_separate": "Separate images (experimental)",
        "dlc_off": "Exclude",
        "resume": "Resume interrupted work",
        "force": "Rebuild existing output",
        "keep_inner": "Keep inner exFAT",
        "ready": "Ready",
        "timing_idle": "Elapsed 00:00 · remaining —",
        "timing_calculating": "Elapsed 00:00 · remaining: calculating…",
        "timing": "Elapsed {elapsed} · remaining {remaining}",
        "calculating": "calculating…",
        "cancel": "Cancel",
        "reveal": "Open output folder",
        "build_selected": "Build selected",
        "check_readiness": "Check readiness",
        "choose_pkg_title": "Select PS4 PKGs",
        "pkg_filter": "PlayStation 4 PKG (*.pkg *.PKG);;All files (*)",
        "choose_source_folder": "Select a PKG folder (subfolders will be scanned)",
        "choose_output": "Select the FFPFSC output folder",
        "choose_temp": "Select the temporary files folder",
        "free_space": "{gib:.1f} GiB free",
        "directory_will_create": "directory will be created during build",
        "source_not_selected": "Source not selected",
        "source_empty": "No PKG files or folder selected",
        "source_recursive": "all subfolders will be scanned",
        "and_more": "… and {count} more",
        "stage_word": "stage",
        "stage_sources": "check metadata and extract PKGs",
        "stage_merge": "merge base and patches",
        "stage_compress": "compress FFPFSC",
        "stage_verify": "verify the container and required files",
        "stage_checksum_cleanup": "publish the result and clean up",
        "phase_scan": "scan files",
        "phase_exfat": "create exFAT",
        "phase_compress": "compress",
        "phase_write": "write image",
        "phase_verify": "verify blocks",
        "phase_compare": "compare data",
        "processing": "processing",
        "game": "Game",
        "extract_pkg": "extract PKG",
        "merge_pkg": "merge PKG",
        "cleanup_temp": "clean temporary files",
        "stage_status": "{title} · stage {stage}/{total}: {action}",
        "pkg_status": "{title} · stage 1/5: {action} {current}/{total} · {percent}%",
        "merge_status": "{title} · stage 2/5: merge PKG {current}/{total}",
        "phase_status": "{title} · stage {stage}/5: {action} · {percent}%",
        "cleanup_status": "{title} · stage 5/5: clean temporary files",
        "scan_none": "Scanning: no PKGs found",
        "scan_progress": "Scanning PKGs: {current}/{total}",
        "scanning": "Scanning…",
        "scan_log": "Scanning PKGs and reading metadata…",
        "source_missing_title": "Source not selected",
        "pkg_select_error": "Could not select PKG",
        "no_buildable": "No game is ready to build.\n\n{details}",
        "select_buildable": "Select at least one buildable game.",
        "build_unavailable": "Build is not available",
        "check_paths": "Check the selected paths",
        "build_started": "Build started: {titles}. Source PKGs will not be modified.",
        "build_preparing": "{title} · preparing build",
        "build_flow": "──── {title}: extract → merge → FFPFSC → verify",
        "worker_missing": "Worker module not found",
        "environment_unready": "Environment is not ready",
        "venv_missing": ".venv was not found. Run scripts/bootstrap_macos.sh once.",
        "cli_missing": "CLI not found",
        "process_start_error": "Could not start the worker",
        "scan_error": "Scan error",
        "scan_failed_title": "Scanning failed",
        "exit_details": "Exit code {code}. See the log for details.",
        "build_success_log": "{title}: build and verification completed successfully.",
        "build_error_log": "{title}: error — {error}",
        "cancelled_log": "Operation cancelled; temporary data can be resumed later.",
        "process_error": "Worker error: {error}",
        "read_results_error": "Could not read results",
        "inventory_read_error": "Could not read inventory",
        "scan_complete": "Scanning completed",
        "found_log": "Found: {packages} PKGs, {games} games, {buildable} buildable, {unsupported} unsupported.",
        "patches_tooltip": "Patches to apply: {patches}",
        "none": "none",
        "duplicate": "Duplicate: {path}",
        "unsupported": "Unsupported or encrypted PKGs: {count}",
        "inventory_summary": "Games: {games} · buildable: {buildable} · unsupported: {unsupported}",
        "cancelled": "Cancelled",
        "completed_errors": "Completed with errors",
        "unknown_error": "unknown error",
        "not_all_built": "Some images were not built",
        "success_count": "Successful: {count}.\n\n{details}",
        "all_ready": "All selected images are ready",
        "build_complete_title": "Build completed",
        "build_complete_message": "Successfully built and verified: {count}.\n\n{path}",
        "cancelling": "Cancelling…",
        "cancel_requested": "Cancellation requested. The worker will stop safely.",
        "about_title": "About {app}",
        "about_body": "GUI for the local PS4 PKG → FFPFSC pipeline. Only legally obtained PKGs supported by the bundled shadPS4 0.7.0 reader are accepted. Source files are never modified.<br><br>The output image is created with MkPFS and verified automatically.",
        "operation_running": "Operation in progress",
        "close_running": "Stop the current operation and close the application?",
    },
}


def _hide_windows_worker_console(arguments: Any) -> None:
    arguments.flags |= CREATE_NO_WINDOW


class MainWindow(QMainWindow):
    def __init__(self, root: Path, resources: Path | None = None) -> None:
        super().__init__()
        self.root = root
        self.resources = resources or root
        self.settings = QSettings()
        stored_language = self.settings.value("language", "ru", type=str)
        self.language = stored_language if stored_language in TEXTS else "ru"
        self.translated_widgets: list[tuple[QWidget, str]] = []
        self.stage_state: tuple[str, dict[str, Any]] = ("ready", {})
        self.summary_state: tuple[str, dict[str, Any]] = ("summary_initial", {})
        self.last_timing: tuple[float, str] | None = None
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        if sys.platform == "win32" and hasattr(
            self.process, "setCreateProcessArgumentsModifier"
        ):
            self.process.setCreateProcessArgumentsModifier(
                _hide_windows_worker_console
            )

        self.source_mode = "folder"
        self.pkg_files: tuple[Path, ...] = ()
        self.source_folder: Path | None = None
        self.inventory: dict[str, Any] | None = None
        self.stdout_buffer = ""
        self.stderr_buffer = ""
        self.operation: str | None = None
        self.build_queue: list[str] = []
        self.build_results: dict[str, Any] = {}
        self.build_total_count = 0
        self.current_build_title: str | None = None
        self.current_build_stage = 0
        self.cancel_requested = False
        self.progress_kind: str | None = None
        self.progress_started_at: float | None = None
        self.progress_percent = 0.0
        self.scan_total = 0
        self.scan_seen = 0
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(1000)
        self.progress_timer.timeout.connect(self._update_elapsed_time)

        self._build_ui()
        self._restore_settings()
        self._update_source_label()
        self._update_controls()

    def _t(self, key: str, **values: Any) -> str:
        text = TEXTS[self.language].get(key, TEXTS["ru"].get(key, key))
        return text.format(**values) if values else text

    def _bind_text(self, widget: QWidget, key: str) -> QWidget:
        self.translated_widgets.append((widget, key))
        widget.setProperty("translationKey", key)
        if hasattr(widget, "setText"):
            widget.setText(self._t(key))
        return widget

    def _set_stage(self, key: str, **values: Any) -> None:
        self.stage_state = (key, values)
        self._render_stage()

    def _render_stage(self) -> None:
        key, values = self.stage_state
        rendered = dict(values)
        for name, value in values.items():
            if name.endswith("_key"):
                rendered[name.removesuffix("_key")] = self._t(str(value))
        self.stage_label.setText(self._t(key, **rendered))

    def _set_summary(self, key: str, **values: Any) -> None:
        self.summary_state = (key, values)
        self.summary_label.setText(self._t(key, **values))

    def _render_last_timing(self) -> None:
        if self.last_timing is None:
            self.time_label.setText(self._t("timing_idle"))
            return
        elapsed, remaining = self.last_timing
        self.time_label.setText(
            self._t(
                "timing",
                elapsed=format_duration(elapsed),
                remaining=remaining,
            )
        )

    def _change_language(self, _index: int) -> None:
        language = self.language_combo.currentData()
        if language not in TEXTS or language == self.language:
            return
        self.language = str(language)
        self.settings.setValue("language", self.language)
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        for widget, key in self.translated_widgets:
            if hasattr(widget, "setText"):
                widget.setText(self._t(key))
        self.games_tree.setHeaderLabels(
            [
                self._t("header_build"),
                self._t("header_type"),
                self._t("header_name"),
                self._t("header_version"),
                "Patch",
                "DLC",
            ]
        )
        combo_text = {
            "current-smp": "compat_current",
            "patched-smp": "compat_patched",
        }
        for index in range(self.compat_combo.count()):
            self.compat_combo.setItemText(
                index, self._t(combo_text[str(self.compat_combo.itemData(index))])
            )
        dlc_text = {
            "auto": "dlc_auto",
            "separate": "dlc_separate",
            "off": "dlc_off",
        }
        for index in range(self.dlc_combo.count()):
            self.dlc_combo.setItemText(
                index, self._t(dlc_text[str(self.dlc_combo.itemData(index))])
            )
        self._update_source_label()
        self._update_storage_labels()
        if self.inventory is not None:
            checked = {
                str(self.games_tree.topLevelItem(index).data(0, Qt.ItemDataRole.UserRole))
                for index in range(self.games_tree.topLevelItemCount())
                if self.games_tree.topLevelItem(index).checkState(0)
                == Qt.CheckState.Checked
            }
            self._populate_inventory()
            for index in range(self.games_tree.topLevelItemCount()):
                item = self.games_tree.topLevelItem(index)
                title_id = item.data(0, Qt.ItemDataRole.UserRole)
                if title_id and str(title_id) not in checked:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
        self._render_stage()
        summary_key, summary_values = self.summary_state
        self.summary_label.setText(self._t(summary_key, **summary_values))
        if self.progress_started_at is not None:
            self._update_elapsed_time()
        else:
            self._render_last_timing()
        self._update_controls()

    def _build_ui(self) -> None:
        self.setWindowTitle(f"{APP_NAME} — PKG → FFPFSC")
        self.resize(1120, 860)
        self.setMinimumSize(880, 700)

        central = QWidget()
        page = QVBoxLayout(central)
        page.setContentsMargins(24, 20, 24, 22)
        page.setSpacing(14)
        self.setCentralWidget(central)

        header = QHBoxLayout()
        mark = QLabel("P4")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(48, 48)
        mark.setObjectName("brandMark")
        title_box = QVBoxLayout()
        title = QLabel("PS4 PKG → FFPFSC")
        title.setObjectName("pageTitle")
        subtitle = self._bind_text(QLabel(), "subtitle")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addWidget(mark)
        header.addLayout(title_box)
        header.addStretch()
        self.language_combo = QComboBox()
        self.language_combo.addItem("Русский", "ru")
        self.language_combo.addItem("English", "en")
        self.language_combo.setCurrentIndex(0 if self.language == "ru" else 1)
        self.language_combo.setFixedWidth(105)
        self.language_combo.currentIndexChanged.connect(self._change_language)
        header.addWidget(self.language_combo)
        about = self._bind_text(QPushButton(), "about")
        about.setObjectName("quietButton")
        about.clicked.connect(self._show_about)
        header.addWidget(about)
        page.addLayout(header)

        self.source_card = QFrame()
        self.source_card.setObjectName("card")
        source_layout = QGridLayout(self.source_card)
        source_layout.setContentsMargins(18, 16, 18, 16)
        source_layout.setHorizontalSpacing(10)
        source_layout.setVerticalSpacing(12)

        source_title = self._bind_text(QLabel(), "source_section")
        source_title.setObjectName("sectionTitle")
        source_layout.addWidget(source_title, 0, 0, 1, 4)
        self.source_label = QLabel()
        self.source_label.setObjectName("pathLabel")
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.source_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        source_layout.addWidget(self.source_label, 1, 0, 1, 4)

        choose_files = self._bind_text(QPushButton(), "choose_pkg")
        choose_files.clicked.connect(self._choose_files)
        choose_folder = self._bind_text(QPushButton(), "choose_folder")
        choose_folder.clicked.connect(self._choose_folder)
        clear_source = self._bind_text(QPushButton(), "clear")
        clear_source.setObjectName("quietButton")
        clear_source.clicked.connect(self._clear_source)
        self.scan_button = self._bind_text(QPushButton(), "scan")
        self.scan_button.setObjectName("primaryButton")
        self.scan_button.clicked.connect(self._start_scan)
        source_layout.addWidget(choose_files, 2, 0)
        source_layout.addWidget(choose_folder, 2, 1)
        source_layout.addWidget(clear_source, 2, 2)
        source_layout.addWidget(self.scan_button, 2, 3)

        output_title = self._bind_text(QLabel(), "storage_section")
        output_title.setObjectName("sectionTitle")
        source_layout.addWidget(output_title, 3, 0, 1, 4)
        output_files_label = self._bind_text(QLabel(), "output_files")
        source_layout.addWidget(output_files_label, 4, 0, 1, 4)
        self.output_label = QLabel()
        self.output_label.setObjectName("pathLabel")
        self.output_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        source_layout.addWidget(self.output_label, 5, 0, 1, 3)
        output_button = self._bind_text(QPushButton(), "choose_folder")
        output_button.clicked.connect(self._choose_output)
        source_layout.addWidget(output_button, 5, 3)
        temp_files_label = self._bind_text(QLabel(), "temp_files")
        source_layout.addWidget(temp_files_label, 6, 0, 1, 4)
        self.temp_label = QLabel()
        self.temp_label.setObjectName("pathLabel")
        self.temp_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        source_layout.addWidget(self.temp_label, 7, 0, 1, 2)
        reset_temp = self._bind_text(QPushButton(), "reset_tmp")
        reset_temp.setObjectName("quietButton")
        reset_temp.clicked.connect(self._reset_temp)
        source_layout.addWidget(reset_temp, 7, 2)
        temp_button = self._bind_text(QPushButton(), "choose_folder")
        temp_button.clicked.connect(self._choose_temp)
        source_layout.addWidget(temp_button, 7, 3)
        source_layout.setColumnStretch(2, 1)
        page.addWidget(self.source_card)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        games_card = QFrame()
        games_card.setObjectName("card")
        games_layout = QVBoxLayout(games_card)
        games_layout.setContentsMargins(18, 14, 18, 14)
        games_header = QHBoxLayout()
        games_title = self._bind_text(QLabel(), "games_section")
        games_title.setObjectName("sectionTitle")
        self.summary_label = QLabel(self._t("summary_initial"))
        self.summary_label.setObjectName("summary")
        games_header.addWidget(games_title)
        games_header.addStretch()
        games_header.addWidget(self.summary_label)
        games_layout.addLayout(games_header)

        self.games_tree = QTreeWidget()
        self.games_tree.setColumnCount(6)
        self.games_tree.setHeaderLabels(
            [
                self._t("header_build"),
                self._t("header_type"),
                self._t("header_name"),
                self._t("header_version"),
                "Patch",
                "DLC",
            ]
        )
        self.games_tree.setRootIsDecorated(True)
        self.games_tree.setAlternatingRowColors(True)
        self.games_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.games_tree.setUniformRowHeights(True)
        self.games_tree.itemChanged.connect(self._tree_item_changed)
        header_view = self.games_tree.header()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        games_layout.addWidget(self.games_tree)
        splitter.addWidget(games_card)

        log_card = QFrame()
        log_card.setObjectName("card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 12, 18, 14)
        log_header = QHBoxLayout()
        log_title = self._bind_text(QLabel(), "log")
        log_title.setObjectName("sectionTitle")
        clear_log = self._bind_text(QPushButton(), "clear_log")
        clear_log.setObjectName("quietButton")
        clear_log.clicked.connect(self.log_edit_clear)
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_header.addWidget(clear_log)
        log_layout.addLayout(log_header)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(5000)
        self.log_edit.document().setDefaultFont(QFont("Menlo", 11))
        log_layout.addWidget(self.log_edit)
        splitter.addWidget(log_card)
        splitter.setSizes([360, 180])
        page.addWidget(splitter, 1)

        options = QGridLayout()
        options.setHorizontalSpacing(10)
        options.setVerticalSpacing(5)
        compatibility_label = self._bind_text(QLabel(), "compatibility")
        options.addWidget(compatibility_label, 0, 0)
        self.compat_combo = QComboBox()
        self.compat_combo.addItem(self._t("compat_current"), "current-smp")
        self.compat_combo.addItem(self._t("compat_patched"), "patched-smp")
        self.compat_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        options.addWidget(self.compat_combo, 0, 1)
        dlc_label = self._bind_text(QLabel(), "dlc")
        options.addWidget(dlc_label, 0, 2)
        self.dlc_combo = QComboBox()
        self.dlc_combo.addItem(self._t("dlc_auto"), "auto")
        self.dlc_combo.addItem(self._t("dlc_separate"), "separate")
        self.dlc_combo.addItem(self._t("dlc_off"), "off")
        self.dlc_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        options.addWidget(self.dlc_combo, 0, 3)
        self.resume_check = self._bind_text(QCheckBox(), "resume")
        self.resume_check.setChecked(True)
        self.force_check = self._bind_text(QCheckBox(), "force")
        self.keep_inner_check = self._bind_text(QCheckBox(), "keep_inner")
        options.addWidget(self.resume_check, 1, 1)
        options.addWidget(self.force_check, 1, 2)
        options.addWidget(self.keep_inner_check, 1, 3)
        options.setColumnStretch(4, 1)
        page.addLayout(options)

        footer = QHBoxLayout()
        self.stage_label = QLabel(self._t("ready"))
        self.stage_label.setObjectName("stage")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        self.progress.setTextVisible(True)
        self.progress.setMinimumWidth(260)
        self.progress.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.time_label = QLabel(self._t("timing_idle"))
        self.time_label.setObjectName("timing")
        self.cancel_button = self._bind_text(QPushButton(), "cancel")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.clicked.connect(self._cancel)
        self.reveal_button = self._bind_text(QPushButton(), "reveal")
        self.reveal_button.clicked.connect(self._reveal_output)
        self.build_button = QPushButton(self._t("build_selected"))
        self.build_button.setObjectName("primaryButton")
        self.build_button.clicked.connect(self._start_build)
        status_box = QVBoxLayout()
        status_box.setSpacing(2)
        status_box.addWidget(self.stage_label)
        status_box.addWidget(self.time_label)
        footer.addLayout(status_box, 2)
        footer.addWidget(self.progress, 3)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.reveal_button)
        footer.addWidget(self.build_button)
        page.addLayout(footer)

        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #11151b; color: #e8edf5; }
            QLabel { background: transparent; }
            QLabel#pageTitle { font-size: 24px; font-weight: 700; }
            QLabel#subtitle, QLabel#summary { color: #9ba9bc; }
            QLabel#sectionTitle { font-size: 14px; font-weight: 700; }
            QLabel#brandMark {
                background: #536dfe; border-radius: 13px; color: white;
                font-size: 17px; font-weight: 800;
            }
            QLabel#pathLabel {
                background: #0c1015; border: 1px solid #2a3340; border-radius: 7px;
                color: #bfcbe0; padding: 8px; min-height: 18px;
            }
            QLabel#stage { color: #d5deec; font-weight: 600; }
            QLabel#timing { color: #8290a5; font-size: 11px; }
            QFrame#card {
                background: #181e27; border: 1px solid #2b3543; border-radius: 10px;
            }
            QPushButton {
                background: #263140; border: 1px solid #3a485b; border-radius: 7px;
                padding: 7px 13px; min-height: 19px;
            }
            QPushButton:hover { background: #303d4f; }
            QPushButton:disabled { color: #667083; background: #1c222b; }
            QPushButton#primaryButton {
                background: #536dfe; border-color: #6d82ff; color: white; font-weight: 700;
            }
            QPushButton#primaryButton:hover { background: #6279ff; }
            QPushButton#quietButton { background: transparent; border-color: #303a48; }
            QPushButton#dangerButton { background: #43242a; border-color: #74404a; }
            QTreeWidget, QPlainTextEdit {
                background: #0d1218; border: 1px solid #2b3543; border-radius: 7px;
                alternate-background-color: #111821; selection-background-color: #334f9d;
            }
            QHeaderView::section {
                background: #202936; color: #b9c5d7; border: none;
                border-right: 1px solid #303a48; padding: 7px;
            }
            QComboBox, QCheckBox { padding: 4px; }
            QComboBox {
                background: #202936; border: 1px solid #374355; border-radius: 6px;
                padding: 6px 10px;
            }
            QProgressBar {
                background: #202936; border: none; border-radius: 6px;
                min-height: 18px; color: white; font-size: 11px; font-weight: 700;
                text-align: center;
            }
            QProgressBar::chunk { background: #536dfe; border-radius: 4px; }
            QSplitter::handle { background: transparent; height: 8px; }
            """
        )

    def _restore_settings(self) -> None:
        output = self.settings.value("output_dir", str(self.root / "output"), type=str)
        self.output_dir = Path(output).expanduser()
        temp = self.settings.value(
            "temp_dir", str(default_temporary_directory()), type=str
        )
        self.temp_dir = Path(temp).expanduser()
        folder = self.settings.value("source_folder", "", type=str)
        if folder and Path(folder).is_dir():
            self.source_mode = "folder"
            self.source_folder = Path(folder)
        geometry = self.settings.value("window_geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        self._update_storage_labels()

    def _save_settings(self) -> None:
        self.settings.setValue("output_dir", str(self.output_dir))
        self.settings.setValue("temp_dir", str(self.temp_dir))
        self.settings.setValue(
            "source_folder", str(self.source_folder) if self.source_folder else ""
        )
        self.settings.setValue("window_geometry", self.saveGeometry())

    def _choose_files(self) -> None:
        start = str(self.source_folder or self.root / "pkg")
        names, _ = QFileDialog.getOpenFileNames(
            self,
            self._t("choose_pkg_title"),
            start,
            self._t("pkg_filter"),
        )
        if not names:
            return
        try:
            _, files, _ = validate_source("files", names, None, self.language)
        except (OSError, ValueError) as error:
            self._show_error(self._t("pkg_select_error"), str(error))
            return
        self.source_mode = "files"
        self.pkg_files = files
        self.source_folder = None
        self.inventory = None
        self.games_tree.clear()
        self._set_summary("summary_initial")
        self._update_source_label()
        self._update_controls()

    def _choose_folder(self) -> None:
        start = str(self.source_folder or self.root / "pkg")
        name = QFileDialog.getExistingDirectory(
            self,
            self._t("choose_source_folder"),
            start,
            QFileDialog.Option.ShowDirsOnly,
        )
        if not name:
            return
        self.source_mode = "folder"
        self.source_folder = Path(name).resolve()
        self.pkg_files = ()
        self.inventory = None
        self.games_tree.clear()
        self._set_summary("summary_initial")
        self._update_source_label()
        self._update_controls()
        self._save_settings()

    def _choose_output(self) -> None:
        name = QFileDialog.getExistingDirectory(
            self,
            self._t("choose_output"),
            str(self.output_dir),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not name:
            return
        self.output_dir = Path(name).resolve()
        self._update_storage_labels()
        self._save_settings()
        self._update_controls()

    def _choose_temp(self) -> None:
        start = str(
            self.temp_dir
            if self.temp_dir.is_dir()
            else default_temporary_directory()
        )
        name = QFileDialog.getExistingDirectory(
            self,
            self._t("choose_temp"),
            start,
            QFileDialog.Option.ShowDirsOnly,
        )
        if not name:
            return
        self.temp_dir = Path(name).resolve()
        self._update_storage_labels()
        self._save_settings()

    def _reset_temp(self) -> None:
        self.temp_dir = default_temporary_directory()
        self._update_storage_labels()
        self._save_settings()

    def _update_storage_labels(self) -> None:
        self.output_label.setText(str(self.output_dir))
        self.output_label.setToolTip(str(self.output_dir))
        detail = str(self.temp_dir)
        try:
            probe = self.temp_dir if self.temp_dir.exists() else self.temp_dir.parent
            free = shutil.disk_usage(probe).free
            detail += "  ·  " + self._t("free_space", gib=free / 1024**3)
        except OSError:
            detail += "  ·  " + self._t("directory_will_create")
        self.temp_label.setText(detail)
        self.temp_label.setToolTip(str(self.temp_dir))

    def _clear_source(self) -> None:
        self.pkg_files = ()
        self.source_folder = None
        self.inventory = None
        self.games_tree.clear()
        self._set_summary("source_not_selected")
        self._update_source_label()
        self._update_controls()

    def _update_source_label(self) -> None:
        if self.source_mode == "files" and self.pkg_files:
            preview = ", ".join(path.name for path in self.pkg_files[:3])
            if len(self.pkg_files) > 3:
                preview += " " + self._t(
                    "and_more", count=len(self.pkg_files) - 3
                )
            self.source_label.setText(f"{len(self.pkg_files)} PKG: {preview}")
            self.source_label.setToolTip("\n".join(str(path) for path in self.pkg_files))
        elif self.source_folder:
            self.source_label.setText(
                f"{self.source_folder}  ·  {self._t('source_recursive')}"
            )
            self.source_label.setToolTip(str(self.source_folder))
        else:
            self.source_label.setText(self._t("source_empty"))
            self.source_label.setToolTip("")

    def _source_arguments(self) -> list[str]:
        return source_cli_arguments(
            self.source_mode,
            self.pkg_files,
            self.source_folder,
            self.language,
        )

    def _base_arguments(self) -> list[str]:
        arguments = [
            "--output-dir",
            str(self.output_dir.resolve()),
            "--compat",
            str(self.compat_combo.currentData()),
            "--include-dlc",
            str(self.dlc_combo.currentData()),
            "--console-log",
            "--json",
        ]
        arguments.extend(temporary_cli_arguments(self.temp_dir))
        arguments.extend(self._source_arguments())
        if self.resume_check.isChecked():
            arguments.append("--resume")
        else:
            arguments.append("--no-resume")
        if self.force_check.isChecked():
            arguments.append("--force")
        if self.keep_inner_check.isChecked():
            arguments.append("--keep-inner-image")
        return arguments

    def _begin_progress(self, kind: str) -> None:
        self.progress_kind = kind
        self.progress_started_at = time.monotonic()
        self.progress_percent = 0.0
        self.scan_total = 0
        self.scan_seen = 0
        self.current_build_stage = 0
        self.last_timing = None
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        self.time_label.setText(self._t("timing_calculating"))
        self.progress_timer.start()

    def _set_progress(
        self,
        value: float,
        status_key: str | None = None,
        **status_values: Any,
    ) -> None:
        if self.progress_started_at is None:
            return
        bounded = max(0.0, min(100.0, value))
        self.progress_percent = max(self.progress_percent, bounded)
        self.progress.setRange(0, 100)
        self.progress.setValue(round(self.progress_percent))
        if status_key:
            self._set_stage(status_key, **status_values)
        self._update_elapsed_time()

    def _finish_progress(self, completed: bool) -> None:
        if self.progress_started_at is None:
            return
        elapsed = time.monotonic() - self.progress_started_at
        if completed:
            self.progress_percent = 100.0
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            remaining = "00:00"
        else:
            remaining = "—"
        self.last_timing = (elapsed, remaining)
        self._render_last_timing()
        self.progress_timer.stop()
        self.progress_started_at = None
        self.progress_kind = None

    def _update_elapsed_time(self) -> None:
        if self.progress_started_at is None:
            return
        elapsed = time.monotonic() - self.progress_started_at
        eta = estimate_remaining_seconds(elapsed, self.progress_percent)
        if self.progress_percent >= 100:
            remaining = "00:00"
        elif eta is None or elapsed < 3 or self.progress_percent < 1:
            remaining = self._t("calculating")
        else:
            remaining = f"≈ {format_duration(eta)}"
        self.time_label.setText(
            self._t(
                "timing",
                elapsed=format_duration(elapsed),
                remaining=remaining,
            )
        )

    def _set_build_progress(
        self,
        local_value: float,
        status_key: str | None = None,
        **status_values: Any,
    ) -> None:
        total = max(1, self.build_total_count)
        completed = min(len(self.build_results), total)
        overall = (
            completed * 100.0 + max(0.0, min(100.0, local_value))
        ) / total
        self._set_progress(overall, status_key, **status_values)

    @staticmethod
    def _progress_ratio(event: dict[str, Any]) -> float:
        try:
            current = float(event.get("current", 0))
            total = float(event.get("total", 0))
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, current / total)) if total > 0 else 0.0

    def _handle_worker_progress(self, event: dict[str, Any]) -> None:
        if self.progress_kind != "build":
            return
        title = self.current_build_title or self._t("game")
        scope = str(event.get("scope") or "")
        if event.get("action") == "status":
            return
        ratio = self._progress_ratio(event)
        try:
            package_index = max(1, int(event.get("package_index", 1)))
            package_total = max(1, int(event.get("package_total", 1)))
        except (TypeError, ValueError):
            package_index = package_total = 1

        if scope == "extract":
            package_progress = (package_index - 1 + ratio) / package_total
            local = 2.0 + 28.0 * package_progress
            self._set_build_progress(
                local,
                "pkg_status",
                title=title,
                action_key="extract_pkg",
                current=package_index,
                total=package_total,
                percent=round(ratio * 100),
            )
            return
        if scope == "merge_package":
            local = 30.0 + 25.0 * ratio
            self._set_build_progress(
                local,
                "merge_status",
                title=title,
                current=event.get("current", 0),
                total=event.get("total", 0),
            )
            return
        if scope == "mkpfs" and self.current_build_stage in {3, 4}:
            phase_name = str(event.get("phase") or "")
            phase_key = MKPFS_PHASE_KEYS.get(phase_name)
            phase_values = (
                {"action_key": phase_key}
                if phase_key
                else {"action": phase_name or self._t("processing")}
            )
            if self.current_build_stage == 3:
                local = 55.0 + 33.0 * ratio
            else:
                local = 88.0 + 8.0 * ratio
            self._set_build_progress(
                local,
                "phase_status",
                title=title,
                stage=self.current_build_stage,
                percent=round(ratio * 100),
                **phase_values,
            )
            return
        if scope == "cleanup":
            self._set_build_progress(
                99.0, "cleanup_status", title=title
            )

    def _handle_progress_line(self, line: str) -> bool:
        event = parse_progress_event(line)
        if event is None:
            return False
        kind = event.get("kind")
        if kind == "scan_total" and self.progress_kind == "scan":
            self.scan_total = max(0, int(event.get("total", 0)))
            if self.scan_total == 0:
                self._set_progress(95, "scan_none")
        elif kind == "scan_item" and self.progress_kind == "scan":
            self.scan_seen += 1
            if self.scan_total:
                percent = min(95.0, self.scan_seen * 95.0 / self.scan_total)
                self._set_progress(
                    percent,
                    "scan_progress",
                    current=self.scan_seen,
                    total=self.scan_total,
                )
        elif kind == "build_stage" and self.progress_kind == "build":
            stage = int(event.get("stage", 0))
            self.current_build_stage = stage
            stage_key = BUILD_STAGE_KEYS.get(stage, "processing")
            self._set_build_progress(
                BUILD_STAGE_START.get(stage, 0.0),
                "stage_status",
                title=self.current_build_title or self._t("game"),
                stage=stage,
                total=event.get("total", 5),
                action_key=stage_key,
            )
        elif kind == "worker":
            self._handle_worker_progress(event)
        return kind == "worker"

    def _start_scan(self) -> None:
        try:
            self._source_arguments()
        except (OSError, ValueError) as error:
            self._show_error(self._t("source_missing_title"), str(error))
            return
        self.inventory = None
        self.games_tree.clear()
        self._set_summary("scanning")
        self._append_log(self._t("scan_log"))
        self._begin_progress("scan")
        self._start_process("scan", ["scan", *self._base_arguments()])

    def _start_build(self) -> None:
        selected: list[str] = []
        for index in range(self.games_tree.topLevelItemCount()):
            item = self.games_tree.topLevelItem(index)
            title_id = item.data(0, Qt.ItemDataRole.UserRole)
            if title_id and item.checkState(0) == Qt.CheckState.Checked:
                selected.append(str(title_id))
        if not selected:
            blocked: list[str] = []
            if self.inventory:
                for title_id, game in sorted(self.inventory.get("games", {}).items()):
                    if not game.get("buildable"):
                        blocked.append(
                            f"{title_id} — {game_block_reason(game, self.language)}"
                        )
            detail = (
                self._t("no_buildable", details="\n".join(blocked))
                if blocked
                else self._t("select_buildable")
            )
            self._show_error(self._t("build_unavailable"), detail)
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            workspace = temporary_workspace(self.temp_dir)
            workspace.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=workspace,
                prefix="ps4ffpsc-gui-write-test-",
                delete=True,
            ):
                pass
            self._source_arguments()
        except OSError as error:
            self._show_error(self._t("check_paths"), str(error))
            return
        self.build_queue = selected
        self.build_results = {}
        self.build_total_count = len(selected)
        self.current_build_title = None
        self.cancel_requested = False
        self._begin_progress("build")
        self._append_log(
            self._t("build_started", titles=", ".join(selected))
        )
        self._start_next_build()

    def _start_next_build(self) -> None:
        if self.cancel_requested or not self.build_queue:
            self._finish_build_batch()
            return
        title_id = self.build_queue.pop(0)
        self.current_build_title = title_id
        self.current_build_stage = 0
        self._set_build_progress(
            0, "build_preparing", title=title_id
        )
        self._append_log(self._t("build_flow", title=title_id))
        self._start_process(
            f"build:{title_id}",
            ["build", title_id, *self._base_arguments()],
        )

    def _start_process(self, operation: str, arguments: list[str]) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        if is_frozen():
            program = worker_executable()
            if not program.is_file():
                self._show_error(self._t("worker_missing"), str(program))
                return
            process_arguments = ["--worker", *arguments]
        else:
            program = self.resources / ".venv" / "bin" / "python"
            if not program.is_file():
                self._show_error(
                    self._t("environment_unready"),
                    self._t("venv_missing"),
                )
                return
            launcher = self.resources / "ps4ffpsc"
            if not launcher.is_file():
                self._show_error(self._t("cli_missing"), str(launcher))
                return
            process_arguments = [str(launcher), *arguments]
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        environment.insert("PYTHONUTF8", "1")
        environment.insert("PYTHONIOENCODING", "utf-8")
        environment.insert("PS4FFPSC_GUI_PROGRESS", "1")
        environment.insert("PS4FFPSC_DATA_ROOT", str(self.root))
        environment.insert("PS4FFPSC_RESOURCE_ROOT", str(self.resources))
        self.process.setProcessEnvironment(environment)
        self.process.setWorkingDirectory(str(self.root))
        self.process.setProgram(str(program))
        self.process.setArguments(process_arguments)
        self.stdout_buffer = ""
        self.stderr_buffer = ""
        self.operation = operation
        self.cancel_requested = False
        if operation == "scan":
            self._set_stage("scanning")
        self._update_controls()
        self.process.start()
        if not self.process.waitForStarted(3000):
            self._show_error(
                self._t("process_start_error"), self.process.errorString()
            )
            self.operation = None
            self._finish_progress(False)
            self._update_controls()

    def _read_stdout(self) -> None:
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.stdout_buffer += data

    def _read_stderr(self) -> None:
        data = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        self.stderr_buffer += data.replace("\r", "\n")
        lines = self.stderr_buffer.split("\n")
        self.stderr_buffer = lines.pop()
        for line in lines:
            if line and not self._handle_progress_line(line):
                self._append_log(line)

    def _flush_stderr(self) -> None:
        line = self.stderr_buffer.strip()
        self.stderr_buffer = ""
        if line and not self._handle_progress_line(line):
            self._append_log(line)

    def _process_finished(
        self,
        exit_code: int,
        _status: QProcess.ExitStatus,
    ) -> None:
        operation = self.operation
        self._read_stdout()
        self._read_stderr()
        self._flush_stderr()
        self.operation = None

        payload: Any = None
        if self.stdout_buffer.strip():
            try:
                payload = json.loads(self.stdout_buffer)
            except json.JSONDecodeError:
                self._append_log(self.stdout_buffer.strip())

        if operation == "scan":
            if exit_code in (0, 3):
                self._finish_scan(payload)
            else:
                self._finish_progress(False)
                self._set_stage("scan_error")
                self._show_error(
                    self._t("scan_failed_title"),
                    self._t("exit_details", code=exit_code),
                )
        elif operation and operation.startswith("build:"):
            title_id = operation.split(":", 1)[1]
            if exit_code == 0:
                self.build_results[title_id] = payload or {"status": "completed"}
                self._append_log(self._t("build_success_log", title=title_id))
            else:
                error_text = build_error_text(
                    payload, title_id, exit_code, self.language
                )
                self.build_results[title_id] = {
                    "status": "cancelled" if self.cancel_requested else "failed",
                    "exit_code": exit_code,
                    "error": error_text,
                }
                self._append_log(
                    self._t("build_error_log", title=title_id, error=error_text)
                )
            self._set_build_progress(0)
            self._start_next_build()
        self._update_controls()

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.Crashed and self.cancel_requested:
            self._append_log(self._t("cancelled_log"))
            return
        self._append_log(
            self._t("process_error", error=self.process.errorString())
        )

    def _finish_scan(self, payload: Any) -> None:
        inventory_path = scan_inventory_path(payload, self.temp_dir)
        try:
            self.inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            self._finish_progress(False)
            self._set_stage("read_results_error")
            self._show_error(self._t("inventory_read_error"), str(error))
            return
        self._populate_inventory()
        summary = inventory_summary(self.inventory)
        self._finish_progress(True)
        self._set_stage("scan_complete")
        self._append_log(
            self._t(
                "found_log",
                packages=summary["packages"],
                games=summary["games"],
                buildable=summary["buildable"],
                unsupported=summary["unsupported"],
            )
        )

    def _populate_inventory(self) -> None:
        self.games_tree.blockSignals(True)
        self.games_tree.clear()
        assert self.inventory is not None
        games = self.inventory.get("games", {})
        for title_id, game in sorted(games.items()):
            buildable = bool(game.get("buildable"))
            patches = sorted(
                {
                    str(item.get("app_version") or "—")
                    for item in game.get("patches", [])
                }
            )
            top = QTreeWidgetItem(
                [
                    "",
                    title_id,
                    str(game.get("title") or title_id),
                    str(
                        (game.get("patches") or game.get("base") or [{}])[-1].get(
                            "app_version", "—"
                        )
                    ),
                    str(len(game.get("patches", []))),
                    str(len(game.get("dlc", []))),
                ]
            )
            top.setData(0, Qt.ItemDataRole.UserRole, title_id)
            top.setCheckState(
                0, Qt.CheckState.Checked if buildable else Qt.CheckState.Unchecked
            )
            if not buildable:
                top.setFlags(top.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                top.setForeground(2, QColor("#e58b95"))
                reason = game_block_reason(game, self.language)
                top.setToolTip(2, reason)
                top.setText(2, f"{top.text(2)}  —  {reason}")
            else:
                top.setToolTip(
                    2,
                    self._t(
                        "patches_tooltip",
                        patches=", ".join(patches) if patches else self._t("none"),
                    ),
                )
            self.games_tree.addTopLevelItem(top)

            groups = (
                ("base", "BASE"),
                ("patches", "PATCH"),
                ("dlc", "DLC"),
                ("unknown", "UNKNOWN"),
            )
            for key, label in groups:
                for package in game.get(key, []):
                    child = QTreeWidgetItem(
                        [
                            "",
                            label,
                            Path(package.get("path", "")).name,
                            package_version_text(package),
                            "",
                            "",
                        ]
                    )
                    child.setToolTip(2, str(package.get("path", "")))
                    if package.get("duplicate_of"):
                        child.setForeground(2, QColor("#c6a15b"))
                        child.setToolTip(
                            2,
                            self._t("duplicate", path=package["duplicate_of"]),
                        )
                    top.addChild(child)
            top.setExpanded(True)

        unsupported = self.inventory.get("unsupported", [])
        if unsupported:
            blocked = QTreeWidgetItem(
                [
                    "",
                    "UNSUPPORTED",
                    self._t("unsupported", count=len(unsupported)),
                    "",
                    "",
                    "",
                ]
            )
            blocked.setForeground(2, QColor("#e58b95"))
            self.games_tree.addTopLevelItem(blocked)
            for package in unsupported:
                child = QTreeWidgetItem(
                    ["", "PKG", Path(package.get("path", "")).name, "—", "", ""]
                )
                child.setToolTip(2, str(package.get("reason") or package.get("error") or ""))
                blocked.addChild(child)
            blocked.setExpanded(True)

        summary = inventory_summary(self.inventory)
        self._set_summary(
            "inventory_summary",
            games=summary["games"],
            buildable=summary["buildable"],
            unsupported=summary["unsupported"],
        )
        self.games_tree.blockSignals(False)
        self._update_controls()

    def _finish_build_batch(self) -> None:
        failed = [
            title_id
            for title_id, result in self.build_results.items()
            if result.get("status") in {"failed", "cancelled"}
        ]
        succeeded = len(self.build_results) - len(failed)
        self._finish_progress(not self.cancel_requested)
        if self.cancel_requested:
            self._set_stage("cancelled")
        elif failed:
            self._set_stage("completed_errors")
            details = "\n".join(
                f"{title_id}: "
                f"{self.build_results[title_id].get('error', self._t('unknown_error'))}"
                for title_id in failed
            )
            self._show_error(
                self._t("not_all_built"),
                self._t("success_count", count=succeeded, details=details),
            )
        else:
            self._set_stage("all_ready")
            QMessageBox.information(
                self,
                self._t("build_complete_title"),
                self._t(
                    "build_complete_message",
                    count=succeeded,
                    path=self.output_dir,
                ),
            )
        self.build_queue = []
        self.current_build_title = None
        self.current_build_stage = 0
        self._update_controls()

    def _cancel(self) -> None:
        if self.process.state() == QProcess.ProcessState.NotRunning:
            return
        self.cancel_requested = True
        self.build_queue = []
        self._set_stage("cancelling")
        self._append_log(self._t("cancel_requested"))
        self.process.terminate()
        QTimer.singleShot(
            3000,
            lambda: self.process.kill()
            if self.process.state() != QProcess.ProcessState.NotRunning
            else None,
        )

    def _tree_item_changed(self, _item: QTreeWidgetItem, _column: int) -> None:
        self._update_controls()

    def _has_checked_game(self) -> bool:
        return any(
            self.games_tree.topLevelItem(index).data(0, Qt.ItemDataRole.UserRole)
            and self.games_tree.topLevelItem(index).checkState(0)
            == Qt.CheckState.Checked
            for index in range(self.games_tree.topLevelItemCount())
        )

    def _update_controls(self) -> None:
        running = self.process.state() != QProcess.ProcessState.NotRunning
        has_source = bool(self.pkg_files) if self.source_mode == "files" else bool(self.source_folder)
        self.source_card.setEnabled(not running)
        self.scan_button.setEnabled(has_source and not running)
        has_checked = self._has_checked_game()
        self.build_button.setText(
            self._t("build_selected")
            if has_checked
            else self._t("check_readiness")
        )
        self.build_button.setEnabled(
            bool(self.inventory) and bool(self.output_dir) and not running
        )
        self.cancel_button.setEnabled(running)
        self.reveal_button.setEnabled(self.output_dir.is_dir() and not running)
        self.games_tree.setEnabled(not running)
        self.compat_combo.setEnabled(not running)
        self.dlc_combo.setEnabled(not running)
        self.resume_check.setEnabled(not running)
        self.force_check.setEnabled(not running)
        self.keep_inner_check.setEnabled(not running)

    def _append_log(self, text: str) -> None:
        clean = text.rstrip()
        if not clean:
            return
        self.log_edit.appendPlainText(clean)
        scrollbar = self.log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def log_edit_clear(self) -> None:
        self.log_edit.clear()

    def _reveal_output(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_dir.resolve())))

    def _show_error(self, title: str, detail: str) -> None:
        QMessageBox.critical(self, title, detail)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            self._t("about_title", app=APP_NAME),
            (
                f"<b>{APP_NAME} {APP_VERSION}</b><br><br>"
                + self._t("about_body")
            ),
        )

    def closeEvent(self, event: Any) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            answer = QMessageBox.question(
                self,
                self._t("operation_running"),
                self._t("close_running"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._cancel()
        self._save_settings()
        event.accept()


def main(argv: list[str] | None = None) -> int:
    del argv
    root = application_data_root()
    resources = resource_root()
    ensure_application_directories(root)
    os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("ps4ffpsc")
    app.setOrganizationDomain("local.ps4ffpsc")
    app.setWindowIcon(QIcon())
    window = MainWindow(root, resources)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

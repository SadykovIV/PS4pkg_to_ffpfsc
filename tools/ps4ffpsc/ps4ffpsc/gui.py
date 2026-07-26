from __future__ import annotations

import json
import os
import tempfile
import sys
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
    game_block_reason,
    inventory_summary,
    package_version_text,
    source_cli_arguments,
    validate_source,
)
from .runtime import (
    application_data_root,
    ensure_application_directories,
    is_frozen,
    resource_root,
    worker_executable,
)


APP_NAME = "PS4 FFPFSC"
APP_VERSION = "0.2.1"
CREATE_NO_WINDOW = 0x08000000


def _hide_windows_worker_console(arguments: Any) -> None:
    arguments.flags |= CREATE_NO_WINDOW


class MainWindow(QMainWindow):
    def __init__(self, root: Path, resources: Path | None = None) -> None:
        super().__init__()
        self.root = root
        self.resources = resources or root
        self.settings = QSettings()
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
        self.operation: str | None = None
        self.build_queue: list[str] = []
        self.build_results: dict[str, Any] = {}
        self.cancel_requested = False

        self._build_ui()
        self._restore_settings()
        self._update_source_label()
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
        subtitle = QLabel(
            "Подготовка проверенных образов для ShadowMountPlus — локально и без изменения исходных PKG"
        )
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addWidget(mark)
        header.addLayout(title_box)
        header.addStretch()
        about = QPushButton("О программе")
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

        source_title = QLabel("1. Исходные пакеты")
        source_title.setObjectName("sectionTitle")
        source_layout.addWidget(source_title, 0, 0, 1, 4)
        self.source_label = QLabel()
        self.source_label.setObjectName("pathLabel")
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.source_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        source_layout.addWidget(self.source_label, 1, 0, 1, 4)

        choose_files = QPushButton("Выбрать PKG-файлы…")
        choose_files.clicked.connect(self._choose_files)
        choose_folder = QPushButton("Выбрать папку…")
        choose_folder.clicked.connect(self._choose_folder)
        clear_source = QPushButton("Очистить")
        clear_source.setObjectName("quietButton")
        clear_source.clicked.connect(self._clear_source)
        self.scan_button = QPushButton("Сканировать")
        self.scan_button.setObjectName("primaryButton")
        self.scan_button.clicked.connect(self._start_scan)
        source_layout.addWidget(choose_files, 2, 0)
        source_layout.addWidget(choose_folder, 2, 1)
        source_layout.addWidget(clear_source, 2, 2)
        source_layout.addWidget(self.scan_button, 2, 3)

        output_title = QLabel("2. Папки хранения")
        output_title.setObjectName("sectionTitle")
        source_layout.addWidget(output_title, 3, 0, 1, 4)
        source_layout.addWidget(QLabel("Готовые FFPFSC"), 4, 0, 1, 4)
        self.output_label = QLabel()
        self.output_label.setObjectName("pathLabel")
        self.output_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        source_layout.addWidget(self.output_label, 5, 0, 1, 3)
        output_button = QPushButton("Выбрать папку…")
        output_button.clicked.connect(self._choose_output)
        source_layout.addWidget(output_button, 5, 3)
        source_layout.addWidget(
            QLabel("Временные файлы (по умолчанию /tmp)"), 6, 0, 1, 4
        )
        self.temp_label = QLabel()
        self.temp_label.setObjectName("pathLabel")
        self.temp_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        source_layout.addWidget(self.temp_label, 7, 0, 1, 2)
        reset_temp = QPushButton("Сбросить /tmp")
        reset_temp.setObjectName("quietButton")
        reset_temp.clicked.connect(self._reset_temp)
        source_layout.addWidget(reset_temp, 7, 2)
        temp_button = QPushButton("Выбрать папку…")
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
        games_title = QLabel("3. Найденные игры")
        games_title.setObjectName("sectionTitle")
        self.summary_label = QLabel("Сначала выберите источник и запустите сканирование")
        self.summary_label.setObjectName("summary")
        games_header.addWidget(games_title)
        games_header.addStretch()
        games_header.addWidget(self.summary_label)
        games_layout.addLayout(games_header)

        self.games_tree = QTreeWidget()
        self.games_tree.setColumnCount(6)
        self.games_tree.setHeaderLabels(
            ["Собрать", "TITLE_ID / тип", "Название / файл", "Версия", "Patch", "DLC"]
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
        log_title = QLabel("Журнал")
        log_title.setObjectName("sectionTitle")
        clear_log = QPushButton("Очистить журнал")
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
        options.addWidget(QLabel("Совместимость:"), 0, 0)
        self.compat_combo = QComboBox()
        self.compat_combo.addItem("Текущий ShadowMountPlus", "current-smp")
        self.compat_combo.addItem("ShadowMountPlus с патчем", "patched-smp")
        self.compat_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        options.addWidget(self.compat_combo, 0, 1)
        options.addWidget(QLabel("DLC:"), 0, 2)
        self.dlc_combo = QComboBox()
        self.dlc_combo.addItem("Авто (подготовить, не встраивать)", "auto")
        self.dlc_combo.addItem("Отдельные образы (экспериментально)", "separate")
        self.dlc_combo.addItem("Не включать", "off")
        self.dlc_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        options.addWidget(self.dlc_combo, 0, 3)
        self.resume_check = QCheckBox("Продолжать прерванное")
        self.resume_check.setChecked(True)
        self.force_check = QCheckBox("Пересобрать существующее")
        self.keep_inner_check = QCheckBox("Сохранить внутренний exFAT")
        options.addWidget(self.resume_check, 1, 1)
        options.addWidget(self.force_check, 1, 2)
        options.addWidget(self.keep_inner_check, 1, 3)
        options.setColumnStretch(4, 1)
        page.addLayout(options)

        footer = QHBoxLayout()
        self.stage_label = QLabel("Готово")
        self.stage_label.setObjectName("stage")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(210)
        self.cancel_button = QPushButton("Отменить")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.clicked.connect(self._cancel)
        self.reveal_button = QPushButton("Открыть папку результата")
        self.reveal_button.clicked.connect(self._reveal_output)
        self.build_button = QPushButton("Собрать выбранные")
        self.build_button.setObjectName("primaryButton")
        self.build_button.clicked.connect(self._start_build)
        footer.addWidget(self.stage_label)
        footer.addWidget(self.progress)
        footer.addStretch()
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
            QLabel#stage { color: #aebbd0; }
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
            QProgressBar { background: #202936; border: none; border-radius: 4px; height: 8px; }
            QProgressBar::chunk { background: #536dfe; border-radius: 4px; }
            QSplitter::handle { background: transparent; height: 8px; }
            """
        )

    def _restore_settings(self) -> None:
        output = self.settings.value("output_dir", str(self.root / "output"), type=str)
        self.output_dir = Path(output).expanduser()
        temp = self.settings.value("temp_dir", tempfile.gettempdir(), type=str)
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
            "Выберите PS4 PKG",
            start,
            "PlayStation 4 PKG (*.pkg *.PKG);;Все файлы (*)",
        )
        if not names:
            return
        try:
            _, files, _ = validate_source("files", names, None)
        except (OSError, ValueError) as error:
            self._show_error("Не удалось выбрать PKG", str(error))
            return
        self.source_mode = "files"
        self.pkg_files = files
        self.source_folder = None
        self.inventory = None
        self.games_tree.clear()
        self._update_source_label()
        self._update_controls()

    def _choose_folder(self) -> None:
        start = str(self.source_folder or self.root / "pkg")
        name = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку с PKG (подпапки будут просканированы)",
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
        self._update_source_label()
        self._update_controls()
        self._save_settings()

    def _choose_output(self) -> None:
        name = QFileDialog.getExistingDirectory(
            self,
            "Куда сохранять FFPFSC",
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
            else Path(tempfile.gettempdir())
        )
        name = QFileDialog.getExistingDirectory(
            self,
            "Папка для временных файлов",
            start,
            QFileDialog.Option.ShowDirsOnly,
        )
        if not name:
            return
        self.temp_dir = Path(name).resolve()
        self._update_storage_labels()
        self._save_settings()

    def _reset_temp(self) -> None:
        self.temp_dir = Path(tempfile.gettempdir())
        self._update_storage_labels()
        self._save_settings()

    def _update_storage_labels(self) -> None:
        self.output_label.setText(str(self.output_dir))
        self.output_label.setToolTip(str(self.output_dir))
        detail = str(self.temp_dir)
        try:
            probe = self.temp_dir if self.temp_dir.exists() else self.temp_dir.parent
            free = os.statvfs(probe).f_bavail * os.statvfs(probe).f_frsize
            detail += f"  ·  свободно {free / 1024**3:.1f} GiB"
        except OSError:
            detail += "  ·  каталог будет создан при сборке"
        self.temp_label.setText(detail)
        self.temp_label.setToolTip(str(self.temp_dir))

    def _clear_source(self) -> None:
        self.pkg_files = ()
        self.source_folder = None
        self.inventory = None
        self.games_tree.clear()
        self.summary_label.setText("Источник не выбран")
        self._update_source_label()
        self._update_controls()

    def _update_source_label(self) -> None:
        if self.source_mode == "files" and self.pkg_files:
            preview = ", ".join(path.name for path in self.pkg_files[:3])
            if len(self.pkg_files) > 3:
                preview += f" … и ещё {len(self.pkg_files) - 3}"
            self.source_label.setText(f"{len(self.pkg_files)} PKG: {preview}")
            self.source_label.setToolTip("\n".join(str(path) for path in self.pkg_files))
        elif self.source_folder:
            self.source_label.setText(
                f"{self.source_folder}  ·  будут просмотрены все подпапки"
            )
            self.source_label.setToolTip(str(self.source_folder))
        else:
            self.source_label.setText("PKG-файлы или папка ещё не выбраны")
            self.source_label.setToolTip("")

    def _source_arguments(self) -> list[str]:
        return source_cli_arguments(
            self.source_mode, self.pkg_files, self.source_folder
        )

    def _base_arguments(self) -> list[str]:
        arguments = [
            "--output-dir",
            str(self.output_dir.resolve()),
            "--temp-dir",
            str(self.temp_dir),
            "--compat",
            str(self.compat_combo.currentData()),
            "--include-dlc",
            str(self.dlc_combo.currentData()),
            "--console-log",
            "--json",
        ]
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

    def _start_scan(self) -> None:
        try:
            self._source_arguments()
        except (OSError, ValueError) as error:
            self._show_error("Источник не выбран", str(error))
            return
        self.inventory = None
        self.games_tree.clear()
        self.summary_label.setText("Сканирование…")
        self._append_log("Сканирование PKG и чтение метаданных…")
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
                        blocked.append(f"{title_id} — {game_block_reason(game)}")
            detail = (
                "Нет игры, готовой к сборке.\n\n" + "\n".join(blocked)
                if blocked
                else "Отметьте хотя бы одну готовую к сборке игру."
            )
            self._show_error("Сборка пока невозможна", detail)
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=self.temp_dir,
                prefix="ps4ffpsc-gui-write-test-",
                delete=True,
            ):
                pass
            self._source_arguments()
        except OSError as error:
            self._show_error("Проверьте пути", str(error))
            return
        self.build_queue = selected
        self.build_results = {}
        self.cancel_requested = False
        self._append_log(
            f"Запущена сборка: {', '.join(selected)}. Исходные PKG не изменяются."
        )
        self._start_next_build()

    def _start_next_build(self) -> None:
        if self.cancel_requested or not self.build_queue:
            self._finish_build_batch()
            return
        title_id = self.build_queue.pop(0)
        self.stage_label.setText(f"Сборка {title_id}")
        self._append_log(f"──── {title_id}: извлечение → объединение → FFPFSC → проверка")
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
                self._show_error("Не найден рабочий модуль", str(program))
                return
            process_arguments = ["--worker", *arguments]
        else:
            program = self.resources / ".venv" / "bin" / "python"
            if not program.is_file():
                self._show_error(
                    "Окружение не готово",
                    "Не найден .venv. Один раз запустите scripts/bootstrap_macos.sh.",
                )
                return
            launcher = self.resources / "ps4ffpsc"
            if not launcher.is_file():
                self._show_error("Не найден CLI", str(launcher))
                return
            process_arguments = [str(launcher), *arguments]
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        environment.insert("PS4FFPSC_DATA_ROOT", str(self.root))
        environment.insert("PS4FFPSC_RESOURCE_ROOT", str(self.resources))
        self.process.setProcessEnvironment(environment)
        self.process.setWorkingDirectory(str(self.root))
        self.process.setProgram(str(program))
        self.process.setArguments(process_arguments)
        self.stdout_buffer = ""
        self.operation = operation
        self.cancel_requested = False
        self.progress.setRange(0, 0)
        self.stage_label.setText(
            "Сканирование…" if operation == "scan" else self.stage_label.text()
        )
        self._update_controls()
        self.process.start()
        if not self.process.waitForStarted(3000):
            self._show_error("Не удалось запустить процесс", self.process.errorString())
            self.operation = None
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self._update_controls()

    def _read_stdout(self) -> None:
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.stdout_buffer += data

    def _read_stderr(self) -> None:
        data = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            self._append_log(line)

    def _process_finished(
        self,
        exit_code: int,
        _status: QProcess.ExitStatus,
    ) -> None:
        operation = self.operation
        self._read_stdout()
        self._read_stderr()
        self.operation = None
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if exit_code == 0 else 0)

        payload: Any = None
        if self.stdout_buffer.strip():
            try:
                payload = json.loads(self.stdout_buffer)
            except json.JSONDecodeError:
                self._append_log(self.stdout_buffer.strip())

        if operation == "scan":
            if exit_code in (0, 3):
                self._finish_scan()
            else:
                self.stage_label.setText("Ошибка сканирования")
                self._show_error(
                    "Сканирование завершилось с ошибкой",
                    f"Код {exit_code}. Подробности находятся в журнале.",
                )
        elif operation and operation.startswith("build:"):
            title_id = operation.split(":", 1)[1]
            if exit_code == 0:
                self.build_results[title_id] = payload or {"status": "completed"}
                self._append_log(f"{title_id}: сборка и проверка успешно завершены.")
            else:
                error_text = build_error_text(payload, title_id, exit_code)
                self.build_results[title_id] = {
                    "status": "cancelled" if self.cancel_requested else "failed",
                    "exit_code": exit_code,
                    "error": error_text,
                }
                self._append_log(f"{title_id}: ошибка — {error_text}")
            self._start_next_build()
        self._update_controls()

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.Crashed and self.cancel_requested:
            self._append_log("Операция отменена пользователем; временные данные можно продолжить позже.")
            return
        self._append_log(f"Ошибка процесса: {self.process.errorString()}")

    def _finish_scan(self) -> None:
        inventory_path = self.root / "unpacked" / "package_inventory.json"
        try:
            self.inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            self._show_error("Не удалось прочитать инвентарь", str(error))
            return
        self._populate_inventory()
        summary = inventory_summary(self.inventory)
        self.stage_label.setText("Сканирование завершено")
        self._append_log(
            "Найдено: "
            f"PKG {summary['packages']}, игр {summary['games']}, "
            f"готово к сборке {summary['buildable']}, "
            f"неподдерживаемых {summary['unsupported']}."
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
                reason = game_block_reason(game)
                top.setToolTip(2, reason)
                top.setText(2, f"{top.text(2)}  —  {reason}")
            else:
                top.setToolTip(
                    2,
                    "Будут применены патчи: " + (", ".join(patches) if patches else "нет"),
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
                            f"Дубликат: {package['duplicate_of']}",
                        )
                    top.addChild(child)
            top.setExpanded(True)

        unsupported = self.inventory.get("unsupported", [])
        if unsupported:
            blocked = QTreeWidgetItem(
                ["", "UNSUPPORTED", f"Неподдерживаемые или зашифрованные PKG: {len(unsupported)}", "", "", ""]
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
        self.summary_label.setText(
            f"Игр: {summary['games']} · к сборке: {summary['buildable']} · "
            f"неподдерживаемых: {summary['unsupported']}"
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
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if succeeded else 0)
        if self.cancel_requested:
            self.stage_label.setText("Отменено")
        elif failed:
            self.stage_label.setText("Завершено с ошибками")
            details = "\n".join(
                f"{title_id}: {self.build_results[title_id].get('error', 'неизвестная ошибка')}"
                for title_id in failed
            )
            self._show_error(
                "Не все образы собраны",
                f"Успешно: {succeeded}.\n\n{details}",
            )
        else:
            self.stage_label.setText("Все выбранные образы готовы")
            QMessageBox.information(
                self,
                "Сборка завершена",
                f"Успешно собрано и проверено: {succeeded}.\n\n{self.output_dir}",
            )
        self.build_queue = []
        self._update_controls()

    def _cancel(self) -> None:
        if self.process.state() == QProcess.ProcessState.NotRunning:
            return
        self.cancel_requested = True
        self.build_queue = []
        self.stage_label.setText("Отмена…")
        self._append_log("Запрошена отмена. Процесс будет остановлен безопасно.")
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
            "Собрать выбранные" if has_checked else "Проверить готовность"
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
            f"О программе {APP_NAME}",
            (
                f"<b>{APP_NAME} {APP_VERSION}</b><br><br>"
                "GUI для локального конвейера PS4 PKG → FFPFSC. "
                "Поддерживаются только законно полученные PKG, которые может "
                "прочитать приложенный shadPS4 0.7.0. Исходные файлы не изменяются.<br><br>"
                "Готовый образ создаётся MkPFS и проходит автоматическую проверку."
            ),
        )

    def closeEvent(self, event: Any) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            answer = QMessageBox.question(
                self,
                "Операция выполняется",
                "Остановить текущую операцию и закрыть программу?",
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

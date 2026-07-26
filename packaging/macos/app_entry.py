from __future__ import annotations

import multiprocessing
import os
import sys


def main() -> int:
    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        from ps4ffpsc.cli import main as cli_main

        return cli_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--mkpfs":
        from mkpfs.__main__ import main as mkpfs_main

        return mkpfs_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--gui-smoke-test":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        from ps4ffpsc.gui import MainWindow
        from ps4ffpsc.runtime import (
            application_data_root,
            ensure_application_directories,
            resource_root,
        )

        app = QApplication([sys.argv[0]])
        app.setApplicationName("PS4 FFPFSC")
        app.setOrganizationName("ps4ffpsc-release-smoke")
        data_root = application_data_root()
        ensure_application_directories(data_root)
        window = MainWindow(data_root, resource_root())
        window.show()
        QTimer.singleShot(250, app.quit)
        result = app.exec()
        if sys.stdout is not None:
            print("gui_smoke_ok")
        return result
    from ps4ffpsc.gui import main as gui_main

    return gui_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

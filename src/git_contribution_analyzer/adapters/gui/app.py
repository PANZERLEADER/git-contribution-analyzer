from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from git_contribution_analyzer import __version__
from git_contribution_analyzer.adapters.gui.controller import GuiController


def qml_url() -> QUrl:
    resource = files("git_contribution_analyzer.gui.qml").joinpath("Main.qml")
    return QUrl.fromLocalFile(str(resource))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gca-gui", description="GCA desktop application")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--repository", type=Path, help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.version:
        print(__version__)
        return 0
    if arguments.smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        if os.name == "nt":
            windows_root = os.environ.get("WINDIR", "C:\\Windows")
            os.environ.setdefault("QT_QPA_FONTDIR", str(Path(windows_root) / "Fonts"))

    application = QGuiApplication(["gca-gui"])
    application.setApplicationName("GCA")
    application.setApplicationDisplayName("Git Contribution Analyzer")
    application.setOrganizationName("GCA")

    engine = QQmlApplicationEngine()
    controller = GuiController()
    application.aboutToQuit.connect(controller.shutdown)
    engine.rootContext().setContextProperty("gca", controller)
    engine.load(qml_url())
    if not engine.rootObjects():
        return 1
    if arguments.repository is not None:
        QTimer.singleShot(0, lambda: controller.openRepository(str(arguments.repository)))
    if arguments.smoke_test:
        QTimer.singleShot(1200 if arguments.repository is not None else 250, application.quit)
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())

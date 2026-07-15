from __future__ import annotations

import os

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from git_contribution_analyzer.adapters.gui.app import qml_url
from git_contribution_analyzer.adapters.gui.controller import GuiController


def test_qml_entrypoint_should_load_offscreen(monkeypatch: object) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    application = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlApplicationEngine()
    controller = GuiController()
    engine.rootContext().setContextProperty("gca", controller)

    url = qml_url()
    engine.load(url)
    application.processEvents()

    assert isinstance(url, QUrl)
    assert engine.rootObjects()

from __future__ import annotations

import os
import subprocess
import sys


def test_gui_module_should_load_and_exit_in_smoke_mode() -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["QT_QUICK_BACKEND"] = "software"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "git_contribution_analyzer.adapters.gui.app",
            "--smoke-test",
        ],
        env=environment,
        check=True,
        timeout=30,
    )

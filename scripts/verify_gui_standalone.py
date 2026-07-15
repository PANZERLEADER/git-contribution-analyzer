from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from git_contribution_analyzer.application.use_cases.init_project import init_project

ROOT = Path(__file__).parents[1]


def _executable() -> Path:
    if sys.platform == "darwin":
        return ROOT / "dist" / "gca-gui.app" / "Contents" / "MacOS" / "gca-gui"
    suffix = ".exe" if os.name == "nt" else ""
    return ROOT / "dist" / f"gca-gui{suffix}"


def _run(arguments: list[str], *, cwd: Path | None = None) -> None:
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["QT_QUICK_BACKEND"] = "software"
    if os.name == "nt":
        windows_root = environment.get("WINDIR", "C:\\Windows")
        environment["QT_QPA_FONTDIR"] = str(Path(windows_root) / "Fonts")
    subprocess.run(arguments, cwd=cwd, env=environment, check=True, timeout=30)


def main() -> None:
    executable = _executable()
    if not executable.is_file():
        raise SystemExit(f"GUI standalone executable not found: {executable}")
    _run([str(executable), "--version"])

    with tempfile.TemporaryDirectory(prefix="gca-gui-standalone-") as temporary:
        repository = Path(temporary) / "GUI 验证 repository"
        subprocess.run(
            ["git", "init", "-b", "main", str(repository)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "config", "user.name", "Release Test"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "config", "user.email", "release@example.com"],
            check=True,
        )
        (repository / "README.md").write_text("# GUI standalone\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repository), "add", "README.md"], check=True)
        subprocess.run(
            ["git", "-C", str(repository), "commit", "-m", "test: initialize GUI smoke"],
            check=True,
            capture_output=True,
            text=True,
        )
        init_project(repository)
        _run(
            [
                str(executable),
                "--smoke-test",
                "--repository",
                str(repository),
            ]
        )


if __name__ == "__main__":
    main()

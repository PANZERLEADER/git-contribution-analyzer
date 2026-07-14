from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _run(arguments: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(arguments, cwd=cwd, check=True)


def main() -> None:
    suffix = ".exe" if os.name == "nt" else ""
    executable = ROOT / "dist" / f"gca{suffix}"
    if not executable.is_file():
        raise SystemExit(f"Standalone executable not found: {executable}")
    _run([str(executable), "--help"])
    _run([str(executable), "--version"])

    with tempfile.TemporaryDirectory(prefix="gca-standalone-") as temporary:
        repository = Path(temporary) / "验证 standalone repository"
        _run(["git", "init", "-b", "main", str(repository)])
        _run(["git", "config", "user.name", "Release Test"], cwd=repository)
        _run(["git", "config", "user.email", "release@example.com"], cwd=repository)
        (repository / "README.md").write_text("# Standalone test\n", encoding="utf-8")
        _run(["git", "add", "README.md"], cwd=repository)
        _run(["git", "commit", "-m", "chore: initialize standalone test"], cwd=repository)
        _run([str(executable), "init", str(repository)])
        _run([str(executable), "status", str(repository), "--json"])
        _run([str(executable), "doctor", str(repository), "--json"])
        _run([str(executable), "uninit", str(repository), "--yes"])


if __name__ == "__main__":
    main()

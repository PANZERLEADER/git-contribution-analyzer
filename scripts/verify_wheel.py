from __future__ import annotations

import os
import subprocess
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _run(arguments: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(arguments, cwd=cwd, check=True)


def _venv_executable(root: Path, name: str) -> Path:
    directory = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" and name != "python" else ""
    return root / directory / f"{name}{suffix}"


def main() -> None:
    wheels = sorted((ROOT / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"Expected exactly one wheel in dist, found {len(wheels)}")

    with tempfile.TemporaryDirectory(prefix="gca-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "isolated environment"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_executable(environment, "python")
        gca = _venv_executable(environment, "gca")
        _run([str(python), "-m", "pip", "install", "--disable-pip-version-check", str(wheels[0])])
        _run([str(gca), "--help"])
        _run([str(gca), "--version"])

        repository = root / "验证 repository with spaces"
        _run(["git", "init", "-b", "main", str(repository)])
        _run(["git", "config", "user.name", "Release Test"], cwd=repository)
        _run(["git", "config", "user.email", "release@example.com"], cwd=repository)
        (repository / "README.md").write_text("# Release test\n", encoding="utf-8")
        _run(["git", "add", "README.md"], cwd=repository)
        _run(["git", "commit", "-m", "chore: initialize release test"], cwd=repository)
        _run([str(gca), "init", str(repository)])
        _run([str(gca), "status", str(repository), "--json"])
        _run([str(gca), "doctor", str(repository), "--json"])
        _run([str(gca), "uninit", str(repository), "--yes"])


if __name__ == "__main__":
    main()

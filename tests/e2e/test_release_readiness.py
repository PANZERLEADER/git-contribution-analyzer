from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_should_ship_required_release_documentation() -> None:
    required_documents = (
        "doc/architecture/architecture.md",
        "doc/architecture/data-model.md",
        "doc/cli/cli-reference.md",
        "doc/guides/installation.md",
        "doc/guides/methodology.md",
        "doc/guides/privacy.md",
        "doc/testing/golden-dataset.md",
        "doc/releases/0.1.0.md",
        "doc/releases/0.2.0.md",
        "doc/releases/0.3.0.md",
        "doc/releases/0.4.0.md",
        "doc/zh-CN/release-0.4.0.md",
        "THIRD_PARTY_NOTICES.md",
    )

    missing = [path for path in required_documents if not (ROOT / path).is_file()]

    assert missing == []


def test_should_enforce_cross_platform_build_and_install_gates() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "windows-latest" in workflow
    assert "ubuntu-latest" in workflow
    assert "macos-latest" in workflow
    assert "python -m build" in workflow
    assert "python -m coverage report" in workflow
    assert "--include=" in workflow
    assert '--exclude "adapters/gui"' in workflow
    assert "--cov-fail-under=0" in workflow
    assert (
        '--omit="src/git_contribution_analyzer/adapters/gui/*,'
        'src/git_contribution_analyzer/application/facades/*"'
        in workflow
    )
    assert "python scripts/verify_wheel.py" in workflow
    assert "gui:" in workflow
    assert 'python -m pip install -e ".[dev,gui]"' in workflow
    assert "libegl1" in workflow
    assert "tests/e2e/test_gui_smoke.py" in workflow
    assert "gitleaks" in workflow.casefold()
    assert "git --redact --verbose" in workflow


def test_should_define_standalone_release_workflow() -> None:
    release_workflow = ROOT / ".github/workflows/release.yml"
    assert release_workflow.is_file()
    workflow = release_workflow.read_text(encoding="utf-8")

    assert "windows-latest" in workflow
    assert "ubuntu-latest" in workflow
    assert "macos-latest" in workflow
    assert "pyinstaller" in workflow.casefold()
    assert "pipx" in workflow.casefold()
    assert "upload-artifact" in workflow
    assert "gca-windows-x86_64.exe" in workflow
    assert "gca-linux-x86_64" in workflow
    assert "gca-macos-x86_64" in workflow
    assert "gca-packages" in workflow
    assert "SHA256SUMS.txt" in workflow
    assert "gh release create" in workflow
    assert 'VERSION="${GITHUB_REF_NAME#v}"' in workflow
    assert 'ENGLISH_NOTES="doc/releases/${VERSION}.md"' in workflow
    assert 'CHINESE_NOTES="doc/zh-CN/release-${VERSION}.md"' in workflow
    assert 'cat "$ENGLISH_NOTES"' in workflow
    assert 'cat "$CHINESE_NOTES"' in workflow
    assert '--notes-file "$COMBINED_NOTES"' in workflow
    assert "--notes-file doc/releases/0.1.0.md" not in workflow
    assert (ROOT / "gca.spec").is_file()
    assert (ROOT / "gca-gui.spec").is_file()
    assert "gca-gui-windows-x86_64.exe" in workflow
    assert "gca-gui-linux-x86_64" in workflow
    assert "gca-gui-macos-x86_64.app.zip" in workflow
    assert "python scripts/verify_gui_standalone.py" in workflow
    assert "libegl1" in workflow


def test_should_record_current_release_in_changelog() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## 0.2.0 - 2026-07-15" in changelog
    assert "## 0.3.0 - 2026-07-15" in changelog
    assert "## 0.4.0 - 2026-07-15" in changelog


def test_should_not_publish_real_identity_or_machine_paths_in_documentation() -> None:
    documents = [
        ROOT / "README.md",
        ROOT / "README.zh-CN.md",
        ROOT / "CHANGELOG.md",
        ROOT / "SECURITY.md",
        *(ROOT / "doc").rglob("*.md"),
    ]
    email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    machine_path_pattern = re.compile(r"\b[A-Za-z]:\\(?:Users|CodeWorkspace)\\", re.IGNORECASE)

    private_emails: list[tuple[Path, str]] = []
    private_paths: list[Path] = []
    for document in documents:
        content = document.read_text(encoding="utf-8")
        private_emails.extend(
            (document.relative_to(ROOT), email)
            for email in email_pattern.findall(content)
            if not email.casefold().endswith("@example.com")
        )
        if machine_path_pattern.search(content):
            private_paths.append(document.relative_to(ROOT))

    assert private_emails == []
    assert private_paths == []

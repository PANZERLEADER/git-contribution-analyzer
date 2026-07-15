from __future__ import annotations

from pathlib import Path

import pytest

from git_contribution_analyzer.application.ports.cancellation import (
    CancellationSource,
    OperationCancelled,
)
from git_contribution_analyzer.application.ports.progress import ProgressEvent
from git_contribution_analyzer.application.use_cases.index_repository import index_repository
from git_contribution_analyzer.application.use_cases.init_project import init_project
from tests.helpers.git_repo_builder import GitRepoBuilder


class RecordingReporter:
    def __init__(self) -> None:
        self.events: list[ProgressEvent] = []

    def report(self, event: ProgressEvent) -> None:
        self.events.append(event)


def test_index_should_report_stable_progress_stages(tmp_path: Path) -> None:
    repository = tmp_path / "progress repository"
    builder = GitRepoBuilder.create(repository)
    builder.commit_text("README.md", "# Progress\n", "docs: add readme")
    init_project(repository)
    reporter = RecordingReporter()

    result = index_repository(
        repository,
        full_rebuild=False,
        progress=reporter,
    )

    assert result["indexedCommits"] == 1
    assert [event.stage for event in reporter.events] == [
        "reading_commits",
        "resolving_delivery",
        "writing_index",
        "completed",
    ]


def test_index_should_honor_cancellation_before_discovery(tmp_path: Path) -> None:
    source = CancellationSource()
    source.cancel()

    with pytest.raises(OperationCancelled):
        index_repository(
            tmp_path / "does-not-need-to-exist",
            full_rebuild=False,
            cancellation=source.token,
        )

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta

from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
)

ISSUE_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b|(?<!\w)(#\d+)\b")
SCOPE_PATTERN = re.compile(r"^[a-zA-Z]+\(([^)]+)\)!?:")
CLUSTER_WINDOW = timedelta(days=14)


@dataclass(slots=True)
class _Cluster:
    key: str
    signal: str
    confidence: str
    commits: list[ContributionCommit] = field(default_factory=list)


def cluster_contributions(
    commits: tuple[ContributionCommit, ...],
) -> tuple[ContributionItem, ...]:
    clusters: list[_Cluster] = []
    for commit in sorted(commits, key=lambda value: (value.authored_at, value.hash)):
        issue = _issue_key(commit.subject)
        scope = _scope(commit.subject)
        if issue:
            cluster = next((value for value in clusters if value.signal == f"issue:{issue}"), None)
            if cluster is None:
                cluster = _Cluster(f"issue:{issue}", f"issue:{issue}", "HIGH")
                clusters.append(cluster)
        else:
            module = commit.modules[0] if commit.modules else "root"
            signal = f"scope:{scope}" if scope else f"module:{module}:{commit.commit_type}"
            cluster = _recent_cluster(clusters, signal, commit)
            if cluster is None:
                sequence = 1 + sum(value.signal == signal for value in clusters)
                cluster = _Cluster(
                    key=f"{signal}:{sequence}",
                    signal=signal,
                    confidence="MEDIUM" if scope else "LOW",
                )
                clusters.append(cluster)
        cluster.commits.append(commit)

    items: list[ContributionItem] = []
    for index, cluster in enumerate(clusters, start=1):
        commits_in_cluster = tuple(cluster.commits)
        items.append(
            ContributionItem(
                id=f"CI-{index:03d}",
                group_key=cluster.key,
                title=_title(cluster, commits_in_cluster[0].subject),
                confidence=cluster.confidence,
                commits=commits_in_cluster,
                evidence_ids=(f"EV-{index:03d}",),
            )
        )
    return tuple(items)


def _recent_cluster(
    clusters: list[_Cluster],
    signal: str,
    commit: ContributionCommit,
) -> _Cluster | None:
    return next(
        (
            cluster
            for cluster in reversed(clusters)
            if cluster.signal == signal
            and commit.authored_at - cluster.commits[-1].authored_at <= CLUSTER_WINDOW
        ),
        None,
    )


def _issue_key(subject: str) -> str | None:
    match = ISSUE_PATTERN.search(subject)
    return next((group for group in match.groups() if group), None) if match else None


def _scope(subject: str) -> str | None:
    match = SCOPE_PATTERN.match(subject.strip())
    return match.group(1).casefold() if match else None


def _title(cluster: _Cluster, subject: str) -> str:
    if cluster.signal.startswith("issue:"):
        return f"{cluster.signal.removeprefix('issue:')}: {subject}"
    if cluster.signal.startswith("scope:"):
        return f"{cluster.signal.removeprefix('scope:')}: {subject}"
    return subject

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from git_contribution_analyzer.domain.models.contribution import ContributionCommit
from git_contribution_analyzer.domain.services.capability_rules import assess_capabilities
from git_contribution_analyzer.domain.services.contribution_clustering import (
    cluster_contributions,
)
from git_contribution_analyzer.domain.services.contribution_rules import (
    build_evidence,
    classify_commit,
    module_from_path,
)


def _fact(
    commit_hash: str,
    subject: str,
    *,
    day: int,
    paths: tuple[str, ...],
    delivery: str = "LANDED",
) -> ContributionCommit:
    return ContributionCommit(
        hash=commit_hash,
        subject=subject,
        authored_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day),
        commit_type=classify_commit(subject),
        delivery_status=delivery,
        paths=paths,
        modules=tuple(sorted({module_from_path(path) for path in paths})),
        insertions=20,
        deletions=5,
        files_changed=len(paths),
        merge=False,
        binary_files=0,
        generated_files=0,
    )


def test_should_classify_conventional_and_fallback_commits() -> None:
    assert classify_commit("feat(api): add user endpoint") == "FEATURE"
    assert classify_commit("fix: prevent duplicate writes") == "FIX"
    assert classify_commit("Revert \"feat: unsafe change\"") == "REVERT"
    assert classify_commit("Update account behavior") == "OTHER"
    assert module_from_path("simi-api/src/main/App.java") == "simi-api"
    assert module_from_path("README.md") == "root"


def test_should_cluster_by_issue_then_scope_and_keep_low_confidence_items_separate() -> None:
    facts = (
        _fact("a" * 40, "feat(api): add endpoint PROJ-42", day=0, paths=("api/a.py",)),
        _fact("b" * 40, "test(api): cover PROJ-42", day=1, paths=("tests/test_a.py",)),
        _fact("c" * 40, "fix(cache): handle expiry", day=2, paths=("cache/store.py",)),
        _fact("d" * 40, "test(cache): cover expiry", day=3, paths=("cache/test.py",)),
        _fact("e" * 40, "update docs", day=4, paths=("docs/a.md",)),
        _fact("f" * 40, "update docs again", day=40, paths=("docs/b.md",)),
    )

    items = cluster_contributions(facts)

    assert len(items) == 4
    issue_item = next(item for item in items if item.group_key == "issue:PROJ-42")
    scope_item = next(item for item in items if item.group_key.startswith("scope:cache:"))
    assert issue_item.confidence == "HIGH"
    assert {commit.hash for commit in issue_item.commits} == {"a" * 40, "b" * 40}
    assert scope_item.confidence == "MEDIUM"
    assert {commit.hash for commit in scope_item.commits} == {"c" * 40, "d" * 40}
    assert sum(item.confidence == "LOW" for item in items) == 2


def test_should_generate_evidence_and_only_claim_supported_capabilities() -> None:
    facts = (
        _fact(
            "a" * 40,
            "feat(api): add endpoint PROJ-7",
            day=0,
            paths=("api/UserController.java", "service/UserService.java"),
        ),
        _fact(
            "b" * 40,
            "test(api): cover endpoint PROJ-7",
            day=1,
            paths=("tests/UserControllerTest.java", "db/V003__user.sql"),
        ),
    )
    items = cluster_contributions(facts)

    evidence = build_evidence(items)
    assessments = assess_capabilities(items, evidence)

    assert len(evidence) == len(items)
    assert all(item.evidence_ids for item in items)
    evidence_ids = {entry.id for entry in evidence}
    assert {evidence_id for item in items for evidence_id in item.evidence_ids} <= evidence_ids
    capabilities = {assessment.capability for assessment in assessments}
    assert capabilities >= {"API_DESIGN", "TESTING", "DATABASE"}
    assert "PERFORMANCE" not in capabilities
    assert all(set(assessment.evidence_ids) <= evidence_ids for assessment in assessments)

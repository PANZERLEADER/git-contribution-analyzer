from __future__ import annotations

from datetime import UTC, datetime

from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
)
from git_contribution_analyzer.domain.models.structural_baseline import StructuralRuleConfig
from git_contribution_analyzer.domain.services.structural_baseline import (
    build_structural_baseline,
    match_work_item_structural_context,
)


def _commit(commit_hash: str, day: int, paths: tuple[str, ...]) -> ContributionCommit:
    return ContributionCommit(
        hash=commit_hash,
        subject=f"feat: {commit_hash}",
        authored_at=datetime(2026, 2, day, tzinfo=UTC),
        commit_type="FEATURE",
        delivery_status="LANDED",
        paths=paths,
        modules=tuple(sorted({path.split("/", maxsplit=1)[0] for path in paths})),
        insertions=10,
        deletions=2,
        files_changed=len(paths),
        merge=False,
        binary_files=0,
        generated_files=0,
    )


def test_should_match_item_to_hotspot_and_coupled_edge() -> None:
    baseline = build_structural_baseline(
        (
            _commit("a", 1, ("api/a.py", "db/b.py")),
            _commit("b", 2, ("api/a.py", "db/b.py")),
            _commit("c", 3, ("api/a.py", "db/b.py")),
        ),
        cutoff=datetime(2026, 2, 4, tzinfo=UTC),
        config=StructuralRuleConfig(
            minimum_baseline_commits=2,
            hotspot_percentile=0.5,
            minimum_co_change_count=2,
            minimum_subset_ratio=0.75,
            minimum_jaccard=0.2,
        ),
    )
    item = ContributionItem(
        id="CI-001",
        group_key="feature:test",
        title="Test",
        confidence="HIGH",
        commits=(_commit("current", 5, ("api/a.py", "db/b.py")),),
        evidence_ids=("EV-001",),
    )

    context = match_work_item_structural_context(item, baseline.materialization)

    assert context.baseline_id == baseline.id
    assert {entry.path for entry in context.hotspot_exposures} == {"api/a.py", "db/b.py"}
    assert len(context.coupling_exposures) == 1
    assert context.coupling_exposures[0].cross_module is True
    assert context.confidence == "MEDIUM"


def test_should_return_gap_when_baseline_sample_is_insufficient() -> None:
    baseline = build_structural_baseline(
        (_commit("a", 1, ("src/a.py",)),),
        cutoff=datetime(2026, 2, 2, tzinfo=UTC),
        config=StructuralRuleConfig(minimum_baseline_commits=10),
    )
    item = ContributionItem(
        id="CI-001",
        group_key="feature:test",
        title="Test",
        confidence="HIGH",
        commits=(_commit("current", 3, ("src/a.py",)),),
        evidence_ids=("EV-001",),
    )

    context = match_work_item_structural_context(item, baseline.materialization)

    assert context.hotspot_exposures == ()
    assert context.coupling_exposures == ()
    assert "INSUFFICIENT_STRUCTURAL_BASELINE" in context.gaps

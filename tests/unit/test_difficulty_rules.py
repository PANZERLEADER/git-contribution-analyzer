from __future__ import annotations

from datetime import UTC, datetime

from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
)
from git_contribution_analyzer.domain.models.work_assessment import DifficultyLevel
from git_contribution_analyzer.domain.services.difficulty_rules import assess_difficulty


def _item(
    paths: tuple[str, ...],
    *,
    subject: str = "feat: implement change",
    insertions: int = 20,
) -> ContributionItem:
    commit = ContributionCommit(
        hash="abc",
        subject=subject,
        authored_at=datetime(2026, 1, 1, tzinfo=UTC),
        commit_type="FEATURE",
        delivery_status="LANDED",
        paths=paths,
        modules=tuple(sorted({path.split("/", 1)[0] for path in paths})),
        insertions=insertions,
        deletions=2,
        files_changed=len(paths),
        merge=False,
        binary_files=0,
        generated_files=0,
    )
    return ContributionItem(
        id="CI-001",
        group_key="test",
        title=subject,
        confidence="HIGH",
        commits=(commit,),
        evidence_ids=("EV-001",),
    )


def test_should_mark_small_database_migration_as_high_risk() -> None:
    result = assess_difficulty(
        _item(("db/migrations/V005__alter_wallet_balance.sql",), insertions=4)
    )

    assert result.level is DifficultyLevel.HIGH_RISK
    assert any(signal.dimension == "DATA_RISK" for signal in result.dimension_signals)


def test_should_not_raise_difficulty_for_large_docs_only_change() -> None:
    result = assess_difficulty(
        _item(("docs/guide.md", "README.md"), subject="docs: rewrite guide", insertions=5000)
    )

    assert result.level is DifficultyLevel.ROUTINE


def test_should_mark_cross_module_data_compatibility_change_as_complex() -> None:
    result = assess_difficulty(
        _item(
            (
                "api/schema/user-v2.json",
                "service/user.py",
                "repository/user_repository.py",
            ),
            subject="feat!: migrate user schema with backward compatibility",
        )
    )

    assert result.level is DifficultyLevel.COMPLEX


def test_should_mark_single_domain_api_logic_as_standard() -> None:
    result = assess_difficulty(_item(("api/user_controller.py", "api/user_service.py")))

    assert result.level is DifficultyLevel.STANDARD
    assert "STRUCTURAL_ANALYZER_UNAVAILABLE" in result.gaps

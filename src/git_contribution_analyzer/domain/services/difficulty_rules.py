from __future__ import annotations

from pathlib import PurePosixPath

from git_contribution_analyzer.domain.models.contribution import ContributionItem
from git_contribution_analyzer.domain.models.work_assessment import (
    DifficultyAssessment,
    DifficultyLevel,
    DimensionSignal,
)

DIFFICULTY_RULE_VERSION = "difficulty-rules-v1"


def assess_difficulty(item: ContributionItem) -> DifficultyAssessment:
    paths = tuple(sorted({path.replace("\\", "/").casefold() for path in item.paths}))
    subject = " ".join(commit.subject.casefold() for commit in item.commits)
    evidence_ids = item.evidence_ids
    if paths and all(_is_documentation(path) for path in paths):
        return DifficultyAssessment(
            level=DifficultyLevel.ROUTINE,
            dimension_signals=(
                _signal(
                    "DELIVERY_BURDEN",
                    "DOCUMENTATION_ONLY",
                    "LOW",
                    "The item changes documentation only.",
                    evidence_ids,
                ),
            ),
            rule_version=DIFFICULTY_RULE_VERSION,
            evidence_ids=evidence_ids,
            confidence="HIGH",
            gaps=(),
        )

    signals: list[DimensionSignal] = []
    modules = {path.split("/", maxsplit=1)[0] for path in paths}
    migration = any(
        path.endswith(".sql") and any(part in path for part in ("migration", "migrations", "db/"))
        for path in paths
    )
    critical = any(
        token in path
        for path in paths
        for token in ("wallet", "payment", "billing", "security", "auth", "permission")
    )
    distributed = any(
        token in f"{subject} {' '.join(paths)}"
        for token in ("redis", "message queue", "mq", "lock", "idempot", "concurr", "retry")
    )
    compatibility = any(
        token in f"{subject} {' '.join(paths)}"
        for token in ("backward", "compatib", "schema", "breaking", "public api", "api-v2")
    )
    code_change = any(not _is_documentation(path) and not path.endswith(".yml") for path in paths)

    if len(modules) > 1:
        signals.append(
            _signal(
                "IMPACT_SCOPE",
                "MULTI_MODULE",
                "SUBSTANTIAL",
                f"The item spans {len(modules)} modules.",
                evidence_ids,
            )
        )
    if migration:
        signals.append(
            _signal(
                "DATA_RISK",
                "DATABASE_MIGRATION",
                "CRITICAL",
                "The item changes a database migration contract.",
                evidence_ids,
            )
        )
    elif any(token in subject for token in ("transaction", "multi-table", "data repair")):
        signals.append(
            _signal(
                "DATA_RISK",
                "TRANSACTIONAL_CHANGE",
                "SUBSTANTIAL",
                "The item contains transactional or data repair signals.",
                evidence_ids,
            )
        )
    if distributed:
        signals.append(
            _signal(
                "DISTRIBUTED_RISK",
                "CONSISTENCY_OR_CONCURRENCY",
                "CRITICAL",
                "The item changes concurrency or distributed consistency behavior.",
                evidence_ids,
            )
        )
    if critical:
        signals.append(
            _signal(
                "BUSINESS_CRITICALITY",
                "CRITICAL_DOMAIN",
                "CRITICAL",
                "The item touches a configured critical business or security domain.",
                evidence_ids,
            )
        )
    if compatibility:
        signals.append(
            _signal(
                "COMPATIBILITY",
                "CONTRACT_COMPATIBILITY",
                "SUBSTANTIAL",
                "The item contains public contract or compatibility signals.",
                evidence_ids,
            )
        )
    if any(_is_test(path) for path in paths):
        signals.append(
            _signal(
                "DELIVERY_BURDEN",
                "TEST_COVERAGE",
                "SUPPORTING",
                "The item includes test changes.",
                evidence_ids,
            )
        )
    if code_change and not signals:
        signals.append(
            _signal(
                "STRUCTURE_COMPLEXITY",
                "LOGIC_OR_API_CHANGE",
                "STANDARD",
                "The item changes application logic or an API surface.",
                evidence_ids,
            )
        )

    if any(signal.severity == "CRITICAL" for signal in signals):
        level = DifficultyLevel.HIGH_RISK
    else:
        substantial = sum(signal.severity == "SUBSTANTIAL" for signal in signals)
        level = (
            DifficultyLevel.COMPLEX
            if substantial >= 2
            else DifficultyLevel.STANDARD
            if code_change
            else DifficultyLevel.ROUTINE
        )
    gaps = ("STRUCTURAL_ANALYZER_UNAVAILABLE",) if code_change else ()
    confidence = (
        "HIGH"
        if level in (DifficultyLevel.ROUTINE, DifficultyLevel.HIGH_RISK)
        else "MEDIUM"
    )
    return DifficultyAssessment(
        level=level,
        dimension_signals=tuple(signals),
        rule_version=DIFFICULTY_RULE_VERSION,
        evidence_ids=evidence_ids,
        confidence=confidence,
        gaps=gaps,
    )


def _is_documentation(path: str) -> bool:
    normalized = PurePosixPath(path)
    return "docs" in normalized.parts or normalized.name.casefold() == "readme.md" or path.endswith(
        (".md", ".rst", ".txt")
    )


def _is_test(path: str) -> bool:
    normalized = PurePosixPath(path)
    return "tests" in normalized.parts or normalized.name.startswith("test_")


def _signal(
    dimension: str,
    code: str,
    severity: str,
    description: str,
    evidence_ids: tuple[str, ...],
) -> DimensionSignal:
    return DimensionSignal(
        dimension=dimension,
        code=code,
        severity=severity,
        description=description,
        evidence_ids=evidence_ids,
    )

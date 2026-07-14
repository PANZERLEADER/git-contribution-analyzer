from __future__ import annotations

from collections.abc import Callable

from git_contribution_analyzer.domain.models.assessment import CapabilityAssessment
from git_contribution_analyzer.domain.models.contribution import ContributionItem, Evidence

PathRule = Callable[[str], bool]


def assess_capabilities(
    items: tuple[ContributionItem, ...],
    evidence: tuple[Evidence, ...],
) -> tuple[CapabilityAssessment, ...]:
    evidence_ids = {entry.id for entry in evidence}
    rules: tuple[tuple[str, PathRule, str], ...] = (
        ("API_DESIGN", _is_api, "API or controller changes are present"),
        ("TESTING", _is_test, "Automated test changes are present"),
        ("DATABASE", _is_database, "Database or persistence changes are present"),
        ("PERFORMANCE", _is_performance, "Performance or caching changes are present"),
        ("DELIVERY", _is_delivery, "Build or delivery configuration changes are present"),
        ("DOCUMENTATION", _is_documentation, "Documentation changes are present"),
    )
    assessments: list[CapabilityAssessment] = []
    for capability, rule, rationale in rules:
        supporting = tuple(
            item
            for item in items
            if any(rule(path.casefold().replace("\\", "/")) for path in item.paths)
        )
        if supporting:
            assessments.append(_assessment(capability, rationale, supporting, evidence_ids))
    cross_module = tuple(item for item in items if len(item.modules) >= 3)
    if cross_module:
        assessments.append(
            _assessment(
                "CROSS_MODULE",
                "Changes span at least three top-level modules",
                cross_module,
                evidence_ids,
            )
        )
    return tuple(assessments)


def _assessment(
    capability: str,
    rationale: str,
    items: tuple[ContributionItem, ...],
    evidence_ids: set[str],
) -> CapabilityAssessment:
    supporting_ids = tuple(
        evidence_id
        for item in items
        for evidence_id in item.evidence_ids
        if evidence_id in evidence_ids
    )
    commit_count = sum(len(item.commits) for item in items)
    return CapabilityAssessment(
        capability=capability,
        confidence="HIGH" if commit_count >= 3 else "MEDIUM",
        rationale=rationale,
        evidence_ids=tuple(dict.fromkeys(supporting_ids)),
        gaps=("Git evidence does not prove business outcome or sole ownership",),
    )


def _is_api(path: str) -> bool:
    return "controller" in path or path.startswith("api/") or "/api/" in path


def _is_test(path: str) -> bool:
    return path.startswith("test") or "/test" in path or path.endswith("_test.py")


def _is_database(path: str) -> bool:
    return path.endswith(".sql") or any(
        token in path for token in ("migration", "mapper", "repository")
    )


def _is_performance(path: str) -> bool:
    return any(token in path for token in ("cache", "redis", "benchmark", "concurrent"))


def _is_delivery(path: str) -> bool:
    return any(token in path for token in (".github/", "docker", "k8s", "terraform", "ci/"))


def _is_documentation(path: str) -> bool:
    return path.startswith("doc") or path.endswith((".md", ".rst"))

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from git_contribution_analyzer.domain.models.assessment import CapabilityAssessment
from git_contribution_analyzer.domain.models.contribution import (
    ContributionCommit,
    ContributionItem,
)


def build_dimensional_summaries(
    commits: tuple[ContributionCommit, ...],
    items: tuple[ContributionItem, ...],
    capabilities: tuple[CapabilityAssessment, ...],
) -> tuple[dict[str, Any], dict[str, Any]]:
    non_merge = tuple(commit for commit in commits if not commit.merge)
    module_counts = Counter(module for commit in non_merge for module in commit.modules)
    type_counts = Counter(commit.commit_type for commit in non_merge)
    dominant_modules = _ranked_counts(module_counts, "name")[:10]
    change_profile = _ranked_counts(type_counts, "type")

    module_evidence: defaultdict[str, set[str]] = defaultdict(set)
    for item in items:
        for module in item.modules:
            module_evidence[module].update(item.evidence_ids)
    technical_highlights = [
        {
            "text": f"{entry['name']} is a dominant technical module with "
            f"{entry['commits']} commits.",
            "evidenceIds": sorted(module_evidence[entry["name"]])[:20],
        }
        for entry in dominant_modules[:5]
        if module_evidence[entry["name"]]
    ]
    technical = {
        "headline": (
            f"{len(commits)} commits across {len(module_counts)} technical modules; "
            f"{len(capabilities)} rule-based capabilities detected."
        ),
        "dominantModules": dominant_modules,
        "changeProfile": change_profile,
        "capabilities": [
            {
                "capability": capability.capability,
                "confidence": capability.confidence,
                "evidenceIds": list(capability.evidence_ids),
                "gaps": list(capability.gaps),
            }
            for capability in capabilities
        ],
        "highlights": technical_highlights,
    }

    domain_items: defaultdict[str, list[ContributionItem]] = defaultdict(list)
    for item in items:
        domain_items[_business_domain(item)].append(item)
    domains: list[dict[str, Any]] = []
    for name, domain_contributions in domain_items.items():
        domain_commits = tuple(
            commit for item in domain_contributions for commit in item.commits
        )
        domains.append(
            {
                "name": name,
                "contributionItems": len(domain_contributions),
                "commits": len(domain_commits),
                "landedCommits": sum(
                    commit.delivery_status != "AUTHORED_ONLY" for commit in domain_commits
                ),
                "evidenceIds": sorted(
                    {
                        evidence_id
                        for item in domain_contributions
                        for evidence_id in item.evidence_ids
                    }
                ),
            }
        )
    domains.sort(key=lambda value: (-value["commits"], value["name"]))
    business_highlights = [
        {
            "text": f"{domain['name']} contains {domain['contributionItems']} contribution "
            f"items and {domain['landedCommits']} landed commits.",
            "evidenceIds": domain["evidenceIds"][:20],
        }
        for domain in domains[:10]
        if domain["evidenceIds"]
    ]
    business = {
        "headline": (
            f"{len(items)} contribution clusters across {len(domains)} deterministic "
            "business domains."
        ),
        "domains": domains[:20],
        "highlights": business_highlights,
        "limitations": [
            "Business domains are inferred from commit scopes and clustering keys.",
            "Git evidence does not prove revenue, customer impact, or business ownership.",
        ],
    }
    return technical, business


def _ranked_counts(counts: Counter[str], label: str) -> list[dict[str, Any]]:
    return [
        {label: name, "commits": count}
        for name, count in sorted(counts.items(), key=lambda value: (-value[1], value[0]))
    ]


def _business_domain(item: ContributionItem) -> str:
    parts = item.group_key.split(":")
    if len(parts) >= 2 and parts[0] in {"scope", "issue", "module"}:
        return parts[1]
    return item.modules[0] if item.modules else "unclassified"

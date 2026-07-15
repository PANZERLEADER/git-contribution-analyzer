from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any, TypedDict

from git_contribution_analyzer.domain.models.contribution import ContributionCommit
from git_contribution_analyzer.domain.services.contribution_rules import is_generated_path

STRUCTURAL_SIGNAL_RULE_VERSION = "structural-signals-v1"
MIN_CO_CHANGE_COMMITS = 2
MIN_HOTSPOT_COMMITS = 2
MAX_SIGNAL_ENTRIES = 20
MAX_COMMIT_HASHES = 50

_LIMITATIONS = (
    "Repeated co-change indicates structural association, not a runtime dependency.",
    "Hotspots indicate change concentration, not code quality or individual performance.",
    "Merge commits, generated paths, binary-only changes, and duplicate patches are excluded.",
)


class _Coupling(TypedDict):
    leftPath: str
    rightPath: str
    coChangeCommits: int
    confidence: str
    commitHashes: list[str]


class _Hotspot(TypedDict):
    path: str
    changeCommits: int
    coupledFiles: int
    coChangeCommits: int
    score: int
    commitHashes: list[str]


def build_structural_signals(
    commits: tuple[ContributionCommit, ...],
) -> dict[str, Any]:
    file_commits: defaultdict[str, set[str]] = defaultdict(set)
    edge_commits: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    analyzed_commits = 0
    seen_patches: set[str] = set()

    for commit in sorted(commits, key=lambda value: (value.authored_at, value.hash)):
        if commit.merge:
            continue
        patch_key = commit.patch_id or commit.hash
        if patch_key in seen_patches:
            continue
        seen_patches.add(patch_key)
        paths = _eligible_paths(commit)
        if not paths:
            continue
        analyzed_commits += 1
        for path in paths:
            file_commits[path].add(commit.hash)
        for left_path, right_path in combinations(paths, 2):
            edge_commits[(left_path, right_path)].add(commit.hash)

    strong_edges = {
        edge: hashes
        for edge, hashes in edge_commits.items()
        if len(hashes) >= MIN_CO_CHANGE_COMMITS
    }
    couplings: list[_Coupling] = [
        {
            "leftPath": left_path,
            "rightPath": right_path,
            "coChangeCommits": len(hashes),
            "confidence": _coupling_confidence(len(hashes)),
            "commitHashes": sorted(hashes)[:MAX_COMMIT_HASHES],
        }
        for (left_path, right_path), hashes in strong_edges.items()
    ]
    couplings.sort(
        key=lambda value: (
            -value["coChangeCommits"],
            value["leftPath"],
            value["rightPath"],
        )
    )

    neighbors: defaultdict[str, set[str]] = defaultdict(set)
    coupled_commits: defaultdict[str, int] = defaultdict(int)
    for (left_path, right_path), hashes in strong_edges.items():
        neighbors[left_path].add(right_path)
        neighbors[right_path].add(left_path)
        coupled_commits[left_path] += len(hashes)
        coupled_commits[right_path] += len(hashes)

    hotspots: list[_Hotspot] = [
        {
            "path": path,
            "changeCommits": len(hashes),
            "coupledFiles": len(neighbors[path]),
            "coChangeCommits": coupled_commits[path],
            "score": len(hashes) + coupled_commits[path],
            "commitHashes": sorted(hashes)[:MAX_COMMIT_HASHES],
        }
        for path, hashes in file_commits.items()
        if len(hashes) >= MIN_HOTSPOT_COMMITS
    ]
    hotspots.sort(
        key=lambda value: (
            -value["score"],
            -value["changeCommits"],
            value["path"],
        )
    )

    return {
        "ruleVersion": STRUCTURAL_SIGNAL_RULE_VERSION,
        "summary": {
            "analyzedCommits": analyzed_commits,
            "analyzedFiles": len(file_commits),
            "coupledPairs": len(couplings),
            "hotspots": len(hotspots),
        },
        "couplings": couplings[:MAX_SIGNAL_ENTRIES],
        "hotspots": hotspots[:MAX_SIGNAL_ENTRIES],
        "limitations": list(_LIMITATIONS),
    }


def _eligible_paths(commit: ContributionCommit) -> tuple[str, ...]:
    if (
        commit.paths
        and commit.binary_files >= len(commit.paths)
        and commit.insertions + commit.deletions == 0
    ):
        return ()
    return tuple(
        sorted(
            {
                normalized
                for path in commit.paths
                if (normalized := path.replace("\\", "/").strip("/"))
                and not is_generated_path(normalized)
            }
        )
    )


def _coupling_confidence(co_change_commits: int) -> str:
    if co_change_commits >= 3:
        return "HIGH"
    return "MEDIUM"

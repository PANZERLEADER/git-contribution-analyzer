from __future__ import annotations

import re

from git_contribution_analyzer.domain.models.contribution import ContributionItem, Evidence

CONVENTIONAL_TYPE = re.compile(r"^(?P<type>[a-zA-Z]+)(?:\([^)]*\))?!?:")
TYPE_MAP = {
    "feat": "FEATURE",
    "feature": "FEATURE",
    "fix": "FIX",
    "refactor": "REFACTOR",
    "perf": "PERFORMANCE",
    "test": "TEST",
    "docs": "DOCUMENTATION",
    "doc": "DOCUMENTATION",
    "build": "BUILD",
    "ci": "CI",
    "chore": "CHORE",
    "style": "STYLE",
    "revert": "REVERT",
}
GENERATED_PARTS = {"build", "dist", "generated", "target", "vendor"}
GENERATED_FILES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "yarn.lock",
}


def classify_commit(subject: str) -> str:
    if subject.casefold().startswith("revert "):
        return "REVERT"
    match = CONVENTIONAL_TYPE.match(subject.strip())
    if match is None:
        return "OTHER"
    return TYPE_MAP.get(match.group("type").casefold(), "OTHER")


def module_from_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized or "/" not in normalized:
        return "root"
    return normalized.split("/", maxsplit=1)[0]


def is_generated_path(path: str) -> bool:
    normalized = path.replace("\\", "/").strip("/").casefold()
    parts = set(normalized.split("/"))
    return normalized.rsplit("/", maxsplit=1)[-1] in GENERATED_FILES or bool(
        parts.intersection(GENERATED_PARTS)
    )


def build_evidence(items: tuple[ContributionItem, ...]) -> tuple[Evidence, ...]:
    evidence: list[Evidence] = []
    for item in items:
        commit_hashes = tuple(commit.hash for commit in item.commits)
        evidence.append(
            Evidence(
                id=item.evidence_ids[0],
                evidence_type="CONTRIBUTION_ITEM",
                summary=(
                    f"{len(item.commits)} commits across {len(item.paths)} files "
                    f"in {len(item.modules)} modules"
                ),
                commit_hashes=commit_hashes,
                paths=item.paths,
                metrics=(
                    ("commits", len(item.commits)),
                    ("filesChanged", sum(commit.files_changed for commit in item.commits)),
                    ("insertions", sum(commit.insertions for commit in item.commits)),
                    ("deletions", sum(commit.deletions for commit in item.commits)),
                ),
            )
        )
    return tuple(evidence)

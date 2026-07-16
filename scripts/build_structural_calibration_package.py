# ruff: noqa: RUF001 - Chinese review templates intentionally use CJK punctuation.

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import subprocess
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Any

from git_contribution_analyzer.adapters.workspace.config import load_config
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.application.use_cases.manage_structural_baselines import (
    rebuild_structural_baseline,
)
from git_contribution_analyzer.domain.models.contribution import ContributionCommit
from git_contribution_analyzer.domain.models.structural_baseline import (
    StructuralRuleConfig,
    StructuralTimeStrategy,
)
from git_contribution_analyzer.domain.services.structural_baseline import (
    build_structural_baseline,
)

STRATUM_ORDER = (
    "STRUCTURAL_CANDIDATE",
    "ORDINARY_CONTROL",
    "MECHANICAL_CONTROL",
    "INSUFFICIENT_HISTORY",
)
TIME_STRATEGIES = (
    StructuralTimeStrategy.LIFETIME,
    StructuralTimeStrategy.ROLLING_WINDOW,
    StructuralTimeStrategy.DUAL_WINDOW,
)
MECHANICAL_SUBJECT = re.compile(
    r"(?i)(format|rename|generated|license|dependenc|\bbump\b|\bchore\b|"
    r"typo|\bstyle\b|cleanup|whitespace)"
)
REVIEWER_FIELDS = (
    "sample_id",
    "repository_alias",
    "stratum",
    "path_count_band",
    "hotspot_exposure_count",
    "coupling_exposure_count",
    "cross_module_coupling_count",
    "mechanical_candidate",
    "expected_handling",
    "reviewer_id",
    "label",
    "preferred_time_strategy",
    "confidence",
    "rationale",
)


@dataclass(frozen=True, slots=True)
class CalibrationCandidate:
    source_id: str
    repository_alias: str
    stratum: str
    path_count: int
    hotspot_exposure_count: int
    coupling_exposure_count: int
    cross_module_coupling_count: int
    mechanical_candidate: bool
    evidence: Mapping[str, Any]


def count_strata(candidates: Iterable[CalibrationCandidate]) -> dict[str, int]:
    counts = Counter(candidate.stratum for candidate in candidates)
    return {stratum: counts[stratum] for stratum in STRATUM_ORDER if counts[stratum]}


def select_stratified_samples(
    candidates: Iterable[CalibrationCandidate], quotas: Mapping[str, int]
) -> list[CalibrationCandidate]:
    grouped: dict[str, list[CalibrationCandidate]] = {
        stratum: [] for stratum in STRATUM_ORDER
    }
    for candidate in candidates:
        if candidate.stratum in grouped:
            grouped[candidate.stratum].append(candidate)

    selected: list[CalibrationCandidate] = []
    for stratum in STRATUM_ORDER:
        required = int(quotas.get(stratum, 0))
        ordered = sorted(grouped[stratum], key=_selection_key)
        if len(ordered) < required:
            raise ValueError(
                f"Insufficient {stratum} candidates: required {required}, found {len(ordered)}"
            )
        selected.extend(ordered[:required])
    return selected


def build_reviewer_rows(
    candidates: Sequence[CalibrationCandidate], *, reviewer_id: str, start_index: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset, candidate in enumerate(candidates):
        rows.append(
            {
                "sample_id": f"CAL-SAMPLE-{start_index + offset:03d}",
                "repository_alias": candidate.repository_alias,
                "stratum": candidate.stratum,
                "path_count_band": _path_count_band(candidate.path_count),
                "hotspot_exposure_count": candidate.hotspot_exposure_count,
                "coupling_exposure_count": candidate.coupling_exposure_count,
                "cross_module_coupling_count": candidate.cross_module_coupling_count,
                "mechanical_candidate": candidate.mechanical_candidate,
                "expected_handling": (
                    "ABSTAIN"
                    if candidate.stratum == "INSUFFICIENT_HISTORY"
                    else "NEGATIVE_CONTROL"
                    if candidate.stratum == "MECHANICAL_CONTROL"
                    else "REVIEW"
                ),
                "reviewer_id": reviewer_id,
                "label": "",
                "preferred_time_strategy": "",
                "confidence": "",
                "rationale": "",
            }
        )
    return rows


def build_package_summary(
    candidates: Sequence[CalibrationCandidate], *, repository_count: int
) -> dict[str, Any]:
    strata = count_strata(candidates)
    mechanical = strata.get("MECHANICAL_CONTROL", 0)
    return {
        "samples": len(candidates),
        "repositories": repository_count,
        "strata": strata,
        "mechanicalNegativeControls": mechanical,
        "readyForIndependentReview": (
            len(candidates) >= 80 and repository_count >= 5 and mechanical >= 20
        ),
    }


def generate_package(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output = Path(str(config["outputDirectory"])).resolve()
    repositories = list(config["repositories"])
    if len(repositories) < 1:
        raise ValueError("At least one calibration repository is required")
    _prepare_output(output)

    all_selected: list[CalibrationCandidate] = []
    repository_results: list[dict[str, Any]] = []
    next_index = 1
    reviewer_a: list[dict[str, Any]] = []
    reviewer_b: list[dict[str, Any]] = []
    draft_samples: list[dict[str, Any]] = []

    for repository in repositories:
        candidates, repository_result = collect_repository_candidates(repository)
        quotas = {key: int(value) for key, value in dict(repository["quotas"]).items()}
        selected = select_stratified_samples(candidates, quotas)
        rows_a = build_reviewer_rows(selected, reviewer_id="A", start_index=next_index)
        rows_b = build_reviewer_rows(selected, reviewer_id="B", start_index=next_index)
        reviewer_a.extend(rows_a)
        reviewer_b.extend(rows_b)
        for offset, candidate in enumerate(selected):
            sample_id = f"CAL-SAMPLE-{next_index + offset:03d}"
            evidence_ref = f"evidence/{sample_id}.json"
            _write_json(output / evidence_ref, dict(candidate.evidence))
            draft_samples.append(
                {
                    "sampleId": sample_id,
                    "repositoryAlias": candidate.repository_alias,
                    "stratum": candidate.stratum,
                    "evidenceRef": evidence_ref,
                    "reviewerA": None,
                    "reviewerB": None,
                    "adjudicatedLabel": None,
                }
            )
        next_index += len(selected)
        all_selected.extend(selected)
        repository_result["selectedStrata"] = count_strata(selected)
        repository_results.append(repository_result)

    summary = build_package_summary(all_selected, repository_count=len(repositories))
    expected = int(config.get("expectedSamples", 80))
    if len(all_selected) != expected:
        raise ValueError(f"Expected {expected} samples, generated {len(all_selected)}")
    if not summary["readyForIndependentReview"]:
        raise ValueError(f"Calibration package does not meet review prerequisites: {summary}")

    extraction_config = {
        "cutoffRule": "eligible-commit-percentile-0.80",
        "strategies": [strategy.value for strategy in TIME_STRATEGIES],
        "thresholds": asdict(StructuralRuleConfig()),
        "repositoryQuotas": [
            {"alias": value["alias"], "quotas": value["quotas"]}
            for value in repositories
        ],
    }
    extraction_hash = _canonical_sha256(extraction_config)
    manifest = {
        "schemaVersion": "1.0",
        "status": "READY_FOR_INDEPENDENT_REVIEW",
        "createdAt": datetime.now(UTC).isoformat(),
        "summary": summary,
        "extractionConfig": extraction_config,
        "extractionConfigSha256": extraction_hash,
        "repositories": repository_results,
        "privacy": {
            "authorsIncluded": False,
            "emailsIncluded": False,
            "reviewerSheetsContainSourceIdentifiers": False,
            "sharedEvidenceContainsPublicGitIdentifiers": True,
        },
        "holdout": {
            "status": "UNTOUCHED",
            "repositoriesIncluded": 0,
        },
    }
    calibration_draft = {
        "schemaVersion": "1.0",
        "status": "READY_FOR_INDEPENDENT_REVIEW",
        "minimumRequiredSamples": 80,
        "repositories": [
            {
                "alias": value["alias"],
                "canonical": value["canonical"],
                "sourceRevision": value["sourceRevision"],
            }
            for value in repository_results
        ],
        "samples": draft_samples,
    }
    _write_json(output / "manifest.json", manifest)
    _write_json(output / "calibration-draft.json", calibration_draft)
    _write_csv(output / "reviewer-a.csv", reviewer_a, REVIEWER_FIELDS)
    _write_csv(output / "reviewer-b.csv", reviewer_b, REVIEWER_FIELDS)
    _write_adjudication(output / "adjudication.csv", reviewer_a)
    (output / "README.md").write_text(
        _readme_text(summary, extraction_hash), encoding="utf-8", newline="\n"
    )
    (output / "REVIEW_GUIDE.zh-CN.md").write_text(
        build_review_guide_zh_cn(), encoding="utf-8", newline="\n"
    )
    (output / "AI_RATIONALE_PROMPT.zh-CN.md").write_text(
        build_ai_rationale_prompt_zh_cn(), encoding="utf-8", newline="\n"
    )
    return manifest


def collect_repository_candidates(
    repository: Mapping[str, Any],
) -> tuple[list[CalibrationCandidate], dict[str, Any]]:
    root = Path(str(repository["path"])).resolve()
    alias = str(repository["alias"])
    canonical = str(repository["canonical"])
    layout = WorkspaceLayout.for_repository(root)
    if not layout.database.is_file():
        raise ValueError(f"GCA index is missing for {alias}: {layout.database}")
    active_config = load_config(layout.config)
    target_ref = f"refs/heads/{active_config.default_branch}"
    allowed_hashes = set(_git(root, "rev-list", target_ref).splitlines())
    source_revision = _git(root, "rev-parse", target_ref)

    connection = sqlite3.connect(f"file:{layout.database.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        facts = [
            row
            for row in connection.execute(
                """
                SELECT f.commit_hash, f.occurred_at, f.path_count, f.edge_count,
                       f.context_capped, f.excluded_reason, c.subject, c.patch_id
                FROM structural_commit_facts f
                JOIN commits c
                  ON c.repository_id = f.repository_id AND c.hash = f.commit_hash
                ORDER BY f.occurred_at, f.commit_hash
                """
            ).fetchall()
            if str(row["commit_hash"]) in allowed_hashes
        ]
        eligible = [row for row in facts if row["excluded_reason"] is None]
        if len(eligible) < 20:
            raise ValueError(f"Insufficient eligible history for {alias}: {len(eligible)}")
        cutoff_index = min(len(eligible) - 1, max(2, int(len(eligible) * 0.80)))
        cutoff = _parse_sqlite_datetime(eligible[cutoff_index]["occurred_at"])
        baselines = {
            strategy.value: rebuild_structural_baseline(
                root,
                cutoff=cutoff,
                time_strategy=strategy,
            )
            for strategy in TIME_STRATEGIES
        }
        candidate_rows = [
            row
            for row in facts
            if row["excluded_reason"] is None
            and _parse_sqlite_datetime(row["occurred_at"]) >= cutoff
        ]
        candidate_hashes = {str(row["commit_hash"]) for row in candidate_rows}
        paths_by_commit: dict[str, list[str]] = {value: [] for value in candidate_hashes}
        for row in connection.execute(
            "SELECT commit_hash, path FROM structural_file_occurrences"
        ).fetchall():
            commit_hash = str(row["commit_hash"])
            if commit_hash in paths_by_commit:
                paths_by_commit[commit_hash].append(str(row["path"]))
        candidates = _classify_candidates(
            alias=alias,
            canonical=canonical,
            cutoff=cutoff,
            rows=candidate_rows,
            paths_by_commit=paths_by_commit,
            baselines=baselines,
        )
        candidates.append(
            _insufficient_history_candidate(
                alias=alias,
                canonical=canonical,
                first_row=eligible[0],
                first_paths=_paths_for_commit(connection, str(eligible[0]["commit_hash"])),
            )
        )
    finally:
        connection.close()

    return candidates, {
        "alias": alias,
        "canonical": canonical,
        "sourceRevision": source_revision,
        "defaultBranch": active_config.default_branch,
        "eligibleHistoryCommits": len(eligible),
        "candidateCommits": len(candidate_rows),
        "candidateStrata": count_strata(candidates),
        "cutoff": cutoff.isoformat(),
        "baselines": {
            strategy: {
                "baselineId": value["baselineId"],
                "summary": value["summary"],
                "confidence": value["materialization"]["confidence"],
                "gaps": value["materialization"]["gaps"],
            }
            for strategy, value in baselines.items()
        },
    }


def _classify_candidates(
    *,
    alias: str,
    canonical: str,
    cutoff: datetime,
    rows: Sequence[sqlite3.Row],
    paths_by_commit: Mapping[str, Sequence[str]],
    baselines: Mapping[str, Mapping[str, Any]],
) -> list[CalibrationCandidate]:
    indexes = {
        strategy: _materialization_index(value)
        for strategy, value in baselines.items()
    }
    result: list[CalibrationCandidate] = []
    for row in rows:
        commit_hash = str(row["commit_hash"])
        paths = tuple(sorted(set(paths_by_commit.get(commit_hash, ()))))
        exposures = {
            strategy: _match_exposures(paths, index)
            for strategy, index in indexes.items()
        }
        hotspot_count = max(len(value["hotspots"]) for value in exposures.values())
        coupling_count = max(len(value["couplings"]) for value in exposures.values())
        cross_module = max(
            sum(1 for coupling in value["couplings"] if coupling["crossModule"])
            for value in exposures.values()
        )
        mechanical = (
            bool(MECHANICAL_SUBJECT.search(str(row["subject"])))
            or bool(row["context_capped"])
            or int(row["path_count"]) >= 50
        )
        if mechanical:
            stratum = "MECHANICAL_CONTROL"
        elif hotspot_count or coupling_count:
            stratum = "STRUCTURAL_CANDIDATE"
        elif int(row["path_count"]) <= 20:
            stratum = "ORDINARY_CONTROL"
        else:
            continue
        evidence = {
            "schemaVersion": "1.0",
            "repository": canonical,
            "repositoryAlias": alias,
            "commitHash": commit_hash,
            "subject": str(row["subject"]),
            "occurredAt": _parse_sqlite_datetime(row["occurred_at"]).isoformat(),
            "paths": list(paths),
            "pathCount": int(row["path_count"]),
            "contextCapped": bool(row["context_capped"]),
            "mechanicalCandidate": mechanical,
            "cutoff": cutoff.isoformat(),
            "exposuresByStrategy": exposures,
            "limitations": [
                "Historical co-change is an association, not a runtime dependency.",
                "Labels concern defensible difficulty context, not individual value.",
            ],
        }
        result.append(
            CalibrationCandidate(
                source_id=commit_hash,
                repository_alias=alias,
                stratum=stratum,
                path_count=int(row["path_count"]),
                hotspot_exposure_count=hotspot_count,
                coupling_exposure_count=coupling_count,
                cross_module_coupling_count=cross_module,
                mechanical_candidate=mechanical,
                evidence=evidence,
            )
        )
    return result


def _insufficient_history_candidate(
    *, alias: str, canonical: str, first_row: sqlite3.Row, first_paths: Sequence[str]
) -> CalibrationCandidate:
    occurred_at = _parse_sqlite_datetime(first_row["occurred_at"])
    commit = ContributionCommit(
        hash=str(first_row["commit_hash"]),
        subject=str(first_row["subject"]),
        authored_at=occurred_at,
        commit_type="STRUCTURAL_FACT",
        delivery_status="LANDED",
        paths=tuple(sorted(first_paths)),
        modules=tuple(sorted({_module(path) for path in first_paths})),
        insertions=1,
        deletions=0,
        files_changed=len(first_paths),
        merge=False,
        binary_files=0,
        generated_files=0,
        patch_id=str(first_row["patch_id"]) if first_row["patch_id"] else None,
        period_at=occurred_at,
    )
    baseline = build_structural_baseline(
        (commit,),
        cutoff=occurred_at + timedelta(seconds=1),
        config=StructuralRuleConfig(minimum_baseline_commits=2),
        identity_context={"repositoryAlias": alias, "scenario": "insufficient-history"},
    )
    evidence = {
        "schemaVersion": "1.0",
        "repository": canonical,
        "repositoryAlias": alias,
        "scenario": "INSUFFICIENT_HISTORY",
        "realHistoryCommitCount": 1,
        "summary": asdict(baseline.summary),
        "confidence": baseline.materialization.confidence,
        "gaps": list(baseline.materialization.gaps),
        "hotspots": [],
        "couplings": [],
    }
    return CalibrationCandidate(
        source_id=f"insufficient:{baseline.id}",
        repository_alias=alias,
        stratum="INSUFFICIENT_HISTORY",
        path_count=0,
        hotspot_exposure_count=0,
        coupling_exposure_count=0,
        cross_module_coupling_count=0,
        mechanical_candidate=False,
        evidence=evidence,
    )


def _materialization_index(baseline: Mapping[str, Any]) -> dict[str, Any]:
    materialization = baseline["materialization"]
    hotspots = {str(value["path"]): dict(value) for value in materialization["hotspots"]}
    couplings = {
        (str(value["leftPath"]), str(value["rightPath"])): dict(value)
        for value in materialization["couplings"]
    }
    return {
        "baselineId": baseline["baselineId"],
        "confidence": materialization["confidence"],
        "gaps": list(materialization["gaps"]),
        "hotspots": hotspots,
        "couplings": couplings,
    }


def _match_exposures(paths: Sequence[str], index: Mapping[str, Any]) -> dict[str, Any]:
    path_set = set(paths)
    hotspots = [index["hotspots"][path] for path in sorted(path_set & index["hotspots"].keys())]
    couplings = []
    if len(path_set) <= 200:
        for pair in combinations(sorted(path_set), 2):
            value = index["couplings"].get(pair)
            if value is not None:
                couplings.append(value)
    return {
        "baselineId": index["baselineId"],
        "confidence": index["confidence"],
        "gaps": index["gaps"],
        "hotspots": hotspots,
        "couplings": couplings,
    }


def _selection_key(candidate: CalibrationCandidate) -> tuple[Any, ...]:
    if candidate.stratum == "STRUCTURAL_CANDIDATE":
        return (
            -candidate.cross_module_coupling_count,
            -candidate.coupling_exposure_count,
            -candidate.hotspot_exposure_count,
            candidate.path_count,
            candidate.source_id,
        )
    if candidate.stratum == "MECHANICAL_CONTROL":
        return (
            -candidate.path_count,
            -candidate.coupling_exposure_count,
            -candidate.hotspot_exposure_count,
            candidate.source_id,
        )
    return (candidate.path_count, candidate.source_id)


def _path_count_band(value: int) -> str:
    if value == 0:
        return "N/A"
    if value <= 5:
        return "1-5"
    if value <= 20:
        return "6-20"
    if value <= 50:
        return "21-50"
    if value <= 200:
        return "51-200"
    return "201+"


def _paths_for_commit(connection: sqlite3.Connection, commit_hash: str) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT path FROM structural_file_occurrences WHERE commit_hash = ? ORDER BY path",
            (commit_hash,),
        ).fetchall()
    ]


def _parse_sqlite_datetime(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _module(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    return normalized.split("/", maxsplit=1)[0] if "/" in normalized else "root"


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _prepare_output(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output directory must be empty: {output}")
    (output / "evidence").mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_adjudication(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        "sample_id",
        "repository_alias",
        "stratum",
        "reviewer_a_label",
        "reviewer_b_label",
        "agreement",
        "adjudicated_label",
        "adjudication_rationale",
    )
    values = [
        {
            "sample_id": row["sample_id"],
            "repository_alias": row["repository_alias"],
            "stratum": row["stratum"],
            "reviewer_a_label": "",
            "reviewer_b_label": "",
            "agreement": "",
            "adjudicated_label": "",
            "adjudication_rationale": "",
        }
        for row in rows
    ]
    _write_csv(path, values, fields)


def _canonical_sha256(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _readme_text(summary: Mapping[str, Any], extraction_hash: str) -> str:
    return f"""# Structural Calibration Review Package

Status: `READY_FOR_INDEPENDENT_REVIEW`

This package contains {summary['samples']} calibration items from
{summary['repositories']} public repositories. Reviewer A and Reviewer B must work independently
before adjudication.

## Review Question

Does the historical hotspot or co-change context add defensible engineering-difficulty context for
this change?

Allowed labels: `YES`, `NO`, `ABSTAIN`. Do not label employee value, time spent, code quality,
business impact, compensation or promotion suitability.

## Files

- `reviewer-a.csv` and `reviewer-b.csv`: independent blank label sheets without source identifiers.
- `evidence/`: shared public Git evidence. Authors and emails are excluded.
- `adjudication.csv`: fill only after both reviewer sheets are complete.
- `calibration-draft.json`: unlabeled fixture draft; do not promote it into tests before review.
- `manifest.json`: repository revisions, baseline summaries and extraction configuration.
- `REVIEW_GUIDE.zh-CN.md`: Chinese decision guide and fill-in rationale templates.
- `AI_RATIONALE_PROMPT.zh-CN.md`: prompt for AI-assisted rationale drafting after human labeling.

Extraction configuration SHA-256: `{extraction_hash}`.

Holdout status: `UNTOUCHED`. Do not acquire or inspect holdout repositories during calibration.
"""


def build_review_guide_zh_cn() -> str:
    return """# 结构校准人工标注指南

## 每项怎么做

1. 打开 Reviewer CSV 中对应的 `sample_id`。
2. 阅读 `evidence/<sample_id>.json`，只判断历史热点或共同变更是否增加了可辩护的工程难度上下文。
3. 先由审核者本人选择 `YES`、`NO` 或 `ABSTAIN`。
4. 再填写 `preferred_time_strategy`、`confidence` 和 `rationale`。
5. 如果不知道理由怎么组织，可以把人工已选标签和 evidence 交给 AI，使用包内提示词整理文字。

AI 可以整理证据和语言，但不得替审核者选择或修改标签。

## YES 理由模板

```text
该变更涉及【模块或路径范围】。在【LIFETIME / ROLLING_WINDOW / DUAL_WINDOW】下，
历史证据显示【热点文件或稳定共同变更关系】；该关系并非主要由【格式化、批量重命名、
依赖升级、公共配置或其他机械因素】造成。因此，这些结构信号为本次变更增加了可辩护的
工程难度上下文，标记为 YES。置信度为【HIGH / MEDIUM / LOW】。
```

## NO 理由模板

```text
该变更虽然命中【热点或共同变更信号】，但暴露主要来自【机械变更、公共 hub、同目录批量
修改、文档/配置同步或偶然关联】。现有历史关系不能可靠说明本次变更具有额外工程难度，
因此标记为 NO。置信度为【HIGH / MEDIUM / LOW】。
```

## ABSTAIN 理由模板

```text
由于【INSUFFICIENT_STRUCTURAL_BASELINE / STRUCTURAL_CONTEXT_CAPPED / 证据缺失或冲突】，
当前材料不足以可靠判断历史结构是否增加工程难度上下文，因此标记为 ABSTAIN。
置信度为【HIGH / MEDIUM / LOW】。
```

## 时间策略怎么填

- `LIFETIME`：长期关系最能解释本次变更，且没有被陈旧历史主导。
- `ROLLING_WINDOW`：最近一年关系更有解释力，长期关系已经过时。
- `DUAL_WINDOW`：长期和近期信息结合后最合理。
- 留空：三种策略都没有形成足够依据，或当前标签为 `ABSTAIN`。

## 禁止判断

不要评价个人能力、价值、工时、代码质量、业务收益、薪酬、绩效或晋升资格。
"""


def build_ai_rationale_prompt_zh_cn() -> str:
    return """# AI 辅助理由整理提示词

你是结构化证据整理助手。人工审核者已经完成标签判断；你不得选择、修改或推荐标签。

## 输入

- 人工已选标签：`{{YES | NO | ABSTAIN}}`
- 人工置信度：`{{HIGH | MEDIUM | LOW}}`
- 人工偏好时间策略：`{{LIFETIME | ROLLING_WINDOW | DUAL_WINDOW | 留空}}`
- Evidence JSON：

```json
{{粘贴 evidence/<sample_id>.json}}
```

## 任务

1. 只引用 Evidence JSON 中存在的事实。
2. 用 2 至 4 句话生成与人工已选标签一致的中文 `rationale` 草稿。
3. 说明热点、共同变更、跨模块关系或 gap 中真正影响判断的部分。
4. 如果人工标签与 evidence 明显矛盾，只输出 `需要人工复核`，不要自行更改标签。

## 禁止

- 不得选择、修改或推荐标签。
- 不得推断个人价值、能力、工时、绩效、代码质量或业务收益。
- 不得使用 Evidence JSON 之外的信息。

## 输出

```json
{
  "label": "保持人工输入不变",
  "preferred_time_strategy": "保持人工输入不变",
  "confidence": "保持人工输入不变",
  "rationale": "2 至 4 句中文理由"
}
```
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a two-reviewer structural calibration package"
    )
    parser.add_argument("config", type=Path, help="Calibration package JSON configuration")
    return parser.parse_args()


def main() -> None:
    arguments = _parse_args()
    manifest = generate_package(arguments.config)
    print(json.dumps(manifest["summary"], ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()

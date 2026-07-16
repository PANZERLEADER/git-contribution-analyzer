from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "build_structural_calibration_package.py"
SPEC = importlib.util.spec_from_file_location("structural_calibration_package", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _candidate(index: int, stratum: str) -> object:
    return MODULE.CalibrationCandidate(
        source_id=f"source-{index:03d}",
        repository_alias="CAL-01",
        stratum=stratum,
        path_count=index % 60 + 1,
        hotspot_exposure_count=index % 5,
        coupling_exposure_count=index % 7,
        cross_module_coupling_count=index % 3,
        mechanical_candidate=stratum == "MECHANICAL_CONTROL",
        evidence={
            "repository": "public/example",
            "commitHash": f"{index:040x}",
            "subject": f"public subject {index}",
            "paths": [f"src/file-{index}.py"],
        },
    )


def test_select_stratified_samples_should_be_deterministic_and_exact() -> None:
    candidates = [
        *(_candidate(index, "STRUCTURAL_CANDIDATE") for index in range(20)),
        *(_candidate(index + 100, "ORDINARY_CONTROL") for index in range(20)),
        *(_candidate(index + 200, "MECHANICAL_CONTROL") for index in range(20)),
        _candidate(999, "INSUFFICIENT_HISTORY"),
    ]
    quotas = {
        "STRUCTURAL_CANDIDATE": 6,
        "ORDINARY_CONTROL": 4,
        "MECHANICAL_CONTROL": 4,
        "INSUFFICIENT_HISTORY": 1,
    }

    first = MODULE.select_stratified_samples(candidates, quotas)
    second = MODULE.select_stratified_samples(reversed(candidates), quotas)

    assert [entry.source_id for entry in first] == [entry.source_id for entry in second]
    assert len(first) == 15
    assert len({entry.source_id for entry in first}) == 15
    assert MODULE.count_strata(first) == quotas


def test_reviewer_rows_should_exclude_source_identifiers() -> None:
    selected = [_candidate(1, "STRUCTURAL_CANDIDATE")]

    rows = MODULE.build_reviewer_rows(selected, reviewer_id="A", start_index=1)

    assert rows == [
        {
            "sample_id": "CAL-SAMPLE-001",
            "repository_alias": "CAL-01",
            "stratum": "STRUCTURAL_CANDIDATE",
            "path_count_band": "1-5",
            "hotspot_exposure_count": 1,
            "coupling_exposure_count": 1,
            "cross_module_coupling_count": 1,
            "mechanical_candidate": False,
            "expected_handling": "REVIEW",
            "reviewer_id": "A",
            "label": "",
            "preferred_time_strategy": "",
            "confidence": "",
            "rationale": "",
        }
    ]
    serialized = repr(rows)
    assert "public/example" not in serialized
    assert "commitHash" not in serialized
    assert "public subject" not in serialized
    assert "src/file" not in serialized


def test_package_summary_should_enforce_protocol_counts() -> None:
    selected = [
        *(_candidate(index, "STRUCTURAL_CANDIDATE") for index in range(32)),
        *(_candidate(index + 100, "ORDINARY_CONTROL") for index in range(21)),
        *(_candidate(index + 200, "MECHANICAL_CONTROL") for index in range(22)),
        *(_candidate(index + 300, "INSUFFICIENT_HISTORY") for index in range(5)),
    ]

    summary = MODULE.build_package_summary(selected, repository_count=5)

    assert summary["samples"] == 80
    assert summary["repositories"] == 5
    assert summary["mechanicalNegativeControls"] == 22
    assert summary["readyForIndependentReview"] is True


def test_review_templates_should_help_with_rationale_without_ai_labeling() -> None:
    guide = MODULE.build_review_guide_zh_cn()
    prompt = MODULE.build_ai_rationale_prompt_zh_cn()

    assert "YES 理由模板" in guide
    assert "NO 理由模板" in guide
    assert "ABSTAIN 理由模板" in guide
    assert "先由审核者本人选择" in guide
    assert "不得选择、修改或推荐标签" in prompt
    assert "人工已选标签" in prompt

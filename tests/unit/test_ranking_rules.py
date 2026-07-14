from __future__ import annotations

from git_contribution_analyzer.domain.models.ranking import RankingConfig
from git_contribution_analyzer.domain.services.ranking_rules import build_ranking


def _item(
    item_id: str,
    *,
    bucket: str = "COMPLETED",
    size: str = "SMALL",
    difficulty: str = "ROUTINE",
) -> dict[str, object]:
    return {
        "contributionItemId": item_id,
        "completionBucket": bucket,
        "size": {"band": size, "gaps": []},
        "difficulty": {"level": difficulty, "gaps": []},
        "evidenceIds": [f"EV-{item_id}"],
    }


def _subject(person_id: str, items: list[dict[str, object]]) -> dict[str, object]:
    return {"person": {"id": person_id}, "itemAssessments": items}


def test_should_rank_supported_dimensions_with_dense_ties() -> None:
    ranking = build_ranking(
        [
            _subject("a", [_item("1", size="LARGE", difficulty="ROUTINE")]),
            _subject("b", [_item("2", size="SMALL", difficulty="HIGH_RISK")]),
            _subject("c", [_item("3", size="SMALL", difficulty="HIGH_RISK")]),
        ],
        ("workload", "difficulty", "delivery"),
        snapshot_id="snapshot",
    )

    workload, difficulty, delivery = ranking["dimensions"]
    assert workload["entries"][0]["personId"] == "a"
    assert workload["entries"][0]["rawValue"] == "6.0000"
    assert [entry["rank"] for entry in difficulty["entries"]] == [1, 1, 2]
    assert [entry["rank"] for entry in delivery["entries"]] == [1, 1, 1]


def test_should_apply_delivery_penalty_with_thirty_percent_cap() -> None:
    ranking = build_ranking(
        [
            _subject(
                "a",
                [
                    _item("1"),
                    _item("2"),
                    *[_item(str(index), bucket="REWORK") for index in range(3, 10)],
                ],
            )
        ],
        ("delivery",),
        snapshot_id="snapshot",
    )

    assert ranking["dimensions"][0]["entries"][0]["rawValue"] == "1.4000"


def test_should_build_weighted_composite_with_cohort_max_normalization() -> None:
    config = RankingConfig.model_validate(
        {
            "schemaVersion": "1.0",
            "rankingRuleVersion": "performance-ranking-v1",
            "weights": {"workload": "0.5", "difficulty": "0.3", "delivery": "0.2"},
            "normalization": "cohort-max",
            "ties": "dense",
        }
    )

    ranking = build_ranking(
        [
            _subject("a", [_item("1", size="LARGE", difficulty="ROUTINE")]),
            _subject("b", [_item("2", size="SMALL", difficulty="HIGH_RISK")]),
        ],
        (),
        snapshot_id="snapshot",
        config=config,
    )

    assert ranking["composite"]["entries"][0]["totalRank"] == 1
    assert ranking["composite"]["entries"][0]["totalScore"] == "75.0000"
    assert ranking["config"]["weights"]["workload"] == "0.5"

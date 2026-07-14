from __future__ import annotations

import json
from time import perf_counter

from git_contribution_analyzer.domain.models.ranking import RankingConfig
from git_contribution_analyzer.domain.services.ranking_rules import build_ranking

PEOPLE = 100
ITEMS_PER_PERSON = 150


def main() -> None:
    subjects = []
    for person_index in range(PEOPLE):
        items = []
        for item_index in range(ITEMS_PER_PERSON):
            item_id = f"{person_index:03d}-{item_index:03d}"
            items.append(
                {
                    "contributionItemId": item_id,
                    "completionBucket": (
                        "REWORK" if item_index % 20 == 0 else "COMPLETED"
                    ),
                    "size": {
                        "band": ("SMALL", "MEDIUM", "LARGE", "XLARGE")[
                            item_index % 4
                        ],
                        "gaps": [],
                    },
                    "difficulty": {
                        "level": ("ROUTINE", "STANDARD", "COMPLEX", "HIGH_RISK")[
                            (person_index + item_index) % 4
                        ],
                        "gaps": [],
                    },
                    "evidenceIds": [f"EV-{item_id}"],
                }
            )
        subjects.append(
            {
                "person": {"id": f"person-{person_index:03d}"},
                "itemAssessments": items,
            }
        )
    config = RankingConfig.model_validate(
        {
            "schemaVersion": "1.0",
            "rankingRuleVersion": "performance-ranking-v1",
            "weights": {"workload": "0.45", "difficulty": "0.35", "delivery": "0.20"},
            "normalization": "cohort-max",
            "ties": "dense",
        }
    )
    started = perf_counter()
    result = build_ranking(subjects, (), snapshot_id="benchmark", config=config)
    elapsed = perf_counter() - started
    print(
        json.dumps(
            {
                "people": PEOPLE,
                "items": PEOPLE * ITEMS_PER_PERSON,
                "elapsedSeconds": round(elapsed, 4),
                "dimensions": len(result["dimensions"]),
                "compositeEntries": len(result["composite"]["entries"]),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

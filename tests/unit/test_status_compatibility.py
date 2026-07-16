from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_status_v1_should_remain_unchanged_and_v2_should_own_structural_summary() -> None:
    v1 = json.loads((ROOT / "schemas" / "status" / "v1.json").read_text(encoding="utf-8"))
    v2 = json.loads((ROOT / "schemas" / "status" / "v2.json").read_text(encoding="utf-8"))

    assert v1["properties"]["schemaVersion"] == {"const": "1.0"}
    assert "structural" not in v1["properties"]["data"]["required"]
    assert "structural" not in v1["properties"]["data"]["properties"]

    assert v2["properties"]["schemaVersion"] == {"const": "2.0"}
    assert "structural" in v2["properties"]["data"]["required"]
    assert "structural" in v2["properties"]["data"]["properties"]

from __future__ import annotations

from typing import Any


def render_work_assessment_series_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Work Assessment Series",
        "",
        f"- Period: **{report['period']}**",
        f"- Time basis: **{report['timeBasis']}**",
        f"- Range: {report['range']['since']} to {report['range']['until']}",
        "",
        "| Period | Completed | Pending | Rework | Workload points | Difficulty points |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for entry in report["periods"]:
        metrics = entry["metrics"]
        label = f"{entry['label']} (partial)" if entry["partial"] else entry["label"]
        lines.append(
            f"| {label} | {metrics['completedItems']} | {metrics['pendingItems']} | "
            f"{metrics['reworkItems']} | {metrics['workloadPoints']} | "
            f"{metrics['difficultyPoints']} |"
        )
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    return "\n".join(lines) + "\n"

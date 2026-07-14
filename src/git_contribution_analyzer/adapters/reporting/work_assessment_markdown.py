from __future__ import annotations

from typing import Any


def render_work_assessment_markdown(report: dict[str, Any]) -> str:
    workload = report["workloadSummary"]
    lines = [
        "# Work Assessment",
        "",
        f"- Scope: **{report['scopeType']}**",
        f"- Completed items: {workload['completedItems']}",
        f"- Pending / rework / integration: {workload['pendingItems']} / "
        f"{workload['reworkItems']} / {workload['integrationItems']}",
        "",
        "## Technical Summary",
        "",
        report["technicalSummary"]["headline"],
        "",
        "## Business Summary",
        "",
        report["businessSummary"]["headline"],
        "",
        "## Work Items",
        "",
    ]
    for subject in report["subjects"]:
        lines.extend([f"### {subject['person']['name']}", ""])
        for item in subject["itemAssessments"]:
            lines.append(
                f"- **{item['contributionItemId']}**: {item['completionBucket']}, "
                f"size {item['size']['band']}, difficulty {item['difficulty']['level']} "
                f"[Evidence: {', '.join(item['evidenceIds'])}]"
            )
        lines.append("")
    if report["identityWarnings"]:
        lines.extend(["## Identity Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["identityWarnings"])
        lines.append("")
    lines.extend(["## Evidence Index", ""])
    for entry in report["evidence"]:
        lines.append(
            f"- **{entry['personId']}:{entry['id']}**: {entry['summary']}"
        )
    lines.append("")
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    return "\n".join(lines) + "\n"

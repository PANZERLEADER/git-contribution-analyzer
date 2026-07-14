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
    ranking = report.get("ranking", {})
    if ranking.get("enabled"):
        lines.extend(["## Rankings", ""])
        for dimension in ranking["dimensions"]:
            lines.extend(
                [
                    f"### {dimension['dimension'].title()}",
                    "",
                    "| Rank | Person | Raw value | Confidence |",
                    "|---:|---|---:|---|",
                ]
            )
            people = {
                subject["person"]["id"]: subject["person"]["name"]
                for subject in report["subjects"]
            }
            for entry in dimension["entries"]:
                lines.append(
                    f"| {entry['rank']} | {people[entry['personId']]} | "
                    f"{entry['rawValue']} | {entry['confidence']} |"
                )
            lines.append("")
        composite = ranking.get("composite")
        if composite:
            lines.extend(
                [
                    "### Composite",
                    "",
                    "| Rank | Person | Total score |",
                    "|---:|---|---:|",
                ]
            )
            people = {
                subject["person"]["id"]: subject["person"]["name"]
                for subject in report["subjects"]
            }
            for entry in composite["entries"]:
                lines.append(
                    f"| {entry['totalRank']} | {people[entry['personId']]} | "
                    f"{entry['totalScore']} |"
                )
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

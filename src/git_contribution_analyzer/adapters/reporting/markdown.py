from __future__ import annotations

from typing import Any

from git_contribution_analyzer.adapters.reporting.resume_markdown import render_resume_markdown
from git_contribution_analyzer.adapters.reporting.work_assessment_markdown import (
    render_work_assessment_markdown,
)


def render_markdown(report: dict[str, Any]) -> str:
    if report.get("reportType") == "WORK_ASSESSMENT":
        return render_work_assessment_markdown(report)
    if report.get("reportType") == "RESUME":
        return render_resume_markdown(report)
    if report.get("reportType") == "PROJECT":
        return _render_project_markdown(report)
    return _render_person_markdown(report)


def _render_person_markdown(report: dict[str, Any]) -> str:
    person = report["person"]
    summary = report["summary"]
    lines = [
        f"# Contribution Report: {person['name']}",
        "",
        f"- Email: `{person['email']}`",
        f"- Commits: {summary['commits']}",
        f"- Files changed: {summary['filesChanged']}",
        f"- Insertions / deletions: {summary['insertions']} / {summary['deletions']}",
        "",
        "## Technical Summary",
        "",
        report["technicalSummary"]["headline"],
        "",
    ]
    for highlight in report["technicalSummary"]["highlights"]:
        lines.append(
            f"- {highlight['text']} [Evidence: {', '.join(highlight['evidenceIds'])}]"
        )
    lines.extend(
        [
            "",
            "## Business Summary",
            "",
            report["businessSummary"]["headline"],
            "",
        ]
    )
    for highlight in report["businessSummary"]["highlights"]:
        lines.append(
            f"- {highlight['text']} [Evidence: {', '.join(highlight['evidenceIds'])}]"
        )
    lines.extend(
        [
        "",
        "## Contribution Items",
        "",
        ]
    )
    for item in report["contributionItems"]:
        lines.extend(
            [
                f"### {item['id']} - {item['title']}",
                "",
                f"Confidence: **{item['confidence']}**",
                "",
                f"Commits: {', '.join(f'`{value[:12]}`' for value in item['commitHashes'])}",
                "",
                f"Evidence: {', '.join(item['evidenceIds'])}",
                "",
            ]
        )
    lines.extend(["## Capabilities", ""])
    for capability in report["capabilities"]:
        lines.extend(
            [
                f"- **{capability['capability']}** ({capability['confidence']}): "
                f"{capability['rationale']} [Evidence: {', '.join(capability['evidenceIds'])}]",
            ]
        )
    semantic = report.get("semantic")
    if semantic:
        lines.extend(["", "## Semantic Summary", ""])
        for claim in semantic["overallSummary"]:
            lines.append(
                f"- {claim['text']} [Evidence: {', '.join(claim['evidenceIds'])}]"
            )
        if semantic["resumeBullets"]:
            lines.extend(["", "## Resume Candidates", ""])
            for claim in semantic["resumeBullets"]:
                lines.append(
                    f"- {claim['text']} [Evidence: {', '.join(claim['evidenceIds'])}]"
                )
    lines.extend(["", "## Evidence Index", ""])
    for entry in report["evidence"]:
        lines.append(f"- **{entry['id']}**: {entry['summary']}")
    lines.extend(["", "## Limitations", ""])
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    return "\n".join(lines) + "\n"


def _render_project_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    technical = report["technicalSummary"]
    business = report["businessSummary"]
    lines = [
        "# Project Contribution Report",
        "",
        f"- Repository: `{report['repository']}`",
        f"- Git people: {summary['people']}",
        f"- Confirmed / unconfirmed: "
        f"{summary['confirmedPeople']} / {summary['unconfirmedPeople']}",
        f"- Commits: {summary['commits']}",
        f"- Files changed: {summary['filesChanged']}",
        f"- Insertions / deletions: "
        f"{summary['insertions']} / {summary['deletions']}",
        "",
        "## Technical Summary",
        "",
        technical["headline"],
        "",
    ]
    for module in technical["dominantModules"]:
        lines.append(f"- Module `{module['name']}`: {module['commits']} commits")
    if technical["capabilities"]:
        lines.extend(["", "### Capability Signals", ""])
        for capability in technical["capabilities"]:
            lines.append(
                f"- {capability['capability']}: {capability['people']} people "
                f"[Evidence: {_format_refs(capability['evidenceRefs'])}]"
            )
    lines.extend(["", "## Business Summary", "", business["headline"], ""])
    for domain in business["domains"][:30]:
        lines.append(
            f"- `{domain['name']}`: {domain['commits']} commits, "
            f"{domain['people']} people "
            f"[Evidence: {_format_refs(domain['evidenceRefs'])}]"
        )
    if len(business["domains"]) > 30:
        lines.append(
            f"- Showing 30 of {len(business['domains'])} domains; "
            "the JSON report contains the complete list."
        )
    lines.extend(["", "## Contributors", ""])
    for person_report in report["people"]:
        person = person_report["person"]
        marker = "confirmed" if person["confirmed"] else "unconfirmed"
        domains = ", ".join(
            f"`{entry['name']}`"
            for entry in person_report["businessSummary"]["domains"][:5]
        )
        lines.extend(
            [
                f"### {person['name']} <{person['email']}>",
                "",
                f"- Identity: {marker}",
                f"- Commits: {person_report['summary']['commits']}",
                f"- Technical: {person_report['technicalSummary']['headline']}",
                f"- Business: {person_report['businessSummary']['headline']}",
                f"- Domains: {domains or 'none identified'}",
                "",
            ]
        )
    if report["identityWarnings"]:
        lines.extend(["## Identity Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["identityWarnings"])
        lines.append("")
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    lines.extend(f"- {limitation}" for limitation in business["limitations"])
    return "\n".join(lines) + "\n"


def _format_refs(values: list[str], limit: int = 5) -> str:
    visible = values[:limit]
    remaining = len(values) - len(visible)
    suffix = f", ... (+{remaining} more)" if remaining else ""
    return f"{', '.join(visible)}{suffix}"

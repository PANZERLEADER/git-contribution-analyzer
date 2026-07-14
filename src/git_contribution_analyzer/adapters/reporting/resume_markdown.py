from __future__ import annotations

from typing import Any


def render_resume_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Resume Draft: {report['person']['name']}",
        "",
        f"- Target role: {report['targetRole'] or 'not specified'}",
        f"- Language / style: {report['language']} / {report['style']}",
        "",
        "## Technical Summary",
        "",
        report["technicalSummary"]["headline"],
        "",
        "## Business Summary",
        "",
        report["businessSummary"]["headline"],
        "",
        "## Experience Bullets",
        "",
    ]
    for claim in report["experienceBullets"]:
        lines.append(
            f"- {claim['text']} ({claim['claimStrength']}) "
            f"[Evidence: {', '.join(claim['evidenceIds'])}]"
        )
    lines.extend(["", "## Omitted Claims", ""])
    for claim in report["omittedClaims"]:
        lines.append(f"- {claim['candidate']}: {claim['reasonCode']}")
    lines.extend(["", "## Evidence Index", ""])
    for entry in report["evidence"]:
        lines.append(f"- **{entry['id']}**: {entry['summary']}")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {value}" for value in report["limitations"])
    return "\n".join(lines) + "\n"

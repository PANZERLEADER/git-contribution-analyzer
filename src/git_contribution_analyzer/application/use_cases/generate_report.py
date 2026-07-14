from __future__ import annotations

import json
from pathlib import Path

from git_contribution_analyzer.adapters.reporting.markdown import render_markdown
from git_contribution_analyzer.adapters.reporting.work_assessment_csv import (
    render_work_assessment_csv,
)
from git_contribution_analyzer.application.use_cases.get_run import get_run
from git_contribution_analyzer.domain.errors import ReportError


def generate_report(
    path: Path,
    run_id: str,
    report_format: str,
    *,
    include_email: bool = False,
) -> str:
    report = get_run(path, run_id)
    normalized_format = report_format.casefold()
    if normalized_format == "json":
        return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if normalized_format == "markdown":
        return render_markdown(report)
    if normalized_format == "csv":
        return render_work_assessment_csv(report, include_email=include_email)
    raise ReportError(f"Unsupported report format: {report_format}")

from __future__ import annotations

from enum import StrEnum


class RunType(StrEnum):
    ANALYSIS = "ANALYSIS"
    WORK_ASSESSMENT = "WORK_ASSESSMENT"
    WORK_ASSESSMENT_SERIES = "WORK_ASSESSMENT_SERIES"
    RESUME = "RESUME"

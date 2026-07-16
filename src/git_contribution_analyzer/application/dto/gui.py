from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True, kw_only=True)
class AssessmentRequest:
    repository: Path
    person_selectors: tuple[str, ...] = ()
    all_people: bool = False
    exclude_selectors: tuple[str, ...] = ()
    rank_by: tuple[str, ...] = ()
    ranking_config: Path | None = None
    since_text: str | None = None
    until_text: str | None = None
    period: str | None = None
    branch: str | None = None
    release: str | None = None
    scope: str | None = None
    delivery: str | None = None
    time_basis: str = "authored"
    use_llm: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportRequest:
    repository: Path
    run_id: str
    report_format: str
    target: Path
    include_email: bool = False
    overwrite: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentityMapRequest:
    repository: Path
    name: str
    email: str
    person_name: str
    person_email: str


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentityMergeRequest:
    repository: Path
    sources: tuple[str, ...]
    target: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ResumeRequest:
    repository: Path
    person_selector: str
    since_text: str | None = None
    until_text: str | None = None
    branch: str | None = None
    release: str | None = None
    scope: str | None = None
    delivery: str | None = None
    time_basis: str = "LANDED"
    target_role: str = ""
    language: str = "zh-CN"
    style: str = "concise"
    max_bullets: int = 6
    include_pending: bool = False
    use_llm: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class StructuralBaselineRequest:
    repository: Path
    cutoff_text: str | None = None
    branch: str | None = None
    scope: str | None = None
    time_strategy: str = "lifetime"


@dataclass(frozen=True, slots=True, kw_only=True)
class GuiError:
    code: str
    title: str
    message: str
    detail: str = ""
    retryable: bool = False

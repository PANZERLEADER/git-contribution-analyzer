from __future__ import annotations

from typing import Any

from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.llm.registry import build_provider
from git_contribution_analyzer.adapters.workspace.config import load_config
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.ranking_config import load_ranking_config
from git_contribution_analyzer.application.dto.gui import (
    AssessmentRequest,
    ExportRequest,
    GuiError,
    IdentityMapRequest,
    IdentityMergeRequest,
    ResumeRequest,
    StructuralBaselineRequest,
)
from git_contribution_analyzer.application.ports.cancellation import (
    CancellationToken,
    NeverCancelledToken,
)
from git_contribution_analyzer.application.ports.progress import (
    NullProgressReporter,
    ProgressReporter,
)
from git_contribution_analyzer.application.services.time_boundaries import (
    parse_boundaries,
    uses_system_timezone,
)
from git_contribution_analyzer.application.use_cases.assess_work import assess_work
from git_contribution_analyzer.application.use_cases.assess_work_series import assess_work_series
from git_contribution_analyzer.application.use_cases.compare_assessment_runs import (
    compare_assessment_runs,
)
from git_contribution_analyzer.application.use_cases.export_report import export_report
from git_contribution_analyzer.application.use_cases.generate_resume import generate_resume
from git_contribution_analyzer.application.use_cases.get_run import get_run
from git_contribution_analyzer.application.use_cases.get_status import get_status
from git_contribution_analyzer.application.use_cases.index_repository import index_repository
from git_contribution_analyzer.application.use_cases.init_project import init_project
from git_contribution_analyzer.application.use_cases.list_identities import list_identities
from git_contribution_analyzer.application.use_cases.list_providers import list_providers
from git_contribution_analyzer.application.use_cases.list_runs import list_runs
from git_contribution_analyzer.application.use_cases.manage_identity_merges import (
    list_identity_merges,
    merge_identities,
    preview_identity_merge,
    unmerge_identities,
)
from git_contribution_analyzer.application.use_cases.manage_structural_baselines import (
    default_structural_cutoff,
    get_structural_status,
    prune_structural_baselines,
    rebuild_structural_baseline,
    show_structural_baseline,
)
from git_contribution_analyzer.application.use_cases.map_identity import map_identity
from git_contribution_analyzer.application.use_cases.recover_runs import (
    recover_interrupted_runs,
)
from git_contribution_analyzer.application.use_cases.run_doctor import run_doctor
from git_contribution_analyzer.application.use_cases.test_provider import test_provider
from git_contribution_analyzer.domain.errors import (
    ConfigurationError,
    GcaError,
    IdentityResolutionError,
    LlmProviderError,
    NotARepositoryError,
    ReportError,
    WorkspaceError,
)
from git_contribution_analyzer.domain.models.analysis import AnalysisFilters
from git_contribution_analyzer.domain.models.structural_baseline import StructuralTimeStrategy
from git_contribution_analyzer.domain.services.ranking_rules import SUPPORTED_DIMENSIONS

_TIME_BASES = {"AUTHORED", "COMMITTED", "MERGED", "LANDED", "RELEASED"}
_PERIODS = {"week", "month", "quarter"}


class GuiApplicationFacade:
    def open_repository(self, path: Any) -> dict[str, Any]:
        repository = discover_repository(path)
        status = get_status(repository.root)
        if status["workspaceInitialized"] and status["databaseHealthy"]:
            status["recoveredRuns"] = recover_interrupted_runs(repository.root)
        else:
            status["recoveredRuns"] = 0
        return status

    def initialize(
        self,
        path: Any,
        *,
        progress: ProgressReporter | None = None,
        cancellation: CancellationToken | None = None,
    ) -> dict[str, Any]:
        layout = init_project(
            path,
            progress=progress,
            cancellation=cancellation,
        )
        return get_status(layout.repository_root)

    def status(self, path: Any) -> dict[str, Any]:
        return get_status(path)

    def doctor(self, path: Any) -> dict[str, Any]:
        return run_doctor(path)

    def index(
        self,
        path: Any,
        *,
        full_rebuild: bool,
        progress: ProgressReporter | None = None,
        cancellation: CancellationToken | None = None,
    ) -> dict[str, Any]:
        return index_repository(
            path,
            full_rebuild=full_rebuild,
            progress=progress,
            cancellation=cancellation,
        )

    def structural_status(self, path: Any) -> dict[str, Any]:
        return get_structural_status(path)

    def rebuild_structural(
        self,
        request: StructuralBaselineRequest,
        *,
        progress: ProgressReporter | None = None,
        cancellation: CancellationToken | None = None,
    ) -> dict[str, Any]:
        cutoff = (
            parse_boundaries(request.cutoff_text, None)[0]
            if request.cutoff_text
            else default_structural_cutoff()
        )
        if cutoff is None:
            raise ValueError("Structural cutoff is required")
        strategy = StructuralTimeStrategy(request.time_strategy.replace("-", "_").upper())
        return rebuild_structural_baseline(
            request.repository,
            cutoff=cutoff,
            branch=request.branch,
            scope=request.scope,
            time_strategy=strategy,
            progress=progress,
            cancellation=cancellation,
        )

    def show_structural(self, path: Any, baseline_id: str) -> dict[str, Any]:
        return show_structural_baseline(path, baseline_id)

    def prune_structural(self, path: Any, *, keep: int) -> dict[str, int]:
        return prune_structural_baselines(path, keep=keep)

    def list_identities(self, path: Any, *, unresolved_only: bool = False) -> dict[str, Any]:
        return list_identities(path, unresolved_only=unresolved_only)

    def map_identity(self, request: IdentityMapRequest) -> dict[str, Any]:
        return map_identity(
            request.repository,
            name=request.name,
            email=request.email,
            person_name=request.person_name,
            person_email=request.person_email,
        )

    def preview_identity_merge(self, request: IdentityMergeRequest) -> dict[str, Any]:
        return preview_identity_merge(request.repository, request.sources, request.target)

    def merge_identities(self, request: IdentityMergeRequest) -> dict[str, Any]:
        return merge_identities(request.repository, request.sources, request.target)

    def list_identity_merges(self, path: Any, *, status: str = "ALL") -> dict[str, Any]:
        return list_identity_merges(path, status)

    def unmerge_identities(self, path: Any, merge_id: str) -> dict[str, Any]:
        return unmerge_identities(path, merge_id)

    def assess(
        self,
        request: AssessmentRequest,
        *,
        progress: ProgressReporter | None = None,
        cancellation: CancellationToken | None = None,
    ) -> dict[str, Any]:
        self._validate_assessment(request)
        parsed_since, parsed_until = parse_boundaries(
            request.since_text,
            request.until_text,
        )
        time_basis = request.time_basis.upper()
        filters = AnalysisFilters(
            since=parsed_since,
            until=parsed_until,
            branch=request.branch,
            release=request.release,
            scope=request.scope,
            delivery=request.delivery,
            time_basis=time_basis,
            system_timezone=uses_system_timezone(
                request.since_text,
                request.until_text,
            ),
        )
        ranking_config = (
            load_ranking_config(request.ranking_config)
            if request.ranking_config is not None
            else None
        )
        provider = None
        allow_fallback = True
        if request.use_llm:
            repository = discover_repository(request.repository)
            config = load_config(WorkspaceLayout.for_repository(repository.root).config)
            if config.llm.enabled:
                provider = build_provider(config.llm)
            allow_fallback = config.llm.allow_fallback_to_rules

        active_progress = progress or NullProgressReporter()
        active_cancellation = cancellation or NeverCancelledToken()
        rank_by = tuple(value.casefold() for value in request.rank_by)
        if request.period is not None:
            return assess_work_series(
                request.repository,
                period=request.period.casefold(),
                person_selectors=request.person_selectors,
                all_people=request.all_people,
                exclude_selectors=request.exclude_selectors,
                rank_by=rank_by,
                ranking_config=ranking_config,
                filters=filters,
                llm_provider=provider,
                allow_llm_fallback=allow_fallback,
                progress=active_progress,
                cancellation=active_cancellation,
            )
        return assess_work(
            request.repository,
            person_selectors=request.person_selectors,
            all_people=request.all_people,
            exclude_selectors=request.exclude_selectors,
            rank_by=rank_by,
            ranking_config=ranking_config,
            filters=filters,
            llm_provider=provider,
            allow_llm_fallback=allow_fallback,
            progress=active_progress,
            cancellation=active_cancellation,
        )

    def list_runs(self, path: Any) -> dict[str, Any]:
        return list_runs(path)

    def get_run(self, path: Any, run_id: str) -> dict[str, Any]:
        return get_run(path, run_id)

    def compare_runs(self, path: Any, base_run_id: str, target_run_id: str) -> dict[str, Any]:
        if base_run_id == target_run_id:
            raise ValueError("Base and target runs must be different")
        return compare_assessment_runs(path, base_run_id, target_run_id)

    def export_report(self, request: ExportRequest) -> Any:
        return export_report(
            request.repository,
            request.run_id,
            request.report_format,
            request.target,
            include_email=request.include_email,
            overwrite=request.overwrite,
        )

    def generate_resume(self, request: ResumeRequest) -> dict[str, Any]:
        since, until = parse_boundaries(request.since_text, request.until_text)
        filters = AnalysisFilters(
            since=since,
            until=until,
            branch=request.branch,
            release=request.release,
            scope=request.scope,
            delivery=request.delivery,
            time_basis=request.time_basis.upper(),
            system_timezone=uses_system_timezone(request.since_text, request.until_text),
        )
        provider = None
        allow_fallback = True
        if request.use_llm:
            repository = discover_repository(request.repository)
            config = load_config(WorkspaceLayout.for_repository(repository.root).config)
            if config.llm.enabled:
                provider = build_provider(config.llm)
            allow_fallback = config.llm.allow_fallback_to_rules
        return generate_resume(
            request.repository,
            person_selector=request.person_selector,
            filters=filters,
            target_role=request.target_role,
            language=request.language,
            style=request.style,
            max_bullets=request.max_bullets,
            include_pending=request.include_pending,
            llm_provider=provider,
            allow_llm_fallback=allow_fallback,
        )

    def list_providers(self, path: Any) -> dict[str, Any]:
        return list_providers(path)

    def test_provider(self, path: Any) -> dict[str, Any]:
        return test_provider(path)

    @staticmethod
    def map_error(error: Exception) -> GuiError:
        mappings: tuple[tuple[type[Exception], str, str, bool], ...] = (
            (NotARepositoryError, "NOT_A_REPOSITORY", "Not a Git repository", False),
            (WorkspaceError, "WORKSPACE", "Workspace unavailable", True),
            (ConfigurationError, "CONFIGURATION", "Invalid configuration", False),
            (IdentityResolutionError, "IDENTITY", "Identity needs attention", False),
            (ReportError, "REPORT", "Report unavailable", False),
            (LlmProviderError, "PROVIDER", "Provider unavailable", True),
            (ValueError, "VALIDATION", "Check the entered values", False),
        )
        for error_type, code, title, retryable in mappings:
            if isinstance(error, error_type):
                return GuiError(
                    code=code,
                    title=title,
                    message=str(error),
                    retryable=retryable,
                )
        if isinstance(error, GcaError):
            return GuiError(code="APPLICATION", title="Operation failed", message=str(error))
        return GuiError(
            code="UNEXPECTED",
            title="Unexpected error",
            message="The operation could not be completed.",
            detail=str(error),
            retryable=True,
        )

    @staticmethod
    def _validate_assessment(request: AssessmentRequest) -> None:
        if request.person_selectors and request.all_people:
            raise ValueError("person selectors and all_people are mutually exclusive")
        if not request.person_selectors and not request.all_people:
            raise ValueError("Either person selectors or all_people is required")
        if request.exclude_selectors and not request.all_people:
            raise ValueError("exclude selectors require all_people")
        normalized_dimensions = tuple(value.casefold() for value in request.rank_by)
        if len(normalized_dimensions) != len(set(normalized_dimensions)):
            raise ValueError("Ranking dimensions must not be repeated")
        unsupported = set(normalized_dimensions) - set(SUPPORTED_DIMENSIONS)
        if unsupported:
            raise ValueError("Unsupported ranking dimension: " + ", ".join(sorted(unsupported)))
        if request.time_basis.upper() not in _TIME_BASES:
            raise ValueError("Unsupported assessment time basis")
        if request.period is not None and request.period.casefold() not in _PERIODS:
            raise ValueError("Unsupported assessment period")
        if request.period is not None and (
            request.since_text is None or request.until_text is None
        ):
            raise ValueError("Periodic assessment requires since and until")

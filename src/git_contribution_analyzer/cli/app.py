from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
from typing import Annotated, Any

import typer

from git_contribution_analyzer import __version__
from git_contribution_analyzer.adapters.git.repository_discovery import discover_repository
from git_contribution_analyzer.adapters.llm.registry import (
    build_provider,
    provider_descriptors,
)
from git_contribution_analyzer.adapters.outcomes.yaml_loader import load_verified_outcomes
from git_contribution_analyzer.adapters.workspace.config import load_config
from git_contribution_analyzer.adapters.workspace.layout import WorkspaceLayout
from git_contribution_analyzer.adapters.workspace.ranking_config import load_ranking_config
from git_contribution_analyzer.application.dto.results import CommandEnvelope
from git_contribution_analyzer.application.use_cases.analyze_contributions import (
    analyze_contributions,
)
from git_contribution_analyzer.application.use_cases.analyze_project import analyze_project
from git_contribution_analyzer.application.use_cases.assess_work import assess_work
from git_contribution_analyzer.application.use_cases.assess_work_series import assess_work_series
from git_contribution_analyzer.application.use_cases.compare_assessment_runs import (
    compare_assessment_runs,
)
from git_contribution_analyzer.application.use_cases.generate_report import generate_report
from git_contribution_analyzer.application.use_cases.generate_resume import generate_resume
from git_contribution_analyzer.application.use_cases.get_run import get_run
from git_contribution_analyzer.application.use_cases.get_status import get_status
from git_contribution_analyzer.application.use_cases.index_repository import index_repository
from git_contribution_analyzer.application.use_cases.init_project import init_project
from git_contribution_analyzer.application.use_cases.list_identities import list_identities
from git_contribution_analyzer.application.use_cases.list_runs import list_runs
from git_contribution_analyzer.application.use_cases.manage_identity_merges import (
    list_identity_merges,
    merge_identities,
    preview_identity_merge,
    unmerge_identities,
)
from git_contribution_analyzer.application.use_cases.map_identity import map_identity
from git_contribution_analyzer.application.use_cases.run_doctor import run_doctor
from git_contribution_analyzer.application.use_cases.uninit_project import uninit_project
from git_contribution_analyzer.cli.exit_codes import ExitCode
from git_contribution_analyzer.cli.output import emit_human, emit_json
from git_contribution_analyzer.domain.errors import (
    ConfigurationError,
    IdentityResolutionError,
    LlmProviderError,
    NotARepositoryError,
    ReportError,
    WorkspaceError,
)
from git_contribution_analyzer.domain.models.analysis import AnalysisFilters
from git_contribution_analyzer.domain.services.ranking_rules import SUPPORTED_DIMENSIONS

app = typer.Typer(
    name="gca",
    help="Git contribution analysis with deterministic evidence and pluggable LLM providers.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
identities_app = typer.Typer(help="Inspect and confirm Git author identities.")
runs_app = typer.Typer(help="Inspect persisted deterministic analysis runs.")
providers_app = typer.Typer(help="Inspect and test pluggable LLM providers.")
app.add_typer(identities_app, name="identities")
app.add_typer(runs_app, name="runs")
app.add_typer(providers_app, name="providers")
BOUNDARY_HELP = "Inclusive ISO date/time; values without an offset use the system time zone."


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit(code=ExitCode.SUCCESS)


@app.callback()
def root(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = None,
) -> None:
    """Git contribution analysis CLI."""


def _exit_for_error(error: Exception) -> None:
    if isinstance(error, NotARepositoryError):
        emit_human(f"Error: {error}")
        raise typer.Exit(code=ExitCode.NOT_A_REPOSITORY) from error
    if isinstance(error, (WorkspaceError, ConfigurationError)):
        emit_human(f"Error: {error}")
        raise typer.Exit(code=ExitCode.WORKSPACE_ERROR) from error
    if isinstance(error, IdentityResolutionError):
        emit_human(f"Error: {error}")
        raise typer.Exit(code=ExitCode.IDENTITY_AMBIGUOUS) from error
    if isinstance(error, ReportError):
        emit_human(f"Error: {error}")
        raise typer.Exit(code=ExitCode.REPORT_ERROR) from error
    if isinstance(error, LlmProviderError):
        emit_human(f"Error: {error}")
        raise typer.Exit(code=ExitCode.PROVIDER_ERROR) from error
    raise error


@app.command("init")
def init_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
) -> None:
    """Initialize a repository-local GCA workspace."""
    try:
        layout = init_project(path)
    except Exception as exc:
        _exit_for_error(exc)
        return
    emit_human(f"Initialized GCA workspace: {layout.root}")


@app.command("status")
def status_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Output versioned JSON.")
    ] = False,
) -> None:
    """Show repository and workspace status."""
    try:
        data = get_status(path)
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="status", data=data))
        return
    emit_human(f"Repository: {data['repository']}")
    emit_human(f"Workspace initialized: {str(data['workspaceInitialized']).lower()}")
    emit_human(f"Database healthy: {str(data['databaseHealthy']).lower()}")
    emit_human(f"Index status: {data['indexStatus']}")


def _run_index_command(path: Path, *, full_rebuild: bool, json_output: bool) -> None:
    try:
        data = index_repository(path, full_rebuild=full_rebuild)
    except Exception as exc:
        _exit_for_error(exc)
        return
    command_name = "index" if full_rebuild else "sync"
    if json_output:
        emit_json(CommandEnvelope(command=command_name, data=data))
        return
    emit_human(
        f"Indexed commits: {data['indexedCommits']} "
        f"(new: {data['newCommits']}, identities: {data['identities']})"
    )


@app.command("index")
def index_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Output versioned JSON.")
    ] = False,
) -> None:
    """Rebuild the Git history index from configured refs."""
    _run_index_command(path, full_rebuild=True, json_output=json_output)


@app.command("sync")
def sync_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Output versioned JSON.")
    ] = False,
) -> None:
    """Incrementally synchronize new commits and changed refs."""
    _run_index_command(path, full_rebuild=False, json_output=json_output)


@app.command("analyze")
def analyze_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    person: Annotated[str, typer.Option("--person", help="Confirmed person name or email.")] = "",
    all_people: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Analyze every Git person, including unconfirmed identities.",
        ),
    ] = False,
    since: Annotated[str | None, typer.Option("--since", help=BOUNDARY_HELP)] = None,
    until: Annotated[str | None, typer.Option("--until", help=BOUNDARY_HELP)] = None,
    branch: Annotated[str | None, typer.Option("--branch", help="Reachable branch ref.")] = None,
    release: Annotated[str | None, typer.Option("--release", help="Release tag.")] = None,
    scope: Annotated[str | None, typer.Option("--scope", help="Repository path prefix.")] = None,
    delivery: Annotated[
        str | None,
        typer.Option(
            "--delivery",
            help="AUTHORED_ONLY, LANDED, RELEASED, REVERTED, or DELIVERED.",
        ),
    ] = None,
    no_llm: Annotated[
        bool, typer.Option("--no-llm", help="Disable semantic LLM analysis.")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output versioned JSON.")
    ] = False,
) -> None:
    """Analyze deterministic Git contribution evidence for one or all people."""
    if person and all_people:
        raise typer.BadParameter("--person and --all are mutually exclusive")
    if not person and not all_people:
        raise typer.BadParameter("Either --person or --all is required")
    if all_people and not no_llm:
        raise typer.BadParameter("--all currently requires --no-llm")
    try:
        repository = discover_repository(path)
        config = load_config(WorkspaceLayout.for_repository(repository.root).config)
        parsed_since, parsed_until = _parse_boundaries(since, until)
        filters = AnalysisFilters(
            since=parsed_since,
            until=parsed_until,
            branch=branch,
            release=release,
            scope=scope,
            delivery=delivery,
            system_timezone=_uses_system_timezone(since, until),
        )
        if all_people:
            report = analyze_project(path, filters=filters)
        else:
            provider = None
            if config.llm.enabled and not no_llm:
                provider = build_provider(config.llm)
            report = analyze_contributions(
                path,
                person_selector=person,
                filters=filters,
                llm_provider=provider,
                allow_llm_fallback=config.llm.allow_fallback_to_rules,
            )
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="analyze", data=report, warnings=report["warnings"]))
        return
    if report["reportType"] == "PROJECT":
        emit_human(
            f"Project analysis run {report['run']['id']}: "
            f"{report['summary']['people']} people, "
            f"{report['summary']['commits']} commits"
        )
    else:
        emit_human(
            f"Analysis run {report['run']['id']}: "
            f"{report['summary']['commits']} commits, "
            f"{len(report['contributionItems'])} contribution items"
        )


@app.command("assess")
def assess_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    person: Annotated[
        list[str] | None,
        typer.Option("--person", help="Confirmed person ID, name, or email. Repeatable."),
    ] = None,
    all_people: Annotated[
        bool, typer.Option("--all", help="Assess every Git person independently.")
    ] = False,
    exclude_person: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude-person",
            help="Exclude a person ID, name, or email from --all. Repeatable.",
        ),
    ] = None,
    rank_by: Annotated[
        list[str] | None,
        typer.Option(
            "--rank-by",
            help="Rank by workload, difficulty, or delivery. Repeatable.",
        ),
    ] = None,
    ranking_config: Annotated[
        Path | None,
        typer.Option(
            "--ranking-config",
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="YAML weights for an optional composite score.",
        ),
    ] = None,
    since: Annotated[str | None, typer.Option("--since", help=BOUNDARY_HELP)] = None,
    until: Annotated[str | None, typer.Option("--until", help=BOUNDARY_HELP)] = None,
    branch: Annotated[str | None, typer.Option("--branch", help="Reachable branch ref.")] = None,
    release: Annotated[str | None, typer.Option("--release", help="Release tag.")] = None,
    scope: Annotated[str | None, typer.Option("--scope", help="Repository path prefix.")] = None,
    delivery: Annotated[
        str | None, typer.Option("--delivery", help="Delivery status filter.")
    ] = None,
    time_basis: Annotated[
        str,
        typer.Option(
            "--time-basis",
            help="Assessment time: authored, committed, merged, landed, or released.",
        ),
    ] = "authored",
    period: Annotated[
        str | None,
        typer.Option("--period", help="Split into calendar week, month, or quarter."),
    ] = None,
    no_llm: Annotated[
        bool, typer.Option("--no-llm", help="Disable optional explanations.")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output versioned JSON.")] = False,
) -> None:
    """Assess completed workload and deterministic engineering difficulty."""
    person_selectors = tuple(person or ())
    exclude_selectors = tuple(exclude_person or ())
    ranking_dimensions = tuple(value.casefold() for value in (rank_by or ()))
    if person_selectors and all_people:
        raise typer.BadParameter("--person and --all are mutually exclusive")
    if not person_selectors and not all_people:
        raise typer.BadParameter("Either --person or --all is required")
    if exclude_selectors and not all_people:
        raise typer.BadParameter("--exclude-person requires --all")
    if len(ranking_dimensions) != len(set(ranking_dimensions)):
        raise typer.BadParameter("--rank-by dimensions must not be repeated")
    unsupported_dimensions = set(ranking_dimensions) - set(SUPPORTED_DIMENSIONS)
    if unsupported_dimensions:
        raise typer.BadParameter(
            "Unsupported --rank-by dimension: " + ", ".join(sorted(unsupported_dimensions))
        )
    normalized_time_basis = time_basis.upper()
    if normalized_time_basis not in {"AUTHORED", "COMMITTED", "MERGED", "LANDED", "RELEASED"}:
        raise typer.BadParameter("Unsupported --time-basis")
    normalized_period = period.casefold() if period else None
    if normalized_period not in {None, "week", "month", "quarter"}:
        raise typer.BadParameter("Unsupported --period")
    if normalized_period is not None and (since is None or until is None):
        raise typer.BadParameter("--period requires both --since and --until")
    try:
        repository = discover_repository(path)
        config = load_config(WorkspaceLayout.for_repository(repository.root).config)
        active_ranking_config = (
            load_ranking_config(ranking_config) if ranking_config is not None else None
        )
        provider = (
            build_provider(config.llm) if config.llm.enabled and not no_llm else None
        )
        parsed_since, parsed_until = _parse_boundaries(since, until)
        filters = AnalysisFilters(
            since=parsed_since,
            until=parsed_until,
            branch=branch,
            release=release,
            scope=scope,
            delivery=delivery,
            time_basis=normalized_time_basis,
            system_timezone=_uses_system_timezone(since, until),
        )
        if normalized_period is not None:
            report = assess_work_series(
                path,
                period=normalized_period,
                person_selectors=person_selectors,
                all_people=all_people,
                exclude_selectors=exclude_selectors,
                rank_by=ranking_dimensions,
                ranking_config=active_ranking_config,
                filters=filters,
                llm_provider=provider,
                allow_llm_fallback=config.llm.allow_fallback_to_rules,
            )
        else:
            report = assess_work(
                path,
                person_selectors=person_selectors,
                all_people=all_people,
                exclude_selectors=exclude_selectors,
                rank_by=ranking_dimensions,
                ranking_config=active_ranking_config,
                filters=filters,
                llm_provider=provider,
                allow_llm_fallback=config.llm.allow_fallback_to_rules,
            )
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="assess", data=report, warnings=report["warnings"]))
        return
    if report["reportType"] == "WORK_ASSESSMENT_SERIES":
        emit_human(
            f"Assessment series {report['run']['id']}: {len(report['periods'])} periods"
        )
        return
    workload = report["workloadSummary"]
    emit_human(
        f"Assessment run {report['run']['id']}: {workload['completedItems']} completed, "
        f"{workload['pendingItems']} pending items"
    )


@app.command("resume")
def resume_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    person: Annotated[str, typer.Option("--person", help="Confirmed person name or email.")] = "",
    since: Annotated[str | None, typer.Option("--since", help=BOUNDARY_HELP)] = None,
    until: Annotated[str | None, typer.Option("--until", help=BOUNDARY_HELP)] = None,
    branch: Annotated[str | None, typer.Option("--branch", help="Reachable branch ref.")] = None,
    release: Annotated[str | None, typer.Option("--release", help="Release tag.")] = None,
    scope: Annotated[str | None, typer.Option("--scope", help="Repository path prefix.")] = None,
    target_role: Annotated[str, typer.Option("--target-role", help="Target role context.")] = "",
    language: Annotated[str, typer.Option("--language", help="zh-CN or en-US.")] = "zh-CN",
    style: Annotated[str, typer.Option("--style", help="concise, star, or xyz.")] = "concise",
    max_bullets: Annotated[int, typer.Option("--max-bullets", min=1, max=20)] = 6,
    include_pending: Annotated[
        bool, typer.Option("--include-pending", help="Include clearly marked pending work.")
    ] = False,
    verified_outcomes: Annotated[
        Path | None,
        typer.Option("--verified-outcomes", exists=True, dir_okay=False),
    ] = None,
    no_llm: Annotated[bool, typer.Option("--no-llm", help="Use conservative templates.")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output versioned JSON.")] = False,
) -> None:
    """Generate evidence-backed resume candidates for one confirmed person."""
    if not person:
        raise typer.BadParameter("--person is required")
    try:
        repository = discover_repository(path)
        config = load_config(WorkspaceLayout.for_repository(repository.root).config)
        provider = (
            build_provider(config.llm) if config.llm.enabled and not no_llm else None
        )
        outcomes = (
            load_verified_outcomes(verified_outcomes) if verified_outcomes is not None else ()
        )
        parsed_since, parsed_until = _parse_boundaries(since, until)
        report = generate_resume(
            path,
            person_selector=person,
            filters=AnalysisFilters(
                since=parsed_since,
                until=parsed_until,
                branch=branch,
                release=release,
                scope=scope,
                system_timezone=_uses_system_timezone(since, until),
            ),
            target_role=target_role,
            language=language,
            style=style,
            max_bullets=max_bullets,
            include_pending=include_pending,
            outcomes=outcomes,
            llm_provider=provider,
            allow_llm_fallback=config.llm.allow_fallback_to_rules,
        )
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="resume", data=report, warnings=report["warnings"]))
        return
    emit_human(
        f"Resume run {report['run']['id']}: {len(report['experienceBullets'])} candidates"
    )



def _parse_boundary(value: str | None, *, end_of_day: bool) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid ISO date/time: {value}") from exc
    if parsed.tzinfo is None:
        if "T" not in value and end_of_day:
            parsed = datetime.combine(parsed.date(), time.max)
        parsed = _localize_system_time(parsed)
    return parsed


def _localize_system_time(value: datetime) -> datetime:
    return value.astimezone()


def _uses_system_timezone(*values: str | None) -> bool:
    supplied = tuple(value for value in values if value is not None)
    return bool(supplied) and all(
        datetime.fromisoformat(value).tzinfo is None for value in supplied
    )


def _parse_boundaries(
    since: str | None, until: str | None
) -> tuple[datetime | None, datetime | None]:
    parsed_since = _parse_boundary(since, end_of_day=False)
    parsed_until = _parse_boundary(until, end_of_day=True)
    if parsed_since is not None and parsed_until is not None and parsed_since > parsed_until:
        raise typer.BadParameter("--since must be earlier than or equal to --until")
    return parsed_since, parsed_until


@identities_app.command("list")
def identities_list_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    unresolved: Annotated[
        bool, typer.Option("--unresolved", help="Show only unresolved persons.")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output versioned JSON.")
    ] = False,
) -> None:
    """List normalized persons and their Git aliases."""
    try:
        data = list_identities(path, unresolved_only=unresolved)
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="identities.list", data=data))
        return
    for person in data["persons"]:
        if not person["active"]:
            marker = f"merged -> {person['mergedIntoPersonId']}"
        else:
            marker = "confirmed" if person["confirmed"] else "unresolved"
        emit_human(f"{person['name']} <{person['email']}> [{marker}]")
        for alias in person["aliases"]:
            emit_human(f"  - {alias['name']} <{alias['email']}> ({alias['source']})")


@identities_app.command("map")
def identities_map_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    name: Annotated[str, typer.Option("--name", help="Existing Git author name.")] = "",
    email: Annotated[str, typer.Option("--email", help="Existing Git author email.")] = "",
    person_name: Annotated[
        str, typer.Option("--person-name", help="Canonical person name.")
    ] = "",
    person_email: Annotated[
        str, typer.Option("--person-email", help="Canonical person email.")
    ] = "",
    json_output: Annotated[
        bool, typer.Option("--json", help="Output versioned JSON.")
    ] = False,
) -> None:
    """Confirm an alias mapping to a canonical person."""
    if not all((name, email, person_name, person_email)):
        raise typer.BadParameter("All identity mapping options are required")
    try:
        data = map_identity(
            path,
            name=name,
            email=email,
            person_name=person_name,
            person_email=person_email,
        )
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="identities.map", data=data))
        return
    person = data["person"]
    emit_human(f"Mapped to {person['name']} <{person['email']}>")


@identities_app.command("merge")
def identities_merge_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    source: Annotated[
        list[str] | None,
        typer.Option("--source", help="Source person selector. Repeatable."),
    ] = None,
    target: Annotated[str, typer.Option("--target", help="Target person selector.")] = "",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Preview without changing identities.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Confirm the merge operation.")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output versioned JSON.")] = False,
) -> None:
    """Preview or execute a reversible identity merge."""
    sources = tuple(source or ())
    if not sources or not target:
        raise typer.BadParameter("--source and --target are required")
    if dry_run == yes:
        raise typer.BadParameter("Choose exactly one of --dry-run or --yes")
    try:
        data = (
            preview_identity_merge(path, sources, target)
            if dry_run
            else merge_identities(path, sources, target)
        )
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="identities.merge", data=data))
        return
    action = "preview" if dry_run else f"merge {data['mergeId']}"
    emit_human(
        f"Identity {action}: {len(data['sources'])} source person(s) -> "
        f"{data['target']['name']}"
    )


@identities_app.command("merges")
def identities_merges_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    status: Annotated[
        str, typer.Option("--status", help="ACTIVE, REVERTED, or ALL.")
    ] = "ALL",
    json_output: Annotated[bool, typer.Option("--json", help="Output versioned JSON.")] = False,
) -> None:
    """List reversible identity merge events."""
    normalized_status = status.upper()
    if normalized_status not in {"ACTIVE", "REVERTED", "ALL"}:
        raise typer.BadParameter("--status must be ACTIVE, REVERTED, or ALL")
    try:
        data = list_identity_merges(path, normalized_status)
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="identities.merges", data=data))
        return
    for event in data["merges"]:
        emit_human(
            f"{event['mergeId']} [{event['status']}] -> {event['targetPersonId']}"
        )


@identities_app.command("unmerge")
def identities_unmerge_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    merge_id: Annotated[str, typer.Option("--merge-id", help="Merge event ID.")] = "",
    yes: Annotated[bool, typer.Option("--yes", help="Confirm the unmerge operation.")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output versioned JSON.")] = False,
) -> None:
    """Reverse an active identity merge event."""
    if not merge_id or not yes:
        raise typer.BadParameter("--merge-id and --yes are required")
    try:
        data = unmerge_identities(path, merge_id)
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="identities.unmerge", data=data))
        return
    emit_human(f"Identity merge {merge_id} reverted")


@runs_app.command("list")
def runs_list_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Output versioned JSON.")
    ] = False,
) -> None:
    """List persisted analysis runs."""
    try:
        data = list_runs(path)
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="runs.list", data=data))
        return
    for run in data["runs"]:
        emit_human(
            f"{run['id']} [{run['runType']}/{run['status']}] {run['startedAt']}"
        )


@runs_app.command("compare")
def runs_compare_command(
    base_run_id: Annotated[str, typer.Argument(help="Baseline work assessment run ID.")],
    target_run_id: Annotated[str, typer.Argument(help="Target work assessment run ID.")],
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    json_output: Annotated[bool, typer.Option("--json", help="Output versioned JSON.")] = False,
) -> None:
    """Compare two persisted work assessment runs."""
    try:
        data = compare_assessment_runs(path, base_run_id, target_run_id)
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="runs.compare", data=data, warnings=data["warnings"]))
        return
    changes = data["changes"]
    emit_human(
        f"Assessment comparison {base_run_id} -> {target_run_id}: "
        f"completed items {changes['completedItems']['absolute']:+d}"
    )


@runs_app.command("show")
def runs_show_command(
    run_id: Annotated[str, typer.Argument(help="Analysis run ID or 'latest'.")],
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Output versioned JSON.")
    ] = False,
) -> None:
    """Show a persisted completed analysis run."""
    try:
        data = get_run(path, run_id)
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="runs.show", data=data))
        return
    emit_human(f"Run: {data['run']['id']} [{data['run']['status']}]")
    report_type = data.get("reportType")
    if report_type in ("PERSON", "PROJECT"):
        emit_human(f"Commits: {data['summary']['commits']}")
    elif report_type == "WORK_ASSESSMENT":
        emit_human(f"Completed items: {data['workloadSummary']['completedItems']}")
    elif report_type == "WORK_ASSESSMENT_SERIES":
        emit_human(f"Assessment periods: {len(data['periods'])}")
    elif report_type == "RESUME":
        emit_human(f"Resume candidates: {len(data['experienceBullets'])}")


@providers_app.command("list")
def providers_list_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Output versioned JSON.")
    ] = False,
) -> None:
    """List built-in providers and the repository's selected provider."""
    try:
        repository = discover_repository(path)
        config = load_config(WorkspaceLayout.for_repository(repository.root).config)
    except Exception as exc:
        _exit_for_error(exc)
        return
    providers: list[dict[str, Any]] = [
        {
            "id": descriptor.provider_id,
            "localExecution": descriptor.local_execution,
            "requiresApiKey": descriptor.requires_api_key,
            "selected": descriptor.provider_id == config.llm.provider,
        }
        for descriptor in provider_descriptors()
    ]
    data = {
        "selected": config.llm.provider,
        "enabled": config.llm.enabled,
        "providers": providers,
    }
    if json_output:
        emit_json(CommandEnvelope(command="providers.list", data=data))
        return
    for provider in providers:
        marker = "selected" if provider["selected"] else "available"
        locality = "local" if provider["localExecution"] else "remote"
        emit_human(f"{provider['id']} [{marker}, {locality}]")


@providers_app.command("test")
def providers_test_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Output versioned JSON.")
    ] = False,
) -> None:
    """Test the selected provider's configuration and health endpoint."""
    try:
        repository = discover_repository(path)
        config = load_config(WorkspaceLayout.for_repository(repository.root).config)
        provider = build_provider(config.llm)
        healthy = provider.health_check()
    except Exception as exc:
        _exit_for_error(exc)
        return
    data = {
        "provider": provider.provider_id,
        "model": provider.model,
        "healthy": healthy,
        "localExecution": provider.capabilities.local_execution,
    }
    if json_output:
        emit_json(CommandEnvelope(command="providers.test", data=data, success=healthy))
    else:
        emit_human(f"Provider {provider.provider_id}: {'healthy' if healthy else 'unhealthy'}")
    if not healthy:
        raise typer.Exit(code=ExitCode.PROVIDER_ERROR)


@app.command("report")
def report_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    run_id: Annotated[str, typer.Option("--run", help="Analysis run ID or 'latest'.")] = "latest",
    report_format: Annotated[
        str, typer.Option("--format", help="Report format: markdown, json, or csv.")
    ] = "markdown",
    output: Annotated[
        Path | None, typer.Option("--output", help="Write report to this file.")
    ] = None,
    include_email: Annotated[
        bool, typer.Option("--include-email", help="Include email in CSV output.")
    ] = False,
) -> None:
    """Rebuild a Markdown, JSON, or CSV report from a persisted analysis run."""
    try:
        rendered = generate_report(
            path, run_id, report_format, include_email=include_email
        )
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            newline = "" if report_format.casefold() == "csv" else "\n"
            output.write_text(rendered, encoding="utf-8", newline=newline)
            emit_human(f"Report written: {output.resolve()}")
            return
    except Exception as exc:
        _exit_for_error(exc)
        return
    typer.echo(rendered, nl=False)


@app.command("doctor")
def doctor_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    json_output: Annotated[
        bool, typer.Option("--json", help="Output versioned JSON.")
    ] = False,
) -> None:
    """Diagnose Git, workspace, database, and lock health."""
    try:
        data = run_doctor(path)
    except Exception as exc:
        _exit_for_error(exc)
        return
    if json_output:
        emit_json(CommandEnvelope(command="doctor", data=data, success=bool(data["healthy"])))
        if not data["healthy"]:
            raise typer.Exit(code=ExitCode.WORKSPACE_ERROR)
        return
    for check in data["checks"]:
        marker = "OK" if check["healthy"] else "FAIL"
        emit_human(f"[{marker}] {check['name']}: {check['detail']}")
    if not data["healthy"]:
        raise typer.Exit(code=ExitCode.WORKSPACE_ERROR)


@app.command("uninit")
def uninit_command(
    path: Annotated[Path, typer.Argument(exists=True, file_okay=False)] = Path("."),
    yes: Annotated[
        bool, typer.Option("--yes", help="Delete without interactive confirmation.")
    ] = False,
) -> None:
    """Remove the repository-local GCA workspace."""
    if not yes and not typer.confirm("Remove the .gca workspace?"):
        raise typer.Abort()
    try:
        removed = uninit_project(path)
    except Exception as exc:
        _exit_for_error(exc)
        return
    emit_human("Removed GCA workspace." if removed else "GCA workspace was not initialized.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()

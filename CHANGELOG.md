# Changelog

## Unreleased

## 0.5.1 - 2026-07-17

- Apply additive SQLite migrations when `status`, `doctor`, `sync` or `index` opens an existing
  workspace, and refresh workspace tool-version metadata after a successful index.
- Preserve confirmed identities and active reversible identity merges across incremental sync and
  full index rebuilds.
- Build combined GitHub Release notes with explicit UTF-8 decoding and reject invalid replacement
  characters before publication.
- Use tag-pinned absolute English and Simplified Chinese links in release notes so links remain
  valid both in the repository and on GitHub Release pages.

## 0.5.0 - 2026-07-17

- Add observation-only historical structural baselines with strict cutoffs, lifetime/rolling/dual
  windows, hotspot percentiles, hub-aware coupling metrics and content-addressed identities.
- Persist structural commit/file/edge occurrences and immutable baseline caches in SQLite, with
  `structural status/rebuild/show/prune`, repository status/doctor diagnostics and GUI controls.
- Publish repository status as `status/v2` while preserving the original `status/v1` contract, and
  retain sanitized BUILDING/FAILED/CANCELLED/STALE structural diagnostics without exposing paths.
- Add the conservative `community-baseline-v1` workspace profile with complete cache fingerprinting,
  explicit hub filtering and automatic difficulty promotion fixed to `false`.
- Preserve `difficulty-rules-v1` and all assessment/ranking/resume behavior; human calibration and
  repository-disjoint holdout are required only before a future automatic promotion rule. No Forge
  API, Hercules runtime, project-health or AI-provenance dependency is introduced.
- Add a deterministic public-repository calibration package builder with 80-item stratified
  sampling, three time-strategy evidence views, independent Reviewer A/B sheets and adjudication
  templates while keeping holdout repositories untouched.
- Treat Gitlink/submodule changes as external binary context so repositories with valid missing
  submodule objects can be indexed without weakening ordinary Blob validation.

## 0.4.1 - 2026-07-15

- Keep CLI standalone artifacts free of PySide6, shiboken6 and QML resources when GUI build
  dependencies are installed in the same release environment.
- Verify the final CLI PyInstaller archive before release and fail if Qt runtime entries are found.
- Read the macOS GUI bundle version from project metadata instead of hard-coding it in the spec.

## 0.4.0 - 2026-07-15

- Add an optional PySide6/QML desktop application for Windows, Linux and macOS.
- Add background repository task scheduling, progress, cooperative cancellation and run recovery.
- Add GUI views for assessments, trends, identities, Evidence, historical comparisons and exports.
- Share system-time-zone boundary validation between the CLI and GUI application facade.
- Add GUI PyInstaller artifacts, smoke tests and third-party Qt notices.

## 0.3.0 - 2026-07-15

- Add calendar week/month/quarter assessment series with persisted child runs, workload and
  difficulty trends, period-over-period changes, and year-over-year changes when the matching
  prior-year period is present.
- Add authored, committed, merged, landed, and released assessment time bases derived from Git
  timestamps, first-parent integration points, and release tag creation times.
- Add `gca runs compare` for deterministic comparison of two historical work assessment runs.
- Reject reversed `--since`/`--until` boundaries, interpret offset-free inputs in the system time
  zone, preserve explicit offsets, and normalize indexed Git timestamps and SQLite query bindings
  to UTC. Existing workspaces should run `gca index` once after upgrading.

## 0.2.0 - 2026-07-15

- Add repeatable person selection, all-scope exclusions, reversible identity
  merge/unmerge events, deterministic workload/difficulty/delivery dense ranking, optional
  Decimal-based weighted composite scores, and persisted UTF-8 BOM CSV export.
- Add `work-assessment/v2` while preserving v1 JSON and Markdown replay compatibility.
- Default team assessment to active, confirmed `HUMAN` identities and record explicit exclusion
  reasons; keep ranking data out of LLM prompts and email out of CSV unless explicitly requested.
- Make `identities map` create reversible `ALIAS_MAP` events while preserving its CLI contract.
- Add Simplified Chinese documentation for installation, CLI usage, architecture, data model,
  assessment/resume methodology, privacy, LLM Providers, golden tests, and the 0.1.0 release.

## 0.1.0 - 2026-07-15

- Add a generated golden Git repository and complete analyze/assess/resume/run/report E2E lifecycle
  covering merge, authored-only work, duplicate patches, revert, migration, docs, generated files,
  binary files, lockfiles, release tags, and Unicode paths.
- Expand the Windows/Linux/macOS CI gate with core-layer coverage, package build, isolated wheel
  installation, repository lifecycle verification, and Git-history credential scanning.
- Add a three-platform PyInstaller and pipx release workflow with standalone artifact smoke tests.
- Make human and JSON CLI output safe on non-UTF-8 Windows stdout while preserving JSON Unicode
  semantics.
- Add architecture, data model, CLI, installation, methodology, privacy, golden dataset, release,
  performance, and security audit documentation for the 0.1.0 release candidate.

- Add immutable, content-addressed `EvidenceSnapshot` values shared by analysis, work assessment,
  and resume generation.
- Add explicit `ANALYSIS`, `WORK_ASSESSMENT`, and `RESUME` run types, optional parent lineage,
  and the additive `0005_run_types` migration.
- Add deterministic workload completion buckets, effective size bands, difficulty dimensions,
  Evidence references, confidence, and gaps without employee totals or rankings.
- Add `gca assess --person|--all`, independent assessment JSON/Markdown reports, and optional
  `assessment-explanation-v1` Provider output.
- Add `gca resume --person` with confirmed identity enforcement, conservative no-LLM templates,
  claim-strength ceilings, verified outcome YAML, and independent JSON/Markdown reports.
- Add independent `resume-v1` Prompt/Schema validation with Item/Evidence/outcome allowlists and
  rejection of unsupported result numbers or ownership claims.
- Mark legacy `semantic.resumeBullets` deprecated while preserving 1.x read compatibility.

- Establish the CLI-first project and workspace lifecycle.
- Add full and incremental Git indexing with refs, commits, parents, and file changes.
- Add deterministic identity normalization using exact email, `.mailmap`, and manual mappings.
- Add delivery classification for target-branch reachability, release tags, patch duplicates,
  and reverts.
- Batch Git metadata, patch ID, ref, reachability, and PyDriller operations for large repositories.
- Add deterministic no-LLM analysis with date, branch, release, scope, and delivery filters.
- Add issue/scope/module Contribution Item clustering with stable Evidence references.
- Add evidence-backed capability rules without employee scoring or unsupported outcome claims.
- Add persisted AnalysisRun state, replayable runs, and Markdown/JSON report rendering.
- Add versioned analysis and report JSON Schemas and the `0003_analysis` migration.
- Add a vendor-neutral `LlmProvider` SPI with Mock, OpenAI-compatible, Anthropic, and Ollama
  adapters.
- Add evidence-constrained semantic summaries, capability explanations, and resume candidates.
- Add timeout, authentication, rate-limit, server retry, and one-shot JSON repair contracts.
- Add `providers list/test`, environment-only secret resolution, and repository LLM settings.
- Add `0004_llm_audit`, deterministic request hashing, response caching, and invocation auditing.
- Add `COMPLETED`, `PARTIAL`, and failed Provider paths with stable exit code `6`.
- Add `codex-cli` and `claude-cli` Providers for reusing authenticated local coding CLIs or their
  configured non-official model gateways without repository access.
- Add deterministic `analyze --all --no-llm` project reports covering every indexed Git identity,
  with explicit warnings for identities that have not been confirmed.
- Add separate technical and business summaries to person and project reports, with business
  domains derived from commit scopes, issue keys, and conservative module clusters.
- Add isolated command execution, stdin prompts, structured CLI output, native Windows Codex
  discovery, tool/MCP disabling, timeout mapping, and configurable executable paths.

# Changelog

## Unreleased

- Add calendar week/month/quarter assessment series with persisted child runs, workload and
  difficulty trends, period-over-period changes, and year-over-year changes when the matching
  prior-year period is present.
- Add authored, committed, merged, landed, and released assessment time bases derived from Git
  timestamps, first-parent integration points, and release tag creation times.
- Add `gca runs compare` for deterministic comparison of two historical work assessment runs.
- Reject reversed `--since`/`--until` boundaries and normalize indexed Git timestamps and CLI
  boundaries to UTC. Existing workspaces should run `gca index` once after upgrading.

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

# Git Contribution Analyzer

[简体中文](README.zh-CN.md)

GCA is a local, evidence-backed Git contribution analysis tool with a stable `gca` CLI and an
optional cross-platform `gca-gui` desktop application. It separates deterministic repository facts
from rule-based and LLM-assisted interpretation.

The 0.4.1 release includes a PySide6/QML desktop workbench for repository lifecycle, assessments,
trends, identities, Evidence, historical comparisons, exports, resumes and Provider health checks.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\gca.exe --help
```

Install and run the optional desktop application:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,gui]"
.\.venv\Scripts\gca-gui.exe
```

## Current CLI

```powershell
# Initialize a repository-local workspace and build the first Git index.
gca init D:\path\to\repository

# Rebuild the deterministic Git index or synchronize new commits and changed refs.
gca index D:\path\to\repository --json
gca sync D:\path\to\repository --json

# Inspect normalized identities and confirm an alias mapping.
gca identities list D:\path\to\repository --json
gca identities map D:\path\to\repository `
  --name "Old Name" `
  --email "old@example.com" `
  --person-name "Canonical Name" `
  --person-email "canonical@example.com" `
  --json

# Read workspace and index health as versioned JSON.
gca status D:\path\to\repository --json
gca doctor D:\path\to\repository --json

# Generate deterministic contribution evidence without an LLM.
gca analyze D:\path\to\repository `
  --person alice@example.com `
  --since 2026-01-01 `
  --until 2026-06-30 `
  --no-llm `
  --json

# Analyze every indexed Git identity, including identities not yet confirmed.
gca analyze D:\path\to\repository --all --no-llm --json

# Assess completed workload and deterministic engineering difficulty.
gca assess D:\path\to\repository `
  --person alice@example.com `
  --person bob@example.com `
  --since 2026-01-01 `
  --no-llm `
  --json
gca assess D:\path\to\repository --all `
  --exclude-person ci@example.com `
  --no-llm --json

# Build calendar month trends; week and quarter are also supported.
gca assess D:\path\to\repository --all `
  --since 2025-01-01 --until 2026-12-31 `
  --period month --time-basis landed --no-llm --json

# Compare two historical work assessment runs.
gca runs compare <base-run-id> <target-run-id> D:\path\to\repository --json

# Generate evidence-backed resume candidates for one confirmed person.
gca resume D:\path\to\repository `
  --person alice@example.com `
  --target-role "Senior Backend Engineer" `
  --language en-US `
  --style concise `
  --max-bullets 6 `
  --no-llm `
  --json

# Inspect the built-in providers and test the selected provider.
gca providers list D:\path\to\repository --json
gca providers test D:\path\to\repository --json

# Inspect and replay persisted analysis runs.
gca runs list D:\path\to\repository --json
gca runs show <run-id> D:\path\to\repository --json

# Rebuild reports from a persisted run.
gca report D:\path\to\repository --run latest --format markdown
gca report D:\path\to\repository --run latest --format json --output report.json

# Remove only the repository-local .gca workspace.
gca uninit D:\path\to\repository --yes
```

Phase 2 indexes refs, commits, parent relationships, file changes, identities, stable
patch IDs, target-branch reachability, release tags, cherry-picks, and reverts. The index
is stored under the analyzed repository's `.gca/` directory and is ignored locally through
`.git/info/exclude`; GCA does not modify source files or Git history.

Git facts and the deterministic contribution analysis do not depend on an LLM.
Analysis runs persist their parameters, Git baseline, rule version, Contribution Items,
capability assessments, Evidence, and versioned report JSON. Phase 4 adds pluggable Mock,
OpenAI-compatible, Anthropic, Ollama, Codex CLI, and Claude CLI providers for semantic
summaries, capability explanations, and resume candidates. Providers cannot replace or modify
deterministic facts.

## LLM Providers

LLM use is disabled by default. Enable it in the analyzed repository's `.gca/config.yml`:

```yaml
llm:
  enabled: true
  provider: openai-compatible
  model: gpt-4.1-mini
  baseUrl: https://api.openai.com/v1
  apiKeyEnv: GCA_LLM_API_KEY
  timeoutSeconds: 30.0
  maxRetries: 2
  allowFallbackToRules: true
```

Set the referenced environment variable outside the repository. Never put the key value in
`.gca/config.yml`. CLI flags are intentionally not provided for key values.

`gca analyze --no-llm` is always offline and deterministic. With LLM enabled, every invocation
records a request hash, Provider/model, Prompt/Schema versions, attempts, latency, status, error
code, and cache-hit state. Prompts, API keys, Authorization headers, and source bodies are not
stored. Provider failures produce a `PARTIAL` deterministic report when fallback is allowed;
otherwise `analyze` exits with code `6` and persists a failed run.

The same Provider configuration is used by `assess` and `resume`. Work assessment uses the
independent `assessment-explanation-v1` task; resume generation uses `resume-v1`. Provider
output cannot alter completion, size, difficulty, Evidence, or the deterministic claim-strength
ceiling. With fallback enabled, assessment retains its deterministic result and resume retains
its conservative template.

To reuse an authenticated coding CLI instead of an API key:

```yaml
llm:
  enabled: true
  provider: codex-cli # or claude-cli
  model: configured-default
  executable: null # auto-discover, or set an absolute wrapper/executable path
  commandTimeoutSeconds: 300
  allowFallbackToRules: true
```

Command Providers run in an isolated temporary directory. Repository source is not made
available to the agent: GCA passes only its minimized semantic task over stdin. Codex runs
ephemerally with a read-only sandbox and MCP disabled; Claude runs without tools, MCP, Chrome,
or session persistence. Existing CLI authentication and model-provider configuration are reused.

See [`doc/guides/provider-guide.md`](doc/guides/provider-guide.md) for all providers and
environment precedence.

## Index Semantics

- `AUTHORED_ONLY`: the commit is indexed but is not reachable from the configured target branch.
- `LANDED`: the commit is reachable from the target branch.
- `RELEASED`: the commit is reachable from the target branch and at least one release tag.
- `REVERTED`: a landed or released commit is linked to a landed revert commit.
- Matching stable patch IDs link an authored-only cherry-pick source to delivered work without
  counting it as a second delivery.

Exact email and `.mailmap` mappings are deterministic. Fuzzy name matches are never merged
automatically; use `gca identities map` to confirm ambiguous aliases.

## Deterministic Analysis

`gca analyze` accepts either one confirmed Person through `--person` or every indexed Git
identity through `--all --no-llm`. Project analysis deliberately keeps unconfirmed identities
separate and emits identity warnings instead of silently merging or excluding them. Both modes
support inclusive date/time, branch, release tag, path scope, and delivery-status filters.

Person and project reports contain separate technical and business summaries. Technical
summaries cover modules, change types, and evidence-backed capability signals. Business domains
are deterministically inferred from conventional commit scopes, issue keys, and module fallback
clusters. They are labels for work areas, not claims about revenue, customer value, business
ownership, or individual performance.

Every Contribution Item and capability claim references an Evidence ID. Reports explicitly
state that Git evidence does not prove business outcome, sole ownership, or employee value.
Optional ranking uses published workload, difficulty, and delivery rules; commit and raw line
counts do not directly determine the score.

Shared or system accounts require manual review. If one email is used by both a person and an
automation identity, do not use the combined Person for individual performance conclusions.

## Work Assessment

`gca assess` separates completed (`LANDED`/`RELEASED`), pending (`AUTHORED_ONLY`), rework, and
merge/integration activity. It reports `SMALL`, `MEDIUM`, `LARGE`, and `XLARGE` effective-change
bands separately from `ROUTINE`, `STANDARD`, `COMPLEX`, and `HIGH_RISK` engineering difficulty.
Merge diffs, matching patch IDs, generated/vendor/build output, lockfiles, and binary line counts
do not create duplicate workload. Difficulty is based on versioned data, distributed-system,
compatibility, impact, critical-domain, and delivery signals; raw line count cannot raise it.

`--time-basis` accepts `authored`, `committed`, `merged`, `landed`, and `released`. Landed time is
the target branch first-parent integration point, merged time includes only work introduced by a
merge commit, and released time is the tag creation time. `--period week|month|quarter` requires
both boundaries and emits persisted trends, period-over-period deltas, and year-over-year deltas
when the matching prior-year period is in range. Weeks start on Monday and partial boundary periods
are marked. Offset-free `--since` and `--until` values use the host system time zone; explicit `Z`
or numeric offsets remain authoritative, and calendar periods follow that local calendar. The Git
index and SQLite query bindings remain normalized to UTC. Run `gca index` once after upgrading so
old timestamps are rebuilt in UTC.

Assessment reports include technical and business summaries, Evidence IDs, rule versions,
confidence, and gaps. Repeatable `--rank-by` enables dense dimension rankings. An explicit
`--ranking-config` YAML can add a cohort-normalized weighted total; without it no total score is
generated. These values are review aids, not performance ratings, working-hours estimates,
compensation, or promotion recommendations. Persisted v2 runs can be exported with
`gca report --format csv`; email is omitted unless `--include-email` is supplied.

## Resume Generation

`gca resume` only accepts a confirmed Person and defaults to landed/released work. Every project
summary and experience bullet references Contribution Item and Evidence IDs. Claim strength is
limited to `CONTRIBUTED`, `IMPLEMENTED`, or `LED`; Git-only evidence never unlocks `LED`.

`--no-llm` generates a conservative template. Optional verified outcomes are loaded from a
strict UTF-8 YAML file:

```yaml
outcomes:
  - id: OUT-001
    text: API P95 latency reduced from 420ms to 180ms
    source: benchmark-report-2026-04.md
    verifiedBy: team-lead
    verifiedAt: 2026-04-20
```

Percentages, revenue, user growth, online performance, and similar result numbers are rejected
unless the claim cites a verified outcome. Resume reports omit email addresses, other people,
team rankings, and internal difficulty comparisons. The legacy `semantic.resumeBullets` field
remains readable during 1.x but is deprecated; new integrations should use `gca resume`.

## Quality Checks

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pytest --cov=git_contribution_analyzer
.\.venv\Scripts\python.exe -m build
```

## Documentation

- [Simplified Chinese documentation](doc/zh-CN/README.md)
- [Architecture](doc/architecture/architecture.md)
- [Data model and migrations](doc/architecture/data-model.md)
- [CLI reference](doc/cli/cli-reference.md)
- [Installation, upgrade and removal](doc/guides/installation.md)
- [Assessment and resume methodology](doc/guides/methodology.md)
- [Privacy and provider data boundaries](doc/guides/privacy.md)
- [Golden dataset](doc/testing/golden-dataset.md)
- [0.4.1 release](doc/releases/0.4.1.md)
- [0.4.0 release](doc/releases/0.4.0.md)
- [0.3.0 release](doc/releases/0.3.0.md)
- [0.2.0 release](doc/releases/0.2.0.md)
- [0.1.0 release](doc/releases/0.1.0.md)
- [Performance baseline](doc/reports/performance-baseline.md)
- [Security and privacy audit](doc/reports/security-privacy-audit.md)

Release CI builds wheel/sdist, CLI standalone and GUI standalone artifacts on Windows, Linux and
macOS. The ordinary CI matrix also performs isolated wheel and repository lifecycle smoke tests.

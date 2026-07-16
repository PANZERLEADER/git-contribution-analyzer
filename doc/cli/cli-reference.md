# GCA CLI Reference

[简体中文](../zh-CN/cli-reference.md)

## Global Options

| Option | Meaning |
|---|---|
| `--help` | Show commands or command-specific help |
| `--version` | Show the installed GCA version |

Paths are optional and default to the current directory. Windows paths containing spaces or
Unicode are supported when passed as one quoted argument.

## Repository Lifecycle

| Command | Purpose |
|---|---|
| `gca init [PATH]` | Create `.gca`, migrate SQLite and perform the first index |
| `gca index [PATH]` | Rebuild the deterministic index |
| `gca sync [PATH]` | Incrementally synchronize refs and commits |
| `gca status [PATH] [--json]` | Show workspace, baseline and identity health |
| `gca doctor [PATH] [--json]` | Diagnose Git, workspace, database and lock state |
| `gca uninit [PATH] [--yes]` | Remove only the repository-local GCA workspace |

`gca status --json` emits `status/v2`, which adds the structural cache summary. The original
`schemas/status/v1.json` remains unchanged for replay and compatibility checks.

## Structural Observations

```powershell
gca structural status <repo> --json
gca structural rebuild <repo> --cutoff 2026-07-01T00:00:00Z `
  --branch main --scope src --time-strategy dual-window --json
gca structural show <repo> --baseline <baseline-id> --json
gca structural prune <repo> --keep 8 --yes --json
```

`--cutoff` is exclusive; omitting it uses the current instant. `--branch` defaults to the
repository configuration, `--scope` is an optional path prefix, and `--time-strategy` accepts
`lifetime`, `rolling-window`, or `dual-window`. When omitted, the command uses `.gca/config.yml`
(`DUAL_WINDOW` in `community-baseline-v1`). Rebuild publishes only completed immutable baselines.
Prune requires `--yes` and removes only old rebuildable baseline caches.

The output is repository-level observation data. It does not change work assessment, difficulty,
ranking or resume results. `status` and `doctor` include cache diagnostics.

## Identities

```powershell
gca identities list <repo> --json
gca identities map <repo> --name Alice --email alice@example.com `
  --person-name Alice --person-email alice@example.com
```

Exact email and `.mailmap` suggestions remain unconfirmed until explicitly mapped. Resume commands
reject unconfirmed identities.

## Analysis

```powershell
gca analyze <repo> --person alice@example.com --no-llm --json
gca analyze <repo> --all --no-llm --json
```

Common filters are `--since`, `--until`, `--branch`, `--release`, `--scope` and `--delivery`.
`--person` and `--all` are mutually exclusive.

## Work Assessment

```powershell
gca assess <repo> --person alice@example.com --no-llm --json
gca assess <repo> --person alice@example.com --person bob@example.com --no-llm --json
gca assess <repo> --all --exclude-person ci@example.com --no-llm --json
gca assess <repo> --all --rank-by workload --rank-by difficulty --no-llm --json
gca assess <repo> --all --ranking-config team-ranking.yml --no-llm --json
gca assess <repo> --all --since 2025-01-01 --until 2026-12-31 `
  --period quarter --time-basis released --no-llm --json
gca report <repo> --run latest --format csv --output team.csv
```

The result separates completed, pending, rework and integration activity. Size and difficulty are
versioned distributions, not an employee score or ranking. `--person` and `--exclude-person` are
repeatable. `--exclude-person` is valid only with `--all`; all-person selection includes active,
confirmed `HUMAN` identities by default and records other identities as exclusions. CSV omits
email unless `--include-email` is explicitly supplied.

`--time-basis` accepts `authored`, `committed`, `merged`, `landed`, and `released`.
`--period` accepts `week`, `month`, or `quarter` and requires ordered `--since` and `--until`
boundaries. Each calendar period is persisted as a work assessment run, together with a series run
containing period-over-period and available year-over-year changes. Weeks start on Monday; partial
boundary periods are marked.
Offset-free dates and times use the host system time zone. Inputs with `Z` or a numeric offset use
that explicit zone. Reports retain the input offset while index queries convert boundaries to UTC.

Identity maintenance supports reversible merges:

```powershell
gca identities merge <repo> --source old@example.com --target person-id --dry-run --json
gca identities merge <repo> --source old@example.com --target person-id --yes --json
gca identities merges <repo> --json
gca identities unmerge <repo> --merge-id <id> --yes --json
```

Merge keeps the source Person and historical reports. It moves aliases to the target for future
analysis and records an event that can be reversed while those aliases remain unchanged.

## Resume

```powershell
gca resume <repo> --person alice@example.com --language en-US `
  --style concise --max-bullets 6 --no-llm --json
```

Options include `--target-role`, `--include-pending` and `--verified-outcomes <yaml>`. Languages are
`zh-CN` and `en-US`; styles are `concise`, `star` and `xyz`. Verified outcomes require `id`, `text`,
`source`, `verifiedBy` and `verifiedAt`.

## Runs And Reports

```powershell
gca runs list <repo> --json
gca runs show <run-id> <repo> --json
gca runs compare <base-run-id> <target-run-id> <repo> --json
gca report <repo> --run <run-id> --format markdown --output report.md
gca report <repo> --run <run-id> --format json --output report.json
```

`runs compare` accepts two persisted `WORK_ASSESSMENT` runs and reports overall, distribution, and
per-person deltas. It warns when rule versions, time bases, or cohorts differ.

`report` replays persisted results and selects a renderer from the run type.

## Providers

```powershell
gca providers list <repo> --json
gca providers test <repo> --json
```

Built-ins: `mock`, `openai-compatible`, `anthropic`, `ollama`, `codex-cli` and `claude-cli`.
Credentials are resolved from environment variables and are never written to `.gca/config.yml`.

## Exit Codes

| Code | Meaning |
|---:|---|
| 0 | Success |
| 2 | CLI usage error |
| 3 | Git/repository error |
| 4 | Workspace/configuration error |
| 5 | Identity error |
| 6 | LLM/provider error |
| 7 | Report/schema error |
| 8 | Interrupted operation |

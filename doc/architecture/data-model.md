# GCA Data Model

[简体中文](../zh-CN/data-model.md)

## Workspace

Each analyzed repository owns a `.gca/` workspace:

```text
.gca/
  config.yml
  meta.json
  index.sqlite
  locks/
```

The database is rebuildable from Git except for manual identity confirmation, persisted runs,
verified external inputs and LLM audit/cache records. Back up `index.sqlite` before downgrading.

## Git Index Tables

| Table | Purpose |
|---|---|
| `repositories` | Repository root, Git directory and default branch |
| `refs` | Observed branches/tags and active state |
| `commits` | Author, timestamps, message, patch/revert metadata and diff totals |
| `commit_parents` | Ordered parent relationships, including merges |
| `file_changes` | Per-commit paths, change type, binary flag and effective line counts |
| `commit_delivery` | `AUTHORED_ONLY`, `LANDED`, `RELEASED` and `REVERTED` evidence |
| `persons` | Canonical repository-scoped identities |
| `identity_aliases` | Exact-email, mailmap and manual alias evidence |
| `identity_merge_events` | Reversible Person merge snapshots and alias movements |

Identity aliases are not fuzzily merged. A Person must be explicitly confirmed before resume
generation. Reversible merges retain inactive source Persons with a redirect to the active target;
historical run JSON remains immutable.

## Analysis Tables

| Table | Purpose |
|---|---|
| `analysis_runs` | Versioned `ANALYSIS`, `WORK_ASSESSMENT`, `WORK_ASSESSMENT_SERIES` or `RESUME` run and result JSON |
| `contribution_items` | Stable grouped work items for analysis runs |
| `evidence` | Commit/path/metric references used by claims |
| `capability_assessments` | Evidence-backed technical capability signals |
| `llm_invocations` | Provider/model/prompt/schema/status audit without API keys |
| `llm_cache` | Validated structured provider responses keyed by request hash |

Work assessment and resume results are persisted in `analysis_runs.result_json`. They remain
replayable even if later rule versions change.

New person and project analysis reports may include the backward-compatible `structuralSignals`
field. It records its rule version, analyzed scope counts, repeated co-change pairs, hotspots,
supporting commit hashes and interpretation limits. Older persisted v1 reports remain valid when
the field is absent.

## Migrations

- `0001_initial`: repository and initial run state.
- `0002_git_index`: refs, commits, file changes, delivery and identities.
- `0003_analysis`: contribution items, Evidence and capability results.
- `0004_llm_audit`: invocation audit and response cache.
- `0005_run_types`: explicit run type and optional parent run.

Upgrade is automatic during workspace open. Downgrade is a maintenance operation and must use a
database backup. The `0004 -> 0005 -> 0004` path is covered by integration tests.

# Performance Baseline

## Reference Environment

- Date: 2026-07-14
- OS: Windows
- Python: 3.13.2
- Storage: local NVMe
- Repository: anonymous scale benchmark; project and identity metadata are not recorded

## Repository Shape

| Metric | Value |
|---|---:|
| Git objects | approximately 300,000 |
| Commits across indexed refs | approximately 15,000 |
| Refs | more than 200 |

## Measurements

| Operation | Observed |
|---|---:|
| First `gca init` and full index | less than 9 minutes |
| No-change `gca sync` | less than 1 second |
| Deterministic project `gca assess --all` | less than 3 seconds |
| Deterministic confirmed-person `gca resume` | less than 2 seconds |
| SQLite workspace | less than 30 MiB |

The first index is below the approved 15-minute target for an approximately 15,000-commit
repository. The no-change sync is below the 30-second target. Assessment and resume measurements
reuse the completed index and exclude initial indexing time.

## Method

Commands ran against the same indexed baseline and isolated workspace. `--no-llm` was used for
assessment and resume so provider/network latency is excluded. Project name, path, source, identity
counts, author emails, commit distributions and raw reports are deliberately not recorded.

## Remaining Benchmarks

- Add a controlled 100-commit incremental sync benchmark.
- Record peak memory with a platform-neutral profiler.
- Compare standalone and wheel startup time on release artifacts.

These items improve optimization evidence but do not change deterministic result correctness.

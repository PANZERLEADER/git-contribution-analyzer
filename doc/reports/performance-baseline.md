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
| 100-person / 15,000-item three-dimension ranking plus composite | 0.0097 seconds |
| SQLite workspace | less than 30 MiB |

The first index is below the approved 15-minute target for an approximately 15,000-commit
repository. The no-change sync is below the 30-second target. Assessment and resume measurements
reuse the completed index and exclude initial indexing time.

## Method

Commands ran against the same indexed baseline and isolated workspace. `--no-llm` was used for
assessment and resume so provider/network latency is excluded. Project name, path, source, identity
counts, author emails, commit distributions and raw reports are deliberately not recorded.

The ranking microbenchmark is reproducible with
`python scripts/benchmark_ranking.py`. It builds 15,000 synthetic item assessments, computes all
three dimensions and a weighted composite, and emits aggregate timing only.

## Remaining Benchmarks

- Add a controlled 100-commit incremental sync benchmark.
- Record peak memory with a platform-neutral profiler.
- Compare standalone and wheel startup time on release artifacts.

These items improve optimization evidence but do not change deterministic result correctness.

Structural baseline performance has a separate reproducible harness at
`scripts/benchmark_structural_baseline.py` and is reported in
`doc/reports/structural-baseline-performance.md`. The 10k/100k pure-Domain synthetic measurements
are recorded there. Two small real local samples cover cold persistence, warm lookup and SQLite
size; controlled incremental and assessment-overhead measurements remain required before any
scoring use.

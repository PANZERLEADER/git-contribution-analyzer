# Structural Baseline Performance

## Status

The synthetic and controlled repository harnesses were run on 2026-07-16 on Windows with Python
3.13.2. The measured performance prerequisites pass for the observation-only implementation.
They support the `community-baseline-v1` observation-only release. They do not replace the separate
human calibration and repository-disjoint holdout gate required for automatic structural difficulty
promotion.

| Commits | Elapsed | Peak traced memory | Eligible files | Raw edges | Couplings |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 1.6256 s | 30,795,032 bytes | 4,000 | 6,000 | 6,000 |
| 100,000 | 4.4788 s | 274,085,003 bytes | 4,000 | 6,000 | 6,000 |

## Real Local Repository Samples

The same Windows/Python environment used temporary local clones and the current GCA executable.
Only aggregate counts, timings and SQLite size were retained.

| Sample | Eligible commits | Eligible files | Raw edges | First index | Cold baseline | Warm hit | SQLite |
|---|---:|---:|---:|---:|---:|---:|---:|
| Local repository A | 4 | 233 | 46 | 2.7710 s | 0.8193 s | 0.7408 s | 741,376 bytes |
| GCA self | 28 | 293 | 19,979 | 2.8185 s | 0.9327 s | 0.7129 s | 21,295,104 bytes |

Both warm calls returned the same baseline ID as their cold build. The GCA sample shows that pair
density, not commit count alone, is the dominant SQLite growth factor. The timings include normal
CLI process startup and therefore represent user-observed command latency rather than an isolated
function microbenchmark.

## Controlled Incremental And Assessment Measurements

The controlled repository started with 10 commits. Each row is cumulative and measures direct
application use cases without standalone process startup.

| Added commits | Sync | Cold baseline | Warm hit | SQLite | Baseline stable |
|---:|---:|---:|---:|---:|---|
| 1 | 0.3837 s | 0.0868 s | 0.0859 s | 327,680 bytes | yes |
| 10 | 0.7247 s | 0.0892 s | 0.0823 s | 397,312 bytes | yes |
| 100 | 3.6923 s | 0.1091 s | 0.0874 s | 753,664 bytes | yes |

Assessment used equivalent SQLite snapshots before and after baseline materialization, with one
warm-up and seven measured deterministic runs per side. Median time changed from 0.0769 seconds to
0.0824 seconds, an observed overhead ratio of 7.14%. This is below the frozen 20% performance
threshold. Observation-only assessment still does not query or score structural results.

## Commands

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_structural_baseline.py --commits 10000
.\.venv\Scripts\python.exe scripts\benchmark_structural_baseline.py --commits 100000
.\.venv\Scripts\python.exe scripts\benchmark_structural_baseline.py `
  --mode incremental --initial-commits 10 --increments 1,10,100 --measure-assessment
```

Performance evidence is complete for the observation-only community profile. Human-labeled
calibration and the repository-disjoint holdout remain optional unless an adopter proposes automatic
difficulty promotion; without them, the feature remains observation-only by design.

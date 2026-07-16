# Structural Difficulty Calibration Report

## Decision

`COMMUNITY_BASELINE_READY_OBSERVATION_ONLY`

## Reason

GCA now provides a conservative, versioned open-source profile that can be used without requiring
every project to reproduce a subjective two-reviewer exercise. The canonical profile is
`config/structural-community-baseline-v1.json`, and new `.gca/config.yml` files contain the same
runtime values.

The profile uses dual-window history, a 50-commit minimum, 95th-percentile hotspots, repeated
co-change and similarity thresholds, an explicit hub penalty, and a 100-path context cap. Its
`automaticDifficultyPromotion` setting is fixed to `false`. All effective thresholds participate in
the baseline cache fingerprint.

The 80-item public-repository package remains useful as an optional validation asset. It contains 32
structural candidates, 21 ordinary controls, 22 mechanical negative controls and five real-history
insufficient-baseline abstentions. No human reviewer labels have been supplied, so it does not
authorize `difficulty-rules-v2` or any automatic personal difficulty promotion.

Separate performance prerequisites passed, including 10k/100k synthetic aggregation, real local
samples, controlled 1/10/100-commit incremental sync and 7.14% measured assessment overhead.

## Product Effect

- Historical structural baselines and reports are ready for observation-only use.
- Projects may override the community thresholds in `.gca/config.yml`; overrides remain
  observation-only and get distinct fingerprints.
- `difficulty-rules-v1` remains authoritative.
- No structural signal changes workload, difficulty, delivery, ranking, resume claims or LLM input.
- Two-reviewer calibration and a repository-disjoint holdout become mandatory only for a future
  automatic promotion rule.

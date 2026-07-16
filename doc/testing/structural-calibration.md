# Structural Difficulty Calibration Protocol

## Status

The open-source baseline is `COMMUNITY_BASELINE_READY_OBSERVATION_ONLY`. GCA ships the conservative
`community-baseline-v1` configuration and fixes `automaticDifficultyPromotion` to `false`.
Project-specific human review is not required to build, inspect or export structural baselines.

The existing 80-item public-repository package is retained as an optional methodology asset. It is
required only if an adopter proposes a rule that automatically changes individual work difficulty.
Synthetic or agent-generated labels must never authorize such a promotion rule.

## Community Baseline

The canonical configuration is `config/structural-community-baseline-v1.json`. New workspaces copy
the same values into `.gca/config.yml`. Projects may override observation thresholds, but any
override remains observation-only and produces a distinct baseline fingerprint.

The baseline deliberately favors lower false-positive volume:

- dual-window history with a 365-day recent window;
- at least 50 eligible historical commits;
- 95th-percentile hotspots;
- at least three co-change commits;
- subset ratio at least 0.80 and Jaccard at least 0.30;
- hub penalty at least 0.50;
- at most 100 eligible paths per commit context;
- no automatic difficulty promotion.

These values are general-purpose defaults, not statistically precise claims for every repository.

## Optional Promotion Validation

An adopter that wants structural evidence to change individual difficulty must create a separate
rule version and complete all of the following before enabling it:

- At least 80 calibration items and 40 repository-disjoint holdout items.
- At least six repositories covering new, mature, sparse and monorepo histories.
- At least 20 mechanical-change or ubiquitous-hub negative controls.
- Two independent reviewers per item, followed by adjudication.
- A configuration frozen before holdout is opened.
- One holdout evaluation with no threshold tuning after results are visible.

Labels describe only whether historical hotspot/coupling context adds defensible difficulty
context. They must not describe employee value, time spent, code quality or business outcome.

## Promotion Go Criteria

- Cohen's kappa >= 0.75.
- Hotspot and coupling precision >= 0.85 independently.
- Mechanical/hub false-positive rate <= 0.05.
- Insufficient-baseline samples always abstain.
- Promoted completed STANDARD items <= 15% overall and <= 20% per repository.
- Every candidate promotion references baseline, threshold, paths/edges and Evidence.

Until every criterion passes, `difficulty-rules-v1` remains authoritative and structural results
remain observation-only. Failure of optional promotion validation does not disable the community
baseline.

## Existing Review Package

The generated package contains Reviewer A/B sheets, shared public Git evidence, an adjudication
template, an unlabeled calibration draft and an immutable manifest. AI may summarize evidence or
draft a rationale after a reviewer selects a label, but it must not select labels, inspect the other
reviewer's sheet or resolve disagreements.

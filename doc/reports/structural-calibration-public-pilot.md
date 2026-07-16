# Structural Calibration Public Repository Pilot

## Decision

`CALIBRATION_PACKAGE_READY_OPTIONAL_PROMOTION_EVIDENCE`

The GCA community profile is independently `COMMUNITY_BASELINE_READY_OBSERVATION_ONLY`.

## Scope

The pilot used a clean local clone of Apache Dubbo's `3.3` branch as a mature multi-module public
repository. The source revision was fixed before indexing. The retained report contains aggregate
counts only; it excludes repository paths, authors, emails, commit hashes, commit subjects, Issue or
PR identifiers and source snippets.

This repository is admitted only as a calibration candidate. Because it has now been inspected, it
must not be reused as the sealed repository-disjoint holdout.

## Repository Fitness

| Requirement | Pilot result | Formal status |
| --- | ---: | --- |
| Large, mature history | 8,891 indexed commits across 2011-2026 | Satisfied for this stratum |
| Multi-module structure | 4,845 tracked files and 23 top-level directories | Satisfied for this stratum |
| Calibration candidate volume | 636 eligible post-cutoff changes | Satisfied |
| Structural candidate stratum | 201 non-mechanical heuristic candidates | Satisfied |
| Ordinary control stratum | 55 small changes without candidate exposure | Satisfied |
| Mechanical negative-control pool | 379 heuristic candidates | Satisfied for sampling, not labeled truth |
| Insufficient-history abstention | 1-commit real-history baseline returned no metrics | Satisfied |
| At least six repositories | One repository | Not satisfied |
| New and sparse histories | Mature monorepo only | Not satisfied |
| Two independent reviewers | No human labels collected | Not satisfied |
| Repository-disjoint holdout | Repository already opened and analyzed | Not satisfied |

The mechanical pool is a sampling heuristic based on change breadth and mechanical-looking subject
patterns. It is not a ground-truth label and must be independently reviewed.

## Baseline Results

The main pilot cutoff produced the following observation-only baselines with the current candidate
thresholds:

| Time strategy | Eligible commits | Eligible files | Raw edges | Hotspots | Couplings | Cross-module couplings | Capped commits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Lifetime | 7,618 | 14,133 | 785,938 | 1,668 | 20,543 | 4,505 | 30 |
| Rolling window | 674 | 1,949 | 54,721 | 338 | 818 | 265 | 3 |
| Dual window | 7,618 | 14,133 | 785,938 | 1,668 | 20,543 | 4,505 | 30 |

All three baselines reported `HIGH` baseline confidence and
`STRUCTURAL_CONTEXT_CAPPED`. The large difference between lifetime and rolling-window candidate
volume confirms that any automatic-promotion time strategy must be selected from reviewed
calibration labels rather than chosen from data volume alone. The community observation profile may
still use a conservative general default without claiming promotion precision.

The abstention check used a real early-history cutoff with one eligible commit. It produced zero
hotspots, zero couplings, `LOW` confidence and `INSUFFICIENT_STRUCTURAL_BASELINE`, satisfying the
required abstention behavior.

## Anonymous Pilot Sample

A deterministic 20-item trial sample was formed without retaining source identifiers:

| Stratum | Items | Retained fields |
| --- | ---: | --- |
| Structural candidate | 8 | Anonymous ID, path-count band and exposure counts |
| Ordinary control | 6 | Anonymous ID, path-count band and zero-exposure confirmation |
| Mechanical control | 5 | Anonymous ID, path-count band and exposure counts |
| Insufficient history | 1 | Anonymous ID and expected `ABSTAIN` handling |

Every item remains `UNREVIEWED`. The sample proves extraction and anonymization feasibility only; it
does not contribute precision, false-positive-rate, kappa or promotion-rate measurements.

## Configuration State

The evaluated candidate threshold snapshot has SHA-256
`756a87a1f9d5ce0ebb72c16cbb1f6edbf9fb5a1ab891b3b2b1b3b3f09799aec8`.

This is a reproducibility fingerprint for the evaluated candidate, not the community profile. A
formal automatic-promotion freeze can occur only after two-reviewer calibration labels are complete
and one time strategy and threshold configuration have been selected without opening holdout data.

## Runtime Observation

- Full first index: approximately 397.7 seconds.
- Lifetime baseline: approximately 17.0 seconds.
- Rolling-window baseline: approximately 1.9 seconds.
- Dual-window baseline: approximately 16.8 seconds.
- Repository-local index after the three main baselines: approximately 1.19 GB.

The initial index should therefore be built once per repository and reused across sample extraction.
This cost does not weaken the calibration methodology, but it affects corpus preparation and storage
planning.

## Additional Public Repository Screening

Four additional calibration candidates were screened using Blob-free Git histories. Only aggregate
history and tree counts are retained; no source path, author, email, commit hash or commit subject is
included in this report.

| Candidate | Intended stratum | Commits | History span | Last 12 months | Tracked files | Top-level units | Merge ratio | Mechanical heuristic pool |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| controller-runtime | Mature medium Go infrastructure | 3,440 | 2018-2026 | 296 | 454 | 7 | 40.93% | 533 |
| FastAPI | Mature medium Python framework | 7,473 | 2018-2026 | 1,579 | 3,019 | 7 | 0.17% | 650 |
| uv | New high-velocity Rust project | 9,710 | 2023-2026 | 2,228 | 1,306 | 12 | 0.00% | 1,176 |
| JUnit4 | Long-lived sparse-maintenance Java library | 2,519 | 2000-2026 | 2 | 619 | 6 | 15.84% | 163 |

The mechanical counts are subject-pattern screening heuristics, not labels. Their purpose is only to
show that each repository can contribute negative-control candidates for independent review.

The four repositories add methodological diversity that Dubbo cannot provide alone:

- controller-runtime tests merge-heavy history and the merge-exclusion boundary.
- FastAPI tests a documentation-rich Python repository with high recent activity.
- uv supplies the required new-history stratum without depending on a synthetic short history.
- JUnit4 supplies a real long-lived but currently sparse maintenance history.

## Recommended Corpus Partition

The following partition reaches the protocol minimum without opening holdout history during
threshold selection:

| Partition | Repository | Target items | Status |
| --- | --- | ---: | --- |
| Calibration | Dubbo | 20 | Already inspected; pilot source |
| Calibration | controller-runtime | 15 | History screened; eligible for labeling |
| Calibration | FastAPI | 15 | History screened; eligible for labeling |
| Calibration | uv | 15 | History screened; eligible for labeling |
| Calibration | JUnit4 | 15 | History screened; eligible for labeling |
| Holdout | ripgrep | 20 | Reserve; metadata only, do not clone before freeze |
| Holdout | spring-petclinic | 20 | Reserve; metadata only, do not clone before freeze |

This yields 80 calibration items, 40 repository-disjoint holdout items and seven repositories. Public
mirror metadata reports approximately 2,263 commits for ripgrep and 1,034 for spring-petclinic,
which is sufficient for a 20-item holdout target without inspecting their samples now.

Before sealing the holdout manifest, verify that each mirror still points to the canonical public
repository and record the immutable source revision. Mirror freshness is an acquisition concern, not
a reason to use Forge evidence in GCA analysis.

## Executed Calibration Package

All five calibration repositories were fully indexed and each produced healthy lifetime,
rolling-window and dual-window baselines:

| Repository alias | Indexed commits | Candidate commits | Structural pool | Ordinary pool | Mechanical pool | Selected items |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CAL-01 | 8,891 | 1,670 | 556 | 207 | 907 | 20 |
| CAL-02 | 3,440 | 407 | 212 | 79 | 116 | 15 |
| CAL-03 | 7,473 | 1,475 | 1,189 | 99 | 184 | 15 |
| CAL-04 | 9,710 | 1,940 | 1,171 | 491 | 278 | 15 |
| CAL-05 | 2,519 | 421 | 268 | 127 | 26 | 15 |

The resulting package contains 80 shared evidence files, two independent 80-row reviewer sheets,
one adjudication template, one unlabeled calibration draft and one manifest. Reviewer sheets contain
no repository name, commit hash, path, subject, author or email. Shared evidence contains only public
Git identifiers needed for review and excludes author and email fields.

The full pilot exposed a valid Gitlink/submodule compatibility defect while indexing CAL-04. GCA
previously attempted to read the submodule commit as a parent-repository Blob. Gitlink mode `160000`
is now treated as external binary context, with a regression test covering a deliberately absent
submodule object. The final validation passed 229 tests, ruff and mypy.

The package has 32 structural candidates, 21 ordinary controls, 22 mechanical negative controls and
five insufficient-history abstentions. All 15 persisted baselines are healthy. Holdout repository
names and data are absent from the extraction configuration and generated package.

## Optional Next Step

No review step is required for observation-only use. If a future adopter proposes automatic
difficulty promotion, complete Reviewer A and Reviewer B independently, calculate agreement and
adjudicate disagreements. Freeze one configuration before acquiring the reserved holdout
repositories, then evaluate exactly 40 holdout items once. Until all promotion criteria pass,
`difficulty-rules-v1` remains authoritative.

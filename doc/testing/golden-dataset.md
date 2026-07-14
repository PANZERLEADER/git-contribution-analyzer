# Golden Dataset

[简体中文](../zh-CN/golden-dataset.md)

## Purpose

The golden repository is generated at test time with real Git commands. It fixes the behavioral
contract for delivery classification, duplicate suppression, difficulty counterexamples, privacy
and run/report replay without copying private repository source.

## Scenarios

`tests/helpers/golden_repository.py` creates:

1. Alice's landed feature, test and documentation merged to `main`.
2. Alice's authored-only feature branch.
3. Bob's independent landed feature.
4. A merge commit.
5. A cherry-picked duplicate patch.
6. A commit followed by revert.
7. A small database migration expected to be high risk.
8. A large documentation-only change expected to remain low difficulty.
9. Generated content, a binary file and a lockfile.
10. A release tag and target branch.

The repository path contains spaces and Chinese characters to exercise Windows and cross-platform
path handling.

## Lifecycle

`tests/e2e/test_dual_track_golden_lifecycle.py` runs:

```text
init -> identities map -> analyze --no-llm
     -> assess --person --no-llm -> assess --all --no-llm
     -> resume --person --no-llm
     -> resume with mock provider and verified outcomes
     -> runs list/show -> report markdown/json
```

Assertions focus on stable contracts rather than generated UUIDs or timestamps. Any new rule
version that intentionally changes a golden result must update the test and this document in the
same change, with a rationale in `CHANGELOG.md`.

## Private Reference Repositories

Large private repositories may be used for performance and calibration, but only anonymous counts,
timings and file sizes may be committed. Source, emails, credentials and raw reports must remain
outside this repository.

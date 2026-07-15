# Assessment And Resume Methodology

[简体中文](../zh-CN/methodology.md)

## Evidence Boundary

GCA observes Git commits, refs, parent relationships, patch IDs, file changes, release tags and
explicit identity mappings. Every derived statement must reference Evidence that can be traced to
those facts. Git cannot prove time spent, sole ownership, business outcome or employee value.

## Completion Buckets

- `COMPLETED`: the item is `LANDED` or `RELEASED` on the evaluated target.
- `PENDING`: evidence exists only on an authored branch and is not counted as completed workload.
- `REWORK`: reverted or repeated-fix evidence retained separately from completed workload.
- `integrationWork`: merge/release integration activity shown separately from feature work.

Merge diffs, duplicate patches, binary line counts, generated content, vendor content and lockfile
noise are excluded from effective workload where the versioned rule declares them noise.

## Work Size

`SMALL`, `MEDIUM`, `LARGE` and `XLARGE` describe effective files, effective churn and module span
relative to a repository baseline. Size is not duration or difficulty.

## Difficulty

`ROUTINE`, `STANDARD`, `COMPLEX` and `HIGH_RISK` are deterministic rule results. Signals cover
structural change, impact scope, data migration, distributed consistency, business-critical paths,
compatibility and delivery burden. Each result includes a rule version, Evidence, confidence and
gaps. Missing structural analyzers lower confidence rather than inventing a signal.

## Ranking

Ranking is disabled unless requested. `workload` maps completed size bands to `1/3/6/10` points;
`difficulty` maps completed difficulty levels to `1/2/4/6`; `delivery` uses completed item count
with a rework penalty capped at 30%. Values use Decimal arithmetic, four decimal places and dense
ties. An optional YAML configuration applies cohort-max normalization and explicit weights that
must sum exactly to `1.0`. Scores cannot be compared across different cohorts or configurations.

## Time Bases And Periods

- `AUTHORED` is the author timestamp; `COMMITTED` is the committer timestamp.
- `LANDED` is the first target-branch first-parent integration point containing the commit.
- `MERGED` is the merge commit that introduces the commit; direct commits have no merged time.
- `RELEASED` is the first associated tag creatordate: tagger time for annotated tags and target
  commit time for lightweight tags.

Weeks start on Monday; months and quarters follow the calendar. Partial boundary periods are
marked. Period-over-period uses the preceding emitted period. Year-over-year is calculated only
when the series contains the corresponding prior-year period. Comparisons require the same
repository, cohort, filters, and rule versions. Git timestamps are normalized to UTC; rebuild an
existing index once after upgrading.

Offset-free CLI dates and times use the host system time zone; `Z` and numeric offsets remain
authoritative. Week, month, and quarter boundaries are calculated in that same local calendar,
including system daylight-saving transitions. Conversion to UTC happens only for index storage and
SQLite time filtering.

## Resume Claims

- `CONTRIBUTED`: contribution evidence exists, but responsibility boundaries are incomplete.
- `IMPLEMENTED`: a confirmed Person has primary delivered implementation evidence without an
  ownership conflict.
- `LED`: requires explicit ownership or human-verified evidence; Git alone cannot grant it.

Percentages, revenue, growth and production outcome numbers require a strict verified-outcome YAML
record. Pending work is excluded by default and explicitly marked when requested.

## LLM Role

LLMs may explain or rewrite allowlisted deterministic claims. They cannot see or change ranking
scores, change size/difficulty,
introduce unknown Item/Evidence IDs, exceed claim-strength ceilings, add unsupported numbers or
infer team ranking. Provider output is schema-validated and audited; failure can safely fall back
to deterministic content.

## Human Review

Use work assessment as a structured review input, not an automated performance decision. Resolve
identity warnings, confirm the target branch and review Evidence gaps before comparing periods.
Resume drafts require editing for context that Git cannot contain, especially outcomes and shared
ownership.

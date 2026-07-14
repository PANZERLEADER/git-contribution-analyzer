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
relative to a repository baseline. Size is not duration or difficulty. GCA reports distributions
and item lists and never reduces them to an employee total score.

## Difficulty

`ROUTINE`, `STANDARD`, `COMPLEX` and `HIGH_RISK` are deterministic rule results. Signals cover
structural change, impact scope, data migration, distributed consistency, business-critical paths,
compatibility and delivery burden. Each result includes a rule version, Evidence, confidence and
gaps. Missing structural analyzers lower confidence rather than inventing a signal.

## Resume Claims

- `CONTRIBUTED`: contribution evidence exists, but responsibility boundaries are incomplete.
- `IMPLEMENTED`: a confirmed Person has primary delivered implementation evidence without an
  ownership conflict.
- `LED`: requires explicit ownership or human-verified evidence; Git alone cannot grant it.

Percentages, revenue, growth and production outcome numbers require a strict verified-outcome YAML
record. Pending work is excluded by default and explicitly marked when requested.

## LLM Role

LLMs may explain or rewrite allowlisted deterministic claims. They cannot change size/difficulty,
introduce unknown Item/Evidence IDs, exceed claim-strength ceilings, add unsupported numbers or
infer team ranking. Provider output is schema-validated and audited; failure can safely fall back
to deterministic content.

## Human Review

Use work assessment as a structured review input, not an automated performance decision. Resolve
identity warnings, confirm the target branch and review Evidence gaps before comparing periods.
Resume drafts require editing for context that Git cannot contain, especially outcomes and shared
ownership.

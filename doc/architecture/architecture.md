# GCA Architecture

## Goals

GCA is a CLI-first, local Git analysis tool. Deterministic Git facts and versioned rules are the
source of truth. LLM providers may improve wording, but cannot replace evidence, change workload
or difficulty levels, or raise resume claim strength beyond deterministic limits.

## Layers

```text
CLI
  -> application use cases
      -> domain models and deterministic rules
          -> application ports
              -> Git, SQLite, LLM, outcome and reporting adapters
```

- `domain`: immutable models and deterministic contribution, workload, difficulty and claim rules.
- `application`: use cases, snapshots, provider tasks and repository-independent ports.
- `adapters`: Native Git/PyDriller, SQLite, LLM providers, YAML outcomes and report renderers.
- `cli`: Typer commands, versioned output envelopes and stable exit-code mapping.

Dependencies point inward. Domain code does not import CLI, SQLite, HTTP or command providers.

## Analysis Flows

```text
init/index/sync -> Git index -> identity normalization
                              -> EvidenceSnapshot
                                  -> analyze
                                  -> assess -> optional assessment explanation
                                  -> resume -> optional resume wording
```

`EvidenceSnapshot` is content-addressed from canonical JSON. The same baseline, filters, identity
scope and rule versions produce the same snapshot ID. A provider receives a redacted allowlisted
context derived from the snapshot; it does not read the repository.

## Extension Points

- Add an LLM by implementing `LlmProvider` and registering it in the provider registry.
- Add deterministic signals through a new rule version; never rewrite historical run results.
- Add a report format behind the reporting adapter boundary.
- Future complexity/impact analyzers implement application ports and report explicit gaps when an
  adapter is unavailable.

## Failure Boundaries

- Git/index failures roll back the SQLite transaction.
- Provider failures either create a `PARTIAL` run with deterministic output or fail explicitly,
  according to configuration.
- Reports are rebuilt from persisted run JSON and do not silently rerun analysis.
- `.gca/` is repository-local state and is added to `.git/info/exclude`, not committed.

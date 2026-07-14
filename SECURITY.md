# Security

Do not include repository source, credentials, API keys, or private reports in public issues.
Report security concerns privately to the project maintainers.

The CLI must never persist LLM API keys in repository-local configuration or logs.

## Data Boundary

Deterministic analysis is local. When an LLM provider is enabled, only the allowlisted Evidence
context described in `doc/guides/privacy.md` may be transmitted. Provider prompts must not contain
source bodies, Person email, credentials, team ranking, or unrestricted repository access.

Use `--no-llm` for repositories that prohibit any model processing. Treat `.gca/index.sqlite`,
verified outcome files, and exported reports as internal data.

## Release Controls

Every release candidate must pass the Git-history credential scan, the three-platform test/build
matrix, isolated wheel lifecycle verification, and standalone artifact smoke tests. A failed scan
or a report containing unsupported identity/outcome information blocks release.

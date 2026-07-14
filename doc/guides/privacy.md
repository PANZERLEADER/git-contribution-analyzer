# Privacy And Data Boundaries

[简体中文](../zh-CN/privacy.md)

## Local Data

By default, indexing, identity normalization, deterministic analysis, assessment and resume
templates run locally. `.gca/index.sqlite` contains repository paths, commit metadata, author
identity data, derived Evidence and persisted reports. Protect it as internal project data.

GCA does not store API keys in repository configuration or logs. Provider secrets must come from
environment variables or the provider's existing authenticated CLI session.

## LLM Context

Provider requests use a redacted, allowlisted context. They may contain:

- contribution item IDs and Evidence IDs;
- commit subjects and conservative module/path summaries;
- deterministic capability or claim ceilings;
- user-selected role, language and style.

They must not contain Person email, source file contents, credentials, other people's resume
details, team ranking or unrestricted repository access.

`codex-cli` and `claude-cli` are invoked with prompts over standard input and with repository tool
access disabled by their adapters. The command still runs under the current operating-system user;
review local CLI configuration before using it with private repositories.

## Provider Choice

- `mock`: local deterministic testing, no network.
- `ollama`: local model endpoint unless configured otherwise.
- `codex-cli` / `claude-cli`: reuse the locally authenticated command provider.
- `openai-compatible` / `anthropic`: send the redacted prompt to the configured HTTP endpoint.

Use `--no-llm` when repository policy prohibits any model processing.

## Reports And Sharing

Person analysis JSON may include canonical email; resume Markdown deliberately omits email and
other identities. Assessment CSV omits email by default and requires `--include-email` to add it.
Excluded team identities are recorded by Person ID and reason. Review and redact internal paths,
identities and commit subjects before sharing reports externally.

Verified outcome files are human-controlled evidence and may contain sensitive business results.
Keep them outside public repositories unless approved.

## Retention And Removal

`gca uninit <repo> --yes` removes the local workspace. Provider invocation audit stores hashes,
versions, status and validated responses, never API keys. Organizational retention and access
policies remain the responsibility of the repository owner.

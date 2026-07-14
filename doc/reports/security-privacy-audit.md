# Security And Privacy Audit

## Scope

The audit covers repository credentials, provider inputs, logging, report identity boundaries,
package installation and local workspace behavior for the 0.1.0 release candidate.

## Controls

| Area | Control |
|---|---|
| Credentials | Provider keys are environment-only and excluded from config/log serialization |
| Prompt context | Evidence allowlists; no email or source body; tools disabled for CLI providers |
| Output claims | Schema, Evidence, numeric outcome and ownership validation |
| Local state | `.gca/` stored in `.git/info/exclude`; `uninit` removes only tool state |
| CI | Gitleaks history scan plus lint, type, test, build and isolated wheel lifecycle |
| Release | Standalone artifacts built independently on Windows, Linux and macOS |

## Verification

- Resume integration tests reject unconfirmed identities and omit emails.
- Provider contract tests cover authentication, rate limits, server errors, invalid JSON and timeouts.
- Golden E2E covers project assessment without ranking and resume isolation from Bob's identity.
- The tracked `.env.example` contains placeholders only.

## Residual Risks

- Commit subjects and internal path summaries may still be sensitive; use `--no-llm` when required.
- Local command providers inherit the operating-system user's executable and network configuration.
- Reports exported outside `.gca` are controlled by the user and require an external retention policy.
- A three-platform credential scan and artifact review must pass on the release commit.

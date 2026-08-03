# Evidence ledger

The only acceptable automated live proof is `.github/workflows/live-datahub-smoke.yml`.
It must run in the expected public repository and pass the verifier described in
`docs/LIVE_SMOKE.md`. Merely committing the workflow, passing fixture tests, or starting
DataHub Core is not a successful integration claim.

This file prevents fixture behavior from being mistaken for a real integration result.

| Evidence | What it proves | What it does not prove | Status |
| --- | --- | --- | --- |
| Deterministic unit tests | Parsing, risk policy, stable receipt IDs, write/read/delete guards | Network or DataHub behavior | Ready |
| Official-adapter contract test | Agent Context Kit call boundary and response minimization | Reachability or authentication | Ready |
| Fixture CLI smoke test | End-to-end local JSON/Markdown generation | Real DataHub data or GMS success | Ready |
| Live DataHub read smoke | Entity/schema/lineage/query calls against Core/Cloud | Production adoption | Workflow ready; public run pending |
| Approval-gated write/read/delete smoke | Decision survives a second-process read with exact content and asset relation | Production adoption or retention beyond the ephemeral proof | Workflow ready; public run pending, never automatic |
| Public video under 3 minutes | Functioning project with visible DataHub evidence | Prize outcome | Pending |

## Privacy and security defaults

- Raw query text is fingerprinted immediately and is never stored in a receipt.
- Tokens and credentials are read only by the official DataHub environment mechanism.
- Fixture mode can never write to DataHub.
- Real write-back requires verified live evidence, an explicit workflow boolean, an explicit CLI
  approval flag, and a private URN handoff for independent read-back and cleanup.
- Receipts and normal CLI output reduce remote failures to stable gap codes and never include
  endpoints, tokens, raw exception text, or response payloads. The upstream SDK/Agent Context
  Kit controls its own diagnostic logging, so operators of real secured instances must treat
  process logs as potentially sensitive and apply their platform's log redaction/retention rules.

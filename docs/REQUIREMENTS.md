# DataHub Agent Hackathon requirements map

Checked against the official DataHub Devpost Overview and Rules on 2026-08-03 JST.

| Official requirement | Project evidence | Current state |
| --- | --- | --- |
| New working application | Independent package created during the submission period | Implemented locally |
| Open-source DataHub platform | Real mode connects to a DataHub Core/Cloud GMS endpoint | Boundary implemented; live smoke pending |
| At least one named component | `datahub-agent-context==1.6.0.17` is the production adapter | Installed, locked, contract-tested |
| Meaningful DataHub use | Entity, schema, downstream lineage, ownership, and query-use context drive the decision | Implemented |
| Agents that do real work | Generates PR-ready receipts and can save an approved decision for the next person/agent through `save_document` | Implementation and fail-closed live proof ready; public run pending |
| Public source and setup | Repo-ready source, tests, fixture, samples, docs, and workflow | Complete locally; public repo pending |
| Apache-2.0 | Top-level full license | Implemented |
| Free Project/test URL | Public repo will provide a clean-checkout, accountless fixture path; public workflow is supporting evidence | Judge path complete locally; publication pending |
| Sample outputs | Byte-checked JSON and Markdown receipts under `examples/` | Implemented |
| Functioning video under 3 minutes | Must show real DataHub context, not fixture-only claims | Pending live smoke |
| English submission materials | README, evidence, and requirement map are English | Implemented |
| AI/pre-existing work disclosure | AI coding assistance disclosed; no LostLine source copied, only workflow discipline reused | Implemented here |

## Eligibility and cost gate

- Official submission deadline: 2026-08-10 17:00 EDT / 2026-08-11 06:00 JST.
- Japan-resident adults are eligible absent the general sponsor/judge/conflict exclusions.
- No purchase or payment is required, and AI coding assistants are expressly allowed.
- No paid model API is used by the application. Its policy engine is deterministic.
- Public repo, video, workflow logs, and the 35-day synthetic proof are intended to remain free
  and accessible through the judging period ending August 31, 2026 at 17:00 ET.

## Resource gate

The pinned `acryl-datahub` quickstart CLI enforces at least 13 GiB of available Docker disk and
starts a multi-container stack. Local Docker remains disabled on the 8 GB development Mac. The
live smoke instead selects GitHub's standard public `ubuntu-24.04` runner, whose published
specification is 4 CPUs, 16 GB RAM, and 14 GB SSD. Standard runner minutes are not billed for a
public repository, subject to GitHub's ordinary usage limits. It installs only locked runtime
dependencies without a persistent uv cache, disables later uv re-syncs, caches, and Python
downloads, then requires at least 2 CPUs, 8 GiB RAM, and 13 GiB host-filesystem free space as an
early proxy before starting Core.

The pinned CLI independently performs the authoritative container-side Docker disk check. A billed
larger runner is never selected. If either measurement cannot satisfy the upstream guard, the
workflow stops fail-closed and the project remains fixture-verified only. Until one public run
succeeds, the application must not be represented as having completed real DataHub integration.
Because the CLI's internal disk probe currently uses `alpine:latest`, the workflow records that
probe image's resolved repository digest in the public run log.

GitHub runner specification: <https://docs.github.com/en/actions/reference/runners/github-hosted-runners>

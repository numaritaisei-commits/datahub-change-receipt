# DataHub Agent Hackathon requirements map

Checked against the official DataHub Devpost Overview and Rules on 2026-08-08 JST.

| Official requirement | Project evidence | Current state |
| --- | --- | --- |
| New working application | Independent package created during the submission period | Implemented locally |
| Open-source DataHub platform | Real mode connects to a DataHub Core/Cloud GMS endpoint | Boundary implemented; public proof is fixture/contract-only and makes no live claim |
| At least one named component | `datahub-agent-context==1.6.0.17` is used by the DataHub-mode adapter | Installed, locked, contract-tested; live endpoint execution not claimed |
| Meaningful DataHub use | Entity, schema, downstream lineage, ownership, and query-use context drive the decision | Implemented behind an Agent Context Kit adapter; fixture evidence stays explicitly non-live |
| Open / Wildcard category | Generates deterministic schema-change receipts and exposes an approval-gated `save_document` path without claiming a live write | Implementation and fail-closed boundary complete; live execution not claimed |
| Public source and setup | Public source, tests, fixture, samples, docs, and workflow | Complete at `https://github.com/numaritaisei-commits/datahub-change-receipt` |
| Apache-2.0 | Top-level full license | Implemented |
| Free Project/test URL | Public repo provides a clean-checkout, accountless fixture path; public CI is supporting evidence | Complete; current public lightweight verification passes |
| Sample outputs | Byte-checked JSON and Markdown receipts under `examples/` | Implemented |
| Functioning video under 3 minutes | Public 1:59 demo shows the functioning synthetic fixture path and labels `real_datahub_verified: false` | Complete at `https://youtu.be/9wlVUFmJXIU`; no live claim |
| English submission materials | README, evidence, and requirement map are English | Implemented |
| AI/pre-existing work disclosure | AI coding assistance disclosed; no LostLine source copied, only workflow discipline reused | Implemented here |

## Eligibility and cost gate

- Official submission deadline: 2026-08-10 17:00 EDT / 2026-08-11 06:00 JST.
- Japan-resident adults are eligible absent the general sponsor/judge/conflict exclusions.
- No purchase or payment is required, and AI coding assistants are expressly allowed.
- No paid model API is used by the application. Its policy engine is deterministic.
- Public repo, video, workflow logs, and committed synthetic sample artifacts are intended to
  remain free and accessible through the judging period ending August 31, 2026 at 17:00 ET.

## Resource gate

The pinned `acryl-datahub` quickstart CLI enforces at least 13 GiB of available Docker disk and
starts a multi-container stack. Local Docker remains disabled on the 8 GB development Mac.
GitHub documents only 14 GB SSD for its free standard runner, leaving no safe documented margin
for checkout, runtime installation, Docker metadata, Core images, volumes, and teardown. The
manual live workflow therefore has not been dispatched. A billed larger runner is never selected,
and the upstream guard is not lowered or bypassed. The public project remains fixture/contract
verified only and must not be represented as having completed real DataHub retrieval, write-back,
or cleanup.

GitHub runner specification: <https://docs.github.com/en/actions/reference/runners/github-hosted-runners>

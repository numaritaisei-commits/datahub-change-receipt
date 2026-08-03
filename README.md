# DataHub Change Receipt

[![verify](https://github.com/numaritaisei-commits/datahub-change-receipt/actions/workflows/verify.yml/badge.svg)](https://github.com/numaritaisei-commits/datahub-change-receipt/actions/workflows/verify.yml)

DataHub Change Receipt is a deterministic pre-merge agent that turns a proposed schema
change into a reviewable evidence bundle. It gathers schema, ownership, downstream lineage,
and query-use context through the open-source **DataHub Agent Context Kit**, then produces a
stable `PASS`, `WARN`, `BLOCK`, or `INSUFFICIENT_CONTEXT` decision with JSON and Markdown
receipts.

The project is intentionally different from a lineage chatbot: it creates a reproducible
artifact for a pull request, minimizes raw query exposure, and can persist the decision for
the next person or agent only behind an explicit approval gate.

For a concrete reviewer workflow, consider a pull request that drops `legacy_status` from an
orders dataset. The agent checks the real catalog identity, schema, downstream lineage, owners,
and query-use signals before producing a stable decision that a data-platform reviewer can
attach to the change review.

## Evidence boundary

- `fixture` mode is deterministic, secret-free, and suitable for unit tests and UI/demo work.
  It proves the policy engine and adapter contract only.
- `datahub` mode uses the official Agent Context Kit against a reachable DataHub Core or
  DataHub Cloud GMS endpoint. A URL and personal access token are required for secured
  deployments.
- No real DataHub connection has been claimed until the separately recorded live smoke test
  succeeds. Fixture output is always labeled `real_datahub_verified: false`.
- The full DataHub Core quickstart is not started by this repository's default test command.

## Development status

The local publication candidate includes the application, deterministic fixture path, real
DataHub adapter, approval-gated decision write-back, tests, sample outputs, and a fail-closed
manual live workflow. The public live workflow has not run yet, so no live-success claim is
made. See [the requirements map](docs/REQUIREMENTS.md), [evidence ledger](docs/EVIDENCE.md),
and [live-proof boundary](docs/LIVE_SMOKE.md).

## Why this is DataHub-native

For each proposed change, the real adapter invokes Agent Context Kit tools to collect:

1. `get_entities` for identity and ownership;
2. `list_schema_fields` for the exact changed columns;
3. `get_lineage` for a bounded downstream blast radius; and
4. `get_dataset_queries` for column-use evidence.

The agent does not persist raw SQL in receipts or normal CLI logs. Returned statements are
immediately turned into short SHA-256 fingerprints. Missing catalog evidence cannot silently
become a pass: destructive changes with missing entity, schema, lineage, or query context return
`INSUFFICIENT_CONTEXT`.

## Judge quick path — free and accountless (macOS/Linux/POSIX shell)

The fixture demonstration requires only Python 3.11+ and
[uv](https://docs.astral.sh/uv/). It needs no DataHub account, token, model API, paid service,
or Docker stack. First setup downloads locked open-source packages from PyPI. From a clean
checkout:

```bash
git clone https://github.com/numaritaisei-commits/datahub-change-receipt.git
cd datahub-change-receipt
uv sync --locked --all-groups
uv run datahub-change-receipt \
  --request examples/change-request.json \
  --fixture fixtures/catalog-context.json \
  --json-out /tmp/change-receipt.json \
  --markdown-out /tmp/change-receipt.md
diff -u examples/receipt.json /tmp/change-receipt.json
diff -u examples/receipt.md /tmp/change-receipt.md
sed -n '1,9p' /tmp/change-receipt.md
```

The demo is designed to return `BLOCK`: a dropped column has both synthetic `SYSTEM` query-use and
downstream-lineage evidence. That proves the fail-closed path rather than optimizing a fixture
for a favorable answer. The committed [JSON receipt](examples/receipt.json) and
[Markdown receipt](examples/receipt.md) let judges inspect the output before installing
anything. The expected header contains receipt `dcr-d191ab33d00bfdd9`, decision `BLOCK`, evidence
mode `fixture`, and `Real DataHub verified: false`. Fixture mode never masquerades as the
separate live DataHub proof.

The local toolchain is tested with Python 3.12 and uv 0.11.26; clean GitHub CI is configured for
Python 3.11 and the same locked dependency graph.

## Judge access

- The public repository itself is the Project/test URL and contains the complete free CLI path,
  source, fixtures, samples, tests, workflows, and setup instructions.
- The successful public live workflow run is supporting provenance for the DataHub-native path,
  not a substitute for the runnable judge quick path. Its manual write-back job is
  maintainer-only; judges are not asked to provide a token or dispatch it.
- The repository, public demo video, successful workflow logs, and synthetic proof artifact will
  remain publicly accessible and free through the judging period ending August 31, 2026.

## Run lightweight verification

```bash
uv run ruff check .
uv run mypy
uv run pytest
```

No Docker service, model API, card, or cloud account is used by these checks.

## Run the isolated live proof

The manual `live DataHub Core smoke` GitHub Actions workflow is deliberately separate from
normal CI. It can run only in the expected public repository and starts a pinned open-source
DataHub Core quickstart on an ephemeral standard runner after CPU, memory, and disk checks.
It seeds synthetic metadata, runs this application through the real Agent Context Kit,
mechanically verifies entity/schema/lineage evidence, and uploads a 35-day synthetic receipt.
The dispatch requires an explicit write-back boolean; the CLI and provider independently repeat
the approval/evidence gate before creating one synthetic decision through `save_document`. A
second process reads it back, verifies its content and asset relation, and deletes it. Cleanup is
attempted on every path, and a green run additionally requires zero remaining Core containers.

After the public repository exists, the intentionally manual invocation is:

```bash
gh workflow run live-datahub-smoke.yml \
  --repo numaritaisei-commits/datahub-change-receipt \
  --ref main \
  -f approve_synthetic_write_back=true
```

This workflow has not yet passed, so this repository does **not** currently claim a successful
live DataHub connection. A successful claim requires the linked public workflow run and its
exact head SHA, not the receipt boolean alone. See [docs/LIVE_SMOKE.md](docs/LIVE_SMOKE.md) for
the exact boundary.

## Connect a real DataHub instance

Configure the official SDK environment without committing the values:

```bash
# Set both values in the current shell from your official DataHub instance.
export DATAHUB_GMS_URL
export DATAHUB_GMS_TOKEN
uv run datahub-change-receipt \
  --mode datahub \
  --request examples/change-request.json \
  --json-out receipts/live.json \
  --markdown-out receipts/live.md
```

Use a least-privilege read token. The normal command is read-only. Optional `save_document`
write-back requires a verified live bundle *and* the explicit `--approve-write-back` flag;
never use that flag without reviewing the generated Markdown and authorizing the write. The
CLI also requires `--write-back-urn-out` so a separate process can verify the created entity
without exposing its identifier in normal logs.

## Originality and assistance disclosure

The differentiator is the combination of a deterministic fail-closed receipt, an explicit
fixture-versus-live evidence boundary, immediate query minimization, and approval-gated decision
memory beside the affected DataHub asset. Rather than creating another catalog chat surface, the
project produces an inspectable engineering artifact with a separately verified read/write
boundary.

This project was created during the DataHub Agent Hackathon submission period with AI coding
assistance. No source code or product logic from an earlier project was incorporated; only
general development discipline such as small deterministic tests and explicit evidence
boundaries was reused.

## License

Apache License 2.0. See [LICENSE](LICENSE).

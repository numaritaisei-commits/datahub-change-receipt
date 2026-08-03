# Live DataHub Core smoke

The manual `live DataHub Core smoke` workflow is the only automated path that may claim
`real_datahub_verified: true`. It is intentionally not triggered by pushes or pull requests:
it runs only through `workflow_dispatch`, only in the expected public repository, and uses
only the standard public GitHub-hosted runner.

## Safety and cost boundary

- The workflow uses no repository secret, cloud credential, paid API, card, or external
  DataHub account.
- It starts the official open-source DataHub Core quickstart only inside an ephemeral
  GitHub-hosted runner. Local Docker is not part of this path.
- It uses GitHub's standard public `ubuntu-24.04` runner (4 CPUs, 16 GB RAM, and 14 GB
  SSD in GitHub's published specification). Standard runner minutes are not billed for public
  repositories (normal GitHub usage limits still apply); the workflow never selects a billed
  larger runner.
- It installs only the locked runtime dependency set with uv's cache disabled. The separate
  verification workflow owns lint, type checking, and tests, so their development dependencies
  do not consume the live runner's constrained disk. Every later `uv run` uses `--no-sync` and
  `--no-cache`, reinforced by job-level uv guards, so it cannot silently restore the default
  development group, retain a cache, or download another Python runtime.
- An early host preflight rejects the runner before invoking quickstart unless it has at least
  2 CPUs, 8 GiB of memory, and 13 GiB of free disk space. The disk threshold matches the guard
  enforced by the pinned `acryl-datahub` quickstart CLI; lowering only this workflow's check
  would not make Core start.
  The host-filesystem measurement after runtime installation is an early proxy; the pinned CLI's
  container-side Docker measurement is authoritative. If either check fails, DataHub Core does
  not start and the run makes no live-proof claim. The CLI's internal probe currently uses a
  mutable `alpine:latest` tag, so the workflow records the resolved repository digest from the
  exact run rather than implying that this helper image is pinned.
- It seeds three synthetic datasets and two synthetic lineage edges. No user data, email,
  source database, or private query is sent.
- The runner receives no DataHub token. It talks only to its own `localhost` quickstart.
- The workflow will not start unless its required `approve_synthetic_write_back` boolean is
  explicitly true. The application independently requires `--approve-write-back`, and the
  provider independently rejects unverified evidence.
- The created child document is read back, content-hash and asset-relation verified, and hard
  deleted. A second `always()` cleanup handles interruption before the final quickstart cleanup.
- The final `always()` cleanup stops the quickstart and fails if any container remains.
- The proof artifact is synthetic, retained for 35 days so it remains available through judging,
  and contains no credential or document
  identifier; its write-back evidence contains booleans only.

## What counts as a passing proof

After seeding, the normal application runs in `datahub` mode through the official Agent
Context Kit. A separate verifier accepts the receipt only when all of the following are true:

1. `source_mode` is `datahub` and `real_datahub_verified` is true;
2. the target URN is the seeded DataHub entity;
3. the four expected schema fields came back from DataHub;
4. the seeded downstream dataset came back through lineage; and
5. entity, schema, and lineage lookups report no gap.

Only after that read proof succeeds, the approved write-back phase creates one `Decision` via
the official Agent Context Kit `save_document` tool. A second process must retrieve the strict
random synthetic Document URN and verify the exact title, `Decision` subtype, published/global
settings, Shared parent, related target dataset, and SHA-256 content digest. It then hard-deletes
only that strict synthetic child and proves the entity is absent. The URN is kept in a private
temporary file only long enough to support verification and cleanup and is never an artifact.
Before mutation the CLI fsyncs a private `write_attempted` marker. If the process stops before
the marker can be replaced with the created URN, per-document cleanup deliberately fails rather
than claiming success; the final fail-closed Core teardown then removes the entire ephemeral
stack.

Indexing is allowed four bounded attempts with increasing waits. Failure remains a failed
workflow; it never falls back to fixture evidence. Query-use context can legitimately be
empty in a synthetic Core instance, but the application still invokes that Agent Context
Kit tool and reports any lookup gap in the receipt.

## Current evidence status

The workflow is implemented and locally validated, but it has **not yet been executed on a
public GitHub-hosted runner**. Until an official run passes, fixture output remains labeled
`real_datahub_verified: false` and no submission material may describe live DataHub retrieval
or write-back as successful.

The workflow is maintainer-dispatched because it intentionally performs one approved synthetic
write. Judges are not expected to dispatch it or provide a credential. Submission-grade
provenance is the public successful run at the exact repository head plus the synthetic receipt,
boolean write-back proof, and green cleanup steps; the free accountless fixture path remains the
direct judge test path.

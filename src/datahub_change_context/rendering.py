"""Receipt renderers."""

from __future__ import annotations

import json

from datahub_change_context.models import Receipt


def render_json(receipt: Receipt) -> str:
    return json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n"


def render_markdown(receipt: Receipt) -> str:
    lines = [
        f"# DataHub Change Receipt `{receipt.receipt_id}`",
        "",
        f"- Decision: **{receipt.decision.value}**",
        f"- Risk score: **{receipt.risk_score}/100**",
        f"- Change: `{receipt.request.change_id}`",
        f"- Asset: `{receipt.request.asset_urn}`",
        f"- Evidence mode: `{receipt.evidence.source_mode}`",
        f"- Real DataHub verified: `{str(receipt.evidence.real_datahub_verified).lower()}`",
        "",
        "## Reasons",
        "",
    ]
    lines.extend(f"- {reason}" for reason in receipt.reasons)
    lines.extend(["", "## Proposed changes", ""])
    for change in receipt.request.changes:
        target = f" → `{change.to}`" if change.to else ""
        lines.append(f"- `{change.kind.value}` `{change.column}`{target}")

    lines.extend(["", "## Downstream evidence", ""])
    if receipt.evidence.downstream_assets:
        for asset in receipt.evidence.downstream_assets:
            owners = ", ".join(asset.owners) if asset.owners else "unowned"
            lines.append(
                f"- hop {asset.degree}: `{asset.urn}` ({asset.entity_type}; owners: {owners})"
            )
    else:
        lines.append("- No downstream assets returned.")

    lines.extend(["", "## Privacy-minimized query evidence", ""])
    if receipt.evidence.query_signals:
        for signal in receipt.evidence.query_signals:
            lines.append(f"- `{signal.column}` / `{signal.source}` / `{signal.fingerprint}`")
    else:
        lines.append("- No query-use signals returned.")

    lines.extend(["", "## Recommended checks", ""])
    if receipt.recommended_checks:
        lines.extend(f"- {check}" for check in receipt.recommended_checks)
    else:
        lines.append("- None beyond the normal change-review process.")

    lines.extend(
        [
            "",
            "## Evidence boundary",
            "",
            "Fixture mode validates deterministic behavior only. It is not evidence of a live "
            "DataHub connection. A real integration claim requires `real_datahub_verified: true` "
            "from a separately recorded smoke test against DataHub Core or Cloud.",
            "",
        ]
    )
    return "\n".join(lines)

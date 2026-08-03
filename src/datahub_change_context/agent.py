"""Deterministic evidence collection and policy evaluation."""

from __future__ import annotations

import hashlib
import json

from datahub_change_context.models import (
    ChangeKind,
    ChangeRequest,
    Decision,
    EvidenceBundle,
    Receipt,
)
from datahub_change_context.provider import ContextProvider

_DESTRUCTIVE = {ChangeKind.DROP, ChangeKind.RENAME, ChangeKind.TYPE_CHANGE}


class ChangeReceiptAgent:
    """Produces a stable review receipt without requiring an LLM or paid API."""

    def __init__(self, provider: ContextProvider) -> None:
        self._provider = provider

    def review(self, request: ChangeRequest) -> Receipt:
        evidence = self._provider.collect(request)
        decision, risk_score, reasons, checks = _evaluate(request, evidence)
        receipt_id = _receipt_id(request, evidence)
        return Receipt(
            receipt_id=receipt_id,
            request=request,
            decision=decision,
            risk_score=risk_score,
            reasons=tuple(reasons),
            recommended_checks=tuple(checks),
            evidence=evidence,
        )


def _evaluate(
    request: ChangeRequest, evidence: EvidenceBundle
) -> tuple[Decision, int, list[str], list[str]]:
    reasons: list[str] = []
    checks: list[str] = []
    hard_gaps = [
        gap
        for gap in evidence.gaps
        if gap.startswith(("entity_", "schema_", "lineage_", "query_context_"))
    ]

    if evidence.entity is None:
        hard_gaps.append("entity_context_missing")
    elif any(change.kind in _DESTRUCTIVE for change in request.changes):
        fields = set(evidence.entity.schema_fields)
        for change in request.changes:
            if change.kind in _DESTRUCTIVE and change.column not in fields:
                hard_gaps.append(f"schema_changed_column_missing:{change.column}")

    if hard_gaps:
        unique_gaps = sorted(set(hard_gaps))
        reasons.extend(f"Missing required evidence: {gap}" for gap in unique_gaps)
        checks.append("Resolve every evidence gap against a reachable DataHub instance.")
        return Decision.INSUFFICIENT_CONTEXT, 100, reasons, checks

    risk = 0
    weights = {
        ChangeKind.ADD: 0,
        ChangeKind.DROP: 40,
        ChangeKind.RENAME: 25,
        ChangeKind.TYPE_CHANGE: 30,
    }
    for change in request.changes:
        weight = weights[change.kind]
        risk += weight
        if weight:
            reasons.append(f"{change.kind.value} on `{change.column}` adds {weight} risk points.")

    downstream_count = len(evidence.downstream_assets)
    if downstream_count:
        downstream_risk = min(30, downstream_count * 5)
        risk += downstream_risk
        reasons.append(f"{downstream_count} downstream asset(s) add {downstream_risk} risk points.")
        checks.append("Notify the listed downstream owners and attach their validation evidence.")

    unowned = sum(not asset.owners for asset in evidence.downstream_assets)
    if unowned:
        risk += 10
        reasons.append(f"{unowned} downstream asset(s) have no owner in the collected context.")
        checks.append("Assign or identify owners for unowned downstream assets.")

    system_signals = [signal for signal in evidence.query_signals if signal.source == "SYSTEM"]
    manual_signals = [signal for signal in evidence.query_signals if signal.source == "MANUAL"]
    if system_signals:
        query_risk = min(30, len(system_signals) * 10)
        risk += query_risk
        reasons.append(
            f"{len(system_signals)} production query signal(s) add {query_risk} risk points."
        )
        checks.append("Run regression checks for every production query fingerprint.")
    if manual_signals:
        query_risk = min(15, len(manual_signals) * 5)
        risk += query_risk
        reasons.append(
            f"{len(manual_signals)} manual query signal(s) add {query_risk} risk points."
        )

    destructive_columns = {
        change.column for change in request.changes if change.kind in _DESTRUCTIVE
    }
    system_hit = any(signal.column in destructive_columns for signal in system_signals)
    if system_hit or risk >= 70:
        decision = Decision.BLOCK
    elif risk >= 20 or downstream_count:
        decision = Decision.WARN
    else:
        decision = Decision.PASS
        reasons.append(
            "No material downstream or query-use risk was found in the collected context."
        )

    if decision is not Decision.PASS:
        checks.append("Re-run the receipt after mitigations; do not override missing evidence.")
    return decision, min(risk, 100), reasons, checks


def _receipt_id(request: ChangeRequest, evidence: EvidenceBundle) -> str:
    canonical = json.dumps(
        {"request": request.to_dict(), "evidence": evidence.to_dict()},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"dcr-{hashlib.sha256(canonical).hexdigest()[:16]}"

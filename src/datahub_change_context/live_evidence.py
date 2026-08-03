"""Fail-closed verification for the synthetic live DataHub receipt."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from datahub_change_context.demo_seed import DOWNSTREAM_URN, TARGET_URN

EXPECTED_SCHEMA_FIELDS = frozenset({"order_id", "customer_id", "legacy_status", "order_total"})
EXPECTED_CHANGE_ID = "synthetic-live-orders-v2"
CRITICAL_GAP_PREFIXES = ("entity_", "schema_", "lineage_")


class LiveEvidenceError(ValueError):
    """Raised when a receipt cannot prove the required live DataHub boundary."""


def load_and_verify(path: Path) -> None:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LiveEvidenceError("receipt root is invalid")
    verify_live_receipt({str(key): value for key, value in raw.items()})


def verify_live_receipt(receipt: Mapping[str, object]) -> None:
    evidence = _mapping(receipt.get("evidence"))
    request = _mapping(receipt.get("request"))
    entity = _mapping(evidence.get("entity"))

    if evidence.get("source_mode") != "datahub":
        raise LiveEvidenceError("source mode is not live DataHub")
    if receipt.get("decision") != "BLOCK":
        raise LiveEvidenceError("synthetic destructive change did not fail closed")
    if request.get("change_id") != EXPECTED_CHANGE_ID:
        raise LiveEvidenceError("change ID does not match the synthetic live request")
    if evidence.get("real_datahub_verified") is not True:
        raise LiveEvidenceError("live DataHub evidence is not verified")
    if request.get("asset_urn") != TARGET_URN or entity.get("urn") != TARGET_URN:
        raise LiveEvidenceError("target DataHub entity does not match the synthetic request")

    fields = _required_string_set(entity.get("schema_fields"), "schema fields")
    if not EXPECTED_SCHEMA_FIELDS.issubset(fields):
        raise LiveEvidenceError("required live schema fields were not retrieved")

    raw_downstream = evidence.get("downstream_assets")
    if not isinstance(raw_downstream, list):
        raise LiveEvidenceError("live downstream lineage is missing")
    if any(not isinstance(item, dict) for item in raw_downstream):
        raise LiveEvidenceError("live downstream lineage is malformed")
    downstream_urns = {urn for item in raw_downstream if (urn := _string(item.get("urn")))}
    if DOWNSTREAM_URN not in downstream_urns:
        raise LiveEvidenceError("synthetic downstream lineage was not retrieved")

    gaps = _required_string_set(evidence.get("gaps"), "evidence gaps")
    if any(gap.startswith(CRITICAL_GAP_PREFIXES) for gap in gaps):
        raise LiveEvidenceError("a required live DataHub lookup reported a gap")


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _required_string_set(value: object, label: str) -> set[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise LiveEvidenceError(f"{label} are malformed")
    return set(value)


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""

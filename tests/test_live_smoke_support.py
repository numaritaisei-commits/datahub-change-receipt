from __future__ import annotations

from typing import cast

import pytest
from datahub.sdk.dataset import Dataset
from datahub.sdk.main_client import DataHubClient

from datahub_change_context.demo_seed import (
    DOWNSTREAM_URN,
    TARGET_URN,
    build_demo_datasets,
    seed_demo,
)
from datahub_change_context.live_evidence import LiveEvidenceError, verify_live_receipt


def _live_receipt() -> dict[str, object]:
    return {
        "decision": "BLOCK",
        "request": {
            "asset_urn": TARGET_URN,
            "change_id": "synthetic-live-orders-v2",
        },
        "evidence": {
            "source_mode": "datahub",
            "real_datahub_verified": True,
            "entity": {
                "urn": TARGET_URN,
                "schema_fields": [
                    "order_id",
                    "customer_id",
                    "legacy_status",
                    "order_total",
                ],
            },
            "downstream_assets": [{"urn": DOWNSTREAM_URN}],
            "gaps": ["query_context_lookup_failed:legacy_status"],
        },
    }


def test_demo_datasets_have_expected_live_graph() -> None:
    raw, target, downstream = build_demo_datasets()

    assert str(target.urn) == TARGET_URN
    assert str(downstream.urn) == DOWNSTREAM_URN
    assert target.upstreams is not None
    assert downstream.upstreams is not None
    assert [item.dataset for item in target.upstreams.upstreams] == [str(raw.urn)]
    assert [item.dataset for item in downstream.upstreams.upstreams] == [TARGET_URN]


def test_seed_demo_checks_connection_and_upserts_only_synthetic_graph() -> None:
    class FakeEntities:
        def __init__(self) -> None:
            self.seen: list[Dataset] = []

        def upsert(self, entity: Dataset) -> None:
            self.seen.append(entity)

    class FakeClient:
        def __init__(self) -> None:
            self.connection_checked = False
            self.entities = FakeEntities()

        def test_connection(self) -> None:
            self.connection_checked = True

    fake = FakeClient()
    urns = seed_demo(cast(DataHubClient, fake))

    assert fake.connection_checked is True
    assert tuple(str(entity.urn) for entity in fake.entities.seen) == urns
    assert len(urns) == 3
    assert TARGET_URN in urns
    assert DOWNSTREAM_URN in urns


def test_live_receipt_accepts_required_datahub_evidence() -> None:
    verify_live_receipt(_live_receipt())


def test_live_receipt_rejects_fixture_label() -> None:
    receipt = _live_receipt()
    evidence = receipt["evidence"]
    assert isinstance(evidence, dict)
    evidence["source_mode"] = "fixture"
    evidence["real_datahub_verified"] = False

    with pytest.raises(LiveEvidenceError):
        verify_live_receipt(receipt)


def test_live_receipt_rejects_missing_lineage() -> None:
    receipt = _live_receipt()
    evidence = receipt["evidence"]
    assert isinstance(evidence, dict)
    evidence["downstream_assets"] = []

    with pytest.raises(LiveEvidenceError):
        verify_live_receipt(receipt)


@pytest.mark.parametrize("malformed", [None, "none", ["lineage_ok", 7]])
def test_live_receipt_rejects_malformed_gap_evidence(malformed: object) -> None:
    receipt = _live_receipt()
    evidence = receipt["evidence"]
    assert isinstance(evidence, dict)
    evidence["gaps"] = malformed

    with pytest.raises(LiveEvidenceError):
        verify_live_receipt(receipt)


def test_live_receipt_rejects_malformed_lineage_entry() -> None:
    receipt = _live_receipt()
    evidence = receipt["evidence"]
    assert isinstance(evidence, dict)
    evidence["downstream_assets"] = [{"urn": DOWNSTREAM_URN}, "invalid"]

    with pytest.raises(LiveEvidenceError):
        verify_live_receipt(receipt)


def test_live_receipt_rejects_critical_lookup_gap() -> None:
    receipt = _live_receipt()
    evidence = receipt["evidence"]
    assert isinstance(evidence, dict)
    evidence["gaps"] = ["schema_lookup_failed"]

    with pytest.raises(LiveEvidenceError):
        verify_live_receipt(receipt)


def test_live_receipt_requires_fail_closed_policy_result() -> None:
    receipt = _live_receipt()
    receipt["decision"] = "PASS"

    with pytest.raises(LiveEvidenceError):
        verify_live_receipt(receipt)


def test_live_receipt_requires_exact_synthetic_change_id() -> None:
    receipt = _live_receipt()
    request = receipt["request"]
    assert isinstance(request, dict)
    request["change_id"] = "unexpected"

    with pytest.raises(LiveEvidenceError):
        verify_live_receipt(receipt)

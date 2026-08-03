from __future__ import annotations

import json
from pathlib import Path

import pytest

from datahub_change_context.agent import ChangeReceiptAgent
from datahub_change_context.fixture_provider import FixtureContextProvider
from datahub_change_context.models import ChangeRequest, Decision
from datahub_change_context.rendering import render_json, render_markdown

ROOT = Path(__file__).parents[1]


def _request() -> ChangeRequest:
    raw: object = json.loads((ROOT / "examples/change-request.json").read_text())
    assert isinstance(raw, dict)
    return ChangeRequest.from_mapping(raw)


def _provider() -> FixtureContextProvider:
    return FixtureContextProvider.from_path(ROOT / "fixtures/catalog-context.json")


def test_fixture_review_is_deterministic_and_blocks_used_drop() -> None:
    agent = ChangeReceiptAgent(_provider())

    first = agent.review(_request())
    second = agent.review(_request())

    assert first == second
    assert first.decision is Decision.BLOCK
    assert first.risk_score == 100
    assert first.evidence.real_datahub_verified is False
    assert len(first.evidence.downstream_assets) == 2
    assert {signal.source for signal in first.evidence.query_signals} == {"MANUAL", "SYSTEM"}


def test_receipts_expose_fingerprints_but_never_raw_sql() -> None:
    receipt = ChangeReceiptAgent(_provider()).review(_request())
    rendered = render_json(receipt) + render_markdown(receipt)

    assert "fixture:system-status-filter-001" in rendered
    assert "SELECT " not in rendered.upper()
    assert "Real DataHub verified: `false`" in rendered


def test_committed_sample_outputs_match_the_current_renderer() -> None:
    receipt = ChangeReceiptAgent(_provider()).review(_request())

    assert render_json(receipt) == (ROOT / "examples/receipt.json").read_text(encoding="utf-8")
    assert render_markdown(receipt) == (ROOT / "examples/receipt.md").read_text(encoding="utf-8")


def test_missing_destructive_column_returns_insufficient_context() -> None:
    request = ChangeRequest.from_mapping(
        {
            "change_id": "missing-column",
            "asset_urn": _request().asset_urn,
            "changes": [{"column": "not_in_catalog", "kind": "drop"}],
        }
    )

    receipt = ChangeReceiptAgent(_provider()).review(request)

    assert receipt.decision is Decision.INSUFFICIENT_CONTEXT
    assert any("schema_changed_column_missing" in reason for reason in receipt.reasons)


def test_duplicate_source_columns_are_rejected() -> None:
    with pytest.raises(ValueError, match="only once"):
        ChangeRequest.from_mapping(
            {
                "change_id": "duplicate",
                "asset_urn": _request().asset_urn,
                "changes": [
                    {"column": "legacy_status", "kind": "drop"},
                    {"column": "legacy_status", "kind": "rename", "to": "status"},
                ],
            }
        )


def test_fixture_mode_cannot_write_back() -> None:
    provider = _provider()
    receipt = ChangeReceiptAgent(provider).review(_request())

    with pytest.raises(RuntimeError, match="never write"):
        provider.write_receipt(receipt, render_markdown(receipt), approved=True)

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

import pytest
from datahub.sdk.main_client import DataHubClient

import datahub_change_context.datahub_provider as adapter
from datahub_change_context.agent import ChangeReceiptAgent
from datahub_change_context.models import ChangeRequest, Decision
from datahub_change_context.rendering import render_markdown

URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.orders,PROD)"


@contextmanager
def _fake_context(client: DataHubClient) -> Iterator[DataHubClient]:
    yield client


def _fake_get_entities(urns: list[str]) -> list[dict[str, object]]:
    assert urns == [URN]
    return [
        {
            "urn": URN,
            "type": "DATASET",
            "properties": {"name": "analytics.orders"},
            "ownership": {"owners": [{"owner": {"urn": "urn:li:corpGroup:data-platform"}}]},
        }
    ]


def _fake_schema(*args: object, **kwargs: object) -> dict[str, object]:
    del args, kwargs
    return {
        "urn": URN,
        "fields": [{"fieldPath": "legacy_status"}, {"fieldPath": "order_id"}],
    }


def _fake_lineage(**kwargs: object) -> dict[str, object]:
    assert kwargs["upstream"] is False
    return {
        "downstreams": {
            "searchResults": [
                {
                    "degree": "1",
                    "entity": {
                        "urn": "urn:li:dashboard:(looker,operations)",
                        "type": "DASHBOARD",
                        "properties": {"name": "Operations"},
                        "ownership": {"owners": []},
                    },
                }
            ]
        }
    }


def _fake_queries(**kwargs: object) -> dict[str, object]:
    assert kwargs["column"] == "legacy_status"
    return {
        "queries": [
            {
                "properties": {
                    "source": "SYSTEM",
                    "statement": {"value": "SELECT legacy_status FROM analytics.orders"},
                }
            }
        ]
    }


def _malformed_response(*args: object, **kwargs: object) -> dict[str, object]:
    del args, kwargs
    return {}


def _wrong_entity_response(*args: object, **kwargs: object) -> list[dict[str, object]]:
    del args, kwargs
    return [{"urn": "urn:li:dataset:(urn:li:dataPlatform:snowflake,wrong,PROD)"}]


def _extra_entity_response(*args: object, **kwargs: object) -> list[dict[str, object]]:
    del args, kwargs
    return _fake_get_entities([URN]) * 2


def _wrong_schema_response(*args: object, **kwargs: object) -> dict[str, object]:
    del args, kwargs
    return {
        "urn": "urn:li:dataset:(urn:li:dataPlatform:snowflake,wrong,PROD)",
        "fields": [{"fieldPath": "legacy_status"}],
    }


def _unknown_query_source(*args: object, **kwargs: object) -> dict[str, object]:
    del args, kwargs
    response = _fake_queries(column="legacy_status")
    queries = response["queries"]
    assert isinstance(queries, list)
    query = queries[0]
    assert isinstance(query, dict)
    properties = query["properties"]
    assert isinstance(properties, dict)
    properties["source"] = "UNKNOWN"
    return response


def _request() -> ChangeRequest:
    return ChangeRequest.from_mapping(
        {
            "change_id": "contract",
            "asset_urn": URN,
            "changes": [{"column": "legacy_status", "kind": "drop"}],
        }
    )


def _provider_with_valid_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> adapter.DataHubAgentContextProvider:
    monkeypatch.setattr(adapter, "DataHubContext", _fake_context)
    monkeypatch.setattr(adapter, "get_entities", _fake_get_entities)
    monkeypatch.setattr(adapter, "list_schema_fields", _fake_schema)
    monkeypatch.setattr(adapter, "get_lineage", _fake_lineage)
    monkeypatch.setattr(adapter, "get_dataset_queries", _fake_queries)
    return adapter.DataHubAgentContextProvider(cast(DataHubClient, object()))


def test_official_adapter_contract_minimizes_query_text(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider_with_valid_tools(monkeypatch)

    evidence = provider.collect(_request())

    assert evidence.real_datahub_verified is True
    assert evidence.gaps == ()
    assert evidence.query_signals[0].fingerprint.startswith("sha256:")
    assert "SELECT" not in repr(evidence)


@pytest.mark.parametrize(
    ("tool_name", "replacement", "expected_gap", "verified"),
    [
        ("get_entities", _malformed_response, "entity_lookup_failed", False),
        ("get_entities", _wrong_entity_response, "entity_lookup_failed", False),
        ("get_entities", _extra_entity_response, "entity_lookup_failed", False),
        ("list_schema_fields", _malformed_response, "schema_lookup_failed", False),
        ("list_schema_fields", _wrong_schema_response, "schema_lookup_failed", False),
        ("get_lineage", _malformed_response, "lineage_lookup_failed", False),
        (
            "get_dataset_queries",
            _malformed_response,
            "query_context_lookup_failed:legacy_status",
            True,
        ),
        (
            "get_dataset_queries",
            _unknown_query_source,
            "query_context_lookup_failed:legacy_status",
            True,
        ),
    ],
)
def test_official_adapter_rejects_malformed_tool_responses(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    replacement: object,
    expected_gap: str,
    verified: bool,
) -> None:
    provider = _provider_with_valid_tools(monkeypatch)
    monkeypatch.setattr(adapter, tool_name, replacement)

    evidence = provider.collect(_request())
    receipt = ChangeReceiptAgent(provider).review(_request())

    assert expected_gap in evidence.gaps
    assert evidence.real_datahub_verified is verified
    assert receipt.decision is Decision.INSUFFICIENT_CONTEXT


def test_write_back_requires_approval_without_calling_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider_with_valid_tools(monkeypatch)
    receipt = ChangeReceiptAgent(provider).review(_request())
    calls = 0

    def fake_save_document(**kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"success": True, "urn": "urn:li:document:shared-unused"}

    monkeypatch.setattr(adapter, "save_document", fake_save_document)

    with pytest.raises(PermissionError, match="explicit approval"):
        provider.write_receipt(receipt, render_markdown(receipt), approved=False)

    assert calls == 0


def test_write_back_requires_verified_live_evidence_without_calling_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider_with_valid_tools(monkeypatch)
    monkeypatch.setattr(adapter, "get_entities", _malformed_response)
    receipt = ChangeReceiptAgent(provider).review(_request())
    calls = 0

    def fake_save_document(**kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"success": True, "urn": "urn:li:document:shared-unused"}

    monkeypatch.setattr(adapter, "save_document", fake_save_document)

    with pytest.raises(RuntimeError, match="verified real DataHub"):
        provider.write_receipt(receipt, render_markdown(receipt), approved=True)

    assert calls == 0


def test_write_back_calls_official_tool_with_exact_decision_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider_with_valid_tools(monkeypatch)
    receipt = ChangeReceiptAgent(provider).review(_request())
    markdown = render_markdown(receipt)
    captured: dict[str, object] = {}
    document_urn = "urn:li:document:shared-12345678-1234-4123-8123-123456789abc"

    def fake_save_document(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"success": True, "urn": document_urn}

    monkeypatch.setattr(adapter, "save_document", fake_save_document)

    assert provider.write_receipt(receipt, markdown, approved=True) == document_urn
    assert captured == {
        "document_type": "Decision",
        "title": "Change receipt contract",
        "content": markdown,
        "topics": ["change-review", "lineage", "block"],
        "related_assets": [URN],
    }


@pytest.mark.parametrize(
    "result",
    [
        {},
        {"success": False, "urn": "urn:li:document:shared-unused"},
        {"success": True},
        {"success": True, "urn": ""},
        "malformed",
    ],
)
def test_write_back_rejects_unconfirmed_tool_results(
    monkeypatch: pytest.MonkeyPatch,
    result: object,
) -> None:
    provider = _provider_with_valid_tools(monkeypatch)
    receipt = ChangeReceiptAgent(provider).review(_request())

    def fake_save_document(**kwargs: object) -> object:
        del kwargs
        return result

    monkeypatch.setattr(adapter, "save_document", fake_save_document)

    with pytest.raises(RuntimeError, match="did not confirm"):
        provider.write_receipt(receipt, render_markdown(receipt), approved=True)

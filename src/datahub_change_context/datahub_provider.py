"""Real integration adapter for the official DataHub Agent Context Kit."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from datahub.sdk.main_client import DataHubClient
from datahub_agent_context.context import DataHubContext
from datahub_agent_context.mcp_tools import (
    get_dataset_queries,
    get_entities,
    get_lineage,
    list_schema_fields,
    save_document,
)

from datahub_change_context.models import (
    ChangeRequest,
    DownstreamAsset,
    EntityContext,
    EvidenceBundle,
    QuerySignal,
    Receipt,
)


class DataHubAgentContextProvider:
    """Uses official Agent Context Kit tools against a configured GMS endpoint."""

    def __init__(self, client: DataHubClient) -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> DataHubAgentContextProvider:
        """Load URL/token through the official DataHub environment mechanism."""
        return cls(DataHubClient.from_env())

    @property
    def source_mode(self) -> str:
        return "datahub"

    def collect(self, request: ChangeRequest) -> EvidenceBundle:
        gaps: list[str] = []
        entity: EntityContext | None = None
        downstream: tuple[DownstreamAsset, ...] = ()
        signals: list[QuerySignal] = []
        entity_ok = schema_ok = lineage_ok = False

        with DataHubContext(self._client):
            try:
                raw_entities: object = get_entities([request.asset_urn])
                entity = _normalize_entity_result(request.asset_urn, raw_entities)
                entity_ok = entity is not None
                if entity is None:
                    gaps.append("entity_not_found")
            except Exception:
                gaps.append("entity_lookup_failed")

            try:
                keywords = [change.column for change in request.changes]
                raw_schema: object = list_schema_fields(
                    request.asset_urn,
                    keywords=keywords,
                    limit=100,
                    offset=0,
                )
                schema_fields = _normalize_schema_fields(request.asset_urn, raw_schema)
                schema_ok = True
                if entity is not None:
                    entity = EntityContext(
                        urn=entity.urn,
                        name=entity.name,
                        owners=entity.owners,
                        schema_fields=schema_fields,
                    )
            except Exception:
                gaps.append("schema_lookup_failed")

            try:
                raw_lineage: object = get_lineage(
                    urn=request.asset_urn,
                    upstream=False,
                    max_hops=request.max_hops,
                    max_results=50,
                )
                downstream = _normalize_downstream(raw_lineage)
                lineage_ok = True
            except Exception:
                gaps.append("lineage_lookup_failed")

            for change in request.changes:
                try:
                    raw_queries: object = get_dataset_queries(
                        urn=request.asset_urn,
                        column=change.column,
                        count=20,
                    )
                    signals.extend(_normalize_queries(change.column, raw_queries))
                except Exception:
                    gaps.append(f"query_context_lookup_failed:{change.column}")

        return EvidenceBundle(
            source_mode="datahub",
            real_datahub_verified=entity_ok and schema_ok and lineage_ok,
            entity=entity,
            downstream_assets=downstream,
            query_signals=tuple(
                sorted(signals, key=lambda item: (item.column, item.source, item.fingerprint))
            ),
            gaps=tuple(sorted(set(gaps))),
        )

    def write_receipt(self, receipt: Receipt, markdown: str, *, approved: bool) -> str:
        if not approved:
            raise PermissionError("DataHub write-back requires explicit approval")
        if not receipt.evidence.real_datahub_verified:
            raise RuntimeError("write-back requires a verified real DataHub evidence bundle")
        with DataHubContext(self._client):
            raw_result: object = save_document(
                document_type="Decision",
                title=f"Change receipt {receipt.request.change_id}",
                content=markdown,
                topics=["change-review", "lineage", receipt.decision.value.lower()],
                related_assets=[receipt.request.asset_urn],
            )
        result = _mapping(raw_result)
        urn = _string(result.get("urn"))
        if result.get("success") is not True or not urn:
            raise RuntimeError("DataHub did not confirm the document write")
        return urn


def _normalize_entity_result(urn: str, value: object) -> EntityContext | None:
    if not isinstance(value, list):
        raise ValueError("get_entities response is malformed")
    if not value:
        return None
    if len(value) != 1:
        raise ValueError("get_entities returned an unexpected result count")
    entity = _required_mapping(value[0], "get_entities entity")
    if entity.get("error") is not None:
        return None
    actual_urn = _string(entity.get("urn"))
    if actual_urn != urn:
        raise ValueError("get_entities returned an unexpected entity")
    properties = _mapping(entity.get("properties"))
    name = _string(properties.get("name")) or _string(entity.get("name")) or urn
    return EntityContext(
        urn=actual_urn,
        name=name,
        owners=_owners(entity),
        schema_fields=_schema_from_entity(entity),
    )


def _normalize_schema_fields(expected_urn: str, value: object) -> tuple[str, ...]:
    result = _required_mapping(value, "list_schema_fields response")
    if result.get("urn") != expected_urn:
        raise ValueError("list_schema_fields returned an unexpected entity")
    raw_fields = result.get("fields")
    if not isinstance(raw_fields, list):
        raise ValueError("list_schema_fields fields are malformed")
    fields: set[str] = set()
    for raw_field in raw_fields:
        field = _required_mapping(raw_field, "list_schema_fields field")
        field_path = _string(field.get("fieldPath"))
        if not field_path:
            raise ValueError("list_schema_fields field path is malformed")
        fields.add(field_path)
    return tuple(sorted(fields))


def _normalize_downstream(value: object) -> tuple[DownstreamAsset, ...]:
    root = _required_mapping(value, "get_lineage response")
    direction = _required_mapping(root.get("downstreams"), "get_lineage downstreams")
    raw_results = direction.get("searchResults")
    if not isinstance(raw_results, list):
        raise ValueError("get_lineage search results are malformed")
    assets: list[DownstreamAsset] = []
    for raw_result in raw_results:
        result = _required_mapping(raw_result, "get_lineage search result")
        entity = _required_mapping(result.get("entity"), "get_lineage entity")
        urn = _string(entity.get("urn"))
        if not urn:
            raise ValueError("get_lineage entity URN is malformed")
        properties = _mapping(entity.get("properties"))
        degree = _degree(result.get("degree"))
        assets.append(
            DownstreamAsset(
                urn=urn,
                name=_string(properties.get("name")) or _string(entity.get("name")) or urn,
                degree=degree,
                entity_type=_string(entity.get("type"), "UNKNOWN"),
                owners=_owners(entity),
            )
        )
    return tuple(sorted(assets, key=lambda asset: (asset.degree, asset.urn)))


def _normalize_queries(column: str, value: object) -> list[QuerySignal]:
    result = _required_mapping(value, "get_dataset_queries response")
    raw_queries = result.get("queries")
    if not isinstance(raw_queries, list):
        raise ValueError("get_dataset_queries queries are malformed")
    signals: list[QuerySignal] = []
    for raw_query in raw_queries:
        query = _required_mapping(raw_query, "get_dataset_queries query")
        properties = _required_mapping(query.get("properties"), "get_dataset_queries properties")
        statement = _required_mapping(properties.get("statement"), "get_dataset_queries statement")
        sql = _string(statement.get("value"))
        if not sql:
            raise ValueError("get_dataset_queries SQL is malformed")
        source = _string(properties.get("source")).upper()
        if source not in {"MANUAL", "SYSTEM"}:
            raise ValueError("get_dataset_queries source is malformed")
        fingerprint = "sha256:" + hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]
        signals.append(QuerySignal(column=column, source=source, fingerprint=fingerprint))
    return signals


def _schema_from_entity(entity: Mapping[str, object]) -> tuple[str, ...]:
    schema = _mapping(entity.get("schemaMetadata"))
    raw_fields = schema.get("fields")
    if not isinstance(raw_fields, list):
        return ()
    return tuple(
        sorted(
            {
                field_path
                for raw_field in raw_fields
                if (field_path := _string(_mapping(raw_field).get("fieldPath")))
            }
        )
    )


def _owners(entity: Mapping[str, object]) -> tuple[str, ...]:
    ownership = _mapping(entity.get("ownership"))
    raw_owners = ownership.get("owners")
    if not isinstance(raw_owners, list):
        return ()
    owners: set[str] = set()
    for raw_owner in raw_owners:
        owner_entry = _mapping(raw_owner)
        owner = _mapping(owner_entry.get("owner"))
        owner_urn = _string(owner.get("urn"))
        if owner_urn:
            owners.add(owner_urn)
    return tuple(sorted(owners))


def _degree(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return max(1, value)
    if isinstance(value, str):
        digits = "".join(character for character in value if character.isdigit())
        if digits:
            return max(1, int(digits))
    return 1


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _required_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is malformed")
    return {str(key): item for key, item in value.items()}


def _string(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default

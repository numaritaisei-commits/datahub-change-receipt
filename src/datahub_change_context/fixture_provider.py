"""Deterministic, explicitly non-live DataHub context fixture."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from datahub_change_context.models import (
    ChangeRequest,
    DownstreamAsset,
    EntityContext,
    EvidenceBundle,
    QuerySignal,
    Receipt,
)


class FixtureContextProvider:
    """Loads sanitized contract fixtures without pretending to reach DataHub."""

    def __init__(self, fixture: Mapping[str, object]) -> None:
        self._fixture = fixture

    @classmethod
    def from_path(cls, path: Path) -> FixtureContextProvider:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("fixture root must be an object")
        return cls(raw)

    @property
    def source_mode(self) -> str:
        return "fixture"

    def collect(self, request: ChangeRequest) -> EvidenceBundle:
        gaps: list[str] = []
        entity = self._entity(request.asset_urn)
        if entity is None:
            gaps.append("entity_not_found")

        downstream = self._downstream(request.asset_urn)
        signals: list[QuerySignal] = []
        for change in request.changes:
            signals.extend(self._query_signals(request.asset_urn, change.column))

        raw_gaps = self._fixture.get("gaps", [])
        if isinstance(raw_gaps, list):
            gaps.extend(str(gap) for gap in raw_gaps if isinstance(gap, str))

        return EvidenceBundle(
            source_mode="fixture",
            real_datahub_verified=False,
            entity=entity,
            downstream_assets=tuple(downstream),
            query_signals=tuple(signals),
            gaps=tuple(sorted(set(gaps))),
        )

    def write_receipt(self, receipt: Receipt, markdown: str, *, approved: bool) -> str:
        del receipt, markdown, approved
        raise RuntimeError("fixture mode can never write metadata to DataHub")

    def _entity(self, urn: str) -> EntityContext | None:
        entities = _mapping(self._fixture.get("entities"))
        raw = _mapping(entities.get(urn))
        if not raw:
            return None
        return EntityContext(
            urn=urn,
            name=_string(raw.get("name"), urn),
            owners=_string_tuple(raw.get("owners")),
            schema_fields=_string_tuple(raw.get("schema_fields")),
        )

    def _downstream(self, urn: str) -> list[DownstreamAsset]:
        lineage = _mapping(self._fixture.get("downstream"))
        raw_assets = lineage.get(urn)
        if not isinstance(raw_assets, list):
            return []
        assets: list[DownstreamAsset] = []
        for raw_asset in raw_assets:
            asset = _mapping(raw_asset)
            asset_urn = _string(asset.get("urn"))
            if not asset_urn:
                continue
            raw_degree = asset.get("degree", 1)
            degree = raw_degree if isinstance(raw_degree, int) else 1
            assets.append(
                DownstreamAsset(
                    urn=asset_urn,
                    name=_string(asset.get("name"), asset_urn),
                    degree=degree,
                    entity_type=_string(asset.get("entity_type"), "UNKNOWN"),
                    owners=_string_tuple(asset.get("owners")),
                )
            )
        return sorted(assets, key=lambda asset: (asset.degree, asset.urn))

    def _query_signals(self, urn: str, column: str) -> list[QuerySignal]:
        queries = _mapping(self._fixture.get("query_signals"))
        raw_signals = queries.get(f"{urn}#{column}")
        if not isinstance(raw_signals, list):
            return []
        signals: list[QuerySignal] = []
        for raw_signal in raw_signals:
            signal = _mapping(raw_signal)
            fingerprint = _string(signal.get("fingerprint"))
            if not fingerprint:
                continue
            signals.append(
                QuerySignal(
                    column=column,
                    source=_string(signal.get("source"), "UNKNOWN").upper(),
                    fingerprint=fingerprint,
                )
            )
        return sorted(signals, key=lambda signal: (signal.source, signal.fingerprint))


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _string(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(sorted({item for item in value if isinstance(item, str) and item}))

"""Typed domain models for proposed data changes and evidence receipts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class ChangeKind(StrEnum):
    """Supported schema change categories."""

    ADD = "add"
    DROP = "drop"
    RENAME = "rename"
    TYPE_CHANGE = "type_change"


class Decision(StrEnum):
    """Deterministic review outcomes."""

    PASS = "PASS"  # noqa: S105 - review status, not a credential
    WARN = "WARN"
    BLOCK = "BLOCK"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


@dataclass(frozen=True, slots=True)
class ColumnChange:
    column: str
    kind: ChangeKind
    to: str | None = None

    def __post_init__(self) -> None:
        if not self.column.strip():
            raise ValueError("change.column must not be empty")
        if self.kind in {ChangeKind.RENAME, ChangeKind.TYPE_CHANGE} and not self.to:
            raise ValueError(f"change.to is required for {self.kind.value}")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ColumnChange:
        column = _required_string(value, "column")
        kind = ChangeKind(_required_string(value, "kind"))
        raw_to = value.get("to")
        if raw_to is not None and not isinstance(raw_to, str):
            raise ValueError("change.to must be a string when provided")
        return cls(column=column, kind=kind, to=raw_to)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"column": self.column, "kind": self.kind.value}
        if self.to is not None:
            result["to"] = self.to
        return result


@dataclass(frozen=True, slots=True)
class ChangeRequest:
    change_id: str
    asset_urn: str
    changes: tuple[ColumnChange, ...]
    max_hops: int = 2

    def __post_init__(self) -> None:
        if not self.change_id.strip():
            raise ValueError("change_id must not be empty")
        if not self.asset_urn.startswith("urn:li:"):
            raise ValueError("asset_urn must be a DataHub URN")
        if not self.changes:
            raise ValueError("at least one change is required")
        if not 1 <= self.max_hops <= 3:
            raise ValueError("max_hops must be between 1 and 3")
        columns = [change.column for change in self.changes]
        if len(columns) != len(set(columns)):
            raise ValueError("each source column may appear only once")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ChangeRequest:
        raw_changes = value.get("changes")
        if not isinstance(raw_changes, list):
            raise ValueError("changes must be a list")
        changes: list[ColumnChange] = []
        for raw_change in raw_changes:
            if not isinstance(raw_change, dict):
                raise ValueError("each change must be an object")
            changes.append(ColumnChange.from_mapping(raw_change))
        raw_hops = value.get("max_hops", 2)
        if not isinstance(raw_hops, int) or isinstance(raw_hops, bool):
            raise ValueError("max_hops must be an integer")
        return cls(
            change_id=_required_string(value, "change_id"),
            asset_urn=_required_string(value, "asset_urn"),
            changes=tuple(changes),
            max_hops=raw_hops,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "change_id": self.change_id,
            "asset_urn": self.asset_urn,
            "changes": [change.to_dict() for change in self.changes],
            "max_hops": self.max_hops,
        }


@dataclass(frozen=True, slots=True)
class EntityContext:
    urn: str
    name: str
    owners: tuple[str, ...]
    schema_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "urn": self.urn,
            "name": self.name,
            "owners": list(self.owners),
            "schema_fields": list(self.schema_fields),
        }


@dataclass(frozen=True, slots=True)
class DownstreamAsset:
    urn: str
    name: str
    degree: int
    entity_type: str
    owners: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "urn": self.urn,
            "name": self.name,
            "degree": self.degree,
            "entity_type": self.entity_type,
            "owners": list(self.owners),
        }


@dataclass(frozen=True, slots=True)
class QuerySignal:
    column: str
    source: str
    fingerprint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "column": self.column,
            "source": self.source,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    source_mode: str
    real_datahub_verified: bool
    entity: EntityContext | None
    downstream_assets: tuple[DownstreamAsset, ...]
    query_signals: tuple[QuerySignal, ...]
    gaps: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "source_mode": self.source_mode,
            "real_datahub_verified": self.real_datahub_verified,
            "entity": self.entity.to_dict() if self.entity else None,
            "downstream_assets": [asset.to_dict() for asset in self.downstream_assets],
            "query_signals": [signal.to_dict() for signal in self.query_signals],
            "gaps": list(self.gaps),
        }


@dataclass(frozen=True, slots=True)
class Receipt:
    receipt_id: str
    request: ChangeRequest
    decision: Decision
    risk_score: int
    reasons: tuple[str, ...]
    recommended_checks: tuple[str, ...]
    evidence: EvidenceBundle

    def to_dict(self) -> dict[str, object]:
        return {
            "receipt_id": self.receipt_id,
            "request": self.request.to_dict(),
            "decision": self.decision.value,
            "risk_score": self.risk_score,
            "reasons": list(self.reasons),
            "recommended_checks": list(self.recommended_checks),
            "evidence": self.evidence.to_dict(),
        }


def _required_string(value: Mapping[str, object], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return raw.strip()

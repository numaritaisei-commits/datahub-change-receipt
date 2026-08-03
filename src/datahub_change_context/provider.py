"""Context-provider boundary shared by fixture and real DataHub modes."""

from __future__ import annotations

from typing import Protocol

from datahub_change_context.models import ChangeRequest, EvidenceBundle, Receipt


class ContextProvider(Protocol):
    """Collects the minimum DataHub context needed for a change review."""

    @property
    def source_mode(self) -> str: ...

    def collect(self, request: ChangeRequest) -> EvidenceBundle: ...

    def write_receipt(self, receipt: Receipt, markdown: str, *, approved: bool) -> str: ...

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import cast

import pytest
from datahub.errors import ItemNotFoundError
from datahub.sdk.document import Document
from datahub.sdk.main_client import DataHubClient

import datahub_change_context.cli as cli
import datahub_change_context.live_writeback as writeback_cli
from datahub_change_context.demo_seed import TARGET_URN
from datahub_change_context.fixture_provider import FixtureContextProvider
from datahub_change_context.live_writeback import (
    SHARED_PARENT_URN,
    SUCCESS_PROOF,
    LiveWritebackError,
    cleanup_from_file,
    load_and_verify_proof,
    load_synthetic_document_urn,
    prove_and_delete,
)

ROOT = Path(__file__).parents[1]
DOCUMENT_URN = "urn:li:document:shared-12345678-1234-4123-8123-123456789abc"


class FakeEntities:
    def __init__(self, document: Document | None) -> None:
        self.document = document
        self.delete_calls: list[tuple[str, bool, bool, bool]] = []
        self.fail_delete = False

    def get(self, urn: str) -> Document:
        if self.document is None or str(self.document.urn) != urn:
            raise ItemNotFoundError("synthetic entity not found")
        return self.document

    def delete(
        self,
        urn: str,
        check_exists: bool = True,
        cascade: bool = False,
        hard: bool = False,
    ) -> None:
        self.delete_calls.append((urn, check_exists, cascade, hard))
        if self.fail_delete:
            raise RuntimeError("synthetic delete failure")
        self.document = None


class FakeClient:
    def __init__(self, document: Document | None) -> None:
        self.entities = FakeEntities(document)


def _document(
    *,
    title: str = "Change receipt synthetic-live-orders-v2",
    text: str = "# Synthetic receipt\n",
    subtype: str = "Decision",
    parent: str = SHARED_PARENT_URN,
    related_assets: list[str] | None = None,
) -> Document:
    return Document.create_document(
        id="shared-12345678-1234-4123-8123-123456789abc",
        title=title,
        text=text,
        subtype=subtype,
        parent_document=parent,
        related_assets=related_assets if related_assets is not None else [TARGET_URN],
        show_in_global_context=True,
    )


def _private_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)


def _live_receipt(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
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
                    "downstream_assets": [
                        {
                            "urn": (
                                "urn:li:dataset:(urn:li:dataPlatform:postgres,"
                                "change_receipt.daily_orders,PROD)"
                            )
                        }
                    ],
                    "gaps": [],
                },
            }
        ),
        encoding="utf-8",
    )


def _proof_paths(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    urn_path = tmp_path / "document.urn"
    receipt_path = tmp_path / "receipt.json"
    markdown_path = tmp_path / "receipt.md"
    proof_path = tmp_path / "proof.json"
    _private_text(urn_path, DOCUMENT_URN + "\n")
    _live_receipt(receipt_path)
    markdown_path.write_text("# Synthetic receipt\n", encoding="utf-8")
    return urn_path, receipt_path, markdown_path, proof_path


def test_live_write_back_is_read_back_hard_deleted_and_proved(tmp_path: Path) -> None:
    urn_path, receipt_path, markdown_path, proof_path = _proof_paths(tmp_path)
    fake = FakeClient(_document())

    prove_and_delete(
        cast(DataHubClient, fake),
        urn_path=urn_path,
        receipt_path=receipt_path,
        markdown_path=markdown_path,
        proof_path=proof_path,
    )

    assert fake.entities.delete_calls == [(DOCUMENT_URN, True, False, True)]
    assert fake.entities.document is None
    assert not urn_path.exists()
    assert stat.S_IMODE(proof_path.stat().st_mode) == 0o600
    assert json.loads(proof_path.read_text()) == SUCCESS_PROOF
    assert DOCUMENT_URN not in proof_path.read_text()
    assert TARGET_URN not in proof_path.read_text()
    assert "Synthetic receipt" not in proof_path.read_text()
    load_and_verify_proof(proof_path)


@pytest.mark.parametrize("numeric_true", [1, 1.0])
def test_live_write_back_proof_rejects_numeric_truth_values(
    tmp_path: Path,
    numeric_true: int | float,
) -> None:
    proof_path = tmp_path / "proof.json"
    malformed_proof: dict[str, object] = dict(SUCCESS_PROOF)
    malformed_proof["approved"] = numeric_true
    proof_path.write_text(json.dumps(malformed_proof), encoding="utf-8")

    with pytest.raises(LiveWritebackError, match="proof is incomplete"):
        load_and_verify_proof(proof_path)


@pytest.mark.parametrize(
    "document",
    [
        _document(title="wrong"),
        _document(text="wrong"),
        _document(subtype="Note"),
        _document(parent="urn:li:document:wrong-parent"),
        _document(related_assets=[]),
    ],
)
def test_live_write_back_mismatch_fails_but_still_cleans_up(
    tmp_path: Path,
    document: Document,
) -> None:
    urn_path, receipt_path, markdown_path, proof_path = _proof_paths(tmp_path)
    fake = FakeClient(document)

    with pytest.raises(LiveWritebackError, match="read-back"):
        prove_and_delete(
            cast(DataHubClient, fake),
            urn_path=urn_path,
            receipt_path=receipt_path,
            markdown_path=markdown_path,
            proof_path=proof_path,
        )

    assert fake.entities.document is None
    assert not urn_path.exists()
    assert not proof_path.exists()


def test_live_write_back_cleanup_failure_is_fail_closed(tmp_path: Path) -> None:
    urn_path, receipt_path, markdown_path, proof_path = _proof_paths(tmp_path)
    fake = FakeClient(_document())
    fake.entities.fail_delete = True

    with pytest.raises(LiveWritebackError, match="cleanup"):
        prove_and_delete(
            cast(DataHubClient, fake),
            urn_path=urn_path,
            receipt_path=receipt_path,
            markdown_path=markdown_path,
            proof_path=proof_path,
        )

    assert urn_path.exists()
    assert not proof_path.exists()


@pytest.mark.parametrize(
    "urn",
    [
        "urn:li:document:__system_shared_documents",
        "urn:li:document:shared-not-a-uuid",
        "urn:li:dataset:shared-12345678-1234-4123-8123-123456789abc",
    ],
)
def test_cleanup_rejects_non_synthetic_targets_without_deleting(
    tmp_path: Path,
    urn: str,
) -> None:
    urn_path = tmp_path / "document.urn"
    _private_text(urn_path, urn)
    fake = FakeClient(_document())

    with pytest.raises(LiveWritebackError):
        cleanup_from_file(cast(DataHubClient, fake), urn_path)

    assert fake.entities.delete_calls == []


def test_private_urn_file_rejects_broad_permissions(tmp_path: Path) -> None:
    urn_path = tmp_path / "document.urn"
    urn_path.write_text(DOCUMENT_URN, encoding="utf-8")
    urn_path.chmod(0o644)

    with pytest.raises(LiveWritebackError, match="permissions"):
        load_synthetic_document_urn(urn_path)


def test_cli_requires_all_write_back_gates_before_provider_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_called = False

    def forbidden_provider(mode: str, fixture: Path | None) -> FixtureContextProvider:
        nonlocal provider_called
        del mode, fixture
        provider_called = True
        raise AssertionError("provider must not be created")

    monkeypatch.setattr(cli, "_provider", forbidden_provider)
    request_path = ROOT / "examples/change-request.json"

    assert cli.main(["--request", str(request_path), "--approve-write-back"]) == 2
    assert (
        cli.main(
            [
                "--request",
                str(request_path),
                "--write-back-urn-out",
                str(tmp_path / "orphan.urn"),
            ]
        )
        == 2
    )
    assert provider_called is False


def test_cli_records_write_back_urn_privately_without_logging_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    document_urn = DOCUMENT_URN

    class FakeProvider(FixtureContextProvider):
        def write_receipt(self, receipt: object, markdown: str, *, approved: bool) -> str:
            del receipt, markdown
            assert approved is True
            return document_urn

    provider = FakeProvider.from_path(ROOT / "fixtures/catalog-context.json")
    monkeypatch.setattr(cli, "_provider", lambda mode, fixture: provider)
    urn_path = tmp_path / "document.urn"

    exit_code = cli.main(
        [
            "--request",
            str(ROOT / "examples/change-request.json"),
            "--mode",
            "datahub",
            "--json-out",
            str(tmp_path / "receipt.json"),
            "--markdown-out",
            str(tmp_path / "receipt.md"),
            "--approve-write-back",
            "--write-back-urn-out",
            str(urn_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert document_urn not in captured.out + captured.err
    assert "datahub_write_back_created=true" in captured.err
    assert urn_path.read_text().strip() == document_urn
    assert stat.S_IMODE(urn_path.stat().st_mode) == 0o600


def test_cli_retains_fail_closed_marker_if_urn_handoff_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_calls = 0

    class FakeProvider(FixtureContextProvider):
        def write_receipt(self, receipt: object, markdown: str, *, approved: bool) -> str:
            nonlocal write_calls
            del receipt, markdown
            assert approved is True
            write_calls += 1
            return DOCUMENT_URN

    provider = FakeProvider.from_path(ROOT / "fixtures/catalog-context.json")
    monkeypatch.setattr(cli, "_provider", lambda mode, fixture: provider)

    def fail_handoff(file_descriptor: int, document_urn: str) -> None:
        del file_descriptor, document_urn
        raise OSError("synthetic handoff failure")

    monkeypatch.setattr(cli, "_write_reserved_private_output", fail_handoff)
    urn_path = tmp_path / "document.urn"

    exit_code = cli.main(
        [
            "--request",
            str(ROOT / "examples/change-request.json"),
            "--mode",
            "datahub",
            "--json-out",
            str(tmp_path / "receipt.json"),
            "--markdown-out",
            str(tmp_path / "receipt.md"),
            "--approve-write-back",
            "--write-back-urn-out",
            str(urn_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert write_calls == 1
    assert urn_path.read_text() == "write_attempted\n"
    assert DOCUMENT_URN not in captured.out + captured.err
    with pytest.raises(LiveWritebackError):
        load_synthetic_document_urn(urn_path)


def test_verifier_redacts_unexpected_sdk_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    urn_path = tmp_path / "document.urn"
    _private_text(urn_path, DOCUMENT_URN)
    sensitive_sentinel = "private-sdk-response-marker"

    class SdkSpecificFailure(Exception):
        pass

    def fail_from_env() -> DataHubClient:
        raise SdkSpecificFailure(f"{DOCUMENT_URN} {sensitive_sentinel}")

    monkeypatch.setattr(writeback_cli, "create_client", fail_from_env)

    exit_code = writeback_cli.cli_main(["cleanup", "--urn-file", str(urn_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "synthetic_write_back_verified=false" in captured.err
    assert DOCUMENT_URN not in captured.out + captured.err
    assert sensitive_sentinel not in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err

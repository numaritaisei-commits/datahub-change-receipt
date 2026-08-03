"""Fail-closed read-back and cleanup for the synthetic DataHub decision document."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from datahub.errors import ItemNotFoundError
from datahub.sdk.document import Document
from datahub.sdk.main_client import DataHubClient

from datahub_change_context.demo_seed import TARGET_URN
from datahub_change_context.live_evidence import EXPECTED_CHANGE_ID, verify_live_receipt

SHARED_PARENT_URN = "urn:li:document:__system_shared_documents"
SYNTHETIC_DOCUMENT_URN = re.compile(
    r"urn:li:document:shared-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)
SUCCESS_PROOF = {
    "approved": True,
    "created": True,
    "retrieved": True,
    "content_verified": True,
    "related_asset_verified": True,
    "deleted": True,
}


class LiveWritebackError(ValueError):
    """Raised when the synthetic write-back cannot be proved and safely cleaned up."""


def prove_and_delete(
    client: DataHubClient,
    *,
    urn_path: Path,
    receipt_path: Path,
    markdown_path: Path,
    proof_path: Path,
) -> None:
    """Verify the created document in a second process, then hard-delete it."""
    document_urn = load_synthetic_document_urn(urn_path)
    verification_error: Exception | None = None
    cleanup_error: Exception | None = None
    try:
        receipt = _load_mapping(receipt_path)
        verify_live_receipt(receipt)
        markdown = markdown_path.read_text(encoding="utf-8")
        if not markdown:
            raise LiveWritebackError("synthetic Markdown receipt is empty")
        document = client.entities.get(document_urn)
        verify_document(
            document,
            document_urn=document_urn,
            expected_markdown=markdown,
        )
    except Exception as error:
        verification_error = error

    try:
        delete_synthetic_document(client, document_urn)
    except Exception as error:
        cleanup_error = error

    if cleanup_error is not None:
        raise LiveWritebackError("synthetic document cleanup was not verified") from cleanup_error
    if verification_error is not None:
        urn_path.unlink(missing_ok=True)
        raise LiveWritebackError(
            "synthetic document read-back was not verified"
        ) from verification_error

    _write_private_json_exclusive(proof_path, SUCCESS_PROOF)
    urn_path.unlink()


def cleanup_from_file(client: DataHubClient, urn_path: Path) -> None:
    """Delete a strict synthetic document referenced by a surviving private URN file."""
    if not urn_path.exists() and not urn_path.is_symlink():
        return
    document_urn = load_synthetic_document_urn(urn_path)
    delete_synthetic_document(client, document_urn)
    urn_path.unlink()


def verify_document(
    document: object,
    *,
    document_urn: str,
    expected_markdown: str,
) -> None:
    """Require exact live metadata without logging content or identifiers."""
    if not isinstance(document, Document):
        raise LiveWritebackError("retrieved entity is not a DataHub document")
    if str(document.urn) != document_urn:
        raise LiveWritebackError("retrieved document URN does not match")
    if document.title != f"Change receipt {EXPECTED_CHANGE_ID}":
        raise LiveWritebackError("retrieved document title does not match")
    if document.subtype != "Decision":
        raise LiveWritebackError("retrieved document subtype does not match")
    if document.status != "PUBLISHED":
        raise LiveWritebackError("retrieved document is not published")
    if document.parent_document != SHARED_PARENT_URN:
        raise LiveWritebackError("retrieved document parent does not match")
    if document.show_in_global_context is not True:
        raise LiveWritebackError("retrieved document is not in global context")
    if document.related_assets != [TARGET_URN]:
        raise LiveWritebackError("retrieved document asset relation does not match")
    actual_text = document.text
    if not isinstance(actual_text, str):
        raise LiveWritebackError("retrieved document content is missing")
    if _digest(actual_text) != _digest(expected_markdown):
        raise LiveWritebackError("retrieved document content digest does not match")


def delete_synthetic_document(client: DataHubClient, document_urn: str) -> None:
    """Hard-delete only a strict, randomly named synthetic child and prove absence."""
    require_synthetic_document_urn(document_urn)
    try:
        client.entities.get(document_urn)
    except ItemNotFoundError:
        return
    client.entities.delete(document_urn, check_exists=True, cascade=False, hard=True)
    try:
        client.entities.get(document_urn)
    except ItemNotFoundError:
        return
    raise LiveWritebackError("synthetic document still exists after cleanup")


def load_synthetic_document_urn(path: Path) -> str:
    """Read one private, regular, non-symlink URN file and validate its exact pattern."""
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise LiveWritebackError("synthetic document URN path is not a regular private file")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise LiveWritebackError("synthetic document URN file permissions are too broad")
    document_urn = path.read_text(encoding="utf-8").strip()
    require_synthetic_document_urn(document_urn)
    return document_urn


def require_synthetic_document_urn(document_urn: str) -> None:
    if SYNTHETIC_DOCUMENT_URN.fullmatch(document_urn) is None:
        raise LiveWritebackError("document URN is outside the synthetic cleanup boundary")


def load_and_verify_proof(path: Path) -> None:
    proof = _load_mapping(path)
    if set(proof) != set(SUCCESS_PROOF) or any(proof[key] is not True for key in SUCCESS_PROOF):
        raise LiveWritebackError("synthetic write-back proof is incomplete")


def _load_mapping(path: Path) -> Mapping[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LiveWritebackError("JSON proof input is not an object")
    return {str(key): value for key, value in raw.items()}


def _write_private_json_exclusive(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    file_descriptor = os.open(path, flags, 0o600)
    complete = False
    try:
        payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        written = os.write(file_descriptor, payload)
        if written != len(payload):
            raise OSError("private proof output was incomplete")
        os.fsync(file_descriptor)
        complete = True
    finally:
        os.close(file_descriptor)
        if not complete:
            path.unlink(missing_ok=True)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    prove = subparsers.add_parser("prove")
    prove.add_argument("--approve-write-back", action="store_true")
    prove.add_argument("--urn-file", required=True, type=Path)
    prove.add_argument("--receipt", required=True, type=Path)
    prove.add_argument("--markdown", required=True, type=Path)
    prove.add_argument("--proof-out", required=True, type=Path)

    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("--urn-file", required=True, type=Path)

    proof = subparsers.add_parser("proof")
    proof.add_argument("path", type=Path)
    return parser


def cli_main(argv: Sequence[str] | None = None) -> int:
    args = build_cli_parser().parse_args(argv)
    try:
        if args.command == "proof":
            load_and_verify_proof(args.path)
            print("synthetic_write_back_proof_verified=true")
            return 0
        if args.command == "cleanup":
            if not args.urn_file.exists() and not args.urn_file.is_symlink():
                print("synthetic_write_back_cleanup_verified=true")
                return 0
            cleanup_from_file(create_client(), args.urn_file)
            print("synthetic_write_back_cleanup_verified=true")
            return 0
        if args.command == "prove":
            if args.approve_write_back is not True:
                raise LiveWritebackError("explicit synthetic write-back approval is required")
            prove_and_delete(
                create_client(),
                urn_path=args.urn_file,
                receipt_path=args.receipt,
                markdown_path=args.markdown,
                proof_path=args.proof_out,
            )
            print("synthetic_write_back_verified=true")
            return 0
        raise LiveWritebackError("unsupported write-back verification command")
    except Exception:
        # This is a privacy boundary around experimental SDK errors. Do not let
        # endpoints, response payloads, or the temporary document URN reach logs.
        print("synthetic_write_back_verified=false", file=sys.stderr)
        return 1


def create_client() -> DataHubClient:
    return DataHubClient.from_env()

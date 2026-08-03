"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from datahub_change_context.agent import ChangeReceiptAgent
from datahub_change_context.fixture_provider import FixtureContextProvider
from datahub_change_context.models import ChangeRequest
from datahub_change_context.provider import ContextProvider
from datahub_change_context.rendering import render_json, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a deterministic change receipt from DataHub context."
    )
    parser.add_argument("--request", required=True, type=Path, help="Change request JSON")
    parser.add_argument("--mode", choices=("fixture", "datahub"), default="fixture")
    parser.add_argument("--fixture", type=Path, help="Sanitized fixture JSON")
    parser.add_argument("--json-out", type=Path, help="Write the JSON receipt here")
    parser.add_argument("--markdown-out", type=Path, help="Write the Markdown receipt here")
    parser.add_argument(
        "--approve-write-back",
        action="store_true",
        help="Explicitly approve saving a verified real receipt as a DataHub document",
    )
    parser.add_argument(
        "--write-back-urn-out",
        type=Path,
        help="Privately record the created document URN for independent verification",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    urn_output_fd: int | None = None
    try:
        _validate_write_back_arguments(
            mode=args.mode,
            approved=args.approve_write_back,
            urn_output=args.write_back_urn_out,
        )
        request = ChangeRequest.from_mapping(_load_mapping(args.request))
        provider = _provider(args.mode, args.fixture)
        receipt = ChangeReceiptAgent(provider).review(request)
        json_output = render_json(receipt)
        markdown_output = render_markdown(receipt)

        if args.json_out:
            _write(args.json_out, json_output)
        else:
            sys.stdout.write(json_output)
        if args.markdown_out:
            _write(args.markdown_out, markdown_output)

        if args.approve_write_back:
            if args.write_back_urn_out is None:
                raise RuntimeError("private write-back output was not configured")
            # Durably mark the mutation attempt before calling the remote write.
            # If the process dies before replacing this marker with the URN, the
            # per-document cleanup must fail closed and the final Core teardown
            # remains the authoritative cleanup.
            urn_output_fd = _reserve_private_output(args.write_back_urn_out)
            document_urn = provider.write_receipt(receipt, markdown_output, approved=True)
            _write_reserved_private_output(urn_output_fd, document_urn)
            urn_output_fd = None
            sys.stderr.write("datahub_write_back_created=true\n")
        return 0
    except (OSError, ValueError, RuntimeError, PermissionError) as error:
        # Avoid printing environment values, remote payloads, or raw query text.
        sys.stderr.write(f"change receipt failed ({type(error).__name__})\n")
        return 2
    finally:
        if urn_output_fd is not None:
            os.close(urn_output_fd)


def _provider(mode: str, fixture: Path | None) -> ContextProvider:
    if mode == "datahub":
        # Keep fixture runs dependency-light and free of SDK initialization warnings.
        from datahub_change_context.datahub_provider import DataHubAgentContextProvider

        return DataHubAgentContextProvider.from_env()
    if fixture is None:
        raise ValueError("--fixture is required in fixture mode")
    return FixtureContextProvider.from_path(fixture)


def _load_mapping(path: Path) -> Mapping[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("request root must be an object")
    return {str(key): item for key, item in raw.items()}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _validate_write_back_arguments(*, mode: str, approved: bool, urn_output: Path | None) -> None:
    if approved and mode != "datahub":
        raise ValueError("write-back is forbidden in fixture mode")
    if approved and urn_output is None:
        raise ValueError("approved write-back requires --write-back-urn-out")
    if not approved and urn_output is not None:
        raise ValueError("--write-back-urn-out requires --approve-write-back")


def _reserve_private_output(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    file_descriptor = os.open(path, flags, 0o600)
    try:
        marker = b"write_attempted\n"
        written = os.write(file_descriptor, marker)
        if written != len(marker):
            raise OSError("private write-back marker was incomplete")
        os.fsync(file_descriptor)
    except Exception:
        os.close(file_descriptor)
        raise
    return file_descriptor


def _write_reserved_private_output(file_descriptor: int, document_urn: str) -> None:
    payload = (document_urn + "\n").encode("utf-8")
    os.lseek(file_descriptor, 0, os.SEEK_SET)
    os.ftruncate(file_descriptor, 0)
    written = os.write(file_descriptor, payload)
    if written != len(payload):
        raise OSError("private write-back output was incomplete")
    os.fsync(file_descriptor)
    os.close(file_descriptor)


if __name__ == "__main__":
    raise SystemExit(main())

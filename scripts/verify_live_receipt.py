"""Verify live evidence without printing the receipt or remote payloads."""

from __future__ import annotations

import sys
from pathlib import Path

from datahub_change_context.live_evidence import LiveEvidenceError, load_and_verify


def main() -> int:
    if len(sys.argv) != 2:
        print("live_datahub_verified=false", file=sys.stderr)
        return 2
    try:
        load_and_verify(Path(sys.argv[1]))
    except (OSError, ValueError, LiveEvidenceError):
        print("live_datahub_verified=false", file=sys.stderr)
        return 1
    print("live_datahub_verified=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

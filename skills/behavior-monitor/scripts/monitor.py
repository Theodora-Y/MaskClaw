#!/usr/bin/env python3
"""Thin CLI wrapper for the runtime behavior monitor contract."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Make `privacy_agent_project` importable when running this script directly.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.behavior_monitor import build_report, mock_events, normalize_events  # noqa: E402


def _load_input(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in input file: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of event objects")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize behavior events to JSON log stream")
    parser.add_argument("--input", type=str, help="Path to input events JSON (list)")
    parser.add_argument("--mock-input", action="store_true", help="Use built-in mock events")
    parser.add_argument("--output", type=str, help="Write output JSON to file path")
    args = parser.parse_args()

    try:
        if args.mock_input:
            events = mock_events()
        elif args.input:
            events = _load_input(Path(args.input))
        else:
            events = []

        records = normalize_events(events)
        out = build_report(records)
        payload = json.dumps(out, ensure_ascii=False, indent=2)

        if args.output:
            Path(args.output).write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)

        return 0
    except Exception as exc:
        err = {"error": str(exc), "type": exc.__class__.__name__}
        print(json.dumps(err, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Behavior monitor CLI.

Non-interactive script that normalizes UI/user events into a stable JSON stream.
"""

import argparse
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List


def _mock_events() -> List[Dict[str, Any]]:
    now = int(time.time())
    return [
        {
            "timestamp": now,
            "role": "agent",
            "action": "agent_fill_form",
            "target_id": "address_field",
            "content": "北京市海淀区xx路",
        },
        {
            "timestamp": now + 2,
            "role": "user",
            "action": "clear",
            "target_id": "address_field",
            "content": "",
        },
        {
            "timestamp": now + 3,
            "role": "user",
            "action": "input",
            "target_id": "address_field",
            "content": "公司地址",
        },
    ]


def _infer_correction(event: Dict[str, Any]) -> str:
    action = str(event.get("action", "")).lower()
    if action in {"clear", "delete", "undo"}:
        return "user_modified_previous_action"
    if action in {"cancel", "back"}:
        return "user_interrupted"
    return ""


def _normalize(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for raw in events:
        ts = raw.get("timestamp")
        if ts is None:
            ts = int(time.time())
        record = {
            "timestamp": int(ts),
            "action": str(raw.get("action", "")),
            "correction": _infer_correction(raw),
            "metadata": {
                "role": raw.get("role", "unknown"),
                "target_id": raw.get("target_id", ""),
                "content": raw.get("content", ""),
            },
        }
        records.append(record)
    return records


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
    args = parser.parse_args()

    try:
        if args.mock_input:
            events = _mock_events()
        elif args.input:
            events = _load_input(Path(args.input))
        else:
            events = []

        records = _normalize(events)
        out = {
            "session_id": f"sess-{uuid.uuid4().hex[:12]}",
            "record_count": len(records),
            "records": records,
            "summary": {
                "correction_count": sum(1 for r in records if r.get("correction")),
            },
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        err = {"error": str(exc), "type": exc.__class__.__name__}
        print(json.dumps(err, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

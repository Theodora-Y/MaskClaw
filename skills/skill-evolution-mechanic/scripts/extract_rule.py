#!/usr/bin/env python3
"""Extract candidate privacy rules from correction logs."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _mock_logs() -> List[Dict[str, Any]]:
    return [
        {"timestamp": 1700000000, "action": "agent_fill_form", "correction": "user_modified_previous_action"},
        {"timestamp": 1700000005, "action": "agent_fill_form", "correction": "user_modified_previous_action"},
        {"timestamp": 1700000010, "action": "agent_submit", "correction": ""},
    ]


def _load_input(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in input file: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of log objects")
    return data


def _build_rule(action: str, correction: str, count: int, total: int) -> Dict[str, Any]:
    confidence = min(0.95, round(0.5 + 0.1 * count, 2))
    return {
        "scene": f"action:{action}",
        "sensitive_field": "unknown",
        "strategy": f"avoid pattern triggering correction:{correction}",
        "confidence": confidence,
        "needs_review": confidence < 0.7,
        "evidence_count": count,
        "total_corrections": total,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract candidate rules from correction logs")
    parser.add_argument("--input", type=str, help="Path to normalized logs JSON")
    parser.add_argument("--mock-input", action="store_true", help="Use built-in mock logs")
    parser.add_argument("--min-support", type=int, default=2, help="Min frequency to emit a rule")
    args = parser.parse_args()

    try:
        if args.mock_input:
            logs = _mock_logs()
        elif args.input:
            logs = _load_input(Path(args.input))
        else:
            logs = []

        filtered: List[Dict[str, Any]] = []
        for item in logs:
            correction = str(item.get("correction", "")).strip()
            if correction:
                filtered.append(
                    {
                        "action": str(item.get("action", "")),
                        "correction": correction,
                    }
                )

        counter: Counter[Tuple[str, str]] = Counter((x["action"], x["correction"]) for x in filtered)
        candidates: List[Dict[str, Any]] = []
        for (action, correction), count in counter.items():
            if count >= args.min_support:
                candidates.append(_build_rule(action, correction, count, len(filtered)))

        out = {
            "input_count": len(logs),
            "filtered_count": len(filtered),
            "candidate_count": len(candidates),
            "candidates": candidates,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        err = {"error": str(exc), "type": exc.__class__.__name__}
        print(json.dumps(err, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

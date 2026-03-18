#!/usr/bin/env python3
"""CLI entry for full evolution mechanic pipeline."""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Make `privacy_agent_project` importable when running this script directly.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skills.evolution_mechanic import SkillEvolution  # noqa: E402


def _mock_logs(user_id: str) -> List[Dict[str, Any]]:
    now = int(time.time())
    return [
        {
            "event_id": f"{user_id}_{now}_001",
            "user_id": user_id,
            "ts": now,
            "app_context": "forum_register",
            "action": "fill_home_address",
            "field": "home_address",
            "resolution": "ask",
            "level": 2,
            "value_preview": "北京市海淀区xx路",
            "correction_type": "user_modified",
            "correction_value": "公司地址",
            "processed": False,
            "expire_ts": now + 86400,
        },
        {
            "event_id": f"{user_id}_{now}_002",
            "user_id": user_id,
            "ts": now + 10,
            "app_context": "forum_register",
            "action": "fill_home_address",
            "field": "home_address",
            "resolution": "ask",
            "level": 2,
            "value_preview": "北京市海淀区xx路",
            "correction_type": "user_modified",
            "correction_value": "公司地址",
            "processed": False,
            "expire_ts": now + 86400,
        },
    ]


def _load_input(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    # Try JSON array first.
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Fallback: JSONL (one JSON object per line)
    rows: List[Dict[str, Any]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {i}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"JSONL line {i} must be an object")
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full evolution mechanic pipeline")
    parser.add_argument("--user-id", type=str, default="", help="Target user id")
    parser.add_argument("--input", type=str, help="Path to correction logs (JSON array or JSONL)")
    parser.add_argument("--mock-input", action="store_true", help="Use built-in mock correction logs")
    parser.add_argument(
        "--step",
        type=str,
        default="all",
        choices=["group", "score", "extract", "sandbox", "commit", "all"],
        help="Pipeline step to run",
    )
    parser.add_argument("--min-support", type=int, default=2, help="Minimum group size")
    parser.add_argument("--threshold", type=float, default=0.6, help="Confidence threshold")
    parser.add_argument("--max-examples", type=int, default=5, help="Max examples sent to MiniCPM per group")
    parser.add_argument("--minicpm-url", type=str, default="http://127.0.0.1:8000/chat", help="MiniCPM API URL")
    parser.add_argument("--logs-root", type=str, default="memory/logs", help="Behavior logs root")
    parser.add_argument("--memory-root", type=str, default="memory", help="Memory root")
    parser.add_argument("--output", type=str, help="Write output JSON to file")
    args = parser.parse_args()

    try:
        if args.mock_input:
            user_id = args.user_id or "mock_user"
            input_logs = _mock_logs(user_id)
        elif args.input:
            input_logs = _load_input(Path(args.input))
            # If user_id not explicitly given, infer from first record.
            user_id = args.user_id or str((input_logs[0] if input_logs else {}).get("user_id", ""))
        else:
            input_logs = None
            user_id = args.user_id

        if not user_id:
            raise ValueError("--user-id is required when --input/--mock-input cannot infer user_id")

        engine = SkillEvolution(
            logs_root=args.logs_root,
            memory_root=args.memory_root,
            minicpm_url=args.minicpm_url,
        )
        result = engine.run_pipeline(
            user_id=user_id,
            step=args.step,
            min_support=args.min_support,
            threshold=args.threshold,
            max_examples=args.max_examples,
            input_logs=input_logs,
        )

        payload = json.dumps(result, ensure_ascii=False, indent=2)
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

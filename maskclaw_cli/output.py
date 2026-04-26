from __future__ import annotations

import json
from typing import Any, Iterable

import typer


def echo_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def echo_kv(title: str, rows: dict[str, Any]) -> None:
    typer.echo(title)
    width = max((len(str(k)) for k in rows), default=0)
    for key, value in rows.items():
        typer.echo(f"  {str(key).ljust(width)} : {value}")


def echo_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> None:
    if not rows:
        typer.echo("No records found.")
        return

    headers = [label for _, label in columns]
    widths = [len(label) for label in headers]
    rendered_rows: list[list[str]] = []

    for row in rows:
        rendered = [str(row.get(key, "") if row.get(key, "") is not None else "") for key, _ in columns]
        rendered_rows.append(rendered)
        for idx, value in enumerate(rendered):
            widths[idx] = max(widths[idx], len(value))

    header = "  ".join(label.ljust(widths[idx]) for idx, label in enumerate(headers))
    rule = "  ".join("-" * width for width in widths)
    typer.echo(header)
    typer.echo(rule)
    for row in rendered_rows:
        typer.echo("  ".join(value.ljust(widths[idx]) for idx, value in enumerate(row)))


def truncate(value: Any, limit: int = 42) -> str:
    text = "" if value is None else str(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def parse_key_value_args(items: Iterable[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise typer.BadParameter(f"Expected KEY=VALUE, got: {item}")
        key, value = item.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed

from __future__ import annotations

import click
import time
import typer

from maskclaw_cli.output import echo_json, truncate
from maskclaw_cli.services.http_client import ApiError
from maskclaw_cli.services.log_service import LogService

app = typer.Typer(help="Inspect audit timelines and raw evolution logs.")


@app.command("recent")
def recent(
    user_id: str | None = typer.Option(None, "--user", "-u"),
    source: str = typer.Option("timeline", "--source", help="timeline or raw."),
    event_type: str | None = typer.Option(None, "--type", help="added, reinforced, conflict, or disabled."),
    log_type: str = typer.Option("all", "--log-type", help="correction, behavior, session_trace, or all."),
    page: int = typer.Option(1, "--page", min=1),
    page_size: int = typer.Option(20, "--page-size", min=1, max=500),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        payload = LogService().recent(
            user_id=user_id,
            source=source,
            event_type=event_type,
            log_type=log_type,
            page=page,
            page_size=page_size,
        )
    except (ValueError, ApiError) as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return

    if source == "raw":
        _print_raw_logs(payload)
        return
    _print_timeline(payload)


@app.command("tail")
def tail(
    user_id: str | None = typer.Option(None, "--user", "-u"),
    log_type: str = typer.Option("all", "--log-type", help="correction, behavior, session_trace, or all."),
    limit: int = typer.Option(10, "--limit", min=1, max=500),
    follow: bool = typer.Option(False, "--follow", help="Keep polling for new raw log entries."),
    poll_interval: float = typer.Option(2.0, "--poll-interval", min=0.2, max=60.0),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    service = LogService()
    try:
        payload = service.tail(user_id=user_id, log_type=log_type, limit=limit)
    except (ValueError, ApiError) as exc:
        raise click.ClickException(str(exc)) from exc

    if json_output:
        echo_json(payload)
        return

    _print_raw_logs(payload)
    if not follow:
        return

    seen = _build_seen_keys(payload)
    try:
        while True:
            time.sleep(poll_interval)
            next_payload = service.tail(user_id=user_id, log_type=log_type, limit=limit)
            new_payload = _extract_new_raw_logs(next_payload, seen)
            if new_payload["logs"]:
                _print_raw_logs(new_payload)
    except KeyboardInterrupt:
        typer.echo("\nStopped following raw logs.")


def _print_timeline(payload: dict) -> None:
    groups = payload.get("groups", [])
    if not groups:
        typer.echo("No audit events found.")
        return

    for group in groups:
        typer.echo(str(group.get("date", "Unknown date")))
        for item in group.get("items", []):
            title = item.get("title") or item.get("summary") or ""
            summary = truncate(item.get("summary", ""), 88)
            typer.echo(
                f"  [{item.get('type_label', item.get('event_type', ''))}] "
                f"{title} | {item.get('source', '')} | {summary}"
            )
        typer.echo("")


def _print_raw_logs(payload: dict) -> None:
    logs = payload.get("logs", {})
    if not logs:
        typer.echo("No raw logs found.")
        return

    for name, records in logs.items():
        typer.echo(name)
        if not records:
            typer.echo("  (empty)")
            typer.echo("")
            continue
        for record in records:
            raw = record.get("raw", {})
            summary = truncate(
                raw.get("summary")
                or raw.get("agent_intent")
                or raw.get("action")
                or raw.get("correction_type")
                or str(raw),
                88,
            )
            typer.echo(
                f"  line={record.get('line_no', '')} ts={record.get('ts', '')} "
                f"{summary}"
            )
        typer.echo("")


def _build_seen_keys(payload: dict) -> set[tuple[str, int, int]]:
    seen: set[tuple[str, int, int]] = set()
    for name, records in payload.get("logs", {}).items():
        for record in records:
            seen.add((name, int(record.get("line_no", 0) or 0), int(record.get("ts", 0) or 0)))
    return seen


def _extract_new_raw_logs(payload: dict, seen: set[tuple[str, int, int]]) -> dict:
    filtered_logs: dict[str, list[dict]] = {}
    for name, records in payload.get("logs", {}).items():
        fresh: list[dict] = []
        for record in records:
            key = (name, int(record.get("line_no", 0) or 0), int(record.get("ts", 0) or 0))
            if key in seen:
                continue
            seen.add(key)
            fresh.append(record)
        if fresh:
            filtered_logs[name] = fresh
    return {
        **payload,
        "logs": filtered_logs,
    }

from __future__ import annotations

import click
import typer

from maskclaw_cli.output import echo_json, echo_kv, echo_table, truncate
from maskclaw_cli.services.http_client import ApiError
from maskclaw_cli.services.review_service import ReviewClientService

app = typer.Typer(help="Review pending rule changes and audit decisions.")


@app.command("pending")
def pending(
    user_id: str | None = typer.Option(None, "--user", "-u"),
    status: str = typer.Option("pending", "--status", help="pending, confirmed, dismissed, or all."),
    lifecycle_status: str = typer.Option("all", "--lifecycle-status", help="draft, pending, active, rejected, archived, or all."),
    page: int = typer.Option(1, "--page", min=1),
    page_size: int = typer.Option(20, "--page-size", min=1, max=100),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        payload = ReviewClientService().list_pending(
            user_id=user_id,
            status=status,
            lifecycle_status=lifecycle_status,
            page=page,
            page_size=page_size,
        )
    except (ValueError, ApiError) as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return

    rows = []
    for item in payload.get("items", []):
        notification = item.get("notification", {})
        target = item.get("target", {})
        rows.append(
            {
                "id": notification.get("id", ""),
                "status": notification.get("status", ""),
                "type": notification.get("notif_type", ""),
                "skill": notification.get("skill_name", ""),
                "version": notification.get("skill_version", ""),
                "state": target.get("current_state", ""),
                "bucket": target.get("storage_bucket", ""),
                "title": truncate(notification.get("title", ""), 40),
            }
        )
    echo_table(
        rows,
        [
            ("id", "ID"),
            ("status", "Status"),
            ("type", "Type"),
            ("skill", "Skill"),
            ("version", "Version"),
            ("state", "State"),
            ("bucket", "Bucket"),
            ("title", "Title"),
        ],
    )


@app.command("show")
def show(
    notif_id: int = typer.Argument(...),
    user_id: str | None = typer.Option(None, "--user", "-u"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        payload = ReviewClientService().show(notif_id, user_id=user_id)
    except (ValueError, ApiError) as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return

    notification = payload.get("notification", {})
    target = payload.get("target", {})
    echo_kv(
        "Notification",
        {
            "id": notification.get("id", ""),
            "status": notification.get("status", ""),
            "type": notification.get("notif_type", ""),
            "title": notification.get("title", ""),
            "skill_name": notification.get("skill_name", ""),
            "skill_version": notification.get("skill_version", ""),
        },
    )
    typer.echo("")
    echo_kv(
        "Target",
        {
            "source_kind": target.get("source_kind", ""),
            "current_state": target.get("current_state", ""),
            "storage_bucket": target.get("storage_bucket", ""),
            "scene": target.get("summary", {}).get("scene", ""),
            "strategy": truncate(target.get("summary", {}).get("strategy", ""), 60),
            "confidence": target.get("summary", {}).get("confidence", ""),
        },
    )
    preview = payload.get("action_preview", {})
    if preview:
        typer.echo("")
        echo_kv("Action preview", preview)
    if target.get("skill_md_preview"):
        typer.echo("\n--- SKILL.md preview ---")
        typer.echo(target["skill_md_preview"])
    if target.get("rules_preview"):
        typer.echo("\n--- rules preview ---")
        echo_json(target["rules_preview"])


@app.command("approve")
def approve(
    notif_id: int = typer.Argument(...),
    user_id: str | None = typer.Option(None, "--user", "-u"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        payload = ReviewClientService().approve(notif_id, user_id=user_id)
    except (ValueError, ApiError) as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return

    notification = payload.get("notification", {})
    sync = payload.get("skill_sync", {})
    echo_kv(
        "Review approved",
        {
            "notif_id": payload.get("notif_id", ""),
            "status": payload.get("status", ""),
            "skill": notification.get("skill_name", ""),
            "version": notification.get("skill_version", ""),
            "action": sync.get("action", ""),
            "applied": sync.get("applied", False),
            "warning": sync.get("warning", ""),
        },
    )


@app.command("reject")
def reject(
    notif_id: int = typer.Argument(...),
    reason: str | None = typer.Option(None, "--reason"),
    user_id: str | None = typer.Option(None, "--user", "-u"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        payload = ReviewClientService().reject(notif_id, reason=reason, user_id=user_id)
    except (ValueError, ApiError) as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return

    notification = payload.get("notification", {})
    sync = payload.get("skill_sync", {})
    echo_kv(
        "Review rejected",
        {
            "notif_id": payload.get("notif_id", ""),
            "status": payload.get("status", ""),
            "skill": notification.get("skill_name", ""),
            "version": notification.get("skill_version", ""),
            "action": sync.get("action", ""),
            "applied": sync.get("applied", False),
            "warning": sync.get("warning", ""),
        },
    )

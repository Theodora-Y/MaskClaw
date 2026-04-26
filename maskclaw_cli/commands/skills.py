from __future__ import annotations

import click
import typer

from maskclaw_cli.output import echo_json, echo_kv, echo_table
from maskclaw_cli.services.skill_service import SkillService

app = typer.Typer(help="Inspect local user skill assets.")


@app.command("list")
def list_skills(
    user_id: str | None = typer.Option(None, "--user", "-u"),
    status: str = typer.Option("all", "--status", help="active, pending, draft, rejected, archived, or all."),
    app_name: str | None = typer.Option(None, "--app", help="Filter by app or scene keyword."),
    query: str | None = typer.Option(None, "--q", help="Search skill name / scene / strategy / rule text."),
    page: int = typer.Option(1, "--page", min=1),
    page_size: int = typer.Option(20, "--page-size", min=1, max=200),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    service = SkillService()
    try:
        payload = service.list_skills_page(
            user_id=user_id,
            status=status,
            app=app_name,
            query=query,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return
    rows = payload["skills"]
    echo_table(
        rows,
        [
            ("skill", "Skill"),
            ("version", "Version"),
            ("status", "Status"),
            ("bucket", "Bucket"),
            ("app", "App"),
            ("strategy", "Strategy"),
            ("confidence", "Conf"),
            ("scene", "Scene"),
        ],
    )


@app.command("show")
def show_skill(
    skill_name: str = typer.Argument(...),
    version: str | None = typer.Option(None, "--version", "-v"),
    user_id: str | None = typer.Option(None, "--user", "-u"),
    full: bool = typer.Option(False, "--full", help="Print full SKILL.md and rules.json content."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        payload = SkillService().show_skill(skill_name, version, user_id)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return
    echo_kv("Skill summary", payload["summary"])
    echo_kv("Rules", payload["rules"])
    if full:
        typer.echo("\n--- SKILL.md ---")
        typer.echo(payload["skill_md"])
        if payload["rules_json"]:
            typer.echo("\n--- rules.json ---")
            typer.echo(payload["rules_json"])


@app.command("archive")
def archive(
    skill_name: str = typer.Argument(...),
    version: str = typer.Option(..., "--version", "-v"),
    user_id: str | None = typer.Option(None, "--user", "-u"),
    reason: str = typer.Option("user_archived", "--reason"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        payload = SkillService().archive_skill(skill_name, version, user_id=user_id, reason=reason)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return
    echo_kv("Archived", payload)


@app.command("restore")
def restore(
    skill_name: str = typer.Argument(...),
    version: str = typer.Option(..., "--version", "-v"),
    user_id: str | None = typer.Option(None, "--user", "-u"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        payload = SkillService().restore_skill(skill_name, version, user_id=user_id)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return
    echo_kv("Restored", payload)


@app.command("diff")
def diff_skill(
    skill_name: str = typer.Argument(...),
    version: str = typer.Option(..., "--version", "-v", help="Primary version to inspect."),
    against: str = typer.Option(..., "--against", help="Comparison version."),
    user_id: str | None = typer.Option(None, "--user", "-u"),
    context_lines: int = typer.Option(3, "--context", min=0, max=20, help="Unified diff context lines."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        payload = SkillService().diff_skill(
            skill_name,
            version=version,
            against=against,
            user_id=user_id,
            context_lines=context_lines,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return
    echo_kv("Comparison", payload["comparison"])
    if payload["rule_field_changes"]:
        typer.echo("\nChanged rule fields")
        for item in payload["rule_field_changes"]:
            typer.echo(f"  - {item['field']}: {item['baseline']} -> {item['current']}")
    if payload["skill_md_diff"]:
        typer.echo("\n--- SKILL.md diff ---")
        typer.echo("\n".join(payload["skill_md_diff"]))
    if payload["rules_json_diff"]:
        typer.echo("\n--- rules.json diff ---")
        typer.echo("\n".join(payload["rules_json_diff"]))
    if not payload["skill_md_diff"] and not payload["rules_json_diff"] and not payload["rule_field_changes"]:
        typer.echo("\nNo content changes detected.")


@app.command("edit")
def edit_skill(
    skill_name: str = typer.Argument(...),
    version: str = typer.Option(..., "--version", "-v"),
    user_id: str | None = typer.Option(None, "--user", "-u"),
    editor: str | None = typer.Option(None, "--editor", help="Override the editor used to open the skill files."),
    validate_only: bool = typer.Option(
        False,
        "--validate-only",
        help="Resolve files and run validation without opening an editor.",
    ),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        payload = SkillService().edit_skill(
            skill_name,
            version=version,
            user_id=user_id,
            editor=editor,
            validate_only=validate_only,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return
    echo_kv("Edit target", payload["files"])
    echo_kv("Validation", {"ok": payload["validation_after"]["ok"], "editor_opened": payload["editor_opened"]})
    if payload.get("editor_note"):
        typer.echo(f"\nEditor note: {payload['editor_note']}")
    if payload["validation_after"]["warnings"]:
        typer.echo("\nWarnings")
        for warning in payload["validation_after"]["warnings"]:
            typer.echo(f"  - {warning}")
    if payload["validation_after"]["errors"]:
        typer.echo("\nErrors")
        for error in payload["validation_after"]["errors"]:
            typer.echo(f"  - {error}")
    typer.echo(f"\nDB sync: {payload['db_sync']['status']} ({payload['db_sync']['note']})")

from __future__ import annotations

import click
import typer

from maskclaw_cli.output import echo_json, echo_kv
from maskclaw_cli.services.guard_service import GuardService

app = typer.Typer(help="Local privacy guard commands for agents and scripts.")


@app.command("decide")
def decide(
    input_path: str | None = typer.Option(None, "--input", "-i", help="Path to event JSON."),
    stdin: bool = typer.Option(False, "--stdin", help="Read event JSON from stdin."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    service = GuardService()
    try:
        event = service.load_event(input_path, stdin)
        payload = service.decide(event)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return
    echo_kv(
        "Guard decision",
        {
            "judgment": payload["judgment"],
            "confidence": payload["confidence"],
            "matched_rules": ", ".join(payload["matched_rules"]),
            "needs_review": payload["needs_review"],
            "reason": payload["reason"],
        },
    )


@app.command("analyze")
def analyze(
    input_path: str = typer.Option(..., "--input", "-i", help="Path to a local screenshot/image."),
    command: str = typer.Option("分析当前页面隐私", "--command", help="User task or page analysis instruction."),
    user_id: str | None = typer.Option(None, "--user", help="Override the configured current user."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    service = GuardService()
    try:
        payload = service.analyze_image(input_path, command, user_id=user_id)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return
    echo_kv(
        "Guard analysis",
        {
            "scene_summary": payload.get("scene_summary", ""),
            "scene_source": payload.get("scene_summary_source", ""),
            "judgment": payload.get("decision", {}).get("judgment", ""),
            "matched_rules": ", ".join(payload.get("decision", {}).get("matched_rules", [])),
            "candidate_keywords": ", ".join(payload.get("candidate_keywords", [])),
            "processing_time_ms": payload.get("processing_time_ms", 0),
        },
    )


@app.command("redact")
def redact(
    input_path: str = typer.Option(..., "--input", "-i", help="Path to a local screenshot/image."),
    output_path: str = typer.Option(..., "--output", "-o", help="Where to write the masked image."),
    command: str = typer.Option("分析当前页面隐私", "--command", help="User task or page analysis instruction."),
    method: str = typer.Option("blur", "--method", help="blur, mosaic, or block."),
    user_id: str | None = typer.Option(None, "--user", help="Override the configured current user."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    service = GuardService()
    try:
        payload = service.redact_image(
            input_path,
            command,
            output_path,
            method=method,
            user_id=user_id,
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        echo_json(payload)
        return
    echo_kv(
        "Guard redaction",
        {
            "output_path": payload.get("output_path", ""),
            "method": payload.get("method", method),
            "masked_count": payload.get("masked_count", 0),
            "judgment": payload.get("decision", {}).get("judgment", ""),
            "matched_rules": ", ".join(payload.get("decision", {}).get("matched_rules", [])),
            "processing_time_ms": payload.get("processing_time_ms", 0),
        },
    )

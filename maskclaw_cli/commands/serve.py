from __future__ import annotations

import typer

from maskclaw_cli.context import ConfigStore
from maskclaw_cli.output import echo_json, echo_table
from maskclaw_cli.services.runtime_service import RuntimeService

app = typer.Typer(help="Start, stop, and inspect MaskClaw services.")


@app.command("status")
def status(json_output: bool = typer.Option(False, "--json")) -> None:
    rows = RuntimeService().status()
    if json_output:
        echo_json({"services": rows})
        return
    echo_table(
        rows,
        [
            ("service", "Service"),
            ("required", "Required"),
            ("managed", "Managed"),
            ("capabilities", "Roles"),
            ("endpoint", "Endpoint"),
            ("status", "Status"),
            ("port", "Port"),
            ("port_alive", "Port Alive"),
            ("pid", "PID"),
            ("pid_alive", "PID Alive"),
            ("depends_on", "Depends On"),
            ("log", "Log"),
        ],
    )


@app.command("up")
def up(
    mode: str | None = typer.Option(None, "--mode", help="personal uses local/Ollama workflows; enterprise targets MiniCPM or intranet services."),
    no_frontend: bool = typer.Option(False, "--no-frontend", help="Do not start the Vite frontend."),
    no_bridge: bool = typer.Option(False, "--no-bridge", help="Do not start the AutoGLM bridge."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print planned services without starting them."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if mode is not None:
        if mode not in {"personal", "enterprise"}:
            raise typer.BadParameter("Mode must be 'personal' or 'enterprise'.")
        store = ConfigStore()
        config = store.load()
        config.mode = mode
        store.save(config)
    rows, ok = RuntimeService().start(no_frontend=no_frontend, no_bridge=no_bridge, dry_run=dry_run)
    if json_output:
        echo_json({"results": rows, "mode": ConfigStore().load().mode, "ok": ok})
        if not ok and not dry_run:
            raise typer.Exit(code=1)
        return
    echo_table(
        rows,
        [
            ("service", "Service"),
            ("status", "Status"),
            ("required", "Required"),
            ("managed", "Managed"),
            ("capabilities", "Roles"),
            ("pid", "PID"),
            ("port", "Port"),
            ("endpoint", "Endpoint"),
            ("depends_on", "Depends On"),
            ("log", "Log"),
            ("command", "Command"),
            ("error", "Error"),
        ],
    )
    if not ok and not dry_run:
        raise typer.Exit(code=1)


@app.command("down")
def down(json_output: bool = typer.Option(False, "--json")) -> None:
    rows = RuntimeService().stop()
    if json_output:
        echo_json({"results": rows, "mode": ConfigStore().load().mode})
        return
    echo_table(rows, [("service", "Service"), ("status", "Status"), ("pid", "PID"), ("error", "Error")])

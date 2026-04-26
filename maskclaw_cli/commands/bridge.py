from __future__ import annotations

import typer

from maskclaw_cli.context import ConfigStore
from maskclaw_cli.output import echo_json, echo_table
from maskclaw_cli.services.runtime_service import RuntimeService

app = typer.Typer(help="Manage the Windows AutoGLM phone bridge.")


@app.command("status")
def status(json_output: bool = typer.Option(False, "--json")) -> None:
    rows = [row for row in RuntimeService().status() if row["service"] == "bridge-autoglm"]
    for row in rows:
        row["autoglm_dir"] = ConfigStore().load().autoglm_dir
    if json_output:
        echo_json({"services": rows})
        return
    echo_table(
        rows,
        [
            ("service", "Service"),
            ("port", "Port"),
            ("port_alive", "Port Alive"),
            ("pid", "PID"),
            ("pid_alive", "PID Alive"),
            ("autoglm_dir", "AutoGLM Dir"),
            ("log", "Log"),
        ],
    )


@app.command("start")
def start(
    autoglm_dir: str | None = typer.Option(None, "--autoglm-dir", help="Open-AutoGLM directory path. Saved to config and used on subsequent runs."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if autoglm_dir:
        store = ConfigStore()
        config = store.load()
        config.autoglm_dir = autoglm_dir
        store.save(config)
        typer.echo(f"Open-AutoGLM dir saved: {autoglm_dir}")

    rows, ok = RuntimeService().start(dry_run=dry_run, only={"bridge-autoglm"})
    for row in rows:
        if row.get("service") == "bridge-autoglm":
            row["autoglm_dir"] = ConfigStore().load().autoglm_dir

    if json_output:
        echo_json({"results": rows, "ok": ok})
        if not ok and not dry_run:
            raise typer.Exit(code=1)
        return
    echo_table(
        rows,
        [
            ("service", "Service"),
            ("status", "Status"),
            ("pid", "PID"),
            ("port", "Port"),
            ("autoglm_dir", "AutoGLM Dir"),
            ("log", "Log"),
            ("command", "Command"),
            ("error", "Error"),
        ],
    )
    if not ok and not dry_run:
        raise typer.Exit(code=1)


@app.command("stop")
def stop(json_output: bool = typer.Option(False, "--json")) -> None:
    service = RuntimeService()
    rows = service.stop(only={"bridge-autoglm"})
    if json_output:
        echo_json({"results": rows})
        return
    echo_table(rows, [("service", "Service"), ("status", "Status"), ("pid", "PID"), ("error", "Error")])

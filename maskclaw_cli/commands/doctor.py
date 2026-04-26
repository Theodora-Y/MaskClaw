from __future__ import annotations

import typer

from maskclaw_cli.output import echo_json, echo_table
from maskclaw_cli.services.doctor_service import DoctorService

app = typer.Typer(help="Check local MaskClaw environment health.")


@app.callback(invoke_without_command=True)
def run(
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    checks = DoctorService().run()
    if json_output:
        echo_json({"checks": checks})
        return
    echo_table(
        checks,
        [
            ("check", "Check"),
            ("ok", "OK"),
            ("value", "Value"),
            ("note", "Note"),
        ],
    )

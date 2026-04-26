from __future__ import annotations

import typer

from maskclaw_cli import __version__
from maskclaw_cli.context import ensure_project_root_on_path

ensure_project_root_on_path()

from maskclaw_cli.commands import auth, bridge, doctor, guard, logs, model, review, serve, skills, task

app = typer.Typer(
    help="MaskClaw CLI: privacy guard, skill audit terminal, and agent bridge.",
    no_args_is_help=True,
)

app.add_typer(doctor.app, name="doctor")
app.add_typer(serve.app, name="serve")
app.add_typer(model.app, name="model")
app.add_typer(bridge.app, name="bridge")
app.add_typer(auth.app, name="auth")
app.add_typer(skills.app, name="skills")
app.add_typer(review.app, name="review")
app.add_typer(logs.app, name="logs")
app.add_typer(guard.app, name="guard")
app.add_typer(task.app, name="task")


def run() -> None:
    app()


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", help="Show CLI version and exit."),
) -> None:
    if version:
        typer.echo(f"maskclaw-cli {__version__}")
        raise typer.Exit()

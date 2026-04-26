from __future__ import annotations

import typer

from maskclaw_cli.output import echo_json, echo_kv, echo_table
from maskclaw_cli.services.model_service import ModelService

app = typer.Typer(help="Manage model backend selection.")


@app.command("list")
def list_backends(json_output: bool = typer.Option(False, "--json")) -> None:
    rows = ModelService().list_backends()
    if json_output:
        echo_json({"backends": rows})
        return
    echo_table(rows, [("backend", "Backend"), ("endpoint", "Default Endpoint"), ("description", "Description")])


@app.command("use")
def use_backend(
    backend: str = typer.Argument(..., help="minicpm, ollama, gemma, or none"),
    endpoint: str | None = typer.Option(None, "--endpoint", help="Model service endpoint."),
    model_name: str | None = typer.Option(None, "--model", help="Local model name, e.g. gemma:2b."),
    mode: str | None = typer.Option(None, "--mode", help="personal uses local backends; enterprise targets intranet MiniCPM."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    try:
        config, path = ModelService().use_backend(backend, endpoint, model_name, mode)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    payload = {
        "config_path": path,
        "model_backend": config.model_backend,
        "model_name": config.model_name,
        "model_endpoint": config.model_endpoint,
        "mode": config.mode,
    }
    if json_output:
        echo_json(payload)
        return
    echo_kv("Model backend updated", payload)


@app.command("status")
def status(json_output: bool = typer.Option(False, "--json")) -> None:
    payload = ModelService().status()
    if json_output:
        echo_json(payload)
        return
    echo_kv(
        "Model status",
        {
            "backend": payload["model_backend"],
            "model": payload["model_name"],
            "endpoint": payload["model_endpoint"],
            "mode": payload["mode"],
            "alive": payload["model_alive"],
        },
    )

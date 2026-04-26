from __future__ import annotations

import getpass

import click
import typer

from maskclaw_cli.output import echo_json, echo_kv
from maskclaw_cli.services.auth_service import AuthService
from maskclaw_cli.services.http_client import ApiError

app = typer.Typer(help="Manage CLI user context.")


@app.command("login")
def login(
    email: str = typer.Option(..., "--email", "-e"),
    password: str | None = typer.Option(None, "--password", "-p", help="Omit to prompt securely."),
    api_base_url: str | None = typer.Option(None, "--api-base-url"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    if password is None:
        password = getpass.getpass("Password: ")
    try:
        config, path = AuthService().login(email, password, api_base_url)
    except ApiError as exc:
        raise click.ClickException(f"Login failed ({exc.status}): {exc.message}") from exc
    payload = {
        "user_id": config.current_user_id,
        "username": config.username,
        "api_base_url": config.api_base_url,
        "config_path": path,
    }
    if json_output:
        echo_json(payload)
        return
    echo_kv("Logged in", payload)


@app.command("whoami")
def whoami(json_output: bool = typer.Option(False, "--json")) -> None:
    config = AuthService().whoami()
    payload = {
        "user_id": config.current_user_id or "",
        "username": config.username or "",
        "api_base_url": config.api_base_url,
        "mode": config.mode,
        "model_backend": config.model_backend,
        "model_name": config.model_name,
    }
    if json_output:
        echo_json(payload)
        return
    echo_kv("Current CLI context", payload)


@app.command("logout")
def logout(json_output: bool = typer.Option(False, "--json")) -> None:
    path = AuthService().logout()
    payload = {"config_path": path, "logged_out": True}
    if json_output:
        echo_json(payload)
        return
    echo_kv("Logged out", payload)


@app.command("use-user")
def use_user(
    user_id: str = typer.Argument(..., help="Local/demo user_id, e.g. demo_UserC."),
    username: str | None = typer.Option(None, "--username"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    config, path = AuthService().use_user(user_id, username)
    payload = {
        "user_id": config.current_user_id,
        "username": config.username,
        "config_path": path,
        "note": "No token stored. This is suitable for local/demo file scanning.",
    }
    if json_output:
        echo_json(payload)
        return
    echo_kv("User context selected", payload)

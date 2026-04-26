from __future__ import annotations

import json


def test_auth_use_user_and_logout(runner, cli_app):
    result = runner.invoke(cli_app, ["auth", "use-user", "demo_UserC", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["user_id"] == "demo_UserC"

    whoami = runner.invoke(cli_app, ["auth", "whoami", "--json"])
    assert whoami.exit_code == 0
    whoami_payload = json.loads(whoami.stdout)
    assert whoami_payload["user_id"] == "demo_UserC"

    logout = runner.invoke(cli_app, ["auth", "logout", "--json"])
    assert logout.exit_code == 0
    logout_payload = json.loads(logout.stdout)
    assert logout_payload["logged_out"] is True

    whoami_after = runner.invoke(cli_app, ["auth", "whoami", "--json"])
    assert whoami_after.exit_code == 0
    whoami_after_payload = json.loads(whoami_after.stdout)
    assert whoami_after_payload["user_id"] == ""


def test_model_use_and_status(runner, cli_app):
    use_none = runner.invoke(cli_app, ["model", "use", "none", "--json"])
    assert use_none.exit_code == 0
    payload_none = json.loads(use_none.stdout)
    assert payload_none["model_backend"] == "none"
    assert payload_none["model_endpoint"] == ""

    status_none = runner.invoke(cli_app, ["model", "status", "--json"])
    assert status_none.exit_code == 0
    status_none_payload = json.loads(status_none.stdout)
    assert status_none_payload["model_backend"] == "none"
    assert status_none_payload["model_alive"] is False

    use_ollama = runner.invoke(
        cli_app,
        ["model", "use", "ollama", "--model", "gemma:2b", "--endpoint", "http://127.0.0.1:8005", "--mode", "personal", "--json"],
    )
    assert use_ollama.exit_code == 0
    payload_ollama = json.loads(use_ollama.stdout)
    assert payload_ollama["model_backend"] == "ollama"
    assert payload_ollama["model_name"] == "gemma:2b"
    assert payload_ollama["mode"] == "personal"

    status_ollama = runner.invoke(cli_app, ["model", "status", "--json"])
    assert status_ollama.exit_code == 0
    status_ollama_payload = json.loads(status_ollama.stdout)
    assert status_ollama_payload["service_roles"]["ollama-proxy"]["endpoint"] == "http://127.0.0.1:8005"
    assert status_ollama_payload["model_roles"]["skillgen"] == "ollama-proxy"

from __future__ import annotations

import json


def test_serve_status_and_dry_run(runner, cli_app):
    runner.invoke(cli_app, ["model", "use", "ollama", "--model", "gemma:2b", "--endpoint", "http://127.0.0.1:8005", "--json"])

    status_result = runner.invoke(cli_app, ["serve", "status", "--json"])
    assert status_result.exit_code == 0
    status_payload = json.loads(status_result.stdout)
    service_names = {item["service"] for item in status_payload["services"]}
    assert "api" in service_names
    assert "evolution-daemon" in service_names
    assert "ollama-proxy" in service_names
    assert "bridge-autoglm" in service_names

    dry_run_result = runner.invoke(cli_app, ["serve", "up", "--mode", "personal", "--dry-run", "--no-frontend", "--no-bridge", "--json"])
    assert dry_run_result.exit_code == 0
    dry_run_payload = json.loads(dry_run_result.stdout)
    dry_run_names = {item["service"] for item in dry_run_payload["results"]}
    assert dry_run_payload["mode"] == "personal"
    assert dry_run_payload["ok"] is True
    assert {"api", "evolution-daemon", "ollama-proxy"} <= dry_run_names
    assert all(item["status"] == "dry-run" for item in dry_run_payload["results"])

    down_result = runner.invoke(cli_app, ["serve", "down", "--json"])
    assert down_result.exit_code == 0
    down_payload = json.loads(down_result.stdout)
    assert "results" in down_payload


def test_bridge_status_and_dry_run(runner, cli_app):
    status_result = runner.invoke(cli_app, ["bridge", "status", "--json"])
    assert status_result.exit_code == 0
    status_payload = json.loads(status_result.stdout)
    assert len(status_payload["services"]) == 1
    assert status_payload["services"][0]["service"] == "bridge-autoglm"

    dry_run_result = runner.invoke(cli_app, ["bridge", "start", "--dry-run", "--json"])
    assert dry_run_result.exit_code == 0
    dry_run_payload = json.loads(dry_run_result.stdout)
    assert dry_run_payload["ok"] is True
    assert len(dry_run_payload["results"]) == 1
    assert dry_run_payload["results"][0]["service"] == "bridge-autoglm"
    assert dry_run_payload["results"][0]["status"] in {"dry-run", "already-running"}

    stop_result = runner.invoke(cli_app, ["bridge", "stop", "--json"])
    assert stop_result.exit_code == 0
    stop_payload = json.loads(stop_result.stdout)
    assert len(stop_payload["results"]) == 1
    assert stop_payload["results"][0]["service"] == "bridge-autoglm"

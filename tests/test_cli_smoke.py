from __future__ import annotations

import json


def test_version_and_help(runner, cli_app):
    version_result = runner.invoke(cli_app, ["--version"])
    assert version_result.exit_code == 0
    assert "maskclaw-cli" in version_result.stdout

    help_result = runner.invoke(cli_app, ["--help"])
    assert help_result.exit_code == 0
    assert "doctor" in help_result.stdout
    assert "model" in help_result.stdout
    assert "skills" in help_result.stdout
    assert "review" in help_result.stdout
    assert "logs" in help_result.stdout


def test_doctor_json(runner, cli_app):
    result = runner.invoke(cli_app, ["doctor", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    check_names = {item["check"] for item in payload["checks"]}
    assert "project-root" in check_names
    assert "model-backend" in check_names
    assert "path:windows_sdk/autoglm_server.py" in check_names
    assert "service:evolution-daemon" in check_names
    assert "model-role:skillgen" in check_names

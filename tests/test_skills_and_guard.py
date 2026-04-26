from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from maskclaw_cli.services.local_log_service import LocalLogService

from maskclaw_cli.services.skill_service import SkillService
from skill_registry.skill_db import SkillDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_skill_dir(base_dir: Path, skill_name: str, version: str) -> tuple[Path, dict]:
    skill_dir = base_dir / skill_name / version
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\nversion: {version}\n---\n# {skill_name}\n",
        encoding="utf-8",
    )
    rules = {
        "skill_name": skill_name,
        "version": version,
        "scene": f"scene for {skill_name}",
        "rule_text": "mask the sensitive field",
        "strategy": "mask",
        "confidence": 0.82,
        "app_context": "wechat",
    }
    (skill_dir / "rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    return skill_dir, rules


@pytest.fixture()
def local_tmp_dir() -> Path:
    base = PROJECT_ROOT / ".pytest_tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"phase2_case_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_skills_list_and_show(runner, cli_app):
    list_result = runner.invoke(cli_app, ["skills", "list", "--user", "demo_UserC", "--json"])
    assert list_result.exit_code == 0
    list_payload = json.loads(list_result.stdout)
    assert list_payload["user_id"] == "demo_UserC"
    assert list_payload["count"] > 0
    assert any(skill["skill"] == "alipay-scan-pay" for skill in list_payload["skills"])

    show_result = runner.invoke(cli_app, ["skills", "show", "alipay-scan-pay", "--user", "demo_UserC", "--version", "v1.0.0", "--json"])
    assert show_result.exit_code == 0
    show_payload = json.loads(show_result.stdout)
    assert show_payload["summary"]["skill"] == "alipay-scan-pay"
    assert show_payload["rules"]["strategy"] == "mask"
    assert "支付记录由支付宝保管" in show_payload["rules"]["rule_text"]


def test_guard_decide_from_json_file(runner, cli_app, event_json_path):
    result = runner.invoke(cli_app, ["guard", "decide", "--input", str(event_json_path), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["judgment"] == "mask"
    assert payload["needs_review"] is False
    assert payload["matched_rules"]
    assert payload["retrieval"]["source"] == "local_active_rules"
    assert payload["decision_trace"]["match_found"] is True


def test_skills_diff_against_registry(runner, cli_app):
    result = runner.invoke(
        cli_app,
        [
            "skills",
            "diff",
            "alipay-scan-pay",
            "--user",
            "demo_UserC",
            "--version",
            "v1.0.0",
            "--against",
            "registry",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["skill_name"] == "alipay-scan-pay"
    assert payload["comparison"]["against"] == "registry"
    assert "current" in payload["comparison"]
    assert "baseline" in payload["comparison"]


def test_skills_edit_validate_only(runner, cli_app):
    result = runner.invoke(
        cli_app,
        [
            "skills",
            "edit",
            "alipay-scan-pay",
            "--user",
            "demo_UserC",
            "--version",
            "v1.0.0",
            "--validate-only",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["editor_opened"] is False
    assert payload["validation_after"]["ok"] is True
    assert payload["db_sync"]["status"] == "deferred"


def test_notepad_editor_targets_only_open_skill_md():
    service = SkillService()
    record = service.get_skill("alipay-scan-pay", "v1.0.0", "demo_UserC")
    opened, skipped, note = service._select_editor_targets(["notepad"], record)
    assert opened == [str(record.skill_md_path)]
    assert skipped == [str(record.rules_json_path)]
    assert note is not None


def test_skills_archive_and_restore_change_bucket(monkeypatch, local_tmp_dir: Path):
    user_id = "phase2_user"
    db = SkillDB(db_path=str(local_tmp_dir / "skill_registry.db"))
    user_root = local_tmp_dir / "user_skills"
    skill_dir, rules = _write_skill_dir(user_root / user_id, "wechat-send", "v1.0.0")
    assert db.add_skill(user_id, "wechat-send", "v1.0.0", str(skill_dir), rules) is True

    monkeypatch.setattr("maskclaw_cli.services.skill_service.USER_SKILLS_ROOT", user_root)
    service = SkillService(db=db)

    archived = service.archive_skill("wechat-send", "v1.0.0", user_id=user_id, reason="phase2_test")
    assert archived["status"] == "archived"
    detail = db.get_skill_detail(user_id, "wechat-send", "v1.0.0")
    assert detail is not None
    assert detail["storage_bucket"] == "trash"
    assert Path(detail["path"]).exists()

    restored = service.restore_skill("wechat-send", "v1.0.0", user_id=user_id)
    assert restored["status"] == "active"
    detail = db.get_skill_detail(user_id, "wechat-send", "v1.0.0")
    assert detail is not None
    assert detail["storage_bucket"] == "active"
    assert Path(detail["path"]).exists()


def test_skills_edit_syncs_registry_after_successful_edit(monkeypatch, local_tmp_dir: Path):
    user_id = "phase2_user"
    db = SkillDB(db_path=str(local_tmp_dir / "skill_registry.db"))
    user_root = local_tmp_dir / "user_skills"
    skill_dir, rules = _write_skill_dir(user_root / user_id, "wechat-send", "v1.0.0")
    assert db.add_skill(user_id, "wechat-send", "v1.0.0", str(skill_dir), rules) is True

    monkeypatch.setattr("maskclaw_cli.services.skill_service.USER_SKILLS_ROOT", user_root)
    monkeypatch.setattr("maskclaw_cli.services.skill_service.SkillService._build_editor_command", staticmethod(lambda editor=None: ["notepad"]))

    def fake_run(command, cwd=None, check=False):
        rules_path = Path(cwd) / "rules.json"
        payload = json.loads(rules_path.read_text(encoding="utf-8"))
        payload["rule_text"] = "edited rule text"
        rules_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        class _Completed:
            returncode = 0

        return _Completed()

    monkeypatch.setattr("maskclaw_cli.services.skill_service.subprocess.run", fake_run)

    payload = SkillService(db=db).edit_skill("wechat-send", "v1.0.0", user_id=user_id, editor="notepad")
    assert payload["db_sync"]["status"] == "synced"
    detail = db.get_skill_detail(user_id, "wechat-send", "v1.0.0")
    assert detail is not None
    rules_json = detail["rules_json_content"]
    if isinstance(rules_json, str):
        rules_json = json.loads(rules_json)
    assert rules_json["rule_text"] == "edited rule text"


def test_local_logs_tail_returns_latest_raw_records(local_tmp_dir: Path):
    project_root = local_tmp_dir
    log_root = project_root / "memory" / "logs" / "demo_UserC"
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / "correction_log.jsonl"
    log_path.write_text(
        "\n".join(
            [
                json.dumps({"ts": 100, "action": "older"}),
                json.dumps({"ts": 200, "action": "newer"}),
            ]
        ),
        encoding="utf-8",
    )

    payload = LocalLogService(project_root=project_root).tail("demo_UserC", log_type="correction", limit=1)
    assert payload["pagination"]["total"] == 2
    records = payload["logs"]["correction_log.jsonl"]
    assert len(records) == 1
    assert records[0]["raw"]["action"] == "newer"


def test_guard_analyze_via_api_returns_structured_payload(runner, cli_app, monkeypatch, sample_image_path: Path):
    def fake_multipart(method, url, fields=None, files=None, token=None, timeout=30.0):
        assert method == "POST"
        assert url.endswith("/guard/analyze")
        assert fields["command"] == "分析当前页面隐私"
        assert files["image"][0] == sample_image_path.name
        return {
            "success": True,
            "scene_summary": "支付宝支付页",
            "scene_summary_source": "fallback_ocr_only",
            "decision": {
                "judgment": "mask",
                "matched_rules": ["demo_UserC:alipay-scan-pay:v1.0.0"],
            },
            "candidate_keywords": ["支付金额", "商家信息"],
            "processing_time_ms": 12,
        }

    monkeypatch.setattr("maskclaw_cli.services.guard_service.request_multipart_json", fake_multipart)
    result = runner.invoke(
        cli_app,
        ["guard", "analyze", "--input", str(sample_image_path), "--user", "demo_UserC", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["transport"] == "api"
    assert payload["decision"]["judgment"] == "mask"


def test_guard_redact_via_api_decodes_image_payload(runner, cli_app, monkeypatch, sample_image_path: Path):
    def fake_multipart(method, url, fields=None, files=None, token=None, timeout=30.0):
        assert method == "POST"
        assert url.endswith("/guard/redact")
        assert fields["method"] == "blur"
        return {
            "success": True,
            "method": "blur",
            "mime_type": "image/png",
            "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WnV7m8AAAAASUVORK5CYII=",
            "detected_regions": [{"x": 1, "y": 2, "width": 3, "height": 4}],
            "masked_count": 1,
            "processing_time_ms": 18,
            "decision": {"judgment": "mask", "matched_rules": ["rule-1"]},
        }

    monkeypatch.setattr("maskclaw_cli.services.guard_service.request_multipart_json", fake_multipart)
    output_path = sample_image_path.parent / "masked.png"
    result = runner.invoke(
        cli_app,
        [
            "guard",
            "redact",
            "--input",
            str(sample_image_path),
            "--output",
            str(output_path),
            "--user",
            "demo_UserC",
            "--json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["transport"] == "api"
    assert Path(payload["output_path"]).exists()
    assert output_path.read_bytes()

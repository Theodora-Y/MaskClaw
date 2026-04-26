from __future__ import annotations

import json

from maskclaw_cli.context import ConfigStore, MaskClawConfig
from maskclaw_cli.services.http_client import ApiError


def _save_logged_in_context() -> None:
    ConfigStore().save(
        MaskClawConfig(
            current_user_id="demo_UserC",
            username="王明",
            token="demo-token",
            api_base_url="http://127.0.0.1:8001",
            model_backend="ollama",
            model_name="gemma:2b",
            model_endpoint="http://127.0.0.1:8005",
            mode="personal",
        )
    )


def test_auth_login_success_and_connection_error(runner, cli_app, monkeypatch):
    def fake_login_request(method, url, payload=None, token=None, timeout=8.0):
        assert method == "POST"
        assert url.endswith("/auth/login")
        assert payload == {"email": "demo_userc@maskclaw.dev", "password": "demo1234"}
        return {
            "user_id": "demo_UserC",
            "username": "王明",
            "token": "demo-token",
            "onboarding_done": True,
        }

    monkeypatch.setattr("maskclaw_cli.services.auth_service.request_json", fake_login_request)
    result = runner.invoke(
        cli_app,
        ["auth", "login", "--email", "demo_userc@maskclaw.dev", "--password", "demo1234", "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["user_id"] == "demo_UserC"
    assert payload["username"] == "王明"

    def fake_error(*args, **kwargs):
        raise ApiError(0, "Connection refused")

    monkeypatch.setattr("maskclaw_cli.services.auth_service.request_json", fake_error)
    failure = runner.invoke(
        cli_app,
        ["auth", "login", "--email", "demo_userc@maskclaw.dev", "--password", "demo1234", "--json"],
    )
    assert failure.exit_code != 0
    assert "Login failed (0): Connection refused" in failure.output


def test_review_pending_show_approve_and_reject(runner, cli_app, monkeypatch):
    _save_logged_in_context()

    review_detail = {
        "notification": {
            "id": 11,
            "status": "pending",
            "notif_type": "skill_added",
            "title": "请确认新增规则：支付宝扫码支付",
            "skill_name": "alipay-scan-pay",
            "skill_version": "v1.0.0",
        },
        "target": {
            "source_kind": "skills",
            "current_state": "pending",
            "storage_bucket": "review",
            "summary": {
                "scene": "支付宝扫码支付",
                "strategy": "支付截图需要脱敏",
                "confidence": 0.92,
            },
            "skill_md_preview": "# alipay-scan-pay",
            "rules_preview": {"scene": "支付宝扫码支付"},
        },
        "action_preview": {
            "approve": "Activate this candidate skill and move it into the active skill directory.",
            "reject": "Reject this candidate skill and keep it in the review area.",
        },
    }

    def fake_review_request(method, url, payload=None, token=None, timeout=8.0):
        assert token == "demo-token"
        if "/review/demo_UserC/pending?" in url:
            return {
                "user_id": "demo_UserC",
                "items": [review_detail],
                "total": 1,
                "unread": 1,
                "page": 1,
                "page_size": 20,
                "status": "pending",
                "lifecycle_status": "all",
            }
        if url.endswith("/review/demo_UserC/11") and method == "GET":
            return review_detail
        if url.endswith("/review/demo_UserC/11/approve"):
            return {
                "ok": True,
                "notif_id": 11,
                "status": "confirmed",
                "notification": {**review_detail["notification"], "status": "confirmed"},
                "skill_sync": {
                    "applied": True,
                    "source_kind": "skills",
                    "action": "activated",
                },
            }
        if url.endswith("/review/demo_UserC/11/reject"):
            return {
                "ok": True,
                "notif_id": 11,
                "status": "dismissed",
                "notification": {**review_detail["notification"], "status": "dismissed"},
                "skill_sync": {
                    "applied": True,
                    "source_kind": "skills",
                    "action": "rejected",
                },
            }
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("maskclaw_cli.services.review_service.request_json", fake_review_request)

    pending = runner.invoke(cli_app, ["review", "pending", "--json"])
    assert pending.exit_code == 0
    pending_payload = json.loads(pending.stdout)
    assert pending_payload["total"] == 1
    assert pending_payload["items"][0]["notification"]["skill_name"] == "alipay-scan-pay"

    show = runner.invoke(cli_app, ["review", "show", "11", "--json"])
    assert show.exit_code == 0
    show_payload = json.loads(show.stdout)
    assert show_payload["target"]["source_kind"] == "skills"
    assert show_payload["target"]["current_state"] == "pending"

    approve = runner.invoke(cli_app, ["review", "approve", "11", "--json"])
    assert approve.exit_code == 0
    approve_payload = json.loads(approve.stdout)
    assert approve_payload["status"] == "confirmed"
    assert approve_payload["skill_sync"]["action"] == "activated"

    reject = runner.invoke(cli_app, ["review", "reject", "11", "--reason", "场景过宽，先不启用", "--json"])
    assert reject.exit_code == 0
    reject_payload = json.loads(reject.stdout)
    assert reject_payload["status"] == "dismissed"
    assert reject_payload["skill_sync"]["action"] == "rejected"


def test_logs_recent_timeline_and_raw(runner, cli_app, monkeypatch):
    _save_logged_in_context()

    def fake_log_request(method, url, payload=None, token=None, timeout=8.0):
        assert method == "GET"
        assert token == "demo-token"
        if "/evolution/events/demo_UserC?" in url:
            return {
                "user_id": "demo_UserC",
                "groups": [
                    {
                        "date": "2026年4月24日",
                        "items": [
                            {
                                "event_type": "conflict",
                                "type_label": "规则冲突",
                                "title": "支付宝扫码支付 规则冲突",
                                "summary": "你拒绝了这次发送操作",
                                "source": "用户纠错",
                            }
                        ],
                    }
                ],
            }
        if "/evolution/source/logs/demo_UserC?" in url:
            return {
                "user_id": "demo_UserC",
                "log_type": "correction",
                "logs": {
                    "correction_log.jsonl": [
                        {
                            "line_no": 1,
                            "ts": 1777000000,
                            "raw": {
                                "correction_type": "user_denied",
                                "agent_intent": "发送支付截图",
                            },
                        }
                    ]
                },
            }
        raise AssertionError(f"Unexpected request: {method} {url}")

    monkeypatch.setattr("maskclaw_cli.services.log_service.request_json", fake_log_request)

    timeline = runner.invoke(cli_app, ["logs", "recent", "--type", "conflict", "--json"])
    assert timeline.exit_code == 0
    timeline_payload = json.loads(timeline.stdout)
    assert timeline_payload["groups"][0]["items"][0]["event_type"] == "conflict"

    raw = runner.invoke(
        cli_app,
        ["logs", "recent", "--source", "raw", "--log-type", "correction", "--json"],
    )
    assert raw.exit_code == 0
    raw_payload = json.loads(raw.stdout)
    assert "correction_log.jsonl" in raw_payload["logs"]


def test_review_and_logs_fallback_to_local_when_api_unavailable(runner, cli_app, monkeypatch):
    _save_logged_in_context()

    def fake_unavailable(*args, **kwargs):
        raise ApiError(0, "Connection refused")

    monkeypatch.setattr("maskclaw_cli.services.review_service.request_json", fake_unavailable)
    monkeypatch.setattr("maskclaw_cli.services.log_service.request_json", fake_unavailable)

    monkeypatch.setattr(
        "maskclaw_cli.services.local_review_service.LocalReviewService.list_pending",
        lambda self, user_id, status="pending", lifecycle_status=None, page=1, page_size=20: {
            "user_id": user_id,
            "items": [
                {
                    "notification": {
                        "id": 11,
                        "status": "pending",
                        "notif_type": "skill_added",
                        "title": "请确认新增规则：支付宝扫码支付",
                        "skill_name": "alipay-scan-pay",
                        "skill_version": "v1.0.0",
                    },
                    "target": {"source_kind": "skills", "current_state": "pending", "storage_bucket": "review"},
                }
            ],
            "total": 1,
            "transport": "local",
        },
    )
    monkeypatch.setattr(
        "maskclaw_cli.services.local_review_service.LocalReviewService.show",
        lambda self, user_id, notif_id: {
            "notification": {"id": notif_id, "skill_name": "alipay-scan-pay"},
            "target": {"source_kind": "skills", "current_state": "pending", "storage_bucket": "review"},
            "transport": "local",
        },
    )
    monkeypatch.setattr(
        "maskclaw_cli.services.local_review_service.LocalReviewService.approve",
        lambda self, user_id, notif_id: {
            "ok": True,
            "notif_id": notif_id,
            "status": "confirmed",
            "notification": {"id": notif_id, "skill_name": "alipay-scan-pay"},
            "skill_sync": {"action": "already_active", "applied": True},
            "transport": "local",
        },
    )
    monkeypatch.setattr(
        "maskclaw_cli.services.local_review_service.LocalReviewService.reject",
        lambda self, user_id, notif_id, reason=None: {
            "ok": True,
            "notif_id": notif_id,
            "status": "dismissed",
            "notification": {"id": notif_id, "skill_name": "alipay-scan-pay"},
            "skill_sync": {"action": "archived", "applied": True, "rollback": {"restored": False}},
            "transport": "local",
        },
    )
    monkeypatch.setattr(
        "maskclaw_cli.services.local_log_service.LocalLogService.recent",
        lambda self, user_id, source="timeline", event_type=None, log_type="all", page=1, page_size=20: {
            "user_id": user_id,
            "groups": [{"date": "2026年4月24日", "items": [{"event_type": "conflict", "title": "规则冲突"}]}],
            "logs": {"correction_log.jsonl": [{"line_no": 1, "ts": 1777000000, "raw": {"agent_intent": "发送截图"}}]},
            "transport": "local",
        },
    )

    pending = runner.invoke(cli_app, ["review", "pending", "--json"])
    assert pending.exit_code == 0
    pending_payload = json.loads(pending.stdout)
    assert pending_payload["transport"] == "local"
    assert pending_payload["items"][0]["notification"]["id"] == 11

    show = runner.invoke(cli_app, ["review", "show", "11", "--json"])
    assert show.exit_code == 0
    show_payload = json.loads(show.stdout)
    assert show_payload["transport"] == "local"

    approve = runner.invoke(cli_app, ["review", "approve", "11", "--json"])
    assert approve.exit_code != 0
    assert "Review write commands require the local API to be online" in approve.output

    reject = runner.invoke(cli_app, ["review", "reject", "11", "--reason", "先不上线", "--json"])
    assert reject.exit_code != 0
    assert "Review write commands require the local API to be online" in reject.output

    logs = runner.invoke(cli_app, ["logs", "recent", "--json"])
    assert logs.exit_code == 0
    logs_payload = json.loads(logs.stdout)
    assert logs_payload["transport"] == "local"

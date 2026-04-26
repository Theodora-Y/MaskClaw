from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from review_service import ReviewService
from skill_registry.skill_db import SkillDB


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def local_tmp_dir() -> Path:
    base = PROJECT_ROOT / ".pytest_tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"review_case_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _write_skill_dir(base_dir: Path, skill_name: str, version: str, scene: str) -> tuple[Path, dict]:
    skill_dir = base_dir / skill_name / version
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\nversion: {version}\n---\n# {skill_name}\n\nScene: {scene}\n",
        encoding="utf-8",
    )
    rules = {
        "skill_name": skill_name,
        "version": version,
        "scene": scene,
        "rule_text": f"{scene} should be protected",
        "strategy": f"Protect {scene}",
        "confidence": 0.92,
    }
    (skill_dir / "rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    return skill_dir, rules


def _insert_notification(db: SkillDB, user_id: str, skill_name: str, version: str, event_id: str) -> int:
    db.add_notification(
        user_id=user_id,
        notif_type="pending_confirm",
        title=f"请确认：{skill_name}",
        body="Pending review",
        skill_name=skill_name,
        skill_version=version,
        event_id=event_id,
        status="pending",
    )
    items, _ = db.get_notifications(user_id=user_id, status="pending", page=1, page_size=10)
    return int(items[0]["id"])


def test_review_service_show_and_approve_pending_skill(local_tmp_dir: Path):
    user_id = "review_user"
    db = SkillDB(db_path=str(local_tmp_dir / "skill_registry.db"))
    user_root = local_tmp_dir / "user_skills"
    skill_dir, rules = _write_skill_dir(user_root / ".review" / user_id, "wechat-share", "v1.0.0", "share wechat file")
    assert db.add_skill(user_id, "wechat-share", "v1.0.0", str(skill_dir), rules, status="pending") is True
    notif_id = _insert_notification(db, user_id, "wechat-share", "v1.0.0", "evt-approve-pending")

    service = ReviewService(db=db, user_skills_root=user_root)
    detail = service.get_review(user_id, notif_id)
    assert detail["target"]["source_kind"] == "skills"
    assert detail["target"]["current_state"] == "pending"

    approved = service.approve_review(user_id, notif_id)
    assert approved["status"] == "confirmed"
    assert approved["skill_sync"]["action"] == "activated"
    restored = db.get_skill_detail(user_id, "wechat-share", "v1.0.0")
    assert restored is not None
    assert restored["source_table"] == "skills"
    assert restored["path"]
    assert restored["status"] == "active"
    assert Path(restored["path"]).exists()


def test_review_service_reject_marks_candidate_rejected_without_touching_active(local_tmp_dir: Path):
    user_id = "review_user"
    db = SkillDB(db_path=str(local_tmp_dir / "skill_registry.db"))
    user_root = local_tmp_dir / "user_skills"

    v1_dir, v1_rules = _write_skill_dir(user_root / user_id, "alipay-pay", "v1.0.0", "pay with alipay")
    assert db.add_skill(user_id, "alipay-pay", "v1.0.0", str(v1_dir), v1_rules) is True

    v2_dir, v2_rules = _write_skill_dir(user_root / ".review" / user_id, "alipay-pay", "v2.0.0", "pay with alipay safely")
    assert db.add_skill(user_id, "alipay-pay", "v2.0.0", str(v2_dir), v2_rules, status="pending") is True

    notif_id = _insert_notification(db, user_id, "alipay-pay", "v2.0.0", "evt-reject-v2")
    service = ReviewService(db=db, user_skills_root=user_root)

    rejected = service.reject_review(user_id, notif_id, reason="too_broad")
    assert rejected["status"] == "dismissed"
    assert rejected["skill_sync"]["action"] == "rejected"

    v2 = db.get_skill_detail(user_id, "alipay-pay", "v2.0.0")
    assert v2 is not None
    assert v2["status"] == "rejected"
    assert v2["storage_bucket"] == "review"
    v1 = db.get_skill_detail(user_id, "alipay-pay", "v1.0.0")
    assert v1 is not None
    assert v1["status"] == "active"
    assert v1["storage_bucket"] == "active"


def test_review_service_handles_missing_target_gracefully(local_tmp_dir: Path):
    user_id = "review_user"
    db = SkillDB(db_path=str(local_tmp_dir / "skill_registry.db"))
    notif_id = _insert_notification(db, user_id, "ghost-skill", "v9.9.9", "evt-missing")
    service = ReviewService(db=db, user_skills_root=local_tmp_dir / "user_skills")

    approved = service.approve_review(user_id, notif_id)
    assert approved["status"] == "confirmed"
    assert approved["skill_sync"]["applied"] is False
    assert approved["skill_sync"]["action"] == "notification_only"


def test_review_service_reject_archives_sop_version(local_tmp_dir: Path):
    user_id = "review_user"
    db = SkillDB(db_path=str(local_tmp_dir / "skill_registry.db"))
    assert db.publish_sop_version(
        user_id=user_id,
        skill_name="calendar-sync",
        version="v1.0.0",
        path=str(local_tmp_dir / "published" / "calendar-sync" / "v1.0.0"),
        app_context="calendar",
        task_description="sync work calendar",
        confidence=0.88,
        source_sessions=["sess-1"],
        skill_md_content="# calendar-sync",
        scripts_json=None,
        rules_json_content=json.dumps({"scene": "calendar sync"}, ensure_ascii=False),
        status="pending",
    ) is True
    notif_id = _insert_notification(db, user_id, "calendar-sync", "v1.0.0", "evt-sop-reject")

    service = ReviewService(db=db, user_skills_root=local_tmp_dir / "user_skills")
    detail = service.get_review(user_id, notif_id)
    assert detail["target"]["source_kind"] == "sop_version"
    assert detail["target"]["current_state"] == "pending"

    rejected = service.reject_review(user_id, notif_id, reason="manual_reject")
    assert rejected["skill_sync"]["source_kind"] == "sop_version"
    assert rejected["skill_sync"]["action"] == "rejected"
    sop_version = db.get_sop_version(user_id, "calendar-sync", "v1.0.0")
    assert sop_version is not None
    assert sop_version["status"] == "rejected"

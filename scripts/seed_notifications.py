#!/usr/bin/env python3
"""
预制 UserC 的 10 条 notifications。
写入 skill_registry.db 的 notifications 表。

UserC 场景：老职员（2月中旬加入），22条 Skill，约40条日志。
10条通知中：7条已确认，3条待确认。

Usage: python3 scripts/seed_notifications.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from skill_registry.skill_db import _db

# 时间戳参考（2026年）
# 2026-03-10 ~ 2026-03-26
TS = {
    "03-10": 1773254400,  # 3月10日
    "03-12": 1773427200,  # 3月12日
    "03-14": 1773600000,  # 3月14日
    "03-17": 1773849600,  # 3月17日
    "03-19": 1774016000,  # 3月19日
    "03-21": 1774188800,  # 3月21日
    "03-23": 1774361600,  # 3月23日
    "03-24": 1774448000,  # 3月24日
    "03-25": 1774534400,  # 3月25日
    "03-26": 1774620800,  # 3月26日
    "03-27": 1774707200,  # 3月27日（最新）
}

NOTIFICATIONS = [
    # 1. 已确认 - 微信转账规则
    {
        "user_id": "demo_UserC",
        "notif_type": "skill_added",
        "title": "微信转账规则已生成",
        "body": "系统检测到你在微信中发起过转账操作，已为你生成「微信转账隐私保护」规则，转账金额和对方账户信息将自动脱敏。",
        "skill_name": "wechat-transfer-money",
        "skill_version": "v1.0.0",
        "event_id": "demo_UserC_notif_001",
        "status": "confirmed",
        "created_ts": TS["03-10"],
    },
    # 2. 已确认 - 钉钉会议规则
    {
        "user_id": "demo_UserC",
        "notif_type": "skill_added",
        "title": "钉钉视频会议规则已生成",
        "body": "系统检测到你在钉钉中发起过视频会议，已生成「钉钉视频会议隐私保护」规则，入会背景和麦克风状态将按规则自动控制。",
        "skill_name": "dingtalk-video-meeting",
        "skill_version": "v1.0.0",
        "event_id": "demo_UserC_notif_002",
        "status": "confirmed",
        "created_ts": TS["03-10"],
    },
    # 3. 已确认 - 微信分享位置冲突解决
    {
        "user_id": "demo_UserC",
        "notif_type": "conflict_resolved",
        "title": "微信分享位置规则冲突已解决",
        "body": "你之前设定的「不分享家庭住址」规则与实际场景产生冲突（工作群需分享公司位置）。系统已将规则细化为：工作时段分享公司地址允许，家庭时段拒绝。",
        "skill_name": "wechat-share-location",
        "skill_version": "v1.0.0",
        "event_id": "demo_UserC_notif_003",
        "status": "confirmed",
        "created_ts": TS["03-12"],
    },
    # 4. 已确认 - 打印机使用规则
    {
        "user_id": "demo_UserC",
        "notif_type": "skill_added",
        "title": "公司打印机使用规则已生成",
        "body": "系统检测到你在公司打印机上有打印行为，已生成「使用公司打印机隐私保护」规则，打印后将自动提醒你及时取件。",
        "skill_name": "use-company-printer",
        "skill_version": "v1.0.0",
        "event_id": "demo_UserC_notif_004",
        "status": "confirmed",
        "created_ts": TS["03-14"],
    },
    # 5. 待确认 - 企业滴滴规则
    {
        "user_id": "demo_UserC",
        "notif_type": "pending_confirm",
        "title": "请确认：企业滴滴出差规则",
        "body": "系统检测到你在企业滴滴上有出差打车记录，建议生成「企业滴滴出差隐私保护」规则：行程信息仅用于报销，紧急情况优先保障安全。请确认是否生成？",
        "skill_name": "company-didi",
        "skill_version": "v1.0.0",
        "event_id": "demo_UserC_notif_005",
        "status": "pending",
        "created_ts": TS["03-17"],
    },
    # 6. 待确认 - 企业邮箱规则变更
    {
        "user_id": "demo_UserC",
        "notif_type": "pending_confirm",
        "title": "请确认：企业邮箱规则变更",
        "body": "你之前确认的「发送工作邮件」规则需要更新：现检测到你有对外商务邮件往来，建议增加「附件不得包含未脱敏合同金额」约束。请确认变更内容。",
        "skill_name": "send-business-email",
        "skill_version": "v1.0.0",
        "event_id": "demo_UserC_notif_006",
        "status": "pending",
        "created_ts": TS["03-19"],
    },
    # 7. 待确认 - 钉钉打卡规则冲突
    {
        "user_id": "demo_UserC",
        "notif_type": "conflict_resolved",
        "title": "请确认冲突解决：考勤打卡规则",
        "body": "你设定的「不记录家庭位置」规则与考勤系统要求（需要定位打卡）产生冲突。系统建议：考勤打卡时允许定位，其他时段拒绝。请确认此方案。",
        "skill_name": "clock-in-attendance",
        "skill_version": "v1.0.0",
        "event_id": "demo_UserC_notif_007",
        "status": "pending",
        "created_ts": TS["03-21"],
    },
    # 8. 待确认 - 内部文件分享
    {
        "user_id": "demo_UserC",
        "notif_type": "pending_confirm",
        "title": "请确认新增规则：内部文件分享",
        "body": "系统检测到你在企业内网分享过文件，建议生成「内部文件分享隐私保护」规则：含客户信息的文件需脱敏后才可分享。请确认是否生成。",
        "skill_name": "internal-file-share",
        "skill_version": "v1.0.0",
        "event_id": "demo_UserC_notif_008",
        "status": "pending",
        "created_ts": TS["03-23"],
    },
    # 9. 已确认 - 考勤打卡规则
    {
        "user_id": "demo_UserC",
        "notif_type": "skill_added",
        "title": "考勤打卡规则已生成",
        "body": "系统已为你生成「企业考勤打卡隐私保护」规则，打卡位置信息仅HR和系统管理员可见，不得转让或公开。",
        "skill_name": "clock-in-attendance",
        "skill_version": "v1.0.0",
        "event_id": "demo_UserC_notif_009",
        "status": "confirmed",
        "created_ts": TS["03-14"],
    },
    # 10. 待确认 - 工作日历同步
    {
        "user_id": "demo_UserC",
        "notif_type": "pending_confirm",
        "title": "请确认：工作日历同步规则",
        "body": "系统检测到你的工作日历与手机日历同步，建议增加隐私约束：日程内容不得暴露出差行程、家庭情况等敏感信息，共享日历前确认可见范围。请确认。",
        "skill_name": "work-calendar",
        "skill_version": "v1.0.0",
        "event_id": "demo_UserC_notif_010",
        "status": "pending",
        "created_ts": TS["03-24"],
    },
    # 11. 待确认 - 新增：支付宝扫码支付
    {
        "user_id": "demo_UserC",
        "notif_type": "skill_added",
        "title": "请确认新增规则：支付宝扫码支付",
        "body": "系统检测到你在支付宝有扫码支付行为，建议生成「支付宝扫码支付隐私保护」规则：交易对手账户信息脱敏展示，异常大额交易触发确认。请确认是否生成。",
        "skill_name": "alipay-scan-pay",
        "skill_version": "v1.0.0",
        "event_id": "demo_UserC_notif_011",
        "status": "pending",
        "created_ts": TS["03-25"],
    },
    # 12. 待确认 - 矛盾处理：考勤打卡
    {
        "user_id": "demo_UserC",
        "notif_type": "conflict_resolved",
        "title": "请确认冲突解决：考勤打卡定位规则",
        "body": "你设定的「不记录家庭位置」规则与考勤系统打卡要求产生冲突（需定位验证）。系统建议：工作日 09:00-18:00 考勤打卡时允许定位，其他时段定位记录自动清除。请确认此方案。",
        "skill_name": "clock-in-attendance",
        "skill_version": "v1.1.0",
        "event_id": "demo_UserC_notif_012",
        "status": "pending",
        "created_ts": TS["03-26"],
    },
]

def main():
    # 先清理旧记录
    deleted = _db.mark_all_notifications_read("demo_UserC")
    print(f"[CLEAN] 清理 demo_UserC 旧通知 {deleted} 条")

    inserted = _db.seed_notifications(NOTIFICATIONS)
    print(f"[OK] 写入 {inserted} 条通知")

    # 验证
    items, total = _db.get_notifications("demo_UserC", status=None, page=1, page_size=100)
    pending = sum(1 for i in items if i["status"] == "pending")
    confirmed = sum(1 for i in items if i["status"] == "confirmed")
    print(f"[DB] demo_UserC: {total} 条通知（待确认 {pending} / 已确认 {confirmed}）")
    for n in items:
        print(f"  [{n['status']:9}] {n['title']}")

if __name__ == "__main__":
    main()

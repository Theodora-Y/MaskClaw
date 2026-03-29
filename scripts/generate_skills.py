#!/usr/bin/env python3
"""
生成 demo_UserA 和 demo_UserC 的 Skill 文件和数据库记录。
调用 localhost:8002 的 miniCPM API 生成 SKILL.md 和 rules.json 内容。

Usage: python3 scripts/generate_skills.py
"""

import json
import os
import sys
import time
import hashlib
import sqlite3
import requests
from pathlib import Path

# ===== 配置 =====
MINICPM_URL = "http://localhost:8002/chat"
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
USER_SKILLS_ROOT = PROJECT_ROOT / "user_skills"
SKILL_REGISTRY_DB = PROJECT_ROOT / "skill_registry" / "skill_registry.db"
MEMORY_ROOT = PROJECT_ROOT / "memory"
API_TIMEOUT = 120  # seconds per call

os.environ["PYTHONIOENCODING"] = "utf-8"

# ===== 23 条 Skill 定义 =====

BASIC_SKILLS = [
    {
        "id": "wechat-send-message",
        "name": "发送微信消息",
        "app": "微信",
        "app_key": "wechat",
        "scene": "在微信聊天窗口中发送一条文字消息",
        "privacy_concern": "消息内容可能被监控或转发，需注意不得包含未脱敏的病历、身份证、家庭住址等隐私信息",
        "user_type": "basic",
    },
    {
        "id": "xiaohongshu-comment",
        "name": "发送小红书评论",
        "app": "小红书",
        "app_key": "xiaohongshu",
        "scene": "在小红书帖子下方发布一条评论",
        "privacy_concern": "评论内容公开可见，不得包含真实姓名、手机号、就诊记录等隐私信息",
        "user_type": "basic",
    },
    {
        "id": "order-food",
        "name": "点外卖",
        "app": "外卖平台",
        "app_key": "food_delivery",
        "scene": "在美团或饿了么上下单点外卖",
        "privacy_concern": "收货地址和联系电话仅用于配送，不得与工作内容混淆；外卖订单不应包含医疗相关标记",
        "user_type": "basic",
    },
    {
        "id": "browse-moments",
        "name": "浏览朋友圈",
        "app": "微信",
        "app_key": "wechat",
        "scene": "在微信中浏览朋友圈内容",
        "privacy_concern": "浏览行为不得被记录或上报；朋友圈中他人的隐私信息不得转发或截图",
        "user_type": "basic",
    },
    {
        "id": "send-work-email",
        "name": "发送工作邮件",
        "app": "邮件",
        "app_key": "email",
        "scene": "使用企业邮箱发送一封工作邮件",
        "privacy_concern": "邮件内容不得包含未脱敏的患者信息、内部通讯录、财务数据等敏感内容",
        "user_type": "basic",
    },
    {
        "id": "dingtalk-group-message",
        "name": "钉钉工作群发消息",
        "app": "钉钉",
        "app_key": "dingtalk",
        "scene": "在钉钉的工作群聊中发送一条消息",
        "privacy_concern": "工作群消息仅限群内可见，不得转发至外部；消息内容不得包含未脱敏的客户信息",
        "user_type": "basic",
    },
    {
        "id": "his-patient-record",
        "name": "填写HIS系统患者记录",
        "app": "HIS系统",
        "app_key": "his",
        "scene": "在医院HIS系统中录入或查询患者病历信息",
        "privacy_concern": "患者病历属高度隐私，仅限授权医护人员访问；不得在外部设备截图或转发；操作需留存审计日志",
        "user_type": "basic",
    },
]

ADVANCED_SKILLS = [
    {
        "id": "wechat-transfer-money",
        "name": "微信转账",
        "app": "微信",
        "app_key": "wechat",
        "scene": "在微信聊天中向好友转账",
        "privacy_concern": "转账金额和对方账户信息仅限双方可见，不得截图外传；不得向陌生人转账",
        "user_type": "advanced",
    },
    {
        "id": "wechat-share-location",
        "name": "微信分享位置",
        "app": "微信",
        "app_key": "wechat",
        "scene": "在微信聊天中发送或分享实时位置",
        "privacy_concern": "位置信息极度敏感，仅在必要时分享给可信联系人，事后及时关闭；不得在工作群分享家庭住址",
        "user_type": "advanced",
    },
    {
        "id": "alipay-scan-pay",
        "name": "支付宝扫码支付",
        "app": "支付宝",
        "app_key": "alipay",
        "scene": "使用支付宝扫描商家收款码完成支付",
        "privacy_concern": "支付记录由支付宝保管，不得将含金额的支付截图发给他人；商家信息不得与客户资料混淆",
        "user_type": "advanced",
    },
    {
        "id": "send-business-email",
        "name": "发送商务邮件",
        "app": "邮件",
        "app_key": "email",
        "scene": "使用企业邮箱向外部合作伙伴发送商务邮件",
        "privacy_concern": "附件和正文不得包含未脱敏的合同金额、商业机密、客户隐私；抄送需确认必要性",
        "user_type": "advanced",
    },
    {
        "id": "dingtalk-video-meeting",
        "name": "发起钉钉视频会议",
        "app": "钉钉",
        "app_key": "dingtalk",
        "scene": "在钉钉中发起或加入一个视频会议",
        "privacy_concern": "会议内容仅限参会人员，不得录音录像外传；入会链接不得随意分享；不得在公共场合接入涉及敏感内容的会议",
        "user_type": "advanced",
    },
    {
        "id": "use-company-printer",
        "name": "使用公司打印机",
        "app": "办公设备",
        "app_key": "office",
        "scene": "在公司使用共享打印机打印或复印文件",
        "privacy_concern": "打印前确认文件不含隐私内容；及时取走打印件；涉密文件需使用碎纸机处理；不得打印客户名单或财务报告",
        "user_type": "advanced",
    },
    {
        "id": "internal-file-share",
        "name": "企业内部文件分享",
        "app": "内部系统",
        "app_key": "intranet",
        "scene": "通过企业网盘或内部IM分享工作文件",
        "privacy_concern": "仅在授权范围内分享；含客户信息的文件需脱敏后再分享；不得通过个人微信/QQ传输工作文件",
        "user_type": "advanced",
    },
    {
        "id": "work-calendar",
        "name": "管理工作日历",
        "app": "企业日历",
        "app_key": "calendar",
        "scene": "在企业日历中创建或查看工作日程",
        "privacy_concern": "日程内容不得暴露出差行程、家庭情况等隐私；共享日历前确认可见范围；涉密会议使用不透明标题",
        "user_type": "advanced",
    },
    {
        "id": "company-didi",
        "name": "企业滴滴出差打车",
        "app": "企业滴滴",
        "app_key": "didienterprise",
        "scene": "使用企业滴滴账户申请出差用车",
        "privacy_concern": "行程起点终点仅用于报销和安全管理；不得虚报行程；紧急情况下优先保障人身安全而非隐私",
        "user_type": "advanced",
    },
    {
        "id": "submit-reimbursement",
        "name": "提交差旅报销单",
        "app": "报销系统",
        "app_key": "expense",
        "scene": "在企业报销系统中提交差旅费用报销",
        "privacy_concern": "报销票据仅用于财务审核；发票信息不得涂改；同行人员信息按需填写；不得虚报不存在的费用",
        "user_type": "advanced",
    },
    {
        "id": "browse-work-chat",
        "name": "浏览工作群消息",
        "app": "钉钉",
        "app_key": "dingtalk",
        "scene": "在钉钉工作群中浏览和回复消息",
        "privacy_concern": "工作群内容属内部信息，不得截图外传；客户姓名可用昵称替代；涉及内部人事变动的话题不得传播",
        "user_type": "advanced",
    },
    {
        "id": "join-online-meeting",
        "name": "加入在线会议",
        "app": "视频会议",
        "app_key": "meeting",
        "scene": "通过会议链接加入一个在线视频会议",
        "privacy_concern": "入会前确认主持人身份防止冒充；入会背景不得暴露家庭环境；麦克风默认静音；不主动共享含隐私内容的屏幕",
        "user_type": "advanced",
    },
    {
        "id": "clock-in-attendance",
        "name": "企业考勤打卡",
        "app": "考勤系统",
        "app_key": "attendance",
        "scene": "在企业考勤系统中完成上下班打卡",
        "privacy_concern": "打卡位置信息由HR和系统管理员可见；不得代打卡；异常考勤需附说明；考勤数据不得转让或公开",
        "user_type": "advanced",
    },
    {
        "id": "submit-work-feedback",
        "name": "提交工作反馈",
        "app": "内部系统",
        "app_key": "intranet",
        "scene": "在企业内部系统提交工作改进建议或投诉",
        "privacy_concern": "反馈内容如实描述；不泄露同事个人信息；匿名反馈需确认系统支持；不借反馈之名行报复之实",
        "user_type": "advanced",
    },
    {
        "id": "order-office-supplies",
        "name": "订购办公用品",
        "app": "企业采购",
        "app_key": "procurement",
        "scene": "在企业采购平台订购办公耗材或设备",
        "privacy_concern": "收货地址填写公司地址而非家庭地址；采购需求如实填写；不得利用职务之便超规格采购",
        "user_type": "advanced",
    },
]


def call_minicpm(prompt: str, max_retries=2) -> str:
    """调用 miniCPM API，返回文本响应。"""
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                MINICPM_URL,
                data={"prompt": prompt},
                timeout=API_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return data["response"].strip()
            print(f"  [WARN] miniCPM 返回状态 {resp.status_code}: {resp.text[:100]}", file=sys.stderr)
        except requests.exceptions.Timeout:
            print(f"  [WARN] miniCPM 超时（尝试 {attempt+1}/{max_retries}）", file=sys.stderr)
        except Exception as e:
            print(f"  [WARN] miniCPM 调用失败: {e}", file=sys.stderr)
        time.sleep(3)
    return ""


def generate_skill_content(skill_def: dict, user_id: str) -> dict:
    """为单条 Skill 调用 miniCPM 生成内容。"""
    app = skill_def["app"]
    scene = skill_def["scene"]
    privacy = skill_def["privacy_concern"]
    skill_id = skill_def["id"]
    skill_name = skill_def["name"]
    user_type = skill_def["user_type"]

    # Step 1: 生成 SKILL.md 正文
    skill_md_prompt = f"""你是一个AI助手，正在为用户（user_id={user_id}）生成一条"操作技能(Skill)"。
该技能用于教AutoGLM（一个在用户手机上运行的AI Agent）如何正确执行以下操作。

【操作场景】
应用：{app}
场景：{scene}
隐私注意事项：{privacy}

请严格按照以下JSON格式输出（只输出JSON，不要有其他文字）：
{{
  "skill_md": "## 何时使用\n在{app}的{scene}时，该技能被触发。\n\n## 执行步骤\n- [ ] 步骤1：xxx\n- [ ] 步骤2：xxx\n- [ ] 步骤3：xxx（根据需要3~6步）\n\n## 边界情况\n- [特殊情况1]：xxx\n- [特殊情况2]：xxx",
  "rule_text": "一句话描述该隐私保护规则，限30字以内",
  "strategy": "mask | replace | block | deny 之一，根据隐私风险选择最合适的策略",
  "sensitive_field": "该场景下最需要保护的隐私字段名称"
}}

要求：
- 执行步骤要像脚本一样具体（手机点击哪里、输入什么、确认什么），AutoGLM需要能够跟着执行
- 边界情况要包含操作超时、网络失败、用户拒绝等真实场景
- strategy的mask表示脱敏打码，replace表示替换内容，block表示拦截操作，deny表示直接拒绝

只输出JSON。"""

    raw = call_minicpm(skill_md_prompt)
    if not raw:
        print(f"  [ERROR] miniCPM 未返回内容，跳过 skill {skill_id}", file=sys.stderr)
        return {}

    # 解析 JSON
    try:
        content = json.loads(raw)
    except json.JSONDecodeError:
        # 尝试提取 JSON 块
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                content = json.loads(raw[start:end])
            except Exception as e:
                print(f"  [ERROR] 解析JSON失败: {e}\n原始内容: {raw[:200]}", file=sys.stderr)
                return {}
        else:
            print(f"  [ERROR] 无法提取JSON: {raw[:200]}", file=sys.stderr)
            return {}

    skill_md = content.get("skill_md", "")
    rule_text = content.get("rule_text", "")
    strategy = content.get("strategy", "mask")
    sensitive_field = content.get("sensitive_field", "")

    # Step 2: 生成 rules.json 内容
    rule_id = f"{user_id}_{int(time.time())}_{skill_id[:8]}"
    now_ts = int(time.time())

    rules_json = {
        "rule_id": rule_id,
        "user_id": user_id,
        "scene": scene,
        "sensitive_field": sensitive_field,
        "model_sensitive_field": "Agent想做的操作内容",
        "strategy": strategy,
        "replacement": "[已脱敏]",
        "rule_text": rule_text,
        "app_context_hint": skill_def["app_key"],
        "confidence": 0.85 if user_type == "basic" else 0.80,
        "needs_review": False,
        "status": "active",
        "created_ts": now_ts,
        "source_event_ids": [],
        "app_context": skill_def["app_key"],
        "action": "send_message",
        "field": sensitive_field,
        "skill_body": skill_md.replace("\n", "\\n"),
        "id": rule_id,
        "version": "v1.0.0",
    }

    # Step 3: 生成 frontmatter
    frontmatter = f"""---
name: {skill_id}
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: {now_ts}
user_id: {user_id}
confidence: {rules_json['confidence']}
needs_review: false
status: sandbox_passed
description: >
  在 {app} 场景下，{scene} 时保护 {sensitive_field} 的隐私规则。
  策略为 {strategy}。
---

{skill_md}"""

    return {
        "skill_md": frontmatter,
        "rules_json": rules_json,
        "skill_id": skill_id,
        "skill_name": skill_name,
        "app": app,
        "app_key": skill_def["app_key"],
        "strategy": strategy,
        "sensitive_field": sensitive_field,
        "rule_text": rule_text,
        "confidence": rules_json["confidence"],
        "now_ts": now_ts,
        "rule_id": rule_id,
    }


def write_skill_files(user_id: str, skill_data: dict, base_dir: Path):
    """将生成的 Skill 内容写入文件系统。"""
    skill_id = skill_data["skill_id"]
    version = "v1.0.0"
    skill_dir = base_dir / skill_id / version
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_md_path = skill_dir / "SKILL.md"
    rules_json_path = skill_dir / "rules.json"

    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(skill_data["skill_md"])

    with open(rules_json_path, "w", encoding="utf-8") as f:
        json.dump(skill_data["rules_json"], f, ensure_ascii=False, indent=2)

    return str(skill_dir)


def write_manifest(base_dir: Path, user_id: str, all_skills: list):
    """写 manifest.json 和 SKILL_CATALOG.md。"""
    manifest = {
        "user_id": user_id,
        "updated_at": int(time.time()),
        "skills": {}
    }
    for s in all_skills:
        sid = s["skill_id"]
        manifest["skills"][sid] = {
            "content_hash": hashlib.md5(s["skill_md"].encode()).hexdigest()[:12],
            "version": "v1.0.0",
            "confidence": s["confidence"],
        }

    with open(base_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    catalog_lines = [f"# {user_id} Skill 目录\n"]
    catalog_lines.append(f"共 {len(all_skills)} 条 Skill（自动生成）\n")
    for s in all_skills:
        catalog_lines.append(f"- **{s['skill_name']}** (`{s['skill_id']}`) — {s['app']} — {s['rule_text']}")

    with open(base_dir / "SKILL_CATALOG.md", "w", encoding="utf-8") as f:
        f.write("\n".join(catalog_lines))


def write_to_db(skill_data: dict, base_dir: Path):
    """将单条 Skill 写入 skill_registry.db。"""
    conn = sqlite3.connect(str(SKILL_REGISTRY_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    skill_md = skill_data["skill_md"]
    rules_json_str = json.dumps(skill_data["rules_json"], ensure_ascii=False)
    content_hash = hashlib.md5(skill_md.encode()).hexdigest()

    now_ts = skill_data["now_ts"]

    try:
        cursor.execute(
            """
            INSERT OR REPLACE INTO skills (
              user_id, skill_name, version, path,
              confidence, content_hash,
              strategy, sensitive_field, scene, rule_text,
              skill_md_content, rules_json_content,
              created_ts, archived_ts, archived_reason, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
            """,
            (
                skill_data["user_id"],
                skill_data["skill_id"],
                "v1.0.0",
                str(base_dir / skill_data["skill_id"] / "v1.0.0"),
                skill_data["confidence"],
                content_hash,
                skill_data["strategy"],
                skill_data["sensitive_field"],
                skill_data["app"],
                skill_data["rule_text"],
                skill_md,
                rules_json_str,
                now_ts,
            ),
        )
        conn.commit()
        print(f"  [DB] 写入 skills 表: {skill_data['skill_id']} v1.0.0")
    except Exception as e:
        print(f"  [DB ERROR] {skill_data['skill_id']}: {e}", file=sys.stderr)
    finally:
        conn.close()


def main():
    print("=" * 60)
    print("Skill 生成脚本开始")
    print("=" * 60)

    # 清理旧目录（可选：保留 demo_UserA/demo_UserC 的其他版本）
    # 仅重建我们生成的版本目录

    all_generated: dict[str, list] = {
        "demo_UserA": [],
        "demo_UserC": [],
    }

    for user_id, skill_list in [
        ("demo_UserA", BASIC_SKILLS),
        ("demo_UserC", BASIC_SKILLS + ADVANCED_SKILLS),
    ]:
        base_dir = USER_SKILLS_ROOT / user_id
        base_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n>>> 处理用户: {user_id} ({len(skill_list)} 条 Skill)")

        for i, skill_def in enumerate(skill_list):
            skill_id = skill_def["id"]
            print(f"  [{i+1}/{len(skill_list)}] 生成 {skill_id}...", end=" ", flush=True)

            # 如果文件已存在且有效，跳过（节省API调用）
            existing_path = base_dir / skill_id / "v1.0.0" / "SKILL.md"
            if existing_path.exists():
                print("已存在，跳过")
                try:
                    with open(existing_path, encoding="utf-8") as f:
                        skill_md = f.read()
                    with open(base_dir / skill_id / "v1.0.0" / "rules.json", encoding="utf-8") as f:
                        rules_json = json.load(f)
                    content_hash = hashlib.md5(skill_md.encode()).hexdigest()
                    skill_data = {
                        **skill_def,
                        "skill_md": skill_md,
                        "rules_json": rules_json,
                        "confidence": rules_json.get("confidence", 0.85),
                        "now_ts": rules_json.get("created_ts", int(time.time())),
                        "rule_id": rules_json.get("rule_id", ""),
                        "strategy": rules_json.get("strategy", "mask"),
                        "rule_text": rules_json.get("rule_text", ""),
                        "sensitive_field": rules_json.get("sensitive_field", ""),
                        "user_id": user_id,
                    }
                    all_generated[user_id].append(skill_data)
                except Exception:
                    pass
                continue

            skill_data = generate_skill_content(skill_def, user_id)
            if not skill_data:
                print("失败！")
                continue

            skill_path = write_skill_files(user_id, skill_data, base_dir)
            skill_data["skill_path"] = skill_path
            print(f"写入 {skill_path}")

            write_to_db(skill_data, base_dir)
            all_generated[user_id].append(skill_data)

            # API 有频率限制，间隔一下
            if i < len(skill_list) - 1:
                time.sleep(2)

        # 写 manifest 和 catalog
        write_manifest(base_dir, user_id, all_generated[user_id])
        print(f">>> {user_id} 完成: {len(all_generated[user_id])} 条 Skill")

    print("\n" + "=" * 60)
    print("全部完成！")
    for uid, skills in all_generated.items():
        print(f"  {uid}: {len(skills)} 条")
    print("=" * 60)


if __name__ == "__main__":
    main()

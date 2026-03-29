#!/usr/bin/env python3
"""SOP 模拟测试脚本 - 模拟一条 skill 通过全部流程并发布"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from skill_registry.skill_db import SkillDB
from skills.evolution_mechanic import SOPEvolution


def mock_minicpm_response(prompt: str) -> str:
    """模拟 MiniCPM 返回高分结果"""
    # 根据 prompt 类型返回不同的模拟内容
    if "请生成一个符合以下要求的 SOP" in prompt:
        return """【安卓手机操作 SOP】

步骤 1: 打开微信应用
具体动作：点击手机桌面上的微信图标，等待微信加载完成
异常处理：若微信未响应，点击"强制停止"后重新打开

步骤 2: 进入通讯录
具体动作：点击屏幕底部的"通讯录"标签页
异常处理：若网络不稳定，等待加载或切换网络

步骤 3: 搜索联系人
具体动作：点击右上角搜索图标，输入联系人姓名
异常处理：若搜索无结果，检查输入是否正确

步骤 4: 发送消息
具体动作：在聊天输入框中点击，然后输入消息，点击发送按钮
异常处理：若发送失败，检查网络连接后重试
"""

    if "小幅改进" in prompt or "变异" in prompt:
        return """【安卓手机操作 SOP】

步骤 1: 打开微信应用
具体动作：点击手机桌面上的微信图标，等待微信加载完成
异常处理：若微信未响应，点击"强制停止"后重新打开

步骤 2: 进入通讯录
具体动作：点击屏幕底部的"通讯录"标签页
异常处理：若网络不稳定，等待加载或切换网络

步骤 3: 搜索联系人
具体动作：点击右上角搜索图标，输入联系人姓名
异常处理：若搜索无结果，检查输入是否正确

步骤 4: 发送消息
具体动作：在聊天输入框中点击，输入消息，点击发送按钮
隐私保护：在发送前检查消息内容是否包含敏感信息
异常处理：若发送失败，检查网络连接后重试
"""

    # 评估返回高分
    return '{"score": 95, "passed": true, "reasoning": "SOP 逻辑完整，手机操作规范，隐私保护到位", "issues": [], "suggestions": []}'


def create_mock_skill_and_publish():
    """创建模拟 skill 并发布"""
    print("=" * 70)
    print("SOP 模拟测试 - 模拟一条 skill 通过全部流程并发布")
    print("=" * 70)
    print()

    # 配置
    user_id = "mock_user"
    draft_name = f"mock/test-{int(time.time())}"
    app_context = "wechat"
    task_goal = "发送微信消息"

    print(f"[配置]")
    print(f"  用户: {user_id}")
    print(f"  草稿名: {draft_name}")
    print(f"  应用场景: {app_context}")
    print(f"  任务目标: {task_goal}")
    print()

    # 初始化进化引擎（使用模拟的 MiniCPM）
    engine = SOPEvolution(
        logs_root="memory/logs",
        memory_root="memory",
    )

    # 临时替换 _call_minicpm 方法
    original_call = engine._call_minicpm
    engine._call_minicpm = mock_minicpm_response

    # ===== Step 1: 模拟已处理的 session_trace =====
    print("=" * 70)
    print("[Step 1] 模拟会话轨迹")
    print("=" * 70)

    # 直接在数据库中创建模拟轨迹
    session_ids = []
    for i in range(3):
        session_id = f"mock_session_{int(time.time())}_{i}"
        session_ids.append(session_id)

        engine.skill_db.save_session_trace_full(
            user_id=user_id,
            session_id=session_id,
            app_context=app_context,
            task_goal=task_goal,
            behaviors=[
                {
                    "action": "click",
                    "target": "wechat_icon",
                    "result": "打开微信",
                    "is_correction": False,
                },
                {
                    "action": "click",
                    "target": "contact_tab",
                    "result": "进入通讯录",
                    "is_correction": True,  # 用户纠正
                    "correction_reason": "应该先进入通讯录",
                },
            ],
            corrections=[
                {
                    "action": "返回并点击通讯录",
                    "reason": "操作顺序错误",
                    "correct_step": "应先进入通讯录再搜索",
                }
            ],
            chain_metadata={
                "rule_type": "N",
                "start_ts": int(time.time()) - 3600,
                "end_ts": int(time.time()),
                "action_count": 5,
                "has_correction": 1,
                "final_resolution": "用户手动纠正后完成",
            },
        )

    print(f"✅ 创建模拟轨迹: {len(session_ids)} 条")
    for sid in session_ids:
        print(f"   - {sid[:40]}...")
    print()

    # ===== Step 2: 初始化草稿 =====
    print("=" * 70)
    print("[Step 2] 初始化进化草稿")
    print("=" * 70)

    init_result = engine.init_evolution(
        user_id=user_id,
        draft_name=draft_name,
        app_context=app_context,
        task_goal=task_goal,
        session_ids=session_ids,
    )
    print(f"✅ 初始化完成")
    print(f"   初始 SOP 长度: {len(init_result.get('initial_content', ''))} 字符")
    print()

    # ===== Step 3: 快速模拟进化（3 轮高分）=====
    print("=" * 70)
    print("[Step 3] 模拟爬山法进化")
    print("=" * 70)

    # 直接修改数据库，模拟 3 轮高分结果
    best_content = """【安卓手机操作 SOP】

步骤 1: 打开微信应用
具体动作：点击手机桌面上的微信图标，等待微信加载完成
异常处理：若微信未响应，点击"强制停止"后重新打开

步骤 2: 进入通讯录
具体动作：点击屏幕底部的"通讯录"标签页
异常处理：若网络不稳定，等待加载或切换网络

步骤 3: 搜索联系人
具体动作：点击右上角搜索图标，输入联系人姓名
异常处理：若搜索无结果，检查输入是否正确

步骤 4: 发送消息
具体动作：在聊天输入框中点击，输入消息，点击发送按钮
隐私保护：在发送前检查消息内容是否包含敏感信息
异常处理：若发送失败，检查网络连接后重试

步骤 5: 确认发送成功
具体动作：查看消息气泡，确认发送状态为"已发送"
异常处理：若显示感叹号，点击重试发送
"""

    # 更新草稿为高分状态
    with engine.skill_db._connect() as conn:
        conn.execute("""
            UPDATE sop_draft
            SET current_content = ?,
                score = 95.0,
                best_score = 95.0,
                iteration = 3,
                stage = 'ready'
            WHERE user_id = ? AND draft_name = ?
        """, (best_content, user_id, draft_name))
        conn.commit()

    print("✅ 模拟完成: 3 轮迭代，得分 95.0")
    print("   - 第 1 轮: 85.0 ↑")
    print("   - 第 2 轮: 90.0 ↑")
    print("   - 第 3 轮: 95.0 ↑ (达标)")
    print()

    # ===== Step 4: 最终沙盒验证 =====
    print("=" * 70)
    print("[Step 4] 最终沙盒验证")
    print("=" * 70)

    sandbox_result = engine.final_sandbox_validation(user_id, draft_name)
    print(f"✅ 沙盒验证完成")
    print(f"   通过: {sandbox_result.get('sandbox_passed', False)}")
    print(f"   测试场景: {sandbox_result.get('scenarios_tested', 0)}")
    print(f"   通过场景: {sandbox_result.get('scenarios_passed', 0)}")
    print()

    # ===== Step 5: 发布 SOP =====
    print("=" * 70)
    print("[Step 5] 发布 SOP")
    print("=" * 70)

    publish_result = engine.publish_sop(user_id, draft_name)

    if publish_result.get("success"):
        print("✅ 发布成功！")
        print(f"   技能名称: {publish_result.get('skill_name')}")
        print(f"   版本号: {publish_result.get('version')}")
        print(f"   文件路径: {publish_result.get('path')}")
        print(f"   轨迹已标记: {publish_result.get('traces_updated')} 条")
    else:
        print(f"❌ 发布失败: {publish_result.get('error')}")
        return

    # 恢复原始方法
    engine._call_minicpm = original_call

    # ===== 验证发布结果 =====
    print()
    print("=" * 70)
    print("[验证] 检查发布结果")
    print("=" * 70)

    # 检查文件是否存在
    skill_path = Path(publish_result.get('path', ''))
    if skill_path.exists():
        print(f"✅ SKILL.md 文件已创建")
        print(f"   路径: {skill_path}")
        print(f"   大小: {skill_path.stat().st_size} 字节")
        print()
        print("=" * 70)
        print("[SKILL.md 内容预览]")
        print("=" * 70)
        content = skill_path.read_text(encoding='utf-8')
        print(content[:1500])
        if len(content) > 1500:
            print(f"\n... (共 {len(content)} 字符)")
    else:
        print(f"❌ SKILL.md 文件未找到")

    # 检查数据库
    print()
    print("=" * 70)
    print("[数据库验证]")
    print("=" * 70)

    # 检查 sop_version 表
    with engine.skill_db._connect() as conn:
        versions = conn.execute("""
            SELECT skill_name, version, confidence, app_context
            FROM sop_version
            WHERE user_id = ?
            ORDER BY created_ts DESC
            LIMIT 5
        """, (user_id,)).fetchall()

    print(f"✅ 已发布版本: {len(versions)} 条")
    for v in versions:
        print(f"   - {v[0]} v{v[1]} (置信度: {v[2]:.0%}, 场景: {v[3]})")

    # 检查轨迹是否被标记
    with engine.skill_db._connect() as conn:
        traces = conn.execute("""
            SELECT session_id, processed
            FROM session_trace
            WHERE user_id = ? AND session_id LIKE 'mock_session_%'
        """, (user_id,)).fetchall()

    print()
    print(f"✅ 轨迹处理状态:")
    processed_count = sum(1 for t in traces if t[1])
    print(f"   已处理: {processed_count}/{len(traces)} 条")

    print()
    print("=" * 70)
    print("🎉 模拟测试完成！Skill 已成功发布。")
    print("=" * 70)

    return publish_result


if __name__ == "__main__":
    try:
        result = create_mock_skill_and_publish()
        sys.exit(0 if result.get("success") else 1)
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

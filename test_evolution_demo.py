#!/usr/bin/env python3
"""SOP 自进化完整测试脚本 - 模拟真实进化流程

此脚本完整复现 evolution_mechanic.py 中的 run_pipeline 流程：
1. rebuild: 重建会话轨迹
2. init: 初始化草稿
3. evolve: 爬山法进化（调用 MiniCPM）
4. sandbox: 最终沙盒验证
5. publish: 发布 SOP

迭代次数减少以加快测试，流程与正式环境完全一致。
"""

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from skills.evolution_mechanic import SOPEvolution


def create_progress_handler():
    """创建进度处理器，实现流式输出"""

    def progress_handler(event_type: str, data: dict):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{timestamp}]"

        if event_type == "iteration_start":
            print(f"\n{prefix} ====== 第 {data['iteration']} 轮迭代开始 ======")
            sys.stdout.flush()

        elif event_type == "mutation":
            print(f"{prefix} [1/6] 变异完成 (MiniCPM)")
            preview = data.get("content_preview", "")[:80].replace("\n", " ")
            if preview:
                print(f"     预览: {preview}...")

        elif event_type == "test":
            passed = data.get("passed", 0)
            total = data.get("total", 0)
            method = data.get("method", "unknown")
            pass_rate = (passed / total * 100) if total > 0 else 0
            method_name = "语义核验" if method == "semantic" else f"状态机({method})"
            print(f"{prefix} [2/6] 批量测试完成 ({method_name})")
            print(f"     通过: {passed}/{total} ({pass_rate:.1f}%)")

        elif event_type == "evaluation":
            score = data.get("score", 0)
            decision = data.get("decision", "N/A")
            is_improvement = data.get("is_improvement", False)
            icon = "↑" if is_improvement else "↓"
            print(f"{prefix} [3/6] Checklist 评估完成")
            print(f"     得分: {score:.1f} {icon}")
            print(f"     决策: {decision}")

        elif event_type == "analysis":
            problems = data.get("problems", [])
            direction = data.get("direction", "")
            print(f"{prefix} [4/6] MiniCPM 分析完成")
            if problems:
                print(f"     发现 {len(problems)} 个问题:")
                for i, p in enumerate(problems[:2], 1):
                    p_str = str(p)[:60]
                    print(f"       {i}. {p_str}...")
            if direction:
                print(f"     改进方向: {direction[:60]}...")

        elif event_type == "commit":
            score = data.get("score", 0)
            print(f"{prefix} [5/6] 变异已提交 (is_best 标记)")

        elif event_type == "iteration_end":
            consecutive = data.get("consecutive_high", 0)
            stagnation = data.get("stagnation_counter", 0)
            should_terminate = data.get("should_terminate", False)
            score = data.get("score", 0)

            print(f"\n{prefix} [6/6] 轮次完成")
            print(f"     当前得分: {score:.1f}")
            print(f"     连续高分: {consecutive} 轮")
            print(f"     停滞计数: {stagnation}")
            if should_terminate:
                print(f"{prefix} ✅ 达标！连续 {consecutive} 轮 >= 90%")
            sys.stdout.flush()

        elif event_type == "stagnation":
            reset_hint = data.get("reset_hint", "")
            print(f"{prefix} ⚠️ 停滞检测，重置进化方向")
            if reset_hint:
                print(f"     新方向: {reset_hint[:60]}...")

        elif event_type == "terminated":
            reason = data.get("reason", "")
            print(f"\n{prefix} 🛑 进化终止: {reason}")

    return progress_handler


def print_section(title: str):
    """打印分节标题"""
    print()
    print("=" * 70)
    print(f"{title}")
    print("=" * 70)


def main():
    print("=" * 70)
    print("        SOP 自进化完整测试 (run_pipeline 流程)")
    print("=" * 70)

    # ===== 配置 =====
    config = {
        "user_id": "d1_UserA",           # 测试用户
        "max_iterations": 3,              # 迭代次数（正式环境 50）
        "score_threshold": 0.8,           # 分数阈值 80%
        "consecutive_threshold": 2,       # 连续高分阈值（正式环境 3）
        "stagnation_threshold": 3,        # 停滞阈值（正式环境 5）
    }

    print("\n[配置]")
    for k, v in config.items():
        print(f"  {k}: {v}")
    print()

    # 初始化进化引擎
    try:
        engine = SOPEvolution(
            logs_root="memory/logs",
            memory_root="memory",
        )
        print("✅ 进化引擎初始化成功\n")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # 生成草稿名
    draft_name = f"test/sandbox-{int(time.time())}"

    # ===== Step 1: 重建会话轨迹 =====
    print_section("[Step 1] 重建会话轨迹 (rebuild)")
    try:
        rebuild_result = engine.rebuild_session_traces(config["user_id"])
        print(f"✅ 重建完成")
        print(f"   来源: {rebuild_result.get('source', 'unknown')}")
        print(f"   保存: {rebuild_result.get('saved', 0)} 条")
        print(f"   跳过: {rebuild_result.get('skipped', 0)} 条")
        print(f"   总计: {rebuild_result.get('total_chains', 0)} 条")
    except Exception as e:
        print(f"⚠️ 重建过程出错: {e}")
        import traceback
        traceback.print_exc()
    print()

    # ===== Step 2: 获取待处理轨迹 =====
    print_section("[Step 2] 获取待处理轨迹")
    try:
        traces = engine.skill_db.get_unprocessed_traces(config["user_id"])
        print(f"✅ 待处理轨迹: {len(traces)} 条")

        if not traces:
            print("⚠️ 没有待处理的轨迹，测试终止")
            return 1

        # 从轨迹提取上下文
        first_trace = traces[0]
        app_context = first_trace.get("app_context", "unknown")
        task_goal = first_trace.get("task_goal", "")
        session_ids = [t.get("session_id") for t in traces[:10] if t.get("session_id")]

        print(f"   app_context: {app_context}")
        print(f"   task_goal: {task_goal}")
        print(f"   session_ids: {len(session_ids)} 条")

    except Exception as e:
        print(f"❌ 获取轨迹失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    print()

    # ===== Step 3: 初始化草稿 =====
    print_section("[Step 3] 初始化草稿 (init_evolution)")
    try:
        init_result = engine.init_evolution(
            user_id=config["user_id"],
            draft_name=draft_name,
            app_context=app_context,
            task_goal=task_goal,
            session_ids=session_ids,
        )
        print(f"✅ 初始化完成")
        print(f"   草稿名: {init_result.get('draft_name')}")
        print(f"   场景: {init_result.get('app_context')}")
        print(f"   目标: {init_result.get('task_goal')}")
        initial_content = init_result.get("initial_content", "")
        print(f"   初始 SOP 长度: {len(initial_content)} 字符")
        if initial_content:
            preview = initial_content[:150].replace("\n", " ")
            print(f"   预览: {preview}...")
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    print()

    # ===== Step 4: 爬山法进化 =====
    print_section("[Step 4] 爬山法进化 (run_evolution)")
    print(f"配置: 最大 {config['max_iterations']} 轮, 阈值 {config['score_threshold']*100:.0f}%")
    print()

    start_time = time.time()

    try:
        progress_handler = create_progress_handler()

        evolve_result = engine.run_evolution(
            user_id=config["user_id"],
            draft_name=draft_name,
            max_iterations=config["max_iterations"],
            score_threshold=config["score_threshold"],
            consecutive_threshold=config["consecutive_threshold"],
            stagnation_threshold=config["stagnation_threshold"],
            progress_callback=progress_handler,
        )

        evolve_time = time.time() - start_time

        print()
        print_section("[Step 4 结果]")
        print(f"  成功: {evolve_result.get('success', False)}")
        print(f"  总迭代: {evolve_result.get('total_iterations', 0)} 轮")
        print(f"  最终得分: {evolve_result.get('final_score', 0):.1f}")
        print(f"  达到阈值: {evolve_result.get('reached_threshold', False)}")
        print(f"  终止原因: {evolve_result.get('terminated_reason', 'N/A')}")
        print(f"  耗时: {evolve_time:.2f} 秒")

        # 历史记录
        history = evolve_result.get("history", [])
        if history:
            print()
            print("  迭代历史:")
            for h in history:
                score = h.get("steps", {}).get("evaluation", {}).get("score", 0)
                decision = h.get("steps", {}).get("evaluation", {}).get("decision", "N/A")
                is_imp = h.get("steps", {}).get("evaluation", {}).get("is_improvement", False)
                icon = "↑" if is_imp else "↓"
                print(f"    第 {h.get('iteration', 0)} 轮: {score:.1f} {icon} ({decision})")

    except Exception as e:
        print(f"❌ 进化流程出错: {e}")
        import traceback
        traceback.print_exc()
        evolve_result = {"reached_threshold": False, "final_score": 0}
    print()

    # ===== Step 5: 最终沙盒验证 =====
    print_section("[Step 5] 最终沙盒验证 (final_sandbox_validation)")

    reached_threshold = evolve_result.get("reached_threshold", False)
    final_score = evolve_result.get("final_score", 0)

    if reached_threshold:
        try:
            print(f"✅ 进化达标 ({final_score:.1f} >= {config['score_threshold']*100:.0f}%)，执行沙盒验证\n")

            sandbox_result = engine.final_sandbox_validation(
                config["user_id"],
                draft_name
            )

            sandbox_passed = sandbox_result.get("sandbox_passed", False)
            print(f"  沙盒通过: {sandbox_passed}")
            print(f"  测试场景: {sandbox_result.get('scenarios_tested', 0)}")
            print(f"  通过场景: {sandbox_result.get('scenarios_passed', 0)}")

            # 打印场景详情
            report = sandbox_result.get("report", {})
            execution_log = report.get("execution_log", []) if isinstance(report, dict) else []

            if execution_log:
                print()
                print("  场景详情:")
                for item in execution_log[:5]:
                    scenario_type = item.get("scenario_type", "normal")
                    name = item.get("scenario_name", "unknown")

                    if scenario_type == "normal":
                        status = "✅" if item.get("executed") else "❌"
                    elif scenario_type in ("malicious", "history_block"):
                        status = "🛡️" if item.get("blocked_correctly") else "⚠️"
                    elif scenario_type == "history_mask":
                        status = "🎭" if item.get("masked_correctly") else "❌"
                    else:
                        status = "?" if item.get("executed") else "❌"

                    print(f"    {status} [{scenario_type}] {name}")

            # 更新结果
            evolve_result["sandbox_passed"] = sandbox_passed
            evolve_result["sandbox"] = sandbox_result

        except Exception as e:
            print(f"⚠️ 沙盒验证出错: {e}")
            evolve_result["sandbox_passed"] = False
    else:
        print(f"⚠️ 进化未达标 (得分 {final_score:.1f} < {config['score_threshold']*100:.0f}%)，跳过沙盒验证")
        evolve_result["sandbox_passed"] = False
    print()

    # ===== Step 6: 发布 SOP =====
    print_section("[Step 6] 发布 SOP (publish_sop)")

    sandbox_passed = evolve_result.get("sandbox_passed", False)

    if sandbox_passed:
        try:
            print("✅ 沙盒通过，准备发布...\n")

            publish_result = engine.publish_sop(
                config["user_id"],
                draft_name
            )

            if publish_result.get("success"):
                print("🎉 发布成功！")
                print(f"  技能名称: {publish_result.get('skill_name')}")
                print(f"  版本号: {publish_result.get('version')}")
                print(f"  文件路径: {publish_result.get('path')}")
                print(f"  轨迹已标记: {publish_result.get('traces_updated')} 条")

                # 显示生成的 SKILL.md 预览
                skill_path = Path(publish_result.get('path', ''))
                if skill_path.exists():
                    print()
                    print("=" * 70)
                    print("[生成的 SKILL.md 预览]")
                    print("=" * 70)
                    content = skill_path.read_text(encoding='utf-8')
                    print(content[:800])
                    if len(content) > 800:
                        print(f"\n... (共 {len(content)} 字符)")
            else:
                print(f"❌ 发布失败: {publish_result.get('error')}")

        except Exception as e:
            print(f"❌ 发布出错: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("⚠️ 沙盒验证未通过，不发布")
        print("   草稿已保存，下次满足条件后可继续")
    print()

    # ===== 最终汇总 =====
    print_section("[汇总] 测试完成")
    print(f"  用户: {config['user_id']}")
    print(f"  草稿名: {draft_name}")
    print(f"  进化轮次: {evolve_result.get('total_iterations', 0)}")
    print(f"  最终得分: {evolve_result.get('final_score', 0):.1f}")
    print(f"  达到阈值: {evolve_result.get('reached_threshold', False)}")
    print(f"  沙盒通过: {evolve_result.get('sandbox_passed', False)}")
    print(f"  发布状态: {'成功' if sandbox_passed else '跳过/失败'}")

    # 数据库验证
    print()
    print("=" * 70)
    print("[数据库验证]")
    print("=" * 70)

    try:
        with engine.skill_db._connect() as conn:
            # 检查草稿状态
            draft_row = conn.execute("""
                SELECT draft_name, stage, best_score, iteration
                FROM sop_draft
                WHERE user_id = ? AND draft_name = ?
            """, (config["user_id"], draft_name)).fetchone()

            if draft_row:
                print(f"  草稿状态: {draft_row[1]} (得分: {draft_row[2]:.1f}, 迭代: {draft_row[3]})")

            # 检查已发布版本
            versions = conn.execute("""
                SELECT skill_name, version, confidence
                FROM sop_version
                WHERE user_id = ?
                ORDER BY created_ts DESC
                LIMIT 3
            """, (config["user_id"],)).fetchall()

            if versions:
                print(f"  已发布版本: {len(versions)} 条")
                for v in versions:
                    print(f"    - {v[0]} v{v[1]} (置信度: {v[2]:.0%})")
            else:
                print("  已发布版本: 无")

            # 检查轨迹处理状态
            trace_stats = conn.execute("""
                SELECT processed, COUNT(*) as cnt
                FROM session_trace
                WHERE user_id = ?
                GROUP BY processed
            """, (config["user_id"],)).fetchall()

            if trace_stats:
                for row in trace_stats:
                    status = "已处理" if row[0] else "未处理"
                    print(f"  轨迹状态: {status} {row[1]} 条")

    except Exception as e:
        print(f"  数据库验证出错: {e}")

    print()
    print("=" * 70)
    print("✅ 测试脚本执行完成")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())

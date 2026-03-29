"""SOP Evolution Mechanic - 基于爬山法的 SOP 自进化引擎。

核心逻辑（爬山法）：
┌─────────────────────────────────────────────────────────────┐
│  第 1 步：agent 对 skill 做一个小改动                 │
│         （比如：加一条"必须核对输入数据"的规则）              │
├─────────────────────────────────────────────────────────────┤
│  第 2 步：用改动后的 skill 跑 10 个测试用例                   │
├─────────────────────────────────────────────────────────────┤
│  第 3 步：用 checklist 给每个输出打分                         │
│         （4 个检查项全过 = 100 分，3 个过 = 75 分...）        │
├─────────────────────────────────────────────────────────────┤
│  第 4 步：算平均分                                           │
│         - 比上一轮高 → 保留改动                               │
│         - 比上一轮低 → 撤销改动                               │
├─────────────────────────────────────────────────────────────┤
│  第 5 步：重复，直到连续 3 轮分数超过 90% 或你喊停            │
└─────────────────────────────────────────────────────────────┘

架构：
- 语义核验器 (SemanticEvaluator): LLM-as-a-Judge，快速验证逻辑
- 检查器 (ChecklistEvaluator): 4项检查评分
- 最终沙盒 (FinalSandbox): 严格验证后发布

数据库表：
- session_trace: 会话轨迹
- sop_draft: SOP 草稿（多轮迭代）
- sop_version: 已发布版本
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from memory.chroma_manager import ChromaManager
from sandbox.checklist_evaluator import ChecklistEvaluator
from sandbox.sandbox_validator import FinalSandbox
from sandbox.semantic_evaluator import SemanticEvaluator, SemanticTestResult
from skill_registry.skill_db import SkillDB


# MiniCPM 调用相关常量
MINICPM_DEFAULT_URL = "http://127.0.0.1:8000/chat"
MINICPM_TIMEOUT = 180  # 3分钟超时

# 默认配置
DEFAULT_EVOLUTION_CONFIG = {
    "max_iterations": 50,
    "score_threshold": 0.9,
    "consecutive_threshold": 3,
    "stagnation_threshold": 5,
}


class SOPEvolution:
    """SOP 自进化引擎 - 基于爬山法的智能 SOP 生成。

    核心特性：
    - while 循环 + 停滞检测：自动跳出局部最优
    - 断点续传：系统重启后自动恢复进化
    - 事务发布：processed 标记确保日志闭环
    - 沙盒验证：发布前必须通过严格验证
    """

    # 进化阶段
    STAGE_INIT = "init"
    STAGE_DIAGNOSE = "diagnose"
    STAGE_MUTATE = "mutate"
    STAGE_TEST = "test"
    STAGE_EVALUATE = "evaluate"
    STAGE_EVOLVING = "evolving"
    STAGE_SANDBOX = "sandbox"
    STAGE_READY = "ready"
    STAGE_PUBLISHED = "published"
    STAGE_FAILED = "failed"

    def __init__(
        self,
        *,
        logs_root: str = "memory/logs",
        memory_root: str = "memory",
        user_skills_root: str = "user_skills",
        prompts_root: str = "prompts",
        minicpm_url: str = MINICPM_DEFAULT_URL,
        chroma_manager: Optional[ChromaManager] = None,
        config_path: Optional[str] = None,
    ) -> None:
        self.logs_root = Path(logs_root)
        self.memory_root = Path(memory_root)
        self.user_skills_root = Path(user_skills_root)
        self.prompts_root = Path(prompts_root)
        self.minicpm_url = minicpm_url
        self.chroma = chroma_manager or ChromaManager(
            storage_dir=str(self.memory_root / "chroma_storage")
        )
        self.skill_db = SkillDB(
            db_path=str(Path("skill_registry") / "skill_registry.db")
        )

        # 加载配置
        self._load_config(config_path)

        # 初始化组件
        self.checklist_evaluator = ChecklistEvaluator()

        self._ensure_dirs()

    def _load_config(self, config_path: Optional[str] = None) -> None:
        """加载进化配置

        Args:
            config_path: 配置文件路径，若为 None 则尝试加载默认路径
        """
        self.config = DEFAULT_EVOLUTION_CONFIG.copy()

        if config_path is None:
            config_path = Path("config") / "evolution_config.json"
        else:
            config_path = Path(config_path)

        if config_path.exists():
            try:
                import json as _json

                with open(config_path, "r", encoding="utf-8") as f:
                    loaded = _json.load(f)
                    if "evolution" in loaded:
                        self.config.update(loaded["evolution"])
                    else:
                        self.config.update(loaded)
            except Exception:
                pass  # 使用默认配置

    def _ensure_dirs(self) -> None:
        """确保必要目录存在"""
        self.memory_root.mkdir(parents=True, exist_ok=True)
        self.user_skills_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
        """读取 JSONL 文件并返回列表。"""
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass
        return rows

    # ============== MiniCPM 调用 ==============

    def _call_minicpm(self, prompt: str, timeout: int = MINICPM_TIMEOUT) -> str:
        """调用 MiniCPM API"""
        data = urlparse.urlencode({"prompt": prompt}).encode("utf-8")
        req = urlrequest.Request(self.minicpm_url, data=data, method="POST")
        try:
            with urlrequest.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                if str(payload.get("status")) != "success":
                    raise RuntimeError(str(payload.get("message", "MiniCPM error")))
                return str(payload.get("response", ""))
        except urlerror.URLError as exc:
            raise RuntimeError(f"MiniCPM request failed: {exc}") from exc

    @staticmethod
    def _extract_json_block(text: str) -> Dict[str, Any]:
        """从文本中提取 JSON 块"""
        s = text.find("{")
        e = text.rfind("}")
        if s < 0 or e < 0 or e <= s:
            raise ValueError("No JSON object in model output")
        return json.loads(text[s : e + 1])

    # ============== 轨迹重建 ==============

    def rebuild_session_traces(self, user_id: str) -> Dict[str, Any]:
        """重建用户的会话轨迹。

        v2.0 逻辑：
        1. 优先读取新格式 session_trace.jsonl
        2. 如果没有新格式，则从旧格式聚类生成
        3. 保存到 skill_db
        """
        user_log_dir = self.logs_root / user_id
        if not user_log_dir.exists():
            return {"saved": 0, "skipped": 0, "errors": 0, "source": "none"}

        # v2.0: 优先读取新格式
        trace_path = user_log_dir / "session_trace.jsonl"
        if trace_path.exists():
            return self._rebuild_from_session_traces(user_id, trace_path)

        # 兼容旧格式：聚类生成
        return self._rebuild_from_legacy_logs(user_id, user_log_dir)

    def _rebuild_from_session_traces(
        self,
        user_id: str,
        trace_path: Path,
    ) -> Dict[str, Any]:
        """从新格式 session_trace.jsonl 读取轨迹并保存到 skill_db。"""
        traces = self._read_jsonl(trace_path)
        saved = 0
        skipped = 0

        for chain in traces:
            chain_id = chain.get("chain_id", "")
            if not chain_id:
                skipped += 1
                continue

            # 跳过已处理的
            if chain.get("processed"):
                skipped += 1
                continue

            app_context = chain.get("app_context", "unknown")
            scenario_tag = chain.get("scenario_tag", "")
            rule_type = chain.get("rule_type", "N")
            actions = chain.get("actions", [])

            # 提取纠错动作
            corrections = [a for a in actions if a.get("is_correction")]
            if not corrections:
                skipped += 1
                continue

            try:
                if self.skill_db.save_session_trace_full(
                    user_id=user_id,
                    session_id=chain_id,
                    app_context=app_context,
                    task_goal=scenario_tag,
                    behaviors=actions,
                    corrections=corrections,
                    chain_metadata={
                        "rule_type": rule_type,
                        "start_ts": chain.get("start_ts"),
                        "end_ts": chain.get("end_ts"),
                        "action_count": chain.get("action_count"),
                        "has_correction": chain.get("has_correction"),
                        "final_resolution": chain.get("final_resolution"),
                    },
                ):
                    saved += 1
                    # 标记为已处理
                    self._mark_chain_processed(user_id, chain_id, trace_path)
                else:
                    skipped += 1
            except Exception:
                skipped += 1

        return {
            "saved": saved,
            "skipped": skipped,
            "errors": 0,
            "source": "session_trace.jsonl",
            "total_chains": len(traces),
        }

    def _rebuild_from_legacy_logs(
        self,
        user_id: str,
        user_log_dir: Path,
    ) -> Dict[str, Any]:
        """从旧格式聚类生成轨迹（兼容）。"""
        correction_path = user_log_dir / "correction_log.jsonl"
        behavior_path = user_log_dir / "behavior_log.jsonl"

        corrections = self._read_jsonl(correction_path)
        behaviors = self._read_jsonl(behavior_path)

        saved = 0
        skipped = 0

        # 按 _scenario_tag 分组（v2.0 核心变化）
        scenario_map: Dict[str, Dict[str, List]] = {}
        for item in corrections + behaviors:
            # v2.0: 使用 _scenario_tag 作为唯一识别标志
            scenario_tag = str(item.get("_scenario_tag") or item.get("_parent_entry_id") or "unknown")
            if scenario_tag not in scenario_map:
                scenario_map[scenario_tag] = {"behaviors": [], "corrections": []}

            if item.get("correction_type"):
                scenario_map[scenario_tag]["corrections"].append(item)
            else:
                scenario_map[scenario_tag]["behaviors"].append(item)

        # 生成新的 session_trace.jsonl
        trace_path = user_log_dir / "session_trace.jsonl"
        trace_lines = []

        for scenario_tag, data in scenario_map.items():
            if not data["corrections"]:
                skipped += 1
                continue

            app_context = self._extract_app_context(data["corrections"])
            rule_type = self._extract_rule_type(data["corrections"])

            # 构建行为链
            all_actions = data["behaviors"] + data["corrections"]
            all_actions.sort(key=lambda x: x.get("ts", 0))

            chain_id = f"{user_id}_{scenario_tag}_{min(a.get('ts', 0) for a in all_actions)}"
            start_ts = min(a.get("ts", 0) for a in all_actions)
            end_ts = max(a.get("ts", 0) for a in all_actions)

            chain = {
                "chain_id": chain_id,
                "user_id": user_id,
                "app_context": app_context,
                "scenario_tag": scenario_tag,
                "rule_type": rule_type,
                "start_ts": start_ts,
                "end_ts": end_ts,
                "action_count": len(all_actions),
                "has_correction": len(data["corrections"]) > 0,
                "correction_count": len(data["corrections"]),
                "final_resolution": all_actions[-1].get("resolution", "unknown") if all_actions else "unknown",
                "processed": False,
                "actions": [
                    {
                        "action_index": i,
                        "ts": a.get("ts", 0),
                        "action": a.get("action", "unknown"),
                        "field": a.get("field"),
                        "resolution": a.get("resolution", "unknown"),
                        "value_preview": a.get("value_preview"),
                        "is_correction": bool(a.get("correction_type")),
                        "correction_type": a.get("correction_type"),
                        "correction_value": a.get("correction_value"),
                        "pii_type": a.get("_pii_type"),
                        "relationship_tag": a.get("_relationship_tag"),
                        "agent_intent": a.get("_agent_intent"),
                        "quality_score": a.get("_quality_score"),
                        "quality_flag": a.get("_quality_flag"),
                    }
                    for i, a in enumerate(all_actions)
                ],
            }

            # 只保留非 None 的字段
            for act in chain["actions"]:
                act = {k: v for k, v in act.items() if v is not None}

            trace_lines.append(json.dumps(chain, ensure_ascii=False))

            # 保存到 skill_db
            try:
                if self.skill_db.save_session_trace_full(
                    user_id=user_id,
                    session_id=chain_id,
                    app_context=app_context,
                    task_goal=scenario_tag,
                    behaviors=chain["actions"],
                    corrections=[a for a in chain["actions"] if a.get("is_correction")],
                    chain_metadata={
                        "rule_type": rule_type,
                        "start_ts": start_ts,
                        "end_ts": end_ts,
                        "action_count": len(all_actions),
                        "has_correction": len(data["corrections"]) > 0,
                        "final_resolution": chain["final_resolution"],
                    },
                ):
                    saved += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1

        # 写入新的 session_trace.jsonl
        if trace_lines:
            with trace_path.open("w", encoding="utf-8") as f:
                f.write("\n".join(trace_lines) + "\n")

        return {
            "saved": saved,
            "skipped": skipped,
            "errors": 0,
            "source": "legacy聚类",
            "migrated_chains": len(trace_lines),
        }

    def _mark_chain_processed(
        self,
        user_id: str,
        chain_id: str,
        trace_path: Path,
    ) -> None:
        """标记行为链为已处理。"""
        # 更新内存缓存（通过调用 behavior_monitor）
        try:
            from skills.behavior_monitor import TraceChainLogger
            logger = TraceChainLogger(user_id, base_dir=str(self.logs_root))
            logger.mark_processed(chain_id)
        except Exception:
            pass

    @staticmethod
    def _extract_app_context(items: List[Dict]) -> str:
        for item in items:
            app = str(item.get("app_context", "")).strip()
            if app:
                return app
        return "unknown"

    @staticmethod
    def _extract_task_goal(items: List[Dict]) -> str:
        for item in items:
            action = str(item.get("action", "")).strip()
            if action:
                return action
        return ""

    @staticmethod
    def _extract_rule_type(items: List[Dict]) -> str:
        for item in items:
            rt = str(item.get("_rule_type", "N")).strip()
            if rt:
                return rt
        return "N"

    # ============== 爬山法核心流程 ==============

    def init_evolution(
        self,
        user_id: str,
        draft_name: str,
        app_context: str,
        task_goal: str,
        session_ids: List[str],
        initial_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """初始化进化流程"""
        # 生成初始 SOP 内容
        if not initial_content:
            initial_content = self._generate_initial_sop(app_context, task_goal)

        # 初始化草稿
        self.skill_db.init_sop_draft(
            user_id=user_id,
            draft_name=draft_name,
            app_context=app_context,
            task_goal=task_goal,
            session_ids=session_ids,
            initial_content=initial_content,
        )

        return {
            "success": True,
            "draft_name": draft_name,
            "app_context": app_context,
            "task_goal": task_goal,
            "initial_content": initial_content,
        }

    def _generate_initial_sop(self, app_context: str, task_goal: str) -> str:
        """生成初始 SOP 草稿"""
        prompt = f"""你是一个手机操作 SOP 编写专家。请为安卓手机上的应用生成标准作业程序（SOP）。

【重要】所有操作都是针对 Android 手机 UI，不是电脑操作。

应用场景：{app_context}
任务目标：{task_goal}

请生成一个符合以下要求的 SOP：
1. **手机操作术语**：使用"点击"、"滑动"、"长按"、"返回"、"切换"等手机操作词汇
2. **清晰的步骤序列**：每个步骤对应一个手机界面动作
3. **每步骤具体动作**：如"点击屏幕底部的发送按钮"、"滑动到下一页"
4. **异常处理提示**：手机特有的异常情况处理

【示例格式】
步骤 1: 打开应用
具体动作：点击手机桌面上的应用图标，进入应用首页
异常处理：若应用未响应，点击"强制停止"后重新打开

请输出完整的手机操作 SOP："""

        try:
            return self._call_minicpm(prompt)
        except Exception:
            return f"""【安卓手机操作 SOP】

步骤 1: 打开 {app_context} 应用
具体动作：点击手机桌面上的应用图标，等待应用加载完成
异常处理：若应用无响应，从最近任务列表滑动关闭后重新打开

步骤 2: 定位到 {task_goal} 相关界面
具体动作：通过点击屏幕上的菜单按钮或滑动屏幕，找到并点击目标功能入口
异常处理：若找不到入口，检查是否在正确的功能模块中

步骤 3: 执行目标操作
具体动作：按照界面提示，点击或滑动完成具体操作
异常处理：若操作失败，记录错误信息后重试

步骤 4: 确认操作结果
具体动作：检查界面反馈，确认操作是否成功
异常处理：若失败，返回上一步重新操作
"""

    def run_mutation(
        self,
        user_id: str,
        draft_name: str,
        mutation_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """爬山法第 1 步：对 SOP 做小幅改动

        mutation_hint 可以指定改动方向，如：
        - "加强隐私保护"
        - "增加异常处理"
        - "优化步骤顺序"
        """
        # 获取当前最佳 SOP
        draft = self.skill_db.get_sop_draft_for_evolution(user_id, draft_name)
        if not draft:
            return {"success": False, "error": "Draft not found"}

        current_content = str(draft.get("current_content", ""))
        if not current_content:
            current_content = str(draft.get("candidate_content", ""))

        app_context = str(draft.get("app_context", "unknown"))
        task_goal = str(draft.get("task_goal", ""))

        # 获取上次的沙盒错误（用于避免重复错误）
        last_sandbox_error = str(draft.get("last_sandbox_error", "") or "")

        # 构建变异 prompt
        prompt = f"""你是一个手机操作 SOP 优化专家。当前有一个 SOP，你需要对它做小幅改进。

【重要】所有操作都是针对 Android 手机 UI，不是电脑操作。

当前 SOP：
{current_content}

应用场景：{app_context}
任务目标：{task_goal}

变异要求：
{mutation_hint or "对 SOP 进行小幅优化，提高其质量和鲁棒性"}
"""
        # 添加上次沙盒错误信息
        if last_sandbox_error:
            prompt += f"""
【重要】上次沙盒验证失败，错误原因如下：
{last_sandbox_error}

请在变异时务必避免上述错误。
"""

        prompt += """
【手机操作规范】
- 使用手机操作术语："点击"、"滑动"、"长按"、"返回"、"切换标签页"等
- 每步骤描述具体的手机界面动作
- 异常处理包含手机特有场景（应用无响应、网络不稳定等）

要求：
1. 只做小幅改动，不要全量重写
2. 保持原有逻辑结构
3. 可以添加、删除或修改个别步骤
4. 确保新 SOP 逻辑连贯
5. 所有步骤必须是手机操作

请输出改进后的完整手机操作 SOP："""

        try:
            mutate_raw = self._call_minicpm(prompt)
            return {
                "success": True,
                "candidate_content": mutate_raw,
                "mutation_hint": mutation_hint,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_batch_test(
        self,
        user_id: str,
        draft_name: str,
        candidate_content: str,
        num_scenarios: int = 10,
    ) -> Dict[str, Any]:
        """爬山法第 2 步：运行批量测试

        优先使用语义核验（LLM-as-a-Judge），状态机作为降级方案。
        """
        draft = self.skill_db.get_sop_draft_for_evolution(user_id, draft_name)
        if not draft:
            return {"success": False, "error": "Draft not found"}

        app_context = str(draft.get("app_context", "wechat"))

        # 获取测试场景
        scenarios = self.skill_db.get_test_scenarios_from_traces(
            user_id=user_id,
            app_context=app_context if app_context != "unknown" else None,
            limit=num_scenarios,
        )

        # 如果没有足够场景，生成默认场景
        if len(scenarios) < num_scenarios:
            default_scenarios = self._generate_default_scenarios(app_context, num_scenarios)
            scenarios.extend(default_scenarios)

        # 语义核验（LLM-as-a-Judge）
        return self._run_semantic_test(
            candidate_content=candidate_content,
            scenarios=scenarios,
            app_context=app_context,
        )

    def _run_semantic_test(
        self,
        candidate_content: str,
        scenarios: List[Dict[str, Any]],
        app_context: str,
    ) -> Dict[str, Any]:
        """基于 LLM 语义的批量测试"""
        # 创建语义评估器
        def minicpm_caller(prompt: str) -> str:
            return self._call_minicpm(prompt)

        evaluator = SemanticEvaluator(minicpm_caller=minicpm_caller)

        results = []
        total_score = 0.0

        for scenario in scenarios:
            scenario_name = scenario.get("session_id", scenario.get("name", "unknown"))

            # 评估
            result = evaluator.evaluate(
                sop_content=candidate_content,
                session_trace=scenario,
                app_context=app_context,
                scenario_name=scenario_name,
            )

            results.append(result)
            total_score += result.score

        # 统计
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        avg_score = total_score / total if total > 0 else 0

        return {
            "success": True,
            "total_scenarios": total,
            "passed_scenarios": passed,
            "pass_rate": passed / total if total > 0 else 0,
            "avg_score": avg_score,
            "test_results": [r.to_dict() for r in results],
            "method": "semantic",  # 标记使用的方法
        }

    def _generate_default_scenarios(
        self,
        app_context: str,
        count: int,
    ) -> List[Dict[str, Any]]:
        """生成默认测试场景"""
        if app_context == "wechat":
            templates = [
                {"name": "发普通红包-100元", "amount": "100"},
                {"name": "发小额红包-1元", "amount": "1"},
                {"name": "发大额红包-1000元", "amount": "1000"},
                {"name": "发口令红包", "amount": "50"},
                {"name": "转账-100元", "amount": "100"},
                {"name": "转账-500元", "amount": "500"},
                {"name": "转账-紧急", "amount": "1000"},
            ]
        elif app_context == "alipay":
            templates = [
                {"name": "扫码支付-100元", "amount": "100"},
                {"name": "转账-50元", "amount": "50"},
                {"name": "充值-100元", "amount": "100"},
            ]
        else:
            templates = [
                {"name": f"默认场景-{i}", "amount": str(i * 10)}
                for i in range(1, count + 1)
            ]

        return templates[:count]

    def run_evaluation(
        self,
        user_id: str,
        draft_name: str,
        candidate_content: str,
        test_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """爬山法第 3-4 步：评分和决策

        使用 Checklist 评分，决定是否保留变异
        """
        draft = self.skill_db.get_sop_draft_for_evolution(user_id, draft_name)
        if not draft:
            return {"success": False, "error": "Draft not found"}

        app_context = str(draft.get("app_context", "wechat"))

        # Checklist 评估
        execution_result = {
            "state_transitions": [],
            "steps_executed": 0,
        }
        if test_results:
            # 汇总测试结果
            execution_result["state_transitions"] = test_results[0].get("state_transitions", [])
            execution_result["steps_executed"] = sum(
                r.get("steps_executed", 0) for r in test_results
            )

        checklist_result = self.checklist_evaluator.evaluate(
            candidate_content,
            execution_result,
            app_context,
        )

        # 计算总分（结合测试通过率和 Checklist 评分）
        if not test_results:
            return {
                "success": False,
                "error": "No test results provided",
                "score": 0,
                "test_pass_rate": 0,
                "checklist_score": 0,
            }

        passed_count = sum(1 for r in test_results if r.get("passed", False))
        total_count = len(test_results)
        test_pass_rate = passed_count / total_count if total_count > 0 else 0

        checklist_score = checklist_result.score

        # 计算语义测试的平均分
        test_avg_score = sum(r.get("score", 0) for r in test_results) / total_count if total_count > 0 else 0

        # 最终分数 = (测试通过率 × 100 × 0.3 + 平均语义分 × 0.3 + Checklist × 0.4)
        # 三者权重相等，各占约 1/3
        final_score = (
            test_pass_rate * 100 * 0.3 +  # 测试通过率占 30%
            test_avg_score * 0.3 +          # 平均语义分占 30%
            checklist_score * 0.4            # Checklist 质量分占 40%
        )

        # 获取当前最佳分数
        current_best = float(draft.get("best_score", 0.0))

        # 爬山决策
        is_improvement = final_score > current_best

        return {
            "success": True,
            "score": final_score,
            "test_pass_rate": test_pass_rate,
            "checklist_score": checklist_score,
            "current_best": current_best,
            "is_improvement": is_improvement,
            "decision": "accept" if is_improvement else "reject",
            "checklist_details": checklist_result.to_dict(),
        }

    def commit_mutation(
        self,
        user_id: str,
        draft_name: str,
        candidate_content: str,
        score: float,
        checklist_scores: Dict[str, Any],
        test_results: List[Dict[str, Any]],
        mutate_raw: Optional[str] = None,
    ) -> Dict[str, Any]:
        """提交变异结果（保存到数据库）"""
        draft = self.skill_db.get_sop_draft_for_evolution(user_id, draft_name)
        if not draft:
            return {"success": False, "error": "Draft not found"}

        iteration = int(draft.get("iteration", 1))

        self.skill_db.update_draft_mutation(
            user_id=user_id,
            draft_name=draft_name,
            iteration=iteration,
            candidate_content=candidate_content,
            score=score,
            checklist_scores=checklist_scores,
            test_results=test_results,
            mutate_raw=mutate_raw,
        )

        return {
            "success": True,
            "score": score,
            "iteration": iteration,
        }

    def check_termination(
        self,
        user_id: str,
        draft_name: str,
        threshold: float = 0.9,
        consecutive_count: int = 3,
    ) -> Dict[str, Any]:
        """检查是否满足终止条件

        条件：连续 N 轮分数超过阈值
        """
        result = self.skill_db.get_consecutive_high_scores(
            user_id=user_id,
            draft_name=draft_name,
            threshold=threshold,
            consecutive_count=consecutive_count,
        )

        return {
            "should_terminate": result["consecutive"],
            "consecutive_count": result["count"],
            "threshold": threshold,
            "required": consecutive_count,
        }

    # ============== 完整进化流程 ==============

    def run_evolution(
        self,
        user_id: str,
        draft_name: str,
        max_iterations: Optional[int] = None,
        score_threshold: Optional[float] = None,
        consecutive_threshold: Optional[int] = None,
        stagnation_threshold: Optional[int] = None,
        mutation_hint: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """完整爬山法进化流程（持久化版）

        核心特性：
        1. while 循环：直到满足终止条件或达到最大迭代次数
        2. 停滞检测：连续 N 轮无提升时重置进化方向
        3. is_best 标记：标识当前最优版本
        4. 断点续传：系统重启后可恢复

        终止条件（满足任一即可）：
        - 连续 consecutive_threshold 轮分数 >= score_threshold
        - 达到 max_iterations 次迭代

        Args:
            progress_callback: 进度回调函数，签名为 callback(event_type, data)
                event_type: "iteration_start" | "mutation" | "test" | "evaluation" |
                           "analysis" | "commit" | "iteration_end" | "stagnation" | "terminated"

        Returns:
            {
                "success": True,
                "draft_name": str,
                "total_iterations": int,
                "history": [...],
                "final_score": float,
                "final_content": str,
                "reached_threshold": bool,
                "terminated_reason": "consecutive_high" | "max_iterations" | "stagnation",
            }
        """
        # 使用配置或默认值
        max_iterations = max_iterations or self.config["max_iterations"]
        score_threshold = score_threshold or self.config["score_threshold"]
        consecutive_threshold = consecutive_threshold or self.config["consecutive_threshold"]
        stagnation_threshold = stagnation_threshold or self.config["stagnation_threshold"]

        history = []
        consecutive_high = 0
        stagnation_counter = 0
        current_mutation_hint = mutation_hint
        last_score = 0.0

        # 获取当前草稿信息
        draft = self.skill_db.get_sop_draft_for_evolution(user_id, draft_name)
        if not draft:
            return {
                "success": False,
                "error": f"Draft not found: {draft_name}",
            }

        # 从断点恢复：如果当前有更优版本，使用其迭代轮次
        checkpoint = self.skill_db.get_checkpoint(user_id, draft_name)
        if checkpoint and checkpoint.get("is_best"):
            current_score = float(checkpoint.get("best_score", 0))
            last_score = current_score
            stagnation_counter = 0
            current_mutation_hint = mutation_hint
            # 断点恢复：从下一轮开始
            iteration = int(checkpoint.get("iteration", 1))
        else:
            iteration = 0  # 新草稿从 0 开始，while 循环会 +1 变成第 1 轮

        # 更新阶段为 evolving
        self.skill_db.update_draft_stage(
            user_id, draft_name, max(iteration, 1), stage=self.STAGE_EVOLVING
        )

        while iteration < max_iterations:
            iteration += 1
            iteration_result = {
                "iteration": iteration,
                "steps": {},
            }

            # 触发迭代开始回调
            if progress_callback:
                progress_callback("iteration_start", {"iteration": iteration})

            # ===== 第 1 步：变异 =====
            mutation_result = self.run_mutation(
                user_id, draft_name,
                mutation_hint=current_mutation_hint,
            )
            if not mutation_result.get("success"):
                iteration_result["error"] = mutation_result.get("error")
                history.append(iteration_result)
                break

            candidate_content = mutation_result["candidate_content"]
            iteration_result["steps"]["mutation"] = {
                "success": True,
                "hint": current_mutation_hint,
                "content_preview": candidate_content[:200] + "...",
            }

            if progress_callback:
                progress_callback("mutation", {
                    "success": True,
                    "content_preview": candidate_content[:100],
                })

            # ===== 第 2 步：批量测试（语义核验）=====
            test_result = self.run_batch_test(
                user_id, draft_name, candidate_content
            )
            iteration_result["steps"]["test"] = {
                "total": test_result.get("total_scenarios", 0),
                "passed": test_result.get("passed_scenarios", 0),
                "pass_rate": test_result.get("pass_rate", 0),
                "method": test_result.get("method", "unknown"),
                "avg_score": test_result.get("avg_score", 0),
                "failed_details": [
                    {"name": r.get("scenario_name"), "errors": r.get("errors", [])}
                    for r in test_result.get("test_results", []) if not r.get("passed")
                ],
            }

            if progress_callback:
                progress_callback("test", {
                    "passed": test_result.get("passed_scenarios", 0),
                    "total": test_result.get("total_scenarios", 0),
                    "method": test_result.get("method", "unknown"),
                })

            # ===== 第 3 步：评估和决策 =====
            eval_result = self.run_evaluation(
                user_id, draft_name,
                candidate_content,
                test_result.get("test_results", []),
            )
            iteration_result["steps"]["evaluation"] = {
                "score": eval_result.get("score", 0),
                "decision": eval_result.get("decision"),
                "is_improvement": eval_result.get("is_improvement"),
                "checklist_score": eval_result.get("checklist_score", 0),
                "test_pass_rate": eval_result.get("test_pass_rate", 0),
            }

            if progress_callback:
                progress_callback("evaluation", {
                    "score": eval_result.get("score", 0),
                    "decision": eval_result.get("decision"),
                    "is_improvement": eval_result.get("is_improvement"),
                })

            # ===== 第 4 步：MiniCPM 分析 =====
            minicpm_analysis = self._analyze_skills_with_minicpm(
                user_id=user_id,
                draft_name=draft_name,
                iteration=iteration,
                current_content=candidate_content,
                test_results=test_result.get("test_results", []),
                eval_result=eval_result,
            )
            iteration_result["steps"]["minicpm_analysis"] = {
                "problems_identified": minicpm_analysis.get("problems", []),
                "improvement_direction": minicpm_analysis.get("direction", ""),
                "next_mutation_hint": minicpm_analysis.get("next_hint", ""),
            }

            if progress_callback:
                progress_callback("analysis", {
                    "problems": minicpm_analysis.get("problems", []),
                    "direction": minicpm_analysis.get("direction", ""),
                    "next_hint": minicpm_analysis.get("next_hint", ""),
                })

            # 为下一轮准备变异提示
            current_mutation_hint = minicpm_analysis.get("next_hint", "")

            # ===== 第 5 步：提交变异并更新 is_best =====
            self.commit_mutation(
                user_id, draft_name,
                candidate_content=candidate_content,
                score=eval_result.get("score", 0),
                checklist_scores=eval_result.get("checklist_details", {}),
                test_results=test_result.get("test_results", []),
                mutate_raw=candidate_content,
            )

            if progress_callback:
                progress_callback("commit", {
                    "score": eval_result.get("score", 0),
                })

            # ===== 第 6 步：检查改进和终止条件 =====
            current_score = eval_result.get("score", 0)
            is_improvement = eval_result.get("is_improvement", False)

            # 更新 is_best 标记
            if is_improvement:
                self.skill_db.set_best_draft(user_id, draft_name, iteration)

            # 检查连续高分
            if current_score >= score_threshold * 100:
                consecutive_high += 1
            else:
                consecutive_high = 0

            # 检查停滞
            if is_improvement:
                stagnation_counter = 0
            else:
                stagnation_counter += 1

            iteration_result["consecutive_high"] = consecutive_high
            iteration_result["stagnation_counter"] = stagnation_counter
            iteration_result["should_terminate"] = consecutive_high >= consecutive_threshold

            history.append(iteration_result)

            if progress_callback:
                progress_callback("iteration_end", {
                    "iteration": iteration,
                    "consecutive_high": consecutive_high,
                    "stagnation_counter": stagnation_counter,
                    "should_terminate": consecutive_high >= consecutive_threshold,
                    "score": current_score,
                })

            # ===== 终止条件检查 =====
            if consecutive_high >= consecutive_threshold:
                # 达到连续高分阈值，终止
                terminated_reason = "consecutive_high"
                if progress_callback:
                    progress_callback("terminated", {
                        "reason": terminated_reason,
                        "consecutive_high": consecutive_high,
                    })
                break

            if stagnation_counter >= stagnation_threshold:
                # 停滞检测：连续 N 轮无提升，重置进化方向
                stagnation_counter = 0
                current_mutation_hint = self._generate_reset_hint()
                current_score = 0.0

                if progress_callback:
                    progress_callback("stagnation", {
                        "counter": stagnation_counter,
                        "reset_hint": current_mutation_hint,
                    })

        # 获取最终 SOP
        final_draft = self.skill_db.get_sop_draft_for_evolution(user_id, draft_name)
        final_content = str(final_draft.get("current_content", "")) if final_draft else ""
        final_score = float(final_draft.get("best_score", 0)) if final_draft else 0

        # 确定终止原因
        if consecutive_high >= consecutive_threshold:
            terminated_reason = "consecutive_high"
        elif iteration > max_iterations:
            terminated_reason = "max_iterations"
        else:
            terminated_reason = "unknown"

        # 检查是否达到阈值
        reached_threshold = final_score >= score_threshold * 100

        # 更新阶段
        if reached_threshold:
            self.skill_db.update_draft_stage(
                user_id, draft_name,
                final_draft.get("iteration", 1) if final_draft else 1,
                stage=self.STAGE_READY,
            )
        elif iteration > max_iterations:
            self.skill_db.mark_evolution_failed(
                user_id, draft_name,
                reason=f"max_iterations={max_iterations}"
            )

        return {
            "success": True,
            "draft_name": draft_name,
            "total_iterations": len(history),
            "history": history,
            "final_score": final_score,
            "final_content": final_content,
            "reached_threshold": reached_threshold,
            "terminated_reason": terminated_reason,
            "config": {
                "max_iterations": max_iterations,
                "score_threshold": score_threshold,
                "consecutive_threshold": consecutive_threshold,
                "stagnation_threshold": stagnation_threshold,
            },
        }

    def _generate_reset_hint(self) -> str:
        """生成重置进化方向的提示"""
        return (
            "【重置进化方向】"
            "之前的优化方向陷入局部最优，请尝试以下策略："
            "1) 重新审视任务目标，从更高层次思考解决方案；"
            "2) 考虑简化步骤而非增加复杂度；"
            "3) 关注用户真正关心的核心问题，忽略次要细节；"
            "4) 尝试完全不同的异常处理策略。"
        )
        final_content = str(final_draft.get("current_content", "")) if final_draft else ""
        final_score = float(final_draft.get("best_score", 0)) if final_draft else 0

        # 更新阶段
        if final_score >= score_threshold * 100:
            self.skill_db.update_draft_stage(
                user_id, draft_name,
                final_draft.get("iteration", 1) if final_draft else 1,
                stage=self.STAGE_READY,
            )

        return {
            "success": True,
            "draft_name": draft_name,
            "total_iterations": len(history),
            "history": history,
            "final_score": final_score,
            "final_content": final_content,
            "reached_threshold": final_score >= score_threshold * 100,
        }

    def _analyze_skills_with_minicpm(
        self,
        user_id: str,
        draft_name: str,
        iteration: int,
        current_content: str,
        test_results: List[Dict[str, Any]],
        eval_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """第 4 步：使用 MiniCPM 分析当前 skills 的问题及改进方向

        Args:
            user_id: 用户ID
            draft_name: 草稿名
            iteration: 当前迭代轮次
            current_content: 当前 SOP 内容
            test_results: 测试结果
            eval_result: 评估结果

        Returns:
            {
                "problems": [问题1, 问题2, ...],
                "direction": 改进方向描述,
                "next_hint": 下一轮变异提示词,
            }
        """
        # 获取相关信息
        draft = self.skill_db.get_sop_draft_for_evolution(user_id, draft_name)
        app_context = str(draft.get("app_context", "unknown")) if draft else "unknown"
        task_goal = str(draft.get("task_goal", "share_or_send")) if draft else "share_or_send"

        # 提取测试失败的原因
        failed_scenarios = []
        for r in test_results:
            if not r.get("passed"):
                failed_scenarios.append({
                    "name": r.get("scenario_name", "unknown"),
                    "errors": r.get("errors", []),
                    "state_transitions": r.get("state_transitions", []),
                })

        # 获取原始 correction 数据（了解用户真正的问题）
        traces = self.skill_db.get_pending_traces(user_id, min_corrections=1)
        corrections_summary = []
        for t in traces[:3]:  # 取前3条
            corrections_summary.append({
                "session_id": t.get("session_id", "")[:50],
                "app_context": t.get("app_context", ""),
                "corrections": t.get("corrections", [])[:2],  # 每条取前2个
            })

        # 构建 MiniCPM 分析提示词
        prompt = f"""## 任务：分析当前 SOP/规则的问题并给出改进方向

### 当前上下文
- 应用场景：{app_context}
- 任务目标：{task_goal}
- 迭代轮次：{iteration}

### 当前 SOP 内容
```sop
{current_content[:1500]}
```

### 测试结果
- 测试场景数：{len(test_results)}
- 通过数：{sum(1 for r in test_results if r.get('passed'))}
- 通过率：{sum(1 for r in test_results if r.get('passed')) / len(test_results) * 100:.1f}%

### 评估结果
- Checklist 得分：{eval_result.get('checklist_score', 0):.1f}
- 测试通过率：{eval_result.get('test_pass_rate', 0) * 100:.1f}%
- 综合得分：{eval_result.get('score', 0):.1f}

### 失败的测试场景
{failed_scenarios[:3] if failed_scenarios else "无失败场景"}

### 原始用户 correction 数据（了解用户真正关心的问题）
{corrections_summary[:2] if corrections_summary else "无 correction 数据"}

---

## 输出要求

请分析上述信息，输出以下 JSON 格式：

```json
{{
    "problems": [
        "问题1：SOP 中缺少对 XX 场景的处理",
        "问题2：步骤顺序不够清晰",
        "问题3：异常处理不够完善"
    ],
    "direction": "改进方向：需要加强 XX 方面的描述，特别是增加对敏感信息（如病历号）的处理指引",
    "next_hint": "mutation_hint: 请在下一轮变异中重点关注：1) 增加对 XX 场景的明确步骤 2) 补充异常处理 3) 优化步骤描述使其更具体"
}}
```

请只输出 JSON，不要有其他内容。
"""
        # 调用 MiniCPM
        try:
            response = self._call_minicpm(prompt)
            
            # 解析 JSON 响应
            import json
            import re
            
            # 尝试提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {"problems": ["解析失败"], "direction": response[:200], "next_hint": ""}
            
            return {
                "success": True,
                "problems": result.get("problems", []),
                "direction": result.get("direction", ""),
                "next_hint": result.get("next_hint", ""),
                "raw_response": response,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "problems": [],
                "direction": "",
                "next_hint": "",
            }

    # ============== 最终沙盒验证 ==============

    def final_sandbox_validation(
        self,
        user_id: str,
        draft_name: str,
    ) -> Dict[str, Any]:
        """最终沙盒验证（用于发布前）

        Returns:
            {
                "success": True,
                "sandbox_passed": bool,
                "report": {...},
                "error_msg": str,  # 沙盒失败时的错误信息
            }
        """
        draft = self.skill_db.get_sop_draft_for_evolution(user_id, draft_name)
        if not draft:
            return {"success": False, "error": "Draft not found"}

        if draft.get("stage") != self.STAGE_READY:
            return {
                "success": False,
                "error": f"Draft stage is '{draft.get('stage')}', expected '{self.STAGE_READY}'"
            }

        sop_content = str(draft.get("current_content", ""))
        app_context = str(draft.get("app_context", "wechat"))
        task_goal = str(draft.get("task_goal", ""))

        # 获取历史轨迹（用于生成历史失败场景）
        history_traces = self._get_history_traces_for_sandbox(user_id, draft)

        # 运行最终沙盒验证
        sandbox = FinalSandbox(user_id)
        result = sandbox.run_validation(
            sop_content=sop_content,
            app_context=app_context,
            task_goal=task_goal,
            history_traces=history_traces,
        )

        sandbox_passed = result.get("passed", False)

        # 更新阶段
        if sandbox_passed:
            self.skill_db.update_draft_stage(
                user_id, draft_name,
                draft.get("iteration", 1),
                stage=self.STAGE_SANDBOX,
            )
            self.skill_db.update_sandbox_error(user_id, draft_name, "")
        else:
            # 记录沙盒错误，用于下一轮变异
            error_msg = result.get("error", str(result))
            self.skill_db.update_sandbox_error(user_id, draft_name, error_msg)

        return {
            "success": True,
            "sandbox_passed": sandbox_passed,
            "report": result,
            "error_msg": error_msg if not sandbox_passed else "",
        }

    def _get_history_traces_for_sandbox(
        self,
        user_id: str,
        draft: Dict[str, Any],
        max_traces: int = 5,
    ) -> List[Dict[str, Any]]:
        """获取用于沙盒测试的历史轨迹

        从相同 app_context 的历史轨迹中选取，用于重现"摔跤"场景
        """
        app_context = draft.get("app_context", "")
        task_goal = draft.get("task_goal", "")

        # 获取未处理的轨迹
        traces = self.skill_db.get_unprocessed_traces(user_id, min_corrections=0)

        # 筛选相同 app_context 的轨迹
        same_app_traces = [
            t for t in traces
            if t.get("app_context") == app_context
        ]

        # 如果有相同 app_context 的轨迹，取最近的
        if same_app_traces:
            return same_app_traces[:max_traces]

        # 否则取所有轨迹（兜底）
        return traces[:max_traces]

    # ============== 发布 ==============

    def publish_sop(
        self,
        user_id: str,
        draft_name: str,
    ) -> Dict[str, Any]:
        """发布 SOP 到 user_skills/

        发布流程（原子操作）：
        1. 检查草稿阶段
        2. 生成技能文件和数据库记录
        3. 标记 session_trace.processed = 1
        4. 更新草稿阶段为 published

        Returns:
            {
                "success": True,
                "skill_name": str,
                "version": str,
                "path": str,
                "traces_updated": int,
            }
        """
        draft = self.skill_db.get_sop_draft_for_evolution(user_id, draft_name)
        if not draft:
            return {"success": False, "error": "Draft not found"}

        stage = draft.get("stage", "")
        if stage not in (self.STAGE_READY, self.STAGE_SANDBOX):
            return {
                "success": False,
                "error": f"Cannot publish: stage is '{stage}', need sandbox validation first"
            }

        sop_content = str(draft.get("current_content", ""))
        app_context = str(draft.get("app_context", "unknown"))
        task_goal = str(draft.get("task_goal", ""))
        confidence = float(draft.get("best_score", 0)) / 100
        session_ids = draft.get("session_ids", [])

        # 构建演进日志
        evolution_log = {
            "latest_improvements": draft.get("mutation_log", ""),
            "last_failure_reason": draft.get("last_sandbox_error", ""),
        }

        # 生成版本
        skill_name = self._generate_skill_name(draft_name)
        version = self._next_version(user_id, skill_name)
        skill_dir = self.user_skills_root / user_id / skill_name / version

        skill_dir.mkdir(parents=True, exist_ok=True)

        # 构建 SKILL.md
        skill_md_content = self._build_skill_md(
            skill_name=skill_name,
            version=version,
            app_context=app_context,
            task_goal=task_goal,
            sop_content=sop_content,
            confidence=confidence,
            user_id=user_id,
            evolution_log=evolution_log,
        )

        try:
            # ===== 事务开始 =====
            # Step 1: 写入技能文件
            (skill_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

            # Step 2: 保存到数据库
            self.skill_db.publish_sop_version(
                user_id=user_id,
                skill_name=skill_name,
                version=version,
                path=str(skill_dir / "SKILL.md"),
                app_context=app_context,
                task_description=task_goal,
                confidence=confidence,
                source_sessions=session_ids,
                skill_md_content=skill_md_content,
            )

            # Step 3: 标记 session_trace 为已处理
            traces_updated = 0
            if session_ids:
                traces_updated = self.skill_db.mark_traces_processed(user_id, session_ids)

            # Step 4: 更新草稿阶段
            self.skill_db.update_draft_stage(
                user_id, draft_name,
                draft.get("iteration", 1),
                stage=self.STAGE_PUBLISHED,
            )

            # Step 5: 更新目录
            self._update_catalog(user_id)
            # ===== 事务结束 =====

            # Step 6: 写入通知（让用户审核新规则）
            app_display = app_context or "该"
            body = (
                f"系统检测到你在「{app_display}」场景下的行为模式，生成了新的隐私保护规则。"
                f"请确认是否符合你的需求，或前往调整。"
            )
            self.skill_db.add_notification(
                user_id=user_id,
                notif_type="skill_added",
                title=f"新规则「{skill_name}」已生成，请确认",
                body=body,
                skill_name=skill_name,
                skill_version=version,
                event_id=f"pub-{user_id}-{int(time.time())}",
            )

            return {
                "success": True,
                "skill_name": skill_name,
                "version": version,
                "path": str(skill_dir / "SKILL.md"),
                "traces_updated": traces_updated,
            }

        except Exception as e:
            # 事务失败：所有操作都已回滚
            # 清理可能创建的文件
            import shutil

            if skill_dir.exists():
                shutil.rmtree(skill_dir, ignore_errors=True)

            return {
                "success": False,
                "error": f"Publish transaction failed: {str(e)}",
            }

    def _generate_skill_name(self, draft_name: str) -> str:
        if "/" in draft_name:
            return draft_name
        return f"general/{draft_name}"

    def _next_version(self, user_id: str, skill_name: str) -> str:
        root = self.user_skills_root / user_id / skill_name
        if not root.exists():
            return "v1.0.0"

        max_v = 0
        for p in root.iterdir():
            if p.is_dir() and p.name.startswith("v"):
                try:
                    v = float(p.name[1:])
                    max_v = max(max_v, v)
                except ValueError:
                    continue
        return f"v{max_v + 1:.1f}"

    def _build_skill_md(
        self,
        skill_name: str,
        version: str,
        app_context: str,
        task_goal: str,
        sop_content: str,
        confidence: float,
        user_id: str,
        evolution_log: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建 Skill.md 文件内容

        使用标准 Skill 格式模板：
        - YAML frontmatter（元数据）
        - 场景描述、核心目标
        - 权限与隐私约束
        - 操作流程表格
        - 工具函数调用
        - 演进记录
        """
        # 解析 SOP 内容，尝试提取结构化字段
        parsed = self._parse_sop_content(sop_content)

        # 构建演进记录
        evo_log = evolution_log or {}
        latest_improvements = evo_log.get("latest_improvements", "")
        last_failure_reason = evo_log.get("last_failure_reason", "")

        lines = [
            "---",
            f"name: {skill_name}",
            f"version: {version}",
            "type: skill",
            "generated_by: sop-evolution",
            f"generated_ts: {int(time.time())}",
            f"user_id: {user_id}",
            f"confidence: {confidence:.0%}",
            "status: active",
            "---",
            "",
            f"# 技能名称: {skill_name}",
            "",
            "## 场景描述",
            f"{app_context}",
            "",
            "## 核心目标",
            f"{task_goal}",
            "",
            "## 权限与隐私约束 (Security Constraints)",
            "- **PII 保护**: " + parsed.get("pii_protection", "遵循最小化原则，不泄露用户隐私"),
            "- **敏感字段**: " + parsed.get("sensitive_fields", "姓名、联系方式、病历号等"),
            "- **交互红线**: " + parsed.get("interaction_restrictions", "禁止将敏感信息发送到第三方平台"),
            "",
            "## 操作流程 (Standard Operating Procedure)",
        ]

        # 添加操作流程表格
        steps = parsed.get("steps", [])
        if steps:
            lines.extend([
                "| 步骤 | 动作 (Action) | 预期 UI 状态 | 异常处理 (Exception Handling) |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for i, step in enumerate(steps, 1):
                action = step.get("action", "")
                state = step.get("expected_state", "")
                exception = step.get("exception", "")
                lines.append(f"| {i} | {action} | {state} | {exception} |")
        else:
            # 如果没有解析出步骤，直接添加 SOP 内容
            lines.extend([
                "| 步骤 | 动作 (Action) | 预期 UI 状态 | 异常处理 (Exception Handling) |",
                "| :--- | :--- | :--- | :--- |",
                "",
                "```",
                f"{sop_content}",
                "```",
            ])

        # 工具函数调用
        tools = parsed.get("tools", [])
        if tools:
            lines.append("")
            lines.append("## 工具函数调用 (Tooling & Scripts)")
            for tool in tools:
                tool_name = tool.get("name", "")
                tool_desc = tool.get("description", "")
                lines.append(f"- **{tool_name}**: {tool_desc}")

        # 演进记录
        lines.extend([
            "",
            "## 演进记录 (Evolution Log)",
            f"- **改进点**: {latest_improvements or '首次生成'}",
            f"- **上次失败原因**: {last_failure_reason or '无'}",
            "",
            "---",
            "*此 Skill 由系统自动进化生成，如有疑问请联系管理员*",
        ])

        return "\n".join(lines)

    def _parse_sop_content(self, sop_content: str) -> Dict[str, Any]:
        """解析 SOP 内容，尝试提取结构化字段

        如果 SOP 是纯文本，会返回空字典，调用方会使用默认格式。
        如果 SOP 包含结构化标记，会尝试解析。
        """
        result = {
            "pii_protection": "",
            "sensitive_fields": "",
            "interaction_restrictions": "",
            "steps": [],
            "tools": [],
        }

        if not sop_content:
            return result

        # 尝试解析 Markdown 表格格式的步骤
        lines = sop_content.strip().split("\n")
        in_step_table = False

        for line in lines:
            line = line.strip()

            # 检测步骤表格开始
            if "| 步骤 |" in line or "| Step |" in line:
                in_step_table = True
                continue

            # 检测步骤表格结束（遇到空行或代码块）
            if in_step_table and (not line or line.startswith("```")):
                in_step_table = False
                continue

            # 解析表格行
            if in_step_table and "|" in line:
                parts = [p.strip() for p in line.split("|")]
                # 跳过表头和分隔符
                if len(parts) >= 4 and parts[0] and parts[0].isdigit():
                    result["steps"].append({
                        "action": parts[1],
                        "expected_state": parts[2],
                        "exception": parts[3],
                    })

        # 尝试从文本中提取 PII 保护相关描述
        pi_keywords = ["PII", "隐私", "敏感", "保护", "脱敏"]
        for kw in pi_keywords:
            if kw in sop_content:
                idx = sop_content.find(kw)
                context = sop_content[max(0, idx-50):idx+100]
                if not result["pii_protection"]:
                    result["pii_protection"] = context.replace("\n", " ").strip()
                break

        return result

    def _update_catalog(self, user_id: str) -> None:
        versions = self.skill_db.get_active_sop_versions(user_id)

        lines = [
            f"# {user_id} 的 SOP 目录",
            "",
            f"> 最后更新：{time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## SOP 索引",
            "",
            "| 技能名称 | 应用 | 任务描述 | 置信度 | 版本 |",
            "|---------|------|---------|--------|------|",
        ]

        for v in versions:
            lines.append(
                f"| `{v.get('skill_name', '')}` | {v.get('app_context', '')} | "
                f"{v.get('task_description', '')} | {v.get('confidence', 0.0):.0%} | "
                f"{v.get('version', '')} |"
            )

        catalog_path = self.user_skills_root / user_id / "SKILL_CATALOG.md"
        catalog_path.write_text("\n".join(lines), encoding="utf-8")

    # ============== 完整流水线 ==============

    def run_pipeline(
        self,
        *,
        user_id: str,
        draft_name: str,
        app_context: Optional[str] = None,
        task_goal: Optional[str] = None,
        session_ids: Optional[List[str]] = None,
        step: str = "all",
        # 配置化参数（None 表示使用 config/evolution_config.json 中的值）
        max_iterations: Optional[int] = None,
        score_threshold: Optional[float] = None,
        consecutive_threshold: Optional[int] = None,
        stagnation_threshold: Optional[int] = None,
    ) -> Dict[str, Any]:
        """完整 SOP 进化流水线（持久化版）

        步骤：
        1. rebuild: 重建会话轨迹
        2. init: 初始化草稿（检查断点）
        3. evolve: 爬山法进化（while 循环 + 停滞检测）
        4. sandbox: 最终沙盒验证
        5. publish: 发布（事务 + processed 标记）

        断点续传：
        - 如果发现 is_best=1 且 stage='evolving' 的草稿，自动恢复进化

        沙盒验证失败：
        - 沙盒失败后，不发布，但保留当前最优 SOP
        - 错误信息写入 last_sandbox_error，下一轮变异会使用

        Args:
            max_iterations: 最大迭代次数，None 则使用配置
            score_threshold: 分数阈值(0-1)，None 则使用配置
            consecutive_threshold: 连续高分阈值，None 则使用配置
            stagnation_threshold: 停滞检测阈值，None 则使用配置
        """
        step = step.lower().strip()
        result = {
            "user_id": user_id,
            "draft_name": draft_name,
            "step": step,
            "checkpoint_resumed": False,
        }

        # 使用配置值作为默认值
        config_max_iterations = max_iterations or self.config["max_iterations"]
        config_score_threshold = score_threshold or self.config["score_threshold"]
        config_consecutive = consecutive_threshold or self.config["consecutive_threshold"]
        config_stagnation = stagnation_threshold or self.config["stagnation_threshold"]

        # 1. 重建轨迹
        if step in ("rebuild", "all"):
            rebuild_result = self.rebuild_session_traces(user_id)
            result["rebuild"] = rebuild_result
            if step == "rebuild":
                return result

        # 2. 获取 session_ids 和检查断点
        traces = None
        if session_ids is None:
            traces = self.skill_db.get_unprocessed_traces(user_id)
            session_ids = [t["session_id"] for t in traces]

        if not session_ids:
            result["warning"] = "No unprocessed sessions"
            return result

        # 如果没有提供 app_context 和 task_goal，从轨迹中提取
        if app_context is None or task_goal is None:
            if traces is None:
                traces = self.skill_db.get_unprocessed_traces(user_id)
            if traces:
                app_context = app_context or traces[0].get("app_context", "unknown")
                task_goal = task_goal or traces[0].get("task_goal", "")

        app_context = app_context or "wechat"
        task_goal = task_goal or f"sop-{int(time.time())}"

        # 2.5 检查断点续传
        checkpoint = self.skill_db.get_checkpoint(user_id, draft_name)
        if checkpoint and checkpoint.get("is_best"):
            result["checkpoint_resumed"] = True
            result["checkpoint_info"] = {
                "iteration": checkpoint.get("iteration"),
                "score": checkpoint.get("best_score"),
                "stage": checkpoint.get("stage"),
            }
        else:
            # 初始化草稿
            if step in ("init", "all"):
                init_result = self.init_evolution(
                    user_id=user_id,
                    draft_name=draft_name,
                    app_context=app_context,
                    task_goal=task_goal,
                    session_ids=session_ids,
                )
                result["init"] = init_result
                if step == "init":
                    return result

        if step == "init":
            return result

        # 3. 爬山法进化
        if step in ("evolve", "all"):
            evolve_result = self.run_evolution(
                user_id=user_id,
                draft_name=draft_name,
                max_iterations=config_max_iterations,
                score_threshold=config_score_threshold,
                consecutive_threshold=config_consecutive,
                stagnation_threshold=config_stagnation,
            )
            result["evolve"] = evolve_result
            if step == "evolve":
                return result

        # 4. 最终沙盒验证（仅当进化达标时）
        if step in ("sandbox", "all"):
            reached_threshold = evolve_result.get("reached_threshold", False)
            final_score = evolve_result.get("final_score", 0)

            if reached_threshold:
                sandbox_result = self.final_sandbox_validation(user_id, draft_name)
                result["sandbox"] = sandbox_result

                # 如果沙盒通过，可以发布
                if sandbox_result.get("sandbox_passed"):
                    evolve_result["sandbox_passed"] = True
                else:
                    evolve_result["sandbox_passed"] = False
                    evolve_result["sandbox_error"] = sandbox_result.get("error_msg", "")
            else:
                sandbox_result = {
                    "success": False,
                    "skipped": True,
                    "reason": f"进化未达标: 得分 {final_score:.1f} < 阈值 {config_score_threshold * 100:.1f}",
                }
                result["sandbox"] = sandbox_result
                evolve_result["sandbox_passed"] = False

            evolve_result["sandbox"] = sandbox_result
            if step == "sandbox":
                return result

        # 5. 发布（仅当沙盒通过时）
        if step in ("publish", "all"):
            sandbox_passed = evolve_result.get("sandbox_passed", False)
            if sandbox_passed:
                publish_result = self.publish_sop(user_id, draft_name)
                result["publish"] = publish_result
            else:
                result["publish"] = {
                    "success": False,
                    "skipped": True,
                    "reason": "沙盒验证未通过，不发布",
                }

        return result

    def resume_pipeline(
        self,
        *,
        user_id: str,
        draft_name: str,
    ) -> Dict[str, Any]:
        """断点续传：恢复中断的进化流程

        自动检测 is_best=1 且 stage='evolving' 的草稿，继续进化。

        Returns:
            同 run_pipeline 的返回值
        """
        checkpoint = self.skill_db.get_checkpoint(user_id, draft_name)
        if not checkpoint:
            return {
                "success": False,
                "error": f"No checkpoint found for draft: {draft_name}",
            }

        return self.run_pipeline(
            user_id=user_id,
            draft_name=draft_name,
            step="all",
        )


# ============== 兼容性别名 ==============
SkillEvolution = SOPEvolution

"""语义核验模块 - LLM-as-a-Judge 替代状态机。

核心思路：
- 不模拟 UI 操作，而是让 LLM 作为"审计员"
- 直接比对 SOP 草稿与历史成功轨迹的逻辑一致性
- 支持任意 app_context，天生泛化

使用方式：
    evaluator = SemanticEvaluator()
    result = evaluator.evaluate(
        sop_content="步骤 1: 登录 OA...",
        session_trace={"task_goal": "...", "behaviors": [...], "corrections": [...]},
        app_context="hospital_oa"
    )
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============== 数据结构 ==============

@dataclass
class SemanticTestResult:
    """语义核验结果"""
    scenario_name: str
    passed: bool
    score: float  # 0-100
    reasoning: str
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "passed": self.passed,
            "score": self.score,
            "reasoning": self.reasoning,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


# ============== 轻量级 DSL 检查器 ==============

class DSLValidator:
    """DSL 动作检查器 - 方案三的轻量实现"""

    # 标准化动作清单（支持任意 app_context）
    ALLOWED_ACTIONS = {
        # 通用动作
        "login", "logout", "open", "close", "navigate", "back", "confirm", "cancel",
        "submit", "wait", "retry", "error_recovery",
        # 输入动作
        "input", "type", "select", "check", "uncheck",
        # 数据操作
        "fetch", "query", "save", "download", "upload", "delete",
        # 截图/脱敏相关
        "screenshot", "mask", "blur", "redact", "encrypt",
        "pii_detect", "sensitive_check", "privacy_verify",
        # 发送/分享
        "send", "share", "post", "forward", "transmit",
        # 审批/确认
        "approve", "reject", "sign", "verify",
    }

    # 敏感关键词（用于隐私检查）
    PRIVACY_KEYWORDS = {
        "pii": ["身份证", "身份证号", "手机号", "电话号码", "邮箱", "地址", "姓名"],
        "medical": ["病历", "诊断", "处方", "检验报告", "病史", "医嘱"],
        "financial": ["银行账号", "卡号", "密码", "验证码", "余额"],
    }

    # 电脑操作关键词（用于检测错误）
    # 注意：排除手机特有的"桌面"用法
    COMPUTER_KEYWORDS = [
        "浏览器", "打开网页", "输入网址", "搜索栏",
        "键盘", "回车键", "Ctrl", "Alt", "Shift",
        "右键", "拖拽文件到",
        "打开我的电脑", "打开资源管理器",
        # 以下在手机上也有对应含义，但需要结合上下文
        "开始菜单", "任务栏",
    ]

    # 手机桌面/桌面的正确用法
    MOBILE_DESKTOP_PATTERN = r"手机[桌桌面]|桌面[上的图标]"

    @classmethod
    def extract_actions(cls, sop_content: str) -> List[str]:
        """从 SOP 内容中提取所有动作"""
        actions = []
        lines = sop_content.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 匹配动作模式：动词 + 名词
            action_patterns = [
                r"^(?:步骤\s*\d+[.、)]\s*)?([a-zA-Z_]+)",
                r"(?:执行|进行|点击|输入|选择|确认|取消|打开|关闭|登录|登出)[^\n]{0,30}",
            ]

            for pattern in action_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    action = match.group(1).lower() if match.lastindex else None
                    if action:
                        actions.append(action)
                    break

        return actions

    @classmethod
    def validate_sop_structure(cls, sop_content: str) -> Dict[str, Any]:
        """验证 SOP 结构合法性"""
        issues = []
        suggestions = []

        # 检查是否为空
        if not sop_content or len(sop_content.strip()) < 50:
            issues.append("SOP 内容过短或为空")
            suggestions.append("SOP 应包含至少 3 个操作步骤")

        # 检查步骤格式
        step_count = len(re.findall(r"步骤\s*\d+", sop_content))
        if step_count < 2:
            issues.append(f"步骤数量过少 (找到 {step_count} 个步骤)")
            suggestions.append("SOP 应包含至少 3 个清晰的步骤")

        # 检查是否包含敏感操作
        has_privacy = False
        for category, keywords in cls.PRIVACY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in sop_content:
                    has_privacy = True
                    break

        if has_privacy and "screenshot" not in sop_content.lower():
            issues.append("SOP 涉及敏感信息但未包含截图/脱敏操作")
            suggestions.append("敏感信息操作应配合 PII 检测和脱敏步骤")

        # 检查是否使用了电脑操作术语
        sop_lower = sop_content.lower()
        computer_keywords_found = []
        for keyword in cls.COMPUTER_KEYWORDS:
            if keyword in sop_content:
                computer_keywords_found.append(keyword)

        # 过滤手机桌面的正确用法（如"手机桌面上的图标"）
        desktop_correct = re.search(r'手机[桌桌面]|桌面[上的图标]', sop_content)
        if desktop_correct and "桌面" in computer_keywords_found:
            computer_keywords_found.remove("桌面")

        if computer_keywords_found:
            issues.append(f"SOP 包含电脑操作术语: {', '.join(computer_keywords_found[:3])}")
            suggestions.append("请使用手机操作术语：点击、滑动、返回、长按等")

        # 检查是否包含手机操作术语
        mobile_keywords = ["点击", "滑动", "长按", "返回", "切换", "截图"]
        has_mobile_ops = any(kw in sop_content for kw in mobile_keywords)
        if not has_mobile_ops and len(sop_content) > 100:
            suggestions.append("建议添加手机操作术语：点击、滑动、返回等")

        # 提取并检查动作
        actions = cls.extract_actions(sop_content)
        unknown_actions = [a for a in actions if a not in cls.ALLOWED_ACTIONS]

        if unknown_actions:
            # 只记录，不作为严重问题
            pass

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "suggestions": suggestions,
            "step_count": step_count,
            "has_privacy_content": has_privacy,
        }


# ============== LLM 语义核验器 ==============

class SemanticEvaluator:
    """LLM 语义核验器 - 方案一的实现"""

    # 用于 MiniCPM 的评估 Prompt 模板
    EVALUATION_PROMPT_TEMPLATE = """## 任务
你是一个手机操作 SOP 质量审计员。请评估以下 SOP 草稿的质量。

【重要】被评估的 SOP 是用于 Android 手机操作的，不是电脑操作。

## 上下文信息
- **应用场景**: {app_context}
- **任务目标**: {task_goal}
- **历史成功轨迹**:
{trace_summary}
- **SOP 草稿**:
{sop_content}

## 评估标准
请检查以下维度并给出评分 (0-100)：

1. **逻辑完整性** (25分): SOP 是否覆盖了完成任务所需的全部手机操作步骤？
2. **手机操作规范性** (25分): 步骤描述是否使用手机操作术语（点击、滑动、返回等）？
3. **隐私保护充分性** (25分): 是否包含必要的隐私拦截/脱敏步骤（如截图、脱敏处理）？
4. **异常处理完备性** (25分): 是否有明确的手机异常处理指引（应用无响应、网络问题等）？

## 输出格式（必须严格遵循）
直接输出一个 JSON 对象，不要添加任何前缀文字、解释或 markdown 代码块标记：
{{"score": 85, "passed": true, "reasoning": "逻辑完整，手机操作规范，隐私保护到位", "issues": ["缺少异常处理"], "suggestions": ["添加网络异常处理"]}}

## 注意事项
- 只输出 JSON 对象，不要输出任何其他内容
- score 必须是 0-100 的整数或浮点数
- passed 必须是布尔值 true 或 false
- reasoning、issues、suggestions 必须是字符串或字符串数组
- issues 和 suggestions 可以是空数组 []
- 如果 SOP 使用了电脑操作术语（如"浏览器"、"键盘"、"桌面"），必须扣分
- 手机操作应该是"点击屏幕"、"滑动屏幕"等，而非"输入框"、"回车键"
"""

    def __init__(self, minicpm_caller=None):
        """
        Args:
            minicpm_caller: MiniCPM 调用函数，签名: (prompt: str) -> str
                           如果为 None，则使用本地 DSL 验证作为降级
        """
        self.minicpm_caller = minicpm_caller

    def evaluate(
        self,
        sop_content: str,
        session_trace: Dict[str, Any],
        app_context: str = "unknown",
        scenario_name: str = "default",
    ) -> SemanticTestResult:
        """
        评估单个场景

        Args:
            sop_content: SOP 草稿内容
            session_trace: 会话轨迹，包含 task_goal, behaviors, corrections 等
            app_context: 应用上下文
            scenario_name: 场景名称

        Returns:
            SemanticTestResult
        """
        # 构造轨迹摘要
        trace_summary = self._format_trace(session_trace)

        # 构造 Prompt
        prompt = self.EVALUATION_PROMPT_TEMPLATE.format(
            app_context=app_context,
            task_goal=session_trace.get("task_goal", "未知任务"),
            trace_summary=trace_summary,
            sop_content=sop_content[:2000],  # 限制长度
        )

        # 优先使用 LLM
        if self.minicpm_caller:
            try:
                return self._evaluate_with_llm(prompt, scenario_name)
            except Exception as e:
                print(f"[SemanticEvaluator] LLM 调用失败，降级到 DSL: {e}")

        # 降级：使用本地 DSL 验证
        return self._evaluate_with_dsl(sop_content, session_trace, scenario_name)

    def _format_trace(self, trace: Dict[str, Any]) -> str:
        """格式化轨迹为可读文本"""
        lines = []

        # 任务目标
        task_goal = trace.get("task_goal", "")
        if task_goal:
            lines.append(f"- 任务目标: {task_goal}")

        # 行为序列
        behaviors = trace.get("behaviors", [])
        if behaviors:
            lines.append("- 行为序列:")
            for i, b in enumerate(behaviors[:5], 1):  # 只取前5个
                action = b.get("action", "未知")
                result = b.get("result", "")
                lines.append(f"  {i}. {action} -> {result}")

        # 纠错
        corrections = trace.get("corrections", [])
        if corrections:
            lines.append("- 用户纠错:")
            for c in corrections[:3]:  # 只取前3个
                action = c.get("action", "")
                reason = c.get("reason", "")
                lines.append(f"  * {action}: {reason}")

        # 正确流程
        correct_flow = trace.get("correct_flow", [])
        if correct_flow:
            lines.append(f"- 正确流程: {' -> '.join(correct_flow[:5])}")

        return "\n".join(lines) if lines else "- 无历史轨迹信息"

    def _evaluate_with_llm(
        self,
        prompt: str,
        scenario_name: str,
    ) -> SemanticTestResult:
        """使用 LLM 进行评估"""
        try:
            response = self.minicpm_caller(prompt)

            # 解析 JSON
            result_data = self._extract_json(response)

            return SemanticTestResult(
                scenario_name=scenario_name,
                passed=result_data.get("passed", False),
                score=result_data.get("score", 0),
                reasoning=result_data.get("reasoning", ""),
                issues=result_data.get("issues", []),
                suggestions=result_data.get("suggestions", []),
            )
        except (json.JSONDecodeError, ValueError) as e:
            # JSON 解析失败，使用降级
            print(f"[SemanticEvaluator] JSON 解析失败: {e}")
            return self._evaluate_with_dsl_fallback(prompt, scenario_name)

    def _evaluate_with_dsl_fallback(
        self,
        prompt: str,
        scenario_name: str,
    ) -> SemanticTestResult:
        """从 Prompt 中提取 SOP 内容进行 DSL 评估"""
        # 从 prompt 中提取 SOP 内容（格式："- **SOP 草稿**:\\n{content}"）
        sop_match = re.search(r"- \*\*SOP 草稿\*\*:\s*\n(.*?)(?=\n## |$)", prompt, re.DOTALL)
        if sop_match:
            sop_content = sop_match.group(1).strip()
        else:
            sop_content = ""

        # 提取任务目标
        task_match = re.search(r"- \*\*任务目标\*\*: (.*?)(?:\n|$)", prompt)
        task_goal = task_match.group(1).strip() if task_match else ""

        # 构造模拟的 session_trace
        session_trace = {"task_goal": task_goal, "behaviors": [], "corrections": [], "correct_flow": []}

        return self._evaluate_with_dsl(sop_content, session_trace, scenario_name)

    def _evaluate_with_dsl(
        self,
        sop_content: str,
        session_trace: Dict[str, Any],
        scenario_name: str,
    ) -> SemanticTestResult:
        """使用 DSL 规则进行本地评估"""
        dsl_result = DSLValidator.validate_sop_structure(sop_content)

        score = 100.0
        issues = list(dsl_result["issues"])
        suggestions = list(dsl_result["suggestions"])

        # 基于轨迹做额外检查
        correct_flow = session_trace.get("correct_flow", [])
        if correct_flow:
            # 检查 SOP 是否包含轨迹中的关键动作
            sop_lower = sop_content.lower()
            missing_actions = []
            for action in correct_flow[:5]:
                if action.lower() not in sop_lower:
                    missing_actions.append(action)

            if missing_actions:
                issues.append(f"缺少轨迹中的关键动作: {', '.join(missing_actions)}")
                score -= 20

        # 检查隐私保护
        # 方案1：检查 SOP 内容是否包含隐私关键词
        sop_lower = sop_content.lower()
        privacy_keywords = ["病历", "身份证", "医保卡", "银行卡", "密码", "账号", "联系方式"]
        has_privacy_in_sop = any(k in sop_lower for k in privacy_keywords)

        # 方案2：检查 task_goal 是否暗示隐私任务
        if session_trace.get("task_goal"):
            goal = session_trace["task_goal"].lower()
            goal_has_privacy = any(k in goal for k in ["病历", "身份证", "隐私", "敏感"])

            if goal_has_privacy:
                # SOP 中需要包含隐私处理步骤（截图、脱敏、打码等）
                privacy_actions = ["截图", "脱敏", "打码", "模糊", "隐藏", "遮盖"]
                has_privacy_action = any(k in sop_content for k in privacy_actions)

                if not has_privacy_action:
                    issues.append("涉及隐私信息的任务缺少隐私保护步骤（如截图、脱敏处理）")
                    score -= 15
                else:
                    # 有隐私处理，但检查关键词是否合理
                    if has_privacy_in_sop and has_privacy_action:
                        # 隐私信息和处理都有，评估为合理
                        pass

        # 步骤太少扣分
        if dsl_result["step_count"] < 3:
            issues.append("步骤数量不足")
            score -= 10

        score = max(0, min(100, score))

        return SemanticTestResult(
            scenario_name=scenario_name,
            passed=score >= 60,
            score=score,
            reasoning="基于 DSL 规则的本地评估",
            issues=issues,
            suggestions=suggestions,
        )

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """从文本中提取 JSON

        支持多种格式：
        1. 纯 JSON 对象：{...}
        2. JSON 在代码块中：```json {...} ```
        3. JSON 嵌入文本中
        """
        if not text:
            raise ValueError("输入文本为空")

        # 清理文本
        text = text.strip()

        # 方法1：尝试直接解析整个文本
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 方法2：移除 markdown 代码块标记
        text_clean = text
        for pattern in [r"^```json\s*", r"^```\s*", r"\s*```$"]:
            text_clean = re.sub(pattern, "", text_clean, flags=re.MULTILINE).strip()

        # 尝试解析清理后的文本
        try:
            return json.loads(text_clean)
        except json.JSONDecodeError:
            pass

        # 方法3：使用括号匹配找到完整的 JSON 对象（支持嵌套）
        def find_matching_braces(s: str, start: int) -> tuple:
            """从 start 位置开始，找到匹配的 { 和 }"""
            depth = 0
            start_brace = s.find('{', start)
            if start_brace == -1:
                return -1, -1
            i = start_brace
            while i < len(s):
                if s[i] == '{':
                    depth += 1
                elif s[i] == '}':
                    depth -= 1
                    if depth == 0:
                        return start_brace, i
                i += 1
            return start_brace, -1

        first_brace, last_brace = find_matching_braces(text_clean, 0)
        if first_brace != -1 and last_brace != -1:
            candidate = text_clean[first_brace:last_brace + 1]
            try:
                result = json.loads(candidate)
                # 验证关键字段存在
                if "score" in result:
                    return result
            except json.JSONDecodeError:
                pass

        # 方法4：尝试找到数组格式 [...]
        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            candidate = text[first_bracket:last_bracket + 1]
            try:
                result = json.loads(candidate)
                if isinstance(result, list) and len(result) > 0:
                    # 尝试找第一个包含 score 的对象
                    for item in result:
                        if isinstance(item, dict) and "score" in item:
                            return item
            except json.JSONDecodeError:
                pass

        # 方法5：尝试修复常见的 JSON 问题
        # 5.1 单引号替换
        fixed = text.replace("'", '"')
        # 5.2 移除尾部的逗号
        fixed = re.sub(r",(\s*[}\]])", r"\1", fixed)
        # 5.3 移除注释
        fixed = re.sub(r"//.*$", "", fixed, flags=re.MULTILINE)
        # 5.4 使用括号匹配移除末尾的非 JSON 文本
        if fixed.startswith("{"):
            _, last_br = find_matching_braces(fixed, 0)
            if last_br > 0:
                fixed = fixed[:last_br + 1]

        try:
            result = json.loads(fixed)
            if "score" in result:
                return result
        except json.JSONDecodeError:
            pass

        raise ValueError(f"无法从文本中提取有效 JSON: {text[:200]}...")

    def _fallback_result(
        self,
        scenario_name: str,
        reason: str,
    ) -> SemanticTestResult:
        """降级时的默认结果"""
        return SemanticTestResult(
            scenario_name=scenario_name,
            passed=False,
            score=0,
            reasoning=f"评估失败: {reason}",
            issues=[reason],
            suggestions=["请检查 SOP 内容是否有效"],
        )


# ============== 便捷函数 ==============

def quick_evaluate(
    sop_content: str,
    session_trace: Dict[str, Any],
    app_context: str = "unknown",
    minicpm_caller=None,
) -> SemanticTestResult:
    """快速评估 SOP"""
    evaluator = SemanticEvaluator(minicpm_caller=minicpm_caller)
    return evaluator.evaluate(
        sop_content=sop_content,
        session_trace=session_trace,
        app_context=app_context,
    )


def batch_evaluate(
    sop_content: str,
    session_traces: List[Dict[str, Any]],
    app_context: str = "unknown",
    minicpm_caller=None,
) -> List[SemanticTestResult]:
    """批量评估 SOP"""
    evaluator = SemanticEvaluator(minicpm_caller=minicpm_caller)
    results = []

    for trace in session_traces:
        scenario_name = trace.get("session_id", trace.get("name", "default"))
        result = evaluator.evaluate(
            sop_content=sop_content,
            session_trace=trace,
            app_context=app_context,
            scenario_name=scenario_name,
        )
        results.append(result)

    return results

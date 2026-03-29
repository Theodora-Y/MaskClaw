"""Checklist Evaluator - SOP 质量评分检查器。

基于用户定义的 4 个检查项对 SOP 执行结果评分：
1. PRIV_01 (隐私合规)：检查敏感字段是否被保护
2. FLOW_01 (逻辑连贯性)：检查步骤状态跳转是否符合 UI 逻辑
3. FAIL_01 (异常鲁棒性)：检查是否有分支异常处理
4. EFFI_01 (执行效率)：评价步骤冗余度

评分标准：
- 4 项全过 = 100 分
- 3 项过 = 75 分
- 2 项过 = 50 分
- 1 项过 = 25 分
- 0 项过 = 0 分

使用方式：
    evaluator = ChecklistEvaluator()
    result = evaluator.evaluate(sop_content, execution_result)
    # result = {"score": 75, "passed": ["PRIV_01", "FLOW_01", "FAIL_01"], "failed": ["EFFI_01"]}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass
class ChecklistItem:
    """检查项定义"""
    item_id: str
    description: str
    weight: float = 1.0
    check_fn: Optional[Callable] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "description": self.description,
            "weight": self.weight,
        }


@dataclass
class ChecklistResult:
    """检查结果"""
    item_id: str
    passed: bool
    score: float
    details: str
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "passed": self.passed,
            "score": self.score,
            "details": self.details,
            "evidence": self.evidence,
        }


@dataclass
class EvaluationResult:
    """完整评估结果"""
    score: float  # 0-100
    passed_items: List[str]
    failed_items: List[str]
    item_results: Dict[str, ChecklistResult]
    overall_pass: bool
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "passed_items": self.passed_items,
            "failed_items": self.failed_items,
            "item_results": {k: v.to_dict() for k, v in self.item_results.items()},
            "overall_pass": self.overall_pass,
            "details": self.details,
        }


class ChecklistEvaluator:
    """SOP 质量评分检查器"""

    # 敏感字段列表
    SENSITIVE_FIELDS = {
        "real_name", "id_card", "id_number", "身份证",
        "phone", "mobile", "电话号码", "手机号",
        "bank_card", "bankcard", "银行卡",
        "address", "家庭地址", "收货地址",
        "balance", "余额", "账户余额",
        "salary", "工资",
        "password", "pin", "支付密码",
    }

    # 状态跳转映射（模拟环境）
    VALID_STATE_TRANSITIONS = {
        "wechat": {
            "home": ["chat_list", "search"],
            "chat_list": ["chat_window", "home"],
            "chat_window": ["add_menu", "red_packet_page", "transfer_page", "chat_list"],
            "add_menu": ["red_packet_page", "transfer_page", "chat_window"],
            "red_packet_page": ["payment_password", "chat_window"],
            "transfer_page": ["payment_password", "chat_window"],
            "payment_password": ["chat_window"],
        },
        "alipay": {
            "home": ["pay_page", "transfer_page"],
            "pay_page": ["payment_password", "home"],
            "transfer_page": ["receiver_picker", "payment_password"],
            "receiver_picker": ["transfer_page"],
            "payment_password": ["transfer_success", "pay_success"],
        },
    }

    # 异常关键词
    EXCEPTION_KEYWORDS = {
        "如果", "若", "万一", "异常", "失败", "错误",
        "try", "except", "catch", "error", "fail",
        "超时", "网络", "重试", "回退",
    }

    def __init__(self):
        self.checklist: Dict[str, ChecklistItem] = {
            "PRIV_01": ChecklistItem(
                item_id="PRIV_01",
                description="隐私合规：检查敏感字段是否被保护",
                weight=1.0,
            ),
            "FLOW_01": ChecklistItem(
                item_id="FLOW_01",
                description="逻辑连贯性：检查步骤状态跳转是否符合 UI 逻辑",
                weight=1.0,
            ),
            "FAIL_01": ChecklistItem(
                item_id="FAIL_01",
                description="异常鲁棒性：检查是否有分支异常处理",
                weight=1.0,
            ),
            "EFFI_01": ChecklistItem(
                item_id="EFFI_01",
                description="执行效率：评价步骤冗余度",
                weight=1.0,
            ),
        }

    def evaluate(
        self,
        sop_content: str,
        execution_result: Optional[Dict[str, Any]] = None,
        app_context: str = "wechat",
    ) -> EvaluationResult:
        """评估 SOP 质量

        Args:
            sop_content: SOP 内容
            execution_result: 执行结果（可选，包含 state_transitions 等）
            app_context: 应用上下文

        Returns:
            EvaluationResult
        """
        results: Dict[str, ChecklistResult] = {}
        passed_items: List[str] = []
        failed_items: List[str] = []

        # 解析 SOP 步骤
        steps = self._parse_steps(sop_content)

        # 1. PRIV_01 - 隐私合规检查
        priv_result = self._check_privacy(sop_content, steps)
        results["PRIV_01"] = priv_result
        if priv_result.passed:
            passed_items.append("PRIV_01")
        else:
            failed_items.append("PRIV_01")

        # 2. FLOW_01 - 逻辑连贯性检查
        flow_result = self._check_flow_coherence(sop_content, steps, execution_result, app_context)
        results["FLOW_01"] = flow_result
        if flow_result.passed:
            passed_items.append("FLOW_01")
        else:
            failed_items.append("FLOW_01")

        # 3. FAIL_01 - 异常鲁棒性检查
        fail_result = self._check_exception_handling(sop_content, steps)
        results["FAIL_01"] = fail_result
        if fail_result.passed:
            passed_items.append("FAIL_01")
        else:
            failed_items.append("FAIL_01")

        # 4. EFFI_01 - 执行效率检查
        effi_result = self._check_efficiency(sop_content, steps)
        results["EFFI_01"] = effi_result
        if effi_result.passed:
            passed_items.append("EFFI_01")
        else:
            failed_items.append("EFFI_01")

        # 计算总分
        total_items = len(self.checklist)
        passed_count = len(passed_items)
        score = (passed_count / total_items) * 100

        # 综合判断
        overall_pass = passed_count >= 3  # 至少 3 项通过

        # 生成详情
        details = self._generate_details(results, passed_count, total_items)

        return EvaluationResult(
            score=score,
            passed_items=passed_items,
            failed_items=failed_items,
            item_results=results,
            overall_pass=overall_pass,
            details=details,
        )

    def _parse_steps(self, sop_content: str) -> List[Dict[str, Any]]:
        """解析 SOP 为步骤列表"""
        steps = []
        lines = sop_content.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 匹配步骤行
            match = re.match(r"^\s*(?:步骤?\s*)?(\d+)[.、):]\s*(.+)$", line, re.IGNORECASE)
            if match:
                step_num = int(match.group(1))
                description = match.group(2).strip()
                steps.append({
                    "step_number": step_num,
                    "description": description,
                    "action": self._extract_action(description),
                })
                continue

            # 匹配 bullet 点
            bullet_match = re.match(r"^\s*[-•*]\s+(.+)$", line)
            if bullet_match:
                description = bullet_match.group(1).strip()
                steps.append({
                    "step_number": len(steps) + 1,
                    "description": description,
                    "action": self._extract_action(description),
                })

        return steps

    def _extract_action(self, description: str) -> str:
        """从描述中提取动作"""
        action_patterns = [
            (r"打开|进入|点击.*聊天", "open_chat"),
            (r"点击.*红包|发.*红包", "click_red_packet"),
            (r"点击.*转账|转.*账", "click_transfer"),
            (r"输入.*金额|填写.*金额", "input_amount"),
            (r"输入.*密码|填写.*密码", "input_password"),
            (r"确认|确定|发送", "confirm"),
            (r"取消|返回", "cancel"),
            (r"点击.*\+|添加", "click_add"),
        ]

        description_lower = description.lower()
        for pattern, action in action_patterns:
            if re.search(pattern, description_lower):
                return action

        return "unknown"

    def _check_privacy(
        self,
        sop_content: str,
        steps: List[Dict[str, Any]],
    ) -> ChecklistResult:
        """PRIV_01: 检查敏感字段处理"""
        evidence = []
        passed = True

        sop_lower = sop_content.lower()

        # 检查是否涉及敏感字段
        sensitive_found = False
        for field in self.SENSITIVE_FIELDS:
            if field.lower() in sop_lower:
                sensitive_found = True
                evidence.append(f"发现敏感字段: {field}")

                # 检查是否有保护措施
                protection_patterns = [
                    r"不.*填写", r"禁止.*填写", r"不要.*填",
                    r"留空", r"跳过", r"空.*红包",
                    r"mask|obfuscate|脱敏|加密",
                ]
                has_protection = any(re.search(p, sop_lower) for p in protection_patterns)

                if not has_protection:
                    passed = False
                    evidence.append(f"敏感字段 '{field}' 缺少保护措施")

        if not sensitive_found:
            evidence.append("未发现敏感字段处理，符合要求")
        elif passed:
            evidence.append("敏感字段已采取保护措施")

        details = "发现敏感信息处理" if sensitive_found else "无敏感信息处理"
        score = 100.0 if passed else 0.0

        return ChecklistResult(
            item_id="PRIV_01",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence,
        )

    def _check_flow_coherence(
        self,
        sop_content: str,
        steps: List[Dict[str, Any]],
        execution_result: Optional[Dict[str, Any]],
        app_context: str,
    ) -> ChecklistResult:
        """FLOW_01: 检查步骤逻辑连贯性"""
        evidence = []
        issues = []

        if execution_result and "state_transitions" in execution_result:
            # 有执行结果，检查实际状态转换
            transitions = execution_result["state_transitions"]
            valid_transitions = self.VALID_STATE_TRANSITIONS.get(app_context, {})

            for i in range(len(transitions) - 1):
                from_state = transitions[i]
                to_state = transitions[i + 1]

                allowed = valid_transitions.get(from_state, [])
                if to_state not in allowed:
                    issues.append(f"状态转换无效: {from_state} -> {to_state}")
                    evidence.append(f"❌ {from_state} → {to_state}")

            if not issues:
                evidence.append("✓ 所有状态转换符合 UI 逻辑")

        # 检查步骤顺序是否合理
        if len(steps) >= 2:
            actions = [s["action"] for s in steps]

            # 检查是否有"打开"作为第一步
            if actions[0] not in ("open_chat", "unknown"):
                issues.append("第一步应该是打开/进入操作")
                evidence.append("⚠ 第一步不是打开操作")

            # 检查是否在确认前有输入
            has_input = "input_amount" in actions or "input_password" in actions
            has_confirm = "confirm" in actions
            if has_confirm and not has_input:
                issues.append("确认操作前缺少必要的输入步骤")
                evidence.append("⚠ 确认前无输入")

        if not issues:
            evidence.append("✓ 步骤逻辑连贯")

        passed = len(issues) == 0
        details = f"发现 {len(issues)} 个逻辑问题" if issues else "步骤逻辑连贯"
        score = 100.0 if passed else 50.0

        return ChecklistResult(
            item_id="FLOW_01",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence,
        )

    def _check_exception_handling(
        self,
        sop_content: str,
        steps: List[Dict[str, Any]],
    ) -> ChecklistResult:
        """FAIL_01: 检查异常处理"""
        evidence = []
        passed = True

        sop_lower = sop_content.lower()

        # 检查是否有关键词
        exception_keywords_found = []
        for keyword in self.EXCEPTION_KEYWORDS:
            if keyword in sop_lower:
                exception_keywords_found.append(keyword)
                evidence.append(f"发现异常处理关键词: {keyword}")

        # 检查是否有分支结构
        branch_patterns = [
            r"如果.*则", r"若.*则", r"如果.*失败",
            r"如果.*异常", r"若.*错误",
        ]
        has_branch = any(re.search(p, sop_lower) for p in branch_patterns)

        if has_branch:
            evidence.append("✓ 发现分支异常处理逻辑")

        # 评估异常处理覆盖率
        if len(steps) >= 3 and not exception_keywords_found:
            passed = False
            evidence.append("⚠ 缺少异常处理描述")
        elif len(exception_keywords_found) < 2:
            passed = False
            evidence.append("⚠ 异常处理不够完善")

        details = f"发现 {len(exception_keywords_found)} 处异常处理" if exception_keywords_found else "缺少异常处理"
        score = 100.0 if passed else 25.0

        return ChecklistResult(
            item_id="FAIL_01",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence,
        )

    def _check_efficiency(
        self,
        sop_content: str,
        steps: List[Dict[str, Any]],
    ) -> ChecklistResult:
        """EFFI_01: 检查执行效率（步骤冗余度）"""
        evidence = []
        passed = True

        step_count = len(steps)
        evidence.append(f"总步骤数: {step_count}")

        # 根据任务类型评估合理步骤数
        # 发红包: 3-6 步合理
        # 转账: 4-7 步合理
        # 发微博: 2-4 步合理
        efficient_range = (2, 8)

        if step_count < efficient_range[0]:
            issues = f"步骤过少({step_count}步)，可能缺少必要步骤"
            evidence.append(f"⚠ {issues}")
            passed = False
        elif step_count > efficient_range[1]:
            issues = f"步骤过多({step_count}步)，可能存在冗余"
            evidence.append(f"⚠ {issues}")
            # 超过 8 步才扣分
            passed = step_count <= 12

        # 检查是否有重复动作
        actions = [s["action"] for s in steps if s["action"] != "unknown"]
        if len(actions) != len(set(actions)):
            duplicates = [a for a in actions if actions.count(a) > 1]
            evidence.append(f"⚠ 发现重复动作: {set(duplicates)}")

        if passed:
            evidence.append("✓ 步骤数量合理，无明显冗余")

        details = f"步骤数 {step_count}，评估为{'高效' if passed else '冗余'}"
        score = 100.0 if passed else 50.0

        return ChecklistResult(
            item_id="EFFI_01",
            passed=passed,
            score=score,
            details=details,
            evidence=evidence,
        )

    def _generate_details(
        self,
        results: Dict[str, ChecklistResult],
        passed_count: int,
        total_count: int,
    ) -> str:
        """生成评估详情"""
        lines = [
            f"评分结果: {passed_count}/{total_count} 项通过",
            f"总分: {int((passed_count / total_count) * 100)} 分",
            "",
        ]

        for item_id, result in results.items():
            status = "✓ 通过" if result.passed else "✗ 失败"
            lines.append(f"[{item_id}] {status} - {result.details}")

        return "\n".join(lines)

    def get_checklist(self) -> List[Dict[str, Any]]:
        """获取检查项列表"""
        return [item.to_dict() for item in self.checklist.values()]


# ============== 便捷函数 ==============

def evaluate_sop(
    sop_content: str,
    execution_result: Optional[Dict[str, Any]] = None,
    app_context: str = "wechat",
) -> Dict[str, Any]:
    """评估 SOP 质量的便捷函数"""
    evaluator = ChecklistEvaluator()
    result = evaluator.evaluate(sop_content, execution_result, app_context)
    return result.to_dict()

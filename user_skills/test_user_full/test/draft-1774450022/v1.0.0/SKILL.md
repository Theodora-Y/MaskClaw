---
name: test/draft-1774450022
version: v1.0.0
type: skill
generated_by: sop-evolution
generated_ts: 1774450022
user_id: test_user_full
confidence: 89%
status: active
---

# 技能名称: test/draft-1774450022

## 场景描述
wechat

## 核心目标
发送微信消息

## 权限与隐私约束 (Security Constraints)
- **PII 保护**: 搜索结果中的联系人，进入对话页面 异常处理：若页面空白，尝试返回后重新搜索  步骤 5: 发送消息 隐私保护：发送前检查消息内容是否包含敏感信息，如身份证号、银行卡号等  步骤 5.5: 脱敏处理（如有必要） 具体动作：若检测到敏感信息，调用脱敏工具处理后再发送 异常处理：若脱敏失败，提示用户手动处
- **敏感字段**: 
- **交互红线**: 

## 操作流程 (Standard Operating Procedure)
| 步骤 | 动作 (Action) | 预期 UI 状态 | 异常处理 (Exception Handling) |
| :--- | :--- | :--- | :--- |

```
【安卓手机操作 SOP - 发送微信消息】

步骤 1: 打开微信应用
具体动作：点击手机桌面上的微信图标，等待微信加载完成
异常处理：若微信未响应，点击"强制停止"后重新打开

步骤 2: 进入通讯录
具体动作：点击屏幕底部的"通讯录"标签页
异常处理：若网络不稳定，等待加载或切换网络

步骤 3: 搜索联系人
具体动作：点击右上角搜索图标，输入联系人姓名
异常处理：若搜索无结果，检查输入是否正确

步骤 4: 进入聊天窗口
具体动作：点击搜索结果中的联系人，进入对话页面
异常处理：若页面空白，尝试返回后重新搜索

步骤 5: 发送消息
隐私保护：发送前检查消息内容是否包含敏感信息，如身份证号、银行卡号等

步骤 5.5: 脱敏处理（如有必要）
具体动作：若检测到敏感信息，调用脱敏工具处理后再发送
异常处理：若脱敏失败，提示用户手动处理
具体动作：在聊天输入框中点击，输入消息，点击发送按钮
隐私保护：发送前检查消息内容是否包含敏感信息
异常处理：若发送失败，检查网络连接后重试

```

## 演进记录 (Evolution Log)
- **改进点**: [{'ts': 1774450022, 'score': 88.14, 'decision': 'accept', 'checklist': {'score': 75.0, 'passed_items': ['PRIV_01', 'FAIL_01', 'EFFI_01'], 'failed_items': ['FLOW_01'], 'item_results': {'PRIV_01': {'item_id': 'PRIV_01', 'passed': True, 'score': 100.0, 'details': '发现敏感信息处理', 'evidence': ['发现敏感字段: 身份证', '发现敏感字段: 银行卡', '敏感字段已采取保护措施']}, 'FLOW_01': {'item_id': 'FLOW_01', 'passed': False, 'score': 50.0, 'details': '发现 1 个逻辑问题', 'evidence': ['✓ 所有状态转换符合 UI 逻辑', '⚠ 确认前无输入']}, 'FAIL_01': {'item_id': 'FAIL_01', 'passed': True, 'score': 100.0, 'details': '发现 5 处异常处理', 'evidence': ['发现异常处理关键词: 重试', '发现异常处理关键词: 网络', '发现异常处理关键词: 若', '发现异常处理关键词: 失败', '发现异常处理关键词: 异常']}, 'EFFI_01': {'item_id': 'EFFI_01', 'passed': True, 'score': 100.0, 'details': '步骤数 6，评估为高效', 'evidence': ['总步骤数: 6', "⚠ 发现重复动作: {'open_chat'}", '✓ 步骤数量合理，无明显冗余']}}, 'overall_pass': True, 'details': '评分结果: 3/4 项通过\n总分: 75 分\n\n[PRIV_01] ✓ 通过 - 发现敏感信息处理\n[FLOW_01] ✗ 失败 - 发现 1 个逻辑问题\n[FAIL_01] ✓ 通过 - 发现 5 处异常处理\n[EFFI_01] ✓ 通过 - 步骤数 6，评估为高效'}}, {'ts': 1774450022, 'score': 89.4, 'decision': 'accept', 'checklist': {'score': 75.0, 'passed_items': ['PRIV_01', 'FAIL_01', 'EFFI_01'], 'failed_items': ['FLOW_01'], 'item_results': {'PRIV_01': {'item_id': 'PRIV_01', 'passed': True, 'score': 100.0, 'details': '发现敏感信息处理', 'evidence': ['发现敏感字段: 身份证', '发现敏感字段: 银行卡', '敏感字段已采取保护措施']}, 'FLOW_01': {'item_id': 'FLOW_01', 'passed': False, 'score': 50.0, 'details': '发现 1 个逻辑问题', 'evidence': ['✓ 所有状态转换符合 UI 逻辑', '⚠ 确认前无输入']}, 'FAIL_01': {'item_id': 'FAIL_01', 'passed': True, 'score': 100.0, 'details': '发现 5 处异常处理', 'evidence': ['发现异常处理关键词: 重试', '发现异常处理关键词: 网络', '发现异常处理关键词: 若', '发现异常处理关键词: 失败', '发现异常处理关键词: 异常']}, 'EFFI_01': {'item_id': 'EFFI_01', 'passed': True, 'score': 100.0, 'details': '步骤数 6，评估为高效', 'evidence': ['总步骤数: 6', "⚠ 发现重复动作: {'open_chat'}", '✓ 步骤数量合理，无明显冗余']}}, 'overall_pass': True, 'details': '评分结果: 3/4 项通过\n总分: 75 分\n\n[PRIV_01] ✓ 通过 - 发现敏感信息处理\n[FLOW_01] ✗ 失败 - 发现 1 个逻辑问题\n[FAIL_01] ✓ 通过 - 发现 5 处异常处理\n[EFFI_01] ✓ 通过 - 步骤数 6，评估为高效'}}, {'ts': 1774450022, 'score': 89.4, 'decision': 'reject', 'checklist': {'score': 75.0, 'passed_items': ['PRIV_01', 'FAIL_01', 'EFFI_01'], 'failed_items': ['FLOW_01'], 'item_results': {'PRIV_01': {'item_id': 'PRIV_01', 'passed': True, 'score': 100.0, 'details': '发现敏感信息处理', 'evidence': ['发现敏感字段: 身份证', '发现敏感字段: 银行卡', '敏感字段已采取保护措施']}, 'FLOW_01': {'item_id': 'FLOW_01', 'passed': False, 'score': 50.0, 'details': '发现 1 个逻辑问题', 'evidence': ['✓ 所有状态转换符合 UI 逻辑', '⚠ 确认前无输入']}, 'FAIL_01': {'item_id': 'FAIL_01', 'passed': True, 'score': 100.0, 'details': '发现 5 处异常处理', 'evidence': ['发现异常处理关键词: 重试', '发现异常处理关键词: 网络', '发现异常处理关键词: 若', '发现异常处理关键词: 失败', '发现异常处理关键词: 异常']}, 'EFFI_01': {'item_id': 'EFFI_01', 'passed': True, 'score': 100.0, 'details': '步骤数 6，评估为高效', 'evidence': ['总步骤数: 6', "⚠ 发现重复动作: {'open_chat'}", '✓ 步骤数量合理，无明显冗余']}}, 'overall_pass': True, 'details': '评分结果: 3/4 项通过\n总分: 75 分\n\n[PRIV_01] ✓ 通过 - 发现敏感信息处理\n[FLOW_01] ✗ 失败 - 发现 1 个逻辑问题\n[FAIL_01] ✓ 通过 - 发现 5 处异常处理\n[EFFI_01] ✓ 通过 - 步骤数 6，评估为高效'}}]
- **上次失败原因**: 无

---
*此 Skill 由系统自动进化生成，如有疑问请联系管理员*
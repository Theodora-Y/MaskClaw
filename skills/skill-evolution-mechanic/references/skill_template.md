# 自动生成 Skill 的模板规范
version: v0.1.0

---

## SKILL.md 结构

分两部分：

**Part 1：YAML frontmatter（脚本填，不走模型）**

---
name: privacy-{field_slug}-{strategy}-v{version}
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: {created_ts}
user_id: {user_id}
confidence: {confidence}
needs_review: {needs_review}
status: sandbox_passed
description: >
  {scene}场景下的隐私防护技能。
  涉及字段：{sensitive_field}，策略：{strategy}。
---

**Part 2：Markdown 正文（MiniCPM 第二次调用生成）**

# {scene}隐私防护

{minicpm_generated_body}

---

## Part 1 占位符填写规则

| 占位符 | 来源 | 处理方式 |
|---|---|---|
| field_slug | sensitive_field | 下划线换连字符，去除非法字符 |
| strategy | MiniCPM 第一次输出 | 直接用 |
| version | 脚本自增 | 同一用户同字段同策略有旧版本则+1 |
| created_ts | 系统时间 | Unix 时间戳 |
| confidence | 脚本计算 | 保留两位小数 |
| needs_review | confidence 是否在 0.6~0.75 | true/false |
| scene | MiniCPM 第一次输出 | 直接用中文 |

## Part 2 正文生成规则

正文由 MiniCPM 第二次调用生成，
详见 prompts/evolution_skill_writing.txt

正文必须包含三个章节：
  ## 何时使用
  ## 执行步骤
  ## 边界情况

不允许出现：
  - 原始字段名作为章节标题
  - JSON 格式内容
  - strategy/replacement 等技术术语直接暴露

---

## name 字段生成规则
```python
def make_skill_name(sensitive_field, strategy, version):
    slug = sensitive_field.lower()
    slug = slug.replace("_", "-")
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    return f"privacy-{slug}-{strategy}-v{version}"
```

示例：
  file_content + block → privacy-file-content-block-v1
  home_address + replace → privacy-home-address-replace-v1
  phone + block → privacy-phone-block-v1
```

---

## 新增的 Prompt 文件
```
prompts/
  evolution_rule_extract.txt    ← 已有，第一次调用
  evolution_skill_writing.txt   ← 新增，第二次调用
```

`evolution_skill_writing.txt` 内容：
```
你是隐私保护技能文档编写助手。
根据以下隐私规则，编写标准的技能操作文档正文。

规则信息：
场景：{scene}
涉及字段：{sensitive_field}
操作策略：{strategy}（block=直接拦截，replace=替换内容）
规则描述：{rule_text}
触发App：{app_context_hint}
替换值：{replacement}

按以下格式输出，不要输出其他任何内容：

## 何时使用
[用一到两句话描述触发场景，面向Agent，说清楚在什么App、
什么操作、什么内容时激活，不要出现字段名]

## 执行步骤
- [ ] [第一步]
- [ ] [第二步]
- [ ] [第三步]
[strategy=block时：步骤包含检查、拦截、提示用户]
[strategy=replace时：步骤包含检查、替换内容、继续操作]
[步骤数量3-5个，每步一个动作]

## 边界情况
- [特殊情况1]：[处理方式]
- [特殊情况2]：[处理方式]
[列出1-3条，不够就写1条，不要硬凑]
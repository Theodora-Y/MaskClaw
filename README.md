<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<div align="center">

# <span style="font-family: 'Orbitron', sans-serif; font-size: 4em; font-weight: 900; letter-spacing: 0.15em; background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">MaskClaw</span>

### <span style="font-family: 'Inter', sans-serif; font-weight: 500; color: #64748b;">基于端侧模型自进化规则抽取的个性化隐私保护框架</span>

<p>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)]()
[![MiniCPM](https://img.shields.io/badge/MiniCPM--V-4.5-FF6B6B?style=for-the-badge&logo=box&logoColor=white)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-08080-009688?style=for-the-badge&logo=fastapi&logoColor=white)]()
[![ChromaDB](https://img.shields.io/badge/ChromaDB-RAG-5E35B1?style=for-the-badge)]()
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)]()

</p>

<p style="font-family: 'Inter', sans-serif; font-size: 1.1em; color: #475569; margin-top: 1.5rem;">
  <strong style="color: #6366f1;">端侧隐私守卫</strong> × <strong style="color: #8b5cf6;">自进化规则引擎</strong> × <strong style="color: #ec4899;">人机协作确认</strong>
</p>

<p style="font-family: 'Inter', sans-serif; color: #64748b; max-width: 700px; margin: 1.5rem auto;">
  OpenClaw 等端侧 Agent 框架让手机自动完成填表、发消息、传文件成为现实。<br/>
  <strong>MaskClaw</strong> 是专为这类 Agent 设计的隐私守卫层——在 Agent 执行操作前介入，判断这个动作该不该做、该怎么做，且所有推理全部在设备本地完成，数据不出端。
</p>

</div>

---

## ◈ 核心痛点

端侧 Agent 的自动化能力越强，隐私暴露面就越大。现有保护方案在三个层面上跟不上这个趋势：

| 层级 | 现有方案 | 核心问题 |
|:---:|:---|:---|
| **感知层** | 只认格式，不认意图 | 身份证号、银行卡号这类格式化数据尚可拦截，但 Agent 真正危险的操作往往没有固定格式——把截图发给陌生人、在不该填的地方填了真实住址、把内部文件传到外部平台，靠正则匹配永远发现不了 |
| **适配层** | 只有公共规则，没有个人规则 | 每个人对隐私的边界不一样，同一个字段在不同职业、不同场景下的敏感程度完全不同。现有方案提供的是一套对所有人都适用的最低标准，而不是随用户习惯动态调整的个性化防护 |
| **架构层** | 云端审核本身就是泄露 | 将屏幕内容上传云端做语义判断，在很多行业的合规要求下根本不被允许，在个人用户侧也制造了"为保护隐私先出让隐私"的悖论 |

---

## ◈ 系统架构

### 瘦客户端 + 胖服务端 + Skill-Use 规则调用的微服务解耦架构

MaskClaw 在不改动 AutoGLM、OpenClaw 等第三方 Agent 任何代码的前提下，通过 **Hooking 机制**介入 Agent 的执行链路。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MaskClaw 隐私保护三层架构                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐         ┌─────────────────┐         ┌───────────────┐ │
│   │    感知层        │   →    │    认知层        │   →    │    执行层      │ │
│   │  Perception      │         │   Cognition     │         │  Tool-Use     │ │
│   ├─────────────────┤         ├─────────────────┤         ├───────────────┤ │
│   │                 │         │                 │         │               │ │
│   │  • PaddleOCR    │         │  • MiniCPM-4.5  │         │  • Smart      │ │
│   │    毫秒级格式化  │         │    语义推理     │         │    Masker    │ │
│   │    敏感信息识别  │         │  • ChromaDB     │         │    视觉打码   │ │
│   │                 │         │    RAG 规则检索 │         │               │ │
│   │  • OpenCV       │         │                 │         │  • PII        │ │
│   │    本地视觉     │         │                 │         │    Detection  │ │
│   │    模糊处理     │         │                 │         │    隐私检测   │ │
│   │                 │         │                 │         │               │ │
│   └─────────────────┘         └─────────────────┘         └───────────────┘ │
│          │                          │                          │           │
│          └──────────────────────────┼──────────────────────────┘           │
│                                     ↓                                          │
│                           ┌───────────────────┐                                │
│                           │    自进化闭环      │                                │
│                           │  Self-Evolution   │                                │
│                           ├───────────────────┤                                │
│                           │                   │                                │
│                           │  • Behaviour_     │                                │
│                           │    monitor 行为   │                                │
│                           │    监控捕获       │                                │
│                           │                   │                                │
│                           │  • Skill_evolution│                                │
│                           │    规则抽取生成   │                                │
│                           │                   │                                │
│                           │  • Sandbox 测试   │                                │
│                           │    沙盒回归验证   │                                │
│                           │                   │                                │
│                           └───────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 对第三方 Agent 完全透明

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           传统架构                                      │
│   Agent → 原始截图 → 上传云端 → 隐私泄露风险！                             │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           MaskClaw 架构                                 │
│   Agent → 原始截图 → MaskClaw 拦截 → 端侧脱敏 → 安全数据 → Agent          │
│                         ↑                                                        │
│                    Hooking 介入                                             │
│                   无需修改 Agent 代码                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ◈ 四大核心模块

| 模块 | 功能 | 核心能力 |
|:---|:---|:---|
| **PII Detection** | 隐私信息检测 | 手机号、身份证、银行卡、地址、姓名等格式化信息毫秒级识别 |
| **Smart Masker** | 智能视觉打码 | OpenCV 本地模糊处理、马赛克、高斯模糊、区域覆盖 |
| **Behavior Monitor** | 行为监控 | 持续监听 Agent 行为，捕获用户主动干预（修改填写值、拒绝操作） |
| **Skill Evolution** | 规则自进化 | 从纠错日志中抽取新规则，沙盒测试验证后自动挂载上线 |

---

## ◈ 设计亮点

<details>
<summary><strong>🔒 轻量端侧模型</strong></summary>

<br/>

语义推理由 **MiniCPM-4.5** 承担，9B 参数量在消费级设备上可本地部署。敏感信息识别与视觉模糊处理全部在本地完成，不依赖网络连接，满足医疗、金融等对数据不出本地有强制要求的场景。

</details>

<details>
<summary><strong>🧬 自进化经验库</strong></summary>

<br/>

规则不是人工维护的静态列表，而是从用户真实操作行为中持续抽取、沙盒验证后自动挂载。系统上线时携带通用基础规则集，随使用时间积累逐步收敛到每个用户自己的隐私偏好，**无需用户手动配置任何规则**。

```
用户行为 → 行为日志 → 模式识别 → 规则抽取 → 沙盒测试 → 版本发布
                                                        ↓
                                                  人工审核门禁
```

</details>

<details>
<summary><strong>🤝 人机协作确认</strong></summary>

<br/>

系统对自己的判断有明确的置信度分级：

| 置信状态 | 含义 | 系统行为 |
|:---:|:---|:---|
| **Allow** | 规则库完整匹配，安全 | 直接放行 |
| **Block** | 规则库完整匹配，风险明确 | 直接拦截 |
| **Mask** | 规则库完整匹配，需脱敏 | 执行打码后放行 |
| **Ask** | 规则库信息不完整 | 主动向用户确认 |
| **Unsure** | 规则库完全没有记录的新场景 | 标记并等待用户教授 |

这一机制使系统在冷启动阶段也能保持可用，而不是频繁误报。

</details>

<details>
<summary><strong>🔄 协同过滤</strong></summary>

<br/>

通过对多用户规则的横向聚合，可以在新用户规则库尚未积累完善时，从相似用户群体的经验中提取参考规则，加速个性化收敛过程，缩短冷启动周期。

</details>

<details>
<summary><strong>📊 仿真数据集构建</strong></summary>

<br/>

学术界目前没有带用户个性化反馈的 Agent 隐私操作数据集。MaskClaw 配套构建了 **P-GUI-Evo** 数据集：

| 维度 | 规格 |
|:---|:---|
| 样本规模 | 622 条（已剔除 discard 条目） |
| 用户画像 | 3 类（医疗顾问、带货主播、普通职员） |
| 操作场景 | 6 类真实场景 |
| 泛化变体 | 截图劣化、话术改写、DOM结构扰动 |
| 判决标签 | Allow / Block / Mask / Ask / Unsure |

</details>

---

## ◈ 实效数据

### 数据集架构

| 维度 | 当前情况（实验版） | 说明 |
|:---|:---:|:---|
| 样本规模 | 622 | 已剔除 discard 条目 |
| 用户画像 | 3 类 | 医疗顾问 UserA、带货主播 UserB、普通职员 UserC |
| 分桶 | D1/D2/D3 | 分别对应基础、泛化、噪声/新分布压力 |
| 分桶规模 | D1: 216, D2: 252, D3: 154 | 按最终分桶清单统计 |
| 样本字段 | 截图 + 操作意图 + 金标准判决 + 质量信息 | 支持回溯与分层实验 |
| 判决标签 | Allow/Block/Mask/Ask/Unsure | 与策略执行行为对齐 |

### 预期指标

| 指标 | 评测分桶 | 预期目标 |
|:---|:---:|:---:|
| 规则抽取 F1 | D1 冷启动 | ≥ 0.85 |
| 规则抽取 F1 | D2 泛化 | ≥ 0.75 |
| 判决准确率 | D1 全量 | ≥ 90% |
| 泛化降级率 | D2 vs D1 | ≤ 10% |
| Unsure 召回率 | D3 新分布 | ≥ 80% |
| 逻辑一致性错误率 | D1/D2/D3 全量 | ≤ 5% |
| PII 定位与打码准确率 | D1 全量 | ≥ 90% |

> **为什么设两层评测而不是只看判决准确率？**
> 判决准确率高不代表系统真正学到了规则——可能只是在 D1 上过拟合了场景。规则抽取 F1 衡量的是模型有没有抽出语义正确的规则，判决一致性层衡量的是这条规则能不能泛化到新样本。两层都过才算真正学会。

---

## ◈ 同类方案对比

| 维度 | MaskClaw | Google DLP | Microsoft Presidio | 云端大模型审核 | Agent 框架内置过滤 |
|:---|:---:|:---:|:---:|:---:|:---:|
| **语境感知** | 多条件组合判断 | 格式匹配 | 格式匹配 | 语义理解但需上云 | 无 |
| **个性化规则** | 自动抽取，持续进化 | 静态规则库 | 静态规则库 | 无记忆 | 无 |
| **数据不出端** | 全端侧 | 需联网 | 本地可部署 | 必须上传截图 | 本地 |
| **自进化能力** | 有，用户行为驱动 | 无 | 无 | 无 | 无 |
| **不确定性输出** | Unsure 机制 | 无 | 无 | 无 | 无 |
| **冷启动** | 通用规则集兜底 | 开箱即用 | 开箱即用 | 开箱即用 | 开箱即用 |
| **Agent 集成方式** | Hooking，无需改动上游 | 独立服务，需接入 | 独立服务，需接入 | API调用，需接入 | 框架绑定 |

### 核心差距

1. **现有方案没有一个能同时做到语境感知 + 数据不出端。** 云端大模型在语义理解上能力足够，但上传截图这一步在合规敏感场景下是硬限制；本地方案（Presidio、DLP本地版）可以不出端，但处理不了语义层面的判断。MaskClaw 是目前唯一在端侧完成语义级判断的方案。

2. **没有任何现有方案具备规则自进化能力。** 所有对比方案的规则库都需要人工维护，无法从用户行为中学习。这在 Agent 深度介入用户操作的场景下是根本性缺陷——Agent 的操作空间太大，人工穷举规则不现实。

---

## ◈ 产学研赋能

MaskClaw 的架构天然适合作为独立中间件嵌入现有产品线，不要求上游改造。

### 可嵌入的产品方向

| 方向 | 场景描述 |
|:---|:---|
| 📱 手机厂商系统级 Agent | 作为系统服务常驻（小艺、小布等），对所有第三方 Agent 统一兜底，厂商无需逐一适配 |
| 💼 企业移动办公套件 | 钉钉、飞书插件层，防止内部敏感信息经由 Agent 流出企业边界 |
| 🏥 医疗、金融终端设备 | 数据不出端的架构天然满足行业合规要求，可作为现有 DLP 方案的语义增强层叠加部署 |

### 数据资产的独立价值

**P-GUI-Evo 数据集**覆盖六类真实操作场景、三类用户画像、三种泛化变体构建方式，是目前唯一面向 Agent 隐私操作评测的合成数据集，可独立授权给隐私合规产品作为评测基准使用。

---

## ◈ 项目结构

```text
MaskClaw/
├── api_server.py                 # FastAPI HTTP 服务 (端口 8001)
│
├── model_server/
│   ├── minicpm_api.py            # MiniCPM-V 视觉模型 API (端口 8000)
│   └── requirements.txt          # 模型服务依赖
│
├── frontend/
│   └── ui-app/                   # React 前端应用
│
├── models/                       # 模型文件目录
│   └── OpenBMB/
│       └── MiniCPM-V-4_5/        # 视觉理解模型 (~16.5GB)
│
├── skills/                       # Skills 模块
│   ├── smart_masker.py           # 视觉打码模块
│   ├── behavior_monitor.py       # 行为监控模块
│   └── evolution_mechanic.py     # 自进化机制
│
├── memory/                       # 记忆存储
│   ├── chroma_manager.py         # ChromaDB 管理器
│   └── chroma_storage/            # ChromaDB 数据库文件
│
├── prompts/                     # Prompt 模板
│
├── docs/                        # 架构文档
│   ├── ARCHITECTURE.md          # 系统架构文档
│   ├── SKILLS_API.md           # Skills API 文档
│   ├── RAG_SCHEMA.md           # RAG 数据模式
│   └── PROMPT_TEMPLATES.md     # Prompt 模板文档
│
├── sandbox/                     # 沙盒测试目录
│
├── autoglm_server.py            # Windows 端 AutoGLM 服务
├── demo.py                      # API 测试演示脚本
├── requirements.txt             # Python 依赖列表
├── README.md                    # 本文件
└── AGENTS.md                   # Agent 行为约束文档
```

---

## ◈ 快速开始

<details>
<summary><strong>1. 安装依赖</strong></summary>

```bash
# Python 依赖
pip install chromadb rapidocr-onnxrunner onnxruntime pillow opencv-python fastapi uvicorn requests transformers>=4.51.0 torch

# 前端依赖
cd frontend/ui-app
npm install
```

</details>

<details>
<summary><strong>2. 启动模型服务 (端口 8000)</strong></summary>

```bash
cd model_server
python minicpm_api.py
```

</details>

<details>
<summary><strong>3. 启动隐私代理服务 (端口 8001)</strong></summary>

```bash
python api_server.py
```

</details>

<details>
<summary><strong>4. 验证服务</strong></summary>

```bash
curl http://127.0.0.1:8001/
```

</details>

<details>
<summary><strong>5. 重启服务（如需）</strong></summary>

```bash
kill <PID>  # 杀掉旧进程
python api_server.py
```

</details>

<details>
<summary><strong>6. 启动前端应用</strong></summary>

```bash
cd frontend/ui-app
npm run dev
```

</details>

</details>

<details>
<summary><strong>7. Windows 本地开发</strong></summary>

```bash
# 激活环境
conda activate autoglm

# 启动 AutoGLM 服务
python autoglm_server.py

# 关闭 SSH
taskkill /f /im ssh.exe
```

</details>

---

## ◈ SSH 端口映射

<details>
<summary><strong>方式一：单端口映射</strong></summary>

```bash
ssh -L 8001:127.0.0.1:8001 root@connect.bjb1.seetacloud.com -N
```

</details>

<details>
<summary><strong>方式二：双端口完整映射</strong></summary>

```bash
# Windows 命令行 1 - 映射 8001 端口
ssh -L 9001:127.0.0.1:8001 root@connect.bjb1.seetacloud.com -p 36647 -N

# Windows 命令行 2 - 映射 28080 端口
ssh -R 28080:127.0.0.1:28080 root@connect.bjb1.seetacloud.com -p 36647 -N
```

</details>

---

## ◈ API 接口

### 健康检查

```bash
# 隐私代理服务
curl http://localhost:8001/

# MiniCPM 视觉模型
curl -X POST http://localhost:8000/chat -F "prompt=hello"
```

### 处理截图（返回脱敏图片）

```bash
curl -X POST http://localhost:8001/process \
  -F "image=@test.jpg" \
  -F "command=分析当前页面隐私" \
  -o output.jpg
```

### 规则管理

```bash
# 查看所有规则
curl http://localhost:8001/rules

# 添加新规则
curl -X POST http://localhost:8001/rules \
  -H "Content-Type: application/json" \
  -d '{
    "scenario": "账号注册页",
    "target_field": "手机号",
    "document": "禁止填写真实手机号",
    "skill": "Visual_Obfuscation_Skill"
  }'
```

---

## ◈ 文档索引

| 文档 | 内容说明 |
|:---|:---|
| [系统架构](docs/ARCHITECTURE.md) | 了解系统整体设计与端云协同架构 |
| [Skills API](docs/SKILLS_API.md) | 四大核心 Skills 的输入输出契约 |
| [RAG 数据模式](docs/RAG_SCHEMA.md) | ChromaDB 向量数据库的存储范式 |
| [Prompt 模板](docs/PROMPT_TEMPLATES.md) | 端侧 LLM 推理与代码生成的模板 |
| [Agent 行为约束](AGENTS.md) | LLM 调度 Skills 的核心原则 |

---

## ◈ 故障排查

<details>
<summary><strong>常见问题</strong></summary>

<br/>

**端口被占用**

```bash
lsof -i :8001
kill -9 <PID>
```

**模型文件缺失**

确保已将 MiniCPM-V-4_5 模型文件放置在 `models/OpenBMB/MiniCPM-V-4_5/` 目录。

**前端启动失败**

```bash
cd frontend/ui-app
rm -rf node_modules package-lock.json
npm install
```

</details>

---

## ◈ 伦理声明

<details>
<summary><strong>请在引用、部署或二次开发前阅读</strong></summary>

- 本项目面向隐私保护、风险识别与产品安全治理，不用于法律意义上的身份认证
- 基于对话内容的隐私判断本质上是概率推断，而非身份事实确认
- 项目不鼓励将模型输出直接用于惩罚性、歧视性或不可申诉的自动化决策
- 涉及高风险处置、模式切换、账号限制时，应保留人工复核与申诉机制
- 数据处理遵循最小化原则，只在必要时进行脱敏处理

</details>

---

<div align="center">

**🔗 GitHub**: [https://github.com/Theodora-Y/MaskClaw](https://github.com/Theodora-Y/MaskClaw)

</div>

---

## 引用

```bibtex
@misc{maskclaw_github_2026,
  title        = {MaskClaw: On-device Privacy-Preserving Framework with Self-Evolving Rule Extraction for Agent Systems},
  author       = {MaskClaw Team},
  year         = {2026},
  howpublished = {https://github.com/Theodora-Y/MaskClaw},
  note         = {GitHub repository}
}
```

<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

<style>
  /* ========================================
     MaskClaw README Custom Styles
     ======================================== */

  :root {
    --primary: #6366f1;
    --primary-dark: #4f46e5;
    --secondary: #8b5cf6;
    --accent: #ec4899;
    --accent2: #06b6d4;
    --bg-dark: #0f172a;
    --bg-card: #1e293b;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --border: #334155;
    --gradient-primary: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
    --gradient-accent: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  }

  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(180deg, var(--bg-dark) 0%, #1a1a2e 100%);
    color: var(--text-primary);
    line-height: 1.7;
  }

  /* Logo Area */
  .logo-area {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.1) 50%, rgba(236, 72, 153, 0.1) 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 24px;
    padding: 3rem 2rem;
    margin-bottom: 2rem;
    text-align: center;
  }

  .logo-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 4.5em;
    font-weight: 900;
    letter-spacing: 0.12em;
    background: var(--gradient-primary);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    text-shadow: 0 0 60px rgba(102, 126, 234, 0.5);
  }

  .logo-subtitle {
    font-size: 1.25em;
    color: var(--text-secondary);
    margin-top: 1rem;
    font-weight: 400;
  }

  /* Badges */
  .badge-row {
    display: flex;
    justify-content: center;
    gap: 0.75rem;
    margin: 1.5rem 0;
    flex-wrap: wrap;
  }

  .badge {
    padding: 0.5rem 1rem;
    border-radius: 50px;
    font-size: 0.85em;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }

  /* Cards */
  .feature-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.5rem;
    margin: 1rem 0;
    transition: all 0.3s ease;
  }

  .feature-card:hover {
    border-color: var(--primary);
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(99, 102, 241, 0.15);
  }

  /* Module Grid */
  .module-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0;
  }

  .module-item {
    background: linear-gradient(145deg, var(--bg-card) 0%, rgba(99, 102, 241, 0.08) 100%);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.75rem;
    position: relative;
    overflow: hidden;
  }

  .module-item::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--gradient-primary);
  }

  .module-icon {
    font-size: 2.5rem;
    margin-bottom: 1rem;
  }

  .module-title {
    font-size: 1.1em;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 0.75rem;
  }

  .module-desc {
    font-size: 0.9em;
    color: var(--text-secondary);
    line-height: 1.6;
  }

  /* Comparison Table */
  .comparison-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 1.5rem 0;
    border-radius: 12px;
    overflow: hidden;
  }

  .comparison-table th {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(139, 92, 246, 0.2) 100%);
    padding: 1rem;
    text-align: left;
    font-weight: 600;
    border-bottom: 2px solid var(--border);
  }

  .comparison-table td {
    padding: 0.85rem 1rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.9em;
  }

  .comparison-table tr:hover td {
    background: rgba(99, 102, 241, 0.05);
  }

  .highlight-cell {
    color: #34d399;
    font-weight: 600;
  }

  /* Architecture Diagram */
  .arch-container {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 2rem;
    margin: 2rem 0;
    overflow-x: auto;
  }

  .arch-title {
    text-align: center;
    font-family: 'Orbitron', sans-serif;
    font-size: 1.5em;
    font-weight: 700;
    margin-bottom: 1.5rem;
    background: var(--gradient-primary);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  /* Flow Diagram */
  .flow-container {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    padding: 1rem 0;
  }

  .flow-item {
    background: linear-gradient(145deg, var(--bg-card) 0%, rgba(139, 92, 246, 0.15) 100%);
    border: 1px solid var(--secondary);
    border-radius: 10px;
    padding: 0.6rem 1.2rem;
    font-size: 0.85em;
    font-weight: 500;
    color: var(--text-primary);
  }

  .flow-arrow {
    color: var(--secondary);
    font-size: 1.2em;
    font-weight: bold;
  }

  /* Pain Point Cards */
  .pain-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.5rem;
    margin: 2rem 0;
  }

  @media (max-width: 768px) {
    .pain-grid {
      grid-template-columns: 1fr;
    }
  }

  .pain-card {
    background: linear-gradient(145deg, var(--bg-card) 0%, rgba(239, 68, 68, 0.08) 100%);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 16px;
    padding: 1.5rem;
    position: relative;
  }

  .pain-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #ef4444, #f97316);
  }

  .pain-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }

  .pain-icon {
    font-size: 1.5rem;
  }

  .pain-title {
    font-weight: 700;
    font-size: 1em;
    color: #fca5a5;
  }

  /* Confidence Level Cards */
  .confidence-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
  }

  @media (max-width: 900px) {
    .confidence-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .confidence-item {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem;
    text-align: center;
    transition: all 0.3s ease;
  }

  .confidence-item:hover {
    transform: scale(1.03);
  }

  .confidence-badge {
    display: inline-block;
    padding: 0.35rem 0.8rem;
    border-radius: 50px;
    font-size: 0.75em;
    font-weight: 700;
    margin-bottom: 0.75rem;
  }

  .confidence-allow { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
  .confidence-block { background: rgba(239, 68, 68, 0.2); color: #f87171; }
  .confidence-mask { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
  .confidence-ask { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
  .confidence-unsure { background: rgba(139, 92, 246, 0.2); color: #a78bfa; }

  /* Metrics Section */
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
  }

  @media (max-width: 900px) {
    .metrics-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  .metric-card {
    background: linear-gradient(145deg, var(--bg-card) 0%, rgba(6, 182, 212, 0.08) 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
  }

  .metric-value {
    font-family: 'Orbitron', sans-serif;
    font-size: 2em;
    font-weight: 800;
    background: linear-gradient(135deg, #06b6d4, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .metric-label {
    font-size: 0.85em;
    color: var(--text-secondary);
    margin-top: 0.5rem;
  }

  /* Quick Start Steps */
  .step-list {
    counter-reset: step;
    list-style: none;
    padding: 0;
    margin: 1.5rem 0;
  }

  .step-item {
    position: relative;
    padding-left: 3.5rem;
    margin-bottom: 1.5rem;
  }

  .step-item::before {
    counter-increment: step;
    content: counter(step);
    position: absolute;
    left: 0;
    top: 0;
    width: 2.5rem;
    height: 2.5rem;
    background: var(--gradient-primary);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Orbitron', sans-serif;
    font-weight: 700;
    font-size: 0.9em;
  }

  .step-title {
    font-weight: 600;
    font-size: 1.05em;
    margin-bottom: 0.5rem;
    color: var(--text-primary);
  }

  .step-desc {
    color: var(--text-secondary);
    font-size: 0.9em;
  }

  /* Code Block Styling */
  code {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    background: rgba(99, 102, 241, 0.15);
    padding: 0.2em 0.5em;
    border-radius: 6px;
    font-size: 0.88em;
  }

  pre {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem;
    overflow-x: auto;
    margin: 1rem 0;
  }

  pre code {
    background: none;
    padding: 0;
  }

  /* Section Headers */
  h1 {
    font-family: 'Orbitron', sans-serif;
  }

  h2 {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.8em;
    font-weight: 700;
    margin-top: 3rem;
    margin-bottom: 1.5rem;
    padding-bottom: 0.75rem;
    border-bottom: 2px solid var(--border);
  }

  h3 {
    font-size: 1.25em;
    font-weight: 600;
    margin-top: 1.5rem;
    color: var(--secondary);
  }

  h4 {
    font-size: 1.05em;
    font-weight: 600;
    margin-top: 1.25rem;
  }

  /* TOC */
  .toc {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem 2rem;
    margin: 2rem 0;
  }

  .toc-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.1em;
    font-weight: 600;
    margin-bottom: 1rem;
    color: var(--secondary);
  }

  .toc-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 0.5rem;
  }

  .toc-item {
    padding: 0.5rem 0;
  }

  .toc-link {
    color: var(--text-secondary);
    text-decoration: none;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .toc-link:hover {
    color: var(--primary);
    transform: translateX(4px);
  }

  /* Footer */
  .footer {
    text-align: center;
    padding: 2rem 0;
    margin-top: 3rem;
    border-top: 1px solid var(--border);
    color: var(--text-secondary);
  }

  /* Divider */
  .section-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border), transparent);
    margin: 3rem 0;
  }
</style>

<div align="center">

  <!-- Logo Area -->
  <div class="logo-area">
    <img src="docs/assets.md/logo.png" width="100%" alt="MaskClaw Logo" />
    <p class="logo-subtitle">基于端侧模型自进化规则抽取的个性化隐私保护框架</p>
  </div>

  <!-- Badges -->
  <div class="badge-row">
    <span class="badge" style="background: rgba(99, 102, 241, 0.2); color: #818cf8;">
      Python 3.10+
    </span>
    <span class="badge" style="background: rgba(255, 107, 107, 0.2); color: #f87171;">
      MiniCPM-V 4.5
    </span>
    <span class="badge" style="background: rgba(0, 150, 136, 0.2); color: #2dd4bf;">
      FastAPI
    </span>
    <span class="badge" style="background: rgba(94, 53, 177, 0.2); color: #a78bfa;">
      ChromaDB RAG
    </span>
    <span class="badge" style="background: rgba(34, 197, 94, 0.2); color: #4ade80;">
      MIT License
    </span>
    <span class="badge" style="background: rgba(6, 182, 212, 0.2); color: #22d3ee;">
      数据不出端
    </span>
  </div>

  <!-- Core Slogan -->
  <p style="max-width: 750px; margin: 1.5rem auto; color: var(--text-secondary); font-size: 1.05em; line-height: 1.8;">
    OpenClaw 等端侧 Agent 框架让手机自动完成填表、发消息、传文件成为现实。
    <strong style="color: var(--primary);">MaskClaw</strong> 是专为这类 Agent 设计的隐私守卫层——
    在 Agent 执行操作前介入，判断这个动作该不该做、该怎么做，且所有推理全部在设备本地完成，
    <strong style="color: var(--accent);">数据不出端</strong>。
  </p>

</div>

---

## 📑 目录

<div class="toc">
  <div class="toc-title">内容导航</div>
  <ul class="toc-list">
    <li class="toc-item"><a class="toc-link" href="#overview">📖 项目概述</a></li>
    <li class="toc-item"><a class="toc-link" href="#pain-points">🎯 核心痛点</a></li>
    <li class="toc-item"><a class="toc-link" href="#architecture">🏗️ 系统架构</a></li>
    <li class="toc-item"><a class="toc-link" href="#modules">🧩 三大核心模块</a></li>
    <li class="toc-item"><a class="toc-link" href="#features">✨ 设计亮点</a></li>
    <li class="toc-item"><a class="toc-link" href="#data">📊 实效数据</a></li>
    <li class="toc-item"><a class="toc-link" href="#comparison">⚔️ 同类对比</a></li>
    <li class="toc-item"><a class="toc-link" href="#scenarios">💡 赋能场景</a></li>
    <li class="toc-item"><a class="toc-link" href="#structure">📂 项目结构</a></li>
    <li class="toc-item"><a class="toc-link" href="#quickstart">🚀 快速开始</a></li>
    <li class="toc-item"><a class="toc-link" href="#api">🔌 API 接口</a></li>
    <li class="toc-item"><a class="toc-link" href="#docs">📚 文档索引</a></li>
    <li class="toc-item"><a class="toc-link" href="#ethics">⚖️ 伦理声明</a></li>
  </ul>
</div>

---

<a id="overview"></a>
## 📖 项目概述

**MaskClaw** 是一个面向**端侧 Agent 隐私保护**的**自进化规则抽取框架**。它并非传统的数据加密或内容过滤工具，而是在 Agent 执行操作前进行**过程内调节**：识别敏感信息、判断操作风险、智能脱敏，并随用户行为反馈持续优化防护策略。

<div align="center">
  <img src="docs/assets.md/架构图.png" width="85%" alt="MaskClaw 架构图" />
</div>

在 MaskClaw 中，**三类核心模块分工协作**，模拟现实中的隐私守护者角色，协同完成**视觉脱敏、行为监控、规则进化**等任务。框架内置**检索增强的认知机制（规则知识库 + 行为记忆）**，并通过**基于反馈的进化式学习**，使系统能够随使用积累自适应优化干预策略。

### 🎯 核心价值

| 价值维度 | 描述 |
|:---|:---|
| 🔒 **隐私安全保障** | 敏感数据在端侧处理，不上传云端，满足医疗、金融等行业合规要求 |
| 🧬 **个性化自适应** | 规则从用户真实行为中持续抽取，贴合个人隐私偏好 |
| 🤝 **人机协作确认** | 明确的置信度分级，Unsure 机制确保冷启动可用 |
| 🔄 **自进化能力** | 用户行为驱动规则更新，系统越用越懂用户 |

---

<a id="pain-points"></a>
## 🎯 我们试图解决的问题

端侧 Agent 的自动化能力越强，隐私暴露面就越大。现有保护方案在三个层面上跟不上这个趋势：

<div class="pain-grid">
  <div class="pain-card">
    <div class="pain-header">
      <span class="pain-icon">🔍</span>
      <span class="pain-title">感知层：只认格式，不认意图</span>
    </div>
    <p class="module-desc">
      身份证号、银行卡号这类格式化数据，现有工具尚可拦截。但 Agent 真正危险的操作往往没有固定格式——
      把截图发给陌生人、在不该填的地方填了真实住址、把内部文件传到外部平台。
      <strong style="color: #fca5a5;">这类行为靠正则匹配永远发现不了。</strong>
    </p>
  </div>

  <div class="pain-card">
    <div class="pain-header">
      <span class="pain-icon">👤</span>
      <span class="pain-title">适配层：只有公共规则，没有个人规则</span>
    </div>
    <p class="module-desc">
      每个人对隐私的边界不一样，同一个字段在不同职业、不同场景下的敏感程度完全不同。
      现有方案提供的是一套对所有人都适用的最低标准，而不是随用户习惯动态调整的个性化防护。
      <strong style="color: #fca5a5;">规则僵化，无法因人而异。</strong>
    </p>
  </div>

  <div class="pain-card">
    <div class="pain-header">
      <span class="pain-icon">☁️</span>
      <span class="pain-title">架构层：云端审核本身就是泄露</span>
    </div>
    <p class="module-desc">
      将屏幕内容上传云端做语义判断，在很多行业的合规要求下根本不被允许，在个人用户侧也制造了
      "为保护隐私先出让隐私"的悖论。
      <strong style="color: #fca5a5;">数据上传云端，合规场景无法落地。</strong>
    </p>
  </div>
</div>

---

<a id="architecture"></a>
## 🏗️ 系统架构

### 瘦客户端 + 胖服务端 + Skill-Use 规则调度的微服务解耦架构

MaskClaw 在不改动 AutoGLM、OpenClaw 等第三方 Agent 任何代码的前提下，通过 **Hooking 机制**介入 Agent 的执行链路。

<div class="arch-container">
  <div class="arch-title">🛡️ MaskClaw 三层拦截引擎</div>

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   ╔═══════════════════════════════════════════════════════════════════╗   │
│   ║                        MASKCLAW 隐私保护架构                          ║   │
│   ╚═══════════════════════════════════════════════════════════════════╝   │
│                                                                             │
│   ┌─────────────────┐         ┌─────────────────┐         ┌───────────────┐ │
│   ║   LAYER 1       ║   →    ║   LAYER 2       ║   →    ║   LAYER 3     ║ │
│   ║   感知层        ║         ║   认知层        ║         ║   执行层      ║ │
│   ║   Perception    ║         ║   Cognition    ║         ║   Tool-Use   ║ │
│   ├─────────────────┤         ├─────────────────┤         ├───────────────┤ │
│   ║                 ║         ║                 ║         ║               ║ │
│   ║  📋 PaddleOCR   ║         ║  🧠 MiniCPM-4.5 ║         ║  🎭 Smart    ║ │
│   ║     毫秒级格式  ║         ║    语义推理     ║         ║    Masker    ║ │
│   ║     敏感识别    ║         ║                 ║         ║    视觉打码   ║ │
│   ║                 ║         ║  📚 ChromaDB    ║         ║               ║ │
│   ║  🎨 OpenCV      ║         ║    RAG 规则检索 ║         ║  👁️ PII      ║ │
│   ║     本地视觉    ║         ║                 ║         ║    Detection  ║ │
│   ║     模糊处理    ║         ║  🎯 场景匹配    ║         ║    隐私检测   ║ │
│   ║                 ║         ║  ⚡ Skill 调度   ║         ║               ║ │
│   └─────────────────┘         └─────────────────┘         └───────────────┘ │
│          │                          │                          │           │
│          └──────────────────────────┼──────────────────────────┘           │
│                                     ↓                                          │
│                           ┌───────────────────┐                                │
│                           ║   LAYER 4         ║                                │
│                           ║   进化层          ║                                │
│                           ║   Self-Evolution ║                                │
│                           ├───────────────────┤                                │
│                           ║                   ║                                │
│                           ║  📊 Behaviour_    ║                                │
│                           ║     monitor      ║                                │
│                           ║     行为监控捕获  ║                                │
│                           ║                   ║                                │
│                           ║  🧬 Skill_evolution║                               │
│                           ║     规则抽取生成  ║                                │
│                           ║                   ║                                │
│                           ║  🔬 Sandbox 测试  ║                                │
│                           ║     沙盒回归验证  ║                                │
│                           ║                   ║                                │
│                           └───────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────┘
```
</div>

### 🔄 工作流程

<div class="flow-container">
  <span class="flow-item">📸 端侧截图</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">🔍 PII 检测</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">🧠 RAG 检索</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">⚖️ 风险判决</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">🎭 视觉脱敏</span>
  <span class="flow-arrow">→</span>
  <span class="flow-item">✅ 安全转发</span>
</div>

### 🛡️ 对第三方 Agent 完全透明

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         传统架构：数据泄露风险                            │
│                                                                         │
│    Agent ──→ 原始截图 ──→ 上传云端 ──→ 🔴 隐私泄露！                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         MaskClaw 架构：安全闭环                          │
│                                                                         │
│    Agent ──→ 原始截图 ──→ MaskClaw ──→ 端侧脱敏 ──→ 安全数据 ──→ Agent    │
│                       ↗️                                                 │
│                  Hooking 介入                                             │
│                 无需修改 Agent 代码                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

<a id="modules"></a>
## 🧩 三大核心模块

<div class="module-grid">
  <div class="module-item">
    <div class="module-icon">🎭</div>
    <div class="module-title">Smart Masker</div>
    <div class="module-desc">
      智能视觉打码模块，基于 RapidOCR 识别图片中的敏感文本区域并进行本地脱敏处理。
      支持高斯模糊、马赛克、色块覆盖等多种打码方式，数据全程不出端。
    </div>
  </div>

  <div class="module-item">
    <div class="module-icon">📊</div>
    <div class="module-title">Behavior Monitor</div>
    <div class="module-desc">
      行为监控模块，持续监听 Agent 操作行为，捕获用户主动干预动作。
      包括修改填写值、拒绝某次操作等修正行为，为规则进化提供数据基础。
    </div>
  </div>

  <div class="module-item">
    <div class="module-icon">🧬</div>
    <div class="module-title">Skill Evolution</div>
    <div class="module-desc">
      规则自进化模块，基于爬山法从纠错日志中持续优化 SOP。
      经沙盒测试验证后自动挂载上线，系统越用越懂用户的个人隐私边界。
    </div>
  </div>
</div>

---

<a id="features"></a>
## ✨ 设计亮点

<details>
<summary><strong>🔒 轻量端侧模型 — 数据不出端的硬核保障</strong></summary>

<br/>

语义推理由 **MiniCPM-4.5** 承担，9B 参数量在消费级设备上可本地部署。敏感信息识别与视觉模糊处理全部在本地完成，不依赖网络连接，满足医疗、金融等对数据不出本地有强制要求的场景。

| 组件 | 技术选型 | 优势 |
|:---|:---|:---|
| 视觉模型 | MiniCPM-4.5 (9B) | 端侧可部署，语义理解强 |
| OCR 引擎 | RapidOCR | 高性能毫秒级文本识别 |
| 脱敏处理 | OpenCV | 本地视觉处理，零上传 |
| 规则检索 | ChromaDB | 高效向量相似度检索 |

</details>

<details>
<summary><strong>🧬 自进化经验库 — 规则从用户行为中生长</strong></summary>

<br/>

规则不是人工维护的静态列表，而是从用户真实操作行为中持续抽取、沙盒验证后自动挂载。系统上线时携带通用基础规则集，随使用时间积累逐步收敛到每个用户自己的隐私偏好，**无需用户手动配置任何规则**。

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  用户行为   │ → │  行为日志   │ → │  模式识别   │ → │  规则抽取   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                ↓
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  版本发布   │ ← │  人工审核   │ ← │  沙盒测试   │ ← │  规则生成   │
│  自动上线   │    │  最终门禁   │    │  回归验证   │    │  智能生成   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

</details>

<details>
<summary><strong>🤝 人机协作确认 — 五级置信度智能判决</strong></summary>

<br/>

系统对自己的判断有明确的置信度分级，不同状态下采取不同策略：

<div class="confidence-grid">
  <div class="confidence-item">
    <span class="confidence-badge confidence-allow">Allow</span>
    <div class="module-desc">规则库完整匹配，安全操作，直接放行</div>
  </div>
  <div class="confidence-item">
    <span class="confidence-badge confidence-block">Block</span>
    <div class="module-desc">规则库完整匹配，风险明确，直接拦截</div>
  </div>
  <div class="confidence-item">
    <span class="confidence-badge confidence-mask">Mask</span>
    <div class="module-desc">规则库完整匹配，需脱敏，执行打码后放行</div>
  </div>
  <div class="confidence-item">
    <span class="confidence-badge confidence-ask">Ask</span>
    <div class="module-desc">规则库信息不完整，主动向用户确认</div>
  </div>
  <div class="confidence-item">
    <span class="confidence-badge confidence-unsure">Unsure</span>
    <div class="module-desc">新场景无记录，标记并等待用户教授</div>
  </div>
</div>

> 💡 **这一机制使系统在冷启动阶段也能保持可用**，而不是频繁误报或漏报。

</details>

<details>
<summary><strong>🔄 协同过滤 — 群体智慧加速个性化收敛</strong></summary>

<br/>

通过对多用户规则的横向聚合，可以在新用户规则库尚未积累完善时，从相似用户群体的经验中提取参考规则，加速个性化收敛过程，缩短冷启动周期。

| 用户阶段 | 规则来源 | 效果 |
|:---|:---|:---|
| 冷启动 | 通用基础规则集 | 开箱即用 |
| 早期积累 | 相似用户群协同过滤 | 快速收敛 |
| 稳定期 | 个人行为自进化 | 精准个性化 |

</details>

<details>
<summary><strong>📊 P-GUI-Evo 数据集 — 业界首个 Agent 隐私评测基准</strong></summary>

<br/>

学术界目前没有带用户个性化反馈的 Agent 隐私操作数据集。MaskClaw 配套构建了 **P-GUI-Evo** 数据集：

| 维度 | 规格 |
|:---|:---|
| 📦 样本规模 | 622 条（已剔除 discard 条目） |
| 👤 用户画像 | 3 类（医疗顾问、带货主播、普通职员） |
| 🎬 操作场景 | 6 类真实场景 |
| 🔄 泛化变体 | 截图劣化、话术改写、DOM结构扰动 |
| 🏷️ 判决标签 | Allow / Block / Mask / Ask / Unsure |

</details>

---

<a id="data"></a>
## 📊 实效数据

### 数据集架构

| 维度 | 当前情况（实验版） | 说明 |
|:---|:---:|:---|
| 样本规模 | 622 | 已剔除 discard 条目 |
| 用户画像 | 3 类 | 医疗顾问 UserA、带货主播 UserB、普通职员 UserC |
| 分桶 | D1/D2/D3 | 分别对应基础、泛化、噪声/新分布压力 |
| 分桶规模 | D1: 216, D2: 252, D3: 154 | 按最终分桶清单统计 |
| 样本字段 | 截图 + 操作意图 + 金标准判决 + 质量信息 | 支持回溯与分层实验 |
| 判决标签 | Allow/Block/Mask/Ask/Unsure | 与策略执行行为对齐 |

### 预期性能指标

<div class="metrics-grid">
  <div class="metric-card">
    <div class="metric-value">≥0.85</div>
    <div class="metric-label">D1 规则抽取 F1</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">≥90%</div>
    <div class="metric-label">D1 判决准确率</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">≤10%</div>
    <div class="metric-label">D2 泛化降级率</div>
  </div>
  <div class="metric-card">
    <div class="metric-value">≥80%</div>
    <div class="metric-label">D3 Unsure 召回率</div>
  </div>
</div>

> **📌 为什么设两层评测？** 判决准确率高不代表系统真正学到了规则——可能只是在 D1 上过拟合了场景。
> 规则抽取 F1 衡量的是模型有没有抽出语义正确的规则，判决一致性层衡量的是这条规则能不能泛化到新样本。
> 两层都过才算真正学会。

---

<a id="comparison"></a>
## ⚔️ 同类方案对比

| 维度 | MaskClaw | Google DLP | Microsoft Presidio | 云端大模型审核 | Agent 框架内置 |
|:---|:---:|:---:|:---:|:---:|:---:|
| **语境感知** | 🟢 多条件组合判断 | 🔴 格式匹配 | 🔴 格式匹配 | 🟡 语义理解但需上云 | 🔴 无 |
| **个性化规则** | 🟢 自动抽取持续进化 | 🔴 静态规则库 | 🔴 静态规则库 | 🔴 无记忆 | 🔴 无 |
| **数据不出端** | 🟢 **全端侧** | 🔴 需联网 | 🟢 本地可部署 | 🔴 必须上传截图 | 🟢 本地 |
| **自进化能力** | 🟢 **有，用户行为驱动** | 🔴 无 | 🔴 无 | 🔴 无 | 🔴 无 |
| **不确定性输出** | 🟢 **Unsure 机制** | 🔴 无 | 🔴 无 | 🔴 无 | 🔴 无 |
| **冷启动** | 🟡 通用规则集兜底 | 🟢 开箱即用 | 🟢 开箱即用 | 🟢 开箱即用 | 🟢 开箱即用 |
| **Agent 集成** | 🟢 **Hooking 零改造** | 🟡 独立服务需接入 | 🟡 独立服务需接入 | 🟡 API调用需接入 | 🔴 框架绑定 |

### 核心差距

1. **现有方案没有一个能同时做到语境感知 + 数据不出端。** 云端大模型在语义理解上能力足够，但上传截图这一步在合规敏感场景下是硬限制；本地方案（Presidio、DLP本地版）可以不出端，但处理不了语义层面的判断。**MaskClaw 是目前唯一在端侧完成语义级判断的方案。**

2. **没有任何现有方案具备规则自进化能力。** 所有对比方案的规则库都需要人工维护，无法从用户行为中学习。这在 Agent 深度介入用户操作的场景下是根本性缺陷——Agent 的操作空间太大，人工穷举规则不现实。

---

<a id="scenarios"></a>
## 💡 产学研赋能

MaskClaw 的架构天然适合作为独立中间件嵌入现有产品线，不要求上游改造。

### 可嵌入的产品方向

| 方向 | 场景描述 | 核心价值 |
|:---|:---|:---|
| 📱 手机厂商系统级 Agent | 小艺、小布等系统服务常驻 | 对所有第三方 Agent 统一兜底，无需逐一适配 |
| 💼 企业移动办公套件 | 钉钉、飞书插件层 | 防止内部敏感信息经由 Agent 流出企业边界 |
| 🏥 医疗、金融终端设备 | 行业合规敏感场景 | 数据不出端架构满足行业强制要求，可作为 DLP 语义增强层 |

### 数据资产的独立价值

**P-GUI-Evo 数据集**覆盖六类真实操作场景、三类用户画像、三种泛化变体构建方式，是目前唯一面向 Agent 隐私操作评测的合成数据集，可独立授权给隐私合规产品作为评测基准使用。

---

<a id="structure"></a>
## 📂 项目结构

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
│   ├── smart_masker.py           # 🎭 视觉打码模块
│   ├── behavior_monitor.py       # 📊 行为监控模块
│   └── evolution_mechanic.py    # 🧬 自进化机制
│
├── memory/                       # 记忆存储
│   ├── chroma_manager.py         # ChromaDB 管理器
│   └── chroma_storage/           # ChromaDB 数据库文件
│
├── prompts/                     # Prompt 模板
│
├── docs/                        # 架构文档
│   ├── ARCHITECTURE.md         # 系统架构文档
│   ├── SKILLS_API.md          # Skills API 文档
│   ├── RAG_SCHEMA.md          # RAG 数据模式
│   └── PROMPT_TEMPLATES.md    # Prompt 模板文档
│
├── sandbox/                    # 沙盒测试目录
│
├── docs/assets.md/            # 📷 项目资源文件 (logo, 架构图等)
│
├── autoglm_server.py          # Windows 端 AutoGLM 服务
├── demo.py                    # API 测试演示脚本
├── requirements.txt           # Python 依赖列表
├── README.md                  # 本文件
└── AGENTS.md                  # Agent 行为约束文档
```

---

<a id="quickstart"></a>
## 🚀 快速开始

### 1️⃣ 安装依赖

```bash
# Python 依赖
pip install chromadb rapidocr-onnxrunner onnxruntime pillow opencv-python \
            fastapi uvicorn requests transformers>=4.51.0 torch

# 前端依赖
cd frontend/ui-app
npm install
```

### 2️⃣ 启动模型服务 (端口 8000)

```bash
cd model_server
python minicpm_api.py
```

### 3️⃣ 启动隐私代理服务 (端口 8001)

```bash
python api_server.py
```

### 4️⃣ 验证服务状态

```bash
curl http://127.0.0.1:8001/
```

### 5️⃣ 重启服务（如需）

```bash
kill <PID>  # 杀掉旧进程
python api_server.py
```

### 6️⃣ 启动前端应用

```bash
cd frontend/ui-app
npm run dev
```

### 7️⃣ Windows 本地开发

```bash
# 激活 conda 环境
conda activate autoglm

# 启动 AutoGLM 服务
python autoglm_server.py

# 关闭 SSH 连接
taskkill /f /im ssh.exe
```

### 8️⃣ SSH 端口映射

**方式一：单端口映射**
```bash
ssh -L 8001:127.0.0.1:8001 root@connect.bjb1.seetacloud.com -N
```

**方式二：双端口完整映射**
```bash
# Windows 命令行 1 - 映射 8001 端口
ssh -L 9001:127.0.0.1:8001 root@connect.bjb1.seetacloud.com -p 36647 -N

# Windows 命令行 2 - 映射 28080 端口
ssh -R 28080:127.0.0.1:28080 root@connect.bjb1.seetacloud.com -p 36647 -N
```

---

<a id="api"></a>
## 🔌 API 接口

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
    "skill": "Smart_Masker"
  }'
```

---

<a id="docs"></a>
## 📚 文档索引

| 文档 | 内容说明 |
|:---|:---|
| [系统架构](docs/ARCHITECTURE.md) | 了解系统整体设计与端云协同架构 |
| [Skills API](docs/SKILLS_API.md) | 三大核心 Skills 的输入输出契约 |
| [RAG 数据模式](docs/RAG_SCHEMA.md) | ChromaDB 向量数据库的存储范式 |
| [Prompt 模板](docs/PROMPT_TEMPLATES.md) | 端侧 LLM 推理与代码生成的模板 |
| [Agent 行为约束](AGENTS.md) | LLM 调度 Skills 的核心原则 |

---

<a id="ethics"></a>
## ⚖️ 伦理声明

<details>
<summary><strong>⚠️ 请在引用、部署或二次开发前阅读</strong></summary>

- 本项目面向隐私保护、风险识别与产品安全治理，<strong>不用于法律意义上的身份认证</strong>
- 基于对话内容的隐私判断本质上是概率推断，而非身份事实确认
- 项目<strong>不鼓励</strong>将模型输出直接用于惩罚性、歧视性或不可申诉的自动化决策
- 涉及高风险处置、模式切换、账号限制时，应<strong>保留人工复核与申诉机制</strong>
- 数据处理遵循最小化原则，只在必要时进行脱敏处理

</details>

---

## 🤝 支持与联系

- 📂 **GitHub 仓库**: [https://github.com/Theodora-Y/MaskClaw](https://github.com/Theodora-Y/MaskClaw)
- 🐛 **问题反馈**: [Issues 页面](https://github.com/Theodora-Y/MaskClaw/issues)
- 💡 **功能建议**: [Discussions 页面](https://github.com/Theodora-Y/MaskClaw/discussions)

---

## 📄 引用

如果您在研究中使用了本项目，请引用：

```bibtex
@misc{maskclaw_2026,
  title        = {MaskClaw: On-device Privacy-Preserving Framework with Self-Evolving Rule Extraction for Agent Systems},
  author       = {MaskClaw Team},
  year         = {2026},
  howpublished = {https://github.com/Theodora-Y/MaskClaw},
  note         = {GitHub repository}
}
```

<div class="footer">
  <p>Made with ❤️ by MaskClaw Team • 2026</p>
</div>

<p align="center">
  <img src="docs/assets.md/logo_4x.png" width="80%" alt="MaskClaw Logo" />
</p>

<h1 align="center" style="font-family: Georgia, 'Times New Roman', serif; font-weight: bold;">
  A Self-Evolving Privacy Protection Framework via On-Device Rule Extraction
</h1>

<p align="center">
  <a href="README.md">简体中文</a> | <a href="README_EN.md">English</a>
</p>

<p align="center">
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/MiniCPM-V_4.5-FF6B6B?style=flat-square" alt="MiniCPM" />
  </a>
  <a href="https://fastapi.tiangolo.com/">
    <img src="https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/ChromaDB-RAG-8b5cf6?style=flat-square" alt="ChromaDB" />
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License" />
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/Privacy-On--Device-10B981?style=flat-square" alt="Privacy" />
  </a>
</p>

<p align="center">
  <strong>On-Device Privacy Guardian</strong> | <strong>Self-Evolving Rule Engine</strong> | <strong>Human-in-the-Loop Confirmation</strong>
</p>

---

[简体中文](README.md) | [English](README_EN.md)

---

OpenClaw and similar on-device Agent frameworks make it possible for phones to automatically fill forms, send messages, and transfer files.
**MaskClaw** is a privacy guardian layer specifically designed for these Agents — it intervenes before an Agent executes an operation, determining whether the action should be taken and how, with all reasoning performed entirely on the local device, ensuring **data never leaves the edge**.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Core Pain Points](#core-pain-points)
- [System Architecture](#system-architecture)
- [Three Core Modules](#three-core-modules)
- [Design Highlights](#design-highlights)
- [Demo Screenshots](#demo-screenshots)
- [Performance Metrics](#performance-metrics)
- [Comparison with Alternatives](#comparison-with-alternatives)
- [Use Cases](#use-cases)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Documentation Index](#documentation-index)

---

## Project Overview

**MaskClaw** is a **self-evolving rule extraction framework** for **on-device Agent privacy protection**. It is not a traditional data encryption or content filtering tool; instead, it performs **in-process mediation** before an Agent executes an operation: identifying sensitive information, assessing operation risks, intelligently masking data, and continuously optimizing protection policies based on user behavioral feedback.

![Architecture](docs/assets.md/架构图.png)

In MaskClaw, **three core modules work in coordination**, simulating the role of a real-world privacy guardian to collaboratively complete tasks such as **visual masking, behavior monitoring, and rule evolution**. The framework includes built-in **retrieval-augmented cognitive mechanisms (rule knowledge base + behavioral memory)** and **feedback-driven evolutionary learning**, enabling the system to adaptively optimize intervention strategies over time.

### Core Values

| Value Dimension | Description |
|:---|:---|
| 🔒 **Privacy Protection** | Sensitive data is processed on-device without uploading to the cloud, meeting compliance requirements for healthcare, finance, and other industries |
| 🧬 **Personalized Adaptation** | Rules are continuously extracted from user behavior, closely matching individual privacy preferences |
| 🤝 **Human-in-the-Loop Confirmation** | Clear confidence level classification with Unsure mechanism ensures usability during cold start |
| 🔄 **Self-Evolution Capability** | User behavior drives rule updates; the system understands users better over time |

---

## Core Pain Points

The more powerful on-device Agents become at automation, the larger the privacy attack surface. Existing protection solutions fall behind on three levels:

### 🔍 Perception Layer: Format Recognition Only, No Intent Understanding

Formatted data like ID card numbers and bank card numbers can be intercepted by existing tools. But the truly dangerous operations Agents perform often have no fixed format — sending screenshots to strangers, entering real addresses where they shouldn't, uploading internal files to external platforms.

> **These behaviors can never be detected by regex matching.**

### 👤 Adaptation Layer: Public Rules Only, No Personal Rules

Everyone has different privacy boundaries; the same field may have completely different sensitivity levels depending on profession and scenario. Existing solutions provide a one-size-fits-all minimum standard, rather than personalized protection that dynamically adjusts to user habits.

> **Rules are rigid and cannot adapt to individuals.**

### ☁️ Architecture Layer: Cloud Auditing is Itself a Leak

Uploading screen content to the cloud for semantic judgment is not permitted under compliance requirements in many industries, and creates a paradox for individual users: "sacrificing privacy to protect privacy."

> **Data uploaded to the cloud cannot meet compliance requirements.**

---

## System Architecture

### Thin Client + Fat Server + Skill-Use Rule Scheduling Microservice Architecture

MaskClaw intervenes in an Agent's execution chain through **Hooking** without modifying any code in third-party Agents like AutoGLM or OpenClaw.

![Four-Layer Architecture](docs/assets.md/四层.svg)

<details>
<summary>📊 Architecture Details</summary>

| Layer | Name | Core Components |
|:---:|:---|:---|
| **Layer 1** | Perception | RapidOCR format-sensitive recognition, OpenCV local visual blur processing |
| **Layer 2** | Cognition | MiniCPM-V 4.5 semantic reasoning, ChromaDB RAG rule retrieval |
| **Layer 3** | Tool-Use | Smart Masker visual masking, PII Detection privacy detection |
| **Layer 4** | Self-Evolution | Behavior Monitor behavior monitoring, Skill Evolution rule extraction, Sandbox verification |

</details>

### Workflow

```
📸 On-device screenshot → 🔍 PII Detection → 🧠 RAG Retrieval → ⚖️ Risk Judgment → 🎭 Visual Masking → ✅ Safe Forward
```

### Transparent to Third-Party Agents

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Traditional Architecture: Data Leak Risk            │
│                                                                         │
│    Agent ──→ Raw Screenshot ──→ Upload to Cloud ──→ Privacy Leak!     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    MaskClaw Architecture: Secure Closed Loop            │
│                                                                         │
│    Agent ──→ Raw Screenshot ──→ MaskClaw ──→ On-Device Masking ──→ Safe Data ──→ Agent │
│                       ↗️                                                 │
│                  Hooking Intervention                                   │
│                 No Agent Code Modification Required                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Three Core Modules

### 🎭 Smart Masker

**Intelligent Visual Masking Module**, uses RapidOCR to identify sensitive text regions in images and performs local desensitization.

- Supports Gaussian blur, pixelation, color block coverage, and other masking methods
- RapidOCR high-performance millisecond-level text recognition
- Data never leaves the device throughout the process

### 📊 Behavior Monitor

**Behavior Monitoring Module**, continuously listens to Agent operation behaviors and captures user intervention actions.

- Records correction behaviors such as modified input values, rejected operations
- Provides data foundation for rule evolution
- Supports session trajectory tracking

### 🧬 Skill Evolution

**Rule Self-Evolution Module**, continuously optimizes SOPs from correction logs based on hill climbing.

- Extracts new rules from real user behaviors
- Automatically deploys after sandbox testing verification
- The system understands users' personal privacy boundaries better over time

---

## Design Highlights

### 🔒 Lightweight On-Device Model — Hardcore Guarantee for Data Not Leaving Edge

Semantic reasoning is handled by **MiniCPM-V 4.5**, and with 9B parameters, it can be locally deployed on consumer-grade devices. Sensitive information identification and visual blur processing are all completed locally without relying on network connections.

| Component | Technology | Advantage |
|:---|:---|:---|
| Vision Model | MiniCPM-V 4.5 (9B) | Deployable on edge, strong semantic understanding |
| OCR Engine | RapidOCR | High-performance millisecond-level text recognition |
| Masking Processing | OpenCV | Local visual processing, zero upload |
| Rule Retrieval | ChromaDB | Efficient vector similarity search |

### 🧬 Self-Evolving Experience Base — Rules Grow from User Behaviors

Rules are not statically maintained lists; they are continuously extracted from real user behaviors and automatically deployed after sandbox verification.

```
User Behavior → Behavior Log → Pattern Recognition → Rule Extraction → Sandbox Test → Version Release
                                                                          ↓
                                                                    Human Review Gate
```

### 🤝 Human-in-the-Loop Confirmation — Five-Level Confidence Smart Judgment

The system has clear confidence level classification for its judgments, with different strategies under different states:

| Judgment | Condition | System Behavior |
|:---:|:---|:---|
| **Allow** | Rule base complete match, safe | Direct pass |
| **Block** | Rule base complete match, risk clear | Direct block |
| **Mask** | Rule base complete match, masking needed | Pass after masking |
| **Ask** | Rule base information incomplete | Actively confirm with user |
| **Unsure** | New scenario, no record | Mark and wait for user instruction |

> 💡 **This mechanism keeps the system usable during cold start**, rather than frequent false positives or missed detections.

### 🔄 Collaborative Filtering — Group Wisdom Accelerates Personalized Convergence

| User Stage | Rule Source | Effect |
|:---|:---|:---|
| Cold Start | General baseline rule set | Ready to use out of the box |
| Early Accumulation | Similar user group collaborative filtering | Fast convergence |
| Stable Period | Personal behavior self-evolution | Precise personalization |

### 📊 P-GUI-Evo Dataset — Industry's First Agent Privacy Benchmark

| Dimension | Spec |
|:---|:---|
| Sample Size | 622 |
| User Profiles | 3 types (Medical Consultant, Live Streamer, General Employee) |
| Operation Scenarios | 6 types of real scenarios |
| Generalization Variants | Screenshot degradation, phrasing rewrites, DOM structure perturbation |
| Judgment Labels | Allow / Block / Mask / Ask / Unsure |

## Demo Screenshots

MaskClaw provides a clean and intuitive web interface for real-time privacy protection status and operation records.

#### Send Commands

![Send Commands](docs/assets.md/发送命令.gif)

#### Masking Display

![Masking Display](docs/assets.md/打码显示.gif)

#### Notification Alerts

![Notifications](docs/assets.md/通知.gif)

#### Skill List Management

![Skill List](docs/assets.md/skill列表.gif)

---

## Performance Metrics

### Dataset Architecture

| Dimension | Current (Experimental) | Description |
|:---|---:|:---|
| Sample Size | 622 | Discarded entries removed |
| User Profiles | 3 types | Medical Consultant UserA, Live Streamer UserB, General Employee UserC |
| Buckets | D1/D2/D3 | Correspond to baseline, generalization, noise/new distribution stress |
| Bucket Sizes | D1: 216, D2: 252, D3: 154 | Statistics based on final bucket list |
| Judgment Labels | Allow/Block/Mask/Ask/Unsure | Aligned with policy execution behavior |

### Expected Performance Indicators

| Metric | Evaluation Bucket | Expected Target |
|:---|---:|:---:|
| Rule Extraction F1 | D1 Cold Start | ≥ 0.85 |
| Rule Extraction F1 | D2 Generalization | ≥ 0.75 |
| Judgment Accuracy | D1 Full | ≥ 90% |
| Generalization Degradation | D2 vs D1 | ≤ 10% |
| Unsure Recall | D3 New Distribution | ≥ 80% |

> **Why two-level evaluation?** High judgment accuracy doesn't mean the system has truly learned the rules. Rule extraction F1 measures whether the model extracted semantically correct rules; judgment consistency measures whether those rules can generalize to new samples. Both must pass for true learning.

---

## Comparison with Alternatives

| Dimension | MaskClaw | Google DLP | Microsoft Presidio | Cloud LLM Audit |
|:---|:---:|:---:|:---:|:---:|
| **Context Awareness** | ✅ Multi-condition combined judgment | ❌ Format matching | ❌ Format matching | ⚠️ Semantic understanding but requires cloud upload |
| **Personalized Rules** | ✅ Automatic extraction and continuous evolution | ❌ Static rule base | ❌ Static rule base | ❌ No memory |
| **Data Never Leaves Edge** | ✅ **Fully on-device** | ❌ Requires internet | ✅ Local deployment possible | ❌ Must upload screenshots |
| **Self-Evolution** | ✅ **Yes, user behavior driven** | ❌ None | ❌ None | ❌ None |
| **Uncertainty Output** | ✅ **Unsure mechanism** | ❌ None | ❌ None | ❌ None |
| **Agent Integration** | ✅ **Hooking zero modification** | ⚠️ Standalone service needs integration | ⚠️ Standalone service needs integration | ⚠️ API call needs integration |

### Key Gaps

1. **No existing solution can simultaneously achieve context awareness + data never leaving edge.** Cloud LLMs have sufficient semantic understanding capabilities, but screenshot upload is a hard constraint in compliance-sensitive scenarios; local solutions (Presidio, DLP on-premises) can stay offline but cannot handle semantic-level judgments. **MaskClaw is currently the only solution that completes semantic-level judgment on-device.**

2. **No existing solution has rule self-evolution capability.** All comparison solutions require manually maintained rule bases and cannot learn from user behaviors. This is a fundamental flaw in scenarios where Agents deeply介入 user operations.

---

## Use Cases

| Direction | Scenario Description | Core Value |
|:---|:---|:---|
| 📱 Mobile Manufacturer System-Level Agent | System services like XiaoYi, XiaoBu remain resident | Provides unified fallback for all third-party Agents without individual adaptation |
| 💼 Enterprise Mobile Office Suite | DingTalk, Feishu plugin layer | Prevents internal sensitive information from leaving enterprise boundaries via Agents |
| 🏥 Medical/Financial Terminal Devices | Industry compliance-sensitive scenarios | Data never leaves edge architecture meets industry mandatory requirements |

---

## Project Structure

```
MaskClaw/
├── api_server.py                 # FastAPI HTTP service (port 8001)
├── auth_router.py                # Authentication router
├── evolution_daemon.py           # Evolution daemon
├── notifications_router.py       # Notifications router
├── proxy_agent.py                # Proxy Agent core logic
├── requirements.txt              # Python dependencies
├── docker-compose.yml            # Docker container orchestration
├── Dockerfile                    # Docker image build
├── STARTUP.md                    # Startup guide
├── AGENTS.md                     # Agent behavior constraints
│
├── docs/                         # Documentation
│   ├── ARCHITECTURE.md           # System architecture
│   ├── SKILLS_API.md             # Skills API documentation
│   ├── RAG_SCHEMA.md             # RAG data schema
│   ├── PROMPT_TEMPLATES.md       # Prompt template documentation
│   ├── SESSION_TRACE_FORMAT.md   # Session trace format
│   └── self_evolution_mechanism.md # Self-evolution mechanism
│   
│
├── model_server/                 # Model service
│   ├── minicpm_api.py            # MiniCPM-V vision model API (port 8000)
│   ├── requirements.txt          # Model service dependencies
│   └── memory/chroma_storage/   # ChromaDB data (runtime generated)
│
├── memory/                        # Memory storage
│   ├── chroma_manager.py        # ChromaDB manager
│   ├── rag_client.py             # RAG retrieval client
│   ├── log_processor.py          # Log processor
│   └── chat_history_db.py        # Chat history storage
│
├── skills/                        # Built-in Skills (platform-level)
│   ├── smart_masker.py          # 🎭 Visual masking module
│   ├── behavior_monitor.py       # 📊 Behavior monitoring module
│   └── evolution_mechanic.py    # 🧬 Self-evolution mechanism
│
├── sandbox/                       # Sandbox testing
│   ├── sandbox_validator.py     # Sandbox validator
│   ├── semantic_evaluator.py     # Semantic evaluator
│   └── checklist_evaluator.py   # Checklist evaluator
│
├── prompts/                       # Prompt templates
│   ├── evolution_rule_extract.txt
│   ├── evolution_skill_writing.txt
│   ├── privacy_analysis.txt
│   ├── relevance_assessment.txt
│   └── retrieval_decision.txt
│
├── scripts/                       # Utility scripts
│   ├── generate_skills.py        # Generate Skills
│   ├── migrate_logs_to_chains.py
│   ├── seed_notifications.py    # Initialize notifications
│   ├── seed_skills_db.py        # Initialize Skills database
│   └── split_traces.py
│
├── skill_registry/               # Skills registry
│   ├── __init__.py
│   └── skill_db.py              # Skills database management
│
├── user_skills/                  # User personalized Skills (L3 Evolution)
│   
│
└── windows_sdk/                   # Windows SDK (AutoGLM integration)

```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install chromadb rapidocr-onnxrunner onnxruntime pillow opencv-python \
            fastapi uvicorn requests transformers>=4.51.0 torch
```

### 2. Start Model Service (Port 8000)

```bash
cd model_server
python minicpm_api.py
```

### 3. Start Privacy Proxy Service (Port 8001)

```bash
python api_server.py
```

### 4. Verify Service Status

```bash
curl http://127.0.0.1:8001/
```

### 5. SSH Port Mapping

```bash
ssh -L 8001:127.0.0.1:8001 root@server -N
```

---

## API Reference

### Health Check

```bash
# Privacy proxy service
curl http://localhost:8001/

# MiniCPM vision model
curl -X POST http://localhost:8000/chat -F "prompt=hello"
```

### Process Screenshot (Returns Masked Image)

```bash
curl -X POST http://localhost:8001/process \
  -F "image=@test.jpg" \
  -F "command=Analyze current page privacy" \
  -o output.jpg
```

### Rule Management

```bash
# View all rules
curl http://localhost:8001/rules

# Add new rule
curl -X POST http://localhost:8001/rules \
  -H "Content-Type: application/json" \
  -d '{"scenario": "Account Registration Page", "target_field": "Phone Number", "document": "Real phone numbers prohibited"}'
```

---

## Documentation Index

| Document | Content Description |
|:---|:---|
| [System Architecture](docs/ARCHITECTURE.md) | Overall system design and edge-cloud coordination |
| [Skills API](docs/SKILLS_API.md) | Input/output contracts for three core Skills |
| [RAG Data Schema](docs/RAG_SCHEMA.md) | ChromaDB vector database storage paradigm |
| [Prompt Templates](docs/PROMPT_TEMPLATES.md) | Templates for edge LLM reasoning and code generation |
| [Agent Behavior Constraints](AGENTS.md) | Core principles for LLM scheduling Skills |

---

## Ethical Statement

> ⚠️ **Please read before citing, deploying, or secondary development**
>
> - This project is oriented toward privacy protection, risk identification, and product security governance, **not for legally意义上的 identity authentication**
> - Privacy judgments based on dialogue content are essentially probabilistic inference, not identity fact confirmation
> - The project **does not encourage** using model outputs directly for punitive, discriminatory, or unappealable automated decisions
> - High-risk disposal, pattern switching, and account restrictions should **retain human review and appeal mechanisms**
> - Data processing follows the minimization principle, only performing masking when necessary

---

## Support & Contact

- 📂 **GitHub Repository**: [https://github.com/Theodora-Y/MaskClaw](https://github.com/Theodora-Y/MaskClaw)
- 🐛 **Issue Reports**: [Issues Page](https://github.com/Theodora-Y/MaskClaw/issues)
- 💡 **Feature Suggestions**: [Discussions Page](https://github.com/Theodora-Y/MaskClaw/discussions)

---

## Citation

```bibtex
@misc{maskclaw_2026,
  title        = {MaskClaw: On-device Privacy-Preserving Framework with Self-Evolving Rule Extraction for Agent Systems},
  author       = {MaskClaw Team},
  year         = {2026},
  howpublished = {https://github.com/Theodora-Y/MaskClaw}
}
```

---

*Made with ❤️ by MaskClaw Team • 2026*

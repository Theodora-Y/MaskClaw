# MaskClaw

An on-device privacy protection and self-evolving rule extraction framework for agent systems.

This is an anonymized review version that only keeps the method overview, data scale, run commands, and API summary.

## Overview

MaskClaw provides a privacy protection layer before an on-device agent executes actions such as screenshot analysis, form filling, file transfer, or message sending. It identifies sensitive information, estimates operation risk, applies masking when needed, and updates personalized privacy rules from user feedback.

The framework focuses on:

- On-device processing: sensitive content is handled locally whenever possible.
- Context-aware judgment: decisions consider task intent and operation context, not only fixed-format patterns.
- Human-in-the-loop confirmation: uncertain or unseen cases can be routed to the user.
- Rule evolution: user corrections, rejections, and confirmations are used to improve privacy rules.

## Core Modules

### Smart Masker

Identifies sensitive regions in screenshots or interface images and applies local visual masking, blurring, or pixelation.

### Behavior Monitor

Records agent actions and user feedback, including corrections, rejected operations, and confirmation decisions.

### Skill Evolution

Extracts privacy rules from behavior logs and updates the personalized rule base after validation.

## Workflow

```text
On-device screenshot / UI state
    -> Sensitive information detection
    -> Rule retrieval and contextual reasoning
    -> Risk decision
    -> Masking or user confirmation when needed
    -> Safe forwarding to the agent
```

## Data and Evaluation

The experiments use the P-GUI-Evo dataset with 800+ samples covering multiple user profiles, operation scenarios, generalization variants, and risk labels.

| Dimension | Description |
|:---|:---|
| Sample size | 800+ samples |
| User profiles | Multiple user settings |
| Scenario types | Form filling, message sending, file handling, account operations, and related tasks |
| Generalization variants | Screenshot degradation, instruction rewriting, UI structure perturbation, and related variants |
| Decision labels | Allow / Block / Mask / Ask / Unsure |

Evaluation focuses on two aspects:

- Decision consistency: whether the system makes correct risk decisions for agent actions.
- Rule extraction quality: whether the system extracts generalizable privacy rules from user feedback.

## Comparison

| Dimension | MaskClaw | Format-based detection | Cloud audit |
|:---|:---:|:---:|:---:|
| Context understanding | Supported | Weak | Supported |
| Personalized rules | Supported | Weak | Usually unsupported |
| On-device processing | Supported | Possible | Unsupported |
| Rule self-evolution | Supported | Unsupported | Usually unsupported |
| Uncertainty handling | Supported | Unsupported | Implementation-dependent |

## Project Structure

```text
MaskClaw/
+-- api_server.py
+-- proxy_agent.py
+-- evolution_daemon.py
+-- model_server/
+-- memory/
+-- skills/
+-- sandbox/
+-- prompts/
+-- scripts/
+-- skill_registry/
+-- user_skills/
+-- windows_sdk/
```

## Quick Start

Install dependencies:

```bash
pip install chromadb rapidocr-onnxrunner onnxruntime pillow opencv-python fastapi uvicorn requests transformers torch
```

Start the model service:

```bash
cd model_server
python minicpm_api.py
```

Start the privacy proxy service:

```bash
python api_server.py
```

## API Summary

| Endpoint | Function |
|:---|:---|
| `GET /` | Health check |
| `POST /process` | Process a screenshot and return the masked result |
| `GET /rules` | View current rules |
| `POST /rules` | Add or update rules |

## Ethics Statement

This project is intended for privacy protection, risk identification, and security governance. It should not be used for identity authentication, punitive decisions, or non-appealable automated enforcement. High-risk scenarios should retain human review and appeal mechanisms. The system should follow the principle of data minimization and apply masking, blocking, or user confirmation only when necessary.

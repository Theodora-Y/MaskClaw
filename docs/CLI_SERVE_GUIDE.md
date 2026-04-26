# MaskClaw CLI 与 `serve` 部署手册

这份文档面向两类读者：

- 想把 `MaskClaw` 安装成可直接使用的 CLI 的开发者
- 想在服务器或内网环境中，按 `serve` 体系拉起完整后台服务栈的部署者

当前文档只描述**已经落地到仓库中的 CLI 能力**，不把未来规划写成已完成事实。

---

## 1. 当前 CLI 的定位

`MaskClaw CLI` 不是另一个 GUI Agent。

它现在承担的是三个入口角色：

- 服务编排入口：`serve / doctor / bridge / model`
- 规则审计入口：`review / skills / logs`
- 安全桥接入口：`guard / task`

其中：

- `task run` 仍然是用户让 agent 执行任务的入口
- `serve up` 负责拉起后台常驻角色
- 自进化不是手工 `generate` 命令主导，而是依赖 `evolution-daemon` 在服务常驻后自动工作

---

## 2. 当前已纳入 CLI 的能力

目前 CLI 已覆盖这些命令组：

- `doctor`
- `model`
- `serve`
- `bridge`
- `auth`
- `skills`
- `review`
- `logs`
- `guard`
- `task`

其中和完整服务栈最相关的是：

- `maskclaw serve up`
- `maskclaw serve status`
- `maskclaw doctor`
- `maskclaw task run`
- `maskclaw review pending/show/approve/reject`
- `maskclaw skills list/show/diff/edit/archive/restore`
- `maskclaw logs recent/tail`

---

## 3. 安装 CLI

### 3.1 进入仓库根目录

```powershell
cd D:\学习笔记\工4\实验设计\MaskClaw
```

Linux / 服务器环境同理，进入仓库根目录即可。

### 3.2 安装依赖

至少需要：

- Python 3.10+
- `pip`
- `typer`
- `fastapi`
- `uvicorn`

如果还要启动前端或桥接，还需要：

- `npm`
- Open-AutoGLM 相关环境

推荐先安装仓库依赖：

```powershell
python -m pip install -r requirements.txt
```

### 3.3 安装 CLI 入口

推荐使用 editable install：

```powershell
python -m pip install -e .
```

安装成功后，应该能直接使用：

```powershell
maskclaw --version
```

如果当前环境不方便做 `pip install`，开发期也可以临时使用备用入口：

```powershell
python -m maskclaw_cli --version
```

---

## 4. `serve` 体系的角色模型

当前 CLI 已将 `serve` 从“少数硬编码进程”升级为**角色化服务编排**。

当前角色 ID 为：

- `api`
- `evolution-daemon`
- `bridge-autoglm`
- `frontend`
- `minicpm-privacy`
- `minicpm-skillgen`
- `minicpm-feedback`
- `ollama-proxy`

其中：

- `api`：本机 `api_server.py`
- `evolution-daemon`：独立常驻进程，自动消费日志并触发自进化
- `bridge-autoglm`：AutoGLM 手机桥接
- `frontend`：前端调试界面
- `minicpm-privacy`：隐私识别 / guard 图像理解角色
- `minicpm-skillgen`：新 skill / SOP 生成角色
- `minicpm-feedback`：任务过程解释 / 前端过程回传角色
- `ollama-proxy`：本地 Ollama/Gemma 实验后端

`task run` 不属于常驻服务，不在 `serve up` 中直接托管；它继续通过 bridge 触发任务。

---

## 5. CLI 配置文件位置

CLI 配置文件默认位置：

- Windows：`%APPDATA%\MaskClaw\config.json`
- Linux：`~/.config/maskclaw/config.json`

也可以通过环境变量覆盖：

```powershell
MASKCLAW_CONFIG_PATH=/custom/path/config.json
```

当前 CLI 已把旧的单模型配置自动迁移成**角色化服务目录**。配置里最关键的字段是：

- `mode`
- `model_backend`
- `model_name`
- `model_endpoint`
- `model_roles`
- `service_roles`
- `autoglm_dir`

---

## 6. 个人模式与企业模式

### 6.1 个人模式

适合：

- 本机开发
- 本地 Ollama/Gemma 实验
- 不依赖企业内网 MiniCPM 的调试

典型设置：

```powershell
maskclaw model use ollama --model gemma:2b --endpoint http://127.0.0.1:8005 --mode personal --json
```

当前 CLI 会把 `privacy / skillgen / feedback` 三个角色都绑定到 `ollama-proxy`。

### 6.2 企业模式

适合：

- 服务器 / 内网环境
- MiniCPM 三角色分工部署
- AutoGLM + 自进化完整闭环验收

基础模式设置：

```powershell
maskclaw model use minicpm --endpoint http://127.0.0.1:8000/chat --mode enterprise --json
```

注意：

- `model use minicpm` 只会给旧兼容入口赋值
- 完整企业模式仍需要你把三类 MiniCPM 角色的 endpoint 明确写进配置文件
- 当前 CLI **还没有**专门的 `config set-role` 命令，因此这一步需要手动编辑 `config.json`

---

## 7. 企业模式下的角色配置

当前仓库的真实设计前提是：MiniCPM 三类职责**不强行合并端口**。

因此企业模式下建议把配置写成类似下面这样：

```json
{
  "mode": "enterprise",
  "model_backend": "minicpm",
  "model_endpoint": "http://127.0.0.1:8000/chat",
  "model_roles": {
    "privacy": "minicpm-privacy",
    "skillgen": "minicpm-skillgen",
    "feedback": "minicpm-feedback"
  },
  "service_roles": {
    "minicpm-privacy": {
      "enabled": true,
      "managed": false,
      "cwd": "",
      "command": [],
      "endpoint": "http://127.0.0.1:<privacy-port>/chat",
      "healthcheck": "tcp",
      "depends_on": []
    },
    "minicpm-skillgen": {
      "enabled": true,
      "managed": false,
      "cwd": "",
      "command": [],
      "endpoint": "http://127.0.0.1:<skillgen-port>/chat",
      "healthcheck": "tcp",
      "depends_on": []
    },
    "minicpm-feedback": {
      "enabled": true,
      "managed": false,
      "cwd": "",
      "command": [],
      "endpoint": "http://127.0.0.1:<feedback-port>/chat",
      "healthcheck": "tcp",
      "depends_on": []
    }
  }
}
```

说明：

- `managed=false` 表示这些服务由现有部署体系负责，CLI 只负责编排视图和体检
- 如果你们后续把某个 MiniCPM 角色也做成可由 CLI 直接拉起的本地脚本，再把该角色改成 `managed=true` 并填入 `cwd + command`
- 请按你们现有部署填写真实端口，不要为了 CLI 去强行改后端接口职责

---

## 8. `serve` 的工作方式

### 8.1 `serve up`

`serve up` 现在会按角色编排服务，而不是只管单一模型端口。

企业模式期望的默认顺序是：

1. 模型角色服务
2. `api`
3. `evolution-daemon`
4. `bridge-autoglm`
5. `frontend`

个人模式同样会把 `evolution-daemon` 纳入编排。

### 8.2 `serve status`

`serve status --json` 会返回每个角色的：

- `service`
- `required`
- `managed`
- `endpoint`
- `depends_on`
- `capabilities`
- `status`
- `log`

### 8.3 `doctor`

`doctor --json` 会额外检查：

- Python / npm / 关键模块是否存在
- 项目关键路径是否存在
- `bridge-autoglm` 的 Open-AutoGLM 路径是否存在
- `model_roles` 三个角色是否正确绑定
- `service_roles` 是否配置完整

---

## 9. 服务器上的完整 `serve` 验收标准

这一节是当前推荐的**完整服务栈验收口径**。

### 9.1 预检

先确认 CLI 可用：

```powershell
maskclaw --version
maskclaw doctor --json
```

预期：

- `maskclaw --version` 正常输出版本
- `doctor` 中 `model-role:privacy/skillgen/feedback` 都应为 `ok=true`
- `service:minicpm-privacy / skillgen / feedback` 不应处于 `unconfigured`

### 9.2 启动完整企业服务栈

```powershell
maskclaw serve up --mode enterprise --json
maskclaw serve status --json
```

验收重点：

- `serve up` 返回 `ok=true`
- `api` 可见且状态正常
- `evolution-daemon` 可见且状态正常
- `bridge-autoglm` 可见且状态正常
- `minicpm-privacy / minicpm-skillgen / minicpm-feedback` 三类角色必须分别可见
- 不接受“只有 API 起了就算成功”的降级口径

### 9.3 登录与用户上下文

```powershell
maskclaw auth login --email <your-email> --password <your-password> --json
maskclaw auth whoami --json
```

验收重点：

- 登录走本机 API
- `whoami` 能看到当前用户

### 9.4 任务执行与桥接

```powershell
maskclaw task run "按用户要求执行任务" --json
maskclaw task list --json
maskclaw task status <task_id> --json
maskclaw task logs <task_id> --json
```

验收重点：

- `task run` 能把任务交给 bridge
- `task logs` 能看到执行过程
- 如果你们的反馈角色参与前端过程说明，这一段应由 `minicpm-feedback` 提供支持

### 9.5 自动自进化与待审规则

这里不应依赖手工 `generate` 命令，而应依赖：

- agent 做事
- 行为 / 纠错日志被记录
- `evolution-daemon` 自动轮询
- 满足阈值后自动生成候选 skill / SOP
- 写入待审状态

建议验收命令：

```powershell
maskclaw review pending --json
maskclaw review show <notif_id> --json
maskclaw skills list --status pending --json
maskclaw logs recent --json
```

验收重点：

- 新生成的 skill / SOP 能进入待审状态
- `review pending` 能看到通知
- `review show` 能看到目标版本详情
- `logs recent` 能看到相关演化事件

### 9.6 审计与修改

```powershell
maskclaw review approve <notif_id> --json
maskclaw review reject <notif_id> --reason "场景过宽，先不启用" --json
maskclaw skills show <skill_name> --version <version> --json
maskclaw skills diff <skill_name> --version <version> --against registry --json
maskclaw skills edit <skill_name> --version <version> --editor "notepad"
```

验收重点：

- `approve / reject` 走本机 API
- 审计与 skill 生命周期联动
- `skills edit` 修改后能通过校验并同步 registry

---

## 10. 推荐命令清单

### 10.1 服务器完整链路

```powershell
maskclaw doctor --json
maskclaw serve up --mode enterprise --json
maskclaw serve status --json
maskclaw auth login --email <your-email> --password <your-password> --json
maskclaw task run "按用户要求执行任务" --json
maskclaw review pending --json
maskclaw logs recent --json
```

### 10.2 规则审计

```powershell
maskclaw skills list --json
maskclaw skills show <skill_name> --version <version> --json
maskclaw skills diff <skill_name> --version <version> --against registry --json
maskclaw skills edit <skill_name> --version <version> --validate-only --json
```

### 10.3 安全判决与图像脱敏

```powershell
maskclaw guard decide --input tests\\data\\guard_event.json --json
maskclaw guard analyze --input path\\to\\screenshot.png --command "分析当前页面隐私" --json
maskclaw guard redact --input path\\to\\screenshot.png --command "分析当前页面隐私" --method blur --output path\\to\\masked.png --json
```

---

## 11. 当前已知边界

当前仓库中的 `serve` 已经具备角色化编排能力，但仍有几个现实边界需要部署时明确：

- 企业模式下，`minicpm-skillgen` 与 `minicpm-feedback` 的真实 endpoint 需要按你们现网部署填写
- 当前 CLI 还没有专门的命令去编辑 `model_roles/service_roles`，这一步需要手工改配置文件
- `task run` 依旧是用户发起任务的入口，不会被 `serve` 替代
- `--no-bridge` 和 `--no-frontend` 适合隔离排障，不适合作为完整产品链路验收口径

---

## 12. 发布到 GitHub 前建议检查

建议在准备提交前至少检查以下几类内容：

- 本地实验文件是否混入提交
- 本地生成的日志、临时 DB、截图样例是否需要排除
- `skill_registry.db` 和 `user_skills/**/rules.json` 的改动是否真的是你要公开提交的数据
- 本地专用的 Gemma/Ollama 实验改动是否与正式仓库目标一致
- `docs/`、`README.md`、测试文件是否与代码能力同步

如果要对外说明 CLI 化成果，建议提交说明至少覆盖：

- CLI 安装入口
- `serve` 角色化编排
- `evolution-daemon` 已纳入托管
- `review / skills / logs / guard / task` 的当前可用范围
- 企业模式仍需补齐真实三角色 endpoint 的配置

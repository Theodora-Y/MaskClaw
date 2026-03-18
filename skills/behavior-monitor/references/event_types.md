## references/event_types.md

---

### action 字段枚举

Agent 意图执行的操作类型，由 proxy_agent 在调用 monitor 前填入。

| action 值 | 含义 | 通常涉及的 field |
|---|---|---|
| `fill_form_field` | 在表单中填入内容 | 表单字段名 |
| `fill_home_address` | 填写家庭住址 | `home_address` |
| `fill_shipping_address` | 填写收货地址（电商场景） | `shipping_address` |
| `fill_phone` | 填写手机号 | `phone` |
| `send_message` | 发送文字消息 | `message_content` |
| `send_file` | 发送文件或图片 | `file_content` |
| `read_screen_content` | 读取当前屏幕内容 | null |
| `submit_form` | 点击提交按钮 | null |
| `upload_file` | 上传文件到某平台 | `file_content` |
| `auto_complete` | 自动补全输入框内容 | 对应字段名 |

> 这个列表不是封闭的，新 action 类型出现时直接追加，不需要改代码。

---

### resolution 字段枚举

proxy_agent 对这次操作的决策结果，是触发 monitor 记录哪个级别、以及是否需要等待的关键依据。

---

**Allow**
- 含义：操作安全，直接放行
- 触发条件：L1 未检测到敏感信息，且 L2 无匹配规则，或规则判定为合规
- monitor 行为：写级别1轻量记录，C_t 已确定，无需等待
- 示例场景：医生在医院内网 HIS 系统查看病历

---

**Block**
- 含义：操作违规，直接拦截，不执行
- 触发条件：L1 或 L2 判定为明确违规
- monitor 行为：写级别1轻量记录，`correction_type` 记为 `blocked_by_rule`
- 示例场景：Agent 试图通过微信发送含身份证号的截图

---

**Mask**
- 含义：检测到敏感信息，自动打码后放行
- 触发条件：L1 识别到格式化 PII（手机号、身份证、银行卡），无需语义判断
- monitor 行为：写级别1轻量记录，`correction_type` 记为 `auto_masked`
- 示例场景：Agent 填入手机号，L1 自动打成 `138****1234`

---

**Ask**
- 含义：操作存在不确定性，暂停并弹窗询问用户
- 触发条件：L2 规则存在但置信度低，或场景属于 Soft 规则需要用户确认
- monitor 行为：**两阶段写入**，阶段一写 pending，阶段二等用户点击后补全
- 用户可能的回应：允许（`user_allowed`）/ 拒绝（`user_denied`）/ 修改后允许（`user_modified`）
- 示例场景：Agent 要在一个不认识的网站填写家庭住址，系统不确定是否应该拦

---

**Defer**
- 含义：操作暂时挂起，放入用户待办列表，等用户有空处理
- 触发条件：L2 输出 `[IsCompliant=Unsure]`，无法当场判断
- monitor 行为：**两阶段写入**，同 Ask，但不弹窗，而是推入待办队列
- 适用场景：用户不在电脑前，或操作不紧急，不适合用弹窗打断用户
- 示例场景：同事请求共享某个文件，用户当前在忙，系统先挂起等用户回来

---

**Interrupt**
- 含义：用户主动介入并打断了 Agent 的操作
- 触发条件：UIAutomator2 检测到用户在 Agent 操作过程中接管了键盘或鼠标
- monitor 行为：写级别2完整记录，`correction_type` 记为 `user_interrupted`
- 这是**最有价值的信号**，说明 Agent 做了用户不想要的事，是 Evolution Mechanic 优先处理的原料
- 示例场景：Agent 正在填写家庭住址，用户直接清掉改成了公司地址

---

### correction_type 字段枚举

用户响应的类型，在级别2记录的 C_t 阶段填入。

| 值 | 含义 | 对应 resolution |
|---|---|---|
| `pending` | 用户尚未处理，等待中 | Ask / Defer |
| `user_allowed` | 用户确认允许操作 | Ask |
| `user_denied` | 用户明确拒绝操作 | Ask / Defer |
| `user_modified` | 用户修改了操作内容后允许 | Ask / Interrupt |
| `user_interrupted` | 用户主动打断 Agent | Interrupt |
| `auto_masked` | 系统自动打码，无需用户参与 | Mask |
| `blocked_by_rule` | 系统根据规则直接拦截 | Block |

---

### 哪些 correction_type 会进入 Evolution Mechanic

只有以下三种才是有效的训练信号：

```
user_denied       → 用户明确不想要这个操作，可能有规则可抽
user_modified     → 用户有具体偏好，correction_value 里有替代值，信号最强
user_interrupted  → 用户主动介入，行为意图最明确
```

其余的（`pending` 超期删除、`user_allowed`、`auto_masked`、`blocked_by_rule`）**不进入** Evolution，只用于统计。

---

这两份 schema 写完之后，脚本的逻辑就很清晰了——基本上就是按照这两份文档把字段填进去、判断走哪个分支。你觉得有没有遗漏的地方，或者哪里想调整？
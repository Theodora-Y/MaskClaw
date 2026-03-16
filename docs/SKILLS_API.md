# Skills 接口定义

本系统通过端侧 LLM 动态调度以下三类工具 (Skills)：

- **Smart_Masker_Skill**
  - 功能：对图像区域执行脱敏操作。
  - 输入：图像 + 敏感信息。
  - 输出：脱敏后的安全图像。

- **Behavior_Monitor_Skill**
  - 功能：监听 UI 事件与用户修正动作。
  - 输出：JSON 日志流 `{"timestamp": int, "action": str, "correction": str}`。

- **Skill_Evolution_Mechanic**
  - 功能：将日志转化为代码补丁或规则。
  - 输入：纠错行为日志。
  - 输出：新规则代码/JSON 规则对象。
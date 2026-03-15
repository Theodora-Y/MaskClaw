# Skills 接口定义

本系统通过端侧 LLM 动态调度以下四类工具 (Skills)：

- **PII_Detection_Skill**
  - 功能：识别敏感实体（姓名、地址等）。
  - 输入：原始屏幕图像。
  - 输出：`List[{"label": str, "box": [x1, y1, x2, y2], "confidence": float}]`

- **Visual_Obfuscation_Skill**
  - 功能：对图像区域执行脱敏操作。
  - 输入：图像 + `List[box]` + 打码模式（模糊/马赛克）。
  - 输出：脱敏后的安全图像。

- **Behavior_Monitor_Skill**
  - 功能：监听 UI 事件与用户修正动作。
  - 输出：JSON 日志流 `{"timestamp": int, "action": str, "correction": str}`。

- **Skill_Evolution_Mechanic**
  - 功能：将日志转化为代码补丁或规则。
  - 输入：纠错行为日志。
  - 输出：新规则代码/JSON 规则对象。
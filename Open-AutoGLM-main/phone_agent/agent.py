"""Main PhoneAgent class for orchestrating phone automation."""

import json
import os
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from privacy_client import PrivacyAgentClient
from phone_agent.actions import ActionHandler
from phone_agent.actions.handler import do, finish, parse_action
from phone_agent.config import get_messages, get_system_prompt
from phone_agent.device_factory import get_device_factory
from phone_agent.model import ModelClient, ModelConfig
from phone_agent.model.client import MessageBuilder


@dataclass
class AgentConfig:
    """Configuration for the PhoneAgent."""

    max_steps: int = 100
    device_id: str | None = None
    lang: str = "cn"
    system_prompt: str | None = None
    verbose: bool = True

    def __post_init__(self):
        if self.system_prompt is None:
            self.system_prompt = get_system_prompt(self.lang)


@dataclass
class StepResult:
    """Result of a single agent step."""

    success: bool
    finished: bool
    action: dict[str, Any] | None
    thinking: str
    message: str | None = None


class PhoneAgent:
    """
    AI-powered agent for automating Android phone interactions.

    The agent uses a vision-language model to understand screen content
    and decide on actions to complete user tasks.

    Args:
        model_config: Configuration for the AI model.
        agent_config: Configuration for the agent behavior.
        confirmation_callback: Optional callback for sensitive action confirmation.
        takeover_callback: Optional callback for takeover requests.

    Example:
        >>> from phone_agent import PhoneAgent
        >>> from phone_agent.model import ModelConfig
        >>>
        >>> model_config = ModelConfig(base_url="http://localhost:8000/v1")
        >>> agent = PhoneAgent(model_config)
        >>> agent.run("Open WeChat and send a message to John")
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        agent_config: AgentConfig | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
    ):
        self.model_config = model_config or ModelConfig()
        self.agent_config = agent_config or AgentConfig()

        self.model_client = ModelClient(self.model_config)
        self.action_handler = ActionHandler(
            device_id=self.agent_config.device_id,
            confirmation_callback=confirmation_callback,
            takeover_callback=takeover_callback,
        )

        timeout_raw = os.getenv("PHONE_AGENT_PRIVACY_API_TIMEOUT", "30").strip()
        try:
            timeout_seconds = max(1, int(timeout_raw))
        except ValueError:
            timeout_seconds = 30

        self.user_id = (
            os.getenv("PHONE_AGENT_USER_ID")
            or self.agent_config.device_id
            or "default_user"
        )
        self._privacy_client = PrivacyAgentClient(timeout_seconds=timeout_seconds)
        self._privacy_client_enabled = self._privacy_client.enabled

        # 按需拉取 skills 的开关（默认开启）
        skill_retrieval_raw = os.getenv("PHONE_AGENT_SKILL_RETRIEVAL", "true").strip()
        self._skill_retrieval_enabled = skill_retrieval_raw.lower() in {"1", "true", "yes", "on"}

        self._skill_catalog_path = Path(__file__).resolve().parents[1] / "SKILL_CATALOG.md"
        self._skill_catalog_content = ""
        self._installed_skills: dict[str, str] = {}
        self._correction_log_path = Path(
            os.getenv("PHONE_AGENT_CORRECTION_LOG", "logs/correction_log.jsonl")
        )

        threshold_raw = os.getenv("PHONE_AGENT_CORRECTION_THRESHOLD", "1").strip()
        try:
            self._correction_threshold = max(1, int(threshold_raw))
        except ValueError:
            self._correction_threshold = 1

        self._correction_count_before_run = 0
        self._bootstrap_privacy_features()

        self._context: list[dict[str, Any]] = []
        self._step_count = 0

    def run(self, task: str) -> str:
        """
        Run the agent to complete a task.

        Args:
            task: Natural language description of the task.

        Returns:
            Final message from the agent.
        """
        self._context = []
        self._step_count = 0
        self._correction_count_before_run = self._count_corrections()

        # ===== 按需拉取匹配的 skills（新增）=====
        if self._privacy_client_enabled and self._skill_retrieval_enabled:
            self._retrieve_and_load_skills(task)

        # First step with user prompt
        result = self._execute_step(task, is_first=True)

        if result.finished:
            self._trigger_evolution_if_needed(task)
            return result.message or "Task completed"

        # Continue until finished or max steps reached
        while self._step_count < self.agent_config.max_steps:
            result = self._execute_step(is_first=False)

            if result.finished:
                self._trigger_evolution_if_needed(task)
                return result.message or "Task completed"

        self._trigger_evolution_if_needed(task)
        return "Max steps reached"

    def step(self, task: str | None = None) -> StepResult:
        """
        Execute a single step of the agent.

        Useful for manual control or debugging.

        Args:
            task: Task description (only needed for first step).

        Returns:
            StepResult with step details.
        """
        is_first = len(self._context) == 0

        if is_first and not task:
            raise ValueError("Task is required for the first step")

        return self._execute_step(task, is_first)

    def reset(self) -> None:
        """Reset the agent state for a new task."""
        self._context = []
        self._step_count = 0

    def _bootstrap_privacy_features(self) -> None:
        """Initialize privacy hook and sync latest skills from backend."""
        self._load_skill_catalog_from_file()
        if not self._privacy_client_enabled:
            return

        try:
            self._privacy_client.install_hook(user_id=self.user_id)
            self._sync_skills_incrementally()
            self._privacy_client.get_evolution_status(user_id=self.user_id)
        except Exception as exc:
            if self.agent_config.verbose:
                print(f"[privacy-client] bootstrap skipped: {exc}")

    def _load_skill_catalog_from_file(self) -> None:
        """Load local SKILL_CATALOG.md if present."""
        if self._skill_catalog_path.exists():
            self._skill_catalog_content = self._skill_catalog_path.read_text(
                encoding="utf-8"
            ).strip()

    def _sync_skills_incrementally(self) -> None:
        """Pull backend skill deltas and update local SKILL_CATALOG.md."""
        payload = self._privacy_client.sync_skills(
            installed_skills=self._installed_skills,
            user_id=self.user_id,
        )

        skill_list = payload.get("skills")
        if not isinstance(skill_list, list):
            skill_list = payload.get("updated_skills")
        if not isinstance(skill_list, list):
            skill_list = payload.get("new_skills")
        if not isinstance(skill_list, list):
            skill_list = []

        for skill in skill_list:
            if not isinstance(skill, dict):
                continue
            name = str(skill.get("name", "")).strip()
            version = str(skill.get("version", "")).strip()
            if name and version:
                self._installed_skills[name] = version

        catalog_md = payload.get("catalog_md")
        if not isinstance(catalog_md, str) or not catalog_md.strip():
            catalog_md = self._build_catalog_from_skills(skill_list)

        if catalog_md.strip():
            self._skill_catalog_path.write_text(catalog_md.strip() + "\n", encoding="utf-8")
            self._skill_catalog_content = catalog_md.strip()

    @staticmethod
    def _build_catalog_from_skills(skill_list: list[Any]) -> str:
        """Build markdown catalog when backend does not provide catalog_md."""
        lines = ["# SKILL CATALOG", ""]
        for skill in skill_list:
            if not isinstance(skill, dict):
                continue
            name = str(skill.get("name") or "Unnamed Skill").strip()
            version = str(skill.get("version") or "unknown").strip()
            description = str(skill.get("description") or "").strip()
            content = str(skill.get("content") or "").strip()
            lines.append(f"## {name} (v{version})")
            if description:
                lines.append(description)
            if content:
                lines.append("```")
                lines.append(content)
                lines.append("```")
            lines.append("")
        return "\n".join(lines).strip()

    def _build_first_user_prompt(self, task: str) -> str:
        """Append skill catalog to task prompt so model can apply defense skills."""
        if not self._skill_catalog_content:
            self._load_skill_catalog_from_file()

        if not self._skill_catalog_content:
            return task

        return (
            f"{task}\n\n"
            "[Defense Skill Catalog]\n"
            "The following skills are available and should be applied when relevant:\n"
            f"{self._skill_catalog_content}"
        )

    def _retrieve_and_load_skills(self, task: str) -> None:
        """根据任务检索并加载相关的 skills

        1. 检测 app_context
        2. 调用 search_skills API
        3. 对每个匹配的 skill 调用 get_skill_detail
        4. 将 skill 规则注入 _context
        """
        # 1. 检测 app_context
        app_context = self._detect_app_context(task)
        action_keywords = self._extract_action_keywords(task)

        if self.agent_config.verbose:
            print(f"[skill-retrieval] task={task[:50]}..., app_context={app_context}")

        # 2. 检索匹配的 skills
        try:
            search_result = self._privacy_client.search_skills(
                user_id=self.user_id,
                task_goal=task,
                app_context=app_context,
                action_keywords=action_keywords,
                limit=5,
            )
        except Exception as e:
            if self.agent_config.verbose:
                print(f"[skill-retrieval] search_skills failed: {e}")
            return

        skills = search_result.get("skills", [])
        if not skills:
            if self.agent_config.verbose:
                print("[skill-retrieval] no matching skills found")
            return

        if self.agent_config.verbose:
            print(f"[skill-retrieval] found {len(skills)} matching skills")

        # 3. 加载每个 skill 的详细内容
        loaded_skills = []
        for skill in skills:
            skill_name = skill.get("skill_name", "")
            version = skill.get("version", "")
            if not skill_name or not version:
                continue

            try:
                skill_detail = self._privacy_client.get_skill_detail(
                    user_id=self.user_id,
                    skill_name=skill_name,
                    version=version,
                )
                if skill_detail:
                    loaded_skills.append(skill_detail)
            except Exception as e:
                if self.agent_config.verbose:
                    print(f"[skill-retrieval] get_skill_detail failed for {skill_name}: {e}")

        if not loaded_skills:
            return

        # 4. 将 skill 规则注入 _context 和 _skill_catalog_content
        self._apply_skill_context(loaded_skills)

    def _detect_app_context(self, task: str) -> str:
        """从任务描述中检测 app_context

        Args:
            task: 任务描述文本

        Returns:
            检测到的 app_context，如果无法检测返回 "unknown"
        """
        app_keywords = {
            "wechat": ["微信", "wechat", "微信聊天", "weixin"],
            "dingtalk": ["钉钉", "dingtalk", "dtalk"],
            "hospital_oa": ["医院", "oa", "医院系统", "病历", "挂号"],
            "alipay": ["支付宝", "alipay"],
            "bank": ["银行", "转账", "支付"],
            "settings": ["设置", "settings"],
            "contacts": ["联系人", "通讯录", "contacts"],
            "photos": ["相册", "照片", "photos", "gallery"],
        }

        task_lower = task.lower()
        for app, keywords in app_keywords.items():
            for kw in keywords:
                if kw.lower() in task_lower:
                    if self.agent_config.verbose:
                        print(f"[skill-retrieval] detected app_context: {app} (keyword: {kw})")
                    return app

        return "unknown"

    def _extract_action_keywords(self, task: str) -> str:
        """从任务描述中提取动作关键词

        Args:
            task: 任务描述文本

        Returns:
            逗号分隔的动作关键词
        """
        action_keywords = {
            "截图": ["截图", "截屏", "screenshot", "screen capture"],
            "发送": ["发送", "分享", "转发", "send", "share", "forward"],
            "上传": ["上传", "upload"],
            "下载": ["下载", "download"],
            "复制": ["复制", "copy"],
            "粘贴": ["粘贴", "paste"],
            "输入": ["输入", "填写", "input", "fill"],
            "登录": ["登录", "login", "signin"],
            "注册": ["注册", "register", "signup"],
        }

        task_lower = task.lower()
        found_actions = []

        for action, keywords in action_keywords.items():
            for kw in keywords:
                if kw.lower() in task_lower:
                    found_actions.append(action)
                    break

        return ",".join(found_actions)

    def _apply_skill_context(self, skills: list[dict[str, Any]]) -> None:
        """将 skill 规则应用到 agent 上下文

        Args:
            skills: 已加载的 skill 详情列表
        """
        catalog_lines = ["# SKILL CATALOG", ""]

        for skill in skills:
            skill_name = skill.get("skill_name", "Unknown")
            version = skill.get("version", "unknown")
            app_context = skill.get("scene", "")
            confidence = skill.get("confidence", 0)
            strategy = skill.get("strategy", "")
            rule_text = skill.get("rule_text", "")
            skill_md_content = skill.get("skill_md_content", "")
            rules_json_content = skill.get("rules_json_content")

            # 添加到 catalog
            catalog_lines.append(f"## {skill_name} (v{version})")
            catalog_lines.append(f"- 场景: {app_context}")
            catalog_lines.append(f"- 策略: {strategy}")
            catalog_lines.append(f"- 置信度: {confidence}")
            if rule_text:
                catalog_lines.append(f"- 规则: {rule_text[:100]}...")
            catalog_lines.append("")

            # 将 SKILL.md 内容添加到上下文
            if skill_md_content:
                self._context.append({
                    "role": "system",
                    "content": f"""[Skill: {skill_name}@{version}]
When this skill applies (scene={app_context}), follow these rules:
{skill_md_content}"""
                })

            # 将 rules.json 内容添加到上下文
            if rules_json_content:
                if isinstance(rules_json_content, list):
                    rules_text = json.dumps(rules_json_content, ensure_ascii=False, indent=2)
                else:
                    rules_text = str(rules_json_content)

                self._context.append({
                    "role": "system",
                    "content": f"""[Privacy Rules for {skill_name}]
{rules_text}"""
                })

        # 更新 catalog 内容
        self._skill_catalog_content = "\n".join(catalog_lines).strip()

    def _count_corrections(self) -> int:
        """Count correction records from local correction log."""
        if not self._correction_log_path.exists():
            return 0

        try:
            with self._correction_log_path.open("r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def _trigger_evolution_if_needed(self, task: str) -> None:
        """Trigger evolution when user correction count reaches threshold."""
        if not self._privacy_client_enabled:
            return

        correction_count_after_run = self._count_corrections()
        delta = correction_count_after_run - self._correction_count_before_run
        if delta < self._correction_threshold:
            return

        try:
            self._privacy_client.trigger_evolution(
                user_id=self.user_id,
                reason=f"correction_threshold_reached for task: {task}",
            )
            if self.agent_config.verbose:
                print(
                    "[privacy-client] evolution triggered "
                    f"(delta_corrections={delta}, threshold={self._correction_threshold})"
                )
        except Exception as exc:
            if self.agent_config.verbose:
                print(f"[privacy-client] trigger evolution skipped: {exc}")

    def _execute_step(
        self, user_prompt: str | None = None, is_first: bool = False
    ) -> StepResult:
        """Execute a single step of the agent loop."""
        self._step_count += 1

        # Capture current screen state
        device_factory = get_device_factory()
        screenshot = device_factory.get_screenshot(self.agent_config.device_id)
        current_app = device_factory.get_current_app(self.agent_config.device_id)
        privacy_meta = getattr(screenshot, "privacy_metadata", None) or {}

        # Build messages
        if is_first:
            self._context.append(
                MessageBuilder.create_system_message(self.agent_config.system_prompt)
            )

            screen_info = MessageBuilder.build_screen_info(
                current_app,
                matched_rules=privacy_meta.get("matched_rules", []),
                masked_count=privacy_meta.get("masked_count", 0),
            )
            prompt_with_skills = self._build_first_user_prompt(user_prompt or "")
            text_content = f"{prompt_with_skills}\n\n{screen_info}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )
        else:
            screen_info = MessageBuilder.build_screen_info(
                current_app,
                matched_rules=privacy_meta.get("matched_rules", []),
                masked_count=privacy_meta.get("masked_count", 0),
            )
            text_content = f"** Screen Info **\n\n{screen_info}"

            self._context.append(
                MessageBuilder.create_user_message(
                    text=text_content, image_base64=screenshot.base64_data
                )
            )

        # Get model response
        try:
            msgs = get_messages(self.agent_config.lang)
            print("\n" + "=" * 50)
            print(f"💭 {msgs['thinking']}:")
            print("-" * 50)
            response = self.model_client.request(self._context)
        except Exception as e:
            if self.agent_config.verbose:
                traceback.print_exc()
            return StepResult(
                success=False,
                finished=True,
                action=None,
                thinking="",
                message=f"Model error: {e}",
            )

        # Parse action from response
        try:
            action = parse_action(response.action)
        except ValueError:
            if self.agent_config.verbose:
                traceback.print_exc()
            action = finish(message=response.action)

        if self.agent_config.verbose:
            # Print thinking process
            print("-" * 50)
            print(f"🎯 {msgs['action']}:")
            print(json.dumps(action, ensure_ascii=False, indent=2))
            print("=" * 50 + "\n")

        # Remove image from context to save space
        self._context[-1] = MessageBuilder.remove_images_from_message(self._context[-1])

        # Execute action
        try:
            result = self.action_handler.execute(
                action,
                screenshot.width,
                screenshot.height,
                privacy_metadata=privacy_meta,
            )
        except Exception as e:
            if self.agent_config.verbose:
                traceback.print_exc()
            result = self.action_handler.execute(
                finish(message=str(e)),
                screenshot.width,
                screenshot.height,
                privacy_metadata=privacy_meta,
            )

        # Add assistant response to context
        self._context.append(
            MessageBuilder.create_assistant_message(
                f"<think>{response.thinking}</think><answer>{response.action}</answer>"
            )
        )

        # Check if finished
        finished = action.get("_metadata") == "finish" or result.should_finish

        if finished and self.agent_config.verbose:
            msgs = get_messages(self.agent_config.lang)
            print("\n" + "🎉 " + "=" * 48)
            print(
                f"✅ {msgs['task_completed']}: {result.message or action.get('message', msgs['done'])}"
            )
            print("=" * 50 + "\n")

        return StepResult(
            success=result.success,
            finished=finished,
            action=action,
            thinking=response.thinking,
            message=result.message or action.get("message"),
        )

    @property
    def context(self) -> list[dict[str, Any]]:
        """Get the current conversation context."""
        return self._context.copy()

    @property
    def step_count(self) -> int:
        """Get the current step count."""
        return self._step_count

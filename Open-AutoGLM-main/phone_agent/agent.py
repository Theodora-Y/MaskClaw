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

"""Action handler for processing AI model outputs."""

import ast
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable

from phone_agent.config.timing import TIMING_CONFIG
from phone_agent.device_factory import get_device_factory


@dataclass
class ActionResult:
    """Result of an action execution."""

    success: bool
    should_finish: bool
    message: str | None = None
    requires_confirmation: bool = False


class ActionHandler:
    """
    Handles execution of actions from AI model output.

    Args:
        device_id: Optional ADB device ID for multi-device setups.
        confirmation_callback: Optional callback for sensitive action confirmation.
            Should return True to proceed, False to cancel.
        takeover_callback: Optional callback for takeover requests (login, captcha).
    """

    def __init__(
        self,
        device_id: str | None = None,
        confirmation_callback: Callable[[str], bool] | None = None,
        takeover_callback: Callable[[str], None] | None = None,
    ):
        self.device_id = device_id
        self.confirmation_callback = confirmation_callback or self._default_confirmation
        self.takeover_callback = takeover_callback or self._default_takeover

    def execute(
        self,
        action: dict[str, Any],
        screen_width: int,
        screen_height: int,
        privacy_metadata: dict[str, Any] | None = None,
    ) -> ActionResult:
        """
        Execute an action from the AI model.

        Args:
            action: The action dictionary from the model.
            screen_width: Current screen width in pixels.
            screen_height: Current screen height in pixels.

        Returns:
            ActionResult indicating success and whether to finish.
        """
        action_type = action.get("_metadata")

        if action_type == "finish":
            return ActionResult(
                success=True, should_finish=True, message=action.get("message")
            )

        if action_type != "do":
            return ActionResult(
                success=False,
                should_finish=True,
                message=f"Unknown action type: {action_type}",
            )

        action_name = action.get("action")
        handler_method = self._get_handler(action_name)

        if handler_method is None:
            return ActionResult(
                success=False,
                should_finish=False,
                message=f"Unknown action: {action_name}",
            )

        block_reason = self._privacy_guard(
            action, action_name, screen_width, screen_height, privacy_metadata
        )
        if block_reason:
            return ActionResult(
                success=False,
                should_finish=False,
                message=block_reason,
            )

        try:
            return handler_method(action, screen_width, screen_height)
        except Exception as e:
            return ActionResult(
                success=False, should_finish=False, message=f"Action failed: {e}"
            )

    def _get_handler(self, action_name: str) -> Callable | None:
        """Get the handler method for an action."""
        handlers = {
            "Launch": self._handle_launch,
            "Tap": self._handle_tap,
            "Type": self._handle_type,
            "Type_Name": self._handle_type,
            "Swipe": self._handle_swipe,
            "Back": self._handle_back,
            "Home": self._handle_home,
            "Double Tap": self._handle_double_tap,
            "Long Press": self._handle_long_press,
            "Wait": self._handle_wait,
            "Take_over": self._handle_takeover,
            "Note": self._handle_note,
            "Call_API": self._handle_call_api,
            "Interact": self._handle_interact,
        }
        return handlers.get(action_name)

    def _privacy_guard(
        self,
        action: dict[str, Any],
        action_name: str | None,
        screen_width: int,
        screen_height: int,
        privacy_metadata: dict[str, Any] | None,
    ) -> str | None:
        """Apply minimal privacy guard before action execution."""
        if not isinstance(privacy_metadata, dict):
            return None

        matched_rules = privacy_metadata.get("matched_rules", [])

        if not isinstance(matched_rules, list) or not matched_rules:
            return None

        high_sensitivity_types = self._get_high_sensitivity_types(matched_rules)

        # Guard typing whenever high-sensitivity rules are matched.
        if action_name in {"Type", "Type_Name"} and high_sensitivity_types:
            text = str(action.get("text", ""))
            if self._contains_restricted_sensitive_text(text, high_sensitivity_types):
                return "Action blocked by privacy guard: matched_rules contain high-sensitivity fields and Type text looks like real sensitive data"

        # Guard tapping into sensitive regions if server provides region coordinates.
        if action_name in {"Tap", "Double Tap", "Long Press"}:
            element = action.get("element")
            if isinstance(element, list) and len(element) >= 2:
                x, y = self._convert_relative_to_absolute(element, screen_width, screen_height)
                for rule in matched_rules:
                    regions = self._extract_rule_regions(rule, screen_width, screen_height)
                    if any(self._point_in_region(x, y, region) for region in regions):
                        return "Action blocked by privacy guard: tap target is inside sensitive region"

        return None

    @staticmethod
    def _get_high_sensitivity_types(matched_rules: list[Any]) -> set[str]:
        """Extract high-sensitivity categories from matched rules."""
        categories: set[str] = set()
        for rule in matched_rules:
            if not isinstance(rule, dict):
                continue

            doc = str(rule.get("document", ""))
            target = str(rule.get("target_field", ""))
            text = f"{doc} {target}"

            if any(keyword in text for keyword in ["身份证", "证件号", "身份证号"]):
                categories.add("id")
            if any(keyword in text for keyword in ["银行卡", "卡号", "bank"]):
                categories.add("bank")
            if any(keyword in text for keyword in ["详细地址", "收货地址", "家庭住址", "地址"]):
                categories.add("address")

        return categories

    @staticmethod
    def _contains_restricted_sensitive_text(text: str, sensitivity_types: set[str]) -> bool:
        """Check whether Type payload appears to contain restricted sensitive data."""
        normalized = text.strip()
        if not normalized:
            return False

        if "id" in sensitivity_types and re.search(r"\b\d{17}[0-9Xx]\b", normalized):
            return True

        # Common bank card length ranges from 12 to 19 digits.
        if "bank" in sensitivity_types and re.search(r"\b\d{12,19}\b", normalized):
            return True

        if "address" in sensitivity_types:
            if len(normalized) >= 8 and any(
                kw in normalized for kw in ["省", "市", "区", "县", "路", "街", "巷", "号", "栋", "室"]
            ):
                return True

        return False

    def _extract_rule_regions(
        self, rule: Any, screen_width: int, screen_height: int
    ) -> list[tuple[int, int, int, int]]:
        """Extract sensitive regions from matched rule payload."""
        if not isinstance(rule, dict):
            return []

        raw_regions = []
        for key in ("regions", "bbox", "box", "rect", "region"):
            value = rule.get(key)
            if value is None:
                continue
            if key == "regions" and isinstance(value, list):
                raw_regions.extend(value)
            else:
                raw_regions.append(value)

        regions: list[tuple[int, int, int, int]] = []
        for item in raw_regions:
            parsed = self._parse_region(item, screen_width, screen_height)
            if parsed is not None:
                regions.append(parsed)
        return regions

    def _parse_region(
        self, region: Any, screen_width: int, screen_height: int
    ) -> tuple[int, int, int, int] | None:
        """Parse region definitions from dict/list forms into absolute pixel box."""
        values: list[float] | None = None

        if isinstance(region, dict):
            keys = ["x1", "y1", "x2", "y2"]
            if all(k in region for k in keys):
                values = [region[k] for k in keys]
            else:
                alt_keys = ["left", "top", "right", "bottom"]
                if all(k in region for k in alt_keys):
                    values = [region[k] for k in alt_keys]
        elif isinstance(region, list) and len(region) >= 4:
            values = region[:4]

        if values is None:
            return None

        try:
            x1 = self._scale_coord(float(values[0]), screen_width)
            y1 = self._scale_coord(float(values[1]), screen_height)
            x2 = self._scale_coord(float(values[2]), screen_width)
            y2 = self._scale_coord(float(values[3]), screen_height)
        except (TypeError, ValueError):
            return None

        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        return left, top, right, bottom

    @staticmethod
    def _scale_coord(value: float, span: int) -> int:
        """Convert normalized or relative coordinates to absolute pixel coordinates."""
        if 0.0 <= value <= 1.0:
            return int(value * span)
        if 1.0 < value <= 1000.0:
            return int(value / 1000.0 * span)
        return int(value)

    @staticmethod
    def _point_in_region(x: int, y: int, region: tuple[int, int, int, int]) -> bool:
        """Check whether a point is inside a rectangular region."""
        left, top, right, bottom = region
        return left <= x <= right and top <= y <= bottom

    def _convert_relative_to_absolute(
        self, element: list[int], screen_width: int, screen_height: int
    ) -> tuple[int, int]:
        """Convert relative coordinates (0-1000) to absolute pixels."""
        x = int(element[0] / 1000 * screen_width)
        y = int(element[1] / 1000 * screen_height)
        return x, y

    def _handle_launch(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle app launch action."""
        app_name = action.get("app")
        if not app_name:
            return ActionResult(False, False, "No app name specified")

        device_factory = get_device_factory()
        success = device_factory.launch_app(app_name, self.device_id)
        if success:
            return ActionResult(True, False)
        return ActionResult(False, False, f"App not found: {app_name}")

    def _handle_tap(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle tap action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)

        # Check for sensitive operation
        if "message" in action:
            if not self.confirmation_callback(action["message"]):
                return ActionResult(
                    success=False,
                    should_finish=True,
                    message="User cancelled sensitive operation",
                )

        device_factory = get_device_factory()
        device_factory.tap(x, y, self.device_id)
        return ActionResult(True, False)

    def _handle_type(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle text input action."""
        text = action.get("text", "")

        device_factory = get_device_factory()

        # Switch to ADB keyboard
        original_ime = device_factory.detect_and_set_adb_keyboard(self.device_id)
        time.sleep(TIMING_CONFIG.action.keyboard_switch_delay)

        # Clear existing text and type new text
        device_factory.clear_text(self.device_id)
        time.sleep(TIMING_CONFIG.action.text_clear_delay)

        # Handle multiline text by splitting on newlines
        device_factory.type_text(text, self.device_id)
        time.sleep(TIMING_CONFIG.action.text_input_delay)

        # Restore original keyboard
        device_factory.restore_keyboard(original_ime, self.device_id)
        time.sleep(TIMING_CONFIG.action.keyboard_restore_delay)

        return ActionResult(True, False)

    def _handle_swipe(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle swipe action."""
        start = action.get("start")
        end = action.get("end")

        if not start or not end:
            return ActionResult(False, False, "Missing swipe coordinates")

        start_x, start_y = self._convert_relative_to_absolute(start, width, height)
        end_x, end_y = self._convert_relative_to_absolute(end, width, height)

        device_factory = get_device_factory()
        device_factory.swipe(start_x, start_y, end_x, end_y, device_id=self.device_id)
        return ActionResult(True, False)

    def _handle_back(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle back button action."""
        device_factory = get_device_factory()
        device_factory.back(self.device_id)
        return ActionResult(True, False)

    def _handle_home(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle home button action."""
        device_factory = get_device_factory()
        device_factory.home(self.device_id)
        return ActionResult(True, False)

    def _handle_double_tap(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle double tap action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)
        device_factory = get_device_factory()
        device_factory.double_tap(x, y, self.device_id)
        return ActionResult(True, False)

    def _handle_long_press(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle long press action."""
        element = action.get("element")
        if not element:
            return ActionResult(False, False, "No element coordinates")

        x, y = self._convert_relative_to_absolute(element, width, height)
        device_factory = get_device_factory()
        device_factory.long_press(x, y, device_id=self.device_id)
        return ActionResult(True, False)

    def _handle_wait(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle wait action."""
        duration_str = action.get("duration", "1 seconds")
        try:
            duration = float(duration_str.replace("seconds", "").strip())
        except ValueError:
            duration = 1.0

        time.sleep(duration)
        return ActionResult(True, False)

    def _handle_takeover(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle takeover request (login, captcha, etc.)."""
        message = action.get("message", "User intervention required")
        self.takeover_callback(message)
        return ActionResult(True, False)

    def _handle_note(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle note action (placeholder for content recording)."""
        # This action is typically used for recording page content
        # Implementation depends on specific requirements
        return ActionResult(True, False)

    def _handle_call_api(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle API call action (placeholder for summarization)."""
        # This action is typically used for content summarization
        # Implementation depends on specific requirements
        return ActionResult(True, False)

    def _handle_interact(self, action: dict, width: int, height: int) -> ActionResult:
        """Handle interaction request (user choice needed)."""
        # This action signals that user input is needed
        return ActionResult(True, False, message="User interaction required")

    def _send_keyevent(self, keycode: str) -> None:
        """Send a keyevent to the device."""
        from phone_agent.device_factory import DeviceType, get_device_factory
        from phone_agent.hdc.connection import _run_hdc_command

        device_factory = get_device_factory()

        # Handle HDC devices with HarmonyOS-specific keyEvent command
        if device_factory.device_type == DeviceType.HDC:
            hdc_prefix = ["hdc", "-t", self.device_id] if self.device_id else ["hdc"]
            
            # Map common keycodes to HarmonyOS keyEvent codes
            # KEYCODE_ENTER (66) -> 2054 (HarmonyOS Enter key code)
            if keycode == "KEYCODE_ENTER" or keycode == "66":
                _run_hdc_command(
                    hdc_prefix + ["shell", "uitest", "uiInput", "keyEvent", "2054"],
                    capture_output=True,
                    text=True,
                )
            else:
                # For other keys, try to use the numeric code directly
                # If keycode is a string like "KEYCODE_ENTER", convert it
                try:
                    # Try to extract numeric code from string or use as-is
                    if keycode.startswith("KEYCODE_"):
                        # For now, only handle ENTER, other keys may need mapping
                        if "ENTER" in keycode:
                            _run_hdc_command(
                                hdc_prefix + ["shell", "uitest", "uiInput", "keyEvent", "2054"],
                                capture_output=True,
                                text=True,
                            )
                        else:
                            # Fallback to ADB-style command for unsupported keys
                            subprocess.run(
                                hdc_prefix + ["shell", "input", "keyevent", keycode],
                                capture_output=True,
                                text=True,
                            )
                    else:
                        # Assume it's a numeric code
                        _run_hdc_command(
                            hdc_prefix + ["shell", "uitest", "uiInput", "keyEvent", str(keycode)],
                            capture_output=True,
                            text=True,
                        )
                except Exception:
                    # Fallback to ADB-style command
                    subprocess.run(
                        hdc_prefix + ["shell", "input", "keyevent", keycode],
                        capture_output=True,
                        text=True,
                    )
        else:
            # ADB devices use standard input keyevent command
            cmd_prefix = ["adb", "-s", self.device_id] if self.device_id else ["adb"]
            subprocess.run(
                cmd_prefix + ["shell", "input", "keyevent", keycode],
                capture_output=True,
                text=True,
            )

    @staticmethod
    def _default_confirmation(message: str) -> bool:
        """Default confirmation callback using console input."""
        response = input(f"Sensitive operation: {message}\nConfirm? (Y/N): ")
        return response.upper() == "Y"

    @staticmethod
    def _default_takeover(message: str) -> None:
        """Default takeover callback using console input."""
        input(f"{message}\nPress Enter after completing manual operation...")


def parse_action(response: str) -> dict[str, Any]:
    """
    Parse action from model response.

    Args:
        response: Raw response string from the model.

    Returns:
        Parsed action dictionary.

    Raises:
        ValueError: If the response cannot be parsed.
    """
    print(f"Parsing action: {response}")
    try:
        response = response.strip()
        if response.startswith('do(action="Type"') or response.startswith(
            'do(action="Type_Name"'
        ):
            text = response.split("text=", 1)[1][1:-2]
            action = {"_metadata": "do", "action": "Type", "text": text}
            return action
        elif response.startswith("do"):
            # Use AST parsing instead of eval for safety
            try:
                # Escape special characters (newlines, tabs, etc.) for valid Python syntax
                response = response.replace('\n', '\\n')
                response = response.replace('\r', '\\r')
                response = response.replace('\t', '\\t')

                tree = ast.parse(response, mode="eval")
                if not isinstance(tree.body, ast.Call):
                    raise ValueError("Expected a function call")

                call = tree.body
                # Extract keyword arguments safely
                action = {"_metadata": "do"}
                for keyword in call.keywords:
                    key = keyword.arg
                    value = ast.literal_eval(keyword.value)
                    action[key] = value

                return action
            except (SyntaxError, ValueError) as e:
                raise ValueError(f"Failed to parse do() action: {e}")

        elif response.startswith("finish"):
            action = {
                "_metadata": "finish",
                "message": response.replace("finish(message=", "")[1:-2],
            }
        else:
            raise ValueError(f"Failed to parse action: {response}")
        return action
    except Exception as e:
        raise ValueError(f"Failed to parse action: {e}")


def do(**kwargs) -> dict[str, Any]:
    """Helper function for creating 'do' actions."""
    kwargs["_metadata"] = "do"
    return kwargs


def finish(**kwargs) -> dict[str, Any]:
    """Helper function for creating 'finish' actions."""
    kwargs["_metadata"] = "finish"
    return kwargs

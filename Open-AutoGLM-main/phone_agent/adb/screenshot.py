"""Screenshot utilities for capturing Android device screen."""

import base64
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from PIL import Image

try:
    from privacy_proxy import PrivacyProxy

    _privacy_proxy = PrivacyProxy()
except Exception:
    _privacy_proxy = None


@dataclass
class Screenshot:
    """Represents a captured screenshot."""

    base64_data: str
    width: int
    height: int
    is_sensitive: bool = False
    privacy_metadata: dict[str, Any] = field(default_factory=dict)


def _get_max_image_side() -> int:
    """Get max allowed image side length from env, defaulting to 2048."""
    raw = os.getenv("PHONE_AGENT_MAX_IMAGE_SIDE", "2048").strip()
    try:
        value = int(raw)
        return max(64, value)
    except ValueError:
        return 2048


def _resize_if_needed(img: Image.Image, max_side: int) -> Image.Image:
    """Resize image to fit within max_side while preserving aspect ratio."""
    width, height = img.size
    max_current_side = max(width, height)

    if max_current_side <= max_side:
        return img

    scale = max_side / float(max_current_side)
    new_width = max(1, int(width * scale))
    new_height = max(1, int(height * scale))

    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def get_screenshot(device_id: str | None = None, timeout: int = 10) -> Screenshot:
    """
    Capture a screenshot from the connected Android device.

    Args:
        device_id: Optional ADB device ID for multi-device setups.
        timeout: Timeout in seconds for screenshot operations.

    Returns:
        Screenshot object containing base64 data and dimensions.

    Note:
        If the screenshot fails (e.g., on sensitive screens like payment pages),
        a black fallback image is returned with is_sensitive=True.
    """
    temp_path = os.path.join(tempfile.gettempdir(), f"screenshot_{uuid.uuid4()}.png")
    adb_prefix = _get_adb_prefix(device_id)

    try:
        # Execute screenshot command
        result = subprocess.run(
            adb_prefix + ["shell", "screencap", "-p", "/sdcard/tmp.png"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Check for screenshot failure (sensitive screen)
        output = result.stdout + result.stderr
        if "Status: -1" in output or "Failed" in output:
            return _create_fallback_screenshot(is_sensitive=True)

        # Pull screenshot to local temp path
        subprocess.run(
            adb_prefix + ["pull", "/sdcard/tmp.png", temp_path],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if not os.path.exists(temp_path):
            return _create_fallback_screenshot(is_sensitive=False)

        # Read raw screenshot first so action coordinates can stay in device space.
        img = Image.open(temp_path)
        raw_width, raw_height = img.size

        # Apply privacy processing. If service output changes size/aspect ratio,
        # force it back to the raw geometry to keep coordinate space stable.
        privacy_metadata: dict[str, Any] = {}
        if _privacy_proxy is not None:
            img, privacy_metadata = _privacy_proxy.process_pil_image_with_metadata(img)
            if img.size != (raw_width, raw_height):
                img = img.resize((raw_width, raw_height), Image.Resampling.LANCZOS)

        # Resize only for model input-limit compliance.
        img = _resize_if_needed(img, _get_max_image_side())

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        base64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # Cleanup
        os.remove(temp_path)

        return Screenshot(
            base64_data=base64_data,
            width=raw_width,
            height=raw_height,
            is_sensitive=False,
            privacy_metadata=privacy_metadata,
        )

    except Exception as e:
        print(f"Screenshot error: {e}")
        return _create_fallback_screenshot(is_sensitive=False)


def _get_adb_prefix(device_id: str | None) -> list:
    """Get ADB command prefix with optional device specifier."""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]


def _create_fallback_screenshot(is_sensitive: bool) -> Screenshot:
    """Create a black fallback image when screenshot fails."""
    default_width, default_height = 1080, 2400
    max_side = _get_max_image_side()

    black_img = Image.new("RGB", (default_width, default_height), color="black")
    black_img = _resize_if_needed(black_img, max_side)
    width, height = black_img.size
    buffered = BytesIO()
    black_img.save(buffered, format="PNG")
    base64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return Screenshot(
        base64_data=base64_data,
        width=width,
        height=height,
        is_sensitive=is_sensitive,
        privacy_metadata={},
    )

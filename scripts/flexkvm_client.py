#!/usr/bin/env python3
"""
FlexKVM Python client wrapper.
Provides a friendly API for remote control of target machines through the
FlexKVM agent HTTPS interface (agent module).

Environment variables:
    FlexKVM_IP: FlexKVM device IP (required, e.g. 192.168.x.x)
    FlexKVM_TOKEN: FlexKVM agent API key (required, sk- + 32 hex)
                   generated in the device web UI (Settings -> Agent)

Example:
    from flexkvm_client import FlexKVMClient

    client = FlexKVMClient()

    client.screenshot("desktop.jpeg")

    client.click(0.5, 0.5)

    client.text("This text is typed synchronously by the device")

    client.key_combo("ctrl", "c")

    client.run_command("notepad")

Notes:
- Self-signed TLS on the default HTTPS port (443): all requests skip certificate verification
- Text events complete synchronously on the device; no chunking required
- Coordinates are normalized [0.0, 1.0], origin at top-left
"""

import os
import sys
import warnings

import requests
from typing import List, Optional, Union

DEFAULT_FLEXKVM_PORT = 443
MAX_EVENTS = 32          # device-side per-request limit
MAX_TEXT_LENGTH = 1024   # device-side text event limit

# py3 urllib3 warnings type
try:
    InsecureRequestWarning = requests.packages.urllib3.exceptions.InsecureRequestWarning
except AttributeError:
    InsecureRequestWarning = None

if InsecureRequestWarning is not None:
    warnings.filterwarnings("ignore", category=InsecureRequestWarning)


def resolve_flexkvm_url(ip: Optional[str] = None,
                        port: int = DEFAULT_FLEXKVM_PORT) -> str:
    resolved_ip = ip or os.getenv("FlexKVM_IP")
    if not resolved_ip:
        raise ValueError(
            "Missing FlexKVM_IP. Set the environment variable FlexKVM_IP "
            "or pass ip to FlexKVMClient."
        )
    return f"https://{resolved_ip}:{port}"


class FlexKVMClient:
    """FlexKVM agent HTTP API client."""

    MOD_CTRL = "ctrl"
    MOD_SHIFT = "shift"
    MOD_ALT = "alt"
    MOD_WIN = "win"
    KEY_ENTER = "enter"
    KEY_ESC = "esc"
    KEY_TAB = "tab"
    KEY_SPACE = "space"
    KEY_BACKSPACE = "backspace"

    def __init__(self, ip: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize the client.

        Args:
            ip: FlexKVM device IP, defaults to env var FlexKVM_IP.
            token: Agent API key, defaults to env var FlexKVM_TOKEN.
        """
        self.url = resolve_flexkvm_url(ip=ip)
        self.token = token or os.getenv("FlexKVM_TOKEN")
        self.session = requests.Session()
        if not self.token:
            raise ValueError(
                "Missing FlexKVM_TOKEN. Set the environment variable "
                "FlexKVM_TOKEN or pass token to FlexKVMClient."
            )
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    @staticmethod
    def _validate_unit_interval(name: str, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be in [0.0, 1.0], got: {value}")

    @staticmethod
    def _validate_dy(name: str, value: int) -> None:
        if not -127 <= value <= 127:
            raise ValueError(f"{name} must be in [-127, 127], got: {value}")

    @staticmethod
    def _validate_text_content(content: str) -> None:
        if not isinstance(content, str):
            raise ValueError("text value must be a string")
        if not (1 <= len(content) <= MAX_TEXT_LENGTH):
            raise ValueError(
                f"text event length must be 1..{MAX_TEXT_LENGTH}, got: {len(content)}"
            )
        for ch in content:
            code = ord(ch)
            if not 32 <= code <= 126:
                raise ValueError(
                    "text event only supports printable ASCII (32~126); "
                    "use hotkey for Tab/Enter."
                )

    @staticmethod
    def _validate_events(events: List[dict]) -> None:
        if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
            raise ValueError(
                f"events must be a non-empty list of at most {MAX_EVENTS} items"
            )

    def _request_json(self, method: str, endpoint: str, timeout: int = 60,
                      **kwargs) -> dict:
        url = f"{self.url}{endpoint}"
        response = self.session.request(method, url, timeout=timeout,
                                        verify=False, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}

    def _request_bytes(self, method: str, endpoint: str, timeout: int = 15,
                       **kwargs) -> bytes:
        url = f"{self.url}{endpoint}"
        response = self.session.request(method, url, timeout=timeout,
                                        verify=False, **kwargs)
        response.raise_for_status()
        return response.content

    def state(self) -> dict:
        """Query agent/keyboard/mouse state (mode, resolution, locks)."""
        return self._request_json("GET", "/api/v1/agent/state", timeout=10)

    def screenshot(self, save_path: Optional[str] = None) -> bytes:
        """
        Capture a screenshot (raw JPEG bytes).

        Args:
            save_path: Optional file path to save the image. Returns raw bytes
                if None.

        Returns:
            JPEG image binary data.
        """
        data = self._request_bytes("GET", "/api/v1/agent/snapshot", timeout=15)
        if save_path:
            with open(save_path, 'wb') as f:
                f.write(data)
            print(f"Screenshot saved: {save_path}")
        return data

    def control(self, events: List[dict]) -> dict:
        """
        Send a sequence of control commands.

        Args:
            events: List of event dicts, e.g.
                [{"type": "click", "button": "left", "x": 0.5, "y": 0.5},
                 {"type": "delay", "ms": 300}]

        Returns:
            API response JSON {"code": 0, "applied": N} or
            {"code": <err>, "applied": N, "error": <msg>}.
        """
        self._validate_events(events)
        result = self._request_json(
            "POST",
            "/api/v1/agent/control",
            json={"events": events},
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        if result.get("code", 0) != 0:
            raise RuntimeError(f"FlexKVM control failed: {result}")
        return result

    def delay(self, milliseconds: int) -> dict:
        """Pause for the specified number of milliseconds (0..5000)."""
        if not 0 <= milliseconds <= 5000:
            raise ValueError("delay ms must be in [0, 5000]")
        return self.control([{"type": "delay", "ms": milliseconds}])

    def move(self, x: float, y: float) -> dict:
        """Move the mouse to absolute coordinates [0.0, 1.0]."""
        self._validate_unit_interval("x", x)
        self._validate_unit_interval("y", y)
        return self.control([{"type": "move", "x": x, "y": y}])

    def click(self, x: float, y: float, button: str = "left",
              double: bool = False, post_delay: int = 200) -> dict:
        """
        Click (or double-click) at a position.

        Args:
            x: Absolute X coordinate [0.0, 1.0].
            y: Absolute Y coordinate [0.0, 1.0].
            button: "left" (default), "right" or "middle".
            double: True for a double click.
            post_delay: Delay (ms) after the click sequence.
        """
        self._validate_unit_interval("x", x)
        self._validate_unit_interval("y", y)
        if button not in ("left", "right", "middle"):
            raise ValueError(f"button must be left/right/middle, got: {button}")
        events = [{"type": "dblclick" if double else "click",
                   "button": button, "x": x, "y": y}]
        if post_delay > 0:
            events.append({"type": "delay", "ms": post_delay})
        return self.control(events)

    def scroll(self, dy: int = 0) -> dict:
        """Scroll the mouse wheel vertically (dy in [-127, 127])."""
        self._validate_dy("dy", dy)
        return self.control([{"type": "scroll", "dy": dy}])

    def text(self, content: str) -> dict:
        """
        Input text (synchronous on the device; printable ASCII only).

        Args:
            content: Text to type, 1..1024 printable ASCII characters.
        """
        self._validate_text_content(content)
        return self.control([{"type": "text", "value": content}])

    def hotkey(self, keys: List[str]) -> dict:
        """
        Press a key combination atomically (modifiers + key names, lowercase).

        Args:
            keys: e.g. ["ctrl", "c"], ["win", "r"], ["enter"], ["win"].
        """
        if not isinstance(keys, list) or not keys:
            raise ValueError("hotkey keys must be a non-empty list")
        if len(keys) > 7:  # 6 non-modifier keys + modifiers
            raise ValueError("hotkey accepts at most 6 non-modifier keys")
        for k in keys:
            if not isinstance(k, str) or not k:
                raise ValueError(f"invalid hotkey key name: {k!r}")
        return self.control([{"type": "hotkey", "keys": keys}])

    def key_combo(self, *keys: str, post_delay: int = 100) -> dict:
        """Alias for hotkey with positional key names."""
        return self.hotkey(list(keys))

    def run_command(self, command: str, wait: int = 1500) -> dict:
        """
        Run a command via Win+R.

        Args:
            command: The command to run (e.g. "notepad", "cmd /c ipconfig").
            wait: Wait time (ms) after the Run dialog opens.
        """
        self._validate_text_content(command)
        if not (0 <= wait <= 5000):
            raise ValueError("wait must be in [0, 5000]")
        return self.control([
            {"type": "hotkey", "keys": ["win", "r"]},
            {"type": "delay", "ms": wait},
            {"type": "text", "value": command},
            {"type": "hotkey", "keys": ["enter"]},
        ])

    def type_key(self, key: str) -> dict:
        """Press a single key by name, e.g. type_key("enter")."""
        return self.hotkey([key])


def quick_text(text: str, ip: Optional[str] = None,
               token: Optional[str] = None) -> dict:
    """Quick text input."""
    return FlexKVMClient(ip=ip, token=token).text(text)


def quick_screenshot(save_path: str = "screen.jpeg", ip: Optional[str] = None,
                     token: Optional[str] = None) -> bytes:
    """Quick screenshot capture."""
    return FlexKVMClient(ip=ip, token=token).screenshot(save_path)


if __name__ == "__main__":
    client = FlexKVMClient()

    if len(sys.argv) < 2:
        print("FlexKVM Client - Remote Control Tool")
        print()
        print("Usage: python flexkvm_client.py <command> [args]")
        print()
        print("Commands:")
        print("  screenshot [path]       - Capture screenshot (default: screen.jpeg)")
        print("  state                   - Print agent state JSON")
        print("  text <content>          - Input text (synchronous)")
        print("  run <command>           - Run a command via Win+R")
        print("  click <x> <y> [button]  - Click at position (0-1 absolute coords)")
        print("  scroll <dy>             - Scroll mouse wheel")
        print("  hotkey <key1> <key2>... - Send a key combination")
        print()
        print("Environment:")
        print("  FlexKVM_IP - FlexKVM device IP (required, e.g. 192.168.x.x)")
        print("  FlexKVM_TOKEN - Agent API key (required, sk- + 32 hex)")
        print()
        print("Examples:")
        print('  python flexkvm_client.py text "Hello World"')
        print('  python flexkvm_client.py run notepad')
        print('  python flexkvm_client.py click 0.5 0.5')
        print('  python flexkvm_client.py hotkey win r')
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "screenshot":
        path = sys.argv[2] if len(sys.argv) > 2 else "screen.jpeg"
        client.screenshot(path)

    elif cmd == "state":
        import json
        print(json.dumps(client.state(), indent=2, ensure_ascii=False))

    elif cmd == "text":
        if len(sys.argv) < 3:
            print("Error: text content is required")
            sys.exit(1)
        content = sys.argv[2]
        result = client.text(content)
        print(f"Input {len(content)} characters")
        print(f"Response: {result}")

    elif cmd == "run":
        if len(sys.argv) < 3:
            print("Error: command is required")
            sys.exit(1)
        result = client.run_command(sys.argv[2])
        print(f"Response: {result}")

    elif cmd == "click":
        if len(sys.argv) < 4:
            print("Error: x and y coordinates required")
            sys.exit(1)
        x, y = float(sys.argv[2]), float(sys.argv[3])
        button = sys.argv[4] if len(sys.argv) > 4 else "left"
        result = client.click(x, y, button=button)
        print(f"Response: {result}")

    elif cmd == "scroll":
        if len(sys.argv) < 3:
            print("Error: dy required")
            sys.exit(1)
        result = client.scroll(int(sys.argv[2]))
        print(f"Response: {result}")

    elif cmd == "hotkey":
        if len(sys.argv) < 3:
            print("Error: at least one key required")
            sys.exit(1)
        keys = sys.argv[2:]
        result = client.hotkey(keys)
        print(f"Hotkey {'+'.join(keys)} sent")
        print(f"Response: {result}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
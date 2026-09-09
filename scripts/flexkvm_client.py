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

    # Press-and-hold (held state persists across requests)
    client.mouse_down(0.2, 0.5)        # press (atomic move + press)
    client.move(0.4, 0.6)              # drag while held, separate request ok
    client.mouse_up()                  # release

    client.drag(0.2, 0.5, 0.8, 0.5)    # composite drag (device interpolates)

    client.key_down("shift")           # Shift+click via separate requests
    client.click(0.5, 0.5)
    client.key_up("shift")

    client.release_all()               # safety net: clear all held state

Notes:
- Self-signed TLS on the default HTTPS port (443): all requests skip certificate verification
- Text events complete synchronously on the device; no chunking required
- Coordinates are normalized [0.0, 1.0], origin at top-left
- Held buttons/keys persist across requests until released; cancel does NOT
  auto-release — call release_all() after an interrupted drag
"""

import os
import sys
import warnings

import requests
from typing import List, Optional, Union

DEFAULT_FLEXKVM_PORT = 443
MAX_EVENTS = 32          # device-side per-request limit
MAX_TEXT_LENGTH = 512    # device-side text event limit

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
                [{"type": "mouse", "action": "click", "button": "left",
                  "x": 0.5, "y": 0.5},
                 {"type": "delay", "ms": 300}]

        Returns:
            API response JSON {"code": 0, "applied": N} or
            {"code": 0, "applied": N, "error": <msg>} when the batch stopped
            early (e.g. "event failed", "cancelled", "request timeout").
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

    def cancel(self) -> dict:
        """
        Abort the currently executing control batch (idempotent).

        Returns:
            {"code": 0, "status": 0, "cancelled": bool}; cancelled is False when
            no batch was running. The aborted control() call returns
            applied + error: "cancelled".
        """
        return self._request_json("POST", "/api/v1/agent/cancel", timeout=10)

    def delay(self, milliseconds: int) -> dict:
        """Pause for the specified number of milliseconds (0..5000)."""
        if not 0 <= milliseconds <= 5000:
            raise ValueError("delay ms must be in [0, 5000]")
        return self.control([{"type": "delay", "ms": milliseconds}])

    def move(self, x: float, y: float) -> dict:
        """Move the mouse to absolute coordinates [0.0, 1.0]."""
        self._validate_unit_interval("x", x)
        self._validate_unit_interval("y", y)
        return self.control([{"type": "mouse", "action": "move",
                              "x": x, "y": y}])

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
        events = [{"type": "mouse", "action": "click",
                   "button": button, "x": x, "y": y, "dblclick": double}]
        if post_delay > 0:
            events.append({"type": "delay", "ms": post_delay})
        return self.control(events)

    def scroll(self, dy: int = 0) -> dict:
        """Scroll the mouse wheel vertically (dy in [-127, 127])."""
        self._validate_dy("dy", dy)
        return self.control([{"type": "mouse", "action": "scroll",
                              "dy": dy}])

    def text(self, content: str) -> dict:
        """
        Input text (synchronous on the device; printable ASCII only).

        Args:
            content: Text to type, 1..512 printable ASCII characters.
        """
        self._validate_text_content(content)
        return self.control([{"type": "keyboard", "action": "text",
                              "value": content}])

    def hotkey(self, keys: List[str]) -> dict:
        """
        Press a key combination atomically (modifiers + key names, lowercase).

        Args:
            keys: e.g. ["ctrl", "c"], ["win", "r"], ["enter"], ["win"].
        """
        if not isinstance(keys, list) or not keys:
            raise ValueError("hotkey keys must be a non-empty list")
        for k in keys:
            if not isinstance(k, str) or not k:
                raise ValueError(f"invalid hotkey key name: {k!r}")
        # Device limit: at most 6 non-modifier keys; modifiers are unlimited
        modifiers = {"ctrl", "control", "shift", "alt", "win", "meta", "cmd"}
        normal_count = sum(1 for k in keys if k not in modifiers)
        if normal_count > 6:
            raise ValueError("hotkey accepts at most 6 non-modifier keys")
        return self.control([{"type": "keyboard", "action": "hotkey",
                              "keys": keys}])

    def key_combo(self, *keys: str, post_delay: int = 100) -> dict:
        """Alias for hotkey with positional key names."""
        return self.hotkey(list(keys))

    def mouse_down(self, x: Optional[float] = None, y: Optional[float] = None,
                   button: str = "left") -> dict:
        """
        Press and hold a mouse button (held until mouse_up/release_all).

        Held state persists across requests. Optional x/y must be given
        together: when present the pointer moves first (atomic move+press,
        useful for starting a drag without a separate move event).

        Args:
            x: Optional absolute X coordinate [0.0, 1.0].
            y: Optional absolute Y coordinate [0.0, 1.0].
            button: "left" (default), "right" or "middle".
        """
        if (x is None) != (y is None):
            raise ValueError("x and y must be provided together")
        if button not in ("left", "right", "middle"):
            raise ValueError(f"button must be left/right/middle, got: {button}")
        event = {"type": "mouse", "action": "down", "button": button}
        if x is not None:
            self._validate_unit_interval("x", x)
            self._validate_unit_interval("y", y)
            event["x"] = x
            event["y"] = y
        return self.control([event])

    def mouse_up(self, button: str = "left") -> dict:
        """
        Release a held mouse button (idempotent).

        Only the named button is released; other held buttons stay held.
        """
        if button not in ("left", "right", "middle"):
            raise ValueError(f"button must be left/right/middle, got: {button}")
        return self.control([{"type": "mouse", "action": "up",
                              "button": button}])

    def key_down(self, key: str) -> dict:
        """
        Press and hold a key (held until key_up/release_all).

        Held state persists across requests, e.g. key_down("shift") +
        click() in a later request performs Shift+click.

        Args:
            key: Single key or modifier name (see references/key_names.md),
                e.g. "shift", "ctrl", "a", "f5".
        """
        if not isinstance(key, str) or not key:
            raise ValueError(f"invalid key name: {key!r}")
        return self.control([{"type": "keyboard", "action": "down",
                              "key": key}])

    def key_up(self, key: str) -> dict:
        """Release a held key (idempotent)."""
        if not isinstance(key, str) or not key:
            raise ValueError(f"invalid key name: {key!r}")
        return self.control([{"type": "keyboard", "action": "up",
                              "key": key}])

    def release_all(self) -> dict:
        """
        Release every held mouse button and key (idempotent safety net).

        Send this whenever an operation is interrupted mid-drag: cancel
        does NOT auto-release held state.
        """
        return self.control([{"type": "release_all"}])

    def drag(self, from_x: float, from_y: float, to_x: float, to_y: float,
             button: str = "left", duration_ms: int = 300) -> dict:
        """
        Composite drag: press at the start, interpolate moves to the end,
        then release (single device-side event; preferred over manual
        mouse down/move/up composition — many target UIs drop drags
        when pointer jumps are too coarse).

        On cancel/interrupt the button stays held; use release_all().

        Args:
            from_x: Start X coordinate [0.0, 1.0].
            from_y: Start Y coordinate [0.0, 1.0].
            to_x: End X coordinate [0.0, 1.0].
            to_y: End Y coordinate [0.0, 1.0].
            button: "left" (default), "right" or "middle".
            duration_ms: Interpolation duration 0..5000 (0 = point-jump
                drag; intermediate samples are still sent).
        """
        for name, value in (("from_x", from_x), ("from_y", from_y),
                            ("to_x", to_x), ("to_y", to_y)):
            self._validate_unit_interval(name, value)
        if button not in ("left", "right", "middle"):
            raise ValueError(f"button must be left/right/middle, got: {button}")
        if not 0 <= duration_ms <= 5000:
            raise ValueError("duration_ms must be in [0, 5000]")
        return self.control([{
            "type": "mouse", "action": "drag", "button": button,
            "from": [from_x, from_y], "to": [to_x, to_y],
            "duration_ms": duration_ms,
        }])

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
            {"type": "keyboard", "action": "hotkey", "keys": ["win", "r"]},
            {"type": "delay", "ms": wait},
            {"type": "keyboard", "action": "text", "value": command},
            {"type": "keyboard", "action": "hotkey", "keys": ["enter"]},
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
        print("  cancel                  - Abort the in-flight control batch")
        print("  mousedown [x] [y] [btn] - Press and hold a mouse button")
        print("  mouseup [button]        - Release a held mouse button")
        print("  keydown <key>           - Press and hold a key")
        print("  keyup <key>             - Release a held key")
        print("  release_all             - Release all held buttons and keys")
        print("  drag <x1> <y1> <x2> <y2> [ms] [button]")
        print("                          - Composite drag (device interpolates)")
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
        print('  python flexkvm_client.py drag 0.2 0.5 0.8 0.5 400')
        print('  python flexkvm_client.py keydown shift')
        print('  python flexkvm_client.py release_all')
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "screenshot":
        path = sys.argv[2] if len(sys.argv) > 2 else "screen.jpeg"
        client.screenshot(path)

    elif cmd == "state":
        import json
        print(json.dumps(client.state(), indent=2, ensure_ascii=False))

    elif cmd == "cancel":
        result = client.cancel()
        print(f"Cancelled: {result.get('cancelled')}")
        print(f"Response: {result}")

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

    elif cmd == "mousedown":
        x = float(sys.argv[2]) if len(sys.argv) > 2 else None
        y = float(sys.argv[3]) if len(sys.argv) > 3 else None
        button = sys.argv[4] if len(sys.argv) > 4 else "left"
        result = client.mouse_down(x, y, button=button)
        print(f"Response: {result}")

    elif cmd == "mouseup":
        button = sys.argv[2] if len(sys.argv) > 2 else "left"
        result = client.mouse_up(button=button)
        print(f"Response: {result}")

    elif cmd == "keydown":
        if len(sys.argv) < 3:
            print("Error: key name required")
            sys.exit(1)
        result = client.key_down(sys.argv[2])
        print(f"Key {sys.argv[2]} held")
        print(f"Response: {result}")

    elif cmd == "keyup":
        if len(sys.argv) < 3:
            print("Error: key name required")
            sys.exit(1)
        result = client.key_up(sys.argv[2])
        print(f"Response: {result}")

    elif cmd == "release_all":
        result = client.release_all()
        print(f"Response: {result}")

    elif cmd == "drag":
        if len(sys.argv) < 6:
            print("Error: drag requires x1 y1 x2 y2")
            sys.exit(1)
        x1, y1, x2, y2 = (float(v) for v in sys.argv[2:6])
        duration_ms = int(sys.argv[6]) if len(sys.argv) > 6 else 300
        button = sys.argv[7] if len(sys.argv) > 7 else "left"
        result = client.drag(x1, y1, x2, y2, button=button,
                             duration_ms=duration_ms)
        print(f"Response: {result}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
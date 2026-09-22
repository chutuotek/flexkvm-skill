---
name: flexkvm-skill
description: >
  A universal skill for the FlexKVM agent control interface, providing
  screen capture and mouse/keyboard automation via HTTPS API on IP-KVM devices.
  Suitable for remote server management, automated testing, and unattended operations.
  Supports absolute-coordinate mouse control, clicks, press-and-hold (drag),
  scrolling, text input, hotkeys, held keys, and delays with synchronous
  completion semantics.
metadata: { "openclaw": { "emoji": "🖥️" }}
---

# FlexKVM Universal Controller

OpenClaw directly calls the standardized HTTPS interface provided by FlexKVM
(screenshot, keyboard, and mouse control via the agent module) to automate the
remote target machine connected to the KVM. Python scripts are optional helpers.

## Prerequisites

Before using this skill, set the following required environment variables:

- `FlexKVM_IP`
- `FlexKVM_TOKEN` (Agent API Key, generated on the device: **Settings → Agent**)

Without them, the skill can still be recognized and enabled by OpenClaw, but
screenshot and control requests will fail due to missing configuration.

### Bash

```bash
export FlexKVM_IP="192.168.x.x"
export FlexKVM_TOKEN="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### PowerShell (recommended)

> Run in PowerShell before first use:
> ```powershell
> [System.Environment]::SetEnvironmentVariable("FlexKVM_IP", "192.168.x.x", "User")
> [System.Environment]::SetEnvironmentVariable("FlexKVM_TOKEN", "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "User")
> ```

The API key format is `sk-` + 32 hex characters (16 bytes of entropy), generated
in the device web UI. FlexKVM serves HTTPS on the default port (443) with a
self-signed TLS certificate, so clients must skip certificate verification
(`curl -k`, or `verify=False` in Python's requests).

## Execution Rules

When executing this skill, follow this order:

1. Read environment variables `FlexKVM_IP` and `FlexKVM_TOKEN`
2. Compose the base URL: `https://${FlexKVM_IP}`
3. For the device/agent state, call: `GET /api/v1/agent/state`
4. For screenshots, call: `GET /api/v1/agent/snapshot`
5. For control, call: `POST /api/v1/agent/control`
6. To cancel an in-flight control batch, call: `POST /api/v1/agent/cancel`
7. All HTTP requests must include the header: `Authorization: Bearer ${FlexKVM_TOKEN}`

> **Note**:
> - `FlexKVM_IP` and `FlexKVM_TOKEN` in `SKILL.md` are variable names only —
>   they will not be auto-replaced with real values
> - Real values must come from environment variables readable by OpenClaw at runtime
> - After updating environment variables, restart OpenClaw or reopen your terminal
>   before executing
> - The Agent service must be enabled in the device settings (`agent.enable`),
>   otherwise all requests return `403 Forbidden`

**Recommended execution model**:

```text
Read FlexKVM_IP and FlexKVM_TOKEN
-> Compose https://${FlexKVM_IP}
-> Call agent state / snapshot / control endpoints
-> Parse results and continue decision-making
```

## System Architecture

```
┌─────────────┐     HTTPS API      ┌─────────────┐     KVM Signal     ┌─────────────┐
│   OpenClaw  │ ◄────────────────► │   FlexKVM   │ ◄────────────────► │   Target    │
│    (PC)     │                    │  (IP-KVM)   │                    │   Machine   │
└─────────────┘                    └─────────────┘                    └─────────────┘

    HTTPS interface (provided by FlexKVM agent module):
    ├── State endpoint:     GET  /api/v1/agent/state
    ├── Screenshot endpoint:GET  /api/v1/agent/snapshot
    ├── Control endpoint:   POST /api/v1/agent/control
    └── Cancel endpoint:    POST /api/v1/agent/cancel
```

## API Reference

### 1. Agent State

Query the current agent/keyboard/mouse status before operating.

| Property | Value |
|:---|:---|
| URL | `https://${FlexKVM_IP}/api/v1/agent/state` |
| Method | GET |
| Returns | JSON |

**Example**:
```json
{
  "code": 0,
  "enable": true,
  "has_key": true,
  "mode": "idle",
  "user_online": false,
  "width": 1920,
  "height": 1080,
  "mouse_mode": "absolute",
  "caps_lock": false,
  "num_lock": false,
  "scroll_lock": false
}
```

- `mode`: `streaming` (H264 pipeline running, a web user is watching) / `idle` (no pipeline)
- `mouse_mode`: `absolute` / `relative` (relative mode is unsuitable for AI control)
- Screenshots work in both modes: when a pipeline is running the JPEG is taken
  from it; when `mode` is `idle` a single-frame capture path is built on demand
  and torn down right after (roughly +50 ms per shot). A snapshot only fails
  when there is no locked HDMI signal.

### 2. Screenshot

Capture a real-time screen image from the target machine for AI model analysis.

| Property | Value |
|:---|:---|
| URL | `https://${FlexKVM_IP}/api/v1/agent/snapshot` |
| Method | GET |
| Returns | JPEG image binary data (`Content-Type: image/jpeg`) |
| Resolution | `X-Resolution: 1920x1080` response header |

**Example**:
```bash
curl -k -X GET "https://${FlexKVM_IP}/api/v1/agent/snapshot" \
     -H "Authorization: Bearer ${FlexKVM_TOKEN}" -o screen.jpeg
```

### 3. Device Control

Send sequences of mouse, keyboard, and text input control commands.

| Property | Value |
|:---|:---|
| URL | `https://${FlexKVM_IP}/api/v1/agent/control` |
| Method | POST |
| Content-Type | `application/json` |

**Request body**:
```json
{
  "events": [
    {"type": "mouse", "action": "move",    "x": 0.5, "y": 0.5},
    {"type": "mouse", "action": "click",   "button": "left", "x": 0.5, "y": 0.5},
    {"type": "keyboard", "action": "text",    "value": "Hello World"},
    {"type": "delay",   "ms": 300}
  ]
}
```

**Response**:
```json
{
  "code": 0,
  "applied": 4
}
```

- `code`: 0 = the batch ran to completion or stopped on an event-level error
  (HTTP 200); non-zero = the request itself was rejected before execution
- `applied`: number of events applied before the request stopped
- On mid-sequence failure the response carries an `error` field describing the
  failing event (`"event failed"` when the failure has no specific description,
  `"cancelled"` when the batch was aborted, `"request timeout"` when the 60s
  budget ran out); check the presence of `error`, not only `code`

**Request limits** (strict, validated on the device):
- At most **32 events** per request
- Total execution time must stay under **60 seconds**
- Events execute in order; on error or timeout the sequence stops and returns
  the partial result
- An in-flight batch can be aborted from another connection with the cancel
  endpoint (checked at each event boundary)

### 4. Cancel Control

Abort the **currently executing** `control` batch. Idempotent, and a no-op when
no batch is running.

| Property | Value |
|:---|:---|
| URL | `https://${FlexKVM_IP}/api/v1/agent/cancel` |
| Method | POST |
| Body | none |

**Example**:
```bash
curl -ks -X POST "https://${FlexKVM_IP}/api/v1/agent/cancel" \
     -H "Authorization: Bearer ${FlexKVM_TOKEN}"
```

**Response**:
```json
{
  "code": 0,
  "status": 0,
  "cancelled": true
}
```

- `cancelled`: `true` = an active batch was flagged and will stop at its next
  event boundary; `false` = nothing was running
- The aborted `control` request returns `applied` plus `error: "cancelled"`
- Cancellation latency is bounded by one event: `text` is the longest (≈15s for
  a full 512-character payload), while `delay` is sliced to ≤50ms

## Event Types

### Mouse Events

Simulate absolute mouse movement, clicks, double-clicks, press-and-hold, and
scrolling. Coordinates are normalized `[0.0, 1.0]`, origin at top-left; the
device maps them to HID absolute coordinates (0..32767) internally, so they
adapt to any resolution.

**Format**: `{"type": "mouse", "action": "move", "x": <float>, "y": <float>}`

| Field | Type | Range | Description |
|:---|:---|:---|:---|
| `x` | number | [0.00, 1.00] | Absolute X coordinate |
| `y` | number | [0.00, 1.00] | Absolute Y coordinate |

**Format**: `{"type": "mouse", "action": "click", "button": <string>, "x": <float>, "y": <float>, "dblclick": <bool>}`

| Field | Type | Description |
|:---|:---|:---|
| `button` | string | `left` (default) / `right` / `middle` |
| `x`, `y` | number | Absolute coordinates [0.00, 1.00] |

The click sequence (move → press → 20ms hold → release) is executed atomically
by the device; `"dblclick": true` repeats it once after a 60ms interval.

**Format**: `{"type": "mouse", "action": "scroll", "dy": <int>}`

| Field | Type | Range | Description |
|:---|:---|:---|:---|
| `dy` | integer | [-127, 127] | Vertical scroll ticks, positive scrolls down |

### Hold Events (mouse down/up · keyboard down/up · release_all)

Press-and-hold primitives for drag & drop, rubber-band selection, sliders,
long-press menus, and modifier+click (e.g. Shift+click range select).

**Held state persists across requests** — you can split a drag into separate
control calls (press → screenshot to observe → move → release).

**Mouse**:

**Format**: `{"type": "mouse", "action": "down" | "up", "button": <string>, "x": <float>, "y": <float>}`

| Field | Type | Description |
|:---|:---|:---|
| `button` | string | `left` (default) / `right` / `middle` |
| `x`, `y` | number | Optional (pair them): move here first, then update the button |

The button state is a persistent bitmask: multiple buttons can be held at once
(e.g. hold `left` + `right`), and `mouse up` releases only the named button.

**Keyboard**:

**Format**: `{"type": "keyboard", "action": "down" | "up", "key": <string>}`

| Field | Type | Description |
|:---|:---|:---|
| `key` | string | Modifier (`ctrl`/`shift`/`alt`/`win`) or key name, same table as `hotkey` |

Up to 6 regular keys can be held simultaneously (HID limit); held modifiers
combine freely.

**Release all**:

**Format**: `{"type": "release_all"}`

Releases every held mouse button and held key in one event. Use it as a safety
reset: `cancel` stops a batch but does **not** auto-release held state, so send
`release_all` whenever an operation is interrupted mid-drag.

**Drag (composite, preferred)**:

**Format**: `{"type": "mouse", "action": "drag", "button": <string>, "from": [<x>, <y>], "to": [<x>, <y>], "duration_ms": <int>}`

| Field | Type | Description |
|:---|:---|:---|
| `button` | string | `left` (default) / `right` / `middle` |
| `from`, `to` | `[x, y]` arrays | Normalized `[0.00, 1.00]` start and end points |
| `duration_ms` | integer | 0..5000 (default 300) — movement time; the device interpolates smooth intermediate moves (~20ms steps) |

One event runs the whole gesture: press at `from` → 100ms dwell → interpolated
moves → 50ms dwell → release. Prefer it over manual `mouse down`/`move`/`up`
composition — many target UIs drop the drag when pointer jumps are too coarse.
On cancel/interrupt the button stays held (same semantics as `mouse down`); send
`release_all` to reset.

**Manual composition** (when you need to observe mid-drag via screenshot):

```json
{
  "events": [
    {"type": "mouse", "action": "down", "button": "left", "x": 0.2, "y": 0.5},
    {"type": "delay", "ms": 150},
    {"type": "mouse", "action": "move", "x": 0.8, "y": 0.5},
    {"type": "delay", "ms": 150},
    {"type": "mouse", "action": "up", "button": "left"}
  ]
}
```

**Shift+click range select example** (across two requests):
```json
{"events": [{"type": "keyboard", "action": "down", "key": "shift"}]}
{"events": [{"type": "mouse", "action": "click", "x": 0.5, "y": 0.9}, {"type": "keyboard", "action": "up", "key": "shift"}]}
```

### Text Event (text)

Input a text string at the current cursor position. **The device types the text
synchronously and returns only after it is complete** — no external delay idiom
is required (unlike interfaces that return immediately).

**Format**: `{"type": "keyboard", "action": "text", "value": "<text>"}`

| Field | Type | Description |
|:---|:---|:---|
| `value` | string | Text to input, 1..512 characters |

**Character set restrictions** (rejected by the device):
- Only printable ASCII: `32` (Space) ~ `126` (`~`)
- Tab and Enter are **not** allowed inside `text` — use a `keyboard hotkey` event for them

### Hotkey Event (hotkey)

Press a key combination (modifier + keys) and release, executed atomically.
Press/release pairing and ordering are handled by the device.

**Format**: `{"type": "keyboard", "action": "hotkey", "keys": ["ctrl", "c"]}`

| Field | Type | Description |
|:---|:---|:---|
| `keys` | array of strings | Modifiers + key names (lowercase), max 6 non-modifier keys |

**Modifiers** (may appear in any order; a bare modifier is allowed, e.g. `["win"]`):

| Name | Key |
|:---|:---|
| `ctrl` / `control` | Left Ctrl |
| `shift` | Left Shift |
| `alt` | Left Alt |
| `win` / `meta` / `cmd` | Left Meta (Windows/Command) |

**Key names** (non-modifier):
- Letters: `a` ~ `z`
- Digits: `0` ~ `9`
- Special: `enter`, `esc`/`escape`, `backspace`, `tab`, `space`,
  `delete`, `insert`, `pause`, `menu`, `printscreen`/`sysrq`,
  `home`, `end`, `pageup`, `pagedown`, `left`, `right`, `up`, `down`
- Lock keys: `capslock`, `numlock`, `scrolllock` (down+up toggles)
- Punctuation: `minus`, `equal`, `leftbracket`, `rightbracket`, `backslash`,
  `semicolon`, `quote`, `grave`, `comma`, `dot`, `slash` — shifted symbols use
  `shift` + key, e.g. `["shift", "equal"]` = `+`, `["shift", "1"]` = `!`
- Functions: `f1` ~ `f12`
- Numpad: `numpad0` ~ `numpad9`, `numpad_enter`, `numpad_dot`, `numpad_add`,
  `numpad_subtract`, `numpad_multiply`, `numpad_divide`
- Media: `mute`, `volumeup`, `volumedown`, `playpause`, `stop`, `previous`, `next`

See `references/key_names.md` for the complete table.

**Examples**:
```json
{"type": "keyboard", "action": "hotkey", "keys": ["win", "r"]}          // Win+R (Run dialog)
{"type": "keyboard", "action": "hotkey", "keys": ["ctrl", "c"]}         // Copy
{"type": "keyboard", "action": "hotkey", "keys": ["win"]}               // Open Start menu
{"type": "keyboard", "action": "hotkey", "keys": ["enter"]}             // Press Enter
```

### Delay Event (delay)

Pause execution to give the target machine time to respond.

**Format**: `{"type": "delay", "ms": <int>}`

| Field | Type | Range | Description |
|:---|:---|:---|:---|
| `ms` | integer | [0, 5000] | Pause duration in milliseconds |

> **Note**: Unlike text input (which is synchronous), delays are still needed
> after launching applications, page loads, and UI transitions — the device
> cannot know when the target machine finished rendering.

## Complete Task Example

### Open Browser and Visit a Website

```json
{
  "events": [
    {"type": "keyboard", "action": "hotkey", "keys": ["win", "r"]},
    {"type": "delay", "ms": 500},
    {"type": "keyboard", "action": "text", "value": "chrome"},
    {"type": "keyboard", "action": "hotkey", "keys": ["enter"]},
    {"type": "delay", "ms": 3000},
    {"type": "mouse", "action": "move", "x": 0.5, "y": 0.08},
    {"type": "mouse", "action": "click", "button": "left", "x": 0.5, "y": 0.08},
    {"type": "keyboard", "action": "text", "value": "example.com"},
    {"type": "keyboard", "action": "hotkey", "keys": ["enter"]},
    {"type": "delay", "ms": 2000}
  ]
}
```

**Step breakdown**:
1. `Win+R` to open the Run dialog
2. Type `chrome` and press Enter to launch the browser (text is synchronous)
3. Wait 3 seconds for the browser to start
4. Move the mouse to the address bar (top center)
5. Type `example.com`, then press Enter to navigate
6. Pause 2000ms for the page to load

## Best Practices

### 1. Coordinate Positioning
- Always prefer normalized `x`/`y` in `[0.00, 1.00]` — adapts to any resolution
- Capture a screenshot **before** critical operations to confirm the current state
- Use AI vision analysis for UI element localization, then map pixels to
  normalized coordinates (`px / width`, `py / height` from the `X-Resolution` header)
- Guard against relative-mode interference: check `mouse_mode` in the state
  endpoint; prefer operating when no user is online (`user_online: false`)

### 2. Timing Control

| Scenario | Recommended Delay | Notes |
|:---|:---|:---|
| After text input | 0 (synchronous) | Device waits for completion internally |
| After launching an app | 2000-5000ms | Depends on app startup time |
| After page load | 1000-3000ms | Depends on network |
| Between consecutive hotkeys | 100-300ms | Keep operations readable |
| After click on menus/dialogs | 300-800ms | UI transition time |

### 3. Long Text Input Strategy

Text up to 512 characters can be sent in a single `text` event — the device
completes it synchronously before returning. No chunking is required. A full
512-character payload takes ≈15s, which counts against the 60s request budget.
For very long content, split into multiple `text` events with short delays only
if you observe key drops on slow target machines:

```json
{
  "events": [
    {"type": "keyboard", "action": "text", "value": "This is a long text that needs"},
    {"type": "delay", "ms": 200},
    {"type": "keyboard", "action": "text", "value": " to be split for slow targets"},
    {"type": "delay", "ms": 200}
  ]
}
```

### 4. Hotkey Rules
- Use modifier + key names in any order, e.g. `["ctrl", "shift", "esc"]`
- For a bare modifier (e.g. `["win"]`) the device presses and releases it alone
- Use `hotkey` with `["enter"]` rather than text-embedded newlines

### 5. Error Handling
- An `error` field in the response means the batch stopped early; `applied`
  tells you how many events ran, so resume from the failed event
- `code` is non-zero only when the request itself was rejected (bad body, agent
  disabled, etc.) — the HTTP status carries the same verdict
- `error: "cancelled"` means another client aborted the batch
- If snapshot fails, check that the HDMI input has a locked signal (see the
  device's own video state); `mode: idle` alone is NOT a failure — snapshots
  are taken on demand in that state.
- 403 = Agent service disabled; 401 = invalid/expired API key — regenerate a
  key in Settings → Agent and update `FlexKVM_TOKEN`

## Troubleshooting

| Symptom | Possible Cause | Solution |
|:---|:---|:---|
| 403 Forbidden | Agent service disabled | Enable Agent in device settings |
| 401 Unauthorized | Wrong/removed API key | Regenerate key in Settings → Agent |
| Snapshot 500 | No locked HDMI signal | Check the HDMI source and the device's video state |
| Control returns `error` | Invalid event field/range | Verify event JSON against this doc |
| Coordinates inaccurate | UI scaled / resolution changed | Use screenshots + normalized coords |
| Garbled text | IME in wrong state | Switch target to English input method first |
| Events stop early | Mid-sequence event failed | Read `applied` and resume from that event |
| Batch will not stop | Long `text`/`delay` in flight | `POST /api/v1/agent/cancel` from another connection |
| Connection refused | Wrong IP / HTTPS not reachable | Check `FlexKVM_IP` connectivity |

## Helper Scripts

### Bash Quick Call

```bash
#!/bin/bash
# scripts/send_control.sh

FlexKVM_IP="${FlexKVM_IP:-}"
FlexKVM_TOKEN="${FlexKVM_TOKEN:-}"

curl -ks -X POST "https://${FlexKVM_IP}/api/v1/agent/control" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${FlexKVM_TOKEN}" \
  -d "$1"
```

### Python Wrapper

```python
#!/usr/bin/env python3
# scripts/flexkvm_client.py

import os
import warnings
import requests

warnings.filterwarnings("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)

class FlexKVMClient:
    def __init__(self):
        ip = os.getenv("FlexKVM_IP")
        if not ip:
            raise ValueError("Missing FlexKVM_IP")
        self.url = f"https://{ip}"
        self.token = os.getenv("FlexKVM_TOKEN")
        if not self.token:
            raise ValueError("Missing FlexKVM_TOKEN")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def state(self) -> dict:
        resp = self.session.get(f"{self.url}/api/v1/agent/state", timeout=10, verify=False)
        return resp.json()

    def screenshot(self, save_path: str = "screen.jpeg") -> bytes:
        resp = self.session.get(f"{self.url}/api/v1/agent/snapshot", timeout=15, verify=False)
        if save_path:
            with open(save_path, 'wb') as f:
                f.write(resp.content)
        return resp.content

    def control(self, events: list) -> dict:
        resp = self.session.post(
            f"{self.url}/api/v1/agent/control",
            json={"events": events},
            headers={"Content-Type": "application/json"},
            timeout=60, verify=False,
        )
        return resp.json()

    def cancel(self) -> dict:
        resp = self.session.post(f"{self.url}/api/v1/agent/cancel", timeout=10, verify=False)
        return resp.json()

    def text(self, content: str) -> dict:
        return self.control([{"type": "keyboard", "action": "text", "value": content}])
```

See `scripts/flexkvm_client.py` for the full wrapper
(`click`/`move`/`scroll`/`hotkey`/`key_combo`/`run_command`/`cancel` helpers
included, plus the hold primitives `mouse_down`/`mouse_up`/`key_down`/
`key_up`/`release_all` and the composite `drag`).

## Related Resources

- **scripts/**: Helper scripts for common operations
- **examples/**: Typical automation task examples
- **references/key_names.md**: Complete hotkey key-name reference table
- **MCP**: the same agent surface is also exposed as JSON-RPC at
  `POST /api/v1/mcp` (tools: `state`, `screenshot`, `type_text`, `press_key`,
  `mouse_move`, `mouse_click`, `mouse_scroll`, `mouse_down`, `mouse_up`,
  `mouse_drag`, `key_down`, `key_up`, `release_all`, `control` (batch of
  events); `notifications/cancelled` aborts an in-flight batch) — see the
  device API docs for details
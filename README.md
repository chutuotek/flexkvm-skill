# FlexKVM Universal Controller

An [OpenClaw](https://docs.openclaw.ai) skill for the FlexKVM agent control
interface — a universal HTTPS way to capture screens and send keyboard and
mouse events to the machine connected to your FlexKVM IP-KVM device.

## Features

- 📸 **Screenshot**: Capture real-time screen images from the target machine
- 🖱️ **Mouse control**: Absolute normalized coordinates `[0.0, 1.0]`, click /
  double-click / scroll
- ⌨️ **Keyboard control**: Atomic hotkeys (modifiers + key names) and Enter-style
  single keys
- 📝 **Text input**: Synchronous completion — the device finishes typing before
  returning; up to 1024 characters per event
- ⏱️ **Delay control**: Fine-grained pacing for app launch / page load waits

## Quick Start

### 1. Device Setup

1. Enable **Agent** in the FlexKVM web UI (Settings → Agent)
2. Generate an **API Key** (`sk-` + 32 hex characters)
3. Note the device IP (HTTPS on the default port 443)

### 2. Environment Setup

The following environment variables are required:

#### Bash

```bash
export FlexKVM_IP="192.168.x.x"
export FlexKVM_TOKEN="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

#### PowerShell

```powershell
[System.Environment]::SetEnvironmentVariable("FlexKVM_IP", "192.168.x.x", "User")
[System.Environment]::SetEnvironmentVariable("FlexKVM_TOKEN", "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "User")
```

> After modifying environment variables, restart OpenClaw or reopen your
> terminal before executing.

### 3. Execution Rules

When executing, read the environment variables, compose the base URL
`https://${FlexKVM_IP}`, then call the FlexKVM agent API:

- State: `GET /api/v1/agent/state`
- Screenshot: `GET /api/v1/agent/snapshot`
- Control: `POST /api/v1/agent/control`
- All requests carry `Authorization: Bearer ${FlexKVM_TOKEN}`

The device uses a self-signed TLS certificate — clients must skip certificate
verification (`curl -k`, Python `verify=False`).

### 4. Usage Examples

#### Bash

```bash
# Send control commands
./scripts/send_control.sh '{"events":[{"type":"text","value":"hello"},{"type":"delay","ms":300}]}'

# Capture a screenshot
curl -ks -X GET "https://${FlexKVM_IP}/api/v1/agent/snapshot" \
     -H "Authorization: Bearer ${FlexKVM_TOKEN}" -o screen.jpeg
```

#### Python (optional)

```python
from scripts.flexkvm_client import FlexKVMClient

client = FlexKVMClient()

# Query state
print(client.state())

# Capture a screenshot
client.screenshot("desktop.jpeg")

# Input text (synchronous, no chunking needed)
client.text("Hello from FlexKVM")

# Click at screen center
client.click(0.5, 0.5)

# Win+R -> notepad -> Enter
client.run_command("notepad")

# Hotkey combinations
client.key_combo("ctrl", "c")       # Copy
client.key_combo("alt", "tab")      # Switch window
```

#### Example JSON files

```bash
curl -ks -X POST "https://${FlexKVM_IP}/api/v1/agent/control" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${FlexKVM_TOKEN}" \
  -d @examples/open_browser.json
```

## Directory Layout

```
flexkvm-skill/
├── SKILL.md                    # Main skill document (OpenClaw spec)
├── README.md                   # This file
├── scripts/
│   ├── send_control.sh         # Bash quick-call script (curl)
│   └── flexkvm_client.py       # Python client wrapper (full helper set)
├── examples/
│   ├── open_browser.json       # Open a browser and visit a website
│   ├── open_notepad.json       # Open Notepad and type a message
│   ├── mouse_demo.json         # Mouse move / click / dblclick / scroll
│   ├── keyboard_shortcuts.json # Hotkey demos (Ctrl+C/V, Alt+Tab, Win)
│   └── long_text_input.json    # Long synchronous text input
└── references/
    └── key_names.md            # Hotkey key-name reference table
```

## Event Types Cheat Sheet

| Event | Example | Description |
|:---|:---|:---|
| move | `{"type":"move","x":0.5,"y":0.5}` | Absolute mouse move |
| click | `{"type":"click","button":"left","x":0.5,"y":0.5}` | Single click |
| dblclick | `{"type":"dblclick","button":"left","x":0.5,"y":0.5}` | Double click |
| scroll | `{"type":"scroll","dy":-3}` | Vertical scroll [-127,127] |
| text | `{"type":"text","value":"hello"}` | Synchronous printable-ASCII text |
| hotkey | `{"type":"hotkey","keys":["ctrl","c"]}` | Atomic key combination |
| delay | `{"type":"delay","ms":1000}` | Pause (0..5000ms) |

**Request limits**: at most 32 events, total execution under 60 seconds.

## Synchronous Text — The Key Difference

The FlexKVM device types `text` events internally and only responds after the
input is complete (30ms/character through the paste channel). Unlike
immediate-return interfaces, you do **not** need "1000ms pause per 30 chars"
idioms. Delays are still required for target-side rendering (app launch, page
load, UI transitions).

## Dependencies

- `curl`: for HTTP requests
- `python3` + `requests`: for the Python client (optional)

## License

This skill is part of the FlexKVM project.
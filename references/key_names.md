# FlexKVM hotkey Key Names Reference

Complete list of key names accepted by the `keyboard` domain events:
- `hotkey` — `{"type": "keyboard", "action": "hotkey", "keys": [...]}`
- `down` / `up` — hold events accept the same names, one per event
  (`{"type": "keyboard", "action": "down", "key": <name>}`; a bare modifier is
  allowed, e.g. `"shift"`)

All names are **lowercase**.

## Modifiers

| Name | Key |
|:---|:---|
| `ctrl` / `control` | Left Ctrl |
| `shift` | Left Shift |
| `alt` | Left Alt |
| `win` / `meta` / `cmd` | Left Meta (Windows/Command) |

Modifiers may appear in any order and mix with key names, e.g.
`["ctrl", "shift", "esc"]`. A bare modifier is allowed: `["win"]` opens the
Start menu. At most 6 non-modifier keys per event.

## Letter Keys

| Name | Description |
|:---|:---|
| `a` ~ `z` | Letter keys A-Z (lowercase single characters) |

## Number Keys

| Name | Description |
|:---|:---|
| `0` ~ `9` | Number keys (single characters) |

## Special Keys

| Name | Description |
|:---|:---|
| `enter` | Enter |
| `esc` / `escape` | Esc |
| `backspace` | Backspace |
| `tab` | Tab |
| `space` | Space bar |
| `delete` | Delete |
| `insert` | Insert |
| `pause` | Pause |
| `menu` | Application/Menu key |
| `printscreen` / `sysrq` | Print Screen / SysRq |
| `home` | Home |
| `end` | End |
| `pageup` | Page Up |
| `pagedown` | Page Down |
| `left` | Arrow Left |
| `right` | Arrow Right |
| `up` | Arrow Up |
| `down` | Arrow Down |

## Lock Keys

Toggle keys — a press-and-release toggles the lock state
(e.g. `["hotkey", "capslock"]` toggles Caps Lock):

| Name | Description |
|:---|:---|
| `capslock` | Caps Lock |
| `numlock` | Num Lock |
| `scrolllock` | Scroll Lock |

## Punctuation Keys

Shifted symbols are expressed as `shift` + the key, e.g.
`["shift", "equal"]` sends `+`, `["ctrl", "shift", "leftbracket"]` sends
Ctrl+Shift+[:

| Name | Key | Shifted (`["shift", <name>]`) |
|:---|:---|:---|
| `minus` | `-` | `_` |
| `equal` | `=` | `+` |
| `leftbracket` | `[` | `{` |
| `rightbracket` | `]` | `}` |
| `backslash` | `\` | `\|` |
| `semicolon` | `;` | `:` |
| `quote` | `'` | `"` |
| `grave` | `` ` `` | `~` |
| `comma` | `,` | `<` |
| `dot` | `.` | `>` |
| `slash` | `/` | `?` |

## Function Keys

| Name | Description |
|:---|:---|
| `f1` ~ `f12` | Function keys F1-F12 |

## Numpad Keys

| Name | Description |
|:---|:---|
| `numpad0` ~ `numpad9` | Numpad digits 0-9 |
| `numpad_enter` | Numpad Enter |
| `numpad_dot` | Numpad decimal point |
| `numpad_add` | Numpad `+` |
| `numpad_subtract` | Numpad `-` |
| `numpad_multiply` | Numpad `*` |
| `numpad_divide` | Numpad `/` |

## Media Keys

| Name | Description |
|:---|:---|
| `mute` | Mute |
| `volumeup` | Volume Up |
| `volumedown` | Volume Down |
| `playpause` | Play / Pause |
| `stop` | Stop |
| `previous` | Previous track |
| `next` | Next track |

## Notes

- Any character can be typed with a `text` event; use hotkey combinations for
  shifted symbols (e.g. `["shift", "1"]` = `!`)
- `hotkey` always performs a press-and-release sequence atomically; hold a key
  across requests with `keyboard down`/`up` (same key names, one per event)
- Windows shortcuts use `win` (e.g. `["win", "r"]` = Run dialog,
  `["win", "d"]` = show desktop)
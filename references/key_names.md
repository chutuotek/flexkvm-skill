# FlexKVM hotkey Key Names Reference

Complete list of key names accepted by the `hotkey` event
(`{"type": "hotkey", "keys": [...]}`). All names are **lowercase**.

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
| `minus` | `-` |
| `equal` | `=` |
| `delete` | Delete |
| `home` | Home |
| `end` | End |
| `pageup` | Page Up |
| `pagedown` | Page Down |
| `left` | Arrow Left |
| `right` | Arrow Right |
| `up` | Arrow Up |
| `down` | Arrow Down |

## Function Keys

| Name | Description |
|:---|:---|
| `f1` ~ `f12` | Function keys F1-F12 |

## Notes

- Punctutation characters (`.`, `,`, `/`, `?` etc.) are **not** hotkey names —
  type them with a `text` event instead
- There is no individual "press and hold" primitive: `hotkey` always performs a
  press-and-release sequence atomically
- Windows shortcuts use `win` (e.g. `["win", "r"]` = Run dialog,
  `["win", "d"]` = show desktop)
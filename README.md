# poco-mcp

FastMCP server wrapping [Poco-SDK](https://github.com/AirtestProject/Poco-SDK) so MCP-aware agents (Claude Code, OpenCode, Cursor, etc.) can drive a Unity game running in Play mode — inspect the UI hierarchy, click/drag/scroll UI elements, read attributes, take screenshots.

Free alternative to AltTester Desktop (no broker, no license).

## Requirements

- Python 3.12 (numpy 1.26.4 lacks 3.13 wheels, pocoui depends on it)
- Unity project with Poco-SDK vendored in — specifically the [`feat/ui-click-executeevents` branch](https://github.com/thalesdeluca/Poco-SDK/tree/feat/ui-click-executeevents) which adds the `PocoUIClickExtension` needed by the `ui_*` tools. Vanilla Poco-SDK works for the non-`ui_*` tools.

## Unity setup

1. Vendor `Unity3D/` from Poco-SDK into `Assets/Scripts/Poco/` (keep `uguiWithTMPro`, drop `ngui` / `ugui` / `fairygui`).
2. Attach `PocoManager` to a GameObject (Main Camera works).
3. Attach `PocoUIClickExtension` to the same GameObject.
4. In the Inspector, drag the `PocoUIClickExtension` component into `PocoManager.pocoListenersBase`.
5. Press Play — Unity listens on `:5001`.

## MCP client setup

OpenCode (`~/.config/opencode/opencode.json`):

```json
{
  "mcp": {
    "Poco": {
      "type": "local",
      "command": [
        "uv", "run", "--python", "3.12",
        "--with", "fastmcp",
        "--with", "pocoui",
        "python", "/path/to/poco-mcp/server.py"
      ],
      "enabled": true
    }
  }
}
```

Claude Code (`claude_mcp_config.json`) — same shape, key `mcpServers`.

## Tools

**Discovery**

- `connect(host, port)` — smoke-test the TCP connection to Unity
- `dump_hierarchy()` — full scene/UI tree as JSON
- `find_object(name, type)` — locate a GameObject
- `wait_for_object(name, type, timeout)` — block until it appears
- `get_attr(name, attr, type)` — read a single attribute
- `get_current_scene()` — best-effort scene name

**Input — use `ui_*` for Canvas UI**

Poco's default input path sends screen-coord touches which work for 3D/physics colliders but frequently miss Canvas UI (Button.onClick needs matching PointerDown+Up on the same Graphic; drag needs the threshold to be crossed; IScrollHandler never fires from synthesized touches). The `ui_*` tools dispatch events via `EventSystem.ExecuteEvents` or set component values directly, bypassing input simulation.

- `ui_click(name)` — Button.onClick-reliable
- `ui_drag(from_name, to_name, steps)` — IBeginDrag/IDrag/IEndDrag/IDrop
- `ui_scroll(name, dx, dy)` — IScrollHandler
- `ui_hover(name, enter)` — IPointerEnter/IPointerExit
- `ui_select(name)` / `ui_submit(name)` — keyboard-style focus + Enter
- `ui_set_slider(name, value)` — Slider.value
- `ui_set_toggle(name, isOn)` — Toggle.isOn
- `ui_set_dropdown(name, index)` — (TMP_)Dropdown.value

For non-UI (3D objects with colliders):

- `tap(name, type)` — screen-coord click
- `long_click(name, duration, type)`
- `swipe(from_name, to_name, duration)`
- `set_text(name, text)` — InputField / TMP_InputField

**Media**

- `screenshot(path)` — save PNG to disk
- `screenshot_base64()` — return as base64 string

## Environment

- `POCO_HOST` (default `127.0.0.1`)
- `POCO_PORT` (default `5001`)

## License

MIT. Poco-SDK itself is Apache-2.0.

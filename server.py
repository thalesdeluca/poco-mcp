"""
Poco MCP server — free alternative to AltTester.
Wraps AirtestProject/Poco (UnityPoco driver) with FastMCP so OpenCode/Claude Code
can drive a Unity game running the Poco SDK in Play mode.

Unity-side setup:
  - Copy Poco-SDK/Unity3D into Assets/Scripts/Poco/ (keep uguiWithTMPro, drop others)
  - Attach PocoManager.cs to Main Camera (or any GameObject)
  - Press Play — Unity listens on :5001 directly, no broker needed

Launch: uv run --with fastmcp --with pocoui python server.py
"""
from __future__ import annotations

import base64
import io
import os
from typing import Any

from fastmcp import FastMCP

try:
    from poco.drivers.unity3d import UnityPoco
except ImportError as e:
    raise SystemExit(
        "pocoui not installed. Run with: "
        "uv run --with fastmcp --with pocoui python server.py"
    ) from e

mcp = FastMCP("poco-custom")

_poco: UnityPoco | None = None


def _get_poco() -> UnityPoco:
    global _poco
    if _poco is None:
        host = os.environ.get("POCO_HOST", "127.0.0.1")
        port = int(os.environ.get("POCO_PORT", "5001"))
        _poco = UnityPoco(
            (host, port),
            unity_editor=True,
            connect_default_device=False,
        )
    return _poco


def _node_info(node) -> dict[str, Any]:
    try:
        payload = node.attr("")
    except Exception:
        payload = {}
    return {
        "name": node.get_name() if hasattr(node, "get_name") else str(node),
        "exists": node.exists() if hasattr(node, "exists") else True,
        "pos": node.get_position() if hasattr(node, "get_position") else None,
        "size": node.get_size() if hasattr(node, "get_size") else None,
        "text": safe_attr(node, "text"),
        "type": safe_attr(node, "type"),
        "visible": safe_attr(node, "visible"),
    }


def safe_attr(node, key: str):
    try:
        return node.attr(key)
    except Exception:
        return None


@mcp.tool()
def connect(host: str = "127.0.0.1", port: int = 5001) -> str:
    """Connect to Poco (Unity in Play mode). Unity must have PocoManager attached."""
    global _poco
    _poco = None
    try:
        _poco = UnityPoco(
            (host, port),
            unity_editor=True,
            connect_default_device=False,
        )
        _poco.agent.hierarchy.dump()  # smoke test
    except Exception as e:
        return (
            f"ERROR: could not connect to Poco at {host}:{port} — "
            f"is Unity in Play mode with PocoManager on a GameObject? "
            f"({type(e).__name__}: {e})"
        )
    return f"connected to poco at {host}:{port}"


@mcp.tool()
def dump_hierarchy() -> dict[str, Any]:
    """Return the full UI/scene hierarchy as JSON (GameObjects + attributes)."""
    return _get_poco().agent.hierarchy.dump()


@mcp.tool()
def find_object(name: str, type: str = "") -> dict[str, Any]:
    """Find a GameObject by name (optionally filtered by type, e.g. 'Button')."""
    poco = _get_poco()
    node = poco(name, type=type) if type else poco(name)
    if not node.exists():
        return {"exists": False, "name": name}
    return _node_info(node)


@mcp.tool()
def wait_for_object(name: str, type: str = "", timeout: float = 20.0) -> dict[str, Any]:
    """Wait until a GameObject appears, then return its info."""
    poco = _get_poco()
    node = poco(name, type=type) if type else poco(name)
    node.wait_for_appearance(timeout=timeout)
    return _node_info(node)


@mcp.tool()
def tap(name: str, type: str = "") -> str:
    """Click/tap a GameObject via screen-coord touch simulation.
    For Unity UI buttons, prefer `ui_click` — touch simulation is flaky in editor."""
    poco = _get_poco()
    node = poco(name, type=type) if type else poco(name)
    node.click()
    return f"tapped {name}"


def _invoke(listener: str, data: dict[str, Any]) -> dict[str, Any]:
    """Call a PocoUIClickExtension RPC and return its response dict."""
    try:
        cb = _get_poco().agent.rpc.call("Invoke", listener=listener, data=data)
        result = cb.wait()
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}
    return result if isinstance(result, dict) else {"success": True, "result": result}


@mcp.tool()
def ui_click(name: str) -> dict[str, Any]:
    """Reliably click a Unity Canvas UI element via EventSystem.ExecuteEvents.
    Use this for any Button/Graphic with onClick handlers. `tap` is flaky on Canvas."""
    return _invoke("UIClick", {"name": name})


@mcp.tool()
def ui_drag(from_name: str, to_name: str, steps: int = 10) -> dict[str, Any]:
    """Drag-and-drop a UI element from one GameObject to another via ExecuteEvents.
    Fires IBeginDrag → IDrag (N steps) → IEndDrag → IDrop. Works for inventory
    slots, reorderable lists, any IDragHandler/IDropHandler pair."""
    return _invoke("UIDrag", {"from_name": from_name, "to_name": to_name, "steps": steps})


@mcp.tool()
def ui_scroll(name: str, dx: float = 0.0, dy: float = -120.0) -> dict[str, Any]:
    """Scroll a ScrollRect / IScrollHandler. Default dy=-120 scrolls down one notch.
    Positive dy scrolls up, positive dx scrolls right."""
    return _invoke("UIScroll", {"name": name, "dx": dx, "dy": dy})


@mcp.tool()
def ui_hover(name: str, enter: bool = True) -> dict[str, Any]:
    """Fire PointerEnter (enter=True) or PointerExit (enter=False) — for tooltips
    and hover highlights that don't respond to click."""
    return _invoke("UIHover", {"name": name, "enter": enter})


@mcp.tool()
def ui_select(name: str) -> dict[str, Any]:
    """Set EventSystem.current.selectedGameObject. Usually a prerequisite for ui_submit
    on InputFields / selectable UI."""
    return _invoke("UISelect", {"name": name})


@mcp.tool()
def ui_submit(name: str) -> dict[str, Any]:
    """Select then submit (ISubmitHandler) — equivalent to pressing Enter on a
    focused UI element."""
    return _invoke("UISubmit", {"name": name})


@mcp.tool()
def ui_set_slider(name: str, value: float) -> dict[str, Any]:
    """Set a Slider's value directly. More reliable than simulating a drag."""
    return _invoke("UISetSlider", {"name": name, "value": value})


@mcp.tool()
def ui_set_toggle(name: str, is_on: bool) -> dict[str, Any]:
    """Set a Toggle's isOn state directly (fires onValueChanged)."""
    return _invoke("UISetToggle", {"name": name, "isOn": is_on})


@mcp.tool()
def ui_set_dropdown(name: str, index: int) -> dict[str, Any]:
    """Set a Dropdown / TMP_Dropdown selected index (fires onValueChanged)."""
    return _invoke("UISetDropdown", {"name": name, "index": index})


@mcp.tool()
def long_click(name: str, duration: float = 2.0, type: str = "") -> str:
    """Long-press a GameObject for `duration` seconds."""
    poco = _get_poco()
    node = poco(name, type=type) if type else poco(name)
    node.long_click(duration=duration)
    return f"long-clicked {name} for {duration}s"


@mcp.tool()
def swipe(from_name: str, to_name: str, duration: float = 0.5) -> str:
    """Swipe from one GameObject to another."""
    poco = _get_poco()
    poco(from_name).swipe(poco(to_name).focus("center"), duration=duration)
    return f"swiped {from_name} -> {to_name}"


@mcp.tool()
def get_attr(name: str, attr: str, type: str = "") -> str:
    """Read an attribute on a GameObject (text, type, visible, pos, size, enabled, ...)."""
    poco = _get_poco()
    node = poco(name, type=type) if type else poco(name)
    return str(node.attr(attr))


@mcp.tool()
def set_text(name: str, text: str) -> str:
    """Set text on an InputField-like GameObject."""
    poco = _get_poco()
    poco(name).set_text(text)
    return f"set text of {name} = {text!r}"


@mcp.tool()
def get_current_scene() -> str:
    """Return the current scene name (best effort via hierarchy root)."""
    tree = _get_poco().agent.hierarchy.dump()
    payload = tree.get("payload", {})
    return str(payload.get("name", "unknown"))


@mcp.tool()
def screenshot(path: str) -> str:
    """Save a PNG screenshot of the game view to `path`."""
    data, fmt = _get_poco().snapshot(width=720)
    blob = base64.b64decode(data) if isinstance(data, str) else data
    with open(path, "wb") as f:
        f.write(blob)
    return f"saved {fmt} screenshot to {path}"


@mcp.tool()
def screenshot_base64() -> str:
    """Capture a PNG screenshot and return as base64 string."""
    data, _ = _get_poco().snapshot(width=720)
    return data if isinstance(data, str) else base64.b64encode(data).decode("ascii")


if __name__ == "__main__":
    mcp.run()

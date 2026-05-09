"""A simple menu bar (port of ``cc.internal.menu`` from the Lua ROM).

This is an internal module used by ROM programs like ``edit`` and ``paint``.
It intentionally mirrors the Lua module's API and behavior.
"""

from __future__ import annotations

from cc import term


# Key codes (from ``lua/rom/apis/keys.lua``)
_KEY_LEFT = 263
_KEY_RIGHT = 262
_KEY_ENTER = 257
_KEY_NUMPAD_ENTER = 335
_KEY_LEFT_CTRL = 341
_KEY_RIGHT_CTRL = 345
_KEY_RIGHT_ALT = 346


def create(items: list[str]) -> dict:
    return {"items": list(items), "selected": 1}


def draw(menu: dict) -> None:
    # NOTE: Lua's edit.lua clears the bottom line and may render other elements (like "Ln <n>")
    # before/after drawing the menu. So we do not clear the line here: callers are expected to.
    w, height = term.get_size()
    term.set_cursor_pos(1, height)

    active_colour = 0x10 if term.is_color() else 0x1  # yellow or white
    try:
        term.set_text_color(0x1)  # white
    except Exception:
        pass

    items = menu.get("items") or []
    selected = int(menu.get("selected") or 1)
    x_pos = 1
    for k, v in enumerate(items, start=1):
        v = str(v)
        if selected == k:
            label_len = len(v) + 2  # [ + item + ]
            if x_pos + label_len - 1 >= w:
                break
            try:
                term.set_text_color(active_colour)
                term.write("[")
                term.set_text_color(0x1)
                term.write(v)
                term.set_text_color(active_colour)
                term.write("]")
                term.set_text_color(0x1)
            except Exception:
                term.write("[" + v + "]")
            x_pos += label_len
        else:
            label = " " + v + " "
            if x_pos + len(label) - 1 >= w:
                break
            term.write(label)
            x_pos += len(label)


def handle_event(menu: dict, event: str, *args):
    """Process an event.

    Returns:
    - None: no action
    - False: menu closed
    - str: selected item
    """
    if event == "key":
        key = args[0] if args else None
        if key == _KEY_RIGHT:
            menu["selected"] = int(menu.get("selected") or 1) + 1
            if menu["selected"] > len(menu.get("items") or []):
                menu["selected"] = 1
            draw(menu)
        elif key == _KEY_LEFT:
            menu["selected"] = int(menu.get("selected") or 1) - 1
            if menu["selected"] < 1:
                menu["selected"] = len(menu.get("items") or [])
            draw(menu)
        elif key == _KEY_ENTER or key == _KEY_NUMPAD_ENTER:
            items = menu.get("items") or []
            idx = int(menu.get("selected") or 1) - 1
            if 0 <= idx < len(items):
                return items[idx]
        elif key in (_KEY_LEFT_CTRL, _KEY_RIGHT_CTRL, _KEY_RIGHT_ALT):
            return False
    elif event == "char":
        ch = (str(args[0]) if args else "").lower()
        if ch:
            for item in menu.get("items") or []:
                item = str(item)
                if item[:1].lower() == ch:
                    return item
    elif event == "mouse_click":
        # args: button, x, y
        if len(args) >= 3:
            _button, x, y = args[0], int(args[1]), int(args[2])
            _, height = term.get_size()
            if y != height:
                return False

            item_start = 1
            for item in menu.get("items") or []:
                item = str(item)
                item_end = item_start + len(item) + 2
                if x >= item_start and x < item_end:
                    return item
                item_start = item_end

    return None


import ctypes
import sys
from typing import Optional


TERMINAL_CLASS_NAMES = frozenset(
    {
        "CASCADIA_HOSTING_WINDOW_CLASS",
        "ConsoleWindowClass",
    }
)


def _default_user32():
    if sys.platform != "win32":
        return None
    try:
        return ctypes.windll.user32
    except (AttributeError, OSError):
        return None


def capture_foreground(user32=None) -> Optional[int]:
    """Return the foreground HWND as an int, or None if unavailable or 0."""
    if user32 is None:
        user32 = _default_user32()
    if user32 is None:
        return None
    try:
        hwnd = user32.GetForegroundWindow()
    except Exception:
        return None
    try:
        hwnd = int(hwnd)
    except (TypeError, ValueError):
        return None
    return hwnd or None


def _window_class_name(user32, hwnd) -> str:
    try:
        buffer = ctypes.create_unicode_buffer(256)
        result = user32.GetClassNameW(hwnd, buffer, len(buffer))
        if isinstance(result, str):
            return result
        if isinstance(result, bytes):
            return result.decode(errors="replace")
        return buffer.value
    except Exception:
        return ""


def _clipboard_copy(clipboard_copy):
    if clipboard_copy is not None:
        return clipboard_copy
    try:
        import pyperclip
    except Exception:
        return None
    return getattr(pyperclip, "copy", None)


def _send_keys(send_keys):
    if send_keys is not None:
        return send_keys
    try:
        import keyboard
    except Exception:
        return None
    return getattr(keyboard, "send", None)


def paste_text(
    text,
    hwnd=None,
    *,
    user32=None,
    clipboard_copy=None,
    send_keys=None,
) -> bool:
    """Copy text, focus the target, and send the appropriate paste chord."""
    if not text:
        return False

    copy = _clipboard_copy(clipboard_copy)
    if copy is None:
        return False
    send = _send_keys(send_keys)
    if send is None:
        return False

    try:
        copy(text)

        if hwnd:
            if user32 is None:
                user32 = _default_user32()
            if user32 is not None:
                user32.SetForegroundWindow(hwnd)

        class_name = ""
        if hwnd and user32 is not None:
            class_name = _window_class_name(user32, hwnd)
        chord = "ctrl+shift+v" if class_name in TERMINAL_CLASS_NAMES else "ctrl+v"
        send(chord)
        return True
    except Exception:
        return False

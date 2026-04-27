from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


def apply_native_window_style(window: object) -> None:
    if sys.platform != "win32":
        return
    try:
        hwnd = int(window.winfo_id())  # type: ignore[attr-defined]
    except Exception:
        return

    _set_dwm_int(hwnd, 20, 1)  # DWMWA_USE_IMMERSIVE_DARK_MODE
    _set_dwm_int(hwnd, 33, 2)  # DWMWA_WINDOW_CORNER_PREFERENCE / DWMWCP_ROUND
    _set_dwm_int(hwnd, 38, 2)  # DWMWA_SYSTEMBACKDROP_TYPE / DWMSBT_MAINWINDOW


def _set_dwm_int(hwnd: int, attribute: int, value: int) -> None:
    try:
        dwmapi = ctypes.windll.dwmapi
        data = wintypes.DWORD(value)
        dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(attribute),
            ctypes.byref(data),
            ctypes.sizeof(data),
        )
    except Exception:
        return

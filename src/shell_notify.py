from __future__ import annotations

import ctypes
import sys
from pathlib import Path


SHCNE_UPDATEDIR = 0x00001000
SHCNE_UPDATEITEM = 0x00002000
SHCNF_PATHW = 0x0005
SHCNF_FLUSHNOWAIT = 0x2000


def notify_shell_dir_changed(path: Path) -> None:
    _notify(SHCNE_UPDATEDIR, path)


def notify_shell_item_changed(path: Path) -> None:
    _notify(SHCNE_UPDATEITEM, path)


def _notify(event: int, path: Path) -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SHChangeNotify(
            event,
            SHCNF_PATHW | SHCNF_FLUSHNOWAIT,
            ctypes.c_wchar_p(str(path)),
            None,
        )
    except Exception:
        return

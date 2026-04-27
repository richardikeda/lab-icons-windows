from __future__ import annotations

import sys
from pathlib import Path


class StartupError(RuntimeError):
    pass


def startup_shortcut_path(app_name: str = "Lab Icons Windows Reapply") -> Path:
    startup = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return startup / f"{app_name}.lnk"


def enable_startup_reapply(app_path: Path) -> None:
    shortcut = startup_shortcut_path()
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    shell = _dispatch_shell()
    link = shell.CreateShortCut(str(shortcut))
    link.Targetpath = sys.executable
    link.Arguments = f'"{app_path}" --reapply-once'
    link.WorkingDirectory = str(app_path.parent)
    link.IconLocation = str(app_path)
    link.save()


def disable_startup_reapply() -> None:
    shortcut = startup_shortcut_path()
    if shortcut.exists():
        shortcut.unlink()


def is_startup_reapply_enabled() -> bool:
    return startup_shortcut_path().exists()


def _dispatch_shell():
    try:
        import win32com.client
    except ImportError as exc:
        raise StartupError("Instale pywin32 para criar inicialização automática.") from exc
    return win32com.client.Dispatch("WScript.Shell")

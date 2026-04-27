from __future__ import annotations

import re
from pathlib import Path


class AppxShortcutError(RuntimeError):
    pass


def create_managed_appx_shortcut(app_id: str, name: str, shortcut_dir: Path) -> Path:
    shortcut_dir.mkdir(parents=True, exist_ok=True)
    shortcut_path = shortcut_dir / f"{_safe_name(name)}.lnk"
    shell = _dispatch_shell()
    link = shell.CreateShortCut(str(shortcut_path))
    link.Targetpath = "explorer.exe"
    link.Arguments = f"shell:AppsFolder\\{app_id}"
    link.WorkingDirectory = str(shortcut_dir)
    link.save()
    return shortcut_path


def _safe_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*]+', "-", name).strip()
    return cleaned or "Windows App"


def _dispatch_shell():
    try:
        import win32com.client
    except ImportError as exc:
        raise AppxShortcutError("Instale pywin32 para criar atalhos de apps do Windows.") from exc
    return win32com.client.Dispatch("WScript.Shell")

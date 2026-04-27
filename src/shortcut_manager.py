from __future__ import annotations

from pathlib import Path


class ShortcutError(RuntimeError):
    pass


def is_windows_shortcut(path: Path) -> bool:
    return path.suffix.lower() == ".lnk"


def read_shortcut_icon(shortcut_path: Path) -> str:
    shell_link = _load_shell_link(shortcut_path)
    icon_path, icon_index = shell_link.GetIconLocation()
    if not icon_path:
        return ""
    return f"{icon_path},{icon_index}"


def apply_shortcut_icon(shortcut_path: Path, ico_path: Path) -> None:
    if not is_windows_shortcut(shortcut_path):
        raise ShortcutError("O protótipo altera apenas atalhos .lnk.")
    if not shortcut_path.exists():
        raise ShortcutError(f"Atalho não encontrado: {shortcut_path}")
    if not ico_path.exists():
        raise ShortcutError(f"Ícone não encontrado: {ico_path}")

    shell_link = _load_shell_link(shortcut_path)
    shell_link.SetIconLocation(str(ico_path), 0)
    persist_file = shell_link.QueryInterface(_pythoncom().IID_IPersistFile)
    persist_file.Save(str(shortcut_path), 0)


def restore_shortcut_icon(shortcut_path: Path, icon_location: str) -> None:
    if not is_windows_shortcut(shortcut_path):
        raise ShortcutError("O protótipo altera apenas atalhos .lnk.")
    if not shortcut_path.exists():
        raise ShortcutError(f"Atalho não encontrado: {shortcut_path}")
    icon_path, icon_index = _parse_icon_location(icon_location)
    shell_link = _load_shell_link(shortcut_path)
    shell_link.SetIconLocation(icon_path, icon_index)
    persist_file = shell_link.QueryInterface(_pythoncom().IID_IPersistFile)
    persist_file.Save(str(shortcut_path), 0)


def shortcut_has_icon(shortcut_path: Path, ico_path: Path) -> bool:
    current = read_shortcut_icon(shortcut_path)
    expected = str(ico_path).lower()
    return current.lower().startswith(expected)


def _load_shell_link(shortcut_path: Path):
    pythoncom = _pythoncom()
    shell = _shell()
    shell_link = pythoncom.CoCreateInstance(
        shell.CLSID_ShellLink,
        None,
        pythoncom.CLSCTX_INPROC_SERVER,
        shell.IID_IShellLink,
    )
    persist_file = shell_link.QueryInterface(pythoncom.IID_IPersistFile)
    persist_file.Load(str(shortcut_path))
    return shell_link


def _pythoncom():
    try:
        import pythoncom
    except ImportError as exc:
        raise ShortcutError("Instale pywin32 para alterar atalhos .lnk no Windows.") from exc
    return pythoncom


def _shell():
    try:
        from win32com.shell import shell
    except ImportError as exc:
        raise ShortcutError("Instale pywin32 para alterar atalhos .lnk no Windows.") from exc
    return shell


def _parse_icon_location(icon_location: str) -> tuple[str, int]:
    if "," not in icon_location:
        return icon_location, 0
    path, index = icon_location.rsplit(",", 1)
    try:
        return path, int(index)
    except ValueError:
        return path, 0

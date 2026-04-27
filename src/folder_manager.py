from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from src.file_hashing import sha1_digest_prefix
from src.shell_notify import notify_shell_dir_changed


class FolderIconError(RuntimeError):
    pass


MANAGED_DIR = ".lab-icons-windows"
MANAGED_ICON = "folder.ico"
MANAGED_ICON_PREFIX = "folder-"
BACKUP_INI = "desktop.ini.backup"


def apply_folder_icon(folder_path: Path, icon_path: Path) -> None:
    if not folder_path.exists() or not folder_path.is_dir():
        raise FolderIconError(f"Pasta nao encontrada: {folder_path}")
    if not icon_path.exists():
        raise FolderIconError(f"Icone nao encontrado: {icon_path}")
    if icon_path.suffix.lower() != ".ico":
        raise FolderIconError("Pastas do Windows devem usar ICO para maior compatibilidade.")

    managed_dir = folder_path / MANAGED_DIR
    managed_dir.mkdir(exist_ok=True)
    managed_icon = managed_dir / _managed_icon_name(icon_path)
    shutil.copy2(icon_path, managed_icon)

    desktop_ini = folder_path / "desktop.ini"
    backup_ini = managed_dir / BACKUP_INI
    if desktop_ini.exists() and not backup_ini.exists():
        shutil.copy2(desktop_ini, backup_ini)

    content = _merge_desktop_ini(desktop_ini, f"{MANAGED_DIR}\\{managed_icon.name}")
    if desktop_ini.exists():
        _attrib("-h", "-s", desktop_ini)
    desktop_ini.write_text(content, encoding="utf-16")
    _attrib("+h", "+s", desktop_ini)
    _attrib("+h", managed_dir)
    _attrib("+s", "+r", folder_path)
    notify_shell_dir_changed(folder_path)


def folder_has_icon(folder_path: Path, icon_path: Path) -> bool:
    desktop_ini = folder_path / "desktop.ini"
    if not desktop_ini.exists():
        return False
    content = _read_desktop_ini(desktop_ini).lower()
    expected_icon = str(Path(MANAGED_DIR) / _managed_icon_name(icon_path)).replace("/", "\\").lower()
    return "labiconswindows=1" in content and expected_icon in content


def read_folder_icon(folder_path: Path) -> str:
    desktop_ini = folder_path / "desktop.ini"
    if not desktop_ini.exists():
        return ""
    try:
        content = _read_desktop_ini(desktop_ini)
    except OSError:
        return ""

    icon_file = ""
    icon_index = ""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip().lower()
        value = value.strip().strip('"')
        if key == "iconresource":
            return _normalize_icon_location(folder_path, value)
        if key == "iconfile":
            icon_file = value
        elif key == "iconindex":
            icon_index = value

    if not icon_file:
        return ""
    normalized = _normalize_icon_location(folder_path, icon_file)
    if icon_index and "," not in normalized:
        return f"{normalized},{icon_index}"
    return normalized


def remove_folder_icon(folder_path: Path) -> None:
    desktop_ini = folder_path / "desktop.ini"
    if not desktop_ini.exists():
        return
    content = _read_desktop_ini(desktop_ini)
    if "LabIconsWindows=1" not in content:
        raise FolderIconError("A pasta tem desktop.ini, mas nao foi criado por este aplicativo.")
    _attrib("-h", "-s", desktop_ini)
    desktop_ini.unlink()
    managed_dir = folder_path / MANAGED_DIR
    if managed_dir.exists():
        backup_ini = managed_dir / BACKUP_INI
        if backup_ini.exists():
            shutil.copy2(backup_ini, desktop_ini)
        _attrib("-h", managed_dir)
        shutil.rmtree(managed_dir, ignore_errors=True)
    _attrib("-s", "-r", folder_path)


def _attrib(*args: str | Path) -> None:
    command = ["attrib", *(str(arg) for arg in args)]
    result = subprocess.run(command, capture_output=True, text=True, shell=False)
    if result.returncode != 0:
        raise FolderIconError(result.stderr.strip() or "Falha ao atualizar atributos da pasta.")


def _read_desktop_ini(path: Path) -> str:
    for encoding in ("utf-16", "utf-8-sig", "utf-8", "mbcs"):
        try:
            return path.read_text(encoding=encoding, errors="ignore")
        except LookupError:
            continue
        except OSError:
            raise
        except UnicodeError:
            continue
    return path.read_text(errors="ignore")


def _merge_desktop_ini(path: Path, relative_icon: str) -> str:
    existing = _read_desktop_ini(path) if path.exists() else ""
    lines = []
    saw_section = False
    for line in existing.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered == "[.shellclassinfo]":
            saw_section = True
            lines.append("[.ShellClassInfo]")
            continue
        if lowered.startswith(("iconresource=", "iconfile=", "iconindex=", "; labiconswindows=", "confirmfileop=")):
            continue
        if stripped:
            lines.append(line)
    if not saw_section:
        lines.insert(0, "[.ShellClassInfo]")
    insert_at = 1 if lines and lines[0].lower() == "[.shellclassinfo]" else len(lines)
    additions = [
        "; LabIconsWindows=1",
        "ConfirmFileOp=0",
        f"IconResource={relative_icon},0",
        f"IconFile={relative_icon}",
        "IconIndex=0",
    ]
    lines[insert_at:insert_at] = additions
    return "\n".join(lines) + "\n"


def _managed_icon_name(icon_path: Path) -> str:
    digest = sha1_digest_prefix(icon_path)
    return f"{MANAGED_ICON_PREFIX}{digest}.ico"


def _normalize_icon_location(folder_path: Path, value: str) -> str:
    if not value:
        return ""
    location = os.path.expandvars(value)
    icon_path, suffix = _split_location_suffix(location)
    path = Path(icon_path)
    if not path.is_absolute():
        path = folder_path / path
    return f"{path}{suffix}"


def _split_location_suffix(location: str) -> tuple[str, str]:
    if "," not in location:
        return location, ""
    icon_path, index = location.rsplit(",", 1)
    if index.strip().lstrip("-").isdigit():
        return icon_path, f",{index.strip()}"
    return location, ""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.app_paths import AppPaths
from src.icon_preview import extract_icon_to_ico


RESOURCE_EXTENSIONS = {".exe", ".dll", ".mun", ".ocx", ".icl", ".cpl"}


def default_backup_dir() -> Path:
    return AppPaths.for_runtime().backup_dir


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def backup_icon_location(icon_location: str, target_path: Path, backup_dir: Path | None = None) -> Path | None:
    if not icon_location:
        return None
    icon_path_text, icon_index = parse_icon_location(icon_location)
    icon_path = Path(os.path.expandvars(icon_path_text))
    if not icon_path.exists():
        return None

    backup_root = backup_dir or default_backup_dir()
    backup_root.mkdir(parents=True, exist_ok=True)
    stem = _backup_stem(target_path, icon_path, icon_index)
    destination = _unique_path(backup_root / f"{stem}.ico")

    if icon_path.suffix.lower() == ".ico":
        shutil.copy2(icon_path, destination)
        return destination
    if icon_path.suffix.lower() in RESOURCE_EXTENSIONS or icon_index:
        return extract_icon_to_ico(icon_path, icon_index, destination)
    return None


def backup_desktop_ini(folder_path: Path, backup_dir: Path | None = None) -> Path | None:
    desktop_ini = folder_path / "desktop.ini"
    if not desktop_ini.exists():
        return None
    backup_root = backup_dir or default_backup_dir()
    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = _unique_path(backup_root / f"{_hash_text(str(folder_path))}-{timestamp}-desktop.ini")
    shutil.copy2(desktop_ini, destination)
    return destination


def original_icon_available(icon_location: str) -> bool:
    if not icon_location:
        return False
    icon_path_text, _icon_index = parse_icon_location(icon_location)
    return Path(os.path.expandvars(icon_path_text)).exists()


def parse_icon_location(icon_location: str) -> tuple[str, int]:
    if "," not in icon_location:
        return icon_location.strip().strip('"'), 0
    path, index = icon_location.rsplit(",", 1)
    try:
        return path.strip().strip('"'), int(index)
    except ValueError:
        return path.strip().strip('"'), 0


def _backup_stem(target_path: Path, source_path: Path, icon_index: int) -> str:
    identity = f"{target_path}|{source_path}|{icon_index}"
    return f"{_hash_text(identity)}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def _hash_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Nao foi possivel criar nome unico de backup em {path.parent}")

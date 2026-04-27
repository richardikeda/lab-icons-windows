from __future__ import annotations

from pathlib import Path

from src.folder_manager import FolderIconError, apply_folder_icon, folder_has_icon, read_folder_icon, remove_folder_icon
from src.mapping_store import AppMapping, MappingStore
from src.shortcut_manager import ShortcutError, apply_shortcut_icon, read_shortcut_icon, restore_shortcut_icon, shortcut_has_icon


def apply_mapping(mapping: AppMapping) -> None:
    target = Path(mapping.shortcut_path)
    if mapping.target_type == "folder":
        icon = _folder_asset(mapping)
        apply_folder_icon(target, icon)
    else:
        icon = Path(mapping.ico_path)
        apply_shortcut_icon(target, icon)


def mapping_has_icon(mapping: AppMapping) -> bool:
    target = Path(mapping.shortcut_path)
    if mapping.target_type == "folder":
        icon = _folder_asset(mapping)
        return folder_has_icon(target, icon)
    icon = Path(mapping.ico_path)
    return shortcut_has_icon(target, icon)


def reapply_changed(store: MappingStore, only_global: bool = False) -> tuple[int, int]:
    if only_global and not store.settings.get("global_auto_reapply", False):
        return 0, 0
    applied = 0
    errors = 0
    for mapping in store.mappings:
        if not mapping.is_customized:
            continue
        if not store.settings.get("global_auto_reapply", False) and not mapping.auto_reapply:
            continue
        try:
            if not mapping_has_icon(mapping):
                apply_mapping(mapping)
                applied += 1
        except (ShortcutError, FolderIconError):
            errors += 1
    return applied, errors


def capture_original_icon(mapping: AppMapping) -> None:
    if mapping.target_type == "folder":
        current_icon = read_folder_icon(Path(mapping.shortcut_path))
        if current_icon and not mapping.original_icon:
            mapping.original_icon = current_icon
    elif mapping.target_type == "shortcut":
        try:
            current_icon = read_shortcut_icon(Path(mapping.shortcut_path))
        except ShortcutError:
            current_icon = ""
        if current_icon and (not mapping.original_icon or mapping.original_icon.lower().endswith(".lnk")):
            mapping.original_icon = current_icon


def restore_mapping(mapping: AppMapping) -> None:
    if mapping.target_type == "folder":
        remove_folder_icon(Path(mapping.shortcut_path))
    elif mapping.original_icon:
        restore_shortcut_icon(Path(mapping.shortcut_path), mapping.original_icon)


def _folder_asset(mapping: AppMapping) -> Path:
    return Path(mapping.ico_path)

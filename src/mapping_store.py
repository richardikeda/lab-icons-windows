from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AppMapping:
    id: str
    program_name: str
    program_group: str
    shortcut_path: str
    icon_group: str
    source_icon: str
    ico_path: str
    auto_reapply: bool = False
    target_type: str = "shortcut"
    png_path: str = ""
    preferred_asset: str = "ico"
    original_icon: str = ""
    is_customized: bool = False
    known_key: str = ""


class MappingStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = {
            "auto_check_seconds": 60,
            "global_auto_reapply": False,
            "startup_reapply_enabled": False,
        }
        self.mappings: list[AppMapping] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return

        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.settings = data.get("settings", self.settings)
        self.mappings = [AppMapping(**self._normalize_mapping(item)) for item in data.get("mappings", [])]

    def save(self) -> None:
        payload = {
            "version": 1,
            "settings": self.settings,
            "mappings": [asdict(mapping) for mapping in self.mappings],
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_mapping(
        self,
        *,
        program_name: str,
        program_group: str,
        shortcut_path: str,
        icon_group: str,
        source_icon: str,
        ico_path: str,
        auto_reapply: bool,
        target_type: str = "shortcut",
        png_path: str = "",
        preferred_asset: str = "ico",
        original_icon: str = "",
        is_customized: bool = False,
        known_key: str = "",
    ) -> AppMapping:
        mapping = AppMapping(
            id=str(uuid.uuid4()),
            program_name=program_name,
            program_group=program_group,
            shortcut_path=shortcut_path,
            icon_group=icon_group,
            source_icon=source_icon,
            ico_path=ico_path,
            auto_reapply=auto_reapply,
            target_type=target_type,
            png_path=png_path,
            preferred_asset=preferred_asset,
            original_icon=original_icon,
            is_customized=is_customized,
            known_key=known_key,
        )
        self.mappings.append(mapping)
        self.save()
        return mapping

    def update_mapping(self, mapping: AppMapping) -> None:
        for index, existing in enumerate(self.mappings):
            if existing.id == mapping.id:
                self.mappings[index] = mapping
                self.save()
                return
        raise ValueError(f"Mapping not found: {mapping.id}")

    def remove_mapping(self, mapping_id: str) -> None:
        self.mappings = [mapping for mapping in self.mappings if mapping.id != mapping_id]
        self.save()

    def _normalize_mapping(self, item: dict) -> dict:
        normalized = dict(item)
        normalized.setdefault("target_type", "shortcut")
        normalized.setdefault("png_path", "")
        normalized.setdefault("preferred_asset", "ico")
        normalized.setdefault("original_icon", "")
        normalized.setdefault("is_customized", bool(normalized.get("auto_reapply")))
        normalized.setdefault("known_key", "")
        return normalized

from __future__ import annotations

import json
import os
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
    theme_name: str = ""


class MappingStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = {
            "auto_check_seconds": 60,
            "global_auto_reapply": True,
            "startup_reapply_enabled": True,
        }
        self.mappings: list[AppMapping] = []
        self._last_saved_serialized: str | None = None
        self._last_saved_signature: tuple[int, int] | None = None
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return

        data = self._load_json()
        self.settings = data.get("settings", self.settings)
        self.mappings = [AppMapping(**self._normalize_mapping(item)) for item in data.get("mappings", [])]
        self._remember_saved_state()

    def save(self) -> None:
        serialized = self._serialize()
        if serialized == self._last_saved_serialized and self._current_signature() == self._last_saved_signature:
            return

        temp_path = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(serialized, encoding="utf-8")
            os.replace(temp_path, self.path)
            self._remember_saved_state(serialized)
        finally:
            if temp_path.exists():
                temp_path.unlink()

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
        theme_name: str = "",
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
            theme_name=theme_name,
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
        normalized.setdefault("theme_name", "")
        return normalized

    def _load_json(self) -> dict:
        last_error: UnicodeDecodeError | json.JSONDecodeError | None = None
        for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
            try:
                text = self.path.read_text(encoding=encoding)
                if self._is_empty_or_comment_only(text):
                    return {"settings": self.settings, "mappings": []}
                return json.loads(text)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                last_error = error
                continue
        if last_error:
            raise last_error
        raise ValueError(f"Unable to load mapping file: {self.path}")

    def _serialize(self) -> str:
        payload = {
            "version": 1,
            "settings": self.settings,
            "mappings": [asdict(mapping) for mapping in self.mappings],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def _current_signature(self) -> tuple[int, int] | None:
        try:
            stat = self.path.stat()
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    def _remember_saved_state(self, serialized: str | None = None) -> None:
        self._last_saved_serialized = serialized if serialized is not None else self._serialize()
        self._last_saved_signature = self._current_signature()

    def _is_empty_or_comment_only(self, text: str) -> bool:
        lines = [line.strip() for line in text.splitlines()]
        return all(not line or line.startswith("#") for line in lines)

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


APP_DATA_DIR_NAME = "LabIcons"


@dataclass(frozen=True)
class AppPaths:
    app_dir: Path
    data_dir: Path
    input_dir: Path
    output_dir: Path
    config_dir: Path
    mappings_file: Path
    performance_log: Path
    icon_cache_dir: Path
    managed_shortcuts_dir: Path
    entrypoint: Path
    is_frozen: bool

    @classmethod
    def for_runtime(cls) -> "AppPaths":
        is_frozen = bool(getattr(sys, "frozen", False))
        app_dir = Path(sys.executable).resolve().parent if is_frozen else Path(__file__).resolve().parents[1]
        data_dir = _local_app_data_dir() if is_frozen else app_dir
        entrypoint = Path(sys.executable).resolve() if is_frozen else app_dir / "app.py"
        paths = cls.from_dirs(app_dir=app_dir, data_dir=data_dir, entrypoint=entrypoint, is_frozen=is_frozen)
        if is_frozen:
            _copy_legacy_mutable_data(app_dir, paths.data_dir)
        return paths

    @classmethod
    def from_dirs(
        cls,
        *,
        app_dir: Path,
        data_dir: Path,
        entrypoint: Path | None = None,
        is_frozen: bool = False,
    ) -> "AppPaths":
        app_dir = Path(app_dir)
        data_dir = Path(data_dir)
        config_dir = data_dir / "config"
        return cls(
            app_dir=app_dir,
            data_dir=data_dir,
            input_dir=data_dir / "icons-in",
            output_dir=data_dir / "icons-out",
            config_dir=config_dir,
            mappings_file=config_dir / "mappings.json",
            performance_log=config_dir / "performance.log",
            icon_cache_dir=config_dir / "icon-cache",
            managed_shortcuts_dir=config_dir / "managed-shortcuts",
            entrypoint=Path(entrypoint) if entrypoint else app_dir / "app.py",
            is_frozen=is_frozen,
        )

    def ensure_mutable_dirs(self) -> None:
        for folder in (
            self.input_dir,
            self.output_dir,
            self.config_dir,
            self.icon_cache_dir,
            self.managed_shortcuts_dir,
        ):
            folder.mkdir(parents=True, exist_ok=True)


def coerce_app_paths(value: AppPaths | Path | str) -> AppPaths:
    if isinstance(value, AppPaths):
        return value
    base_dir = Path(value)
    return AppPaths.from_dirs(app_dir=base_dir, data_dir=base_dir)


def _local_app_data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / APP_DATA_DIR_NAME
    return Path.home() / "AppData" / "Local" / APP_DATA_DIR_NAME


def _copy_legacy_mutable_data(app_dir: Path, data_dir: Path) -> None:
    if app_dir == data_dir:
        return
    for name in ("config", "icons-in", "icons-out"):
        source = app_dir / name
        destination = data_dir / name
        if source.exists() and not destination.exists():
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


MAX_THEME_FILES = 512
MAX_THEME_BYTES = 200 * 1024 * 1024
MANIFEST_NAMES = ("theme.json", "config.json", "manifest.json")


class ThemeImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ThemeAssociation:
    program_name: str
    icon_path: Path
    program_group: str
    target_type: str = "shortcut"
    target_path: str = ""


@dataclass(frozen=True)
class ThemeImportResult:
    theme_name: str
    theme_dir: Path
    png_paths: list[Path]
    associations: list[ThemeAssociation]


def import_theme(source: Path, icons_in_dir: Path) -> ThemeImportResult:
    with tempfile.TemporaryDirectory(prefix="lab-icons-theme-") as tmp:
        staging = Path(tmp) / "theme"
        if source.is_dir():
            shutil.copytree(source, staging)
        elif source.suffix.lower() == ".zip":
            _extract_zip(source, staging)
        else:
            raise ThemeImportError("Selecione uma pasta de tema ou um arquivo .zip.")
        return _import_from_staging(staging, icons_in_dir)


def delete_theme(theme_name: str, icons_in_dir: Path) -> Path:
    safe = _safe_name(theme_name)
    theme_dir = icons_in_dir / "themes" / safe
    root = (icons_in_dir / "themes").resolve()
    resolved = theme_dir.resolve()
    if root != resolved and root not in resolved.parents:
        raise ThemeImportError("Tema fora da pasta permitida.")
    if theme_dir.exists():
        shutil.rmtree(theme_dir)
    return theme_dir


def _extract_zip(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    with zipfile.ZipFile(source) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        if len(infos) > MAX_THEME_FILES:
            raise ThemeImportError("Tema muito grande: quantidade de arquivos excedida.")
        for info in infos:
            total += info.file_size
            if total > MAX_THEME_BYTES:
                raise ThemeImportError("Tema muito grande: limite de tamanho excedido.")
            relative = _safe_zip_member(info.filename)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)


def _safe_zip_member(name: str) -> Path:
    normalized = PurePosixPath(name.replace("\\", "/"))
    if normalized.is_absolute() or any(part in {"", ".", ".."} for part in normalized.parts):
        raise ThemeImportError("ZIP contem caminho inseguro.")
    return Path(*normalized.parts)


def _import_from_staging(staging: Path, icons_in_dir: Path) -> ThemeImportResult:
    manifest_path = _find_manifest(staging)
    manifest = _load_manifest(manifest_path)
    theme_name = str(manifest.get("theme") or manifest.get("name") or staging.name).strip() or "Tema"
    safe_theme = _safe_name(theme_name)
    theme_dir = icons_in_dir / "themes" / safe_theme
    theme_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    associations: list[ThemeAssociation] = []
    icons = manifest.get("icons", [])
    if not isinstance(icons, list):
        raise ThemeImportError("O manifesto deve conter uma lista 'icons'.")

    manifest_base = manifest_path.parent
    for item in icons:
        if not isinstance(item, dict):
            continue
        file_name = str(item.get("file") or item.get("png") or "").strip()
        if not file_name:
            continue
        source_png = _safe_manifest_path(manifest_base, file_name)
        if source_png.suffix.lower() != ".png" or not source_png.exists():
            continue
        group = _safe_name(str(item.get("group") or item.get("program_group") or "default"))
        target = theme_dir / group / _safe_png_name(source_png.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_png, target)
        copied.append(target)
        program_name = str(item.get("program") or item.get("program_name") or item.get("app") or "").strip()
        if program_name:
            associations.append(
                ThemeAssociation(
                    program_name=program_name,
                    icon_path=target,
                    program_group=str(item.get("program_group") or item.get("category") or group),
                    target_type=_normalize_target_type(str(item.get("target_type") or item.get("kind") or "shortcut")),
                    target_path=str(item.get("target_path") or item.get("path") or ""),
                )
            )

    if not copied:
        raise ThemeImportError("Nenhum PNG valido foi encontrado no manifesto do tema.")
    return ThemeImportResult(theme_name=theme_name, theme_dir=theme_dir, png_paths=copied, associations=associations)


def _find_manifest(staging: Path) -> Path:
    for name in MANIFEST_NAMES:
        direct = staging / name
        if direct.exists():
            return direct
    matches = [path for path in staging.rglob("*.json") if path.name.lower() in MANIFEST_NAMES]
    if matches:
        return matches[0]
    raise ThemeImportError("Tema sem theme.json, config.json ou manifest.json.")


def _load_manifest(path: Path) -> dict:
    for encoding in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            data = json.loads(path.read_text(encoding=encoding))
            if not isinstance(data, dict):
                raise ThemeImportError("Manifesto do tema deve ser um objeto JSON.")
            return data
        except UnicodeError:
            continue
        except json.JSONDecodeError as exc:
            raise ThemeImportError(f"Manifesto JSON invalido: {exc}") from exc
    raise ThemeImportError("Nao foi possivel ler o manifesto do tema.")


def _safe_manifest_path(base: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or any(part in {"..", ""} for part in relative.parts):
        raise ThemeImportError("Manifesto contem caminho inseguro.")
    resolved = (base / relative).resolve()
    root = base.resolve()
    if root != resolved and root not in resolved.parents:
        raise ThemeImportError("Manifesto contem caminho fora do tema.")
    return resolved


def _safe_name(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*\x00-\x1f]+', "-", value).strip(" .-_")
    return cleaned[:80] or "Tema"


def _safe_png_name(value: str) -> str:
    name = _safe_name(Path(value).stem)
    return f"{name}.png"


def _normalize_target_type(value: str) -> str:
    return "folder" if value.casefold() in {"folder", "pasta"} else "shortcut"

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.backup_manager import original_icon_available
from src.mapping_store import AppMapping, MappingStore
from src.reapply_service import restore_mapping


@dataclass(frozen=True)
class RollbackCounts:
    total: int
    shortcuts: int
    folders: int
    themed: int
    with_backup: int
    without_backup: int


@dataclass(frozen=True)
class RollbackReportItem:
    mapping_id: str
    program_name: str
    target: str
    target_type: str
    theme: str
    original_icon: str
    backup_icon_path: str
    backup_desktop_ini_path: str
    backup_used: bool
    status: str
    error: str = ""


@dataclass(frozen=True)
class RollbackReport:
    timestamp: str
    totals: RollbackCounts
    restored: list[RollbackReportItem]
    errors: list[RollbackReportItem]


@dataclass(frozen=True)
class RollbackResult:
    report: RollbackReport
    report_path: Path


def rollback_counts(mappings: list[AppMapping]) -> RollbackCounts:
    customized = [mapping for mapping in mappings if mapping.is_customized]
    with_backup = sum(1 for mapping in customized if mapping_has_backup(mapping))
    return RollbackCounts(
        total=len(customized),
        shortcuts=sum(1 for mapping in customized if mapping.target_type != "folder"),
        folders=sum(1 for mapping in customized if mapping.target_type == "folder"),
        themed=sum(1 for mapping in customized if bool(mapping.theme_name)),
        with_backup=with_backup,
        without_backup=len(customized) - with_backup,
    )


def restore_all_to_default(
    store: MappingStore,
    report_dir: Path,
    *,
    restore_func: Callable[[AppMapping], None] = restore_mapping,
) -> RollbackResult:
    timestamp = _utc_timestamp()
    restored: list[RollbackReportItem] = []
    errors: list[RollbackReportItem] = []
    counts = rollback_counts(store.mappings)
    for mapping in store.mappings:
        if not mapping.is_customized:
            continue
        backup_used = rollback_would_use_backup(mapping)
        try:
            restore_func(mapping)
        except Exception as exc:
            errors.append(_report_item(mapping, "error", backup_used, str(exc)))
            continue
        mapping.is_customized = False
        restored.append(_report_item(mapping, "restored", backup_used))
    store.save()
    report = RollbackReport(timestamp=timestamp, totals=counts, restored=restored, errors=errors)
    report_path = save_rollback_report(report, report_dir)
    return RollbackResult(report=report, report_path=report_path)


def save_rollback_report(report: RollbackReport, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromisoformat(report.timestamp.replace("Z", "+00:00")).strftime("%Y%m%d-%H%M%S")
    path = _unique_report_path(report_dir / f"rollback-report-{stamp}.json")
    payload = asdict(report)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def mapping_has_backup(mapping: AppMapping) -> bool:
    if mapping.target_type == "folder":
        return bool(mapping.backup_desktop_ini_path)
    return bool(mapping.backup_icon_path)


def rollback_would_use_backup(mapping: AppMapping) -> bool:
    if mapping.target_type == "folder":
        return bool(mapping.backup_desktop_ini_path)
    if mapping.backup_icon_path and not original_icon_available(mapping.original_icon):
        return True
    return bool(mapping.backup_icon_path and not mapping.original_icon)


def _report_item(mapping: AppMapping, status: str, backup_used: bool, error: str = "") -> RollbackReportItem:
    return RollbackReportItem(
        mapping_id=mapping.id,
        program_name=mapping.program_name,
        target=mapping.shortcut_path,
        target_type=mapping.target_type,
        theme=mapping.theme_name,
        original_icon=mapping.original_icon,
        backup_icon_path=mapping.backup_icon_path,
        backup_desktop_ini_path=mapping.backup_desktop_ini_path,
        backup_used=backup_used,
        status=status,
        error=error,
    )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _unique_report_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Nao foi possivel criar relatorio de rollback em {path.parent}")

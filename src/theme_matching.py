from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from src.app_discovery import DiscoveredTarget, normalized_target_key
from src.icon_pipeline import icon_group_for, output_path_for, png_output_path_for, process_icon
from src.mapping_store import AppMapping, MappingStore
from src.reapply_service import apply_mapping, capture_original_icon
from src.theme_manager import ThemeIconItem, ThemeImportResult, load_manual_associations, save_manual_association


FUZZY_THRESHOLD = 0.72


@dataclass(frozen=True)
class ThemeReviewItem:
    icon_path: Path
    expected_program: str
    program_group: str
    target_type: str
    target_path: str
    status: str
    target: DiscoveredTarget | None = None
    suggestion_score: float = 0.0
    confirmed: bool = False
    error: str = ""


@dataclass(frozen=True)
class ThemeApplySummary:
    applied: int = 0
    ignored: int = 0
    errors: int = 0


def build_theme_review(result: ThemeImportResult, targets: list[DiscoveredTarget]) -> list[ThemeReviewItem]:
    target_by_key = {target.key: target for target in targets}
    manual = load_manual_associations(result.theme_dir)
    reviewed: list[ThemeReviewItem] = []
    for item in result.items:
        key = _manual_key(result.theme_dir, item.icon_path)
        if key in manual and manual[key] in target_by_key:
            reviewed.append(_review_item(item, "manual", target_by_key[manual[key]], 1.0, True))
            continue
        exact = exact_match(item, targets)
        if exact:
            reviewed.append(_review_item(item, "found", exact, 1.0, True))
            continue
        suggestion, score = fuzzy_match(item, targets)
        if suggestion:
            reviewed.append(_review_item(item, "suggestion", suggestion, score, False))
            continue
        reviewed.append(_review_item(item, "missing", None, 0.0, False))
    return reviewed


def exact_match(item: ThemeIconItem, targets: list[DiscoveredTarget]) -> DiscoveredTarget | None:
    if item.target_path:
        normalized = normalized_target_key(Path(item.target_path))
        for target in targets:
            if normalized_target_key(Path(target.path)) == normalized:
                return target
    expected = normalize_name(item.program_name)
    if not expected:
        return None
    for target in _compatible_targets(item.target_type, targets):
        if normalize_name(target.name) == expected:
            return target
    return None


def fuzzy_match(item: ThemeIconItem, targets: list[DiscoveredTarget]) -> tuple[DiscoveredTarget | None, float]:
    expected = normalize_name(item.program_name)
    if not expected:
        return None, 0.0
    best_target: DiscoveredTarget | None = None
    best_score = 0.0
    for target in _compatible_targets(item.target_type, targets):
        score = difflib.SequenceMatcher(None, expected, normalize_name(target.name)).ratio()
        if score > best_score:
            best_target = target
            best_score = score
    if best_target and best_score >= FUZZY_THRESHOLD:
        return best_target, best_score
    return None, best_score


def confirm_suggestion(item: ThemeReviewItem) -> ThemeReviewItem:
    if item.status != "suggestion" or item.target is None:
        return item
    return replace(item, status="manual", confirmed=True)


def associate_manually(result: ThemeImportResult, item: ThemeReviewItem, target: DiscoveredTarget) -> ThemeReviewItem:
    save_manual_association(result.theme_dir, item.icon_path, target.key)
    return replace(item, status="manual", target=target, suggestion_score=1.0, confirmed=True)


def apply_confirmed_theme_items(
    *,
    theme_name: str,
    items: list[ThemeReviewItem],
    store: MappingStore,
    input_dir: Path,
    output_dir: Path,
    ensure_mapping: Callable[[ThemeReviewItem, Path], AppMapping | None],
    process_icon_func: Callable[[Path, Path, Path], object] = process_icon,
    capture_func: Callable[[AppMapping], None] = capture_original_icon,
    apply_func: Callable[[AppMapping], None] = apply_mapping,
) -> ThemeApplySummary:
    applied = 0
    ignored = 0
    errors = 0
    for item in items:
        if not item.confirmed or item.target is None:
            ignored += 1
            continue
        generated = output_path_for(input_dir, output_dir, item.icon_path)
        try:
            if not generated.exists():
                process_icon_func(input_dir, output_dir, item.icon_path)
            mapping = ensure_mapping(item, generated)
            if not mapping:
                errors += 1
                continue
            mapping.ico_path = str(generated)
            mapping.png_path = str(png_output_path_for(input_dir, output_dir, item.icon_path))
            mapping.source_icon = str(item.icon_path)
            mapping.icon_group = icon_group_for(input_dir, item.icon_path)
            mapping.program_group = item.program_group or mapping.program_group
            mapping.theme_name = theme_name
            mapping.auto_reapply = True
            store.update_mapping(mapping)
            capture_func(mapping)
            apply_func(mapping)
            mapping.is_customized = True
            mapping.auto_reapply = True
            store.update_mapping(mapping)
            applied += 1
        except Exception:
            errors += 1
    return ThemeApplySummary(applied=applied, ignored=ignored, errors=errors)


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _compatible_targets(target_type: str, targets: list[DiscoveredTarget]) -> list[DiscoveredTarget]:
    if target_type == "folder":
        return [target for target in targets if target.target_type == "folder"]
    return [target for target in targets if target.target_type in {"shortcut", "appx"}]


def _review_item(
    item: ThemeIconItem,
    status: str,
    target: DiscoveredTarget | None,
    score: float,
    confirmed: bool,
) -> ThemeReviewItem:
    return ThemeReviewItem(
        icon_path=item.icon_path,
        expected_program=item.program_name or item.icon_path.stem,
        program_group=item.program_group,
        target_type=item.target_type,
        target_path=item.target_path,
        status=status,
        target=target,
        suggestion_score=score,
        confirmed=confirmed,
    )


def _manual_key(theme_dir: Path, icon_path: Path) -> str:
    try:
        return str(icon_path.relative_to(theme_dir)).replace("\\", "/")
    except ValueError:
        return icon_path.name

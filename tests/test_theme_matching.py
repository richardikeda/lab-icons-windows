from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from src.app_discovery import DiscoveredTarget
from src.mapping_store import MappingStore
from src.theme_manager import ThemeIconItem, ThemeImportResult, load_manual_associations
from src.theme_matching import (
    apply_confirmed_theme_items,
    associate_manually,
    build_theme_review,
    confirm_suggestion,
    exact_match,
    fuzzy_match,
)


def target(name: str, key: str | None = None, target_type: str = "shortcut") -> DiscoveredTarget:
    key = key or f"{target_type}:{name}"
    return DiscoveredTarget(
        key=key,
        name=name,
        group="Apps",
        path=f"C:/{name}.lnk" if target_type != "folder" else f"C:/{name}",
        target_type=target_type,
    )


class ThemeMatchingTests(unittest.TestCase):
    def test_exact_matching_uses_normalized_program_name(self) -> None:
        item = ThemeIconItem(icon_path=Path("spotify.png"), program_name="Spotify", target_type="shortcut")

        found = exact_match(item, [target("Spotify"), target("Slack")])

        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Spotify")

    def test_fuzzy_matching_suggests_without_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            icon = Path(tmp) / "spotfy.png"
            result = ThemeImportResult(
                theme_name="Demo",
                theme_dir=Path(tmp),
                png_paths=[icon],
                items=[ThemeIconItem(icon_path=icon, program_name="Spotfy")],
                associations=[],
            )

            suggestion, score = fuzzy_match(result.items[0], [target("Spotify")])
            review = build_theme_review(result, [target("Spotify")])

            self.assertIsNotNone(suggestion)
            self.assertGreaterEqual(score, 0.72)
            self.assertEqual(review[0].status, "suggestion")
            self.assertFalse(review[0].confirmed)

            confirmed = confirm_suggestion(review[0])

            self.assertTrue(confirmed.confirmed)
            self.assertEqual(confirmed.status, "manual")

    def test_item_without_destination_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            icon = Path(tmp) / "unknown.png"
            result = ThemeImportResult(
                theme_name="Demo",
                theme_dir=Path(tmp),
                png_paths=[icon],
                items=[ThemeIconItem(icon_path=icon, program_name="Definitely Missing")],
                associations=[],
            )

            review = build_theme_review(result, [target("Spotify")])

            self.assertEqual(review[0].status, "missing")
            self.assertIsNone(review[0].target)

    def test_manual_association_persists_and_is_reused_by_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme_dir = Path(tmp) / "theme"
            icon = theme_dir / "Media" / "chat.png"
            icon.parent.mkdir(parents=True)
            icon.write_bytes(b"png")
            result = ThemeImportResult(
                theme_name="Demo",
                theme_dir=theme_dir,
                png_paths=[icon],
                items=[ThemeIconItem(icon_path=icon, program_name="Chat App")],
                associations=[],
            )
            chosen = target("Discord", "shortcut:discord")
            review = build_theme_review(result, [chosen])

            associated = associate_manually(result, review[0], chosen)
            rebuilt = build_theme_review(result, [chosen])

            self.assertTrue(associated.confirmed)
            self.assertEqual(load_manual_associations(theme_dir), {"Media/chat.png": "shortcut:discord"})
            self.assertEqual(rebuilt[0].status, "manual")
            self.assertTrue(rebuilt[0].confirmed)
            self.assertEqual(rebuilt[0].target, chosen)

    def test_apply_confirmed_theme_items_partially_counts_error_and_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / "icons-in"
            output_dir = base / "icons-out"
            source_ok = input_dir / "themes" / "Demo" / "ok.png"
            source_error = input_dir / "themes" / "Demo" / "error.png"
            source_ignored = input_dir / "themes" / "Demo" / "ignored.png"
            source_ok.parent.mkdir(parents=True)
            for path in (source_ok, source_error, source_ignored):
                Image.new("RGBA", (16, 16), (20, 40, 80, 255)).save(path)
            store = MappingStore(base / "config" / "mappings.json")
            ok_target = target("OK", "shortcut:ok")
            error_target = target("Error", "shortcut:error")
            items = [
                build_item(source_ok, "OK", ok_target, confirmed=True),
                build_item(source_error, "Error", error_target, confirmed=True),
                build_item(source_ignored, "Ignored", None, confirmed=False),
            ]

            def ensure_mapping(item, generated):
                if item.expected_program == "Error":
                    raise RuntimeError("boom")
                return store.add_mapping(
                    program_name=item.expected_program,
                    program_group="Apps",
                    shortcut_path=item.target.path,
                    icon_group="default",
                    source_icon="",
                    ico_path=str(generated),
                    auto_reapply=True,
                    target_type="shortcut",
                    known_key=item.target.key,
                )

            summary = apply_confirmed_theme_items(
                theme_name="Demo",
                items=items,
                store=store,
                input_dir=input_dir,
                output_dir=output_dir,
                ensure_mapping=ensure_mapping,
                capture_func=mock.Mock(),
                apply_func=mock.Mock(),
            )

            self.assertEqual(summary.applied, 1)
            self.assertEqual(summary.ignored, 1)
            self.assertEqual(summary.errors, 1)
            self.assertEqual(store.mappings[0].theme_name, "Demo")
            self.assertTrue(store.mappings[0].is_customized)


def build_item(path: Path, name: str, found: DiscoveredTarget | None, confirmed: bool):
    from src.theme_matching import ThemeReviewItem

    return ThemeReviewItem(
        icon_path=path,
        expected_program=name,
        program_group="Apps",
        target_type="shortcut",
        target_path="",
        status="found" if found else "missing",
        target=found,
        confirmed=confirmed,
    )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.mapping_store import MappingStore
from src.rollback_report import restore_all_to_default, rollback_counts


class RollbackReportTests(unittest.TestCase):
    def test_rollback_total_success_preserves_mappings_and_theme_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = MappingStore(base / "config" / "mappings.json")
            first = add_mapping(
                store,
                "Slack",
                "shortcut",
                theme_name="Work Theme",
                backup_icon_path=str(base / "Backups" / "slack.ico"),
            )
            second = add_mapping(
                store,
                "Docs",
                "folder",
                backup_desktop_ini_path=str(base / "Backups" / "docs-desktop.ini"),
            )
            restored_ids: list[str] = []

            result = restore_all_to_default(
                store,
                base / "Logs",
                restore_func=lambda mapping: restored_ids.append(mapping.id),
            )

            self.assertEqual(restored_ids, [first.id, second.id])
            self.assertEqual(len(store.mappings), 2)
            self.assertFalse(first.is_customized)
            self.assertFalse(second.is_customized)
            self.assertEqual(first.theme_name, "Work Theme")
            self.assertEqual(first.source_icon, "icons-in/themes/Work/slack.png")
            self.assertEqual(first.ico_path, "icons-out/ico/themes/Work/slack.ico")
            self.assertEqual(first.png_path, "icons-out/png/themes/Work/slack.png")
            self.assertTrue(result.report_path.exists())
            payload = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["totals"]["total"], 2)
            self.assertEqual(len(payload["restored"]), 2)
            self.assertEqual(payload["errors"], [])

    def test_rollback_partial_failure_keeps_failed_mapping_customized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = MappingStore(base / "config" / "mappings.json")
            ok = add_mapping(store, "OK", "shortcut")
            fail = add_mapping(store, "Fail", "folder", theme_name="Theme")

            def restore(mapping):
                if mapping.id == fail.id:
                    raise RuntimeError("restore failed")

            result = restore_all_to_default(store, base / "Logs", restore_func=restore)

            self.assertFalse(ok.is_customized)
            self.assertTrue(fail.is_customized)
            self.assertEqual(len(store.mappings), 2)
            self.assertEqual(len(result.report.restored), 1)
            self.assertEqual(len(result.report.errors), 1)
            self.assertEqual(result.report.errors[0].theme, "Theme")
            self.assertIn("restore failed", result.report.errors[0].error)

    def test_rollback_counts_shortcuts_folders_themes_and_backups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MappingStore(Path(tmp) / "mappings.json")
            add_mapping(store, "Shortcut", "shortcut", backup_icon_path="C:/backup.ico")
            add_mapping(store, "Folder", "folder", backup_desktop_ini_path="C:/desktop.ini", theme_name="Theme")
            add_mapping(store, "NoBackup", "shortcut")
            store.add_mapping(
                program_name="Inactive",
                program_group="Apps",
                shortcut_path="C:/Inactive.lnk",
                icon_group="default",
                source_icon="",
                ico_path="",
                auto_reapply=False,
                target_type="shortcut",
                is_customized=False,
            )

            counts = rollback_counts(store.mappings)

            self.assertEqual(counts.total, 3)
            self.assertEqual(counts.shortcuts, 2)
            self.assertEqual(counts.folders, 1)
            self.assertEqual(counts.themed, 1)
            self.assertEqual(counts.with_backup, 2)
            self.assertEqual(counts.without_backup, 1)

    def test_report_records_backup_paths_and_backup_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            store = MappingStore(base / "config" / "mappings.json")
            backup = base / "Backups" / "missing.ico"
            backup.parent.mkdir()
            backup.write_bytes(b"ico")
            mapping = add_mapping(
                store,
                "Missing",
                "shortcut",
                original_icon=str(base / "missing.exe") + ",0",
                backup_icon_path=str(backup),
            )

            result = restore_all_to_default(store, base / "Logs", restore_func=lambda _mapping: None)

            item = result.report.restored[0]
            self.assertEqual(item.mapping_id, mapping.id)
            self.assertEqual(item.backup_icon_path, str(backup))
            self.assertTrue(item.backup_used)


def add_mapping(
    store: MappingStore,
    name: str,
    target_type: str,
    *,
    theme_name: str = "",
    original_icon: str = "C:/Original.exe,0",
    backup_icon_path: str = "",
    backup_desktop_ini_path: str = "",
):
    return store.add_mapping(
        program_name=name,
        program_group="Apps",
        shortcut_path=f"C:/{name}" + ("" if target_type == "folder" else ".lnk"),
        icon_group="themes/Work",
        source_icon="icons-in/themes/Work/slack.png",
        ico_path="icons-out/ico/themes/Work/slack.ico",
        png_path="icons-out/png/themes/Work/slack.png",
        auto_reapply=True,
        target_type=target_type,
        original_icon=original_icon,
        backup_icon_path=backup_icon_path,
        backup_desktop_ini_path=backup_desktop_ini_path,
        is_customized=True,
        theme_name=theme_name,
    )


if __name__ == "__main__":
    unittest.main()

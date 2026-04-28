from __future__ import annotations

import queue
import tempfile
import threading
import time
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest import mock

from PIL import Image

from src.app_discovery import _discover_shortcuts, _group_for_name, discover_targets
from src.folder_manager import _managed_icon_name, _merge_desktop_ini, read_folder_icon
import src.folder_manager as folder_manager
import src.icon_pipeline as icon_pipeline
from src.icon_pipeline import discover_png_entries, output_path_for, process_icon, processed_outputs_current, snapshot_pngs
from src.mapping_store import MappingStore
import src.reapply_service as reapply_service
from src.shortcut_manager import _file_digest
from src.ui import IconMapperApp
from src.ui import build_gallery_entries, discover_gallery_icons, remember_icon_image


class IconPipelineTests(unittest.TestCase):
    def test_discover_png_entries_capture_mtime_once_for_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "icons-in"
            source = input_dir / "social" / "whatsapp.png"
            source.parent.mkdir(parents=True)
            Image.new("RGBA", (16, 16), (0, 180, 90, 255)).save(source)

            entries = discover_png_entries(input_dir)

            self.assertEqual([path for path, _mtime_ns in entries], [source])
            self.assertEqual(snapshot_pngs(entries), ((str(source), source.stat().st_mtime_ns),))

    def test_process_icon_generates_clean_png_and_ico(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / "icons-in"
            output_dir = base / "icons-out"
            source = input_dir / "social" / "whatsapp.png"
            source.parent.mkdir(parents=True)
            image = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
            for x in range(16, 48):
                for y in range(16, 48):
                    image.putpixel((x, y), (0, 180, 90, 255))
            image.save(source)

            processed = process_icon(input_dir, output_dir, source)

            self.assertTrue(processed.output_path.exists())
            self.assertTrue(processed.png_output_path.exists())
            self.assertEqual(processed.output_path, output_path_for(input_dir, output_dir, source))
            with Image.open(processed.output_path) as ico:
                self.assertIn((256, 256), ico.ico.sizes())
                self.assertIn((96, 96), ico.ico.sizes())
            with Image.open(processed.png_output_path) as png:
                self.assertEqual(png.size, (1024, 1024))

    def test_process_icon_reuses_square_canvas_for_png_and_ico(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / "icons-in"
            output_dir = base / "icons-out"
            source = input_dir / "square-check.png"
            source.parent.mkdir(parents=True)
            Image.new("RGBA", (80, 48), (20, 40, 60, 255)).save(source)

            original_fit = icon_pipeline._fit_square_canvas
            with mock.patch("src.icon_pipeline._fit_square_canvas", wraps=original_fit) as fit_square:
                process_icon(
                    input_dir,
                    output_dir,
                    source,
                    remove_white_background=False,
                    remove_corner_marks=False,
                )

            self.assertEqual(fit_square.call_count, 1)

    def test_processed_outputs_current_requires_fresh_ico_and_clean_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / "icons-in"
            output_dir = base / "icons-out"
            source = input_dir / "social" / "whatsapp.png"
            source.parent.mkdir(parents=True)
            Image.new("RGBA", (32, 32), (0, 180, 90, 255)).save(source)

            process_icon(input_dir, output_dir, source)
            self.assertTrue(processed_outputs_current(input_dir, output_dir, source))

            (output_dir / "png" / "social" / "whatsapp.png").unlink()
            self.assertFalse(processed_outputs_current(input_dir, output_dir, source))

    def test_processed_outputs_current_detects_newer_source_than_generated_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / "icons-in"
            output_dir = base / "icons-out"
            source = input_dir / "social" / "whatsapp.png"
            source.parent.mkdir(parents=True)
            Image.new("RGBA", (32, 32), (0, 180, 90, 255)).save(source)

            process_icon(input_dir, output_dir, source)
            time.sleep(0.02)
            Image.new("RGBA", (32, 32), (255, 80, 80, 255)).save(source)

            self.assertFalse(processed_outputs_current(input_dir, output_dir, source))

    def test_discover_gallery_icons_skips_output_scan_when_sources_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source_pngs = [base / "icons-in" / "sample.png"]

            with mock.patch.object(Path, "rglob", side_effect=AssertionError("rglob should not run")):
                icons = discover_gallery_icons(source_pngs, base / "icons-out")

            self.assertEqual(icons, [])

    def test_remember_icon_image_replaces_stale_signature_and_bounds_cache(self) -> None:
        cache: OrderedDict[tuple[Path, int, tuple[int, int] | None], object] = OrderedDict()
        path = Path("icons-in/demo.png")

        remember_icon_image(cache, (path, 44, (1, 100)), object(), limit=2)
        remember_icon_image(cache, (Path("icons-in/older.png"), 44, (1, 50)), object(), limit=2)
        remember_icon_image(cache, (path, 44, (2, 120)), object(), limit=2)

        self.assertEqual(len(cache), 2)
        self.assertNotIn((path, 44, (1, 100)), cache)
        self.assertIn((path, 44, (2, 120)), cache)

        remember_icon_image(cache, (Path("icons-in/newest.png"), 44, (3, 140)), object(), limit=2)

        self.assertEqual(len(cache), 2)
        self.assertNotIn((Path("icons-in/older.png"), 44, (1, 50)), cache)
        self.assertIn((path, 44, (2, 120)), cache)

    def test_build_gallery_entries_precomputes_group_search_and_ready_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / "icons-in"
            output_dir = base / "icons-out"
            source = input_dir / "social" / "whatsapp.png"
            generated = output_dir / "ico" / "social" / "whatsapp.ico"
            fallback_ico = output_dir / "ico" / "archive" / "legacy.ico"
            source.parent.mkdir(parents=True)
            generated.parent.mkdir(parents=True)
            fallback_ico.parent.mkdir(parents=True)
            Image.new("RGBA", (16, 16), (0, 180, 90, 255)).save(source)
            generated.write_bytes(b"ico")
            fallback_ico.write_bytes(b"ico")

            entries = build_gallery_entries(input_dir, output_dir, [source, fallback_ico])

            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].group, "social")
            self.assertEqual(entries[0].relative_text, "social\\whatsapp.png")
            self.assertEqual(entries[0].search_text, "social\\whatsapp.png")
            self.assertEqual(entries[0].generated_path, generated)
            self.assertTrue(entries[0].ready)
            self.assertEqual(entries[1].group, "archive")
            self.assertEqual(entries[1].generated_path, fallback_ico)
            self.assertTrue(entries[1].ready)


class MappingStoreTests(unittest.TestCase):
    def test_customized_mapping_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.json"
            store = MappingStore(path)
            store.add_mapping(
                program_name="WhatsApp",
                program_group="Comunicacao",
                shortcut_path="config/managed-shortcuts/WhatsApp.lnk",
                icon_group="social",
                source_icon="icons-in/whatsapp.png",
                ico_path="icons-out/ico/whatsapp.ico",
                png_path="icons-out/png/whatsapp.png",
                auto_reapply=False,
                target_type="shortcut",
                is_customized=True,
                known_key="appx:whatsapp",
            )

            reloaded = MappingStore(path)

            self.assertEqual(len(reloaded.mappings), 1)
            self.assertTrue(reloaded.mappings[0].is_customized)
            self.assertEqual(reloaded.mappings[0].known_key, "appx:whatsapp")

    def test_save_skips_unchanged_mappings_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.json"
            store = MappingStore(path)
            first_stat = path.stat()

            store.save()

            self.assertEqual(path.stat().st_mtime_ns, first_stat.st_mtime_ns)

    def test_save_skips_unchanged_file_without_rereading_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.json"
            store = MappingStore(path)

            with mock.patch.object(Path, "read_text", side_effect=AssertionError("read_text should not run")):
                store.save()

    def test_save_rewrites_when_disk_file_changes_externally(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.json"
            store = MappingStore(path)
            original = path.read_text(encoding="utf-8")
            path.write_text('{"version":999,"settings":{"external":true},"mappings":[]}', encoding="utf-8")

            store.save()

            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_load_accepts_utf16_mappings_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.json"
            path.write_text('{"version": 1, "settings": {}, "mappings": []}', encoding="utf-16")

            store = MappingStore(path)

            self.assertEqual(store.mappings, [])

    def test_load_falls_back_when_first_decode_is_not_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.json"
            path.write_text('{"version": 1, "settings": {}, "mappings": []}', encoding="utf-16-be")

            store = MappingStore(path)

            self.assertEqual(store.mappings, [])

    def test_load_treats_comment_only_mappings_file_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.json"
            path.write_text("# redacted local file\n# recreate on save", encoding="utf-16")

            store = MappingStore(path)

            self.assertEqual(store.mappings, [])

    def test_load_adds_backup_fields_to_legacy_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.json"
            path.write_text(
                """
                {
                  "version": 1,
                  "settings": {},
                  "mappings": [
                    {
                      "id": "legacy",
                      "program_name": "Demo",
                      "program_group": "Dev",
                      "shortcut_path": "Demo.lnk",
                      "icon_group": "dev",
                      "source_icon": "demo.png",
                      "ico_path": "demo.ico"
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            store = MappingStore(path)

            self.assertEqual(store.mappings[0].backup_icon_path, "")
            self.assertEqual(store.mappings[0].backup_desktop_ini_path, "")
            self.assertEqual(store.mappings[0].backup_created_at, "")

    def test_capture_original_replaces_shortcut_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mapping = MappingStore(Path(tmp) / "unused.json").add_mapping(
                program_name="Demo",
                program_group="Dev",
                shortcut_path="C:/Users/demo/Desktop/Demo.lnk",
                icon_group="dev",
                source_icon="",
                ico_path="icons-out/ico/demo.ico",
                auto_reapply=False,
                target_type="shortcut",
                original_icon="C:/Users/demo/Desktop/Demo.lnk",
            )
        original_reader = reapply_service.read_shortcut_icon
        try:
            reapply_service.read_shortcut_icon = lambda _: "C:/Program Files/Demo/demo.exe,0"
            reapply_service.capture_original_icon(mapping)
        finally:
            reapply_service.read_shortcut_icon = original_reader

        self.assertEqual(mapping.original_icon, "C:/Program Files/Demo/demo.exe,0")

    def test_capture_original_copies_shortcut_ico_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            original_icon = base / "original.ico"
            original_icon.write_bytes(b"ico-data")
            backup_dir = base / "Backups"
            mapping = MappingStore(base / "mappings.json").add_mapping(
                program_name="Demo",
                program_group="Dev",
                shortcut_path=str(base / "Demo.lnk"),
                icon_group="dev",
                source_icon="",
                ico_path=str(base / "custom.ico"),
                auto_reapply=False,
                target_type="shortcut",
            )

            with mock.patch("src.reapply_service.read_shortcut_icon", return_value=f"{original_icon},0"):
                with mock.patch("src.backup_manager.default_backup_dir", return_value=backup_dir):
                    reapply_service.capture_original_icon(mapping)

            backup = Path(mapping.backup_icon_path)
            self.assertEqual(mapping.original_icon, f"{original_icon},0")
            self.assertTrue(backup.is_file())
            self.assertEqual(backup.parent, backup_dir)
            self.assertEqual(backup.read_bytes(), b"ico-data")
            self.assertTrue(mapping.backup_created_at)

    def test_capture_original_backs_up_folder_desktop_ini_outside_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = base / "Folder"
            backup_dir = base / "Backups"
            folder.mkdir()
            (folder / "desktop.ini").write_text("[.ShellClassInfo]\nIconFile=old.ico\n", encoding="utf-16")
            mapping = MappingStore(base / "mappings.json").add_mapping(
                program_name="Folder",
                program_group="Pastas",
                shortcut_path=str(folder),
                icon_group="folders",
                source_icon="",
                ico_path=str(base / "custom.ico"),
                auto_reapply=False,
                target_type="folder",
            )

            with mock.patch("src.backup_manager.default_backup_dir", return_value=backup_dir):
                reapply_service.capture_original_icon(mapping)

            backup = Path(mapping.backup_desktop_ini_path)
            self.assertTrue(backup.is_file())
            self.assertEqual(backup.parent, backup_dir)
            self.assertNotEqual(backup.parent, folder)
            self.assertIn("IconFile=old.ico", backup.read_text(encoding="utf-16"))

    def test_restore_shortcut_falls_back_to_backup_when_original_missing(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            backup = base / "Backups" / "original.ico"
            backup.parent.mkdir()
            backup.write_bytes(b"ico")
            mapping = MappingStore(base / "mappings.json").add_mapping(
                program_name="Demo",
                program_group="Dev",
                shortcut_path=str(base / "Demo.lnk"),
                icon_group="dev",
                source_icon="",
                ico_path=str(base / "custom.ico"),
                auto_reapply=False,
                target_type="shortcut",
                original_icon=str(base / "missing.exe") + ",0",
                backup_icon_path=str(backup),
            )

            with mock.patch(
                "src.reapply_service.restore_shortcut_icon",
                side_effect=lambda _p, icon: calls.append(icon),
            ):
                reapply_service.restore_mapping(mapping)

        self.assertEqual(calls, [f"{backup},0"])


class DiscoveryTests(unittest.TestCase):
    def test_known_apps_classification(self) -> None:
        self.assertEqual(_group_for_name("WhatsApp"), "Comunicacao")
        self.assertEqual(_group_for_name("Google Chrome"), "Browsers")
        self.assertEqual(_group_for_name("Visual Studio Code"), "Dev")
        self.assertEqual(_group_for_name("7-Zip Help"), "Pessoal")

    def test_discover_shortcuts_builds_keys_without_path_resolve(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            appdata = base / "AppData"
            desktop = base / "Desktop"
            programs = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            programs.mkdir(parents=True)
            desktop.mkdir(parents=True)
            shortcut = programs / "Demo Tool.lnk"
            shortcut.write_bytes(b"")

            env = {"APPDATA": str(appdata), "PROGRAMDATA": str(base / "ProgramData"), "PUBLIC": str(base / "Public")}
            with mock.patch.dict("os.environ", env, clear=False):
                with mock.patch("pathlib.Path.home", return_value=base):
                    with mock.patch.object(Path, "resolve", side_effect=AssertionError("resolve should not run")):
                        targets = _discover_shortcuts()

            self.assertEqual(len(targets), 1)
            self.assertTrue(targets[0].key.startswith("shortcut:"))
            self.assertEqual(targets[0].path, str(shortcut))

    def test_discover_targets_runs_sources_in_parallel(self) -> None:
        common = [
            DiscoveredTarget(
                key="folder:a",
                name="Desktop",
                group="Pastas do usuario",
                path="C:/Users/demo/Desktop",
                target_type="folder",
            )
        ]
        shortcuts = [
            DiscoveredTarget(
                key="shortcut:a",
                name="Demo",
                group="Pessoal",
                path="C:/Users/demo/Desktop/Demo.lnk",
                target_type="shortcut",
            )
        ]
        apps = [
            DiscoveredTarget(
                key="appx:a",
                name="Store App",
                group="Pessoal",
                path="Store.App",
                target_type="appx",
            )
        ]
        started: queue.Queue[str] = queue.Queue()
        release = threading.Event()

        def gated(name: str, payload: list[DiscoveredTarget]) -> list[DiscoveredTarget]:
            started.put(name)
            release.wait(timeout=1)
            return payload

        with mock.patch("src.app_discovery._discover_common_folders", side_effect=lambda: gated("folders", common)):
            with mock.patch("src.app_discovery._discover_shortcuts", side_effect=lambda: gated("shortcuts", shortcuts)):
                with mock.patch("src.app_discovery._discover_start_apps", side_effect=lambda: gated("apps", apps)):
                    worker = queue.Queue()

                    def run() -> None:
                        worker.put(discover_targets())

                    thread = threading.Thread(target=run)
                    thread.start()
                    seen = {started.get(timeout=1) for _ in range(3)}
                    release.set()
                    thread.join(timeout=1)

        self.assertEqual(seen, {"folders", "shortcuts", "apps"})
        targets = worker.get_nowait()
        self.assertEqual([target.key for target in targets], ["folder:a", "shortcut:a", "appx:a"])


class BatchProcessingTests(unittest.TestCase):
    def test_process_worker_skips_icons_with_current_outputs(self) -> None:
        app = object.__new__(IconMapperApp)
        app.input_dir = Path("icons-in")
        app.output_dir = Path("icons-out")
        app.process_queue = queue.Queue()
        app.perf = mock.Mock()

        with mock.patch("src.ui.processed_outputs_current", return_value=True), mock.patch(
            "src.ui.ThreadPoolExecutor", side_effect=AssertionError("executor should not run")
        ), mock.patch("src.ui.process_icon", side_effect=AssertionError("process_icon should not run")):
            app._process_worker([Path("icons-in") / "one.png", Path("icons-in") / "two.png"])

        self.assertEqual(app.process_queue.get_nowait(), ("finished", 0))
        app.perf.log.assert_called_once()


class FolderIniTests(unittest.TestCase):
    def test_managed_icon_digest_streams_without_read_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            icon = Path(tmp) / "source.ico"
            icon.write_bytes(b"ico-data" * 32)

            with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("read_bytes should not run")):
                folder_name = _managed_icon_name(icon)
                shortcut_digest = _file_digest(icon)

        self.assertEqual(folder_name, f"folder-{shortcut_digest}.ico")
        self.assertEqual(len(shortcut_digest), 12)

    def test_merge_preserves_music_shell_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "desktop.ini"
            path.write_text(
                "\n".join(
                    [
                        "[.ShellClassInfo]",
                        "LocalizedResourceName=@%SystemRoot%\\system32\\shell32.dll,-21790",
                        "InfoTip=@%SystemRoot%\\system32\\shell32.dll,-12689",
                        "IconResource=%SystemRoot%\\system32\\imageres.dll,-108",
                        "IconFile=%SystemRoot%\\system32\\shell32.dll",
                        "IconIndex=-237",
                    ]
                ),
                encoding="utf-16",
            )

            merged = _merge_desktop_ini(path, ".lab-icons-windows\\folder.ico")

            self.assertIn("LocalizedResourceName=", merged)
            self.assertIn("InfoTip=", merged)
            self.assertIn("; LabIconsWindows=1", merged)
            self.assertIn("IconResource=.lab-icons-windows\\folder.ico,0", merged)
            self.assertIn("IconFile=.lab-icons-windows\\folder.ico", merged)
            self.assertNotIn("IconResource=%SystemRoot%", merged)

    def test_existing_desktop_ini_attrs_removed_before_write(self) -> None:
        calls: list[tuple[str, ...]] = []
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            icon = folder / "source.ico"
            desktop_ini = folder / "desktop.ini"
            icon.write_bytes(b"ico")
            desktop_ini.write_text("[.ShellClassInfo]\nIconIndex=0\n", encoding="utf-16")

            original_attrib = folder_manager._attrib
            try:
                folder_manager._attrib = lambda *args: calls.append(tuple(str(arg) for arg in args))
                folder_manager.apply_folder_icon(folder, icon)
            finally:
                folder_manager._attrib = original_attrib

        self.assertIn(("-h", "-s", str(desktop_ini)), calls)

    def test_read_folder_icon_resolves_relative_utf16_iconfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            managed = folder / ".lab-icons-windows" / "folder.ico"
            managed.parent.mkdir()
            managed.write_bytes(b"ico")
            (folder / "desktop.ini").write_text(
                "\n".join(["[.ShellClassInfo]", "IconFile=.lab-icons-windows\\folder.ico", "IconIndex=0"]),
                encoding="utf-16",
            )

            icon = read_folder_icon(folder)

            self.assertEqual(icon, f"{managed},0")

    def test_remove_folder_icon_restores_external_desktop_ini_backup(self) -> None:
        calls: list[tuple[str, ...]] = []
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "Folder"
            folder.mkdir()
            managed = folder / ".lab-icons-windows"
            managed.mkdir()
            desktop_ini = folder / "desktop.ini"
            desktop_ini.write_text(
                "[.ShellClassInfo]\n; LabIconsWindows=1\nIconResource=.lab-icons-windows\\folder.ico,0\n",
                encoding="utf-16",
            )
            external_backup = Path(tmp) / "Backups" / "folder-desktop.ini"
            external_backup.parent.mkdir()
            external_backup.write_text("[.ShellClassInfo]\nIconFile=old.ico\n", encoding="utf-16")

            original_attrib = folder_manager._attrib
            try:
                folder_manager._attrib = lambda *args: calls.append(tuple(str(arg) for arg in args))
                folder_manager.remove_folder_icon(folder, external_backup)
            finally:
                folder_manager._attrib = original_attrib

            self.assertIn("IconFile=old.ico", desktop_ini.read_text(encoding="utf-16"))
            self.assertFalse(managed.exists())


if __name__ == "__main__":
    unittest.main()

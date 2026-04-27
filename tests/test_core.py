from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from src.app_discovery import _group_for_name
from src.folder_manager import _merge_desktop_ini, read_folder_icon
import src.folder_manager as folder_manager
import src.icon_pipeline as icon_pipeline
from src.icon_pipeline import output_path_for, process_icon
from src.mapping_store import MappingStore
import src.reapply_service as reapply_service


class IconPipelineTests(unittest.TestCase):
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


class DiscoveryTests(unittest.TestCase):
    def test_known_apps_classification(self) -> None:
        self.assertEqual(_group_for_name("WhatsApp"), "Comunicacao")
        self.assertEqual(_group_for_name("Google Chrome"), "Browsers")
        self.assertEqual(_group_for_name("Visual Studio Code"), "Dev")
        self.assertEqual(_group_for_name("7-Zip Help"), "Pessoal")


class FolderIniTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

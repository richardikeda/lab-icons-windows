from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from src.theme_manager import ThemeImportError, delete_theme, import_theme, load_manual_associations, save_manual_association


class ThemeManagerTests(unittest.TestCase):
    def test_import_theme_folder_copies_manifest_pngs_grouped_by_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            theme = base / "pack"
            assets = theme / "assets"
            icons_in = base / "icons-in"
            assets.mkdir(parents=True)
            Image.new("RGBA", (32, 32), (20, 120, 240, 255)).save(assets / "spotify.png")
            (theme / "theme.json").write_text(
                json.dumps(
                    {
                        "theme": "Blue Work",
                        "icons": [
                            {
                                "file": "assets/spotify.png",
                                "program": "Spotify",
                                "group": "Media",
                                "program_group": "Comunicacao",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = import_theme(theme, icons_in)

            self.assertEqual(result.theme_name, "Blue Work")
            self.assertEqual(len(result.png_paths), 1)
            self.assertTrue((icons_in / "themes" / "Blue Work" / "Media" / "spotify.png").exists())
            self.assertEqual(result.associations[0].program_name, "Spotify")
            self.assertEqual(result.associations[0].program_group, "Comunicacao")
            self.assertEqual(result.items[0].program_name, "Spotify")
            self.assertEqual(result.items[0].icon_path, result.png_paths[0])

    def test_import_theme_zip_rejects_zip_slip_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            archive = base / "bad.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("../theme.json", "{}")

            with self.assertRaises(ThemeImportError):
                import_theme(archive, base / "icons-in")

    def test_delete_theme_stays_inside_themes_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            icons_in = Path(tmp) / "icons-in"
            theme_dir = icons_in / "themes" / "Demo"
            theme_dir.mkdir(parents=True)

            deleted = delete_theme("Demo", icons_in)

            self.assertEqual(deleted, theme_dir)
            self.assertFalse(theme_dir.exists())

    def test_manual_association_is_saved_inside_imported_theme_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme_dir = Path(tmp) / "icons-in" / "themes" / "Demo"
            icon = theme_dir / "Media" / "spotify.png"
            icon.parent.mkdir(parents=True)
            icon.write_bytes(b"png")

            save_manual_association(theme_dir, icon, "shortcut:C:/Demo.lnk")

            self.assertEqual(load_manual_associations(theme_dir), {"Media/spotify.png": "shortcut:C:/Demo.lnk"})
            self.assertTrue((theme_dir / ".lab-icons-theme-associations.json").exists())


if __name__ == "__main__":
    unittest.main()

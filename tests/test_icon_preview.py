from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from src.icon_preview import preview_for_icon_location


class IconPreviewTests(unittest.TestCase):
    def test_preview_cache_invalidates_when_source_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cache_dir = base / "cache"
            source = base / "Demo.exe"
            source.write_bytes(b"v1")

            extracted = [
                Image.new("RGBA", (8, 8), (220, 30, 30, 255)),
                Image.new("RGBA", (8, 8), (30, 220, 30, 255)),
            ]

            with mock.patch("src.icon_preview._extract_windows_icon", side_effect=extracted) as extract:
                first = preview_for_icon_location(str(source), cache_dir)
                self.assertIsNotNone(first)
                self.assertTrue(first.exists())

                source.write_bytes(b"v2 with updated icon bits")

                second = preview_for_icon_location(str(source), cache_dir)

            self.assertIsNotNone(second)
            self.assertTrue(second.exists())
            self.assertNotEqual(first, second)
            self.assertEqual(extract.call_count, 2)

    def test_windows_icon_extraction_releases_native_handles(self) -> None:
        import src.icon_preview as icon_preview

        calls: list[tuple[str, object]] = []

        class FakeBitmap:
            def CreateCompatibleBitmap(self, hdc: object, width: int, height: int) -> None:
                calls.append(("bitmap.create", width, height))

            def GetBitmapBits(self, signed: bool) -> bytes:
                return bytes([0, 0, 0, 255] * 48 * 48)

        class FakeMemDC:
            def SelectObject(self, bitmap: object) -> None:
                calls.append(("memdc.select", bitmap))

            def FillSolidRect(self, rect: tuple[int, int, int, int], color: object) -> None:
                calls.append(("memdc.fill", rect, color))

            def GetSafeHdc(self) -> str:
                return "safe-hdc"

            def DeleteDC(self) -> None:
                calls.append(("memdc.delete",))

        class FakeDC:
            def CreateCompatibleDC(self) -> FakeMemDC:
                return FakeMemDC()

            def DeleteDC(self) -> None:
                calls.append(("hdc.delete",))

        fake_win32gui = mock.Mock()
        fake_win32gui.GetDC.return_value = "screen-dc"
        fake_win32gui.ExtractIconEx.return_value = (["icon-handle"], [])
        fake_win32gui.RGB.return_value = 0
        fake_win32gui.DrawIconEx.side_effect = lambda *args, **kwargs: calls.append(("draw",))
        fake_win32gui.DestroyIcon.side_effect = lambda icon: calls.append(("destroy", icon))
        fake_win32gui.ReleaseDC.side_effect = lambda hwnd, dc: calls.append(("release", hwnd, dc))

        fake_win32ui = mock.Mock()
        fake_win32ui.CreateDCFromHandle.return_value = FakeDC()
        fake_win32ui.CreateBitmap.return_value = FakeBitmap()

        with mock.patch.dict(
            "sys.modules",
            {
                "win32con": mock.Mock(DI_NORMAL=1),
                "win32gui": fake_win32gui,
                "win32ui": fake_win32ui,
            },
        ):
            image = icon_preview._extract_windows_icon(Path("C:/Demo.exe"), 0)

        self.assertEqual(image.size, (48, 48))
        self.assertIn(("destroy", "icon-handle"), calls)
        self.assertIn(("memdc.delete",), calls)
        self.assertIn(("hdc.delete",), calls)
        self.assertIn(("release", 0, "screen-dc"), calls)


if __name__ == "__main__":
    unittest.main()

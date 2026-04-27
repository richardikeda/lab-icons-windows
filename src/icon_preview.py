from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image


def preview_for_icon_location(icon_location: str, cache_dir: Path) -> Path | None:
    if not icon_location:
        return None
    icon_path, icon_index = _parse_icon_location(icon_location)
    path = Path(icon_path)
    if not path.exists():
        return None
    if path.suffix.lower() in {".png", ".ico"}:
        return path

    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(path, icon_index)
    output = cache_dir / f"{key}.png"
    if output.exists():
        return output
    try:
        image = _extract_windows_icon(path, icon_index)
    except Exception:
        try:
            image = _extract_shell_icon(path)
        except Exception:
            return None
    image.save(output, format="PNG")
    return output


def extract_icon_to_ico(icon_path: Path, icon_index: int, output_path: Path) -> Path | None:
    try:
        image = _extract_windows_icon(icon_path, icon_index)
    except Exception:
        try:
            image = _extract_shell_icon(icon_path)
        except Exception:
            return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        output_path,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return output_path


def _cache_key(path: Path, icon_index: int) -> str:
    try:
        stat = path.stat()
        fingerprint = f"{path}|{icon_index}|{stat.st_mtime_ns}|{stat.st_size}"
    except OSError:
        fingerprint = f"{path}|{icon_index}"
    return hashlib.sha1(fingerprint.encode("utf-8", errors="ignore")).hexdigest()


def _parse_icon_location(icon_location: str) -> tuple[str, int]:
    if "," not in icon_location:
        return icon_location, 0
    path, index = icon_location.rsplit(",", 1)
    try:
        return path.strip('"'), int(index)
    except ValueError:
        return path.strip('"'), 0


def _extract_windows_icon(path: Path, icon_index: int) -> Image.Image:
    try:
        return _extract_private_icon(path, icon_index, 256)
    except Exception:
        pass

    import win32con
    import win32gui
    import win32ui

    large_icons, small_icons = win32gui.ExtractIconEx(str(path), icon_index, 1)
    icons = large_icons or small_icons
    if not icons:
        raise ValueError("No icon found")
    hicon = icons[0]
    width = height = 48
    screen_dc = win32gui.GetDC(0)
    hdc = win32ui.CreateDCFromHandle(screen_dc)
    memdc = hdc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    try:
        bitmap.CreateCompatibleBitmap(hdc, width, height)
        memdc.SelectObject(bitmap)
        memdc.FillSolidRect((0, 0, width, height), win32gui.RGB(0, 0, 0))
        win32gui.DrawIconEx(memdc.GetSafeHdc(), 0, 0, hicon, width, height, 0, None, win32con.DI_NORMAL)
        bits = bitmap.GetBitmapBits(True)
        return Image.frombuffer("RGBA", (width, height), bits, "raw", "BGRA", 0, 1)
    finally:
        win32gui.DestroyIcon(hicon)
        memdc.DeleteDC()
        hdc.DeleteDC()
        win32gui.ReleaseDC(0, screen_dc)


def _extract_private_icon(path: Path, icon_index: int, size: int) -> Image.Image:
    import ctypes

    hicon = ctypes.c_void_p()
    icon_id = ctypes.c_uint()
    extracted = ctypes.windll.user32.PrivateExtractIconsW(
        ctypes.c_wchar_p(str(path)),
        ctypes.c_int(icon_index),
        ctypes.c_int(size),
        ctypes.c_int(size),
        ctypes.byref(hicon),
        ctypes.byref(icon_id),
        ctypes.c_uint(1),
        ctypes.c_uint(0),
    )
    if extracted == 0 or not hicon.value:
        raise ValueError("No icon found")
    try:
        return _hicon_to_image(int(hicon.value), size)
    finally:
        ctypes.windll.user32.DestroyIcon(hicon)


def _extract_shell_icon(path: Path) -> Image.Image:
    import win32con
    import win32gui
    import win32ui
    from win32com.shell import shell, shellcon

    flags = shellcon.SHGFI_ICON | shellcon.SHGFI_LARGEICON
    info = shell.SHGetFileInfo(str(path), 0, flags)
    hicon = info[0]
    width = height = 48
    screen_dc = win32gui.GetDC(0)
    hdc = win32ui.CreateDCFromHandle(screen_dc)
    memdc = hdc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    try:
        bitmap.CreateCompatibleBitmap(hdc, width, height)
        memdc.SelectObject(bitmap)
        memdc.FillSolidRect((0, 0, width, height), win32gui.RGB(0, 0, 0))
        win32gui.DrawIconEx(memdc.GetSafeHdc(), 0, 0, hicon, width, height, 0, None, win32con.DI_NORMAL)
        bits = bitmap.GetBitmapBits(True)
        return Image.frombuffer("RGBA", (width, height), bits, "raw", "BGRA", 0, 1)
    finally:
        win32gui.DestroyIcon(hicon)
        memdc.DeleteDC()
        hdc.DeleteDC()
        win32gui.ReleaseDC(0, screen_dc)


def _hicon_to_image(hicon: int, size: int) -> Image.Image:
    import win32con
    import win32gui
    import win32ui

    screen_dc = win32gui.GetDC(0)
    hdc = win32ui.CreateDCFromHandle(screen_dc)
    memdc = hdc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    try:
        bitmap.CreateCompatibleBitmap(hdc, size, size)
        memdc.SelectObject(bitmap)
        memdc.FillSolidRect((0, 0, size, size), win32gui.RGB(0, 0, 0))
        win32gui.DrawIconEx(memdc.GetSafeHdc(), 0, 0, hicon, size, size, 0, None, win32con.DI_NORMAL)
        bits = bitmap.GetBitmapBits(True)
        return Image.frombuffer("RGBA", (size, size), bits, "raw", "BGRA", 0, 1)
    finally:
        memdc.DeleteDC()
        hdc.DeleteDC()
        win32gui.ReleaseDC(0, screen_dc)

from __future__ import annotations

import shutil
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ICON_SIZES = (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 256)
CLEAN_PNG_SIZE = 1024


@dataclass(frozen=True)
class ProcessedIcon:
    source_path: Path
    output_path: Path
    icon_group: str
    png_output_path: Path


def discover_pngs(input_dir: Path) -> list[Path]:
    return sorted(path for path in input_dir.rglob("*.png") if path.is_file())


def icon_group_for(input_dir: Path, png_path: Path) -> str:
    relative = png_path.relative_to(input_dir)
    if len(relative.parts) <= 1:
        return "default"
    return str(Path(*relative.parts[:-1]))


def output_path_for(input_dir: Path, output_dir: Path, png_path: Path) -> Path:
    relative = png_path.relative_to(input_dir).with_suffix(".ico")
    return output_dir / "ico" / relative


def png_output_path_for(input_dir: Path, output_dir: Path, png_path: Path) -> Path:
    relative = png_path.relative_to(input_dir)
    return output_dir / "png" / relative


def process_all_icons(
    input_dir: Path,
    output_dir: Path,
    *,
    remove_white_background: bool = True,
    remove_corner_marks: bool = True,
) -> list[ProcessedIcon]:
    processed: list[ProcessedIcon] = []
    for png_path in discover_pngs(input_dir):
        processed.append(
            process_icon(
                input_dir,
                output_dir,
                png_path,
                remove_white_background=remove_white_background,
                remove_corner_marks=remove_corner_marks,
            )
        )
    return processed


def process_icon(
    input_dir: Path,
    output_dir: Path,
    png_path: Path,
    *,
    remove_white_background: bool = True,
    remove_corner_marks: bool = True,
) -> ProcessedIcon:
    ico_path = output_path_for(input_dir, output_dir, png_path)
    png_output_path = png_output_path_for(input_dir, output_dir, png_path)
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    png_output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(png_path).convert("RGBA")
    if remove_white_background:
        image = remove_edge_white_background(image)
    if remove_corner_marks:
        image = soften_corner_marks(image)
    save_clean_png(image, png_output_path)
    save_as_ico(image, ico_path)
    return ProcessedIcon(
        source_path=png_path,
        output_path=ico_path,
        icon_group=icon_group_for(input_dir, png_path),
        png_output_path=png_output_path,
    )


def remove_edge_white_background(image: Image.Image, threshold: int = 245) -> Image.Image:
    rgba = image.convert("RGBA")
    if not _has_near_white_border(rgba, threshold):
        return rgba
    pixels = rgba.load()
    width, height = rgba.size
    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        visited.add((x, y))
        r, g, b, a = pixels[x, y]
        if a == 0 or not _is_near_white(r, g, b, threshold):
            continue

        pixels[x, y] = (r, g, b, 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                queue.append((nx, ny))

    return rgba


def soften_corner_marks(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    box_w = max(8, width // 5)
    box_h = max(8, height // 5)
    corner_boxes = (
        (0, height - box_h, box_w, height),
        (width - box_w, height - box_h, width, height),
    )

    for box in corner_boxes:
        crop = rgba.crop(box)
        if _looks_like_flat_mark(crop):
            _fade_box(rgba, box)

    return rgba


def save_as_ico(image: Image.Image, output_path: Path) -> None:
    square = _prepare_ico_master(_fit_square_canvas(image))
    square.save(output_path, format="ICO", sizes=[(size, size) for size in ICON_SIZES])


def save_clean_png(image: Image.Image, output_path: Path) -> None:
    square = _fit_square_canvas(image)
    if square.size != (CLEAN_PNG_SIZE, CLEAN_PNG_SIZE):
        square = square.resize((CLEAN_PNG_SIZE, CLEAN_PNG_SIZE), Image.Resampling.LANCZOS)
    square.save(output_path, format="PNG", optimize=True)


def migrate_legacy_icons(output_dir: Path) -> None:
    for ico_path in output_dir.rglob("*.ico"):
        if "ico" in ico_path.relative_to(output_dir).parts[:1]:
            continue
        target = output_dir / "ico" / ico_path.relative_to(output_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(ico_path, target)


def _fit_square_canvas(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = max(width, height)
    canvas = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    canvas.alpha_composite(image, ((side - width) // 2, (side - height) // 2))
    return canvas


def _prepare_ico_master(image: Image.Image) -> Image.Image:
    side = image.size[0]
    if side < 256:
        return image.resize((256, 256), Image.Resampling.LANCZOS)
    if side > 1024:
        return image.resize((1024, 1024), Image.Resampling.LANCZOS)
    return image


def _is_near_white(red: int, green: int, blue: int, threshold: int) -> bool:
    return red >= threshold and green >= threshold and blue >= threshold


def _has_near_white_border(image: Image.Image, threshold: int) -> bool:
    width, height = image.size
    sample = []
    pixels = image.load()
    step_x = max(1, width // 48)
    step_y = max(1, height // 48)
    for x in range(0, width, step_x):
        sample.append(pixels[x, 0])
        sample.append(pixels[x, height - 1])
    for y in range(0, height, step_y):
        sample.append(pixels[0, y])
        sample.append(pixels[width - 1, y])
    white = sum(1 for r, g, b, a in sample if a > 0 and _is_near_white(r, g, b, threshold))
    return white / max(1, len(sample)) > 0.35


def _looks_like_flat_mark(image: Image.Image) -> bool:
    pixels = list(image.getdata())
    visible = [(r, g, b) for r, g, b, a in pixels if a > 32]
    if len(visible) < max(4, len(pixels) // 20):
        return False

    avg = tuple(sum(channel) / len(visible) for channel in zip(*visible))
    variance = sum(
        abs(r - avg[0]) + abs(g - avg[1]) + abs(b - avg[2]) for r, g, b in visible
    ) / len(visible)
    return variance < 36


def _fade_box(image: Image.Image, box: tuple[int, int, int, int]) -> None:
    pixels = image.load()
    left, top, right, bottom = box
    for x in range(left, right):
        for y in range(top, bottom):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (r, g, b, int(a * 0.15))

#!/usr/bin/env python3
"""Normalize a generated slide header without another image-generation call."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from check_header_ratio import detect_header_height


DEFAULT_LEFT = (6, 51, 184)
DEFAULT_RIGHT = (12, 164, 235)
FONT_CANDIDATES = (
    Path.home() / "Library/Fonts/NotoSansJP-ExtraBold.ttf",
    Path("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def is_plausible_blue(color: tuple[int, int, int]) -> bool:
    r, g, b = color
    return b >= 100 and b >= r + 20 and max(color) - min(color) >= 30


def sample_header_color(image: Image.Image, x: int, old_header: int) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    y = max(0, min(rgb.height - 1, old_header // 2))
    samples = []
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            sx = max(0, min(rgb.width - 1, x + dx))
            sy = max(0, min(rgb.height - 1, y + dy))
            samples.append(rgb.getpixel((sx, sy)))
    color = tuple(round(sum(pixel[i] for pixel in samples) / len(samples)) for i in range(3))
    return color if is_plausible_blue(color) else (DEFAULT_LEFT if x < rgb.width // 2 else DEFAULT_RIGHT)


def find_font(explicit: Path | None) -> Path:
    candidates = (explicit,) if explicit else FONT_CANDIDATES
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise FileNotFoundError("Japanese bold font not found; pass --font /absolute/path/to/font.ttf")


def fit_font(draw: ImageDraw.ImageDraw, font_path: Path, title: str, max_width: int, max_height: int) -> ImageFont.FreeTypeFont:
    low, high = 20, max(20, int(max_height * 1.4))
    best: ImageFont.FreeTypeFont | None = None
    while low <= high:
        size = (low + high) // 2
        font = ImageFont.truetype(str(font_path), size=size)
        box = draw.textbbox((0, 0), title, font=font)
        width, height = box[2] - box[0], box[3] - box[1]
        if width <= max_width and height <= max_height:
            best = font
            low = size + 1
        else:
            high = size - 1
    if best is None:
        raise ValueError("Title cannot fit on one line at a readable size; shorten it upstream")
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--target-ratio", type=float, default=0.15)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--row-threshold", type=float, default=0.50)
    args = parser.parse_args()

    if not args.image.is_file():
        print(f"ERROR image not found: {args.image}", file=sys.stderr)
        return 2
    if "\n" in args.title or "\r" in args.title:
        print("ERROR title must be one line", file=sys.stderr)
        return 2
    if not 0.14 <= args.target_ratio <= 0.16:
        print("ERROR target ratio must remain inside 14–16%", file=sys.stderr)
        return 2

    font_path = find_font(args.font)
    with Image.open(args.image) as source:
        source = source.convert("RGB")
        width, height = source.size
        old_header = detect_header_height(source, args.row_threshold)
        if old_header <= 0 or old_header >= height:
            print(f"ERROR could not detect existing header in {args.image}", file=sys.stderr)
            return 2

        new_header = round(height * args.target_ratio)
        body = source.crop((0, old_header, width, height)).resize(
            (width, height - new_header), Image.Resampling.LANCZOS
        )
        result = Image.new("RGB", (width, height), "white")
        result.paste(body, (0, new_header))

        left = sample_header_color(source, 2, old_header)
        right = sample_header_color(source, width - 3, old_header)
        pixels = result.load()
        for x in range(width):
            color = mix(left, right, x / max(1, width - 1))
            for y in range(new_header):
                pixels[x, y] = color

        draw = ImageDraw.Draw(result)
        font = fit_font(
            draw,
            font_path,
            args.title,
            max_width=round(width * 0.92),
            max_height=round(new_header * 0.62),
        )
        draw.text(
            (width / 2, new_header / 2),
            args.title,
            font=font,
            fill=(255, 255, 255),
            anchor="mm",
        )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        result.save(args.output, format="PNG")

    with Image.open(args.output) as checked:
        detected = detect_header_height(checked, args.row_threshold)
        ratio = detected / checked.height
    if not 0.14 <= ratio <= 0.16:
        print(f"ERROR normalized header ratio is {ratio:.2%}", file=sys.stderr)
        return 1
    print(
        f"PASS old_header={old_header}px new_header={detected}px ratio={ratio:.2%} "
        f"font={font_path} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

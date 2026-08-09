#!/usr/bin/env python3
"""Measure blue-gradient header bands and enforce the 14–16% rule."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image


def is_blue_header_pixel(r: int, g: int, b: int) -> bool:
    """Match cobalt-to-cyan pixels while excluding white title/background pixels."""
    return b >= 105 and b >= r + 20 and (b >= g - 8) and (max(r, g, b) - min(r, g, b) >= 35)


def detect_header_height(image: Image.Image, row_threshold: float) -> int:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    header_rows = 0

    # Measure only the outer edges. Centered white title glyphs can cover most of
    # a row and must never be mistaken for the end of the gradient band.
    edge_width = max(1, int(width * 0.12))
    sample_x = list(range(edge_width)) + list(range(width - edge_width, width))

    # The header begins at y=0 and is the first contiguous block dominated by blue.
    for y in range(min(height, int(height * 0.30))):
        blue_count = sum(is_blue_header_pixel(*pixels[x, y]) for x in sample_x)
        if blue_count / len(sample_x) >= row_threshold:
            header_rows = y + 1
        elif y >= 3:
            break

    return header_rows


def check_image(image_path: Path, min_ratio: float, max_ratio: float, row_threshold: float) -> int:
    if not image_path.is_file():
        print(f"ERROR image not found: {image_path}", file=sys.stderr)
        return 2

    with Image.open(image_path) as image:
        width, height = image.size
        header_height = detect_header_height(image, row_threshold)

    ratio = header_height / height if height else 0.0
    status = "PASS" if min_ratio <= ratio <= max_ratio else "FAIL"
    print(
        f"{status} header={header_height}px canvas={width}x{height} "
        f"ratio={ratio:.2%} allowed={min_ratio:.0%}-{max_ratio:.0%} target=15% "
        f"image={image_path}"
    )
    return 0 if status == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("images", type=Path, nargs="+")
    parser.add_argument("--min-ratio", type=float, default=0.14)
    parser.add_argument("--max-ratio", type=float, default=0.16)
    parser.add_argument("--row-threshold", type=float, default=0.50)
    args = parser.parse_args()

    results = [
        check_image(image, args.min_ratio, args.max_ratio, args.row_threshold)
        for image in args.images
    ]
    return max(results, default=0)


if __name__ == "__main__":
    raise SystemExit(main())

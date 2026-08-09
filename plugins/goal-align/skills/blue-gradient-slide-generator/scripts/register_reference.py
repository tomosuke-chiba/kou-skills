#!/usr/bin/env python3
"""Register an explicitly approved slide and rebuild the style reference board."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps


SKILL_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = SKILL_ROOT / "assets" / "reference-images"
INDEX_PATH = SKILL_ROOT / "references" / "reference-index.json"
BOARD_PATH = SKILL_ROOT / "assets" / "reference-board.png"
SEMANTIC_BOARD_PATH = SKILL_ROOT / "assets" / "semantic-reference-board.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path)
    parser.add_argument("--source", default="user-approved-output")
    parser.add_argument("--rating", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--feedback", default="Explicitly approved visual reference")
    parser.add_argument("--tags", default="")
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--rebuild-only", action="store_true")
    return parser.parse_args()


def load_index() -> dict:
    if not INDEX_PATH.exists():
        return {"version": 1, "references": []}
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def save_index(index: dict) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:40] or "reference"


def register(args: argparse.Namespace, index: dict) -> None:
    if not args.approved:
        raise SystemExit("Refusing to persist a reference without --approved")
    if not args.image or not args.image.is_file():
        raise SystemExit("--image must point to an existing image")

    with Image.open(args.image) as image:
        image.verify()

    digest = file_digest(args.image)
    if any(item.get("sha256") == digest for item in index["references"]):
        print(f"Already registered: {args.image}")
        return

    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = args.image.suffix.lower() if args.image.suffix else ".png"
    filename = f"{timestamp}-{safe_slug(args.source)}-{digest[:8]}{suffix}"
    destination = REFERENCE_DIR / filename
    shutil.copy2(args.image, destination)

    width, height = Image.open(destination).size
    index["references"].append(
        {
            "file": f"assets/reference-images/{filename}",
            "sha256": digest,
            "source": args.source,
            "rating": args.rating,
            "feedback": args.feedback,
            "tags": [tag.strip() for tag in args.tags.split(",") if tag.strip()],
            "width": width,
            "height": height,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    save_index(index)
    print(f"Registered: {destination}")


def render_board(candidates: list[dict], path: Path, columns: int, rows: int) -> None:
    if not candidates:
        print(f"No references registered; board not created: {path}")
        return

    tile_w, tile_h = 410, 231
    board = Image.new("RGB", (tile_w * columns, tile_h * rows), "white")
    for position, item in enumerate(candidates[: columns * rows]):
        image_path = SKILL_ROOT / item["file"]
        if not image_path.exists():
            continue
        with Image.open(image_path) as image:
            tile = ImageOps.contain(image.convert("RGB"), (tile_w - 8, tile_h - 8))
        x = (position % columns) * tile_w + (tile_w - tile.width) // 2
        y = (position // columns) * tile_h + (tile_h - tile.height) // 2
        board.paste(tile, (x, y))
    path.parent.mkdir(parents=True, exist_ok=True)
    board.save(path, optimize=True)
    print(f"Rebuilt: {path}")


def rebuild_board(index: dict) -> None:
    style_candidates = sorted(
        [item for item in index["references"] if "semantic-only" not in item.get("tags", [])],
        key=lambda item: (item.get("rating", 0), item.get("added_at", "")),
        reverse=True,
    )[:16]
    semantic_candidates = sorted(
        [item for item in index["references"] if "semantic-only" in item.get("tags", [])],
        key=lambda item: (item.get("rating", 0), item.get("added_at", "")),
        reverse=True,
    )
    render_board(style_candidates, BOARD_PATH, columns=4, rows=4)
    render_board(semantic_candidates, SEMANTIC_BOARD_PATH, columns=3, rows=max(1, (len(semantic_candidates) + 2) // 3))


def main() -> None:
    args = parse_args()
    index = load_index()
    if not args.rebuild_only:
        register(args, index)
        index = load_index()
    rebuild_board(index)


if __name__ == "__main__":
    main()

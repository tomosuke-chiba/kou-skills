#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""to_cover.py — 動画の冒頭フレームを使ってインスタ用カバー画像を作る（1080×1920・白文字＋ドロップシャドウ）"""
import argparse, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FFMPEG = "ffmpeg"
W, H = 1080, 1920


def find_font():
    candidates = [
        str(Path(__file__).resolve().parent.parent.parent.parent / "assets/fonts/NotoSansJP-ExtraBold.ttf"),
        str(Path.home() / "Library/Fonts/NotoSansJP-ExtraBold.ttf"),
        "/Library/Fonts/NotoSansJP-ExtraBold.ttf",
        "C:/Windows/Fonts/NotoSansJP-ExtraBold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    sys.stderr.write("ERROR: NotoSansJP-ExtraBold.ttf not found\n")
    sys.exit(2)


def fit_font(font_path, s, max_width):
    sz = 160
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    while sz > 40:
        f = ImageFont.truetype(font_path, sz)
        if d.textlength(s, font=f) <= max_width:
            return f
        sz -= 2
    return ImageFont.truetype(font_path, 40)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--frame", type=float, default=2.0, help="抜き出す秒数")
    ap.add_argument("--text", required=True, help="カバーのメインコピー（1行）")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    font_path = find_font()
    # フレーム抽出
    tmp_frame = Path(args.out).with_suffix(".tmp_frame.png")
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", str(args.frame), "-i", args.video, "-frames:v", "1",
                    "-vf", f"scale={W}:{H}", str(tmp_frame)], check=True)
    im = Image.open(str(tmp_frame)).convert("RGBA")

    # 薄ブルーティント（瀬戸内の空気感）
    tint = Image.new("RGBA", (W, H), (180, 210, 225, int(255 * 0.10)))
    im = Image.alpha_composite(im, tint)

    # 中央にコピー（白文字＋黒ドロップシャドウ）
    font = fit_font(font_path, args.text, W * 0.88)
    d0 = ImageDraw.Draw(im)
    x = (W - d0.textlength(args.text, font=font)) / 2
    asc, desc = font.getmetrics()
    yc = int(H * 0.455)
    y = yc - (asc + desc) / 2

    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x + 5, y + 6), args.text, font=font, fill=(0, 0, 0, 235))
    sh = sh.filter(ImageFilter.GaussianBlur(7))
    im = Image.alpha_composite(im, sh)
    ImageDraw.Draw(im).text((x, y), args.text, font=font, fill=(255, 255, 255, 255))

    im.convert("RGB").save(args.out, quality=92)
    tmp_frame.unlink(missing_ok=True)
    print(f"cover written: {args.out}")


if __name__ == "__main__":
    main()

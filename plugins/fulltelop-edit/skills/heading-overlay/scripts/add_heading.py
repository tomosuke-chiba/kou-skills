#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""左上見出し（KOU標準・紺グラデ帯デザイン）を動画に焼き込む。

2026-08 沖縄研修 IMG_4786 rev3 でユーザー確定したデザイン（3案から案2を選定）:
  - 紺グラデーション帯（左 RGB(22,32,92) → 右 RGB(56,80,168)）
  - 帯は画面左端からブリード、右端は斜めカット（下辺が+28px右へ張り出す）
  - 下辺にライトブルー RGB(130,160,230) の差し色スリバー（高さ7px）
  - 白文字 NotoSansJP-ExtraBold 62px＋紺の薄影、帯の下に落ち影
  - 位置: y=38px・帯高112px・左パディング72px（変更しない。同じ位置に出すのが仕様）

使い方:
  焼き込み:  python3 add_heading.py --src <動画> --text "見出し" --out <出力mp4>
  PNGのみ:   python3 add_heading.py --png-only --text "見出し" --png <出力png>

焼き込みは映像のみ再エンコード（videotoolbox 10M→libx264 CRF18 フォールバック）、
音声は -c:a copy で無劣化。overlay=shortest=1 でループPNG起因の尺伸びを防ぐ
（-shortest だけだと映像が10フレーム程度余分に出る実測あり）。
"""
import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
FONT_PATH = PLUGIN_ROOT / "assets/fonts/NotoSansJP-ExtraBold.ttf"

# ---- デザイン定数（ユーザー確定・変更しない） ----
CANVAS = (1920, 1080)
Y0, BAND_H = 38, 112
PAD_L, PAD_R = 72, 64
SKEW = 28
FONT_SIZE = 62
GRAD_L, GRAD_R = (22, 32, 92), (56, 80, 168)
SLIVER = (130, 160, 230, 235)
SHADOW = (10, 15, 40, 110)
TEXT_SHADOW = (10, 15, 50, 120)


def make_heading_png(text: str, out_path: Path):
    font = ImageFont.truetype(str(FONT_PATH), FONT_SIZE)
    img = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    bw = PAD_L + tw + PAD_R

    sh = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon(
        [(0, Y0 + 5), (bw + 4, Y0 + 5), (bw + SKEW + 4, Y0 + BAND_H + 5), (0, Y0 + BAND_H + 5)],
        fill=SHADOW)
    img = Image.alpha_composite(img, sh)

    grad = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    gp = grad.load()
    for x in range(0, bw + SKEW + 1):
        t = x / (bw + SKEW)
        col = tuple(int(a + (b - a) * t) for a, b in zip(GRAD_L, GRAD_R)) + (255,)
        for y in range(Y0, Y0 + BAND_H + 1):
            gp[x, y] = col
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).polygon(
        [(0, Y0), (bw, Y0), (bw + SKEW, Y0 + BAND_H), (0, Y0 + BAND_H)], fill=255)
    img.paste(grad, (0, 0), mask)

    sl = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    ImageDraw.Draw(sl).polygon(
        [(0, Y0 + BAND_H - 7), (bw + int(SKEW * (BAND_H - 7) / BAND_H), Y0 + BAND_H - 7),
         (bw + SKEW, Y0 + BAND_H), (0, Y0 + BAND_H)],
        fill=SLIVER)
    img = Image.alpha_composite(img, sl)

    d = ImageDraw.Draw(img)
    ty = Y0 + (BAND_H - (bb[3] - bb[1])) // 2 - bb[1] - 3
    d.text((PAD_L + 2, ty + 3), text, font=font, fill=TEXT_SHADOW)
    d.text((PAD_L, ty), text, font=font, fill=(255, 255, 255, 255))
    img.save(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--src", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--png", type=Path, help="見出しPNGの出力先（省略時は out と同じ場所）")
    ap.add_argument("--png-only", action="store_true")
    args = ap.parse_args()

    if args.png_only:
        if not args.png:
            sys.exit("--png-only には --png が必要")
        make_heading_png(args.text, args.png)
        print(f"png: {args.png}")
        return

    if not (args.src and args.out):
        sys.exit("焼き込みには --src と --out が必要")
    png = args.png or args.out.with_suffix(".heading.png")
    make_heading_png(args.text, png)

    def encode(vcodec):
        return subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-nostats",
             "-i", str(args.src), "-loop", "1", "-framerate", "30", "-i", str(png),
             "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p[vout]",
             "-map", "[vout]", "-map", "0:a", "-c:a", "copy"] + vcodec +
            ["-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart",
             str(args.out)]).returncode

    if encode(["-c:v", "h264_videotoolbox", "-b:v", "10M", "-profile:v", "high"]) != 0:
        print("videotoolbox 失敗 → libx264 にフォールバック")
        if encode(["-c:v", "libx264", "-crf", "18", "-preset", "medium"]) != 0:
            sys.exit("render failed")

    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(args.out)],
                       capture_output=True, text=True)
    print(f"done: {args.out}  duration={r.stdout.strip()}s")


if __name__ == "__main__":
    main()

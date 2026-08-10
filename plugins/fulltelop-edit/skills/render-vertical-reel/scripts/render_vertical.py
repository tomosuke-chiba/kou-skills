#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_vertical.py — 縦リール完結型 4K 焼き込み

入力:
  --spec spec.json
  --koetsu koetsu.json          # テロップ items[].start/.end/.text
  --keep keep_segments.json     # [[src_in, src_out], ...]
  --out  output.mp4 (省略時は {spec.work_dir}/{stem}_short_4k.mp4 に自動)

仕様: 白テロップ + 黒ドロップシャドウ・y=0.50・末尾フリーズで末尾カードテロップ（任意）
      入力素材を必ず 2160x3840 にスケール+パッド（縦9:16保証）
      ファイル名は既定で ASCII（--japanese-filename で stem 使用）
"""
import argparse, json, os, shutil, subprocess, sys, platform
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def find_ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    for c in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if Path(c).exists():
            return c
    sys.stderr.write("ERROR: ffmpeg not found. Install with `brew install ffmpeg`\n")
    sys.exit(2)


FFMPEG = find_ffmpeg()
W, H, FPS = 2160, 3840, 30
TELOP_Y = 0.50
SH_OFF = (6, 16)
SH_BLUR = 10
SH_ALPHA = 235
SIZE = 120


def find_font():
    candidates = [
        str(Path.home() / "Library/Fonts/NotoSansJP-ExtraBold.ttf"),
        "/Library/Fonts/NotoSansJP-ExtraBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "C:/Windows/Fonts/NotoSansJP-ExtraBold.ttf",
    ]
    # プラグイン同梱フォント
    script_dir = Path(__file__).resolve().parent
    candidates.insert(0, str(script_dir.parent.parent.parent / "assets/fonts/NotoSansJP-ExtraBold.ttf"))
    for c in candidates:
        if Path(c).exists():
            return c
    sys.stderr.write("ERROR: NotoSansJP-ExtraBold.ttf not found. "
                     "Install it or place in assets/fonts/\n")
    sys.exit(2)


def render_telop_png(text, path, color=(255, 255, 255, 255), font_path=None):
    font = ImageFont.truetype(font_path, SIZE)
    asc, desc = font.getmetrics()
    lh = asc + desc + 16
    lines = text.split("\n")
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    d0 = ImageDraw.Draw(img)
    y0 = int(H * TELOP_Y) - (len(lines) - 1) * lh // 2
    for i, ln in enumerate(lines):
        x = (W - d0.textlength(ln, font=font)) / 2
        sd.text((x + SH_OFF[0], y0 + i * lh + SH_OFF[1]), ln, font=font, fill=(0, 0, 0, SH_ALPHA))
    sh = sh.filter(ImageFilter.GaussianBlur(SH_BLUR))
    img = Image.alpha_composite(sh, img)
    dd = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        x = (W - dd.textlength(ln, font=font)) / 2
        dd.text((x, y0 + i * lh), ln, font=font, fill=color)
    img.save(path)


def map_out_factory(keep):
    def m(t):
        o = 0.0
        for si, so in keep:
            if t < si - 1e-6:
                return None
            if t <= so + 1e-6:
                return o + (t - si)
            o += so - si
        return None
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--koetsu", required=True)
    ap.add_argument("--keep", required=True)
    ap.add_argument("--out", default=None,
                    help="出力 mp4 パス（省略時は spec.work_dir/{stem}_short_4k.mp4）")
    ap.add_argument("--ascii-stem", action="store_true", default=True,
                    help="ファイル名を ASCII にする（既定）。Win 文字化け対策")
    ap.add_argument("--japanese-filename", action="store_true",
                    help="--ascii-stem を解除して spec.stem を使う")
    ap.add_argument("--bitrate", default="50M")
    ap.add_argument("--freeze-tail", type=float, default=0.0,
                    help="末尾フリーズ秒数（末尾カードテロップに使う・既定0）")
    ap.add_argument("--telop-color", default="white",
                    choices=["white", "yellow"])
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    koetsu = json.loads(Path(args.koetsu).read_text(encoding="utf-8"))
    keep_data = json.loads(Path(args.keep).read_text(encoding="utf-8"))
    keep = [(float(a), float(b)) for a, b in keep_data["keep_segments"]]

    # 出力パス自動推論
    if args.out is None:
        stem = spec.get("stem", "output")
        if args.ascii_stem and not args.japanese_filename:
            # ASCII化（既定）
            import re
            stem = re.sub(r"[^A-Za-z0-9_\-]", "_", stem) or "output"
        work_dir = Path(spec.get("work_dir", "."))
        args.out = str(work_dir / f"{stem}_short_4k.mp4")
    out_dir = Path(args.out).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    work = Path(spec["work_dir"])
    PNG = work / "telop_png"
    if PNG.exists():
        shutil.rmtree(PNG)
    PNG.mkdir(parents=True, exist_ok=True)
    font_path = find_font()
    out_dur = sum(b - a for a, b in keep)

    # テロップ → 出力時刻に変換
    map_out = map_out_factory(keep)
    segs = []
    for it in koetsu["items"]:
        oa = map_out(float(it["start"]))
        ob = map_out(float(it["end"]))
        if oa is None or ob is None:
            print(f"  warn: out of range telop: {it['text'][:20]}", file=sys.stderr)
            continue
        segs.append((oa, ob, it["text"]))

    # 末尾フリーズに末尾カードテロップ（任意・spec.countdown で指定）
    countdown = spec.get("countdown") or {}
    freeze = args.freeze_tail
    if countdown.get("enabled") and countdown.get("amount") is not None:
        freeze = max(freeze, 1.5)
        label = countdown.get("label", "")
        amount = countdown["amount"]
        cd_text = f"{label}{amount}" if not label else f"{label}{amount}"
        segs.append((out_dur + 0.10, out_dur + freeze - 0.10, cd_text))

    # PNG 生成
    color = (255, 255, 255, 255) if args.telop_color == "white" else (251, 227, 95, 255)
    for ti, (_, _, t) in enumerate(segs):
        render_telop_png(t, str(PNG / f"t_{ti:03d}.png"), color, font_path)

    # ffmpeg コマンド組み立て
    SRC = spec["src"]
    N = len(keep)
    inputs = ["-i", SRC]
    idx = 1
    parts = []
    # 映像 trim+concat + 2160x3840 への scale/pad（縦9:16保証・素材サイズ問わず）
    # scale で長辺を縮めて、不足分を黒帯で pad（同梱フォントとレイアウトが破綻しない）
    vfit = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    for i, (si, so) in enumerate(keep):
        parts.append(f"[0:v]trim={si:.6f}:{so:.6f},setpts=PTS-STARTPTS,{vfit},fps={FPS}[v{i}]")
    vbase = f"concat=n={N}:v=1:a=0"
    if freeze > 0:
        vbase += f",tpad=stop_mode=clone:stop_duration={freeze}"
    parts.append("".join(f"[v{i}]" for i in range(N)) + f"{vbase}[vbase]")
    # 音声 trim+concat + 境界12msフェード
    for i, (si, so) in enumerate(keep):
        D = so - si
        parts.append(
            f"[0:a]atrim={si:.6f}:{so:.6f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.012,afade=t=out:st={max(0,D-0.012):.6f}:d=0.012[a{i}]"
        )
    aout = f"concat=n={N}:v=0:a=1"
    if freeze > 0:
        aout = f"concat=n={N}:v=0:a=1,apad=pad_dur={freeze}"
    parts.append("".join(f"[a{i}]" for i in range(N)) + f"{aout}[aout]")
    # テロップ overlay 連鎖
    prev = "vbase"
    for ti, (oa, ob, _) in enumerate(segs):
        inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{ob-oa:.6f}",
                   "-i", str(PNG / f"t_{ti:03d}.png")]
        parts.append(f"[{idx}:v]setpts=PTS-STARTPTS+{oa:.6f}/TB,fps={FPS}[tl{ti}]")
        parts.append(f"[{prev}][tl{ti}]overlay=0:0:enable='between(t,{oa:.6f},{ob:.6f})'[vx{ti}]")
        prev = f"vx{ti}"
        idx += 1
    parts.append(f"[{prev}]format=yuv420p[vout]")
    fc = ";\n".join(parts)
    (work / "filter_render.txt").write_text(fc, encoding="utf-8")

    # エンコーダ
    vcodec = "h264_videotoolbox" if platform.system() == "Darwin" else "libx264"
    extra_v = []
    if vcodec == "libx264":
        extra_v = ["-preset", "fast", "-crf", "18"]

    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *inputs,
           "-filter_complex_script", str(work / "filter_render.txt"),
           "-map", "[vout]", "-map", "[aout]",
           "-t", f"{out_dur + freeze:.3f}",
           "-c:v", vcodec, "-b:v", args.bitrate,
           "-maxrate", "60M", "-bufsize", "100M",
           "-profile:v", "high", "-pix_fmt", "yuv420p",
           *extra_v,
           "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
           "-movflags", "+faststart", args.out]

    print(f"keep={N} 出力{out_dur:.1f}s +フリーズ{freeze}s テロップ{len(segs)}件")
    print(f"vcodec={vcodec} bitrate={args.bitrate}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:] + "\n")
        sys.exit(3)
    print(f"OK -> {args.out}")


if __name__ == "__main__":
    main()

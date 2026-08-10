#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""横インタビュー（話者色分けフルテロップ）焼き込みレンダラ。

2026-07 DH木村さんインタビュー制作で確立したパイプラインの汎用化:

  1. cutplan の drop_ranges で物理カット（映像 trim+concat / 音声 12ms 境界フェード）
  2. koetsu.json（src 時刻・speaker 付き）をカット後タイムラインへ写像
  3. loudnorm 2パス（測定→測定値埋め込み）で -14 LUFS / TP -1.5 のマスター音声を作成
  4. onset_snap.py でテロップ開始を実発話の立ち上がりへ前方スナップ（＋SRT出力）
  5. 話者別スタイルのフル画面テロップPNGを生成し、ffconcat 1トラック＋overlay 1段で焼き込み
     （subtitles/drawtext フィルタ無しの ffmpeg でも動く・49枚で約1分）

テロップ同期の設計:
  - koetsu の start は「発話開始そのもの」（word アンカー→オンセットスナップ済み）
  - 焼き込み表示は start より LEAD (0.05s) 先行 = 発話に絶対遅れない
  - end は「最終語の終わり +0.15〜0.25s」を次テロップ開始でクランプ（上流で設定）

使い方:
  python3 render_interview.py \
    --src <元動画> --work <work_dir> --koetsu <koetsu.json> --cutplan <cutplan.json> \
    --out <出力mp4> [--lead 0.05] [--no-onset-snap] [--styles styles.json]

  cutplan.json: {"drop_ranges": [[s,e],...], "end_time": 194.05}
  koetsu.json:  {"items":[{"start":s,"end":e,"speaker":"interviewer|respondent","text":"..."}]}
                start/end は src タイムライン
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
FONT_PATH = PLUGIN_ROOT / "assets/fonts/NotoSansJP-ExtraBold.ttf"
ONSET_SNAP = PLUGIN_ROOT / "skills/smart-caption/scripts/onset_snap.py"

FADE = 0.012
BOTTOM_MARGIN = 56
CANVAS = (1920, 1080)

# クリニック系インタビューの既定スタイル（spec で上書き可）
# サイズはユーザー確定値 72/74px（2026-07 「もう少し大きく」の要望で 64/66 から変更）
DEFAULT_STYLES = {
    "interviewer": {  # 白文字＋黒フチ＋黒影
        "size": 72, "fill": [255, 255, 255, 255], "stroke": 6,
        "stroke_fill": [32, 32, 32, 255], "shadow": [0, 0, 0, 140], "shadow_off": [3, 4],
    },
    "respondent": {   # #FF3399＋白フチ＋薄い暖色影
        "size": 74, "fill": [255, 51, 153, 255], "stroke": 6,
        "stroke_fill": [255, 255, 255, 255], "shadow": [70, 60, 90, 120], "shadow_off": [3, 4],
    },
}


def run(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        sys.exit(f"command failed: {' '.join(map(str, cmd[:6]))} ...")
    return r


def keep_segments(drops, end_time):
    segs, cursor = [], 0.0
    for s, e in drops:
        if cursor < s:
            segs.append((cursor, s))
        cursor = e
    if cursor < end_time:
        segs.append((cursor, end_time))
    return segs


def make_mapper(drops):
    def map_time(t):
        removed = 0.0
        for s, e in drops:
            if t >= e:
                removed += e - s
            elif t > s:
                removed += t - s
        return max(0.0, t - removed)
    return map_time


def _dilate(mask, r):
    """文字マスクを半径 r で膨張（円周サンプリングの和集合）。
    PIL の stroke_width 描画は半濁点や「置」の罒など小さな空隙を潰す
    （ストローカーの自己交差・2026-08 実測）ため、フチはこの方式で作る。"""
    import math
    from PIL import ImageChops
    out = mask.copy()
    offs = set()
    for rad, n in [(r, 32), (int(r * 0.8), 20), (int(r * 0.55), 14), (int(r * 0.3), 8)]:
        if rad <= 0:
            continue
        for i in range(n):
            a = 2 * math.pi * i / n
            offs.add((round(rad * math.cos(a)), round(rad * math.sin(a))))
    for dx, dy in offs:
        out = ImageChops.lighter(out, ImageChops.offset(mask, dx, dy))
    return out


def render_png(text, style, path):
    S = 2  # スーパーサンプリング倍率（エッジ平滑化）
    font = ImageFont.truetype(str(FONT_PATH), style["size"] * S)
    lines = text.split("\n")
    stroke = style["stroke"] * S
    gap = 14 * S
    W, H = CANVAS[0] * S, CANVAS[1] * S

    mask = Image.new("L", (W, H), 0)
    fill_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mask)
    fdraw = ImageDraw.Draw(fill_img)
    boxes = [mdraw.textbbox((0, 0), ln, font=font, stroke_width=stroke) for ln in lines]
    widths = [b[2] - b[0] for b in boxes]
    heights = [b[3] - b[1] for b in boxes]
    y = H - BOTTOM_MARGIN * S - (sum(heights) + gap * (len(lines) - 1))
    for ln, bx, h, w in zip(lines, boxes, heights, widths):
        x = (W - w) // 2 - bx[0]
        yy = y - bx[1]
        mdraw.text((x, yy), ln, font=font, fill=255)
        fdraw.text((x, yy), ln, font=font, fill=tuple(style["fill"]))
        y += h + gap

    big = _dilate(mask, stroke)
    sx, sy = style["shadow_off"]
    sh_r, sh_g, sh_b, sh_a = style["shadow"]
    st_r, st_g, st_b, st_a = style["stroke_fill"]

    shadow = Image.new("RGBA", (W, H), (sh_r, sh_g, sh_b, 0))
    from PIL import ImageChops
    shadow.putalpha(ImageChops.offset(big, sx * S, sy * S).point(lambda v: v * sh_a // 255))
    outline = Image.new("RGBA", (W, H), (st_r, st_g, st_b, 0))
    outline.putalpha(big.point(lambda v: v * st_a // 255))

    img = Image.alpha_composite(Image.alpha_composite(shadow, outline), fill_img)
    img = img.resize(CANVAS, Image.LANCZOS)
    img.save(path)


def esc_concat(p: Path) -> str:
    return str(p.resolve()).replace("'", "'\\''")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--koetsu", required=True, type=Path)
    ap.add_argument("--cutplan", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--lead", type=float, default=0.05)
    ap.add_argument("--no-onset-snap", action="store_true")
    ap.add_argument("--styles", type=Path, help="スタイル上書き JSON")
    ap.add_argument("--heading", help="左上見出しテキスト（heading-overlay スキルの固定デザインで全編表示）")
    args = ap.parse_args()

    work = args.work
    work.mkdir(parents=True, exist_ok=True)
    styles = dict(DEFAULT_STYLES)
    if args.styles:
        styles.update(json.loads(args.styles.read_text(encoding="utf-8")))

    cutplan = json.loads(args.cutplan.read_text(encoding="utf-8"))
    drops = [tuple(d) for d in cutplan.get("drop_ranges", [])]
    end_time = cutplan["end_time"]
    segs = keep_segments(drops, end_time)
    map_time = make_mapper(drops)
    out_dur = sum(e - s for s, e in segs)
    print(f"keep segments: {len(segs)}  out_duration: {out_dur:.2f}s")

    # --- koetsu をカット後タイムラインへ写像 ---
    src_items = json.loads(args.koetsu.read_text(encoding="utf-8"))["items"]
    items = []
    for it in src_items:
        s, e = map_time(it["start"]), map_time(it["end"])
        if e - s < 0.2:
            sys.exit(f"caption too short after mapping: {it['text']!r} ({s:.2f}-{e:.2f}) "
                     "— DROP と重なっていないか確認")
        items.append({"start": round(s, 3), "end": round(e, 3),
                      "speaker": it.get("speaker", "respondent"), "text": it["text"]})
    for a, b in zip(items, items[1:]):
        if a["end"] > b["start"] + 1e-6:
            sys.exit(f"caption overlap: {a['text']!r} / {b['text']!r}")
    koetsu_out = work / "koetsu_out.json"
    koetsu_out.write_text(json.dumps({"version": 1, "items": items},
                                     ensure_ascii=False, indent=2), encoding="utf-8")

    # --- 音声: カット＋境界フェード → loudnorm 2パス → マスターwav ---
    a_lines, a_labels = [], []
    for i, (s, e) in enumerate(segs):
        dur = e - s
        a_lines.append(
            f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={FADE},afade=t=out:st={max(0.0, dur - FADE):.3f}:d={FADE}[a{i}];")
        a_labels.append(f"[a{i}]")
    acat = "".join(a_lines) + f"{''.join(a_labels)}concat=n={len(segs)}:v=0:a=1[acat];"

    measure = acat + "[acat]loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[aout]"
    (work / "filter_measure.txt").write_text(measure)
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(args.src),
         "-filter_complex_script", str(work / "filter_measure.txt"),
         "-map", "[aout]", "-f", "null", "-"],
        capture_output=True, text=True)
    m = re.search(r"\{[^}]*\}", r.stderr, re.S)
    if not m:
        sys.exit("loudnorm 測定に失敗")
    meas = json.loads(m.group(0))
    print(f"measured: I={meas['input_i']} TP={meas['input_tp']}")
    ln2 = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={meas['input_i']}"
           f":measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}"
           f":measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}")
    master = acat + f"[acat]{ln2},aresample=48000[aout]"
    (work / "filter_master.txt").write_text(master)
    master_wav = work / "master.wav"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(args.src),
         "-filter_complex_script", str(work / "filter_master.txt"),
         "-map", "[aout]", "-c:a", "pcm_s16le", str(master_wav)])

    # --- オンセットスナップ（前方のみ）＋ SRT ---
    srt_path = work / f"{args.out.stem}.srt"
    if args.no_onset_snap:
        pass
    else:
        run([sys.executable, str(ONSET_SNAP), "--koetsu", str(koetsu_out),
             "--media", str(master_wav), "--srt", str(srt_path)])
        items = json.loads(koetsu_out.read_text(encoding="utf-8"))["items"]

    # --- テロップトラック（フル画面PNG＋ffconcat・ミリ秒整数で累積誤差ゼロ） ---
    asset = work / "telop_png"
    asset.mkdir(exist_ok=True)
    heading_img = None
    if args.heading:
        heading_png = work / "heading.png"
        run([sys.executable,
             str(PLUGIN_ROOT / "skills/heading-overlay/scripts/add_heading.py"),
             "--png-only", "--text", args.heading, "--png", str(heading_png)])
        heading_img = Image.open(heading_png).convert("RGBA")
    blank = asset / "blank.png"
    base = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    if heading_img:
        base = Image.alpha_composite(base, heading_img)
    base.save(blank)
    disp = [[max(0, int(round((it["start"] - args.lead) * 1000))),
             int(round(it["end"] * 1000)), it["speaker"], it["text"]] for it in items]
    for i in range(len(disp) - 1):
        if disp[i][1] > disp[i + 1][0]:
            disp[i][1] = disp[i + 1][0]
    lines = ["ffconcat version 1.0"]
    cursor = 0
    for i, (s, e, spk, text) in enumerate(disp, 1):
        p = asset / f"t{i:03d}.png"
        render_png(text, styles.get(spk, styles["interviewer"]), p)
        if heading_img:
            merged = Image.alpha_composite(
                Image.alpha_composite(Image.new("RGBA", CANVAS, (0, 0, 0, 0)), heading_img),
                Image.open(p).convert("RGBA"))
            merged.save(p)
        if s > cursor:
            lines += [f"file '{esc_concat(blank)}'", f"duration {(s - cursor) / 1000:.3f}"]
        lines += [f"file '{esc_concat(p)}'", f"duration {(e - s) / 1000:.3f}"]
        cursor = e
    total_ms = int(round(out_dur * 1000))
    if total_ms > cursor:
        lines += [f"file '{esc_concat(blank)}'", f"duration {(total_ms - cursor) / 1000:.3f}"]
    lines.append(f"file '{esc_concat(blank)}'")
    (work / "telop_concat.txt").write_text("\n".join(lines) + "\n")

    # --- 最終レンダリング ---
    v_lines, v_labels = [], []
    for i, (s, e) in enumerate(segs):
        v_lines.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}];")
        v_labels.append(f"[v{i}]")
    vf = ("".join(v_lines)
          + f"{''.join(v_labels)}concat=n={len(segs)}:v=1:a=0[vcat];"
          + "[vcat][1:v]overlay=0:0[ovl];[ovl]format=yuv420p[vout]")
    (work / "filter_video.txt").write_text(vf)

    def encode(vcodec):
        return subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-nostats",
             "-i", str(args.src), "-f", "concat", "-safe", "0", "-i", str(work / "telop_concat.txt"),
             "-i", str(master_wav),
             "-filter_complex_script", str(work / "filter_video.txt"),
             "-map", "[vout]", "-map", "2:a"] + vcodec +
            ["-pix_fmt", "yuv420p", "-r", "30",
             "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(args.out)]).returncode

    if encode(["-c:v", "h264_videotoolbox", "-b:v", "10M", "-profile:v", "high"]) != 0:
        print("videotoolbox 失敗 → libx264 にフォールバック")
        if encode(["-c:v", "libx264", "-crf", "18", "-preset", "medium"]) != 0:
            sys.exit("render failed")

    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(args.out)],
                       capture_output=True, text=True)
    print(f"done: {args.out}  duration={r.stdout.strip()}s  captions={len(items)}")
    print(f"srt : {srt_path if srt_path.exists() else '(未出力)'}")


if __name__ == "__main__":
    main()

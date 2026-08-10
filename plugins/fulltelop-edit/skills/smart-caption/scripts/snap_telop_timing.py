#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""テロップ chunk のタイミングを音声の発話区間（VAD）に合わせて補正する。

Whisper のタイミングは体感より「早め」に出る傾向があり、そのままだと
テロップが音声より先に出てしまう。ffmpeg silencedetect で無音区間を取り、
各 chunk の start を「直近の発話開始 + オフセット」に snap する。

しゅうへいの校閲版との差分学習（IMG_8905 / IMG_9097, 2026-05）から：
- snap が当たれば start 差は中央値 0.00 秒（ほぼ完璧）
- snap が外れる（近くに無音が無い）と Whisper の早いタイミングのまま 0.2〜0.5 秒早すぎる
  → 外した chunk には一律 FALLBACK_OFFSET を足して救済する
- しゅうへいは「音が始まってから 0.15〜0.25 秒後にテロップ」を好む → START_OFFSET

使い方:
  python3 snap_telop_timing.py <校閲済み.json> <動画 or 音声>
  → 同じ 校閲済み.json を snap 済みで上書き
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# --- 学習済みパラメータ（差分学習で調整可） ---
SILENCE_NOISE = "-30dB"   # 無音とみなす音量しきい値
SILENCE_DUR = 0.15        # これ以上続く無音だけを区切りとみなす（秒）
START_OFFSET = 0.18       # 発話開始から少し後ろにテロップを出す（しゅうへい好み）
END_OFFSET = 0.10         # 発話終了から少し余韻を残す
SNAP_LO = -0.4            # start を探す範囲：元 start のこれだけ前から
SNAP_HI = 0.3             #                  元 start のこれだけ後ろまで
FALLBACK_OFFSET = 0.15    # snap 候補が無かった chunk に足す保険オフセット


def detect_silences(media_path: Path):
    """ffmpeg silencedetect で無音区間 [(start, end), ...] を返す"""
    r = subprocess.run(
        ["/opt/homebrew/bin/ffmpeg", "-i", str(media_path),
         "-af", f"silencedetect=noise={SILENCE_NOISE}:d={SILENCE_DUR}",
         "-f", "null", "-"],
        capture_output=True, text=True,
    )
    log = r.stderr
    starts = sorted(float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", log))
    ends = sorted(float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", log))
    return starts, ends


def media_duration(media_path: Path) -> float:
    """メディアの総尺（秒）"""
    r = subprocess.run(
        ["/opt/homebrew/bin/ffprobe", "-v", "error",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def clamp_and_distribute(items, dur, min_dur=0.4):
    """動画長を超えた / 重複密集した chunk を救済。
    Whisper が末尾の chunk に退化したタイミング（同一 start/end）を付けることがあり、
    snap の重なり回避が動画長を超えて押し出すのを防ぐ。
    duration を超える chunk 群は、直前 chunk の end 〜 duration に均等配分する。
    """
    if not items or dur <= 0:
        return items
    out = [dict(it) for it in items]
    n = len(out)
    for i in range(n):
        # この chunk が duration を超える / 尺が潰れている → ここから末尾を均等配分
        if out[i]["end"] > dur or out[i]["start"] >= dur - 0.05 \
                or out[i]["end"] - out[i]["start"] < 0.05:
            avail_start = out[i - 1]["end"] if i > 0 else 0.0
            space = dur - avail_start
            k = n - i
            if space > 0 and k > 0:
                seg = space / k
                # 最小尺を確保できないほど詰まっている場合もとりあえず均等割り
                for j in range(k):
                    out[i + j]["start"] = round(avail_start + seg * j, 3)
                    out[i + j]["end"] = round(avail_start + seg * (j + 1), 3)
            break
    return out


def snap_items(items, media_path: Path):
    silence_starts, silence_ends = detect_silences(media_path)
    # 発話開始ポイント = 無音明け（+冒頭 0.0）、発話終了ポイント = 無音入り
    speech_starts = sorted([0.0] + silence_ends)
    speech_ends = sorted(silence_starts)

    def nearest_in_range(t, candidates, lo, hi):
        in_r = [c for c in candidates if t + lo <= c <= t + hi]
        if not in_r:
            return None
        return min(in_r, key=lambda c: abs(c - t))

    out = []
    for it in items:
        # start
        snapped = nearest_in_range(it["start"], speech_starts, SNAP_LO, SNAP_HI)
        if snapped is not None:
            new_start = snapped + START_OFFSET
        else:
            # snap 外し → 一律フォールバックで少し後ろへ
            new_start = it["start"] + FALLBACK_OFFSET
        # end
        snapped_e = nearest_in_range(it["end"], speech_ends, -0.3, 0.5)
        if snapped_e is not None:
            new_end = snapped_e + END_OFFSET
        else:
            new_end = it["end"] + FALLBACK_OFFSET
        # 前 chunk との重なり回避
        if out and new_start < out[-1]["end"]:
            new_start = out[-1]["end"]
        if new_end <= new_start:
            new_end = new_start + max(it["end"] - it["start"], 0.3)
        out.append({**it, "start": round(new_start, 3), "end": round(new_end, 3)})
    # 動画長クランプ＋末尾の退化タイミング救済
    dur = media_duration(media_path)
    out = clamp_and_distribute(out, dur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reviewed_json", help="校閲済み.json のパス")
    ap.add_argument("media", help="動画 or 音声ファイル（VAD用）")
    args = ap.parse_args()

    rev_path = Path(args.reviewed_json)
    media_path = Path(args.media)
    if not rev_path.exists():
        sys.exit(f"校閲済み.json が見つかりません: {rev_path}")
    if not media_path.exists():
        sys.exit(f"メディアが見つかりません: {media_path}")

    data = json.loads(rev_path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    snapped = snap_items(items, media_path)
    data["items"] = snapped
    rev_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ snap 完了: {len(snapped)} chunks → {rev_path.name}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""オンセットスナップ — テロップ開始を実際の音声立ち上がりに前方スナップする。

背景（2026-07 DH木村さんインタビューの実測で確定）:
  Whisper の word 開始時刻は「ポーズ明けの語」で実発話より 0.2〜0.7 秒早く付く。
  直前語の引き延ばしや無音を語頭に含める癖があるため、word 時刻に
  そのままアンカーすると「声より先にテロップが出る」ズレになる。
  逆方向（遅れ）はほぼ発生しない。

やること:
  各テロップ start 付近の RMS 包絡（10ms窓）から
  「MIN_SIL 以上の無音 → ONSET_HOLD 連続の持続的有音」の立ち上がりを検出し、
  start をそこへ**遅らせる方向のみ**スナップする。

鉄則（実測で踏んだ地雷。変更前に必ず理由を確認）:
  1. 前方（遅らせる）のみ。早める補正は「はい」「そうですね」などテロップに
     含めない先行語へ誤吸着する。
  2. 候補は「アンカー以降の最初のオンセット」。最近傍で選ぶと直前発話の
     立ち上がりを拾う。
  3. 無音カウンタは「持続的有音が無い区間」で数える。孤立ノイズ1フレームで
     リセットすると候補を取り逃す。
  4. 無音閾値は固定値にしない。整音後はノイズフロアが上がる（-42dB前後）ため
     包絡の10パーセンタイル+4dB で自動決定する。
  5. 検出オンセットから息漏れ・柔らかい子音ぶんを最大 0.15s 巻き戻す
     （閾値ベース検出は soft onset を遅く見積もるため）。
  6. 連続発話中（近傍に無音なし）のテロップは触らない。word アンカーが正。

使い方:
  python3 onset_snap.py --koetsu <koetsu.json> --media <mp4/wav>  [--check] [--srt <out.srt>]

  --koetsu : items[].start/end が --media と同じタイムライン（カット後動画なら
             カット後時刻）であること
  --check  : 書き換えずズレレポートのみ（qc-gate の sync 独立検証に使える）
  --srt    : スナップ後の SRT も書き出す

表示側の注意:
  焼き込み時はさらに 0.05s 程度の表示リードを付けること（render-* 側の仕事）。
  koetsu.json の start は「発話開始そのもの」を表す。
"""
import argparse
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

try:
    import numpy as np
except ImportError:
    sys.exit("onset_snap.py には numpy が必要です: pip3 install numpy")

HOP = 0.010          # RMS 窓 10ms
MIN_SIL = 0.15       # オンセット直前に必要な無音長（秒）
ONSET_HOLD = 3       # 3フレーム(30ms)連続で有音なら立ち上がりとみなす
SOFT_BACK = 15       # 柔らかい立ち上がりの巻き戻し上限（フレーム＝0.15s）
SEARCH_PRE = 0.60    # アンカーより前をどこまで見るか（無音判定のため）
SEARCH_POST = 0.90   # アンカーよりどれだけ後ろまでオンセットを探すか
MIN_SHIFT = 0.12     # これ未満のズレは触らない
MAX_SHIFT = 0.85     # これ超の移動はしない（誤検出ガード）
MIN_DUR = 0.45       # スナップ後の最低表示時間


def extract_env(media: Path):
    """media → 16k mono RMS包絡(dB) と 自動無音閾値"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(media),
             "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav_path)],
            check=True)
        with wave.open(str(wav_path)) as w:
            sr = w.getframerate()
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)
    finally:
        wav_path.unlink(missing_ok=True)
    x /= 32768.0
    hop = int(sr * HOP)
    n = len(x) // hop
    env = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    db = 20 * np.log10(np.maximum(env, 1e-8))
    sil_db = max(-48.0, float(np.percentile(db, 10)) + 4.0)
    return db, sil_db


def find_onset(db, sil_db, anchor):
    """anchor 以降の最初の「無音→持続的有音」立ち上がり時刻。無ければ None"""
    soft_db = sil_db - 6.0
    i0 = max(0, int((anchor - SEARCH_PRE) / HOP))
    i1 = min(len(db) - ONSET_HOLD, int((anchor + SEARCH_POST) / HOP))
    voiced = db >= sil_db
    run = 0
    for i in range(i0, i1):
        sustained = bool(all(voiced[i : i + ONSET_HOLD]))
        if not sustained:
            run += 1        # 孤立ノイズもここに落ちる（リセットしない）
            continue
        if run * HOP >= MIN_SIL:
            j = i
            while j > 0 and i - j < SOFT_BACK and db[j - 1] >= soft_db:
                j -= 1
            t = j * HOP
            if t >= anchor - 0.05:   # 前方のみ・直前発話に吸着しない
                return t
        run = 0
    return None


def srt_time(t):
    ms = int(round(t * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--koetsu", required=True, type=Path)
    ap.add_argument("--media", required=True, type=Path)
    ap.add_argument("--check", action="store_true", help="書き換えずレポートのみ")
    ap.add_argument("--srt", type=Path, help="スナップ後の SRT 出力先")
    args = ap.parse_args()

    db, sil_db = extract_env(args.media)
    data = json.loads(args.koetsu.read_text(encoding="utf-8"))
    items = data["items"] if isinstance(data, dict) else data
    print(f"noise-floor auto threshold: {sil_db:.1f} dB")

    adjusted = 0
    for idx, it in enumerate(items):
        onset = find_onset(db, sil_db, it["start"])
        if onset is None:
            continue
        new_start = round(onset, 3)
        shift = new_start - it["start"]
        if shift < MIN_SHIFT or shift > MAX_SHIFT:
            continue
        if it["end"] - new_start < MIN_DUR:
            new_start = round(max(it["start"], it["end"] - MIN_DUR), 3)
        if idx > 0 and new_start < items[idx - 1]["end"]:
            new_start = items[idx - 1]["end"]
        if new_start <= it["start"]:
            continue
        head = it["text"].splitlines()[0]
        print(f"  {it['start']:8.2f} -> {new_start:8.2f} ({new_start - it['start']:+.2f}s)  {head}")
        if not args.check:
            it["start"] = new_start
        adjusted += 1

    verb = "would adjust" if args.check else "adjusted"
    print(f"{verb} {adjusted}/{len(items)} captions")
    if args.check:
        return

    args.koetsu.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.srt:
        with args.srt.open("w", encoding="utf-8") as f:
            for i, it in enumerate(items, 1):
                f.write(f"{i}\n{srt_time(it['start'])} --> {srt_time(it['end'])}\n{it['text']}\n\n")
        print(f"wrote {args.srt}")


if __name__ == "__main__":
    main()

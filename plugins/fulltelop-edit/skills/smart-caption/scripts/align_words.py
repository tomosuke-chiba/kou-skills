#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""align_words.py — テロップ草案（[[text, first_anchor, last_anchor, after_s], ...]）を
words.json に対して first+last anchor で時刻アンカーし、aligned_telops.json と koetsu.json を出す。

使い方:
  align_words.py --words <words.json> --telops <telops.json> --work <work_dir> [--lead 0.07] [--tail 0.18]

telops.json の形式:
  [
    {"text": "やばい", "first": "やばい", "last": "やばい", "after": 0},
    {"text": "1時間ぐらいで\ndできちゃいました", "first": "1時間", "last": "ました", "after": 10},
    ...
  ]
"""
import argparse, json, sys
from pathlib import Path


def build_index(words):
    """words から char→time のフラットなインデックスを作る"""
    chars, cstart, cend = [], [], []
    for w in words:
        s, e, txt = w["start"], w["end"], w["word"]
        for ch in txt:
            chars.append(ch)
            cstart.append(float(s))
            cend.append(float(e))
    return "".join(chars), cstart, cend


def idx_after(cstart, t):
    for i, x in enumerate(cstart):
        if x >= t:
            return i
    return 0


def align(words, telops, lead=0.07, tail=0.18, min_dur=0.9, max_dur=3.6, end_safety=99999.0):
    full, cstart, cend = build_index(words)
    spans = []
    for ts in telops:
        text = ts["text"]
        first = ts["first"]
        last = ts.get("last", first)
        after = float(ts.get("after", 0))
        i0 = idx_after(cstart, after)
        p1 = full.find(first, i0)
        s = cstart[p1] if p1 >= 0 else after
        p2 = full.find(last, p1 if p1 >= 0 else i0)
        e = cend[p2 + len(last) - 1] if p2 >= 0 else s + 1.5
        spans.append([round(s + lead, 3), round(e, 3), text])

    # end clamp: next.start - 0.05 / +tail / max_dur
    out = []
    for i, (s, e, t) in enumerate(spans):
        nxt = spans[i + 1][0] if i + 1 < len(spans) else end_safety
        e_clamped = min(e + tail, nxt - 0.05, s + max_dur)
        if e_clamped - s < min_dur:
            e_clamped = min(s + min_dur, nxt - 0.05)
        out.append([round(s, 3), round(e_clamped, 3), t])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", required=True)
    ap.add_argument("--telops", required=True, help="テロップ草案 JSON (list of {text, first, last, after})")
    ap.add_argument("--work", required=True, help="出力ディレクトリ")
    ap.add_argument("--stem", default="captions")
    ap.add_argument("--lead", type=float, default=0.07)
    ap.add_argument("--tail", type=float, default=0.18)
    args = ap.parse_args()

    wdata = json.loads(Path(args.words).read_text(encoding="utf-8"))
    words = [w for seg in wdata.get("segments", []) for w in seg.get("words", [])]
    telops = json.loads(Path(args.telops).read_text(encoding="utf-8"))
    aligned = align(words, telops, args.lead, args.tail)

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    (work / "aligned_telops.json").write_text(
        json.dumps(aligned, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    koetsu = {
        "version": 1,
        "stem": args.stem,
        "items": [{"start": a, "end": b, "text": t} for a, b, t in aligned],
    }
    (work / "koetsu.json").write_text(
        json.dumps(koetsu, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"aligned {len(aligned)} telops → {work}/aligned_telops.json, koetsu.json")


if __name__ == "__main__":
    main()

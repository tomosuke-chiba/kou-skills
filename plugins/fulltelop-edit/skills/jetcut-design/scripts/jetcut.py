#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jetcut.py — words.json から keep_segments を計算（無音詰め + DROP_RANGES + opening/end cut）"""
import argparse, json, sys
from pathlib import Path


SENT_END_TAIL = ("ます", "です", "でした", "ました", "ない", "なくて", "ください",
                 "だ", "だった", "ね", "よ", "か", "?", "？", "！", "！？")


def _extend_to_sentence_end(words, idx, max_extend=0.40):
    """word[idx] が文末形に近いなら、文末の語まで end を延ばして返す。
    語尾の途中で切らないため。"""
    if idx + 1 >= len(words):
        return words[idx][1]
    w = words[idx][2].strip()
    # 既に文末形なら延ばさない
    if any(w.endswith(t) for t in SENT_END_TAIL):
        return words[idx][1]
    # 直後 1〜2 word が文末形なら、その end まで延ばす
    for j in range(idx + 1, min(idx + 3, len(words))):
        nw = words[j][2].strip()
        if any(nw.endswith(t) for t in SENT_END_TAIL):
            if words[j][1] - words[idx][1] <= max_extend:
                return words[j][1]
            break
    return words[idx][1]


def compute_keep(words, opening_cut, end_cut, silence_thresh, drop_ranges,
                 src_duration, keep_side=0.20, protect_sentence_end=True):
    def in_drop(t):
        return any(a <= t <= b for a, b in drop_ranges)
    if end_cut <= 0:
        end_cut = src_duration
    Wr = [(s, e, w) for s, e, w in words
          if opening_cut - 0.5 <= s <= end_cut and not in_drop(s)]
    keep = []
    cur = opening_cut
    extensions = []  # 語尾延長ログ
    for i in range(len(Wr) - 1):
        gap = Wr[i + 1][0] - Wr[i][1]
        boundary = any(Wr[i][1] <= a <= Wr[i + 1][0] or Wr[i][1] <= b <= Wr[i + 1][0]
                       for a, b in drop_ranges)
        if gap > silence_thresh or boundary:
            cut_out = Wr[i][1]
            if protect_sentence_end:
                ext = _extend_to_sentence_end(Wr, i)
                if ext > cut_out:
                    extensions.append({
                        "src_in": round(cur, 3),
                        "from": round(cut_out, 3),
                        "to": round(ext, 3),
                        "reason": f"語尾「{Wr[i][2]}」が途中で切れるため延長"
                    })
                    cut_out = ext
            keep.append((round(cur, 3), round(min(end_cut, cut_out + keep_side), 3)))
            cur = max(opening_cut, Wr[i + 1][0] - keep_side)
    if Wr:
        keep.append((round(cur, 3), round(min(end_cut, Wr[-1][1] + 0.3), 3)))
    return keep, extensions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", required=True)
    ap.add_argument("--out", required=True, help="keep_segments.json output")
    ap.add_argument("--opening-cut", type=float, default=0.0)
    ap.add_argument("--end-cut", type=float, default=0.0, help="0 = use src duration")
    ap.add_argument("--silence-thresh", type=float, default=1.0)
    ap.add_argument("--drop", action="append", default=[], help="DROP range e.g. 64.30-68.18 (can repeat)")
    ap.add_argument("--src-duration", type=float, required=True)
    ap.add_argument("--keep-side", type=float, default=0.20)
    args = ap.parse_args()

    wdata = json.loads(Path(args.words).read_text(encoding="utf-8"))
    words = [(w["start"], w["end"], w["word"])
             for seg in wdata.get("segments", [])
             for w in seg.get("words", [])]
    drops = []
    for d in args.drop:
        a, b = d.split("-")
        drops.append((float(a), float(b)))
    keep, extensions = compute_keep(words, args.opening_cut, args.end_cut, args.silence_thresh,
                                    drops, args.src_duration, args.keep_side)
    out_dur = sum(b - a for a, b in keep)
    src_dur = args.src_duration
    result = {
        "keep_segments": keep,
        "out_duration_s": round(out_dur, 2),
        "src_duration_s": src_dur,
        "compression_ratio": round(out_dur / src_dur, 3) if src_dur else None,
        "drop_ranges_applied": [[a, b] for a, b in drops],
        "opening_cut_s": args.opening_cut,
        "end_cut_s": args.end_cut,
        "silence_thresh_s": args.silence_thresh,
        "sentence_end_extensions": extensions,
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"keep_segments={len(keep)}  src {src_dur:.1f}s → out {out_dur:.1f}s  ratio {result['compression_ratio']}")
    if extensions:
        print(f"  語尾延長: {len(extensions)}件（途中切れ回避）")


if __name__ == "__main__":
    main()

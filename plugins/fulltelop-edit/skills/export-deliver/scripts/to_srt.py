#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""to_srt.py — koetsu.json から SRT を出力"""
import argparse, json, re, sys
from pathlib import Path


def s_to_srt(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("koetsu")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    d = json.loads(Path(args.koetsu).read_text(encoding="utf-8"))
    lines = []
    for i, it in enumerate(d["items"], 1):
        text = it["text"]
        # SRT は改行があってもOK
        lines.append(f"{i}\n{s_to_srt(it['start'])} --> {s_to_srt(it['end'])}\n{text}\n")
    # Python 3.9 互換のため Path.write_text は newline 未対応 → open で書く
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"SRT written: {args.out}  ({len(d['items'])} cues)")


if __name__ == "__main__":
    main()

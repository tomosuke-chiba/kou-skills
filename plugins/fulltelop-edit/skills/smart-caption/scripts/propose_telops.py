#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""propose_telops.py — words.json から telops.json の雛形を自動生成。

LLM が文脈で直す前段として、機械的に「ここで区切るのが自然」な候補を出す。
出力された telops.json を LLM が読んで誤変換補正・意訳・行頭NG調整してから、
align_words.py で word 時刻にアンカーする。

使い方:
  propose_telops.py --words <words.json> --out <telops.json>
                    [--max-chars 17] [--min-pause 0.4]
                    [--vocab <vocabulary.json>]

出力フォーマット:
  [
    {"text": "やばい", "first": "やばい", "last": "やばい", "after": 0.0,
     "_src_text": "やばい", "_notes": ["短発話"]},
    {"text": "AIで1日でアプリ作れちゃった", "first": "AI", "last": "ちゃった", "after": 4.5,
     "_src_text": "AIで1日でアプリ作れちゃった", "_notes": []},
    ...
  ]

`_src_text` は生Whisperの原文。`text` はそのコピーで、LLM が後から
誤変換補正・「ぐらい」保持・意訳をして書き換える。
"""
import argparse, json, re, sys, unicodedata
from pathlib import Path


def zenkaku_len(s):
    n = 0.0
    for ch in s:
        if ch in ("\n", "\r"):
            continue
        w = unicodedata.east_asian_width(ch)
        n += 1.0 if w in ("F", "W", "A") else 0.5
    return n


def is_breakable_after(prev_word, next_word):
    """この語境界で区切れるか（文末・接続助詞・格助詞の優先）"""
    # 文末
    SENT_END = ("です", "ます", "ました", "でした", "ですよ", "ますよ",
                "ない", "だ", "だった", "ね", "よ", "か", "?", "？")
    # 接続助詞
    CONN = ("から", "ので", "くて", "して", "のに", "けど", "けれど", "ても")
    # 格助詞
    CASE = ("が", "を", "に", "で", "と", "は", "も", "へ")

    p = prev_word.strip()
    n = next_word.strip()

    if any(p.endswith(e) for e in SENT_END):
        return 3  # 最優先
    if any(p.endswith(c) for c in CONN):
        return 2
    if any(p.endswith(c) for c in CASE):
        return 1
    # 名詞→新しい文の頭（指示語など）も中程度
    if n in ("で", "じゃあ", "なので", "あと", "あとは", "なんか", "もう", "やっぱり",
             "今日", "昨日", "実は", "ちなみに"):
        return 2
    return 0


def is_filler(word):
    """フィラー（消してよい）。「なんか」「もう」は語り味として残すべきだが、
    ここは機械的に検出して LLM 側で残す/消すを判断する。"""
    FILLERS = ("えー", "えーっと", "あー", "あのー", "あの", "うーん", "そのー", "その",
               "まあ", "なんか", "ちょっと", "一応", "はい", "いやー")
    return word.strip() in FILLERS


JOIN_FORBIDDEN = re.compile(r"[A-Za-z0-9ー]")  # カタカナ・英数字の連続途中で割らない


def split_at(text, idx):
    """文字列の idx 位置で割っていいか。カタカナ・英数字・固有名詞の連続途中なら避ける"""
    if idx <= 0 or idx >= len(text):
        return False
    a, b = text[idx - 1], text[idx]
    if JOIN_FORBIDDEN.search(a) and JOIN_FORBIDDEN.search(b):
        return False
    # カタカナ連続途中
    katakana = lambda c: "ァ" <= c <= "ヴ" or c == "ー"
    if katakana(a) and katakana(b):
        return False
    return True


def propose(words, max_chars=17, min_pause=0.4):
    """word 配列から テロップ候補リストを返す"""
    out = []
    buf_words = []
    buf_text = ""
    buf_start = None

    def flush():
        nonlocal buf_words, buf_text, buf_start
        if not buf_words:
            return
        text = buf_text.strip()
        if not text:
            buf_words = []
            buf_text = ""
            buf_start = None
            return
        # first / last アンカー語の選定
        # first: できるだけ固有性のある先頭2-3文字
        # last: できるだけ後方の動詞末尾・名詞
        first = text[:2]
        last = text[-3:] if len(text) >= 3 else text[-2:] if len(text) >= 2 else text
        notes = []
        if any(is_filler(w["word"]) for w in buf_words):
            notes.append("フィラー含む(要見直し)")
        if zenkaku_len(text) > max_chars:
            notes.append(f"{zenkaku_len(text):.0f}字超(2行化推奨)")
        out.append({
            "text": text,
            "first": first,
            "last": last,
            "after": round(buf_start, 2) if buf_start is not None else 0.0,
            "_src_text": text,
            "_notes": notes,
        })
        buf_words = []
        buf_text = ""
        buf_start = None

    for i, w in enumerate(words):
        if buf_start is None:
            buf_start = float(w["start"])
        buf_words.append(w)
        buf_text += w["word"]

        # 次の語との間隔をチェック
        pause = 0.0
        if i + 1 < len(words):
            pause = float(words[i + 1]["start"]) - float(w["end"])

        cur_len = zenkaku_len(buf_text)
        next_word = words[i + 1]["word"] if i + 1 < len(words) else ""

        # 区切り判断
        force_break = False
        if pause >= min_pause:
            force_break = True  # 自然な間
        elif cur_len >= max_chars * 0.8:
            # しきい値の80%超えたら、文末・接続助詞があれば切る
            score = is_breakable_after(w["word"], next_word)
            if score >= 2:
                force_break = True
            elif cur_len >= max_chars:
                # しきい値超えたら格助詞でも切る
                if score >= 1:
                    force_break = True
                elif cur_len >= max_chars * 1.3 and split_at(buf_text, len(buf_text)):
                    # 強制（カタカナ・英数字連続途中は避ける）
                    force_break = True
        if force_break:
            flush()

    flush()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-chars", type=int, default=17)
    ap.add_argument("--min-pause", type=float, default=0.4)
    ap.add_argument("--vocab", default=None, help="vocabulary.json で辞書ベース補正を当てる")
    args = ap.parse_args()

    wdata = json.loads(Path(args.words).read_text(encoding="utf-8"))
    words = [w for seg in wdata.get("segments", []) for w in seg.get("words", [])]
    if not words:
        sys.stderr.write("ERROR: words.json に word が無い\n")
        sys.exit(2)

    # 辞書補正（pattern → replacement）
    if args.vocab and Path(args.vocab).exists():
        vocab = json.loads(Path(args.vocab).read_text(encoding="utf-8"))
        for c in vocab.get("corrections", []):
            try:
                pat = re.compile(c["pattern"])
                for w in words:
                    w["word"] = pat.sub(c["replacement"], w["word"])
            except re.error:
                continue

    proposed = propose(words, args.max_chars, args.min_pause)
    Path(args.out).write_text(json.dumps(proposed, ensure_ascii=False, indent=1), encoding="utf-8")

    n_filler = sum(1 for p in proposed if any("フィラー" in n for n in p["_notes"]))
    n_long = sum(1 for p in proposed if any("字超" in n for n in p["_notes"]))
    print(f"proposed {len(proposed)} telops → {args.out}")
    print(f"  flags: filler={n_filler}, too_long={n_long}")
    print(f"  next step: LLM が文脈で text を直し、誤変換補正・意訳・行頭NG調整 →")
    print(f"  align_words.py --words {args.words} --telops {args.out} --work <dir>")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""テロップ chunk のタイミングを、ユーザーtext と Whisper word を
系列アライメント（Needleman-Wunsch）で対応づけて正確に振り直す。

なぜ DP アライメントか（2026-06「Claudeがやばい」改修の最終形）:
- VAD snap：無音がほぼ無い一気喋りで誤吸着→全体ズレ。
- 文字数比：ローマ字(Claude/Code)や言い換え・追加語(「1文字も」)・落とした語(「すごい」)で
  境界がドリフト→間延び／次の音が入り込む。
- → ユーザーが文言を書き換えても、**1文字ずつ最適対応**を取れば各 chunk が
  「実際にその言葉を喋っている時刻」に乗る。straddle（こちら|293万円）も落とし語も正しく処理。

アルゴリズム:
  A = ユーザー全テキストの正規化文字列（chunk 境界を記録）
  B = Whisper word を1文字に展開（各文字に word の start/end を持たせる）
  NW で A↔B を大域整列（カタカナ→ひらがな・英字小文字化で一致率UP）
  各 chunk:
    start = chunk 先頭文字が対応する word の開始時刻（語頭にスナップ）
    end   = 次 chunk の start まで（連続喋り＝自然な余韻）。
            ただし chunk 末尾語の終わり〜次 start の空白が大きい（間/落とし語）なら語尾に詰める。

使い方:
  python3 retime_telop.py <校閲済み.json> <動画 or 音声>
  word JSON（/tmp/telop_<stem>/<stem>.json）が無ければ何もしない（壊さない）。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TRIM_GAP = 0.25       # 次の頭までの空白がこれ以上なら end を語尾に詰める（間延び防止）
END_PAD = 0.08
MIN_DUR = 0.35

_PUNCT = re.compile(r'[\s、。，．,\.\?\？!！「」『』…・ー─-]')


def to_match_form(s: str) -> str:
    """一致比較用に正規化：記号除去・カタカナ→ひらがな・英字小文字化"""
    s = _PUNCT.sub('', s or '')
    out = []
    for ch in s:
        o = ord(ch)
        if 0x30A1 <= o <= 0x30F6:        # カタカナ → ひらがな
            out.append(chr(o - 0x60))
        else:
            out.append(ch.lower())
    return ''.join(out)


def find_word_json(media_path: Path, stem: str, hint: Path = None):
    """word JSON を探す。hint があれば優先（プラグイン経路では明示指定）。"""
    if hint and hint.exists():
        return hint
    for p in [Path(f"/tmp/telop_{stem}/{stem}.json"),
              Path(f"/private/tmp/telop_{stem}/{stem}.json"),
              media_path.parent / f"{stem}.json",
              media_path.parent / "words.json"]:
        if p.exists():
            return p
    return None


def load_words(word_json: Path):
    d = json.loads(word_json.read_text(encoding="utf-8"))
    words = []
    for seg in d.get("segments", []):
        for w in seg.get("words", []):
            s = w.get("start")
            if s is None:
                continue
            e = w.get("end")
            words.append((float(s), float(e if e is not None else s),
                          w.get("word", "")))
    words.sort(key=lambda x: x[0])
    return words


def media_duration(media_path: Path) -> float:
    r = subprocess.run(
        ["/opt/homebrew/bin/ffprobe", "-v", "error",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def nw_align(A, B):
    """A,B は文字列。各 A[i] に対応する B index（or None）の配列を返す。
    match=+2, mismatch=-1, gap=-1 の Needleman-Wunsch。"""
    M, N = len(A), len(B)
    GAP = -1.0
    # 同一文字のタイは「より早い（小さい j）一致」を優先：match に EPS*(N-j) を加点。
    # これで「ない」の い が、落とした「すごい」の い に飛ぶ誤マッチを防ぐ。
    EPS = 1e-7
    prev = [j * GAP for j in range(N + 1)]
    bt = [[2] * (N + 1) for _ in range(M + 1)]  # 0=diag 1=up(Aを消費) 2=left(Bを消費)
    for j in range(N + 1):
        bt[0][j] = 2
    for i in range(1, M + 1):
        cur = [i * GAP] + [0.0] * N
        bt[i][0] = 1
        ai = A[i - 1]
        for j in range(1, N + 1):
            if ai == B[j - 1]:
                diag = prev[j - 1] + 2.0 + EPS * (N - j)
            else:
                diag = prev[j - 1] - 1.0
            up = prev[j] + GAP
            left = cur[j - 1] + GAP
            best = diag
            d = 0
            if up > best:
                best = up
                d = 1
            if left > best:
                best = left
                d = 2
            cur[j] = best
            bt[i][j] = d
        prev = cur
    aligned = [None] * M
    i, j = M, N
    while i > 0 and j > 0:
        d = bt[i][j]
        if d == 0:
            aligned[i - 1] = j - 1
            i -= 1
            j -= 1
        elif d == 1:
            i -= 1
        else:
            j -= 1
    return aligned


def retime(items, words, dur):
    n = len(items)
    if n == 0 or not words:
        return items
    last_end = words[-1][1]

    # B: word を1文字展開（char, word_start, word_end）
    B_chars, B_on, B_off = [], [], []
    for s, e, w in words:
        for ch in to_match_form(w):
            B_chars.append(ch)
            B_on.append(s)
            B_off.append(e)
    Bstr = ''.join(B_chars)

    # A: ユーザー全文字 + 各 chunk の [先頭, 末尾] 文字 index
    A_chars = []
    spans = []  # (first_idx, last_idx) per chunk（空 chunk は (None,None)）
    for it in items:
        t = to_match_form(it.get("text", ""))
        if not t:
            spans.append((None, None))
            continue
        fi = len(A_chars)
        A_chars.extend(t)
        spans.append((fi, len(A_chars) - 1))
    Astr = ''.join(A_chars)
    if not Astr or not Bstr:
        return items

    aligned = nw_align(Astr, Bstr)

    def fwd_bidx(i):
        """A index i 以降で最初に対応がついた B index"""
        for k in range(i, len(aligned)):
            if aligned[k] is not None:
                return aligned[k]
        return None

    def bwd_bidx(i):
        """A index i 以前で最後に対応がついた B index"""
        for k in range(i, -1, -1):
            if aligned[k] is not None:
                return aligned[k]
        return None

    # 各 chunk の start（語頭）と 末尾語の offset
    starts = [None] * n
    last_off = [None] * n
    for k, (fi, li) in enumerate(spans):
        if fi is None:
            continue
        b0 = fwd_bidx(fi)
        b1 = bwd_bidx(li)
        if b0 is not None:
            starts[k] = B_on[b0]
        if b1 is not None:
            last_off[k] = B_off[b1]

    # 欠損（空 chunk 等）を前後で補間
    for k in range(n):
        if starts[k] is None:
            starts[k] = starts[k - 1] if k > 0 and starts[k - 1] is not None else 0.0
    # 単調化
    for k in range(1, n):
        if starts[k] <= starts[k - 1]:
            starts[k] = starts[k - 1] + 0.05

    out = []
    for k in range(n):
        st = starts[k]
        if k + 1 < n:
            ns = starts[k + 1]
            en = ns
            lo = last_off[k]
            if lo is not None and lo > st and (ns - lo) > TRIM_GAP:
                en = min(ns, lo + END_PAD)   # 間/落とし語 → 語尾に詰める
        else:
            en = last_off[k] if last_off[k] and last_off[k] > st else last_end
        if en <= st:
            en = st + MIN_DUR
        out.append({**items[k], "start": round(st, 3), "end": round(en, 3)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reviewed_json", help="校閲済み.json または koetsu.json（item: start/end/text）")
    ap.add_argument("media", help="動画 or 音声ファイル")
    ap.add_argument("--words", default=None,
                    help="words.json を明示指定（プラグイン経路推奨）。無ければ自動探索")
    args = ap.parse_args()
    rev = Path(args.reviewed_json)
    media = Path(args.media)
    if not rev.exists():
        sys.exit(f"校閲済み.json が見つかりません: {rev}")
    data = json.loads(rev.read_text(encoding="utf-8"))
    items = data.get("items", [])
    stem = data.get("stem") or media.stem
    hint = Path(args.words) if args.words else None
    wj = find_word_json(media, stem, hint)
    if not wj:
        print(f"⚠️ word JSON 無し → retime スキップ（時刻そのまま）: {stem}", file=sys.stderr)
        return
    words = load_words(wj)
    dur = media_duration(media) if media.exists() else (words[-1][1] if words else 0)
    data["items"] = retime(items, words, dur)
    rev.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ retime(DP) 完了: {len(data['items'])} chunks → {rev.name}")


if __name__ == "__main__":
    main()

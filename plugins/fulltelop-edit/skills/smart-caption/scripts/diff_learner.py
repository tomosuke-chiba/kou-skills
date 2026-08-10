#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raw.tsv と 校閲済み.json の diff から corrections 候補を抽出

各 item の text と raw_map[src] を比較。共通プレフィックス・サフィックスを除いた
「変化したコア」が
- before の長さ ≥ 3 字
- levenshtein 距離 ≥ 2
を満たすものを `<stem>_learn_candidates.json` に書き出す。

分割された 2 つの item が同じ src を持つ場合は、両方の text を連結して比較する
（分割は誤変換補正の対象ではないため）。
"""
import argparse
import json
from datetime import date
from pathlib import Path


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def extract_diff(before: str, after: str):
    if before == after:
        return None
    i = 0
    while i < min(len(before), len(after)) and before[i] == after[i]:
        i += 1
    j = 0
    max_j = min(len(before) - i, len(after) - i)
    while j < max_j and before[-(j + 1)] == after[-(j + 1)]:
        j += 1
    b_core = before[i:len(before) - j] if j else before[i:]
    a_core = after[i:len(after) - j] if j else after[i:]
    if not b_core and not a_core:
        return None
    return b_core, a_core


def analyze(raw_tsv: Path, reviewed_json: Path, out_json: Path, stem: str) -> list:
    # raw_map: src(idx) → text
    raw_map = {}
    with raw_tsv.open(encoding="utf-8") as f:
        next(f, None)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 4:
                raw_map[int(parts[0])] = parts[3]

    data = json.loads(reviewed_json.read_text(encoding="utf-8"))
    items = data.get("items", [])

    # 同 src の text を連結（分割で 2 つ以上の item に分かれた場合の救済）
    by_src = {}
    for it in items:
        src = it.get("src", -1)
        if src is None or src < 0:
            continue
        by_src.setdefault(src, []).append(it.get("text", "") or "")
    src_to_reviewed = {s: "".join(parts).strip() for s, parts in by_src.items()}

    counter = {}
    for src, rev in src_to_reviewed.items():
        raw = (raw_map.get(src) or "").strip()
        if not raw or not rev or raw == rev:
            continue
        d = extract_diff(raw, rev)
        if not d:
            continue
        b, a = d
        # しきい値1：単語レベルの誤変換補正だけを残す
        if len(b) < 3 or levenshtein(b, a) < 2:
            continue
        # しきい値2：raw 全体の半分以上が変わったら「大幅編集」→ 誤変換補正ではない
        if len(b) >= len(raw) * 0.5:
            continue
        # しきい値3：after が空 = 「削除」操作。校閲者の語り口の意図的削除なので除外
        #            （「なんか」「もう」「やっぱ」など本人の特徴語を消す候補を弾く）
        if not a:
            continue
        # しきい値4：after が極端に長い（before の 1.5 倍 + 5 字超）→ 分割編集の副産物
        if len(a) > len(b) * 1.5 + 5:
            continue
        key = (b, a)
        if key not in counter:
            counter[key] = {"before": b, "after": a, "count": 0, "examples": []}
        counter[key]["count"] += 1
        if len(counter[key]["examples"]) < 3:
            counter[key]["examples"].append({"raw": raw, "reviewed": rev})

    candidates = sorted(counter.values(), key=lambda x: -x["count"])

    out_json.write_text(
        json.dumps({
            "stem": stem,
            "generated": date.today().isoformat(),
            "candidates": candidates,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return candidates


def analyze_from_proposed(proposed_json: Path, reviewed_json: Path,
                          out_json: Path, stem: str) -> list:
    """プラグイン経路：proposed_telops.json(raw) と koetsu.json(reviewed) の差分から候補抽出。
    両方とも items: [{text:..., ...}] 形式（順序対応・proposed の index → reviewed の index）。"""
    proposed = json.loads(proposed_json.read_text(encoding="utf-8"))
    reviewed = json.loads(reviewed_json.read_text(encoding="utf-8"))
    # proposed は list（propose_telops.py の形式）or dict.items
    p_items = proposed if isinstance(proposed, list) else proposed.get("items", [])
    r_items = reviewed.get("items", [])

    # 並び順で対応（LLM が分割/統合してると個数が違うので min まで）
    counter = {}
    n = min(len(p_items), len(r_items))
    for i in range(n):
        before = (p_items[i].get("_src_text") or p_items[i].get("text") or "").strip()
        after = (r_items[i].get("text") or "").strip()
        if not before or not after or before == after:
            continue
        diff = extract_diff(before, after)
        if not diff:
            continue
        b, a = diff
        if len(b) < 3 or levenshtein(b, a) < 2:
            continue
        if len(a) > len(b) * 1.5 + 5:
            continue
        key = (b, a)
        if key not in counter:
            counter[key] = {"before": b, "after": a, "count": 0, "examples": []}
        counter[key]["count"] += 1
        if len(counter[key]["examples"]) < 3:
            counter[key]["examples"].append({"raw": before, "reviewed": after})

    candidates = sorted(counter.values(), key=lambda x: -x["count"])
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps({
            "stem": stem,
            "generated": date.today().isoformat(),
            "candidates": candidates,
            "source": "proposed_vs_reviewed",
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return candidates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hook", default=None, help="（旧経路）telop-editor の hook ファイル")
    # プラグイン経路（proposed_telops vs koetsu の差分）
    ap.add_argument("--proposed", default=None, help="proposed_telops.json")
    ap.add_argument("--reviewed", default=None, help="koetsu.json または校閲済み.json")
    ap.add_argument("--out", default=None, help="候補出力 JSON")
    ap.add_argument("--stem", default=None)
    args = ap.parse_args()

    # 旧経路（telop-editor hook）
    if args.hook:
        hook = json.loads(Path(args.hook).read_text(encoding="utf-8"))
        reviewed_json = Path(hook.get("reviewed_json") or hook.get("reviewed_text", ""))
        if not reviewed_json.exists() or reviewed_json.suffix != ".json":
            print(f"⚠️ 校閲済み.json なし、スキップ: {reviewed_json}")
            return
        out_json = Path(hook["work_dir"]) / f"{hook['stem']}_learn_candidates.json"
        cands = analyze(Path(hook["raw_tsv"]), reviewed_json, out_json, hook["stem"])
        print(f"✅ diff_learner(hook): {len(cands)} candidates → {out_json}")
        return

    # プラグイン経路
    if not (args.proposed and args.reviewed and args.out):
        sys.exit("--proposed --reviewed --out のすべてが必要（または --hook 旧経路）")
    stem = args.stem or Path(args.reviewed).stem
    cands = analyze_from_proposed(
        Path(args.proposed), Path(args.reviewed), Path(args.out), stem
    )
    print(f"✅ diff_learner: {len(cands)} candidates → {args.out}")


if __name__ == "__main__":
    import sys
    main()

---
name: smart-caption
description: words.json から「意味の通った字幕（スマート字幕）」を作る。Whisper の誤変換を文脈で直し、17文字前後で意味の切れ目に分割し、各テロップを「最初の語」と「最後の語」の両方で word 時刻にアンカーする。生Whisperそのまま出さない・文末＞接続助詞＞格助詞の優先順位で切る・行頭NG回避・カタカナ/英数字を割らない。スマート字幕／意味の切れ目／文脈補正／誤変換補正で発火。
---

# smart-caption — 文脈補正＋word時刻アンカーの本体

教科書の核心スキル。**生Whisper＋辞書補正＋retime だけでは出さない**。全文を意味で読み直し、文脈依存の誤変換を直し、word 時刻にアンカーしてテロップを作る。

## やること（3段階のパイプライン）

```
words.json
   │
   ▼ scripts/propose_telops.py で機械的に候補生成
proposed_telops.json   ← 機械の素案（分割候補＋first/last/after が埋まってる）
   │
   ▼ LLM（あなた）が文脈で text を書き換え
telops.json            ← 確定版（誤変換補正・意訳・行頭NG調整 済み）
   │
   ▼ scripts/align_words.py で word 時刻にアンカー
aligned_telops.json + koetsu.json
```

### ステップA：機械的に候補を出す

```bash
python3 scripts/propose_telops.py \
  --words {work_dir}/words.json \
  --out   {work_dir}/proposed_telops.json \
  --vocab assets/vocabulary.json \
  --max-chars 17 \
  --min-pause 0.4
```

`proposed_telops.json` は `[{"text":..., "first":..., "last":..., "after":..., "_src_text":..., "_notes":[...]}, ...]` の形式。`_notes` に「フィラー含む」「字超」などのフラグが付く。

### ステップB：LLM が文脈で書き換える（このスキルの本体）

1. `proposed_telops.json` を全件読む
2. `references/context-corrections.md` を参照して **文脈依存の誤変換**を直す
   - `Claude Train` → `コルトレーン`（ジャズ文脈）
   - `リンパ種` → `リンパ腫`（医療文脈）
   - `黒のコード` → `Claude Code` など
3. **意訳して短縮**（「メンタルのアップダウン激しかった」→そのまま、ではなく「アップダウン激しかった」など）
4. 字数 ≤ 15・幅 ≤ 1900px に収める（超えるなら `\n` で2行化）
5. **行頭NG**（ん／っ／ー／ら／り／る／れ／ろ／よ／ね）を回避
6. **「ぐらい」「とか」**を数値・時間・人数の文脈で勝手に削らない
7. **一人称・文体** は投稿者の好み（テロップ草案 telops.json 段階で確定する）
8. **句読点は付けない**（縦リール）
9. `first` / `last` を **固有性の高い語**に書き換える（繰り返し語「これ」「ね」を避ける）
10. 書き換え後を `telops.json` として書き出す

### ステップC：word 時刻にアンカー

```bash
python3 scripts/align_words.py \
  --words  {work_dir}/words.json \
  --telops {work_dir}/telops.json \
  --work   {work_dir} \
  --stem   my_video
```

出力：`{work_dir}/aligned_telops.json` + `{work_dir}/koetsu.json`

### ステップD：オンセットスナップ（テロップ同期の最終補正・2026-07追加）

**Whisper の word 開始時刻は「ポーズ明けの語」で実発話より 0.2〜0.7 秒早く付く**
（直前語の引き延ばし・無音を語頭に含める癖。逆方向＝遅れはほぼ出ない）。
word アンカーのままだと声より先にテロップが出るので、音声エネルギーの
立ち上がりへ**遅らせる方向のみ**スナップする：

```bash
python3 scripts/onset_snap.py \
  --koetsu {work_dir}/koetsu.json \
  --media  <koetsu と同じタイムラインの音声/動画> \
  [--srt {work_dir}/{stem}.srt] [--check]
```

- カット後に焼くルート（render-horizontal-interview）ではカット後音声に対して実行（render 側が自動でやる）
- `--check` は書き換えずレポートのみ（qc-gate の sync 独立検証に使う）
- 実測（DHインタビュー 2026-07）: 49枚中21枚を +0.17〜+0.74s 補正、以後のズレ報告ゼロ
- 前方専用の理由: 早める補正は「はい」「そうですね」などテロップに載せない先行語へ誤吸着する

## 🚨 スマート字幕の鉄則（制作実例での確定運用）

1. **意味の切れ目で分割**（Whisper の区切りをそのまま使わない）。「でしょうか」が行頭に取り残される／「とんでも‖ない」「やって‖くれて」の分断を直す
2. **フィラー除去**：いやー／まあ／っていうか／言い淀みの重複。ただし **「なんか」「もう」は語り味として残す箇所もあり**
3. **話し言葉→書き言葉**：やっとる→やってる、入っておると→入ってると
4. **★文脈依存の誤変換を直す（核心）**：
   - `Claude Train` → `コルトレーン`（ジャズ文脈）
   - `リンパ種` → `リンパ腫`（医療文脈）
   - `SLS` → `SNS`（マーケ文脈）
   - `紙` → `神`（「ゴッドの紙＝神レベル」の文脈）
   - `黒のコード` → `Claude Code`
   - `クロードコード` → `Claude Code`（vocabulary.json でも辞書化済）
5. **「ぐらい」「とか」など曖昧表現を勝手に削らない**（特に医療数値・時間・人数）。「200ml ぐらい」→「200ml」と断定化するのは NG（制作実例での確定運用）
6. **句読点（、。）はテロップに付けない**（縦リール）。横講座は別ルール
7. **一人称・文体** は投稿者の好み（テロップ草案 telops.json 段階で確定する）

## word 時刻アンカー（first+last anchor 方式）

各テロップ `text` について：
- **first_anchor**: テロップ先頭の特徴的な語（例「200ml」「コルトレーン」「やばい」）
- **last_anchor**: テロップ末尾の語（「ました」「ください」「ね」など）

そのテロップが出現する `src_after` 秒以降から、words の連結文字列で `first_anchor` を探して開始時刻に、`last_anchor` を探して終了時刻にする。終了は `+0.18s` のテイル、次テロップ start - 0.05s でクランプ。

```python
# 概念コード（実装は scripts/align_words.py）
spans = []
for text, first, last, after in TELOPS:
    s = find_word_start(full_chars, first, after_time=after)
    e = find_word_end(full_chars, last, search_from=s)
    spans.append((s, e + 0.18, text))
```

## なぜ first+last の両方でアンカーするか

最初の実装（first だけ）では、Codex の独立検証で **「テロップが文頭の語より遅れて始まる」系統ミス**が多発した：

- 「本当に早かったよね」を `早かった` でアンカー → start 40.26s
- 実際の「本当に」は 39.28s から → **1秒遅れ**

これを直すため、両端でアンカーして開始は first・終了は last + テイル、にしている。

## 分割の優先順位

長すぎるテロップを2つに割るとき：

1. **文末**（です／ます／でした／ですよ／ますよ／ない 等）で切る
2. それが無ければ **接続助詞**（から／ので／くて／して 等）
3. それも無ければ **格助詞**（が／を／に／で／と 等）
4. それも無ければ単純な中央分割（ただしカタカナ・英数字の連続途中で切らない）

**連語（印象に残る／気に入る／身につける／お世話になる／目にする 等）はカードをまたがせない**。
字数が超えるなら2行1カードにして凌ぐ（カード自体は割らない）。

**カードの最小文字数は6文字。** 下回る断片（「はい」「先生自身」等）は隣接カードに吸収する。

行頭NGの判定は**先頭1文字の部分一致ではなく、実際の word 単位**で行うこと
（「もっと」「もちろん」「いくら」等、NG文字で始まる独立語を誤検出しない）。

詳細パターン・分割確定前の機械チェックリスト：`references/split-rules.md`

## 行頭NG

行頭に来ると違和感の出る文字を、分割位置の微調整で回避：
`ん っ ー ら り る れ ろ よ ね`

## 文字数・幅の閾値

| 状態 | しきい値 |
|---|---|
| 1行・快適 | ≤12文字 / ≤1750px |
| 1行・限界 | ≤15文字 / ≤1900px |
| FAIL（横長） | >15文字 / >1900px → 必ず2行化 |
| 表示秒数（cps） | ≤7字/秒 が快適・>12字/秒 は物理的に読めない（FAIL） |
| 畳み掛け（同 text 連続表示） | cps 検査から除外 |

詳細：`references/split-rules.md`

## 出力

- `{work_dir}/aligned_telops.json` — `[[start_src, end_src, text], ...]` 形式（src 時刻）
- `{work_dir}/koetsu.json` — `{version, stem, items: [{start, end, text}], ...}` 形式（render-* で使う）

## 関連

- 既知誤変換の辞書：`assets/vocabulary.sample.json`（購入者は `assets/vocabulary.json` を作って上書き）
- 詳細な分割ルール：`references/split-rules.md`
- 文脈補正の判断基準：`references/context-corrections.md`

## 同梱補助スクリプト

| スクリプト | 役割 | 呼び出し元 |
|---|---|---|
| `propose_telops.py` | words.json → 機械的な分割候補 | LLM 補正の前段 |
| `align_words.py` | telops.json → koetsu.json（first+last anchor）| 確定テロップを word 時刻に乗せる |
| `retime_telop.py` | koetsu.json を Needleman-Wunsch DP で発話実時刻に再スナップ（🎯音に合わせる本体） | telop-preview の `/api/snap` |
| `snap_telop_timing.py` | VAD ベースのタイミング吸着（retime の旧経路・フォールバック用）。START_OFFSET=0.18 は「発話の少し後に出す」流儀（校閲者好み）| （現在は補助） |
| `onset_snap.py` | **エネルギーオンセットへ前方専用スナップ**（「発話に遅れない」流儀・インタビュー系の正）。`--check` で独立検証にも使う | render-horizontal-interview / qc |
| `diff_learner.py` | proposed_telops と koetsu の差分から辞書学習候補を抽出（💡 直すほど賢くなる本体）| telop-preview の `/api/save` 強化 |

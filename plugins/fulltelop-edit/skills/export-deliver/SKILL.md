---
name: export-deliver
description: koetsu.json（time-aligned caption）から SRT／FCPXML／カバー画像PNG を出力する。MP4焼き込みは render-* スキルが担うが、SRT（YouTube字幕投稿）／FCPXML（Final Cut Pro 読み込み）／PNG カバー（Instagram用）はこのスキルがまとめて出口を提供。SRT／FCPXML／字幕ファイル／カバー画像で発火。
---

# export-deliver — SRT / FCPXML / カバー の出口

## やること

`koetsu.json`（`{items: [{start, end, text}], ...}` の中間表現）から、編集ソフト別の出力を作る：

| 出力 | 用途 |
|---|---|
| `*.srt` | YouTube 字幕投稿・Premiere Pro 読み込み・CapCut 読み込み |
| `*.fcpxml` | Final Cut Pro 読み込み（Vlog／通常リール向け） |
| `*_cover.png` | Instagram用カバー画像（1080×1920・冒頭フレーム自動） |

MP4 焼き込みは `render-vertical-reel` / `render-horizontal-lecture` の責務（出口を統一しないのは、焼き込みは編集工程と密結合のため）。

## SRT 出力

```bash
python3 scripts/to_srt.py koetsu.json --out output.srt
```

特徴:
- UTF-8 BOM 無し
- 改行コード LF
- ファイル名 ASCII 強制（`{stem}.srt`、stem が日本語なら `output.srt` に fallback）
- 中身のテキストは日本語OK
- YouTube／Premiere Pro／DaVinci Resolve／CapCut で互換

## FCPXML 出力

```bash
python3 scripts/to_fcpxml.py koetsu.json --video original.mov --out output.fcpxml
```

特徴:
- FCPXML version 1.10 / 1.14 両対応（オプション）
- 各テロップは Title 要素（NotoSansJP-ExtraBold 31pt 白＋ドロップシャドウ）
- タイムコードは `100/3000s`（30fps）
- セミナー／講座は焼き込みmp4のみ推奨（FCPXMLは出さない＝制作実例での運用）

## カバー画像

```bash
python3 scripts/to_cover.py --video output.mp4 --frame 2.0 --text "やばいAIで1日でアプリ" --out cover.png
```

仕様:
- 1080×1920（縦9:16）
- 冒頭2秒地点のフレームを使う（`reel-cover` スキルの仕様）
- 中央に白文字1行（ドロップシャドウ）
- 自動顔選定はしない（制作実例での確定運用）

## なぜ FCPXML より SRT を推奨するか

- SRT は Premiere Pro / Final Cut / DaVinci / CapCut / YouTube 全部で読める
- FCPXML は FCP 専用＋バージョン互換問題が出る
- 制作実例での運用は「白テロップは FCPXML、黄色焼き込みは MP4」
- 購入者の編集環境はバラバラ＝ SRT を出口の本命にする

## ASCII fallback ファイル名

Windows での文字化けと、Codex の sandbox 制約を避けるため、出力ファイル名は ASCII を既定にする：

```
output.srt         # default
output.fcpxml      # default
output_cover.png   # default
```

`--japanese-filename` を指定したら spec.stem を使う（自己責任）。

## 統一インターフェース

`koetsu.json` を中間表現として全形式が読む。形式が増えても出口を `export-deliver` に集約：

```
koetsu.json
   ├── to_srt.py     → output.srt
   ├── to_fcpxml.py  → output.fcpxml
   └── to_cover.py   → output_cover.png
```

## v2 で対応予定

- DaVinci Resolve .drp テンプレ出力
- Premiere .prproj 直接出力（複雑なので保留中）
- カラオケ風 word-level karaoke timing SRT

# fulltelop-edit — Codex / Claude Code 共通ルート指示

このディレクトリは動画編集パック fulltelop-edit のスキル群です。Codex CLI と Claude Code の両方から呼び出せます。

## あなた（AI）への指示

ユーザーから動画ファイル（`.mov` / `.mp4` / `.m4a`）のパスとともに「テロップ入れて」「字幕付けて」「インタビュー編集」「リール作って」などの依頼が来たら、以下の流れで進めてください。

1. 最初にユーザーと対話して確定する: 出力の種類（横インタビュー焼き込み／縦リール焼き込み／SRT・FCPXMLのみ）、カット指定の有無、見出し帯の有無
2. `transcribe-words` で word 単位の文字起こし（words.json）
3. `jetcut-design` で無音・フィラー・言い直しのカット設計
4. `smart-caption` で文脈補正済みのスマート字幕を生成
5. `audio-master` で整音（-14LUFS）
6. `telop-preview` でユーザーに目視・編集してもらう（必要時）
7. `qc-gate` を必ず通す（FAIL が残ったまま納品しない）
8. 出口: `render-horizontal-interview`（横インタビュー）／ `render-vertical-reel`（縦リール）／ `export-deliver`（SRT・FCPXML・カバー）。見出し帯は `heading-overlay`

## スキル一覧と発火タイミング

| スキル | 発火条件 |
|---|---|
| `transcribe-words` | 文字起こしが無いとき最初に |
| `jetcut-design` | 無音／フィラー／言い直し／DROP範囲 |
| `smart-caption` | 字幕の意味の切れ目／文脈誤変換補正／word時刻アンカー |
| `audio-master` | 整音（無音／クリップ／-14LUFS） |
| `telop-preview` | 字幕を目視・編集したいとき（http://localhost:5050） |
| `qc-gate` | 焼く前・書き出す前に必ず |
| `render-horizontal-interview` | 横インタビュー（話者色分けテロップ）のとき |
| `render-vertical-reel` | 縦リール（Instagram / TikTok）のとき |
| `heading-overlay` | 左上見出し帯を付けたいとき |
| `export-deliver` | SRT / FCPXML / カバー画像で出口を分ける |

## Codex で使う際の注意

- Codex のデフォルト sandbox は `workspace-write` です。ffmpeg や Whisper を動かすため、起動時に `codex --sandbox workspace-write` を明示してください
- ネットワークが必要なツール（`pip install` 等）は事前にインストールしておく（runtime では実行しない設計）
- `~/Downloads/` など workspace 外には書き込めません。出力先はプロジェクト内ディレクトリを使ってください
- Codex には Claude Code の「Skillツール」が無いため、スキル間の連携は「同梱スキルの SKILL.md を直接読み込む」方式で動きます
- スクリプトはフォント等を `skills/` の親ディレクトリの `assets/` から探します。`install-codex-fulltelop.sh` でインストールすると `~/.agents/skills/` と `~/.agents/assets/` に正しく配置されます

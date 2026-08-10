# fulltelop-edit — 動画編集パック

インタビュー動画（横16:9）と縦リール（Instagram / TikTok）の編集ワークフローをClaude Codeのスキルとして呼べるパックです。
fulltelop-pack からインタビュー・リール制作に必要なスキルだけを抜き出した構成です。

## 収録スキル

| スキル | 役割 |
|---|---|
| `transcribe-words` | word単位タイムスタンプ付き文字起こし（Whisper） |
| `jetcut-design` | 無音・フィラー・言い直しの物理カット設計 |
| `smart-caption` | 文脈補正＋意味の切れ目で分割するスマート字幕 |
| `audio-master` | 整音（loudnorm 2パスで -14LUFS） |
| `telop-preview` | 字幕のローカルWeb UI編集（http://localhost:5050） |
| `qc-gate` | 納品前の品質改札（caption / sync / audio / render） |
| `render-horizontal-interview` | 横インタビュー動画の話者色分けテロップ焼き込み |
| `render-vertical-reel` | 縦リール完結型（2160×3840・白テロップ＋ドロップシャドウ）焼き込み |
| `heading-overlay` | 左上見出し帯（紺グラデ＋白文字）の焼き込み |
| `export-deliver` | SRT／FCPXML／カバー画像の出力（telop-preview の出力ボタンからも使用） |

## 基本フロー

```
動画ファイル
  → transcribe-words（words.json）
  → jetcut-design（カット設計）
  → smart-caption（字幕生成）
  → audio-master（整音）
  → telop-preview（目視・編集）
  → qc-gate（品質チェック）
  → render-horizontal-interview または render-vertical-reel（焼き込みMP4＋SRT）
```

## インストール

```
/plugin marketplace add tomosuke-chiba/kou-claude-plugins
/plugin install fulltelop-edit@kou-plugins
```

初回は ffmpeg / Python / Whisper モデルの導入が必要です。詳細は [docs/install-requirements.md](docs/install-requirements.md) を参照してください。

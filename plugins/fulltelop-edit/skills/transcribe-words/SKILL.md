---
name: transcribe-words
description: 動画／音声ファイルを word 単位のタイムスタンプ付きで文字起こしする。Mac は mlx_whisper、Windows は faster-whisper にフォールバック。出力は spec.json で指定された work_dir に words.json として保存。テロップ化／字幕化／文字起こし／Whisper／word timestamp で発火。
---

# transcribe-words — word 単位 文字起こし

spec-router の後に走る最初のスキル。後段の smart-caption と jetcut-design がこの出力を使います。

## やること

1. `spec.json` を読んで `src` と `work_dir` を取得
2. 環境を判定して mlx_whisper か faster-whisper を選ぶ
3. 16kHz モノラル WAV に変換して文字起こし
4. word 単位 JSON を `{work_dir}/words.json` に保存

## 実行

```bash
# spec.json から SRC と WORK を取得
SRC=$(python3 -c "import json; print(json.load(open('spec.json'))['src'])")
WORK=$(python3 -c "import json; print(json.load(open('spec.json'))['work_dir'])")

# 16kHz mono に変換（必要時）
ffmpeg -y -hide_banner -loglevel error -i "$SRC" -ac 1 -ar 16000 "$WORK/audio16k.wav"

# 文字起こし（Mac / Linux で mlx_whisper があればそれを使う）
python3 scripts/transcribe.py "$WORK/audio16k.wav" --out "$WORK/words.json"
```

## 出力フォーマット（words.json）

```json
{
  "engine": "mlx_whisper",
  "model": "large-v3-turbo",
  "language": "ja",
  "segments": [
    {
      "start": 0.0,
      "end": 4.32,
      "text": "やばい、これ見て",
      "words": [
        {"start": 1.44, "end": 1.86, "word": "やばい"},
        {"start": 2.0,  "end": 2.20, "word": "これ"}
      ]
    }
  ]
}
```

## 環境フォールバック

- **Mac (Apple Silicon)**: `pip install mlx-whisper` → mlx_whisper を直接呼ぶ（最速・高精度）
- **Windows / Linux (CUDA)**: `pip install faster-whisper` → CTranslate2 経由
- **CPUのみ**: faster-whisper でも CPU で動くが遅い（実時間の 2〜4倍）

詳細：`docs/install-requirements.md`

## 語彙ガード

文字起こし直後に `assets/vocabulary.sample.json` の corrections を当てて固有名詞の Whisper 誤変換を補正します（例：「クロード」→「Claude」「ジェミニ」→「Gemini」）。実際の補正は `smart-caption` が文脈判断で行うため、ここでは辞書ベースの自動補正のみ。

## エラー時

- `mlx_whisper not found` → faster-whisper にフォールバック
- `model download failed` → ネットワーク確認＋初回は数 GB のダウンロードが走ることをユーザーに告知
- Codex で `--sandbox workspace-write` 起動していない場合は WAV 書き出しでブロック → ユーザーに「--sandbox を緩めて再起動」を依頼

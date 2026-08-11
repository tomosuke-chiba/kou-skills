# インストール詳細（OS別）

## macOS (Apple Silicon 推奨)

```bash
# Homebrew が無ければ先に（Homebrew公式のインストーラ）
# ⚠️ リモートスクリプトの直接実行になるため、気になる場合は一度ファイルに保存して
#    中身を確認してから実行する: curl -fsSL <URL> -o install.sh → 内容確認 → bash install.sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 必須
brew install ffmpeg python@3.11

# Python ライブラリ
pip3 install pillow numpy mlx-whisper
```

## Linux (Ubuntu / Debian)

```bash
sudo apt update
sudo apt install ffmpeg python3 python3-pip

# Python ライブラリ
pip3 install pillow numpy faster-whisper
```

CUDA GPU を使うなら：

```bash
pip3 install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

## Windows (PowerShell)

```powershell
# Chocolatey で
choco install ffmpeg python

# または winget で
winget install ffmpeg
winget install Python.Python.3.11

# Python ライブラリ
pip install pillow numpy faster-whisper
```

## フォント

`assets/fonts/NotoSansJP-ExtraBold.ttf` がパッケージに同梱されています。
スクリプトは以下の順で検索：

1. `<plugin>/assets/fonts/NotoSansJP-ExtraBold.ttf`
2. `~/Library/Fonts/NotoSansJP-ExtraBold.ttf` (Mac)
3. `/Library/Fonts/NotoSansJP-ExtraBold.ttf` (Mac)
4. `/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc` (Linux)
5. `C:/Windows/Fonts/NotoSansJP-ExtraBold.ttf` (Win)

見つからなければ「インストールするかフォントファイルを置いてください」とエラー。

### システムにインストール

- **Mac**: フォントファイルをダブルクリック → 「インストール」
- **Linux**: `cp NotoSansJP-ExtraBold.ttf ~/.fonts/ && fc-cache -fv`
- **Windows**: ダブルクリック → 「インストール」

## Whisper エンジン比較

| エンジン | 環境 | 速度 | 精度 | インストール |
|---|---|---|---|---|
| mlx_whisper | Mac Apple Silicon | ◎（最速） | ◎ | `pip install mlx-whisper` |
| faster-whisper | Mac Intel / Win / Linux | ○（CPU 2-4倍時間） | ◎ | `pip install faster-whisper` |
| openai-whisper | 全般 | △（遅い） | ◎ | `pip install openai-whisper` |

このパッケージは mlx → faster-whisper の順でフォールバックします。
両方無いとエラー（CPU only でも faster-whisper を入れてください）。

## 動作確認

```bash
# ffmpeg
ffmpeg -version | head -1

# Python
python3 -c "import PIL, numpy; print('PIL', PIL.__version__, 'numpy', numpy.__version__)"

# Whisper（どちらか）
python3 -c "import mlx_whisper; print('mlx ok')"
python3 -c "import faster_whisper; print('faster ok')"
```

全部通れば準備完了。

#!/bin/bash
# fulltelop-edit スキルを Codex 用にインストールする
# - スキルのコピー先: ~/.agents/skills（Codex公式のユーザーグローバル置き場）
# - アセット（フォント・辞書）のコピー先: ~/.agents/assets
#   ※各スクリプトは skills/ の親ディレクトリの assets/ を参照するため、この配置が必須
# - ~/.codex/skills が存在する環境では、そこへもシムリンクを張る
# - 既定では既存の同名スキルは上書きしない（skip）
# - --update を付けると、既存スキル（実体ディレクトリのみ）をリポの最新版で置き換える
#   ※シムリンクは利用者側の独自運用とみなし、--update でも触らない
set -euo pipefail

UPDATE=0
if [ "${1:-}" = "--update" ]; then
  UPDATE=1
fi

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$REPO_DIR/plugins/fulltelop-edit"
SRC="$PLUGIN_DIR/skills"
AGENTS_DIR="$HOME/.agents/skills"
ASSETS_DIR="$HOME/.agents/assets"
CODEX_DIR="$HOME/.codex/skills"

mkdir -p "$AGENTS_DIR" "$ASSETS_DIR/fonts"

# アセット（フォント・辞書サンプル）: 無ければコピー、--update なら更新
for f in "$PLUGIN_DIR/assets/fonts/NotoSansJP-ExtraBold.ttf" "$PLUGIN_DIR/assets/fonts/LICENSE_OFL.txt"; do
  dst="$ASSETS_DIR/fonts/$(basename "$f")"
  if [ ! -e "$dst" ] || [ "$UPDATE" -eq 1 ]; then
    cp "$f" "$dst"
    echo "asset:     $dst"
  fi
done
if [ ! -e "$ASSETS_DIR/vocabulary.sample.json" ] || [ "$UPDATE" -eq 1 ]; then
  cp "$PLUGIN_DIR/assets/vocabulary.sample.json" "$ASSETS_DIR/vocabulary.sample.json"
  echo "asset:     $ASSETS_DIR/vocabulary.sample.json"
fi
# vocabulary.json（利用者の育てた辞書）はユーザー資産なので一切触らない

for skill in "$SRC"/*/; do
  name="$(basename "$skill")"

  if [ -L "$AGENTS_DIR/$name" ]; then
    echo "skip:      $AGENTS_DIR/$name（シムリンクのため触りません）"
  elif [ -e "$AGENTS_DIR/$name" ]; then
    if [ "$UPDATE" -eq 1 ]; then
      rm -rf "$AGENTS_DIR/$name"
      cp -R "$skill" "$AGENTS_DIR/$name"
      echo "updated:   $AGENTS_DIR/$name"
    else
      echo "skip:      $AGENTS_DIR/$name（既存。更新するには --update）"
    fi
  else
    cp -R "$skill" "$AGENTS_DIR/$name"
    echo "installed: $AGENTS_DIR/$name"
  fi

  if [ -d "$CODEX_DIR" ]; then
    if [ -e "$CODEX_DIR/$name" ] || [ -L "$CODEX_DIR/$name" ]; then
      echo "skip:      $CODEX_DIR/$name（既存）"
    else
      ln -s "$AGENTS_DIR/$name" "$CODEX_DIR/$name"
      echo "linked:    $CODEX_DIR/$name -> $AGENTS_DIR/$name"
    fi
  fi
done

echo ""
echo "完了。ffmpeg / Python / Whisper が未導入なら plugins/fulltelop-edit/docs/install-requirements.md を参照してください。"
echo "新しい Codex セッションを 'codex --sandbox workspace-write' で起動し、動画パス＋「テロップ入れて」等で試してください。"

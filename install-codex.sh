#!/bin/bash
# goal-align スキル7本を Codex 用にインストールする
# - コピー先: ~/.agents/skills（Codex公式のユーザーグローバル置き場）
# - ~/.codex/skills が存在する環境では、そこへもシムリンクを張る
# - 既存の同名スキルは上書きしない（skip）
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$REPO_DIR/plugins/goal-align/skills"
AGENTS_DIR="$HOME/.agents/skills"
CODEX_DIR="$HOME/.codex/skills"

mkdir -p "$AGENTS_DIR"

for skill in "$SRC"/*/; do
  name="$(basename "$skill")"

  if [ -e "$AGENTS_DIR/$name" ]; then
    echo "skip:      $AGENTS_DIR/$name（既存のため上書きしません）"
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
echo "完了。新しい Codex セッションで \$align-dod-solve（または /skills で一覧）を試してください。"

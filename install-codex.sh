#!/bin/bash
# goal-align スキルを Codex 用にインストールする
# - コピー先: ~/.agents/skills（Codex公式のユーザーグローバル置き場）
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
SRC="$REPO_DIR/plugins/goal-align/skills"
AGENTS_DIR="$HOME/.agents/skills"
CODEX_DIR="$HOME/.codex/skills"

mkdir -p "$AGENTS_DIR"

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
echo "完了。新しい Codex セッションで \$grill-dod-solution-research 等を試してください。"

# kou-plugins — goal-align

## できること

- 認識合わせ（`grill-me`）→完了定義（`dod`）→木下式ソリューション展開（`kinoshita-solution`）を1本のオーケストレータ `align-dod-solve` で回せます。
- grill-me で作った共通認識の地図を、重複質問なしで dod の4要素（目的・目標・答えの条件・検証方法）に自動変換します。
- 「認識ズレてる気がするから最初から詰めて」のような曖昧な依頼でも、要件定義のズレを構造化して止められます。

## コアメンバー向けインストール手順

```
/plugin marketplace add tomosuke-chiba/kou-claude-plugins
/plugin install goal-align@kou-plugins
```

## 基本フロー

```
grill-me（認識合わせ・地図作成）
     ↓
  地図→4要素変換
     ↓
dod（完了定義を確定・ここで一旦停止）
     ↓（ユーザーが明示指示した場合のみ）
kinoshita-solution（4案展開）
```

## 更新方法

- 正本は `~/.claude/skills` 側（一部は `recruit/skills` 配下の実体からのシムリンク）です。このリポは配布用のコピーであり、直接編集しないでください。
- スキルを更新した場合は、正本側を更新したうえで本リポの `plugins/goal-align/skills/` 配下へコピーし直し、コミット・pushしてください。

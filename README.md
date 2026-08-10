# kou-plugins

KOUコアメンバー向けのClaude Codeプラグイン集。

| プラグイン | 内容 |
|---|---|
| `goal-align` | 認識合わせ→完了定義→ソリューション探索のスキルパック |
| `fulltelop-edit` | 動画編集パック（文字起こし→カット→字幕→整音→横インタビュー／縦リール焼き込み。詳細は [plugins/fulltelop-edit/README.md](plugins/fulltelop-edit/README.md)） |

インストール（共通）:

```
/plugin marketplace add tomosuke-chiba/kou-claude-plugins
/plugin install goal-align@kou-plugins
/plugin install fulltelop-edit@kou-plugins
```

※ fulltelop-edit は ffmpeg / Python / Whisper の導入が別途必要です（[plugins/fulltelop-edit/docs/install-requirements.md](plugins/fulltelop-edit/docs/install-requirements.md)）。

---

# goal-align

## できること

- 認識合わせ（`grill-me`）→完了定義（`dod`）→ソリューション探索（`solution-research`）を1本のオーケストレータ `grill-dod-solution-research` で回せます（旧名 `align-dod-solve` から改名）。
- grill-me で作った共通認識の地図を、重複質問なしで dod の4要素（目的・目標・答えの条件・検証方法）に自動変換します。
- 「認識ズレてる気がするから最初から詰めて」のような曖昧な依頼でも、要件定義のズレを構造化して止められます。
- `solution-research` は思考法の型レジストリ（26型＋人物ペルソナ）から手法を選び、DoDの答えの条件から逆算して解決策案と推奨を出します。木下式の固定4案が欲しいときは従来どおり `kinoshita-solution` を単体起動できます。

## コアメンバー向けインストール手順

> このリポは public です。GitHub の招待や認証設定は不要で、誰でもそのままインストールできます。

### A. ターミナル版 Claude Code の人

```
/plugin marketplace add tomosuke-chiba/kou-claude-plugins
/plugin install goal-align@kou-plugins
```

### B. デスクトップアプリの人（/plugin が使えない環境）

デスクトップアプリでは `/plugin` コマンドは使えません。次のどちらかで導入します。

**B-1. いちばん簡単: 下のプロンプトを Claude にそのまま貼る**

```
次のプラグインを導入してください。
1. ~/.claude/settings.json（なければ作成）に以下をマージする（既存の設定は消さない）:
{
  "extraKnownMarketplaces": {
    "kou-plugins": {
      "source": { "source": "github", "repo": "tomosuke-chiba/kou-claude-plugins" }
    }
  },
  "enabledPlugins": ["goal-align@kou-plugins"]
}
2. マージ後、settings.json が有効なJSONであることを確認して報告してください。
3. 反映にはアプリの再起動（新しいセッション）が必要な旨も教えてください。
```

**B-2. アプリのプラグインブラウザから**

デスクトップアプリのプラグイン画面（Plugin Browser）でこのマーケットプレイスを追加し、`goal-align` をインストールします。

導入後は新しいチャットで `/grill-dod-solution-research` が使えれば成功です。

### C. Codex の人

Codex は同じ SKILL.md 形式に対応しています（配置先が違うだけ）。ターミナルで:

```bash
git clone https://github.com/tomosuke-chiba/kou-claude-plugins.git
bash kou-claude-plugins/install-codex.sh
```

スクリプトが10スキルを `~/.agents/skills`（Codex公式の置き場）へコピーし、`~/.codex/skills` がある環境にはシムリンクも張ります。既存の同名スキルは上書きしません。

動画編集パック fulltelop-edit を Codex で使う場合は、こちらを実行します（フォント等のアセットも `~/.agents/assets` へ配置します）:

```bash
bash kou-claude-plugins/install-codex-fulltelop.sh
```

ターミナルを使いたくない場合は、次のプロンプトを Codex にそのまま貼ってもOKです:

```
https://github.com/tomosuke-chiba/kou-claude-plugins を一時ディレクトリに git clone し、
同梱の install-codex.sh の内容を確認してから実行して、結果を報告してください。
```

導入後は新しい Codex セッションで `$grill-dod-solution-research` と入力（または自動発動）で使えます。
Codex には Claude Code の「Skillツール」が無いため、スキル間の連携は「同梱スキルの SKILL.md を直接読み込む」方式で動きます（grill-dod-solution-research 内に読み替えルールを記載済み）。

## 同梱スキル（v0.2.0で10本）

> `align-dod-solve` は `grill-dod-solution-research` に改名しました。

| スキル | 役割 |
|---|---|
| grill-dod-solution-research | オーケストレータ（grill-me→dod→solution-research。旧名 align-dod-solve） |
| grill-me / teach-back | 認識合わせ・理解確認 |
| dod | 木下式・完了の定義 |
| solution-research | 思考法の型レジストリ（26型＋人物ペルソナ）でソリューション案を発想・推奨 |
| kinoshita-solution / chakugan-ho / kujo-ho | ソリューション4案展開（木下式固定構成。単体起動も可） |
| slide-message-architect | 原稿→スライド枚数・1枚1メッセージ設計表 |
| blue-gradient-slide-generator | KOU青系ビジュアルの16:9スライドPNG生成（生成エンジン=Codexのimagegen。Claude Codeから使うと生成部分をcodex execへ委譲） |

## 既存インストール者のアップデート方法

- **Claude Code（ターミナル）**: `/plugin marketplace update kou-plugins` → プラグインを更新
- **デスクトップアプリ**: 次のプロンプトを Claude にそのまま貼る:

```
Claude Codeプラグイン「goal-align@kou-plugins」を最新版にアップデートしてください。

1. ~/.claude/plugins/marketplaces/kou-plugins ディレクトリが存在するか確認する
   （なければ ~/.claude/plugins/known_marketplaces.json から kou-plugins の
   installLocation を調べて、そのディレクトリを対象にする）
2. そのディレクトリで git pull を実行する
3. 更新後、plugins/goal-align/.claude-plugin/plugin.json の version を表示して
   報告する（0.2.0 以上になっていれば成功）
4. 見つからない・失敗した場合は、エラー内容だけ報告して他の方法を勝手に試さない
5. 成功したら「アプリを再起動して新しいチャットから新スキルが使えます」と案内する
```

- **Codex**: `git -C kou-claude-plugins pull` → `bash kou-claude-plugins/install-codex.sh --update`（既存スキルも最新化。シムリンク運用のものは触りません）

## 基本フロー

```
grill-me（認識合わせ・地図作成）
     ↓
  地図→4要素変換
     ↓
dod（完了定義を確定・ここで一旦停止）
     ↓（ユーザーが明示指示した場合のみ）
solution-research（思考法の型で解決策を探索・推奨）
     ※木下式の固定4案が欲しいときは kinoshita-solution を単体起動
```

## 更新方法

- 正本は `~/.claude/skills` 側（一部は `recruit/skills` 配下の実体からのシムリンク）です。このリポは配布用のコピーであり、直接編集しないでください。
- スキルを更新した場合は、正本側を更新したうえで本リポの `plugins/goal-align/skills/` 配下へコピーし直し、コミット・pushしてください。

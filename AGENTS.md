# KOU Skillsリポジトリ固有ルール

## Skill追加時の絶対条件

- `plugins/*/skills/<skill-name>/SKILL.md`を追加するときは、同じ変更で`docs/images/skills/<NN>-<skill-name>.png`を必ず1枚追加する。
- 専用画像は`$blue-gradient-slide-generator`で生成し、1600×900以上の16:9、KOU青系トーン、文字台帳、ヘッダー比率14–16%、最終目視QAを満たす。
- `<NN>`には既存画像を変更・改名せず、次の未使用2桁番号を使う。
- READMEの対象Skill説明直下に専用画像を掲載する。
- Skillの改名・削除時は、対応画像とREADME参照も同じ変更で整合させる。
- `node mcp-server/build-skills.mjs`と`node mcp-server/test.mjs`を実行し、1 Skill＝専用PNGちょうど1枚のゲートを含む全テストが通るまでcommit・push・deployしない。GitHub Actionsの`Skill image gate`も必須検査として扱う。

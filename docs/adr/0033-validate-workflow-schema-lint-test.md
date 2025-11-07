## ADR-033: Validate Workflow 段階的ロールアウト（schema 必須・lint/test 警告化）

- 日付: 2025-11-06
- ステータス: Accepted
- 影響範囲: GitHub Actions CI, README, requirements-dev
- 関連ADR: ADR-030, ADR-032

### Context

ADR-030 で thresholds.json バリデータ CI を導入したが、品質ゲートは schema / fixtures のみに限定されていた。Phase 5 完了後は CLI / Dashboard / Lambda のコード量が増え、追加の lint / test 監視が必要になった一方、既存コードは Ruff / Black / Pytest が未整備であり、即時必須化するとすべての PR が失敗するリスクがあった。

### Decision

GitHub Actions `validate.yml` を拡張し、以下の段階的ロールアウトを採用する。

- schema / fixtures 検証は必須ジョブとして維持し、thresholds 品質を継続保証
- lint / unit-tests ジョブを追加しつつ `continue-on-error: true` に設定し、失敗を警告として可視化
- README に CI バッジを追加し、ワークフロー結果をリポジトリトップで確認可能にする

### Rationale

- **安全性優先**: thresholds.json の回帰防止を最優先しつつ、追加チェックを段階導入することで Main ブランチ保護を維持
- **負債の可視化**: Ruff/Black/pytest の失敗を PR 上で確認でき、Phase 6 での是正範囲を定量化
- **運用継続**: 既存コードに大規模フォーマット変更を強制せず、CI 導入を MVP として完了できる

### Implementation

1. `.github/workflows/validate.yml`
   - トリガー: `push`（main / feature/**）と `pull_request`（opened / synchronize / reopened）を対象
   - lint ジョブ: Python 3.10 / 3.11 マトリクス、Ruff (`--output-format=github`) と Black を実行、`continue-on-error: true`
   - unit-tests ジョブ: Python 3.10 / 3.11 マトリクスで `pytest -q --maxfail=1 --disable-warnings` を実行、`continue-on-error: true`
   - schema / fixtures ジョブ: 3.11 固定で `scripts/validate.py` を実行し、正常/異常フィクスチャ検証を必須化
   - すべてのジョブで `actions/cache@v4` による pip キャッシュを導入
2. `requirements-dev.txt`: Ruff 0.4.7 / Black 24.4.2 をピン留めし、CI とローカルで同一ツールを利用可能に
3. `README.md`: CI バッジを `https://github.com/tfujimoto913/thf_motion_scan/actions/workflows/validate.yml/badge.svg` に更新

### Consequences

**メリット**
- schema / fixtures は引き続き回帰ブロックを担保
- lint / test の失敗内容が PR 上で可視化され、技術的負債の解消優先度を判断しやすい
- CI 成果が README バッジで共有され、チーム外にも状況を伝達できる

**デメリット**
- lint / test が赤のままでも CI 全体は成功となるため、初見では違反を見落とす可能性がある
- 大規模フォーマット適用や PYTHONPATH 再設計といった抜本的対策は Phase 6 へ持ち越し

### Follow-up

- Phase 6 で Ruff / Black / Pytest の必須化に向けたコード整備（unused import 解消、Black 適用、PYTHONPATH 設定）を行う
- pre-commit に Ruff / Black を統合し、ローカル段階での逸脱抑止を検討
- lint / test ジョブの `continue-on-error` を解除するタイミングを、Phase 6 の成果レビュー後に決定

### References

- 実装: `.github/workflows/validate.yml`, `README.md`, `requirements-dev.txt`
- コミット: `feat: CI with staged rollout (schema/fixtures required, lint/test warning-only)`
- ブランチ: `feature/phase5-complete`

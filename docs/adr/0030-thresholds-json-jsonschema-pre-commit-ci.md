## ADR-030: thresholds.json バリデータ自動化（jsonschema + pre-commit + CI）
- 日付: 2025-11-04
- 決定者: Human + Codex
- 決定: `thresholds.json` の検証を Python + jsonschema ベースの単一スクリプトに集約し、pre-commit フックと GitHub Actions で必須化。旧 `scripts/validate-thresholds.py` / `.github/workflows/validate-thresholds.yml` を廃止し、新チェーンへ統合
- 理由:
  - **ロジック一元化**: スキーマ検証とビジネスルールチェックを1実装に統合し、重複管理を解消
  - **早期検知**: pre-commit でローカル段階から不正 JSON をブロックし、レビュー手戻りを削減
  - **回帰防止**: 正常/異常フィクスチャを自動検証に組み込み、既知の失敗ケース再発を防止
  - **依存明示**: `requirements-dev.txt` に jsonschema / pre-commit を追加し、開発・CI のセットアップ差異を解消
- 実施内容:
  1. **新バリデータ** (`scripts/validate.py`)
     - Draft7Validator + カスタム検証（test_code重複、キー不一致、band分類重複、`range_inc` の下限≦上限チェック）を実装
     - 複数ファイル/ディレクトリ検証、quiet モード、スキーマパス指定に対応
     - 依存未導入時は `pip install -r requirements-dev.txt` を案内
  2. **開発体験整備**
     - `requirements-dev.txt` に jsonschema / pre-commit を追加
     - `.pre-commit-config.yaml` で `config/thresholds.json` 変更時に `python scripts/validate.py --quiet` を実行
     - README に手動検証手順、フィクスチャ期待値、フック無効化方法を追記
  3. **CI リプレイス**
     - `.github/workflows/validate.yml` を新設し、dev依存インストール → 本番ファイル検証 → 正常フィクスチャ成功 → 異常フィクスチャ失敗（exit=1）を確認
     - 旧 `.github/workflows/validate-thresholds.yml` を削除
  4. **フィクスチャ整備**
     - `tests/fixtures/thresholds/valid/` に 3 ケース（最小構成・複数テスト・hysteresis）
     - `tests/fixtures/thresholds/invalid/` に 10 ケース（op/value不整合、band重複、schema_version書式不正 等）
  5. **レガシー撤去**
     - `scripts/validate-thresholds.py` を削除し、新スクリプトへ機能を統合
- 影響:
  - **依存**: `requirements-dev.txt` の導入（`pip install -r requirements-dev.txt`）が CI / ローカル前提に
  - **開発プロセス**: pre-commit のインストール・実行が推奨（緊急時は `SKIP=validate-thresholds` を利用）
  - **運用ドキュメント**: README / Notion ハンドオーバーに検証フローと対処手順を追記
- トレードオフ:
  - **メリット**: 失敗ログの可読性向上、複数ファイル同時検証、フィクスチャで網羅性確保
  - **デメリット**: pre-commit 導入の初期作業、CI ステップ増加（invalid フィクスチャ検証）
- 今後の展開:
  - `schema/thresholds.schema.json` のバージョンエイリアス提供（例: `thresholds.schema.v1.json`）
  - `scripts/diff-thresholds.py` と連携した変更種別レポート（PR コメント自動化等）の検討
  - Data Science 向けに複数ファイルバッチ検証・レポート生成を行う軽量 CLI/GUI の検討
- 参照:
  - 新規/更新ファイル: `.pre-commit-config.yaml`, `.github/workflows/validate.yml`, `requirements-dev.txt`, `scripts/validate.py`, `tests/fixtures/thresholds/valid/*`, `tests/fixtures/thresholds/invalid/*`, `README.md`

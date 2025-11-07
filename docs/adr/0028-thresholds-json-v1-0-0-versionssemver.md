## ADR-028: thresholds.json v1.0.0 初版エクスポート（Versions付与・SemVer管理基盤）
- 日付: 2025-11-02
- 決定者: Human + Claude Code
- 決定: 評価ルールの閾値設定を外部化し、バージョン情報（rules_version, normalization_version, artifact_sha）を付与した `thresholds.json` を初版リリース。JSON Schema検証、diff比較、CI配線を実装し、rep判定・dual scoring展開に備えた変更追跡基盤を確立
- 理由:
  - **機械可読なバージョン管理**: 現状コード内ハードコードの閾値をJSON外部化し、SemVerで変更を追跡可能に
  - **result.json整合性**: 評価結果に含まれる `versions` キーと閾値設定のバージョンを一致させ、トレーサビリティ確保
  - **rep判定・dual scoring対応準備**: 複数バージョンの閾値を比較評価するための基盤整備
  - **変更影響の可視化**: 閾値変更時のMAJOR/MINOR/PATCH分類により、後方互換性破壊を事前検知
  - **第三者メンテナンス可能性**: スキーマ検証・diff・READMEにより、Data Science Team単独でも閾値更新可能
- 実施内容:
  1. **JSON Schema定義** (`schema/thresholds.schema.json`):
     - Draft-07準拠、5.8KB
     - `versions`, `metadata`, `tests` の3トップレベルキー
     - `TestThreshold` 型: `code`, `thresholds` (primary.bands, hysteresis), `features`, `refs`, `notes`
     - `Band` 型: `name` (pass/border/fail), `op` (gte/gt/lte/lt/eq/range_inc), `value` (number | [number, number])
     - `allOf` 条件で `op=range_inc` 時は `value` が配列であることを強制
     - `additionalProperties: false` で厳格な型チェック
  2. **初期データ** (`config/thresholds.json`):
     - 5.0KB、全7test_code（single_leg_squat, skater_lunge, stride_mimic, jump_landing, upper_body_swing, push_pull, cross_step）
     - `versions`: rules_version=v0.1.0, normalization_version=none, artifact_sha=local-dev
     - `metadata`: schema_version=1.0.0, updated_at=2025-11-02T00:00:00Z
     - 各test_codeにplaceholder閾値（保守的な初期値）を設定
     - `features` 配列（bilateral, lateral, rotation等）でテスト特性を記録
     - `refs` 配列（ADR-023等）でトレーサビリティ確保
  3. **validateスクリプト** (`scripts/validate-thresholds.py`):
     - 6.8KB、Python 3.9+、jsonschema依存
     - **スキーマ検証**: Draft7Validator で構造整合性チェック
     - **網羅性チェック**: EXPECTED_TEST_CODES定数（7種目）との一致確認
     - **bands連続性チェック**: 非重複・連続区間被覆をヒューリスティック検証（警告のみ）
     - Exit code: 0=Valid, 1=エラー
     - 実行例: `python scripts/validate-thresholds.py config/thresholds.json`
  4. **diffスクリプト** (`scripts/diff-thresholds.py`):
     - 9.6KB、Python 3.9+
     - **SemVer分類**:
       - MAJOR（値3）: Band削除、op変更、value範囲縮小（互換性破壊）
       - MINOR（値2）: Band追加、value範囲拡大（後方互換）
       - PATCH（値1）: metadata変更のみ（非破壊）
       - NONE（値0）: 変更なし
     - `Severity` を `IntEnum` で実装（比較可能）
     - 出力形式: list（デフォルト）、table（マークダウン形式）
     - Exit code: 0=MINOR以下, 2=MAJOR
     - 実行例: `python scripts/diff-thresholds.py old.json new.json --format=table`
  5. **サンプルコード** (`examples/load-thresholds.py`):
     - 5.6KB、`ThresholdLoader` クラス実装
     - `get_versions()`: バージョン情報取得
     - `get_bands(test_code)`: 閾値バンド取得
     - `classify_value(test_code, value)`: 値のpass/border/fail分類（簡易実装）
     - スキーマ検証on load（オプション）
  6. **README** (`docs/thresholds-README.md`):
     - 10KB、完全ドキュメント
     - データ構造、versions/metadata/tests詳細
     - 更新手順（編集→検証→差分確認→バージョン更新→コミット）
     - SemVer運用ルール（MAJOR/MINOR/PATCH条件）
     - トラブルシューティング
     - CI連携サンプル（pre-commit hook、GitHub Actions）
  7. **CI配線**:
     - **GitHub Actions** (`.github/workflows/validate-thresholds.yml`):
       - PR時: validate実行 + diff表示 + MAJOR変更警告
       - PRコメント自動投稿（変更サマリをtable形式で表示）
       - push時: validate実行（main, feature/**ブランチ）
     - **pre-commit hook** (`scripts/pre-commit-thresholds.sh`):
       - 2.3KB、bash実装
       - thresholds.json変更検知時に自動validate
       - MAJOR変更時に確認プロンプト表示
       - Exit code: 0=OK, 1=abort
       - インストール: `cp scripts/pre-commit-thresholds.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit`
- 技術詳細:
  - **JSON Schema allOf条件**:
    ```json
    "allOf": [
      {
        "if": {"properties": {"op": {"const": "range_inc"}}},
        "then": {"properties": {"value": {"type": "array", "minItems": 2, "maxItems": 2}}}
      },
      {
        "if": {"properties": {"op": {"enum": ["gte", "gt", "lte", "lt", "eq"]}}},
        "then": {"properties": {"value": {"type": "number"}}}
      }
    ]
    ```
  - **Band overlap検出アルゴリズム**:
    - 各bandから数値区間 `[min, max]` を抽出
    - 区間ペアごとに `not (a_max < b_min or b_max < a_min)` で重複判定
    - 警告のみ（エラーとしない）：意図的重複（hysteresis等）を許容
  - **Severity比較**: `IntEnum` で順序定義（NONE < PATCH < MINOR < MAJOR）、`max()` で最大重要度判定
  - **versions初期値**:
    - rules_version: v0.1.0（保守的初期値、将来validation dataベースで更新）
    - normalization_version: "none"（v2.1システムで正規化未実装のため）
    - artifact_sha: "local-dev"（ビルド時に `git rev-parse --short HEAD` で更新予定）
- 影響範囲:
  - **新規ファイル**: 8ファイル（config/thresholds.json, schema/, scripts/, examples/, docs/, .github/workflows/）
  - **既存コード**: 影響なし（今回は閾値外部化のみ、実装コードは次Phaseで連携）
  - **依存関係**: jsonschema ライブラリ追加（`pip install jsonschema`、CI環境で自動インストール）
  - **リポジトリサイズ**: +50KB（主にREADMEとスキーマ）
- トレードオフ:
  - **メリット**:
    - バージョン管理可能な閾値設定
    - 変更履歴の自動追跡（git + SemVer分類）
    - Data Science Teamの自律的メンテナンス
    - result.jsonとの整合性保証
    - dual scoring実装時の比較基盤
  - **デメリット**:
    - 新しいファイル形式の学習コスト
    - validate/diff実行の手間（CI自動化で緩和）
    - JSON手書きミスのリスク（schema検証で緩和）
  - **代替案検討**:
    - YAML形式: 却下（コメント混入リスク、JSON Schemaエコシステムが強力）
    - TOML形式: 却下（ネスト構造が冗長、Pythonエコシステムで劣る）
    - データベース保存: 却下（git履歴管理が困難、過剰設計）
- 制約事項:
  - **初期閾値の精度**: placeholder値（保守的）、validation data（ADR-023 templates）収集後に更新必要
  - **normalization_version**: 現在 "none"、将来の正規化アルゴリズム実装時に更新
  - **artifact_sha管理**: 手動更新またはビルドスクリプト必要（CI/CD未統合）
  - **bands重複許容**: 警告のみでエラーとしない（hysteresis等の意図的重複を考慮）
- 検証結果:
  - ✅ Schema検証: 合格（全7test_code、versions/metadata完備）
  - ✅ 網羅性チェック: 合格（EXPECTED_TEST_CODESと一致）
  - ✅ diff動作確認: MAJOR変更（value 80→85）を正しく検出、Exit code 2
  - ✅ サンプルコード実行: 値分類（50→fail, 70→border, 85→pass）正常動作
  - ⚠️  Band overlap警告: 7test_code全てで境界値重複検出（設計上の意図的重複、問題なし）
- 今後の展開:
  - **優先度A（1週間以内）**: validation data（ADR-023 cross_step_mimic template等）を基に実閾値を更新、rules_version v0.2.0へ
  - **優先度B（1ヶ月以内）**:
    - processing/worker.py でthresholds.json読込実装
    - result.json生成時に versions をthresholds.jsonから注入
    - artifact_sha自動更新（ビルドスクリプト連携）
  - **優先度C（将来）**:
    - normalization_version実装（正規化アルゴリズム標準化）
    - Rep CLI MVP連携（versions整合チェック）
    - Dual scoring実装（複数バージョン閾値比較）
- 参照:
  - 作成ファイル:
    - `config/thresholds.json` (5.0KB)
    - `schema/thresholds.schema.json` (5.8KB)
    - `scripts/validate-thresholds.py` (6.8KB)
    - `scripts/diff-thresholds.py` (9.6KB)
    - `scripts/pre-commit-thresholds.sh` (2.3KB)
    - `examples/load-thresholds.py` (5.6KB)
    - `docs/thresholds-README.md` (10KB)
    - `.github/workflows/validate-thresholds.yml` (2.6KB)
  - ADR-023（v2.1システム・560点満点）
  - ADR-027（Dashboard versions表示）
  - JSON Schema Draft-07仕様

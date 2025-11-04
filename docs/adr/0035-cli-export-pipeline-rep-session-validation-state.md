## ADR-035: CLI Export Pipeline統合（rep/session validation state付与）

- 日付: 2025-11-03
- 決定者: Human + codex (実装), Claude Code (文書化)
- 状態: ✅ Accepted
- 関連ADR: ADR-031（thresholds.json互換性チェッカー）, ADR-033（Validate Workflow）

### Context（背景）
Task A（thresholds_v2自動生成）とTask B（ValidationEngine統合）完了後、CLIとLambdaで統一されたvalidation_state（OK/WARN/ERROR）をrep/sessionレコードに付与する必要があった。Phase 2.5→5横断で同一語彙（rules_version, thresholds_version, normalization_version, artifact_sha）を使用し、エンドツーエンドでの整合性を担保する。

### Decision（決定）
**CLI Export Pipeline統合**:
- キャッシュされたthresholdsローダー実装
  - config/thresholds_v2.jsonを唯一の真実源として導入
  - run_pipelineでversions.thresholds_versionとvalidation.state付与
- rep/sessionレコードビルダー追加
  - CLIがrep_result.json / session_result.jsonを出力（cli/rep_cli.py:332-520）
  - result.jsonと並行して詳細情報をエクスポート
- スキーマ緩和
  - rep/sessionスキーマで長いテストコード対応（schema/rep_result.schema.json:25-96）
  - ローカルビルドSHA対応（schema/session_result.schema.json:20-83）
  - ランタイムエクスポートがスキーマ検証をパス
- CLIテストスイート強化
  - cv2/mediapipe/numpyの軽量スタブ実装（tests/test_rep_cli.py:22-99）
  - end-to-endエクスポートテスト追加（tests/test_rep_cli.py:433-485）
  - 既存スキーマfixtureテストも全パス（tests/test_result_schemas.py:1-87）

### Rationale（理由）
**thresholds_v2を唯一の真実源に**:
- Notion Templates → thresholds_v2.json → ValidationEngine → rep/session の一貫性
- 複数バージョン管理の混乱を回避

**validation_state統一**:
- CLI/Lambda/Dashboardで同一語彙使用
- OK/WARN/ERRORの3状態で互換性判定を標準化

**スキーマ緩和の必要性**:
- 既存スキーマは短いテストコード（"T02_B2"等）を想定
- ValidationEngineは長形式テストコード対応が必要
- ローカルビルドSHAも許容（開発時の柔軟性）

**end-to-endテスト**:
- 生成されたrep_result.json / session_result.jsonがスキーマ検証パス
- 回帰防止とCI統合準備

### Consequences（影響）
**影響範囲**:
- cli/rep_cli.py: エクスポートヘルパー実装（332-520行、codex実装）
- config/thresholds_v2.json: 唯一の真実源（1-22行、Task A成果物）
- schema/rep_result.schema.json: スキーマ緩和（25-96行、codex実装）
- schema/session_result.schema.json: スキーマ緩和（20-83行、codex実装）
- tests/test_rep_cli.py: スタブ・end-to-endテスト追加（22-99, 433-485行、codex実装）
- tests/test_result_schemas.py: 既存テスト維持（1-87行、全パス）

**テスト結果**:
- ✅ pytest tests/test_rep_cli.py: 全パス
- ✅ pytest tests/test_result_schemas.py: 全パス
- ✅ Schema更新のend-to-endテストが通過

**破壊的変更**: なし
- result.jsonは従来通り出力
- rep_result.json / session_result.jsonは追加出力（既存フローに影響なし）
- スキーマ緩和は後方互換性維持

**次のステップ（Next Step）**:
- AWS VideoProcessingWorker統合
  - LambdaでCLIと同じexport helpers使用
  - Lambda出力がCLI contractと一致
- Mission Control Board更新
  - Task C（version_display最小実装）を「完了」にマーク
  - Next step（AWS VideoProcessingWorker統合）を新規カードとして起票

**参照**:
- cli/rep_cli.py:332-520（エクスポートヘルパー）
- config/thresholds_v2.json:1-22（唯一の真実源）
- schema/rep_result.schema.json:25-96（スキーマ緩和）
- schema/session_result.schema.json:20-83（スキーマ緩和）
- tests/test_rep_cli.py:22-99, 433-485（スタブ・end-to-endテスト）
- tests/test_result_schemas.py:1-87（既存テスト維持）

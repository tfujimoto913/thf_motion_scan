## ADR-037: Validation System Integration（Task A〜D統合）

- 日付: 2025-11-03
- 決定者: Human + codex + Claude Code
- 状態: ✅ Accepted
- 関連ADR: ADR-034（Task C）, ADR-035（Task B+C CLI統合）, ADR-036（Task D）

### Context（背景）

Phase 2.5→5横断で、Notion Templates → thresholds_v2.json → ValidationEngine → Dashboard の一貫したvalidation state管理が必要となった。Task A（thresholds自動生成）、Task B（ValidationEngine統合）、Task C（version_display UI）、Task D（validation_badge UI）が個別に完了したが、全体視点での統合的な設計判断と影響範囲を記録する必要があった。

### Decision（決定）

**Task A〜D統合によるValidation Systemの確立**:

**Task A: Thresholds v2自動生成パイプライン**
- tools/build_thresholds.py実装（codex）
- Notion Templates → config/thresholds_v2.json自動生成
- SemVer管理（rules_version, thresholds_version, normalization_version, artifact_sha）
- 唯一の真実源（Single Source of Truth）として確立

**Task B: ValidationEngine統合**
- src/config/compat.py実装（codex）
- SemVer互換性判定ロジック: MAJOR差=ERROR, MINOR差=WARN, PATCH差=OK
- src/config/loader.py実装（thresholds読み込み・versions抽出）
- CLI/Lambda両方で使用可能な共通モジュール

**Task C: Dashboard Version Compatibility UI**
- dashboard/version_display.py実装（codex）
- config/required_versions.json作成（codex）
- 全体バージョン互換性チェック（サイドバー表示）
- force_override機構（ERROR時も強制続行可能）
- dashboard/app.py統合（29行目、2002行目）

**Task D: Validation State Badge UI**
- dashboard/validation_badge.py実装（Claude Code）
- セッション単位のvalidation state表示（OK=緑/WARN=黄/ERROR=赤）
- violations/reasons両対応（後方互換性）
- tests/fixtures/session_result/valid/valid_warn_low_count.json追加（WARN状態テスト）
- dashboard/session_pages.py統合（318-330行）

### Rationale（理由）

**唯一の真実源（Single Source of Truth）**:
- Notion Templates → thresholds_v2.json → ValidationEngine の一貫性
- 複数バージョン管理の混乱を回避
- tools/build_thresholds.pyで自動生成、手動編集禁止

**SemVer準拠の互換性判定**:
- MAJOR差: 破壊的変更、実行ブロック（ERROR + st.stop()）
- MINOR差: 後方互換、警告のみ（WARN、続行可）
- PATCH差: バグ修正のみ（OK）
- 業界標準に準拠し、影響範囲を明確化

**UI層での一貫した可視化**:
- version_display.py: 全体互換性チェック（サイドバー、起動時）
- validation_badge.py: セッション単位評価結果（詳細画面）
- 役割分離で保守性向上、両方のコンポーネントが補完関係

**OK/WARN/ERROR統一語彙**:
- CLI/Lambda/Dashboardで同一ステータス使用
- Phase 2.5（ValidationEngine）→ Phase 5（Dashboard）横断で整合性担保
- rep_result.json / session_result.jsonにvalidation.state付与

**後方互換性維持**:
- 既存フローは非破壊（result.jsonは従来通り出力）
- rep_result.json / session_result.jsonは追加出力
- validation未取得時もクラッシュしない（フォールバック実装）

### Consequences（影響）

**影響範囲**:

**Task A成果物**:
- tools/build_thresholds.py（新規、codex実装）
- config/thresholds_v2.json（自動生成、SemVer管理）

**Task B成果物**:
- src/config/compat.py（新規、codex実装）
- src/config/loader.py（新規、codex実装）
- tests/test_config_compat.py（6ケース、codex実装）

**Task C成果物**:
- dashboard/version_display.py（新規168行、codex実装）
- config/required_versions.json（新規、codex実装）
- dashboard/app.py（29行目、2002行目、codex実装）
- README.md（707-737行、Claude Code実装）

**Task D成果物**:
- dashboard/validation_badge.py（新規145行、Claude Code実装）
- dashboard/session_pages.py（318-330行、Claude Code実装）
- dashboard/session_result_loader.py（デモフィクスチャ自動検出、Claude Code実装）
- tests/fixtures/session_result/valid/valid_warn_low_count.json（新規、Claude Code実装）
- README.md（740-772行 → 統合セクションに変更、Claude Code実装）

**CLI Export Pipeline統合（Task B+C横断）**:
- cli/rep_cli.py: エクスポートヘルパー実装（332-520行、codex実装）
- schema/rep_result.schema.json: スキーマ緩和（25-96行、codex実装）
- schema/session_result.schema.json: スキーマ緩和（20-83行、codex実装）
- tests/test_rep_cli.py: end-to-endテスト追加（22-99, 433-485行、codex実装）

**DoD達成状況**:
- ✅ Task A: thresholds_v2.json自動生成パイプライン
- ✅ Task B: SemVer互換性判定ロジック（6テストケース全パス）
- ✅ Task C: version_display UI統合（OK/WARN/ERROR表示、force_override対応）
- ✅ Task D: validation_badge UI統合（3状態色分け、ツールチップ、フォールバック）
- ✅ CLI Export Pipeline統合（rep/session validation state付与）
- ✅ README統合セクション作成（Task A〜D概要）
- ⏳ スクリーンショット（ユーザー実施待ち）

**破壊的変更**: なし
- 全Task非破壊的統合
- 既存フロー（result.json、session_list等）は影響なし
- validation未取得時もフォールバック動作

**メリット**:
- エンドツーエンド整合性担保（Notion → CLI → Lambda → Dashboard）
- 段階的ロールアウト可能（各Task独立実装、段階的統合）
- 観測性向上（validation.state + versions情報をログ・UI両方で可視化）
- 保守性向上（唯一の真実源、役割分離、テストカバレッジ）

**デメリット**:
- 複数コンポーネント横断（tools/src/dashboard）、全体把握の学習コスト
- Demo Mode依存（session_result.json取得可能性）
- Task E（AWS VideoProcessingWorker統合）待ち

### Follow-up（今後の展開）

**即座の次ステップ**:
- Demo Mode動作確認（valid/invalid フィクスチャ切り替え）
- スクリーンショット取得（OK/WARN/ERRORの3パターン）
- PR作成・レビュー

**Task E（AWS VideoProcessingWorker統合）**:
- LambdaでCLIと同じexport helpers使用
- Lambda出力がCLI contractと一致
- validation.stateをDynamoDB・S3両方に記録

**将来拡張**:
- UI/UX: サイドバーに「強制的に続行」トグル設置
- ログ/監査: 強制続行時に構造化ログ出力（event="force_override"）
- CloudWatch メトリクス連携（`compat_status{status=OK|WARN|ERROR}` 分布）
- 自動マイグレーション提案（MAJOR差異検出時の移行手順出力）

### 参照

**ADR参照**:
- ADR-028（thresholds.json versions導入）
- ADR-030（thresholds.json構造検証）
- ADR-031（SemVer互換性チェッカー）
- ADR-032（構造化ログ規約）
- ADR-034（Task C: version_display UI）
- ADR-035（Task B+C: CLI Export Pipeline）
- ADR-036（Task D: validation_badge UI）

**コミット**:
- 75b0260（Task C README追記）
- e9ace62（Task D実装）
- 7921ac7（Task D README追記）
- d1f89d5（README統合セクション作成）

**実装ファイル**:
- Task A: tools/build_thresholds.py, config/thresholds_v2.json
- Task B: src/config/compat.py, src/config/loader.py
- Task C: dashboard/version_display.py, config/required_versions.json
- Task D: dashboard/validation_badge.py, tests/fixtures/session_result/valid/valid_warn_low_count.json
- CLI統合: cli/rep_cli.py:332-520, schema/*_result.schema.*
- README: README.md 統合セクション（~200文字概要 + Task A-D箇条書き）

---

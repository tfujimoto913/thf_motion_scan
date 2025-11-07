## ADR-036: Validation State Badge UI統合（Dashboard v2.1 Task D）

- 日付: 2025-11-03
- 決定者: Human + Claude Code
- 状態: ✅ Accepted
- 関連ADR: ADR-034（version_display UI統合）, ADR-035（CLI Export Pipeline統合）

### Context（背景）
Task A-Cで確立されたvalidation.state（OK/WARN/ERROR）語彙をDashboardセッション詳細画面に統合し、ユーザーに視覚的フィードバックを提供する必要があった。session_result.jsonにvalidation情報が既に含まれており、これを色分けバッジで表示する。

### Decision（決定）
**Validation State Badge実装**:
- dashboard/validation_badge.py作成
  - render_validation_badge()関数: OK/WARN/ERRORを色分け表示
  - アイコン: ✅ OK（緑）、⚠️ WARN（黄）、❌ ERROR（赤）
  - ツールチップ: validation.violations/reasonsをエクスパンダーで展開表示
  - versions情報表示: rules_version, thresholds_version, artifact_sha（短縮）
  - フォールバック: validation未取得時は"Validation情報なし"表示（クラッシュしない）
- dashboard/session_pages.py統合
  - session_detail_page関数にバッジ表示追加（318-330行）
  - session_result_loader.load_session_result()で情報取得
  - display_versionsと併存（非破壊的統合）
- テストフィクスチャ拡張
  - tests/fixtures/session_result/valid/*.json（OK/WARNシナリオ3件）
  - tests/fixtures/session_result/invalid/*.json（想定外シナリオ5件）
- README更新
  - Validation State Badgeセクション追加（740-772行）
  - 表示仕様、ツールチップ、フォールバック、テストフィクスチャを文書化

### Rationale（理由）
**Streamlitネイティブカラー採用**:
- シンプル実装（`:green[...]`, `:orange[...]`, `:red[...]`）
- カスタムCSSなしで可読性高い

**violations/reasons両方サポート**:
- codex実装ではviolations使用、将来的にreasonsも想定
- 両方の命名規則に対応し、柔軟性を担保

**display_versionsと併存**:
- version_display.pyは全体互換性チェック
- validation_badge.pyはセッション単位の評価結果表示
- 役割分離で保守性向上

**フォールバック実装**:
- session_result.json未取得時もクラッシュしない
- state不正値は"UNKNOWN（グレー）"表示

### Consequences（影響）
**影響範囲**:
- dashboard/validation_badge.py: 新規作成（145行、Claude Code実装）
- dashboard/session_pages.py: バッジ統合（318-330行、Claude Code実装）
    - dashboard/session_result_loader.py: デモフィクスチャ自動検出ロジック追加
    - tests/fixtures/session_result/valid/valid_warn_low_count.json: 新規作成（Claude Code実装）
- README.md: Validation State Badgeセクション追加（740-772行、Claude Code実装）

**DoD達成状況**:
- ✅ 3状態（OK/WARN/ERROR）で正しい色・文言・ツールチップ表示
- ✅ versions欠落時もクラッシュせずバッジ動作
- ✅ README更新（Stateバッジ仕様記載）
- ⏳ PRにスクリーンショット3枚添付（ユーザー実施待ち）

**破壊的変更**: なし
- 既存セッション詳細画面に追加表示のみ
- validation情報がない場合は"Validation情報なし"表示（後方互換）

**次のステップ（Task D以降）**:
- デモモード動作確認（3状態フィクスチャ切り替え）
- スクリーンショット取得（OK/WARN/ERROR）
- PR作成・レビュー

**参照**:
- Commit: e9ace62（Task D実装）
- dashboard/validation_badge.py:1-145
- dashboard/session_pages.py:318-330（バッジ統合）
- tests/fixtures/session_result/valid/valid_ok_all_pass.json（OK状態）
- tests/fixtures/session_result/valid/valid_warn_low_count.json（WARN状態）
- tests/fixtures/session_result/invalid/invalid_bad_state.json（ERROR状態）
- README.md:740-772（Validation State Badge仕様）

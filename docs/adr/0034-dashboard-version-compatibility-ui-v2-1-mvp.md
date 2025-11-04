## ADR-034: Dashboard Version Compatibility UI統合（v2.1 MVP）

- 日付: 2025-11-03
- 決定者: Human + Claude Code (codex実装, Claude Code文書化)
- 状態: ✅ Accepted
- 関連ADR: ADR-031（thresholds.json互換性チェッカー）, ADR-032（構造化ログ規約）

### Context（背景）
Dashboard v2.1では、thresholds.jsonのバージョン互換性を実行時にチェックし、不一致時にユーザーへ通知・ブロックする機能が必要となった。Phase 2.5→5横断で同一語彙（rules_version, normalization_version, artifact_sha）を使用し、SemVer準拠の比較ポリシーで一貫性を担保する。

### Decision（決定）
**version_display最小実装（MVP）**:
- dashboard/version_display.py実装（codex作成済み）
  - display_versions()関数: required_versions.jsonと現在バージョンを比較
  - SemVer比較ポリシー: MAJOR差=ERROR、MINOR差=WARN、PATCH差=OK
  - artifact_sha完全一致チェック
  - force_override機構（st.session_state.force_override）でERROR時も強制続行可能
- config/required_versions.json作成（codex作成済み）
  - 必須鍵: rules_version, normalization_version, artifact_sha
- dashboard/app.py組み込み（codex作成済み）
  - main()冒頭でdisplay_versions()呼び出し
- README追記（Claude Code実施）
  - SemVer比較ポリシー、必須鍵、force_override仕様を文書化

### Rationale（理由）
**SemVer比較ポリシー採用**:
- MAJOR差: 破壊的変更のため実行ブロック（ERROR + st.stop()）
- MINOR差: 後方互換のため警告のみ（WARN、続行可）
- PATCH差: バグ修正のみのためOK

**force_override機構**:
- 開発・検証時にERROR状態でも動作確認可能
- 監査推奨: 強制続行時は構造化ログで記録（将来拡張）

**サイドバー表示**:
- 常時可視でバージョン情報を確認可能
- エラー詳細はエクスパンダーで展開

### Consequences（影響）
**影響範囲**:
- dashboard/version_display.py: 新規作成（168行、codex実装）
- config/required_versions.json: 新規作成（codex実装）
- dashboard/app.py: display_versions()呼び出し追加（29行目、2002行目、codex実装）
- README.md: Version Compatibilityセクション追加（707-737行、Claude Code実装）

**依存関係**:
- src/config/compat.py（Task B: ValidationEngineで作成済み）
- dashboard/i18n.py（既存）

**DoD（完了想定）**:
- ✅ OK/WARN/ERROR 3状態が正しく判定・表示される
- ✅ force_override=TrueでERROR時も続行可能
- ✅ 必須鍵（rules_version, normalization_version, artifact_sha）が比較される
- ✅ READMEにSemVerポリシー・override挙動が明記

**オプション（将来拡張）**:
- UI/UX: サイドバーに「強制的に続行」トグル設置
- ログ/監査: 強制続行時に構造化ログ出力（event="force_override"）
- i18n: WARN/ERRORメッセージの多言語対応拡張
- 取得方法: get_current_versions()をビルドメタから取得

**破壊的変更**: なし
- 既存機能に影響なし
- display_versions()は新規追加、既存フローは非破壊

**参照**:
- Commit: 75b0260（README追記）
- dashboard/version_display.py:1-168
- config/required_versions.json
- src/config/compat.py（Task B実装）
- README.md:707-737

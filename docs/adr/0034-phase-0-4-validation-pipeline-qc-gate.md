## ADR-034: Phase 0-4 Validation Pipeline 運用開始（QC Gate / ドキュメント整備）

- 日付: 2025-11-06
- ステータス: Accepted
- 影響範囲: processing pipeline, CI, docs
- 関連ADR: ADR-022, ADR-023, ADR-030, ADR-032, ADR-033

### Context

Phase 0-4 適用ルール（Validation Ops Hub）を本番運用に組み込む準備が整い、Thresholds v2 / ValidationEngine / スキーマ整備（Task A-C）と Dashboard バッジ表示（Task D）が完了。残課題として、前処理での QC Gate 適用・撮影ガイド更新・Canary 監視手順・CI での schema 検証統合が未実装だった。

### Decision

1. **QC Gate**: `processing/qc_gate.py` と `config/qc_gate.json` を新設し、evaluation 出力に対して Phase 0-4 gate（初期は B4 骨盤水平 σ >= 3.0）をチェック。`VideoProcessingWorker` で gate を呼び出し、構造化ログへ WARN/INFO を出力する。結果を `result['qc_gate']` に格納。
2. **CI**: `.github/workflows/validate-thresholds-v2.yml` に rep/session スキーマ検証と例示データの smoke test を追加し、Phase 0-4 ルールが壊れていないことを自動確認。
3. **ドキュメント**:
   - `docs/phase0-4_deployment_rules.md` : CI・QC Gate・撮影ガイド・Canary/rollback の運用手順を統合。
   - `docs/filming_guide_v2.md` : 撮影距離/照度/解像度の定量基準と再撮手順を明文化。
   - `docs/canary_monitoring.md` : Canary 10% 運用、監視指標 (BCR > 10%, κ < 0.6, override_rate > 15%)、Rollback 手順を定義。
   - README に上記ドキュメントへのリンクを追加。

### Implementation

- `processing/worker.py` に QC Gate 呼び出しとログ出力 (`log_qc_gate`) を追加。
- `processing/logger.py` に QC Gate 用ロガーを追加。
- `tests/processing/test_qc_gate.py` で gate 評価の単体テストを実装。
- `schema/rep_result.schema.json`, `schema/session_result.schema.json`, `examples/*.sample` を QC Gate 語彙（band / metric / violations）に合わせて更新。
- CI の schema 検証に `tests/fixtures/schemas/**` と公開サンプルを含めた。

### Consequences

**メリット**
- Phase 0-4 適用ルールの最小構成が通電し、監視・ドキュメント・撮影基準が揃った。
- 前処理の QC Gate で WARN を出力でき、将来的な Gate 拡張の足場が整った。
- CI で schema / sample チェックを行い、破壊的変更を早期検知可能。

**デメリット**
- B4 σ のみを対象とした暫定 gate のため、他原則は未カバー。
- QC Gate の WARN はブロックしない（運用判断が必要）。
- 撮影ガイドと Canary 手順は文書化のみで、運用整備（FAQ・テンプレ）は今後が必要。

### Follow-up

- Gate 対象の拡張（B4 以外のルール、複合指標、override ログ）。
- Dual Scoring / Dashboard 表示で Gate 結果を明示。
- CI を必須化（2025-12 予定）し、Phase Gate ルールに組み込む。
- 撮影ガイドの PDF 化 + 現場教育。

### References

- コード: `processing/qc_gate.py`, `processing/worker.py`, `.github/workflows/validate-thresholds-v2.yml`
- ドキュメント: `docs/phase0-4_deployment_rules.md`, `docs/filming_guide_v2.md`, `docs/canary_monitoring.md`
- テスト: `tests/processing/test_qc_gate.py`, `tests/test_result_schemas.py`

# Phase 0-4 適用ルール運用手順

## 目的
Phase 0-4 の適用ルール（Validation Ops Hub）の要点を CI / 前処理 / 撮影ガイド / 監視手順に反映し、最小限の通電確認を実施する。

## 1. CI 連携
- `.github/workflows/validate-thresholds-v2.yml` を既存 CI に追加し、以下を自動検証
  - `tests/fixtures/thresholds_v2/{valid,warn}/` → pass
  - `tests/fixtures/thresholds_v2/invalid/` → fail
  - `tests/fixtures/rep_result/{valid,warn}/` → pass
  - `tests/fixtures/session_result/{valid,warn}/` → pass
  - `tests/fixtures/rep_result/invalid/`, `tests/fixtures/session_result/invalid/` → fail
  - `examples/rep_result.sample.json` / `examples/session_result.sample.json` → smoke test
- 2025-11 までは警告モード。2025-12 リリースで必須チェックに格上げ予定（README `Result Schema Contracts` 参照）。

## 2. 前処理 (QC Gate)
- `config/qc_gate.json` に Phase 0-4 gate を定義（初期実装は B4 σ しきい値 >= 3.0）。
- `processing/qc_gate.py` ＋ `VideoProcessingWorker` により、各テストの評価結果を QC Gate に照合。
- 失敗時は構造化ログ `QC gate violation detected` を WARN で出力し、`result['qc_gate']` に格納。

## 3. 撮影ガイド連携
- `docs/filming_guide_v2.md` に距離 / 照度 / 解像度の推奨値と再撮手順を明記。
- ガイドは現場向け PDF への取り込みを前提とし、改訂履歴 (v2.0 → 2025-11-03) を付与。

## 4. Canary 監視・Rollback
- `docs/canary_monitoring.md` に 3 指標 (BCR > 10%、κ < 0.6、override_rate > 15%) の Canary 条件と対応策を記載。
- 逸脱時は Δ/±1° パッチで緩和し、状況が改善しない場合は Phase 0-3 へロールバック。

## 5. 成功条件 (DoD)
1. CI: valid/invalid フィクスチャが期待通り挙動。
2. QC Gate: `processing/logger.py` に WARN が記録されること（B4 gate 低値ケースで確認）。
3. 撮影ガイド: 撮影基準・再撮手順を明文化。
4. Canary/rollback: 監視条件と復旧手順をドキュメント化。

## 6. 次のアクション (Phase 5+)
- QC Gate の網羅（B4 以外の原則、複合指標、現場 override ログ）。
- Dual Scoring 可視化（Dashboard / CLI での gate 表示）。
- Phase Gate 制御（QC Gate 失敗時に CI ブロック / 自動再撮リクエスト）。

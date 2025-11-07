# Canary Monitoring & Rollback Playbook

## 目的
Phase 0-4 適用ルールの導入後、早期にドリフトを検知し安全にロールバックするための監視・対応手順を定義する。

## Canary リリース方針
- 本番トラフィックの 10% を Canary グループに振り分け、Phase 0-4 適用ルールを適用。
- Canary 対象は全テスト種目の均等サンプル（週単位でランダム抽出）とする。

## 監視指標と閾値
| 指標 | 定義 | Canary 閾値 | 評価期間 |
|------|------|------------|----------|
| BCR (Bad Case Rate) | `failed_reps / total_reps` | > 10% | 24 時間移動平均 |
| κ (Cohen's kappa) | モデル vs. コーチ判定の一致度 | < 0.6 | 24 時間移動平均 |
| override_rate | コーチの手動差し戻し率 | > 15% | 24 時間移動平均 |

閾値を超過した場合は Canary ロールアウトを即停止し、運用チームへ Slack / PagerDuty でアラートを送出する。

## 逸脱時の一次対応
1. 直近 12 時間のログを確認し、対象種目とテストコードを特定。
2. `QC gate violation detected` WARN の増減を分析。B4 しきい値が原因の場合はテンポラリパッチ（Δ/±1°）を適用。
3. 問題が継続する場合は Phase 0-3 ルールセットへロールバック。

## Rollback 手順
1. CloudWatch Dashboard の Canary スイッチを OFF に設定（10% → 0%）。
2. Lambda 環境変数 `PHASE_RULES_VERSION` を `phase_0_3` に戻し、デプロイ。
3. `config/qc_gate.json` をバックアップし、Phase 0-3 向け設定へ差し替え。
4. `validate-thresholds-v2.yml` のフィクスチャを実行し、既存ルールで pass することを確認。
5. Streamlit Dashboard v2.1 の管理者ビューで「適用ルール: Phase0-3 (rollback)」を表示。

## 復帰判定
- 24 時間連続で BCR / κ / override_rate が閾値内に収まり、QC Gate WARN が baseline ±5% に戻った場合に再度 Canary 10% を開始。
- 再度展開する際は、パッチ内容（Δ/±1° 等）を本番ルールへ反映後にロールアウトする。

## エスカレーション
- SRE → PM: BCR > 15% または κ < 0.45 が 6 時間継続。
- PM → 経営層: 24 時間以内に復帰見込みが立たない場合。

## 履歴
| 日付 | 内容 |
|------|------|
| 2025-11-03 | 初版作成（Phase 0-4 適用ルール通電リリース） |

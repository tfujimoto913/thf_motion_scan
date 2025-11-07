# Threshold Dry-Run Impact Estimation Tool

## 概要

閾値変更がセッションデータの再分類にどう影響するかを**瞬時に試算**するツールです。
SLS（Single Leg Squat）等の10-20件のサンプルに対して、新しい閾値を適用した場合の影響を事前確認できます。

**主要機能**:
- ✅ 再分類率の算出（affected_count / n_sample）
- ✅ 代表例の抽出（best: 改善, worst: 悪化, neutral: 変化なし）
- ✅ 高速処理（< 2s / 20件、実測: ~10-50ms）
- ✅ 決定論的サンプリング（固定seed）
- ✅ 監査ログ記録（JSONL形式）

---

## ファイル構成

```
tools/
├── threshold_dryrun.py          # 影響試算エンジン
├── convert_sls_samples.py       # サンプルデータ変換ツール
└── README_threshold_dryrun.md   # このファイル

tests/tools/
└── test_threshold_dryrun.py     # 23テストケース（全合格）

config/thresholds/
└── changelog.jsonl              # 閾値変更の監査ログ
```

---

## 使い方

### 1. 基本的な使い方（Pythonコード）

```python
import pandas as pd
from tools.threshold_dryrun import dry_run_threshold_change, log_threshold_decision

# サンプルデータ準備（CSVや既存rep_resultから変換可能）
samples_df = pd.DataFrame({
    "sample_id": ["rep_001", "rep_002", "rep_003", ...],
    "metric_value": [8.5, 12.3, 18.7, ...],          # 実測値
    "old_label": ["OK", "WARN", "WARN", ...],        # 現在の閾値での判定
})

# 新しい閾値バンド（緩和例: OK ≤12deg, WARN ≤22deg）
new_bands = [
    {"label": "OK", "max": 12.0},
    {"label": "WARN", "max": 22.0},
    {"label": "NG", "max": None},  # 上限なし
]

# Dry-run実行
result = dry_run_threshold_change(
    metric_id="SLS:B1:trunk_lean_deg",
    new_bands=new_bands,
    samples_df=samples_df,
    seed=42,         # 再現性のため固定
    sample_n=20,     # 最大20件サンプリング
)

# 結果表示
print(f"影響件数: {result['affected_count']}/{result['n_sample']}")
print(f"再分類率: {result['reclassified_rate']:.1%}")
print(f"実行時間: {result['dry_run_duration_ms']}ms")

# 代表例
if result["examples"]["best"]:
    best = result["examples"]["best"]
    print(f"Best改善例: {best['sample_id']} ({best['old_label']} → {best['new_label']}, 値={best['metric_value']:.1f})")

# 監査ログ記録（採用決定時のみ）
old_bands = [{"label": "OK", "max": 10.0}, {"label": "WARN", "max": 20.0}, {"label": "NG", "max": None}]
log_threshold_decision(
    metric_id="SLS:B1:trunk_lean_deg",
    old_bands=old_bands,
    new_bands=new_bands,
    dryrun_summary=result,
    actor="coach@example.com",
)
```

---

### 2. サンプルデータ変換

#### 2-1. 既存rep_resultから変換

```python
from tools.convert_sls_samples import convert_rep_results_to_samples
import json

# rep_resultロード
with open("test_reps.json", "r") as f:
    rep_results = json.load(f)

# 変換
old_bands = [{"label": "OK", "max": 10.0}, {"label": "WARN", "max": 20.0}, {"label": "NG", "max": None}]
df = convert_rep_results_to_samples(
    rep_results=rep_results,
    metric_id="SLS:B1:trunk_lean_deg",
    old_bands=old_bands,
)

# 保存
df.to_csv("sample_dataset/sls_samples.csv", index=False)
```

#### 2-2. CSVから読み込み

```python
from tools.convert_sls_samples import convert_csv_to_samples

df = convert_csv_to_samples(
    csv_path="data/sls_samples.csv",
    sample_id_col="rep_id",
    metric_value_col="trunk_lean",
    old_label_col="current_label",
)
```

#### 2-3. 合成データ生成（テスト用）

```python
from tools.convert_sls_samples import generate_synthetic_samples

df = generate_synthetic_samples(n_samples=20, seed=42)
```

#### 2-4. CLIから実行

```bash
# 合成データ生成
python tools/convert_sls_samples.py --generate --output sample_dataset/sls_samples.csv --n-samples 20

# rep_resultから変換
python tools/convert_sls_samples.py --rep-results test_reps.json --metric SLS:B1:trunk_lean_deg --output sample_dataset/converted.csv

# CSVを標準形式に変換
python tools/convert_sls_samples.py --csv data/raw_samples.csv --output sample_dataset/standardized.csv
```

---

### 3. UI組み込み（将来拡張）

**最小ワイヤー**:
```python
import streamlit as st
from tools.threshold_dryrun import dry_run_threshold_change

# UIパネル
st.header("Threshold Dry-run Preview")
metric_id = st.selectbox("指標選択", ["SLS:B1:trunk_lean_deg", ...])

# 新閾値入力
ok_max = st.number_input("OK上限 (deg)", value=10.0)
warn_max = st.number_input("WARN上限 (deg)", value=20.0)

if st.button("Dry-run実行"):
    new_bands = [
        {"label": "OK", "max": ok_max},
        {"label": "WARN", "max": warn_max},
        {"label": "NG", "max": None},
    ]

    # サンプルロード（既存データから）
    samples_df = load_sls_samples()  # 実装必要

    result = dry_run_threshold_change(metric_id, new_bands, samples_df)

    # 結果カード表示
    st.metric("影響件数", f"{result['affected_count']}/{result['n_sample']}")
    st.metric("再分類率", f"{result['reclassified_rate']:.1%}")

    # 代表例テーブル
    examples_data = []
    for category, example in result["examples"].items():
        if example:
            examples_data.append({
                "種別": category,
                "サンプルID": example["sample_id"],
                "旧": example["old_label"],
                "新": example["new_label"],
                "値": f"{example['metric_value']:.1f}",
            })
    st.table(examples_data)
```

---

## データ契約

### 入力（samples_df）

| 列名 | 型 | 必須 | 説明 |
|------|-----|------|------|
| `sample_id` | str | ✅ | 一意ID（rep_id等） |
| `metric_value` | float | ✅ | 指標の実測値 |
| `old_label` | str | ✅ | 現在の閾値での判定（"OK"\|"WARN"\|"NG"） |

### 閾値バンド（thresholds.json v2）

```json
{
  "version": "2.0",
  "metrics": {
    "SLS:B1:trunk_lean_deg": {
      "direction": "lower_is_better",
      "bands": [
        {"label": "OK", "max": 10.0},
        {"label": "WARN", "max": 20.0},
        {"label": "NG", "max": null}
      ]
    }
  }
}
```

- `direction`: `"lower_is_better"` のみ対応（現在）
- `bands`: 上から順に評価、`max: null` は上限なし

### 出力（dry_run_threshold_change）

```python
{
    "metric_id": str,
    "dry_run_duration_ms": int,           # 実行時間（ms）
    "affected_count": int,                # 再分類された件数
    "reclassified_rate": float,           # 再分類率（0.0-1.0）
    "n_sample": int,                      # 評価したサンプル数
    "examples": {
        "best": {                         # 最も改善した例（None可）
            "sample_id": str,
            "old_label": str,
            "new_label": str,
            "metric_value": float,
            "margin": float               # バンド中央からの距離
        },
        "worst": {...},                   # 最も悪化した例
        "neutral": {...}                  # 変化なしで境界に近い例
    }
}
```

---

## テスト

```bash
# 全テスト実行
python -m pytest tests/tools/test_threshold_dryrun.py -v

# 性能テストのみ
python -m pytest tests/tools/test_threshold_dryrun.py::test_dryrun_performance_under_2s_for_20_samples -v

# カバレッジ付き
python -m pytest tests/tools/test_threshold_dryrun.py --cov=tools.threshold_dryrun --cov-report=term
```

**現状**: 23テスト全合格、実行時間1.00秒

---

## パフォーマンス

| サンプル数 | 実行時間（実測） | 要件 |
|-----------|----------------|------|
| 20件 | ~10-50ms | < 2000ms ✅ |
| 10件 | ~5-20ms | < 2000ms ✅ |
| 100件（参考） | ~50-100ms | N/A |

**最適化ポイント**:
- ✅ ベクトル化（pandas/numpy）
- ✅ apply()の最小化（compute_label()は必要最小限）
- ✅ I/O分離（メモリ内処理）

---

## 監査ログ（changelog.jsonl）

閾値変更を決定した際、以下を記録：

```jsonl
{"ts": "2025-11-04T12:34:56Z", "actor": "coach@example.com", "type": "threshold_decision", "metric_id": "SLS:B1:trunk_lean_deg", "old_bands": [...], "new_bands": [...], "dryrun": {...}}
```

**フィールド**:
- `ts`: UTC ISO8601タイムスタンプ
- `actor`: 変更実行者（メールアドレス等）
- `type`: 固定値 `"threshold_decision"`
- `metric_id`: 対象指標
- `old_bands`, `new_bands`: 変更前後の閾値
- `dryrun`: dry_run_threshold_change()の出力（影響サマリー）

**用途**:
- コンプライアンス監査
- 変更履歴の追跡
- ロールバック時の参照

---

## よくある質問（FAQ）

### Q1: `direction: "higher_is_better"` は使えますか？

**A**: 現在未実装です。`NotImplementedError` が発生します。
将来のバージョンで対応予定（ADR参照）。

### Q2: サンプル数が10件未満の場合は？

**A**: 問題なく動作します。`sample_n` はリクエスト最大値で、実際には `min(sample_n, len(df))` を使用します。

### Q3: 実行時間が2sを超える場合は？

**A**: 通常は発生しません（20件で~10-50ms）。もし発生した場合：
1. サンプル数を減らす（`sample_n=10`）
2. I/O処理を確認（DataFrameロードが遅い可能性）
3. Issueを報告

### Q4: 代表例（best/worst/neutral）がNoneの場合は？

**A**: 該当する例が存在しない場合です。例：
- `best=None`: 改善例がない（全て悪化 or 変化なし）
- `worst=None`: 悪化例がない（全て改善 or 変化なし）
- `neutral=None`: 変化なしの例がない（全て再分類）

---

## ロードマップ

### v1.0（現在実装済み）
- ✅ 基本dry-run機能
- ✅ 代表例抽出
- ✅ 監査ログ
- ✅ 決定論的サンプリング

### v1.1（計画）
- [ ] `direction: "higher_is_better"` 対応
- [ ] 年齢層・性別別の閾値対応
- [ ] Streamlit UI統合
- [ ] 代表例のフレーム画像表示

### v2.0（将来）
- [ ] 複数指標の一括dry-run
- [ ] 差分可視化（ヒストグラム・散布図）
- [ ] 自動推奨閾値提案（機械学習）

---

## トラブルシューティング

### エラー: `ValueError: Invalid metric_id format`

**原因**: `metric_id` が `"TEST:GROUP:METRIC"` 形式でない

**解決**: 形式を修正
```python
# ❌ 間違い
metric_id = "trunk_lean_deg"

# ✅ 正しい
metric_id = "SLS:B1:trunk_lean_deg"
```

### エラー: `KeyError: 'old_label'`

**原因**: `samples_df` に `old_label` 列がない

**解決**: `convert_sls_samples.py` で変換、または手動で追加
```python
from tools.threshold_dryrun import compute_label

df["old_label"] = df["metric_value"].apply(
    lambda v: compute_label(v, old_bands, direction="lower_is_better")
)
```

### 警告: `SettingWithCopyWarning`

**原因**: DataFrame操作時のコピー警告

**解決**: `.copy()` を追加
```python
df = samples_df.sample(n=20, random_state=42).copy()
```

---

## 関連ドキュメント

- [ADR-030: Thresholds JSON v2 + JSON Schema](../docs/adr/0030-thresholds-json-jsonschema-pre-commit-ci.md)
- [Thresholds README](../docs/thresholds-README.md)
- [Phase 2 Processing Overview](../docs/design/overview.md)

---

## ライセンス・貢献

本ツールは thf_motion_scan プロジェクトの一部です。
バグ報告・機能要望は Issue にてお願いします。

---

**最終更新**: 2025-11-04
**作成者**: Claude Code
**テスト状況**: 23/23 passed (1.00s)

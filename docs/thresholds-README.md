# Thresholds Configuration (thresholds.json)

## 概要

`thresholds.json` は、THF Motion Scan評価システムの閾値設定を外部化し、バージョン管理可能にするための設定ファイルです。

**目的**:
- 評価ルールの変更追跡（SemVer管理）
- rep判定、dual scoring展開への対応準備
- result.jsonとのバージョン整合性確保

**作成日**: 2025-11-02
**Decision Log**: ADR-028

---

## ファイル構造

```
repo/
├── config/thresholds.json          # 閾値設定本体
├── schema/thresholds.schema.json   # JSON Schema定義
├── scripts/
│   ├── validate-thresholds.py      # 検証スクリプト
│   └── diff-thresholds.py          # 差分比較スクリプト
├── examples/load-thresholds.py     # サンプルコード
└── docs/thresholds-README.md       # このファイル
```

---

## データ構造

### トップレベル

```json
{
  "versions": {
    "rules_version": "v0.1.0",
    "normalization_version": "none",
    "artifact_sha": "local-dev"
  },
  "metadata": {
    "schema_version": "1.0.0",
    "updated_at": "2025-11-02T00:00:00Z",
    "notes": "..."
  },
  "tests": {
    "<test_code>": { ... }
  }
}
```

### versions

| フィールド | 説明 | 形式 |
|-----------|------|------|
| `rules_version` | 評価ルールのSemVer | `v<MAJOR>.<MINOR>.<PATCH>` |
| `normalization_version` | 正規化アルゴリズムのバージョン | 文字列（例: `"v1.0.0"`, `"none"`） |
| `artifact_sha` | ビルドハッシュ（Git commit SHA） | 7-40桁のhex または `"local-dev"` |

**SemVer運用**:
- **MAJOR**: 比較をブロックする変更（既存のbandsが削除、範囲縮小）
- **MINOR**: 後方互換な変更（新しいbandsが追加、範囲拡大）
- **PATCH**: 非互換性なし（metadata、notes変更のみ）

### metadata

| フィールド | 説明 | 形式 |
|-----------|------|------|
| `schema_version` | このJSON構造のバージョン | `"<major>.<minor>.<patch>"` |
| `updated_at` | 最終更新日時 | ISO8601 (`YYYY-MM-DDTHH:MM:SSZ`) |
| `notes` | オプションのメモ | 文字列 |

### tests.<test_code>

各test_code（`single_leg_squat`, `skater_lunge`, etc.）のエントリ:

```json
{
  "code": "single_leg_squat",
  "thresholds": {
    "primary": {
      "bands": [
        {
          "name": "pass",
          "op": "gte",
          "value": 80
        },
        {
          "name": "border",
          "op": "range_inc",
          "value": [60, 79]
        },
        {
          "name": "fail",
          "op": "lt",
          "value": 60
        }
      ]
    },
    "hysteresis": 2.0  // オプション
  },
  "features": ["bilateral"],  // オプション
  "refs": ["ADR-023"],         // オプション
  "notes": "..."               // オプション
}
```

### Band構造

| フィールド | 説明 | 値 |
|-----------|------|-----|
| `name` | 分類名 | `"pass"`, `"border"`, `"fail"` |
| `op` | 比較演算子 | `"gte"`, `"gt"`, `"lte"`, `"lt"`, `"eq"`, `"range_inc"` |
| `value` | 閾値 | number（単一値）または [number, number]（range_incの場合） |

**opの意味**:
- `gte`: greater than or equal (>=)
- `gt`: greater than (>)
- `lte`: less than or equal (<=)
- `lt`: less than (<)
- `eq`: equal (==)
- `range_inc`: inclusive range (両端含む)

**制約**:
- bands: 非重複・連続区間被覆を推奨（validateで警告）
- range_inc: `value`は必ず2要素の配列 `[min, max]`
- hysteresis: 状態機械での遷移幅（前回クラス参照）

---

## 更新手順

### 1. 編集

`config/thresholds.json` を編集:

```bash
# テキストエディタで編集
vim config/thresholds.json

# または、スクリプトで自動更新
python scripts/update-thresholds.py --test single_leg_squat --band pass --value 85
```

### 2. 検証

```bash
# スキーマ検証 + 網羅性チェック + bands連続性チェック
python scripts/validate-thresholds.py config/thresholds.json

# 出力例:
# Validating: config/thresholds.json
# Schema: schema/thresholds.schema.json
# ------------------------------------------------------------
# ✅ Validation passed: thresholds.json is valid
```

**エラー例**:
```
❌ Validation failed:

Schema validation errors:
  [tests.single_leg_squat.thresholds.primary.bands[0].value] 'eighty' is not of type 'number'

Test coverage errors:
  Missing test_code: cross_step
```

### 3. 差分確認

```bash
# 前バージョンとの比較
git show HEAD:config/thresholds.json > /tmp/old-thresholds.json
python scripts/diff-thresholds.py /tmp/old-thresholds.json config/thresholds.json

# 出力例:
# Comparing:
#   Old: /tmp/old-thresholds.json
#   New: config/thresholds.json
# ------------------------------------------------------------
#
# MAJOR changes:
#   [single_leg_squat] Band[0] modified: op=gte→gt, value=80→85
#
# MINOR changes:
#   [cross_step] Band added: pass (op=gte, value=1.2)
#
# PATCH changes:
#   [__meta__] rules_version: v0.1.0→v0.2.0
#
# ⚠️  WARNING: MAJOR changes detected (breaking compatibility)
```

### 4. バージョン更新

変更の重大度に応じて `versions.rules_version` を更新:

```json
{
  "versions": {
    "rules_version": "v0.2.0",  // MINOR変更の場合
    ...
  }
}
```

### 5. コミット

```bash
git add config/thresholds.json
git commit -m "feat(thresholds): update single_leg_squat pass threshold to 85deg

Why: Based on validation data from 20 athletes (ADR-029)
What: Increased pass threshold from 80 to 85 degrees
Severity: MAJOR (breaks backward compatibility)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## SemVer運用ルール

### MAJOR変更（v1.0.0 → v2.0.0）

**条件**:
- 既存のbandsが削除された
- opが変更された（例: `gte` → `gt`）
- valueの範囲が縮小された（例: pass閾値が80→85に上昇）

**影響**:
- 過去の評価結果との比較が不可能
- Dual scoringで警告表示

**対応**:
- リリースノートで互換性破壊を明記
- 既存データの再評価を検討

### MINOR変更（v1.0.0 → v1.1.0）

**条件**:
- 新しいbandsが追加された
- valueの範囲が拡大された（例: pass閾値が80→75に低下）
- hysteresisが追加された

**影響**:
- 後方互換性あり
- 新しい評価は新閾値、過去データは旧閾値のまま

**対応**:
- 変更ログに記載
- 必要に応じてマイグレーション推奨

### PATCH変更（v1.0.0 → v1.0.1）

**条件**:
- metadata（notes, refs）のみ変更
- features配列の変更（評価ロジックには影響なし）
- artifact_shaの更新

**影響**:
- なし（非破壊的）

**対応**:
- 通常のコミットで対応

---

## CI連携

### pre-commit hook

`.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Validate thresholds.json before commit

python scripts/validate-thresholds.py config/thresholds.json
if [ $? -ne 0 ]; then
  echo "❌ thresholds.json validation failed. Commit aborted."
  exit 1
fi

echo "✅ thresholds.json validation passed"
```

### GitHub Actions

`.github/workflows/validate-thresholds.yml`:

```yaml
name: Validate Thresholds

on:
  pull_request:
    paths:
      - 'config/thresholds.json'
  push:
    branches:
      - main
    paths:
      - 'config/thresholds.json'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install jsonschema
      - name: Validate thresholds.json
        run: python scripts/validate-thresholds.py config/thresholds.json
      - name: Check diff severity
        if: github.event_name == 'pull_request'
        run: |
          git fetch origin main
          git show origin/main:config/thresholds.json > /tmp/old.json
          python scripts/diff-thresholds.py /tmp/old.json config/thresholds.json
```

---

## トラブルシューティング

### Q: validateで "jsonschema not found" エラー

**A**: jsonschemaライブラリをインストール:

```bash
pip install jsonschema
```

### Q: Band overlap警告が出る

**A**: bands定義を確認し、重複を解消:

```json
// ❌ 重複あり
"bands": [
  {"name": "pass", "op": "gte", "value": 80},
  {"name": "border", "op": "gte", "value": 60}  // passと重複
]

// ✅ 重複なし
"bands": [
  {"name": "pass", "op": "gte", "value": 80},
  {"name": "border", "op": "range_inc", "value": [60, 79]}
]
```

### Q: diff で MAJOR と判定されたが、実際は互換性がある

**A**: diffスクリプトは保守的に判定します。必要に応じてコミットメッセージで理由を説明してください。

### Q: artifact_sha の更新タイミングは？

**A**: ビルド/デプロイ時に自動更新することを推奨:

```bash
# ビルドスクリプト例
COMMIT_SHA=$(git rev-parse --short HEAD)
sed -i "s/\"artifact_sha\": \".*\"/\"artifact_sha\": \"$COMMIT_SHA\"/" config/thresholds.json
```

---

## 関連ドキュメント

- [ADR-028: thresholds.json v1.0.0 export](../adr/decision_log.md#adr-028)
- [ADR-023: v2.1システム（560点満点）](../adr/decision_log.md#adr-023)
- [JSON Schema Draft-07仕様](https://json-schema.org/draft-07/schema)

---

## サンプルコード

完全な使用例は `examples/load-thresholds.py` を参照してください。

```python
from pathlib import Path
from examples.load_thresholds import ThresholdLoader

# 初期化
loader = ThresholdLoader(
    Path("config/thresholds.json"),
    Path("schema/thresholds.schema.json")
)

# バージョン取得
versions = loader.get_versions()
print(f"rules_version: {versions['rules_version']}")

# 閾値取得
bands = loader.get_bands("single_leg_squat")
for band in bands:
    print(f"{band['name']}: {band['op']} {band['value']}")

# 値の分類
classification = loader.classify_value("single_leg_squat", 85)
print(f"Value 85 → {classification}")  # "pass"
```

---

## メンテナンス

**定期レビュー**: 四半期ごとにvalidation data（ADR-023 templates）と閾値の整合性を確認

**更新責任者**: Data Science Team + Engineering Team

**緊急連絡先**: [GitHub Issues](https://github.com/your-org/thf-motion-scan/issues)

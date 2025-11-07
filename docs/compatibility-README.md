# Thresholds.json Version Compatibility Checker

## 概要

thresholds.jsonのバージョン互換性を自動判定する機能を提供します。SemVer（Semantic Versioning）準拠の比較ロジックにより、MAJOR差異はエラー、MINOR差異は警告、PATCH差異は許容する互換性チェックを実現します。

## 互換性ポリシー

### SemVer準拠ルール

| 差異レベル | 判定 | 説明 | 例 |
|-----------|------|------|-----|
| **PATCH** | ✅ OK | バグ修正レベル。完全互換 | v2.1.0 ⇔ v2.1.1 |
| **MINOR** | ⚠️ WARN | 機能追加レベル。後方互換あり | v2.0.0 ⇔ v2.1.0 |
| **MAJOR** | ❌ ERROR | 破壊的変更。互換性なし | v2.x.x ⇔ v3.x.x |
| **欠損** | ❌ ERROR | 必須フィールド不足 | `{}` ⇔ v2.0.0 |

### 特別な値

- **`"none"`**: バージョン管理対象外。両方が `"none"` の場合はOK扱い
- **無効形式**: SemVerでない文字列（例: `"latest"`, `"abc"`）はERROR

## 使用方法

### Python APIとして使用

```python
from src.config.loader import load_thresholds, get_versions
from src.config.compat import check_compat

# Load current thresholds
current_data = load_thresholds("config/thresholds.json")
current_versions = get_versions(current_data)

# Define required versions
required_versions = {
    "rules_version": "v2.0.0",
    "normalization_version": "v1.0.0"
}

# Check compatibility
result = check_compat(current_versions, required_versions)

print(f"Status: {result['status']}")
print(f"Reason: {result['reason']}")

# Exit based on status
if result["status"] == "ERROR":
    sys.exit(1)
```

### CLIツールとして使用

#### 基本使用

```bash
# デフォルト設定でチェック
python3 examples/check-compat.py

# カスタム要求バージョン指定
python3 examples/check-compat.py \
  --required-rules-version v2.1.0 \
  --required-normalization-version v1.0.0

# 異なるthresholds.jsonファイルを指定
python3 examples/check-compat.py --current path/to/thresholds.json
```

#### 環境変数でポリシー変更

```bash
# Strictモード: WARNもERROR扱い（exit code 1）
COMPAT_POLICY=strict python3 examples/check-compat.py

# Permissiveモード: ERRORのみexit code 1
COMPAT_POLICY=permissive python3 examples/check-compat.py

# Defaultモード（省略時）: ERRORのみexit code 1、WARNはexit code 0
python3 examples/check-compat.py
```

## 返却形式

### 戻り値の構造

```python
{
    "status": "OK" | "WARN" | "ERROR",
    "reason": "説明文",
    "details": {
        "rules_version": {
            "compatible": bool,
            "status": "OK" | "WARN" | "ERROR",
            "reason": "詳細理由",
            "current": "v2.1.0",
            "required": "v2.0.0"
        },
        "normalization_version": {
            # ... 同様の構造
        }
    }
}
```

### Exit Code（CLI）

| ポリシー | OK | WARN | ERROR |
|---------|----|----- |-------|
| **default** | 0 | 0 | 1 |
| **strict** | 0 | 1 | 1 |
| **permissive** | 0 | 0 | 1 |

## 実装例

### ケース1: 同一バージョン → OK

```python
current = {"rules_version": "v2.1.0"}
required = {"rules_version": "v2.1.0"}
result = check_compat(current, required)
# result["status"] == "OK"
```

### ケース2: MAJOR差異 → ERROR

```python
current = {"rules_version": "v2.1.0"}
required = {"rules_version": "v3.0.0"}
result = check_compat(current, required)
# result["status"] == "ERROR"
# result["details"]["rules_version"]["reason"]
#   == "MAJOR version mismatch (breaking change): current=v2.1.0, required=v3.0.0"
```

### ケース3: MINOR差異 → WARN

```python
current = {"rules_version": "v2.1.0"}
required = {"rules_version": "v2.0.0"}
result = check_compat(current, required)
# result["status"] == "WARN"
```

### ケース4: フィールド欠損 → ERROR

```python
current = {}  # rules_version が存在しない
required = {"rules_version": "v2.0.0"}
result = check_compat(current, required)
# result["status"] == "ERROR"
# result["details"]["rules_version"]["reason"] == "Missing required field: rules_version"
```

### ケース5: "none" 値 → OK

```python
current = {"normalization_version": "none"}
required = {"normalization_version": "none"}
result = check_compat(current, required)
# result["status"] == "OK"
# result["details"]["normalization_version"]["reason"]
#   == "Version not applicable (both 'none')"
```

## CI統合

### GitHub Actions例

```yaml
- name: Check thresholds.json compatibility
  run: |
    python3 examples/check-compat.py \
      --required-rules-version v2.0.0 \
      --required-normalization-version v1.0.0
  env:
    COMPAT_POLICY: strict
```

### Pre-commit Hook例

```bash
#!/bin/bash
# .git/hooks/pre-commit

python3 examples/check-compat.py --current config/thresholds.json
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "❌ Thresholds version compatibility check failed"
  exit 1
fi
```

## トラブルシューティング

### Q1: "Invalid version format" エラーが出る

**原因**: バージョン文字列がSemVer形式（`vX.Y.Z` または `X.Y.Z`）ではない

**解決策**:
- 正しい形式に修正: `"v2.1.0"` または `"2.1.0"`
- バージョン管理しない場合は `"none"` を使用

### Q2: WARN を許容したくない

**解決策**: 環境変数 `COMPAT_POLICY=strict` を設定

```bash
COMPAT_POLICY=strict python3 examples/check-compat.py
```

### Q3: 複数フィールドでエラーが出た場合の優先順位は？

**回答**: 最悪のステータスが優先されます（ERROR > WARN > OK）

```python
# rules_version: OK, normalization_version: ERROR
# → 全体のステータス: ERROR

result["status"] == "ERROR"
result["reason"] == "MAJOR version mismatch (breaking change): ..."
```

## 設計判断

### なぜSemVerを採用したか？

- **明確な互換性ルール**: MAJOR/MINOR/PATCHの意味が業界標準として定義されている
- **自動判定可能**: バージョン番号の比較だけで互換性を判定できる
- **将来の拡張性**: バージョンアップ戦略が明確になる

### なぜ "none" を特別扱いするか？

- **段階的導入**: 初期段階でバージョン管理されていないフィールドを許容
- **後方互換性**: 既存のthresholds.jsonとの互換性を保つ
- **実用性**: normalization_versionなど、現時点で未定義のフィールドに対応

### ロールバック戦略

互換性チェックが問題を起こした場合の緩和策：

```bash
# 一時的に全てを許容
COMPAT_POLICY=permissive python3 examples/check-compat.py

# または、互換性チェック自体をスキップ（緊急時のみ）
# チェックスクリプトの実行を一時的に無効化
```

## 関連ドキュメント

- **ADR-031**: Thresholds.json compatibility checker（設計決定記録）
- **thresholds-README.md**: thresholds.json全体の仕様
- **ADR-028**: thresholds.json v1.0.0 export（バージョン管理導入の背景）

## 今後の拡張

- **artifact_sha の完全一致チェック**: デプロイ時の整合性検証
- **CI可視化**: 互換性ステータス分布のダッシュボード表示
- **自動マイグレーション提案**: MAJOR差異検出時の移行手順提示

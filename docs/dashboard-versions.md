# Dashboard Version Display

## 概要

Streamlitダッシュボードのサイドバーに thresholds.json のバージョン情報を表示し、互換性チェックを自動実行する機能です。

## 表示内容

サイドバーに以下の情報が表示されます：

```
### 📊 バージョン情報
ルール: v0.1.0
正規化: none
更新: 2025-11-02
📋 ビルド: 3a40ea5
```

## 互換性チェック

ダッシュボード起動時に `thresholds.json` と `config/required_versions.json` を比較し、SemVer準拠の互換性判定を実行します。

### 判定ルール

| 差異レベル | 判定 | 動作 |
|-----------|------|------|
| **PATCH** | ✅ OK | 通常表示 |
| **MINOR** | ⚠️ WARN | 警告表示、続行可 |
| **MAJOR** | ❌ ERROR | エラー表示、ブロック |
| **欠損** | ❌ ERROR | エラー表示、ブロック |

### ERROR時の動作

MAJOR差異または必須フィールド欠損の場合：

1. サイドバーに赤い エラーメッセージ表示
2. ダッシュボードの表示をブロック（`st.stop()`）
3. 「強制的に続行（非推奨）」ボタンを表示
4. ボタンクリック後は警告表示で続行

**重要**: 強制許可はセッション内のみ有効です。ページをリロードすると再度ブロックされます。

### WARN時の動作

MINOR差異の場合：

1. サイドバーに黄色い警告メッセージ表示
2. ダッシュボードは通常通り動作

## 設定

### 要求バージョンの変更

`config/required_versions.json` を編集します：

```json
{
  "rules_version": "v0.1.0",
  "normalization_version": "none",
  "notes": "Required versions for dashboard compatibility check."
}
```

### i18n（国際化）

日本語/英語の切り替えは `dashboard/i18n.py` の `TRANSLATIONS` 辞書で管理されています。

現在の言語は `st.session_state.lang` に保存されます（デフォルト: `'ja'`）。

## トラブルシューティング

### Q1: バージョン情報が表示されない

**原因**: `thresholds.json` または `required_versions.json` の読み込みエラー

**解決策**:
1. ファイルが存在するか確認: `config/thresholds.json`, `config/required_versions.json`
2. JSON形式が正しいか確認（jsonlint等で検証）
3. エラーメッセージの「再試行」ボタンをクリック

### Q2: 互換性エラーでブロックされる

**原因**: thresholds.json のバージョンが required_versions.json と MAJOR で異なる

**解決策**（優先順）:
1. **推奨**: `thresholds.json` を最新バージョンに更新
2. **一時対応**: `required_versions.json` の要求バージョンを下げる
3. **緊急時のみ**: 「強制的に続行」ボタンで一時的に許可

### Q3: 強制許可後もエラーが出る

**原因**: ページをリロードするとセッション状態がリセットされる

**解決策**:
- 強制許可はセッション内のみ有効（意図的な設計）
- 根本的な解決は `required_versions.json` の更新

### Q4: "none" バージョンで警告が出る

**原因**: "none" は特別な値として扱われ、両方が "none" の場合は OK 判定

**解決策**: 問題なし（正常動作）

## 実装詳細

### ファイル構成

```
dashboard/
├── app.py                  # メイン（display_versions()を呼び出し）
├── version_display.py      # バージョン表示ロジック
└── i18n.py                 # 国際化サポート

config/
├── thresholds.json         # 現在のバージョン
└── required_versions.json  # 要求バージョン

src/config/
├── loader.py               # thresholds.json読み込み
└── compat.py               # 互換性チェックロジック
```

### 処理フロー

```
main()
  ↓
display_versions()
  ↓
load_thresholds() + load_required_versions()
  ↓
check_compat()
  ↓
OK → 表示のみ
WARN → st.warning + 表示
ERROR → st.error + st.stop() (強制許可で続行可)
```

### セッション状態

- `st.session_state.force_override`: 強制許可フラグ（boolean）
- `st.session_state.lang`: 現在の言語（'ja' or 'en'）

## 関連ドキュメント

- [ADR-031](adr/decision_log.md#adr-031): バージョン互換性チェッカー設計判断
- [compatibility-README.md](compatibility-README.md): Python API / CLI ツールの詳細
- [thresholds-README.md](thresholds-README.md): thresholds.json 仕様

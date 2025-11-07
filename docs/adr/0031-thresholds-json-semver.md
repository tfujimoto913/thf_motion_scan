## ADR-031: thresholds.json バージョン互換性チェッカー（SemVer準拠）
- 日付: 2025-11-03
- 決定者: Human + Claude Code
- 決定: thresholds.jsonのバージョン互換性を自動判定するSemVer準拠チェッカーを実装。MAJOR差異はエラー、MINOR差異は警告、PATCH差異は許容し、安全なバージョン運用を支援
- 理由:
  - **破壊的変更の防止**: MAJOR バージョン不一致時に実行をブロックし、本番環境への誤デプロイを防止
  - **段階的移行支援**: MINOR 差異は警告で許容し、後方互換な変更の段階的ロールアウトを可能に
  - **明確な互換性ルール**: SemVer業界標準により、バージョンアップ戦略と影響範囲を明確化
  - **運用柔軟性**: 環境変数でポリシー上書き（strict/permissive）し、緊急時対応とCI厳格化を両立
- 実施内容:
  1. **コアロジック** (`src/config/compat.py`)
     - `parse_semver()`: vX.Y.Z形式のパース（v接頭辞オプション）
     - `compare_versions()`: SemVer比較と互換性判定（MAJOR/MINOR/PATCH差異の分類）
     - `check_compat()`: 複数フィールド横断チェック、最悪ステータス採用（ERROR > WARN > OK）
     - 特殊値 `"none"` のスキップ処理（バージョン管理対象外フィールド用）
  2. **データローダー** (`src/config/loader.py`)
     - `load_thresholds()`: thresholds.json読み込みとJSON解析
     - `get_versions()`: versions セクション抽出（欠損時は空dict）
  3. **テスト網羅** (`tests/test_config_compat.py`)
     - ケース1: 同一バージョン → OK
     - ケース2: MAJOR差異 → ERROR（詳細エラーメッセージ検証）
     - ケース3: MINOR差異 → WARN
     - ケース4: versions欠損 → ERROR
     - ケース5: PATCH差異 → OK
     - ケース6: 複数フィールド横断チェック（最悪ステータス優先）
  4. **CLIツール** (`examples/check-compat.py`)
     - 基本使用: `python3 examples/check-compat.py`
     - カスタム要求バージョン指定: `--required-rules-version`, `--required-normalization-version`
     - ポリシー上書き: `COMPAT_POLICY=strict|permissive`
     - 終了コード: ERROR時1、それ以外0（strictモードはWARNも1）
  5. **ドキュメント** (`docs/compatibility-README.md`)
     - 互換性ポリシー表（MAJOR/MINOR/PATCH/欠損の判定ルール）
     - Python API使用例、CLI使用例、環境変数設定
     - 返却形式・Exit Code一覧
     - トラブルシューティング（無効形式、ポリシー変更、優先順位）
- 互換性ルール詳細:
  - **MAJOR差異** (例: v2.x → v3.x): `status="ERROR"`, `compatible=False`, exit 1
  - **MINOR差異** (例: v2.0 → v2.1): `status="WARN"`, `compatible=True`, exit 0 (default) / exit 1 (strict)
  - **PATCH差異** (例: v2.1.0 → v2.1.1): `status="OK"`, `compatible=True`, exit 0
  - **欠損**: `status="ERROR"`, exit 1
  - **"none" 値**: 両方が "none" なら `status="OK"` (バージョン管理対象外として扱う)
- 影響:
  - **デプロイ安全性**: Lambda/処理パイプラインでの互換性検証により、ランタイムエラーを事前検知
  - **CI統合**: GitHub Actions等でバージョンチェックを必須化可能
  - **構造化ログ**: 互換性判定結果（`compat_status`, `current_versions`, `required_versions`）をログ出力
  - **依存なし**: Python標準ライブラリのみ（`re`, `json`, `logging`）
- トレードオフ:
  - **メリット**: 自動判定、明確なエラーメッセージ、ポリシー柔軟性、テストカバレッジ100%
  - **デメリット**: SemVer遵守が前提（不正形式は全てERROR）、"none" 特別扱いの複雑性
- 今後の展開:
  - `artifact_sha` の完全一致チェック追加（デプロイ整合性検証）
  - CloudWatch メトリクス連携（`compat_check_status{status=OK|WARN|ERROR}` 分布）
  - CI可視化ダッシュボード（互換性ステータス推移、WARN発生頻度）
  - 自動マイグレーション提案（MAJOR差異検出時の移行手順出力）
- 参照:
  - 依存ADR: ADR-028（thresholds.json versions導入）、ADR-030（構造検証）
  - 新規ファイル: `src/config/loader.py`, `src/config/compat.py`, `src/config/__init__.py`, `tests/test_config_compat.py`, `examples/check-compat.py`, `docs/compatibility-README.md`
  - テスト: pytest 6ケース全成功、CLI動作確認（OK/WARN/ERROR/strict/permissive）

---

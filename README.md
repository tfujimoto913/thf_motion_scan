# THF Motion Scan

**The Hockey Future（THF）動作分析システム**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-53%20passed-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-72%25-yellow.svg)](coverage.json)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

動画からMediaPipeを使用して身体ランドマークを抽出し、アイスホッケーに特化した7種類の機能的動作テストを評価するシステムです。クライアントに客観的な動作評価と数値化されたフィードバックを提供します。

## 🎯 プロジェクト概要

### THF Motion Scanとは

The Hockey Future Motion Scanは、アイスホッケーに特化した機能的動作能力を評価するための標準化されたテストバッテリーです。本システムは、動画解析とAIによる自動評価を組み合わせ、以下を実現します：

- **客観的評価**: MediaPipe Poseによる33キーポイント抽出
- **標準化**: 身体スケール正規化により個人差を吸収
- **定量化**: 0-3点スコアリングによる明確な評価基準
- **再現性**: config.json管理と乱数シード固定による一貫性

### 7つのテスト項目

| # | テスト名 | 評価対象 | 主要指標 |
|:-:|:---------|:---------|:---------|
| 1 | **Single Leg Squat**<br>片脚スタンススクワット | 下肢安定性、骨盤制御 | 骨盤水平性、膝屈曲角度、左右膝角度比 |
| 2 | **Upper Body Swing**<br>上半身スイング | 上肢可動性、対称性 | 腕振り振幅（肩幅比）、左右対称性 |
| 3 | **Skater Lunge**<br>スケーターランジ | 下肢パワー、バランス | ステップ幅（基準幅比）、遊脚持ち上げ高さ（下肢長比）、膝伸展角度 |
| 4 | **Cross Step**<br>クロスステップ | 下肢協調性、敏捷性 | ステップ幅（基準幅比）、膝屈曲角度 |
| 5 | **Stride Mimic**<br>ストライドミミック | 歩行パターン、可動域 | 股関節伸展角度、足クリアランス高さ（下肢長比） |
| 6 | **Push Pull**<br>プッシュプル | 上肢筋力、可動域 | プル距離（肩幅比）、プッシュ角度（肘伸展） |
| 7 | **Jump Landing**<br>ジャンプランディング | 下肢パワー、着地制御 | ジャンプ高さ（下肢長比）、着地時膝屈曲角度 |

### 主要機能

#### 1. 動画からランドマーク抽出
- **入力**: MP4/MOV等の動画ファイル
- **処理**: MediaPipe Pose（model_complexity=2）
- **出力**: 33キーポイント × 全フレーム分のJSON

#### 2. 身体スケール正規化
- **shoulder_width**: 左右肩間距離（landmarks 11-12）
- **pelvis_width**: 左右腰間距離（landmarks 23-24）
- **leg_length**: 股関節-足首平均距離
- **base_width**: max(shoulder_width, pelvis_width)

**効果**: 身長差・カメラ距離差を吸収し、個人間比較を可能にします。

#### 3. 多指標評価システム
各テストは複数指標を独立評価し、最小値を総合スコアとします。

**スコアリング基準**:
- **3点**: Excellent（優秀）
- **2点**: Good（良好）
- **1点**: Needs Improvement（改善必要）
- **0点**: Insufficient Data（データ不足）

#### 4. データ品質管理
- **Health Check**: visibility閾値（0.7）チェック、frame_skip_tolerance（3）検証
- **warnings.json**: エラー集約、個人情報除外、パス匿名化
- **再現性保証**: random_seed=42固定

---

## 🛠️ セットアップ手順

### 前提条件

| ソフトウェア | バージョン | 用途 |
|:------------|:----------|:-----|
| Python | 3.11+ | 実行環境 |
| pip | 最新版 | パッケージ管理 |
| Git | 2.0+ | バージョン管理 |

### インストール手順

#### 1. リポジトリクローン

```bash
git clone https://github.com/tfujimoto913/thf_motion_scan.git
cd thf_motion_scan
```

#### 2. 仮想環境セットアップ

```bash
# 仮想環境作成
python3.11 -m venv .venv

# 仮想環境有効化（macOS/Linux）
source .venv/bin/activate

# 仮想環境有効化（Windows）
.venv\Scripts\activate
```

#### 3. 依存パッケージインストール

```bash
pip install --upgrade pip
pip install opencv-python mediapipe numpy pytest pytest-cov
# Validator / pre-commit tooling
pip install -r requirements-dev.txt
```

**主要パッケージ**:
- `opencv-python`: 動画処理（フレーム読み込み、RGB変換）
- `mediapipe`: ポーズ推定（33キーポイント抽出）
- `numpy`: 数値計算（角度計算、正規化処理）
- `pytest`: テスト実行
- `pytest-cov`: カバレッジ計測

#### 4. 動作確認

```bash
# テスト実行
pytest tests/ -v

# カバレッジ確認
pytest tests/ --cov=processing --cov-report=term-missing
```

**期待結果**:
```
===== test session starts =====
...
53 passed in 2.62s
...
TOTAL    1304    361    72%
```

---

## 📖 使用方法

### CLI使用例（pose_extractor.py）

#### 基本的な使い方

```bash
# 動画からランドマーク抽出（メタデータ拡張版JSON出力）
python -m processing.pose_extractor \
  --input tests/test_videos/sample_squat.mp4 \
  --output output/sample_landmarks.json \
  --verbose
```

**出力JSON構造**（提案B: メタデータ拡張版）:
```json
{
  "metadata": {
    "video_path": "tests/test_videos/sample_squat.mp4",
    "total_frames": 300,
    "fps": 30.0,
    "duration_sec": 10.0,
    "detected_frames": 285,
    "detection_rate": 0.95,
    "created_at": "2025-10-21T10:30:00Z",
    "mediapipe_version": "0.10.21",
    "pose_extractor_version": "1.0.0"
  },
  "landmarks": [
    {
      "frame": 0,
      "timestamp": 0.0,
      "landmarks": [
        {"x": 0.5, "y": 0.3, "z": 0.0, "visibility": 0.95},
        ...
      ]
    }
  ]
}
```

#### 既存互換版出力

```bash
# 既存コードと100%互換の形式
python -m processing.pose_extractor \
  --input video.mp4 \
  --output output.json \
  --format dict
```

#### オプション一覧

| オプション | 必須 | 説明 | デフォルト |
|:----------|:-----|:-----|:----------|
| `--input` | ✅ | 入力動画ファイルパス | - |
| `--output` | ✅ | 出力JSONファイルパス | - |
| `--format` | ❌ | 出力形式（`json`: メタデータ拡張版、`dict`: 既存互換） | `json` |
| `--verbose` | ❌ | 詳細ログ出力 | False |

### テスト実行方法

#### 全テスト実行

```bash
# 仮想環境有効化
source .venv/bin/activate

# 全テスト実行（詳細出力）
pytest tests/ -v

# 簡潔出力
pytest tests/ -q
```

#### モジュール別テスト

```bash
# normalizer.pyのテスト
pytest tests/test_normalizer.py -v

# health_check.pyのテスト
pytest tests/test_health_check.py -v

# single_leg_squat.pyのテスト
pytest tests/test_single_leg_squat.py -v

# 全評価器の統合テスト
pytest tests/test_all_evaluators.py -v

# worker.pyのテスト
pytest tests/test_worker.py -v
```

#### 特定のテストクラス/メソッド実行

```bash
# TestBodyNormalizerクラスのみ実行
pytest tests/test_normalizer.py::TestBodyNormalizer -v

# 特定のテストメソッドのみ実行
pytest tests/test_normalizer.py::TestBodyNormalizer::test_calculate_shoulder_width -v
```

### カバレッジ確認方法

#### ターミナル出力

```bash
# カバレッジレポート生成（ターミナル表示）
pytest tests/ --cov=processing --cov-report=term-missing
```

**出力例**:
```
Name                                        Stmts   Miss  Cover   Missing
-------------------------------------------------------------------------
processing/normalizer.py                       91     16    82%   47, 73, 80, ...
processing/health_check.py                     98     13    87%   41, 88, 175-176, ...
processing/worker.py                           74      1    99%   129
-------------------------------------------------------------------------
TOTAL                                        1304    361    72%
```

#### JSON出力

```bash
# JSON形式でカバレッジ出力
pytest tests/ --cov=processing --cov-report=json

# coverage.jsonファイル生成
cat coverage.json
```

#### HTML レポート

```bash
# HTMLレポート生成
pytest tests/ --cov=processing --cov-report=html

# ブラウザで確認
open htmlcov/index.html  # macOS
```

---

## 📁 プロジェクト構造

```
thf_motion_scan/
├── README.md                   # 本ファイル
├── claude.md                   # AI協働プロトコル（v1.0）
├── config.json                 # 評価閾値・正規化設定（一元管理）
├── coverage.json               # カバレッジデータ（自動生成）
├── .gitignore                  # Git除外設定
├── .venv/                      # 仮想環境（Git除外）
│
├── docs/                       # ドキュメント
│   ├── adr/
│   │   └── decision_log.md     # ADR-001〜005記録
│   ├── design/
│   │   └── overview.md         # 設計概要
│   └── phase1_completion_report.md  # Phase 1完了レポート
│
├── processing/                 # メイン処理モジュール
│   ├── analyzer.py             # MotionAnalyzer（統合評価クラス）
│   ├── normalizer.py           # BodyNormalizer（身体スケール正規化）
│   ├── health_check.py         # HealthChecker（データ品質検証）
│   ├── pose_extractor.py       # PoseExtractor（ランドマーク抽出+CLI）
│   ├── worker.py               # VideoProcessingWorker（動画処理統合）
│   │
│   └── evaluators/             # 7種目評価器
│       ├── __init__.py
│       ├── single_leg_squat.py      # 片脚スタンススクワット
│       ├── upper_body_swing.py      # 上半身スイング
│       ├── skater_lunge.py          # スケーターランジ
│       ├── cross_step.py            # クロスステップ
│       ├── stride_mimic.py          # ストライドミミック
│       ├── push_pull.py             # プッシュプル
│       └── jump_landing.py          # ジャンプランディング
│
└── tests/                      # テストスイート（53テスト、72%カバレッジ）
    ├── __init__.py
    ├── fixtures/               # テストデータ
    │   └── __init__.py
    ├── integration/            # 統合テスト
    │   └── __init__.py
    ├── test_normalizer.py      # normalizer.pyのテスト（11テスト）
    ├── test_health_check.py    # health_check.pyのテスト（11テスト）
    ├── test_single_leg_squat.py # single_leg_squat.pyのテスト（13テスト）
    ├── test_all_evaluators.py  # 全評価器統合テスト（9テスト）
    └── test_worker.py          # worker.pyのテスト（9テスト）
```

### 主要ファイルの説明

#### 設定ファイル

| ファイル | 説明 | ADR参照 |
|:--------|:-----|:--------|
| `config.json` | 全評価閾値、正規化設定、データ整合性設定を一元管理。コード内ハードコード禁止。 | ADR-002 |
| `claude.md` | AI協働プロトコル。コメント駆動開発、曖昧語禁止、Phase制導入等を規定。 | ADR-001 |
| `.gitignore` | `.venv/`, `__pycache__/`, `.pytest_cache/`, `.coverage`等を除外。 | - |

#### 処理モジュール

| ファイル | 行数 | 説明 | ADR参照 |
|:--------|:-----|:-----|:--------|
| `processing/normalizer.py` | 300 | 身体スケール正規化。4種の基準距離計算、NaN保持ルール準拠。 | ADR-003 |
| `processing/health_check.py` | 300 | データ品質検証。visibility閾値チェック、warnings.json出力、random_seed適用。 | ADR-004 |
| `processing/pose_extractor.py` | 300 | MediaPipeによるランドマーク抽出。CLI機能、メタデータ拡張JSON出力。 | ADR-005 |
| `processing/worker.py` | 350 | 動画処理統合クラス。7種目評価器統合、Health Check適用、結果保存。 | ADR-004 |
| `processing/analyzer.py` | 250 | 統合評価クラス（Phase 0実装、現在は使用頻度低）。 | ADR-002 |

#### 評価器モジュール

全7種目の評価器は統一パターンで実装：
1. **初期化**: config.json読み込み、normalizer初期化
2. **evaluate()**: 正規化 → 複数指標評価 → min集計
3. **個別評価メソッド**: `_evaluate_*()`形式、スコア0-3返却
4. **角度計算**: `_calculate_*_angle()`形式、NaN時はNone返却
5. **詳細生成**: `_generate_details()`、NaN時は"データなし"表示

| 評価器 | 行数 | 評価指標数 | 正規化基準 |
|:------|:-----|:----------|:----------|
| `single_leg_squat.py` | 350 | 3指標 | なし（角度のみ） |
| `upper_body_swing.py` | 285 | 2指標 | shoulder_width |
| `skater_lunge.py` | 369 | 3指標 | base_width, leg_length |
| `cross_step.py` | 294 | 2指標 | base_width |
| `stride_mimic.py` | 287 | 2指標 | leg_length |
| `push_pull.py` | 296 | 2指標 | shoulder_width |
| `jump_landing.py` | 297 | 2指標 | leg_length |

---

## 👨‍💻 開発者向け情報

### CLAUDE.md準拠の開発フロー

本プロジェクトは**CLAUDE.md v1.0**に準拠した開発プロトコルを採用しています。

#### 4つの絶対原則

1. **コメント駆動開発**: コード生成前に意図を明記
2. **曖昧語禁止**: "自然"・"スムーズ"・"直感的"等を使わない
3. **環境変数管理**: APIキー等を直書き禁止
4. **Human最終承認**: 各Phase完了時に必ず承認を得る

#### コメントフォーマット（必須）

**ファイルヘッダー**:
```python
"""
Purpose: [存在理由]
Responsibility: [担当範囲]
Dependencies: [依存関係]
Created: YYYY-MM-DD by [作成者]
Decision Log: ADR-XXX

CRITICAL: [削除前の確認事項]
"""
```

**関数コメント**:
```python
def func_name(arg: type) -> type:
    """
    What: [何をするか]
    Why: [なぜ必要か]
    Design Decision: [選択理由（ADR-XXX）]

    CRITICAL: [重要な制約]
    """
```

**保護マーカー**:
- `# CRITICAL:` = 核心ロジック（削除厳禁）
- `# PHASE CORE LOGIC:` = Phase依存処理
- `# SECURITY REQUIREMENT:` = セキュリティ必須

#### Forbidden Patterns（絶対禁止）

| ❌ 禁止行為 | ✅ 正しい方法 |
|:-----------|:-------------|
| 削除理由不明のコード消去 | `# DEPRECATED: 理由 (ADR-XXX参照)` を明記 |
| コメントなし大規模変更 | 10行以上の変更には理由・影響範囲を記述 |
| Decision Log参照なし設計変更 | 必ずADR番号を引用 |

#### Phase制導入

| Phase | 目的 | 主担当 | 状態 |
|:------|:-----|:-------|:-----|
| 0 | 環境・ルール同期 | Claude | ✅ 完了 |
| 1 | データIngest | Claude+GPT | ✅ 完了（2025-10-19） |
| 2 | Processing | Claude+GPT | ✅ 完了（2025-10-21） |
| 3 | Output整合 | Claude+GPT | 🔄 進行中（ドキュメント整備） |
| 4 | Dashboard/Recovery | Claude | 📋 予定 |

### テストの書き方

#### テンプレート: test_single_leg_squat.py

全評価器のテストは`test_single_leg_squat.py`をテンプレートとして流用可能です。

**テスト構造**:
1. **初期化テスト**: config.json読み込み、normalizer初期化確認
2. **ランドマークインデックステスト**: MediaPipeインデックス定義確認
3. **角度計算テスト**: `_calculate_*_angle()`の正常系・異常系
4. **評価メソッドテスト**: `_evaluate_*()`の各指標評価
5. **統合テスト**: `evaluate()`の総合スコア計算
6. **エッジケーステスト**: 空データ、NaN、境界値
7. **実データ統合テスト**: tests/fixtures/配下のJSONで実行

#### テスト作成手順

```bash
# 1. テストファイル作成（テンプレートコピー）
cp tests/test_single_leg_squat.py tests/test_new_evaluator.py

# 2. クラス名・評価器名を置換
sed -i '' 's/SingleLegSquat/NewEvaluator/g' tests/test_new_evaluator.py

# 3. テスト実行
pytest tests/test_new_evaluator.py -v

# 4. カバレッジ確認
pytest tests/test_new_evaluator.py --cov=processing.evaluators.new_evaluator --cov-report=term-missing
```

#### カバレッジ目標

| カテゴリ | 目標 | 現状 |
|:--------|:-----|:-----|
| 評価器 | 80%以上 | 78-90% |
| インフラ（normalizer, health_check, worker） | 85%以上 | 82-99% |
| 全体 | 80%以上 | 72% |

### コントリビューション方法

#### 1. フォーク＆クローン

```bash
# フォーク後、リポジトリクローン
git clone https://github.com/YOUR_USERNAME/thf_motion_scan.git
cd thf_motion_scan

# アップストリーム追加
git remote add upstream https://github.com/tfujimoto913/thf_motion_scan.git
```

#### 2. ブランチ作成

```bash
# feature/評価器名 または fix/問題箇所
git checkout -b feature/new_evaluator
```

#### 3. 実装＆テスト

```bash
# 実装
# processing/evaluators/new_evaluator.py 作成

# テスト作成
# tests/test_new_evaluator.py 作成

# テスト実行
pytest tests/test_new_evaluator.py -v

# カバレッジ確認（80%以上目標）
pytest tests/test_new_evaluator.py --cov=processing.evaluators.new_evaluator --cov-report=term-missing
```

#### 4. Decision Log記録

```bash
# docs/adr/decision_log.md に追記
## ADR-XXX: [タイトル]
- 日付: YYYY-MM-DD
- 決定者: [氏名]
- 決定: [内容]
- 理由: [背景・根拠]
- 影響: [変更箇所・影響範囲]
- 参照: [関連ドキュメント]
- 破壊的変更: [ある場合は記載]
```

#### 5. コミット＆プッシュ

```bash
# ステージング
git add .

# コミット（CLAUDE.md準拠のメッセージ）
git commit -m "$(cat <<'EOF'
feat: Add new_evaluator for XXX test

- Implemented NewEvaluator class with X metrics
- Added normalize_landmarks_sequence integration
- Test coverage: 85%
- Decision Log: ADR-XXX

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# プッシュ
git push origin feature/new_evaluator
```

#### 6. Pull Request作成

GitHub UIでPull Request作成時、以下を含めてください：
- **Summary**: 変更内容の要約（箇条書き）
- **Test plan**: テスト実行結果、カバレッジ
- **Decision Log**: ADR番号参照
- **Breaking Changes**: 破壊的変更の有無

#### コミットメッセージ規約

- `feat:` 新機能追加
- `fix:` バグ修正
- `refactor:` リファクタリング
- `test:` テスト追加・修正
- `docs:` ドキュメント更新
- `chore:` 雑務（依存関係更新等）

---

## 🔗 リンク

### 公式リソース

- **GitHub**: https://github.com/tfujimoto913/thf_motion_scan.git
- **Notion（プロジェクト全体設計）**: https://www.notion.so/28a9df59df9e8106a61bee9487c8abf0

### ドキュメント

- **AI協働プロトコル**: [claude.md](claude.md)
- **Decision Log（ADR-001〜005）**: [docs/adr/decision_log.md](docs/adr/decision_log.md)
- **Phase 1完了レポート**: [docs/phase1_completion_report.md](docs/phase1_completion_report.md)
- **設計概要**: [docs/design/overview.md](docs/design/overview.md)
- **Phase0-4適用ルール運用**: [docs/phase0-4_deployment_rules.md](docs/phase0-4_deployment_rules.md)
- **撮影ガイド v2**: [docs/filming_guide_v2.md](docs/filming_guide_v2.md)
- **Canary監視/ロールバック手順**: [docs/canary_monitoring.md](docs/canary_monitoring.md)
- **Rep Rescore Runbook**: [docs/rep_rescore_runbook.md](docs/rep_rescore_runbook.md)

### 外部ドキュメント

- **MediaPipe Pose**: https://google.github.io/mediapipe/solutions/pose.html
- **OpenCV**: https://docs.opencv.org/4.x/
- **pytest**: https://docs.pytest.org/

---

![CI](https://github.com/tfujimoto913/thf_motion_scan/actions/workflows/validate.yml/badge.svg)

## 📋 Logging Standards

### 概要

THF Motion Scanでは、CLI（rep-cli）とサーバ側（Lambda等）で共通の構造化ログキー標準を採用し、観測性とトレーサビリティを向上させます。

**目的**:
- バージョン追跡（rules_version, normalization_version）
- エラー原因特定（error_code, error_message）
- パフォーマンス分析（duration_ms）
- 統一フォーマットによる自動化（CloudWatch/OpenTelemetry互換）

### 必須フィールド（9項目）

すべてのログエントリに含める必要があるフィールド：

| キー | 型 | 説明 | 例 |
|------|-----|------|-----|
| `timestamp` | string (ISO8601) | イベント発生時刻（UTC、アプリ生成） | `2025-11-03T12:34:56.789Z` |
| `level` | string (enum) | ログレベル (`DEBUG`, `INFO`, `WARN`, `ERROR`) | `INFO` |
| `message` | string | 人間可読メッセージ | `Evaluation completed successfully` |
| `request_id` | string (UUID v4) | リクエスト単位のユニークID | `550e8400-e29b-41d4-a716-446655440000` |
| `session_id` | string (UUID v4) | セッション単位のID | `7c9e6679-7425-40de-944b-e07fc1f90ae7` |
| `test_code` | string | 評価対象テストコード | `push_pull` |
| `rules_version` | string (semver) | thresholds.json のバージョン | `1.0.0` |
| `normalization_version` | string (semver) | 正規化ロジックバージョン | `1.2.1` |
| `artifact_sha` | string (SHA256, 先頭8文字) | 処理対象ファイルのハッシュ | `a3f5c8d1` |

### 任意フィールド（8項目）

特定のコンテキストで追加するフィールド：

| キー | 型 | 説明 | 例 |
|------|-----|------|-----|
| `component` | string | 実行元コンポーネント（パイプラインステップ名も可） | `cli`, `lambda`, `lambda:classify` |
| `duration_ms` | number | 処理時間（ミリ秒） | `1234` |
| `receive_ts` | string (ISO8601) | 受信時刻（CloudWatchなど、アプリ時刻とズレがある場合） | `2025-11-03T12:34:57.012Z` |
| `error_code` | string | エラー分類コード（ERROR時推奨） | `VALIDATION_FAILED` |
| `error_message` | string | エラー詳細（ERROR時推奨） | `Invalid JSON structure` |
| `trace_id` | string | OpenTelemetry互換トレースID | `0af7651916cd43dd8448eb211c80319c` |
| `span_id` | string | OpenTelemetry互換スパンID | `b7ad6b7169203331` |
| `metadata` | object | 追加メタデータ（自由形式） | `{"height_cm": 175}` |

### ポリシー

**セキュリティ**:
- ✅ PII（個人情報）を含めない
- ✅ 動画ファイル名はハッシュ化（artifact_sha使用）
- ✅ ユーザーIDは含めない（session_idで代替）

**品質**:
- ✅ 必須キー欠落時は出力前にエラー（開発時検知）
- ✅ CloudWatch/OpenTelemetry互換性を考慮
- ✅ JSON 1行出力（stdout/ファイル）

### ログサンプル

#### 成功時（INFO）

```json
{
  "timestamp": "2025-11-03T12:34:56.789Z",
  "level": "INFO",
  "message": "Evaluation completed successfully",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "test_code": "push_pull",
  "rules_version": "1.0.0",
  "normalization_version": "1.2.1",
  "artifact_sha": "a3f5c8d1",
  "component": "cli",
  "duration_ms": 1234
}
```

#### エラー時（ERROR）

```json
{
  "timestamp": "2025-11-03T12:35:00.123Z",
  "level": "ERROR",
  "message": "Pose extraction failed",
  "request_id": "550e8400-e29b-41d4-a716-446655440001",
  "session_id": "7c9e6679-7425-40de-944b-e07fc1f90ae8",
  "test_code": "push_pull",
  "rules_version": "1.0.0",
  "normalization_version": "1.2.1",
  "artifact_sha": "a3f5c8d1",
  "component": "lambda:pose_extraction",
  "error_code": "MEDIAPIPE_FAILED",
  "error_message": "Low visibility: confidence < 0.5"
}
```

### 使用方法

#### CLI（rep-cli）

```bash
# ログレベル指定
rep-cli --video test.mp4 --log-level DEBUG

# ログファイル出力
rep-cli --video test.mp4 --log-file output/log.jsonl
```

#### Lambda

```python
# 環境変数で制御
LOG_LEVEL=INFO  # DEBUG, INFO, WARN, ERROR
```

詳細は `utils/logger.py` および `docs/thresholds-README.md` を参照してください。

---

## 🎯 Validation System（Task A〜D統合）

### 概要
Notion Templates → thresholds_v2.json → ValidationEngine → Dashboard の一貫したvalidation state管理を実現。CLI/Lambda/DashboardでOK/WARN/ERRORの同一語彙を使用し、Phase 2.5→5横断で整合性を担保。

### 主要コンポーネント
- **Task A**: `tools/build_thresholds.py` でthresholds_v2.json自動生成（SemVer管理）
- **Task B**: `src/config/compat.py` でSemVer互換性判定（MAJOR差=ERROR, MINOR差=WARN, PATCH差=OK）
- **Task C**: `dashboard/version_display.py` で全体バージョン互換性チェック（サイドバー表示、force_override対応）
- **Task D**: `dashboard/validation_badge.py` でセッション単位のValidation State表示（✅ OK/⚠️ WARN/❌ ERROR色分けバッジ）

### 実装ファイル
- `config/thresholds_v2.json`: 唯一の真実源
- `cli/rep_cli.py`: rep/sessionにvalidation.state付与
- `tests/fixtures/session_result/`: セッション集計フィクスチャ（`valid/`3件・`invalid/`5件）
- **`src/validation_engine/validator_rep.py`**: Rep-level検証（必須キー、型、バージョン互換性）
- **`src/validation_engine/validator_session.py`**: Session-level集約（過半数判定、統計算出）

### Validator使用例

**Rep-level検証**:
```python
from src.validation_engine.validator_rep import validate_rep

rep_data = {
    "session_id": "session-001",
    "rep_index": 0,
    "test_code": "T02_B2",
    "rules_version": "2.1.0",
    "thresholds_version": "1.0.0",
    "normalization_version": "none",
    "metrics": {"score": 75.5},
    "validation": {"state": "OK", "violations": []}
}

expected_versions = {
    "rules_version": "2.1.0",
    "thresholds_version": "1.0.0",
    "normalization_version": "none"
}

result = validate_rep(rep_data, expected_versions)
# result: {"state": "OK", "violations": []}
```

**Session-level集約**:
```python
from src.validation_engine.validator_session import aggregate_session

# 5 reps（3 OK + 2 WARN）
reps = [...]  # JSONLファイルから読み込み

result = aggregate_session(reps, metric_key="score")
# result: {
#   "qc_pass_count": 5,  # OK + WARN
#   "total_reps": 5,
#   "aggregates": {
#     "mean": 74.84,
#     "sd": 4.36,
#     "p95": 78.2,  # nearest-rank: sorted[3]
#     "rep_states": ["OK", "OK", "OK", "WARN", "WARN"]
#   },
#   "validation": {
#     "state": "WARN",  # 最悪ステータス採用
#     "violations": [...]
#   }
# }
```

**過半数ルール**:
- 5 reps中3以上がOK/WARN → session有効
- 3未満 → `state="INSUFFICIENT"`（再撮影必要）
- 統計対象: WARN含む・ERROR除外

**テストフィクスチャ**:
- `tests/validation_engine/fixtures/all_ok.jsonl` - 全5本OK
- `tests/validation_engine/fixtures/error_mixed.jsonl` - 2 OK, 1 WARN, 2 ERROR
- `tests/validation_engine/fixtures/warn_mixed.jsonl` - 3 OK, 2 WARN
- `tests/validation_engine/fixtures/insufficient.jsonl` - 2 OK, 3 ERROR（過半数未達）

詳細は ADR-034〜037 および各実装ファイルのコメントを参照してください。

---

## 📊 プロジェクト統計

### 実装規模（Phase 2完了時点）

| カテゴリ | ファイル数 | 総行数 |
|:--------|:----------|:-------|
| 評価器（7種目） | 7 | 2,178 |
| インフラ（normalizer, health_check, pose_extractor, worker） | 4 | 1,100 |
| テスト | 5 | 1,500+ |
| **合計** | **16** | **4,778+** |

### テスト統計

| メトリクス | 値 |
|:----------|:---|
| テスト数 | 53 |
| 合格率 | 100% |
| 実行時間 | 2.62秒 |
| カバレッジ | 72% |

### コード品質

| メトリクス | 値 |
|:----------|:---|
| CLAUDE.md準拠率 | 100% |
| Forbidden Patterns違反 | 0件 |
| ADR記録 | 5件 |
| CRITICAL保護マーカー | 78箇所 |

---

## 🚀 AWS デプロイ

THF Motion ScanをAWS Serverlessアーキテクチャにデプロイする手順です。

### アーキテクチャ

```
S3 (Videos) → SQS → Lambda (Container) → S3 (Results) + DynamoDB
```

**コンポーネント**:
- **S3**: 動画アップロード＆結果保存
- **SQS**: 非同期処理キュー
- **Lambda**: MediaPipeによる動画解析（Container Image）
- **DynamoDB**: 処理結果のメタデータ保存

### 前提条件

- AWSアカウント
- AWS CLI（v2.31.20+）
- AWS SAM CLI（v1.145.2+）
- Docker Desktop（v28.5.1+）
- IAM認証設定完了（`aws configure`）

### デプロイ手順

#### Step 1: ECRリポジトリ作成

```bash
# ECRリポジトリを作成
aws ecr create-repository --repository-name thf-motion-scan --region ap-northeast-1

# ECRログイン
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin \
  <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com
```

#### Step 2: Dockerイメージをビルド＆プッシュ

```bash
# SAM buildでイメージをビルド
sam build

# イメージをECRにプッシュ
docker tag thf-motion-scan:latest \
  <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/thf-motion-scan:latest

docker push <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/thf-motion-scan:latest
```

#### Step 3: SAMデプロイ

```bash
# 初回デプロイ（ガイド付き）
sam deploy --guided

# 2回目以降
sam deploy
```

#### Step 4: 動作確認

```bash
# S3バケット名を取得
aws cloudformation describe-stacks \
  --stack-name thf-motion-scan \
  --query 'Stacks[0].Outputs[?OutputKey==`VideosBucketName`].OutputValue' \
  --output text

# テスト動画をアップロード
aws s3 cp test_video.mp4 s3://thf-motion-scan-videos-<account-id>/videos/single_leg_squat/test.mp4

# Lambda実行ログを確認
sam logs -n ProcessingFunction --stack-name thf-motion-scan --tail
```

### ローカルテスト

```bash
# イメージをビルド
docker build -t thf-motion-scan:local .

# ローカルで実行（テスト用）
docker run --rm \
  -e RESULTS_BUCKET=test-bucket \
  -e TABLE_NAME=test-table \
  thf-motion-scan:local
```

### モニタリング

```bash
# Lambda関数のログを確認
sam logs -n ProcessingFunction --stack-name thf-motion-scan --tail

# 特定の時間範囲のログ
sam logs -n ProcessingFunction --start-time '10 minutes ago' --end-time 'now'
```

### コスト試算

**無料枠（12ヶ月）**:
- Lambda: 月100万リクエスト、40万GB-秒
- S3: 5GB、20,000 GETリクエスト
- DynamoDB: 25GB、25 WCU、25 RCU

**想定コスト（100動画/月の場合）**:
- Lambda: $5-10/月（実行時間による）
- S3: $1-2/月
- DynamoDB: $0-1/月
- **合計: 約$6-13/月**

詳細は [ADR-007](docs/adr/decision_log.md#adr-007-aws-lambda-container-architectureの選択) を参照してください。

---

## ✅ thresholds.json バリデーション

最新のしきい値ファイルは JSON Schema で検証できます。開発時は以下のワークフローを守ってください。

### 手動検証

```bash
# 事前に開発用依存をインストール
pip install -r requirements-dev.txt

# メイン設定ファイルを検証
python3 scripts/validate.py

# 複数ファイル／ディレクトリをまとめて検証する場合
python3 scripts/validate.py config/thresholds.json tests/fixtures/thresholds/valid
```

### フィクスチャでの挙動チェック

```bash
# 正常ケース（3件）は成功する
python3 scripts/validate.py tests/fixtures/thresholds/valid

# 異常ケース（10件）は失敗することを確認
python3 scripts/validate.py --quiet tests/fixtures/thresholds/invalid || echo "expected failure"
```

### pre-commit フック

`.pre-commit-config.yaml` により `config/thresholds.json` へのコミット前検証が有効化できます。

```bash
pre-commit install
# 以後、thresholds.json を変更してコミットすると自動検証が走ります
```

フックを一時的に無効化したい場合は `SKIP=validate-thresholds git commit ...` を使用してください（緊急時のみ）。

### 失敗時の対処

1. バリデータ出力の `$.tests.xxx...` で報告されたキーを特定  
2. 該当バンドやメタデータを修正  
3. `python3 scripts/validate.py` を再実行して通ることを確認  
4. コミット → CI（Validate Thresholds workflow）の完了を確認

---

## ✅ thresholds_v2 自動生成と検証フロー

Phase 5 では Notion Templates を唯一の真実源とし、`thresholds_v2.json` を自動生成するパイプラインを導入しました。出力は ValidationEngine から `validation_state` を算出するための中間データです。

### ビルド手順

```bash
python tools/build_thresholds.py \
  --src tests/fixtures/thresholds_v2/notion_exports/templates_minimal.json \
  --out config/thresholds_v2.json \
  --rules-version 0.2.0 \
  --thresholds-version 2.0.0 \
  --artifact-sha $(git rev-parse --short HEAD)
```

- `--dry-run` を付与するとファイル生成せず標準出力に結果を表示  
- `--normalization-version`（既定値: `none`）で正規化ロジックのバージョンを明示  
- 標準ログは構造化 JSON（utils.logger）で記録されます

### フィクスチャ検証

| ディレクトリ | 役割 | 内容 |
|--------------|------|------|
| `tests/fixtures/thresholds_v2/valid/` | スキーマに準拠した3件 | 単一テスト / secondary付き / 複合ユニット |
| `tests/fixtures/thresholds_v2/invalid/` | 失敗期待の5件 | versions欠落 / code書式 / 演算子 / range長 / artifact_sha |

CIでは `.github/workflows/validate-thresholds-v2.yml` がこれらのフィクスチャを検証し、`tools/build_thresholds.py --dry-run` を実行してビルドが成功することを保証します。

### トラブルシューティング

1. Notion Export の `templates` 構造を確認（必須キー: `test_code`, `metric`, `unit`, `thresholds`）  
2. 変換した `config/thresholds_v2.json` を JSON Schema (`schema/thresholds_v2.schema.json`) で再検証  
3. invalid フィクスチャと同等の違反を起こしていないか比較  
4. `tools/build_thresholds.py --dry-run --log-level DEBUG` で変換ログを確認

---

## 📦 Result Schema Contracts

- **互換ポリシー**: `schema/rep_result.schema.jsonl` / `schema/session_result.schema.json` は Draft-07 準拠。後方互換を維持したい場合は「任意フィールドの追加」のみで対応し、既存キーの型変更・必須化は禁止。破壊的変更を行う場合は `versions.rules_version` / `versions.thresholds_version` の MAJOR を更新し、ValidationEngine・Dashboard・CLI を同一リリースウィンドウで展開する。
- **Non-breaking 例**: `validation.violations[*].hint` のようなオプションフィールド追加、`aggregates.extra_metrics` の追加は OK。**Breaking 例**: `validation.state` 語彙の変更、`versions.artifact_sha` の削除、`rep_index` の型変更など。
- **マイグレーション注意点**: 既存データで `versions.*` が欠落している場合は `build_thresholds.py` 出力のメタデータを反映し、ValidationEngine が `validation.state` を再計算できるようにする。CI の `schema-fixtures` ジョブ（`tests/fixtures/schemas/**`）と `tests/test_result_schemas.py` を通過させること。
- **運用チェックリスト**: 変更前後で `examples/rep_result.sample.jsonl` / `examples/session_result.sample.json` を `jsonschema --instance` で検証し、`qc_pass_count <= total_reps` の事後チェックを必須化。
- **関連仕様**: Validation Ops Hub「出力ルール＆処方マップ」、Streamlit Dashboard 統合仕様 v2.1、Rep CLI MVP。

---

## 📜 ライセンス

MIT License（予定）

---

## 🙏 謝辞

- **MediaPipe**: Google による高精度なポーズ推定ライブラリ
- **OpenCV**: コンピュータビジョン処理の標準ライブラリ
- **Claude Code**: AI協働開発プロトコル（CLAUDE.md）の実装支援

---

**Last Updated**: 2025-10-21
**Version**: Phase 2完了版
**Protocol**: CLAUDE.md v1.0


## 🧭 運用ガードレール (Phase 5)

- CloudWatchダッシュボード: `MotionScan-Ops-<env>` でリクエスト・エラー率・リトライ成功率・DLQ状況を一元監視
- SNSアラート: `thf-alerts-<env>`（メール、将来Slack連携予定）に 4 種類のアラームを集約
- Runbook: [docs/runbooks/dlq_redrive.md](docs/runbooks/dlq_redrive.md) にDLQ復旧手順と観測ポイントを記録
- ツール: `scripts/redrive.py` でガードレールに沿った再投入（メトリクス/停止条件を自動実行）

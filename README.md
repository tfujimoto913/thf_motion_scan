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

### 外部ドキュメント

- **MediaPipe Pose**: https://google.github.io/mediapipe/solutions/pose.html
- **OpenCV**: https://docs.opencv.org/4.x/
- **pytest**: https://docs.pytest.org/

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

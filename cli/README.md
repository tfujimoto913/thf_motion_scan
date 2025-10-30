# THF Motion Scan - ローカル評価CLI

## 概要

ローカル環境で動画評価を行うコマンドラインツールです。
AWS Lambda環境と同じ評価エンジン（processing/worker.py）を使用し、完全に同じ出力形式で結果を生成します。

## 特徴

- ✅ AWS環境不要、ローカルで完結
- ✅ Lambda環境と同一の評価ロジック
- ✅ 同一の出力形式（score.json, manifest.json）
- ✅ シンプルなコマンドライン操作
- ✅ 詳細なエラーメッセージ

## 前提条件

### 1. 仮想環境のアクティベート

```bash
source .venv/bin/activate  # macOS/Linux
# または
.venv\Scripts\activate  # Windows
```

### 2. 依存パッケージのインストール

すでにプロジェクトの依存関係がインストールされていれば追加作業不要です。

```bash
pip install -r requirements.txt
```

### 3. 設定ファイルの準備

プロジェクトルートに `config.json` が必要です（通常は既存）。

## 基本的な使い方

### 最もシンプルな実行

```bash
python cli/evaluate.py test_videos/balance/sample1.mp4
```

デフォルト設定：
- テストタイプ: `single_leg_squat`
- アスリートID: 自動生成
- セッションID: 自動生成
- 出力先: `output/`

### テストタイプを指定

```bash
python cli/evaluate.py test_videos/balance/sample1.mp4 --test-type single_leg_squat
```

### アスリートIDとセッションIDを指定

```bash
python cli/evaluate.py test_videos/balance/sample1.mp4 \
  --athlete-id TaroYamada-100315 \
  --session-id 2025-10-29-morning
```

### 出力先を指定

```bash
python cli/evaluate.py test_videos/balance/sample1.mp4 \
  --output-dir my_results
```

## オプション一覧

| オプション | 説明 | デフォルト | 例 |
|----------|------|-----------|---|
| `video_path` | 評価する動画ファイルのパス（必須） | - | `test_videos/balance/sample1.mp4` |
| `--test-type` | テストタイプ | `single_leg_squat` | `single_leg_squat` |
| `--athlete-id` | アスリートID | 自動生成 | `TaroYamada-100315` |
| `--session-id` | セッションID | 自動生成 | `2025-10-29-morning` |
| `--output-dir` | 出力ディレクトリ | `output` | `my_results` |
| `--config` | config.jsonのパス | `config.json` | `config/custom.json` |

## 出力ファイル

評価完了後、以下のファイルが生成されます：

```
output/
└── sample1/                    # 動画ファイル名（拡張子なし）
    ├── score.json              # 評価結果（スコア、詳細評価）
    └── manifest.json           # メタデータ（athlete_id, session_id等）
```

### score.json の例

```json
{
  "score": 9.5,
  "evaluation": {
    "pelvis_stability": {"score": 2.0, "notes": "..."},
    "trunk_stability": {"score": 1.5, "notes": "..."}
  },
  "video_info": {
    "total_frames": 150,
    "fps": 30,
    "duration_sec": 5.0
  },
  "health_check": {
    "status": "ok",
    "warnings": []
  }
}
```

### manifest.json の例

```json
{
  "athlete_id": "TaroYamada-100315",
  "session_id": "2025-10-29-morning",
  "test_type": "single_leg_squat",
  "processed_at": "2025-10-29T12:34:56+09:00",
  "score_file": "output/sample1/score.json",
  "manifest_file": "output/sample1/manifest.json"
}
```

## 対応テストタイプ

現在対応しているテストタイプ（config.jsonで定義）：

- `single_leg_squat` - 片脚スクワット評価
- `upper_body_swing` - 上半身スイング評価
- `skater_lunge` - スケーターランジ評価
- `cross_step` - クロスステップ評価
- `stride_mimic` - ストライド模倣評価
- `push_pull` - プッシュプル評価
- `jump_landing` - ジャンプ着地評価

## トラブルシューティング

### エラー: 動画ファイルが見つかりません

```
❌ エラー: 動画ファイルが見つかりません: test_videos/balance/sample1.mp4
   現在のディレクトリ: /path/to/thf_motion_scan
```

**解決方法**:
- パスが正しいか確認
- プロジェクトルートから実行しているか確認
- 動画ファイルが実際に存在するか確認

### エラー: config.jsonが見つかりません

```
❌ エラー: config.json not found at config.json
```

**解決方法**:
```bash
# プロジェクトルートにconfig.jsonがあるか確認
ls -la config.json

# 別の場所にある場合は --config で指定
python cli/evaluate.py video.mp4 --config path/to/config.json
```

### エラー: MediaPipeのインストールエラー

```
ImportError: No module named 'mediapipe'
```

**解決方法**:
```bash
# 仮想環境をアクティベート
source .venv/bin/activate

# 依存関係を再インストール
pip install -r requirements.txt
```

### エラー: 評価エンジンの初期化失敗

```
❌ 評価エンジン初期化中にエラーが発生しました
```

**解決方法**:
- config.jsonの形式が正しいか確認
- config.jsonに必要な評価器設定が含まれているか確認
- `--config` オプションで正しいパスを指定

## 開発情報

### アーキテクチャ

```
cli/evaluate.py (薄いラッパー)
    ↓
processing/worker.py (評価エンジン本体)
    ↓
processing/evaluators/* (各評価器)
    ↓
output/{video_name}/score.json, manifest.json
```

### 設計原則

- **CRITICAL: worker.pyを変更せず再利用**
  - Lambda環境との完全な互換性を維持
  - 評価ロジックの一元管理
  - テスト容易性

- **出力形式の統一**
  - AWS Lambda環境と完全一致
  - ADR-017で定義されたJSON構造
  - スキーマ互換性保証

### 関連ドキュメント

- **ADR-017**: 統一評価器インターフェース設計
- **ADR-020**: チーム一括受付システム基盤実装
- **processing/worker.py**: 評価エンジン本体
- **test_videos/README.md**: テスト動画配置ガイド

## Stage 2以降の拡張予定

- **Stage 2**: バッチ評価（ディレクトリ指定で一括評価）
- **Stage 3**: 評価結果の可視化（グラフ、レポート生成）
- **Stage 4**: 比較分析（複数セッションの比較）

## ライセンス

プロジェクトのライセンスに従います。

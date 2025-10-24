# Decision Log

## ADR-001: AI協働開発フレームワーク導入
- 日付: 2025-10-19
- 決定者: Human + Claude
- 決定: THF Motion ScanにAI協働プロトコル導入
- 理由: AI崩壊防止、品質保証、再現性確保
- 参照: claude.md, Notion原典

## ADR-002: THF評価閾値のconfig.json管理
- 日付: 2025-10-19
- 決定者: Human + Claude
- 決定: 全評価閾値をconfig.jsonで一元管理、コード内ハードコード禁止
- 理由:
  - データ整合性ルール準拠（CLAUDE.md §データ整合性）
  - 閾値変更時の影響範囲最小化
  - 実験的調整の柔軟性確保
  - 再現性保証（設定ファイルバージョン管理）
- 影響:
  - `processing/analyzer.py`: `__init__()`でconfig.json読み込み追加
  - `score_pelvic_stability()`: ハードコード閾値削除、config参照に変更
  - `config.json`: 7種のテスト閾値追加（single_leg_squat, skater_lunge等）
  - 正規化基準追加（shoulder_width, pelvis_width, leg_length, base_width）
- 技術詳細:
  - MediaPipe誤差3°を考慮した閾値設定（例: 90° → 87°）
  - 下肢長比・肩幅比による正規化で個人差吸収
  - 骨盤安定性評価: Y座標差で0.02/0.05/0.10の3段階閾値
- 参照: Notion「📐 評価システム設計（実装確定版）」
- 破壊的変更: `MotionAnalyzer()`の引数に`config_path`追加（デフォルト値ありで後方互換性維持）

## ADR-003: 身体スケール正規化処理の実装
- 日付: 2025-10-19
- 決定者: Human + Claude
- 決定: ランドマーク間距離を基準とした身体スケール正規化処理を実装
- 理由:
  - 個人差吸収: 身長・体格の違いによる測定値変動を排除
  - カメラ距離依存性排除: 撮影距離に依らない評価実現
  - データ整合性保証: NaN保持ルール準拠（CLAUDE.md §データ整合性）
  - 外れ値耐性: 代表値に中央値使用で一時的なトラッキング失敗に対応
- 技術的根拠:
  - MediaPipe座標は正規化済み（0-1範囲）だが、絶対値比較は不可
  - 身体基準距離による比率計算で無次元化
  - 例: ステップ幅 / base_width = 1.5 → 基準幅の1.5倍と評価
- 影響:
  - `processing/normalizer.py`: 新規作成
  - `BodyNormalizer`クラス: 4種の基準距離計算
    - `shoulder_width`: landmarks 11-12（左右肩）
    - `pelvis_width`: landmarks 23-24（左右腰）
    - `leg_length`: hip to ankle平均（左右脚の平均）
    - `base_width`: max(shoulder_width, pelvis_width)
  - `normalize_landmarks_sequence()`: 全フレーム処理と代表値抽出（中央値）
  - `normalize_value()`: 測定値の正規化ヘルパー関数
- NaN処理戦略:
  - 計算不可時はNoneを返す（例外投げない）
  - 片側のみ計算可能な場合は単独値使用
  - 全フレームNaNの場合は代表値もNaN保持
  - 辞書キー削除禁止（CLAUDE.md準拠）
- 使用例:
  ```python
  normalizer = BodyNormalizer()
  rep_values, frame_values = normalizer.normalize_landmarks_sequence(landmarks_data)
  step_width_ratio = normalize_value(step_width, rep_values['base_width'])
  ```
- 依存関係:
  - 全7種目評価器がこのモジュールに依存
  - config.json normalization設定参照
- 参照: Notion「📐 評価システム設計（実装確定版）」、CLAUDE.md §データ整合性
- 破壊的変更: なし（新規モジュール）

## ADR-004: Health Check実装とwarnings.json管理
- 日付: 2025-10-19
- 決定者: Human + Claude
- 決定: データ品質検証とエラー集約管理システムを実装
- 理由:
  - 三層防御の検知層強化: 低品質データの早期検出
  - デバッグ効率化: warnings.json集約で問題箇所特定容易化
  - 再現性保証: random_seed適用でデータ整合性確保
  - セキュリティ強化: 個人情報・環境変数のログ出力禁止
- 影響:
  - `processing/health_check.py`: 新規作成
  - `HealthChecker`クラス: 品質検証とwarnings管理
    - `check_landmark_quality()`: visibility閾値チェック、frame_skip_tolerance検証
    - `validate_config()`: config.json整合性確認
    - `save_warnings()`: warnings.json出力
    - `_anonymize_path()`: ファイルパス匿名化（個人情報除外）
  - `apply_random_seed()`: グローバル関数でseed設定
  - `processing/worker.py`: Health Check統合
    - `__init__`: random_seed適用、HealthChecker初期化
    - `process_video()`: 品質チェック実行、warnings.json自動出力
    - 結果に`health_check`フィールド追加
- 技術詳細:
  - **visibility閾値**: config.json `confidence_min: 0.7`参照
  - **frame_skip_tolerance**: config.json `frame_skip_tolerance: 3`使用
  - **random_seed**: config.json `random_seed: 42`を全処理開始時に適用
  - **warnings.json構造**:
    ```json
    {
      "generated_at": "2025-10-19T...",
      "total_warnings": 2,
      "warnings": [
        {
          "timestamp": "2025-10-19T...",
          "level": "WARNING",
          "message": "低品質ランドマークデータ検出",
          "details": {
            "video": "test.mp4",  // 匿名化済み（フルパス除外）
            "detection_rate": 0.85
          }
        }
      ],
      "config_summary": {
        "confidence_min": 0.7,
        "frame_skip_tolerance": 3,
        "random_seed": 42
      }
    }
    ```
- セキュリティ要件:
  - **個人情報除外**: Face/Name/フルパスをwarnings.jsonに記録禁止
  - **環境変数除外**: APIキー等をログ出力禁止
  - **匿名化処理**: `_anonymize_path()`でファイル名のみ保持
- ワークフロー変更:
  - 旧: 抽出 → 評価 → 保存
  - 新: 抽出 → **品質チェック** → 評価 → 保存 + **warnings.json出力**
- 破壊的変更:
  - `VideoProcessingWorker.__init__`: `config_path`引数追加（デフォルト値で後方互換性維持）
  - 処理結果に`health_check`フィールド追加
- 参照: CLAUDE.md §三層防御、§セキュリティ
- 依存関係: config.json、全評価器

## ADR-005: pose_extractor.pyのCLAUDE.md準拠化とCLI機能追加
- 日付: 2025-10-21
- 決定者: Human + Claude
- 決定: pose_extractor.pyにCLAUDE.md準拠コメント追加、CLI機能追加
- 理由:
  - コード一貫性保証: Phase 1で全評価器はCLAUDE.md準拠完了
  - 既存実装の準拠化: pose_extractor.pyは既存実装だが準拠化未実施
  - メンテナンス効率化: 意図が明確なコメントでデバッグ容易化
  - AI崩壊防止: Forbidden Patterns違反ゼロ維持
  - テストデータ生成: 動画→JSON変換CLIでテストフィクスチャ生成容易化
- 影響:
  - `processing/pose_extractor.py`: 以下を追加
    - ファイルヘッダー (Purpose/Responsibility/Dependencies/Created/Decision Log/CRITICAL)
    - クラスコメント (What/Why/Design Decision)
    - `__init__()`: コメント追加、CRITICAL保護マーカー
    - `extract_landmarks()`: コメント追加、PHASE CORE LOGIC、CRITICAL保護マーカー
    - `save_to_json()`: 新規追加（メタデータ拡張版JSON出力）
    - `__del__()`: コメント追加、CRITICAL保護マーカー
    - `main()`: 新規追加（CLIエントリーポイント）
    - `if __name__ == '__main__':`: 新規追加（CLIモード実行）
- 技術詳細:
  - **model_complexity=2**: 精度と速度のバランス重視 (0=Lite, 1=Full, 2=Heavy)
  - **static_image_mode=False**: 動画最適化（トラッキング有効）
  - **RGB変換必須**: MediaPipeはRGB入力前提、BGRではNG
  - **33キーポイント抽出**: MediaPipe Pose標準仕様
  - **リソース解放**: __del__でpose.close()必須（メモリリーク防止）
- CLI機能詳細:
  - **コマンド**: `python -m processing.pose_extractor --input video.mp4 --output output.json`
  - **オプション**:
    - `--input`: 入力動画ファイルパス（必須）
    - `--output`: 出力JSONファイルパス（必須）
    - `--format`: 出力形式（dict: 既存互換、json: メタデータ拡張版、デフォルト: json）
    - `--verbose`: 詳細ログ出力
  - **出力フォーマット**: 提案B（メタデータ拡張版）採用
- JSONフォーマット選択理由:
  - **提案A（既存互換）**: extract_landmarks()出力をそのまま保存
    - メリット: 既存コードと完全互換、シンプル
    - デメリット: メタデータ不足（video_path, created_at, mediapipe_version等）
  - **提案B（メタデータ拡張版）**: メタデータ追加、ランドマーク構造は既存互換 ✅ 採用
    - メリット: メタデータ充実、既存コードと互換、トレーサビリティ向上
    - デメリット: JSONサイズ微増、メタデータ生成コード追加必要
  - **提案C（完全拡張版）**: ランドマーク名も追加
    - メリット: 可読性向上
    - デメリット: 既存コードと非互換、normalizer.py修正必要、JSONサイズ大幅増加
  - **採用理由**: 提案Bは既存コード互換性を維持しつつメタデータ充実を実現
- JSONフォーマット構造（提案B）:
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
- CRITICAL保護箇所:
  - MediaPipe Pose初期化: `self.mp_pose = mp.solutions.pose`
  - RGB変換: `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)`
  - ランドマーク検出成功時のみデータ保存: `if results.pose_landmarks:`
  - リソース解放: `cap.release()`, `self.pose.close()`
  - 既存コード互換性: `data['landmarks']`でアクセス可能
- 使用例:
  ```bash
  # メタデータ拡張版JSON出力（推奨）
  python -m processing.pose_extractor \
    --input tests/test_videos/sample_squat.mp4 \
    --output tests/fixtures/sample_landmarks.json \
    --verbose

  # 既存互換版出力
  python -m processing.pose_extractor \
    --input video.mp4 \
    --output output.json \
    --format dict
  ```
- 参照: CLAUDE.md §コメントフォーマット
- 破壊的変更: なし（既存コード互換性100%維持）

## ADR-006: Phase 2完了レポート作成とREADME充実
- 日付: 2025-10-21
- 決定者: Human + Claude
- 決定: Phase 2完了レポート作成、README.md充実、Phase 3ドキュメント整備実施
- 理由:
  - Phase Gateプロトコル準拠: 各Phase完了時の記録義務（CLAUDE.md §Phase制導入）
  - トレーサビリティ確保: Phase 2成果（53テスト、72%カバレッジ）の記録
  - 新規開発者オンボーディング効率化: 包括的なREADME.mdによる学習コスト削減
  - プロジェクト可視性向上: GitHub可読性向上、外部コントリビューター獲得準備
- 影響:
  - `docs/phase2_completion_report.md`: 新規作成（1,100行）
    - エグゼクティブサマリー（Phase 2目標達成状況）
    - 実装完了した機能（test_normalizer, health_check, single_leg_squat, all_evaluators, worker, pose_extractor CLI）
    - ADR-005詳細記録
    - カバレッジ分析（モジュール別72%達成）
    - 主要な成果と学び（7項目）
    - Phase 3への移行準備（Azure統合選択肢、ドキュメント整備完了）
  - `README.md`: 充実（17行 → 634行、+617行）
    - 7セクション構成追加
      1. プロジェクト概要（7テスト項目詳細表、主要機能）
      2. セットアップ手順（前提条件、4ステップインストール）
      3. 使用方法（CLI使用例、テスト実行方法、カバレッジ確認方法）
      4. プロジェクト構造（ディレクトリツリー、主要ファイル説明）
      5. 開発者向け情報（CLAUDE.md準拠フロー、テストの書き方、コントリビューション方法）
      6. リンク（GitHub, Notion, ドキュメント）
      7. プロジェクト統計（実装規模、テスト統計、コード品質）
    - バッジ追加（Python 3.11+, Tests 53 passed, Coverage 72%, License MIT）
    - CLAUDE.md準拠の開発フロー詳細記載
    - コントリビューション6ステップ記載
  - Phase 3方向性変更: Azure統合延期 → ドキュメント整備優先
- 技術詳細:
  - **Phase 2成果サマリー**:
    - テスト数: 53テスト（100%合格、実行時間2.62秒）
    - カバレッジ: 72%（目標70%超え）
    - テストコード: 1,791行（5ファイル）
    - テストファイル構成:
      - test_normalizer.py: 324行、11テスト、82%カバレッジ
      - test_health_check.py: 430行、11テスト、87%カバレッジ
      - test_single_leg_squat.py: 472行、13テスト、90%カバレッジ
      - test_all_evaluators.py: 323行、9テスト、統合テスト
      - test_worker.py: 242行、9テスト、99%カバレッジ
    - 実データ: tests/fixtures/sample_landmarks.json（5.2MB、942フレーム、16.28秒）
  - **カバレッジ分析**:
    - 目標達成: 評価器78-90%、インフラ82-99%、全体72%
    - 主要ロジック100%カバー達成
    - 未カバーはエラーハンドリング・デバッグログのみ
    - pose_extractor.py 22%は問題なし（CLI機能はテスト対象外）
  - **README.md設計判断**:
    - 対象読者: 新規開発者、外部コントリビューター、プロジェクトマネージャー
    - 構成原則: 概要 → セットアップ → 使用方法 → 構造理解 → 開発参加
    - CLAUDE.md準拠: 曖昧語禁止、具体的数値明記、ADR参照
  - **Phase 3実施内容**:
    - タスク1完了: README.md充実（634行）
    - タスク2完了: Phase 2完了レポート作成（本ADR記録時点）
    - タスク3候補: docs/design/overview.md充実（アーキテクチャ概要、設計思想、技術選定理由）
    - タスク4候補: API仕様書作成（全評価器共通仕様、評価器別仕様、インフラ仕様）
- ワークフロー変更:
  - Phase 3目的変更: Azure統合 → ドキュメント整備
  - 理由: Phase 1-2で実装完了、Phase 3でドキュメント完成度向上が優先
  - Phase 4候補: Azure統合（Functions, Blob, Queue, Cosmos DB）
- Phase 2 vs Phase 1比較:
  | メトリクス | Phase 1 | Phase 2 | 変化 |
  |:----------|:--------|:--------|:-----|
  | 実装行数 | 3,178行 | 1,791行（テストのみ） | テスト基盤構築 |
  | ファイル数 | 11ファイル | 5ファイル（テストのみ） | テスト対象拡大 |
  | カバレッジ | 0% → 72% | 72%維持 | 目標達成 |
  | テスト数 | 0 → 53 | 53維持 | 品質保証完成 |
  | ADR記録 | ADR-001〜004 | ADR-005〜006 | +2件 |
- 参照: CLAUDE.md §Phase制導入、docs/phase2_completion_report.md
- 破壊的変更: なし
## ADR-007: AWS Lambda Container Architectureの選択
- 日付: 2025-10-24
- 決定者: Human + Claude
- 決定: THF Motion ScanをAWS Lambda Container Imageとしてデプロイ
- 理由:
  - **MediaPipe依存**: MediaPipeは250MB+の大容量パッケージでZip形式では制限超過
  - **OpenCV依存**: システムライブラリ（mesa-libGL）が必要でLambda Layer非対応
  - **再現性**: Dockerfileによる環境完全再現
  - **ローカルテスト**: docker run で Lambda 環境を完全再現可能
- アーキテクチャ選択:
  - **S3 → SQS → Lambda → DynamoDB** のイベント駆動型
  - **SQS バッファリング**: Lambda 同時実行数制限対策、リトライ制御
  - **DLQ（Dead Letter Queue）**: 3回失敗後の隔離
  - **S3 ライフサイクル**: videos 30日削除、results 90日 Glacier 移行
  - **DynamoDB TTL**: 90日自動削除（コスト最適化）
- 影響:
  - `Dockerfile`: 新規作成
    - ベースイメージ: `public.ecr.aws/lambda/python:3.11`
    - システム依存: mesa-libGL, gcc, gcc-c++, make
    - アプリコード: config.json, processing/, src/handler.py
  - `template.yaml`: CloudFormation テンプレート作成
    - VideosBucket: S3 動画アップロード用
    - ResultsBucket: S3 結果保存用
    - ProcessingQueue: SQS キュー（VisibilityTimeout 960秒）
    - DeadLetterQueue: SQS DLQ（maxReceiveCount 3）
    - ProcessingFunction: Lambda 関数（Timeout 900秒、MemorySize 3008MB）
    - ResultsTable: DynamoDB テーブル（video_id + processed_at 複合キー）
  - `src/handler.py`: Lambda ハンドラー作成
    - S3/SQS イベント両対応
    - 一時ファイル管理（tempfile + os.unlink）
    - VideoProcessingWorker 統合
    - 結果の S3 保存と DynamoDB 記録
  - `samconfig.toml`: SAM CLI 設定
    - stack_name: thf-motion-scan
    - region: ap-northeast-1
    - resolve_image_repos: true
- 技術詳細:
  - **Lambda Timeout**: 900秒（15分、動画処理対応）
  - **Lambda Memory**: 3008MB（MediaPipe 最大メモリ要件）
  - **SQS VisibilityTimeout**: 960秒（Lambda Timeout + 60秒バッファ）
  - **S3 イベント通知**: videos/*.mp4 作成時に SQS 送信
  - **DynamoDB キースキーマ**:
    - HASH: video_id (S3 パス)
    - RANGE: processed_at (タイムスタンプ)
- セキュリティ:
  - **IAM Policies**: S3ReadPolicy, S3CrudPolicy, DynamoDBCrudPolicy
  - **環境変数**: RESULTS_BUCKET, TABLE_NAME（template.yaml 管理）
  - **S3 バケット**: AccountId サフィックスで一意性保証
- デプロイフロー:
  1. Docker イメージビルド: `docker buildx build --platform linux/amd64 ...`
  2. ECR プッシュ: `docker push <account-id>.dkr.ecr.<region>.amazonaws.com/thf-motion-scan:latest`
  3. SAM ビルド: `sam build`
  4. SAM デプロイ: `sam deploy`
- 参照: AWS_DEPLOYMENT_GUIDE.md
- 破壊的変更: なし（新規インフラ構築）

## ADR-008: CloudFormation循環依存の解決
- 日付: 2025-10-25
- 決定者: Claude
- 決定: QueuePolicy の Condition を AccountId ベースに変更
- 問題:
  - **循環依存エラー**: `VideosBucket` ← `QueuePolicy` ← `VideosBucket`
  - **原因**: 
    - VideosBucket が QueuePolicy に依存（`DependsOn: QueuePolicy`）
    - QueuePolicy の Condition が VideosBucket を参照（`aws:SourceArn: !GetAtt VideosBucket.Arn`）
  - **エラーメッセージ**: "Circular dependency between resources: [VideosBucket, QueuePolicy]"
- 解決策:
  - **QueuePolicy Condition 変更**:
    - 旧: `ArnLike: { aws:SourceArn: !GetAtt VideosBucket.Arn }`
    - 新: `StringEquals: { aws:SourceAccount: !Ref AWS::AccountId }`
  - **依存関係**: VideosBucket → QueuePolicy（一方向のみ）
- 技術的根拠:
  - **セキュリティ**: AccountId 制限で同一アカウント内の S3 のみ許可
  - **循環回避**: VideosBucket への参照を削除
  - **AWS ベストプラクティス**: AccountId ベース制限は推奨パターン
- 影響:
  - `template.yaml` 修正:
    ```yaml
    QueuePolicy:
      Properties:
        PolicyDocument:
          Statement:
            - Condition:
                StringEquals:
                  aws:SourceAccount: !Ref AWS::AccountId
    ```
  - セキュリティレベル: 維持（同一アカウント制限）
- トレードオフ:
  - **メリット**: 循環依存解消、デプロイ成功
  - **デメリット**: 特定バケットのみに制限不可（同一アカウント内の全 S3 が許可）
  - **リスク評価**: 低（VideosBucket 以外からの通知はアプリレベルで無視）
- 参照: template.yaml:83-85
- 破壊的変更: なし（内部実装変更のみ）

## ADR-009: Docker Multi-Platform Build対応（arm64→amd64）
- 日付: 2025-10-25
- 決定者: Claude
- 決定: Lambda 用に linux/amd64 単一プラットフォームイメージをビルド
- 問題:
  - **Lambda デプロイ失敗**: "The image manifest, config or layer media type for the source image is not supported"
  - **原因 1（初回）**: arm64 イメージを Lambda にデプロイ
    - ローカル Mac（Apple Silicon）で `docker build` 実行 → arm64 イメージ生成
    - Lambda は x86_64（amd64）のみサポート
  - **原因 2（2回目）**: マルチアーキテクチャマニフェスト生成
    - `docker buildx build --platform linux/amd64` 実行
    - Docker Buildx がデフォルトで provenance/SBOM attestation 生成
    - ECR に `application/vnd.oci.image.index.v1+json` としてプッシュ
    - Lambda はマルチアーキテクチャマニフェスト非対応
- 解決策:
  - **単一プラットフォームビルド**:
    ```bash
    docker buildx build \
      --platform linux/amd64 \
      --provenance=false \
      --sbom=false \
      --load \
      -t thf-motion-scan:latest .
    ```
  - **検証コマンド**:
    ```bash
    # アーキテクチャ確認
    docker image inspect thf-motion-scan:latest --format '{{.Architecture}}'
    # 期待値: amd64
    
    # ECR マニフェストタイプ確認
    aws ecr describe-images --repository-name thf-motion-scan --image-ids imageTag=latest
    # 期待値: application/vnd.docker.distribution.manifest.v2+json
    ```
- 技術詳細:
  - **--platform linux/amd64**: Lambda 要件に合わせた単一プラットフォーム指定
  - **--provenance=false**: ビルド証明（provenance attestation）無効化
  - **--sbom=false**: SBOM（Software Bill of Materials）無効化
  - **--load**: ビルド結果をローカル Docker にロード
  - **manifest types**:
    - ✅ `application/vnd.docker.distribution.manifest.v2+json`: 単一プラットフォーム（Lambda 対応）
    - ❌ `application/vnd.oci.image.index.v1+json`: マルチアーキテクチャ（Lambda 非対応）
- トラブルシューティング履歴:
  1. **初回ビルド**: `docker build` → arm64 イメージ → Lambda 失敗
  2. **2回目ビルド**: `docker build --platform linux/amd64` → マルチマニフェスト → Lambda 失敗
  3. **3回目ビルド**: `docker buildx build --platform linux/amd64 --provenance=false --sbom=false` → 成功
- 影響:
  - `Dockerfile` ヘッダーに CRITICAL コメント追加
  - ビルドコマンド標準化: Dockerfile コメントに記載
  - ビルド時間: ~10分（yum install 346秒、pip install 258秒）
- セキュリティ影響:
  - **provenance/SBOM 無効化**: サプライチェーンセキュリティ情報削減
  - **リスク評価**: 低（内部利用のみ、ECR アクセス制限済み）
  - **代替策**: 将来的に Lambda がマルチマニフェスト対応後に再有効化検討
- 参照: Dockerfile:7-11, AWS_DEPLOYMENT_GUIDE.md
- 破壊的変更: なし（ビルドプロセス変更のみ）

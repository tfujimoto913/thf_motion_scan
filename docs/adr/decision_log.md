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
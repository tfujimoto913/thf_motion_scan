## ADR-029: Rep CLI MVP実装（単一動画評価エンドツーエンド）
- 日付: 2025-11-03
- 決定者: Human + Claude Code
- 決定: ローカル環境での単一動画評価を最短経路で実現する新規CLI（rep_cli.py）をMVPスコープで実装
- 理由:
  - **既存evaluate.pyとの差別化**: worker.py依存のevaluate.pyとは独立し、rep単位での「計測→可視化→判定」エンドツーエンドに特化
  - **最短経路でのMVP実現**: AWS不要、単一動画入力、代表フレーム抽出・オーバーレイ・JSON/CSV出力を1コマンドで完結
  - **TDD厳守**: 全15テスト・7ステージでテストファーストを徹底し、flakyテストゼロを達成
  - **versions追跡基盤**: ADR-028（thresholds.json）との整合性を見据え、rules_version/normalization_version/artifact_shaを必須出力
  - **視覚的フィードバック**: 代表フレーム3枚（best/worst/median）への骨格オーバーレイでUX向上
- 影響:
  - **新規ファイル**:
    - `cli/rep_cli.py` (668行): CLI本体（argparse, pipeline, overlay, export）
    - `tests/test_rep_cli.py` (395行): 15テスト（TDD方式で作成）
    - `cli/README.md` (327行): 使用例・フラグ一覧・オーバーレイ仕様
    - `cli/CHANGELOG.md` (73行): v0.1.0 MVP + v0.2.0 Overlay
    - `cli/RUNBOOK.md` (運用手順書)
  - **既存コードへの影響**: なし（独立実装）
  - **依存関係**: MediaPipe, OpenCV, argparse（標準ライブラリ）、PoseExtractor, BodyNormalizer, SingleLegSquatEvaluatorV2
  - **ブランチ**: feature/phase5-complete（7コミット完了）
- 技術詳細:
  - **CLI引数設計**:
    - `--video PATH` (必須): 入力動画ファイル
    - `--out-dir PATH` (オプション): 出力ディレクトリ（デフォルト：入力動画と同階層）
    - `--dump-trace {true,false}` (デフォルト: true): CSV出力制御
    - `--overlay {true,false}` (デフォルト: true): 画像出力制御
    - 決定理由: argparse標準ライブラリ使用、true/false文字列選択でシェルスクリプト連携容易、boolean型より明示的
    - 代替案: Click（過剰機能）、環境変数（可視性低）→ 却下
  - **代表フレーム選定アルゴリズム**:
    ```python
    def select_representative_frames(frame_scores: List[Dict]) -> Dict:
        sorted_frames = sorted(frame_scores, key=lambda x: x['score'])
        return {
            'best': sorted_frames[-1],      # max score
            'worst': sorted_frames[0],      # min score
            'median': sorted_frames[len(sorted_frames) // 2]  # middle
        }
    ```
    - 決定理由: overall scoreベースのソート後、統計的に意味のある3点抽出、実装シンプル、テスト決定論的
    - 代替案: クラスタリング（過剰）、ランダム抽出（非決定論的）→ 却下
  - **可視性ガード実装**:
    ```python
    def check_visibility(landmarks: List[Dict], threshold: float = 0.5) -> bool:
        required_indices = [0, 11, 12, 23, 24]  # nose, shoulders, hips
        for idx in required_indices:
            if landmarks[idx].get('visibility', 0.0) < threshold:
                return False
        return True
    ```
    - 閾値: 0.5（MediaPipe推奨値）
    - 必須ランドマーク: 5点（NOSE=0, LEFT_SHOULDER=11, RIGHT_SHOULDER=12, LEFT_HIP=23, RIGHT_HIP=24）
    - 不足時処理: 描画スキップ + `flags=['low_visibility']` 付与
    - 決定理由: 人体主要構造点で十分判定可能、ユーザーへ透明性確保、低品質フレーム自動除外
    - 代替案: 全33ランドマークチェック（過剰）、閾値なし（品質低下）→ 却下
  - **オーバーレイ色コーディング**:
    ```python
    # 肩線（緑）、骨盤線（青）、体幹軸（黄）
    cv2.line(frame, left_shoulder, right_shoulder, (0, 255, 0), 2)  # BGR: 緑
    cv2.line(frame, left_hip, right_hip, (255, 0, 0), 2)            # BGR: 青
    cv2.line(frame, neck, pelvis, (0, 255, 255), 2)                 # BGR: 黄
    ```
    - 描画内容: 肩線・骨盤線・体幹軸 + Class注記（"pass (p=0.92)"）+ Score注記（"Score: 75.0"）
    - 座標変換: 正規化座標（0-1）→ ピクセル座標（frame.shape使用）
    - 決定理由: 視覚的区別容易、赤は警告色で回避、OpenCV BGR順対応
    - 代替案: 単色描画（区別困難）、カスタム配色（主観的）→ 却下
  - **Versionsフィールド構造**:
    ```python
    def generate_versions() -> Dict[str, str]:
        return {
            'rules_version': '0.1.0',
            'normalization_version': 'none',
            'artifact_sha': 'local-dev'
        }
    ```
    - 決定理由: ADR-028準拠、再現性追跡、将来のthresholds.json連携基盤
    - 代替案: バージョン単一フィールド（粒度粗）、なし（トレーサビリティ喪失）→ 却下
  - **出力ファイル構造**:
    - `result.json`: {session_id, rep_id, scores, class, class_prob, uncertainty, flags, versions, representative_frames}
    - `trace.csv`: 時系列データ（time, angle_x/y/z, events, class_trace）
    - `{session_id}_{rep_id}_{best|worst|repr}.jpg`: 代表フレーム3枚（骨格オーバーレイ付き）
- Stage別実装履歴:
  - **Stage 1 (CLI骨格)**: argparse、入力検証（FileNotFoundError）、エラーハンドリング（原因+次アクション提示）、6テスト
  - **Stage 2-1 (Pose抽出)**: PoseExtractor統合、ランドマークデータ生成、versions生成、2テスト追加
  - **Stage 2-2 (評価器統合)**: BodyNormalizer（base_width計算）+ SingleLegSquatEvaluatorV2（8原則・80点満点）、分類ロジック（pass>=60, needs_improvement>=40）
  - **Stage 3 (代表フレーム)**: select_representative_frames()実装、best/worst/median抽出、2テスト追加
  - **Stage 3-overlay (画像オーバーレイ)**: draw_overlay()実装、check_visibility()実装、OpenCV描画、3テスト追加
  - **Stage 4 (ファイル出力)**: export_result_json(), export_trace_csv()実装、2テスト追加
  - **Stage 5 (ドキュメント)**: README, RUNBOOK, CHANGELOG作成
  - コミット: 全7件、形式 `stage(X): <why> - <what>`、ブランチ feature/phase5-complete
- テスト詳細:
  - **全15テスト合格**（pytest, TDD方式）:
    - `TestRepCLIArgumentParsing`: 3件（最小引数、全引数、--helpフラグ）
    - `TestRepCLIInputValidation`: 2件（ファイル不在、読込不可）
    - `TestRepCLIErrorMessages`: 1件（原因+次アクション含有）
    - `TestRepCLIPipeline`: 2件（versionsフィールド、scores/class出力）
    - `TestRepresentativeFrames`: 2件（3フレーム抽出、単一フレーム処理）
    - `TestJSONCSVOutput`: 2件（result.json, trace.csv生成）
    - `TestImageOverlay`: 3件（オーバーレイ描画、--overlayフラグ、low_visibilityフラグ）
  - **flakyテストゼロ**: 決定論的実装、mock使用、再現性保証
  - **TDD Red-Green-Refactor**: 全ステージでテストファーストを徹底
- MVP制約と今後の拡張:
  - **MVP制約**:
    - テストタイプ: single_leg_squatのみ（T01）
    - 回旋矢印: 未実装（deferred）
    - trace.csv: evaluatorのframe_data提供時のみ出力
    - base_width: 最初のフレームから計算（簡易実装）
    - artifact_sha: "local-dev"固定（CI未統合）
  - **将来拡張（v0.3.0以降）**:
    - 全テストタイプ対応（T02-T07）
    - 回旋矢印描画（体幹回旋角の符号で左右描き分け）
    - base_width計算改善（median使用）
    - バッチ処理対応
    - CI統合でartifact_sha自動埋め込み
    - thresholds.json連携（versions整合チェック）
- トレードオフ:
  - **メリット**:
    - AWS不要のローカル完結、実行速度高速（Lambda起動待ちなし）
    - 視覚的フィードバック充実（3PNG画像）
    - versions追跡基盤構築（再現性保証）
    - TDDによる品質保証（flakyゼロ）
    - 既存evaluate.pyと独立（影響範囲分離）
  - **デメリット**:
    - 単一テストタイプのみ（MVP段階）
    - 回旋矢印未実装（視覚情報やや不足）
    - バッチ処理未対応（1動画ずつ実行必要）
    - artifact_sha手動管理（CI未統合）
  - **代替案検討**:
    - evaluate.py拡張: 却下（worker.py依存、AWS Lambda互換性維持が目的）
    - Jupyter Notebook: 却下（コマンドライン実行困難、自動化不可）
    - Web UI: 却下（Phase 5 Dashboard別実装、CLI優先）
- 検証結果:
  - ✅ 全15テスト合格（pytest）
  - ✅ CLI引数パース正常動作（minimal, all, help）
  - ✅ エラーハンドリング適切（FileNotFoundError、原因+次アクション提示）
  - ✅ 代表フレーム抽出正確（best/worst/median正しいインデックス）
  - ✅ オーバーレイ描画動作（肩線緑・骨盤線青・体幹軸黄、Class/Score注記）
  - ✅ 可視性ガード機能（閾値0.5、flags付与）
  - ✅ JSON/CSV出力正常（result.json, trace.csv）
  - ✅ versions必須フィールド含有（rules_version, normalization_version, artifact_sha）
  - ✅ ドキュメント完備（README, CHANGELOG, RUNBOOK）
- 破壊的変更: なし（新規CLI、既存コードと独立）
- 参照:
  - 実装ファイル: `cli/rep_cli.py`, `tests/test_rep_cli.py`
  - ドキュメント: `cli/README.md`, `cli/CHANGELOG.md`, `cli/RUNBOOK.md`
  - 依存ADR: ADR-028（thresholds.json versions）、ADR-017（統一評価器インターフェース）
  - ブランチ: feature/phase5-complete（7コミット）
  - コミット形式: `stage(X): <why> - <what>`

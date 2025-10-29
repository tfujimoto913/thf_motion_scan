# Conversation Guidelines
- 常に日本語で会話する
- 長文履歴（10往復超）になったら /clear で新セッション開始
- コンテキスト劣化を感じたら躊躇なく /clear を実行

# Development Philosophy

## Core Beliefs
- Incremental progress over big bangs - 小さな変更を積み重ねる
- Learning from existing code - 既存コードを研究してから実装
- Clear intent over clever code - 明快さ優先
- Reproducibility over speed - 再現性を速度より優先
- Clarity over elegance - 明確性を華麗さより優先

## Test-Driven Development (TDD)

### 基本原則
- 原則としてテスト駆動開発（TDD）で進める
- まずテストを作成し、失敗を確認（Red）
- テストが正しいことを確認できた段階でコミット
- その後、テストをパスさせる実装を進める（Green）
- テストを保ちながらリファクタリング（Refactor）

### テスト構造
- テストは種別を明示：
  - `tests/unit/` - 単体テスト（関数・クラス単位）
  - `tests/integration/` - 結合テスト（複数モジュール連携）
- ファイル命名：`test_<module_name>.py`
- テスト関数命名：`test_<機能>_<条件>_<期待結果>()`
  - 例：`test_pelvis_stability_angle_threshold_15deg()`
  - 仕様をテスト名に埋め込む

### 決定論的テスト
- 乱数依存：seed固定（例：`random.seed(20251029)`, `np.random.seed(20251029)`）
- 時刻依存：freezegun等でモック（`@freeze_time("2025-10-29 12:00:00")`）
- 環境依存：環境変数をモック、テスト用設定ファイル使用
- 外部API依存：レスポンスをモック（pytest-mock, responses等）

### Flaky対策
- flakyテスト検出時は `@pytest.mark.flaky` 禁止
- 原因を特定し、決定論的に修正
- どうしても安定しない場合は隔離（`@pytest.mark.skip(reason="...")`）し、Issue化

## 3回失敗ルール

CRITICAL: Maximum 3 attempts per issue, then STOP.

### 「1回」の定義
同一の以下3要素が揃った場合を「同一エラー」とカウント：
- エラーメッセージ（本質的な部分）
- スタックトレース（発生箇所）
- 再現手順

### 失敗時の手順
同じエラーで3回失敗したら：

1. **失敗ログを記録**（以下のテンプレートに従う）：
```
   ### FAIL LOG — Stage X / Task Y — YYYY-MM-DD HH:MM
   
   **Repro（再現手順）**:
   - コマンド: `pytest tests/unit/test_xxx.py::test_yyy`
   - 前提条件: ZZZ
   - 入力データ: AAA
   
   **Failure ID**: <短い識別子>（例：LANDMARK_LEN_MISMATCH）
   
   **Attempt #**: 3/3
   
   **試行履歴**:
   1. 試行1: XXX を変更 → エラーYYY（時刻: HH:MM）
   2. 試行2: ZZZ を変更 → エラーAAA（時刻: HH:MM）
   3. 試行3: BBB を変更 → エラーCCC（時刻: HH:MM）
   
   **差分サマリ**:
   - 変更ファイル: file1.py, file2.py
   - 変更関数: func_a(), func_b()
   
   **原因仮説**:
   DDDが原因と思われる。根拠：EEE
   
   **次の一手候補**:
   - 案1: FFF（設計レベル変更）
   - 案2: GGG（技術選定変更）
   - 案3: HHH（実装順序変更）
```

2. **リカバリコマンド実行**:
   - `/timeout` を実行（コーディング停止、状態整理）
   - `/rebuild_context` を実行（前提リセット）

3. **セッション停止**:
   - `esc` → `/exit` でClaude Codeを終了

4. **Architectへハンドオフ**:
   - 上記失敗ログをClaude.ai（Architect）に渡す
   - 設計レベルでの見直しを相談

## コマンド体系

### `/start_session` - セッション開始
**目的**: 作業開始時の準備と現状確認

**実行内容**:
1. CLAUDE.mdを読み込む
2. Claude.aiからのハンドオーバー情報を確認
3. 現在のStageを明確化
4. 前回の作業状態を確認（git status, 最新コミット等）
5. 今回の作業目標を再確認

**使用例**:
```
/start_session
```

### `/continue_stage` - Stage作業継続
**目的**: 現在のStageでの次のアクションを明確化

**実行内容**:
1. 現在のStage番号を確認
2. 取り組むべきテストを提示
3. 影響を受けるファイルを列挙
4. 次の最小変更（smallest change）を提案
5. 人間の承認を待つ

**使用例**:
```
/continue_stage
```

### `/run_tdd` - TDD実行
**目的**: テスト駆動開発の厳格な実施

**実行内容**:
1. 失敗するテストを先に書く（Red）
2. テストコードを提示し、人間の承認を待つ
3. 承認後、テストを実行して失敗を確認
4. テストをパスさせる最小コードを書く（Green）
5. リファクタリングの必要性を検討

**使用例**:
```
/run_tdd
```

**注意**:
- 実装前に必ず人間の承認を得る
- テストが「正しく失敗している」ことを確認する

### `/timeout` - 失敗時リカバリ（停止・整理）
**目的**: 行き詰まった時にコーディングを停止し、状況を整理

**実行内容**:
1. コーディングを即座に停止
2. 以下を整理して提示：
   - 最後の安定状態（最終成功コミット等）
   - これまでに試みた内容
   - 失敗理由の仮説
3. 2-3の代替戦略を提示（アーキテクチャレベル）
4. 人間の判断を待つ

**使用例**:
```
/timeout
```

**提示する代替戦略の例**:
- 技術選定変更（ライブラリ変更等）
- 設計パターン変更
- 実装順序変更
- スコープ縮小

### `/rebuild_context` - コンテキストリセット
**目的**: 前提をリセットし、クリーンな状態から再出発

**実行内容**:
1. これまでの前提・仮定をクリア
2. 以下を再定義：
   - **目的**: 何を達成するか
   - **入力**: どんなデータ・状態が与えられるか
   - **制約**: 技術的制約、依存関係、パフォーマンス要件
   - **期待される結果**: どうなったら成功か（検証方法含む）
3. 人間からの新しい指示を待つ

**使用例**:
```
/rebuild_context
```

### `/reflect` - 学習・ルール提案
**目的**: ユーザーの好み・パターンを学習し、CLAUDE.mdに反映

**実行内容**:
1. 最近の会話からユーザーの好みを抽出
2. CLAUDE.mdに追加すべき明示的ルールを提案
3. 推測・憶測は含めない（実際の発言ベース）

**使用例**:
```
/reflect
```

**提案例**:
```
以下のルールを追加することを提案します：

## Commit Message Style
- 必ず "why" を含める
- 形式: `stage(X): <why> - <what>`
- 例: `stage(2): guard against 15deg flicker - seed fixed`

根拠: 直近5回のコミットで全て "why" を重視したフィードバックがあったため
```

## コンテキスト管理

### セッション開始時の原則
1. **必ず CLAUDE.md を読み込む**
   - プロジェクト固有のルールを確認
   - グローバル設定との差異を把握

2. **Claude.ai からのハンドオーバー情報を確認**
   - 目的・スコープ・制約条件
   - Stage分割案
   - 成功の定義

3. **現在のStageを明確にする**
   - Stage番号
   - 現在の進捗状況
   - 次のマイルストーン

### チャットリセット戦略
以下の場合は **必ず** `/clear` して新チャット開始：

1. **Stage完了時**
   - 現在の状態をコミット
   - 次Stageの準備を整理
   - 新しいチャットで `/start_session`

2. **重大エラー発生時**
   - 3回失敗ルール発動時
   - 想定外の挙動が続く時
   - コンテキストが混乱している時

3. **長文化（10往復超）**
   - コンテキストウィンドウの劣化を防ぐ
   - 古い情報・誤った前提の蓄積を避ける

**リセット前のチェックリスト**:
- [ ] 現在の作業をコミット済みか
- [ ] 次Stageの準備は整理されているか
- [ ] 引き継ぐべき情報はメモしたか

## Implementation Flow

### 標準的な実装フロー
1. **Understand** - 既存コードパターンを研究
   - 類似機能の実装を確認
   - 命名規則・設計パターンを把握
   - 依存関係を理解

2. **Test** - テストを先に書く（Red）
   - 失敗するテストを作成
   - テストが「正しく失敗している」ことを確認
   - コミット（Red状態を記録）

3. **Implement** - テストを通す最小コード（Green）
   - テストをパスさせる最小限の実装
   - 過剰な機能追加を避ける
   - コミット（Green状態を記録）

4. **Refactor** - テストを保ちながら整理
   - コードの可読性向上
   - 重複排除
   - 命名改善
   - コミット（Refactor完了を記録）

5. **Commit** - 適切なコミットメッセージで記録
   - 形式: `stage(X): <why> - <what>`
   - "why"（理由）を必ず含める
   - 例: `stage(2): prevent flaky test - fix random seed`

6. **Review** - 人間がspot-check
   - 仕様逸脱がないか
   - 依存関係が不要に拡大していないか
   - 次Stageへの準備ができているか

### Stage完了の定義
以下が全て満たされた時にStage完了：
- [ ] 全テストがグリーン
- [ ] コードレビュー完了
- [ ] コミット済み
- [ ] 次Stageの準備整理済み

## Git Policy

### Branch運用
- **初期開発フェーズ（1人作業）**: main直接作業OK
  - プロジェクト立ち上げ時、基盤構築中はmainで作業
  - レビュアーがいない、並行開発がない段階
- **チーム開発フェーズ（複数人）**: feature branch必須
  - 複数人の変更が衝突しないよう、必ずブランチを切る
  - 命名: `feature/<stage>-<task>`
  - 例: `feature/stage2-pelvis-stability`

### Commit規約
- **形式**: `stage(X): <why> - <what>`
- **why（理由）を必ず1行で含める**
- **what（内容）は簡潔に**

**良い例**:
```
stage(2): prevent flaky test - fix random seed to 20251029
stage(3): improve readability - extract landmark extraction to separate function
stage(1): guard against missing frames - add frame count validation
```

**悪い例**:
```
fix bug  # whyがない
update code  # 何をしたか不明
stage(2): add test  # whyがない
```

### Push制限
- **Claude は commit まで**
- **push は人間のみ**
- 理由: 最終的なコード品質管理は人間が行う

## Security & Secrets

### 環境変数・秘密情報
- `.env` ファイルは必ずダミー値（本番値禁止）
- リポジトリにコミットするのは `.env.example`（ダミー値のみ）
- 本番の秘密情報は環境変数で注入、直接コードに書かない

**ダミー値の例（.env.example）**:
```
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name
DYNAMO_TABLE=your-table-name
```

### AWS認証
- 認証は IAM Role で委譲（推奨）
- 環境変数で認証情報を直入れしない
- IAM ポリシーは最小権限
  - S3: `PutObject`, `GetObject` のみ
  - DynamoDB: `PutItem`, `Query` のみ
  - 不要な権限は付与しない

### S3バケット・パス制限
- プロジェクト専用のバケット・パスに限定
- 例: `thf-motion-scan/<env>/<stage>/...`
- ワイルドカード許可は避ける

## Project Context

現在のプロジェクト情報はこのファイルではなく、プロジェクト直下の CLAUDE.md（もし存在すれば）に記載する。

グローバル設定（このファイル）はプロジェクト横断的なルールのみを定義。
# Conversation Guidelines
- 常に日本語で会話する

# Development Philosophy

## Core Beliefs
- **Incremental progress over big bangs** - 小さな変更を積み重ねる
- **Learning from existing code** - 既存コードを研究してから実装
- **Clear intent over clever code** - 明快さ優先
- **Pragmatic over dogmatic** - プロジェクトの現実に適応

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

**CRITICAL: Maximum 3 attempts per issue, then STOP.**

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

3. **人間へエスカレーション**:
   - 上記失敗ログを提示
   - 次の判断を仰ぐ

4. **Architectへハンドオフ**:
   - 上記失敗ログをClaude.ai（Architect）に渡す
   - 設計レベルでの見直しを相談

---

# 4つの絶対原則
1. **コメント駆動開発**: コード生成前に意図を明記
2. **曖昧語禁止**: "自然"・"スムーズ"・"直感的"等を使わない
3. **環境変数管理**: APIキー等を直書き禁止
4. **Human最終承認**: 各Phase完了時に必ず承認を得る

## 🚫 Forbidden Patterns
以下の行動は絶対禁止：

| ❌ 禁止行為 | ✅ 正しい方法 |
|------------|--------------|
| 削除理由不明のコード消去 | # DEPRECATED: 理由 (ADR-XXX参照) を明記 |
| コメントなし大規模変更 | 10行以上の変更には理由・影響範囲を記述 |
| Decision Log参照なし設計変更 | 必ずADR番号を引用 |

---

# 📝 コメントフォーマット

## ファイルヘッダー（必須）
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

## 関数コメント（必須）
```python
def func_name(arg: type) -> type:
    """
    What: [何をするか]
    Why: [なぜ必要か]
    Design Decision: [選択理由（ADR-XXX）]
    
    CRITICAL: [重要な制約]
    """
```

## 保護マーカー
- `# CRITICAL:` = 核心ロジック（削除厳禁）
- `# PHASE CORE LOGIC:` = Phase依存処理
- `# SECURITY REQUIREMENT:` = セキュリティ必須

---

# 🔄 Phase制導入

| Phase | 目的 | 主担当 | Human承認 | 状態 |
|-------|------|--------|-----------|------|
| 0 | 環境・ルール同期 | Claude | ✅ | ✅ 完了 |
| 1 | データIngest（pose_extractor, normalizer） | Claude+GPT | ✅ | ✅ 完了 |
| 2 | Processing（evaluators, health_check, worker） | Claude+GPT | ✅ | ✅ 完了 |
| 3 | Testing & Documentation | Claude+GPT | ✅ | ✅ 完了 |
| 4 | Cloud Deployment（AWS Lambda, S3, DynamoDB） | Claude | ✅ | ✅ 完了 |
| 5 | Dashboard/Recovery | Claude | - | 未実施 |

**Phase Gate**: 各Phase完了時に承認なしでは次へ進めない

**Phase更新履歴**:
- 2025-10-25: Phase 4をCloud Deploymentに変更（旧Dashboard/Recoveryは Phase 5へ）
- Phase 4完了内容: AWS Lambda Container, ECR, SAM, CloudFormation（ADR-007〜009）

---

# 🔁 実装フロー

## Implementation Flow（コードレベル - TDD）
各機能実装時の技術的手順：
1. **Understand** - 既存コードパターンを研究
2. **Test** - テストを先に書く（red）
3. **Implement** - テストを通す最小コード（green）
4. **Refactor** - テストを保ちながら整理
5. **Commit** - IMPLEMENTATION_PLAN.mdと紐づけてコミット

## 標準ワークフロー（プロジェクトレベル - Phase制）
Phase全体の進行手順：
1. Claude実装提案（上記Implementation Flowに従う）
2. コード生成（意図コメント付き）
3. GPT Subagent検証
4. Human承認
5. Decision Log記録
6. 次Phase移行

---

# 🆕 v2.1 - AI Co-Maintenance Protocol
**コンセプト**: "AIがコードを生成"→"AIがコード文化を維持"

## 責務定義
- **Claude Code**: 構文整合、型安全、Notion→コード変換、ドリフト監査
- **GPT**: 概念設計、スキーマ監督、品質監査、GitHub→Notion同期監督

## 実装優先度（Tier分類）
- 🔥 **Tier A（今すぐ）**: JSON Schema検証、SemVer厳守、冪等キー、ゴールデンテスト3件
- ⚡ **Tier B（1ヶ月）**: 構造化ログ、CloudWatch、DLQ+リトライ、Notion整合チェック
- 📈 **Tier C（将来）**: コストトラッキング、Feature Flag、バイアス監査

## ドリフト監査
- **目的**: Notion定義と実装の不整合を自動検出
- **実装**: `scripts/check_drift.py`
- **実行**: Push時 + 日次スケジュール

## Maintenance Window
- **定義**: 日曜 22:00 - 月曜 01:00 JST
- **ルール**: AIは構成変更を行わない

---

# 🛡️ 三層防御
```
予防層: Design First + ADR記録
  ↓
検知層: Health Check + Subagent監査
  ↓
対応層: Phase Gate + Emergency Recovery
```

---

# 🤖 Subagent一覧

| Subagent | 役割 | 適用Phase |
|----------|------|-----------|
| architecture-reviewer | 構造整合 | 1, 2, 4 |
| comment-reviewer | コメント品質 | 全Phase |
| doc-sync-checker | 仕様整合 | 1, 3 |
| diff-analyzer | 変更影響 | 3 |
| similarity-detector | 重複検出 | 2 |

**使い方**: Phase完了時にGPTが該当Subagentを実行し、構造化JSON出力

---

# 🔒 セキュリティ

## 必須対応
```python
# ❌ 禁止
api_key = "sk-abc123..."

# ✅ 必須
import os
api_key = os.getenv("AWS_SECRET_KEY")
```

## 保護対象
- **個人情報**: Face/Name/Path等をログ出力禁止
- **顔認識**: 処理後即座に匿名化ID変換
- **エラーログ**: warnings.jsonに集約（環境変数除外）

---

# 📊 データ整合性
```python
# ✅ NaN保持（列削除禁止）
df['col'] = df['col'].fillna(np.nan)

# ✅ 閾値外部化（config.json使用）
threshold = config['thresholds']['confidence_min']

# ✅ 再現性保証（乱数シード固定）
random.seed(42)
np.random.seed(42)

# ✅ 特殊文字禁止（JSON/YAML）
">=80deg flexion"  # ✅ OK
">=80° flexion"    # ❌ NG (UTF-8 error)
# CRITICAL: 度数記号（°）等の非ASCII文字はエンコーディングエラーの原因
```

---

# 🚨 緊急対応

## AI崩壊の兆候
- 曖昧語3回以上
- 循環参照検出
- コメント欠落10行以上
- Forbidden Patterns違反
- **3回失敗ルール違反**（同じエラーで3回以上試行）

## 復旧手順
1. 作業停止
2. Decision Log確認
3. `git revert` で安定版へ
4. Human介入レビュー
5. Phase Gateから再開

---

# 📋 ADR作成プロトコル

## Claude Codeの処理
1. `docs/adr/decision_log.md` に詳細ADR追記
2. Notionサマリー自動出力（ターミナル表示）
3. "上記をNotionにコピー&ペーストしてください" メッセージ

## サマリーフォーマット
- タイトル、日付、決定（1文）
- 概要（3-5ポイント）
- 技術詳細（必要に応じてコード例）

---

# ✅ デプロイ前チェックリスト
- [ ] JSON Schema検証がCIでブロック
- [ ] 冪等キー実装済み
- [ ] ゴールデンテスト 3件以上
- [ ] 構造化ログに `rules_version` + `artifact_sha`
- [ ] DLQ + アラート設定
- [ ] ドリフトチェック動作確認

---

# 📚 詳細ドキュメント
- 完全版: `docs/framework_full.md`
- Phase別詳細: `docs/phase_guide.md`
- ADR: `docs/adr/decision_log.md`
- 設計: `docs/design/overview.md`
- ドリフト監査: `scripts/check_drift.py`

---

# 🛠️ プロジェクト構造
```
thf-motion-scan/
├── claude.md              # このファイル
├── config.json            # 閾値等外部設定
├── warnings.json          # エラー集約
├── docs/
│   ├── adr/decision_log.md
│   └── design/overview.md
├── src/
│   ├── ingest/           # Phase 1
│   ├── processing/       # Phase 2
│   ├── output/           # Phase 3
│   └── dashboard/        # Phase 5
├── scripts/
│   └── check_drift.py    # ドリフト監査
└── tests/
```

---

# ✅ 初回導入チェック
- [ ] `docs/adr/decision_log.md` 作成
- [ ] `docs/design/overview.md` 作成
- [ ] `config.json` 作成
- [ ] `.env` で環境変数設定
- [ ] `scripts/check_drift.py` 設置
- [ ] Git初期化

---

# 🔧 コマンド体系

## `/start_session` - セッション開始
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

## `/continue_stage` - Stage作業継続
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

## `/run_tdd` - TDD実行
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

## `/timeout` - 失敗時リカバリ（停止・整理）
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

## `/rebuild_context` - コンテキストリセット
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

## `/reflect` - 学習・ルール提案
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

---

# 🔄 コンテキスト管理

## セッション開始時の原則
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

## チャットリセット戦略
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

---

# 🔀 Git Policy

## Branch運用
- **初期開発フェーズ（1人作業）**: main直接作業OK
  - プロジェクト立ち上げ時、基盤構築中はmainで作業
  - レビュアーがいない、並行開発がない段階
- **チーム開発フェーズ（複数人）**: feature branch必須
  - 複数人の変更が衝突しないよう、必ずブランチを切る
  - 命名: `feature/<stage>-<task>`
  - 例: `feature/stage2-pelvis-stability`

## Commit規約
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

## Push制限
- **Claude は commit まで**
- **push は人間のみ**
- 理由: 最終的なコード品質管理は人間が行う

---

# 🔐 Security & Secrets

## 環境変数・秘密情報
- `.env` ファイルは必ずダミー値（本番値禁止）
- リポジトリにコミットするのは `.env.example`（ダミー値のみ）
- 本番の秘密情報は環境変数で注入、直接コードに書かない

**ダミー値の例（.env.example）**:
```
AWS_REGION=us-east-1
S3_BUCKET=your-bucket-name
DYNAMO_TABLE=your-table-name
```

## AWS認証
- 認証は IAM Role で委譲（推奨）
- 環境変数で認証情報を直入れしない
- IAM ポリシーは最小権限
  - S3: `PutObject`, `GetObject` のみ
  - DynamoDB: `PutItem`, `Query` のみ
  - 不要な権限は付与しない

## S3バケット・パス制限
- プロジェクト専用のバケット・パスに限定
- 例: `thf-motion-scan/<env>/<stage>/...`
- ワイルドカード許可は避ける
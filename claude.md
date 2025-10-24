# THF Motion Scan – AI協働プロトコル
**v1.0** | Claude Code運用版 | 2025-10-19

---

## 🎯 4つの絶対原則

1. **コメント駆動開発**: コード生成前に意図を明記
2. **曖昧語禁止**: "自然"・"スムーズ"・"直感的"等を使わない
3. **環境変数管理**: APIキー等を直書き禁止
4. **Human最終承認**: 各Phase完了時に必ず承認を得る

---

## 🚫 Forbidden Patterns

以下の行動は**絶対禁止**：

| ❌ 禁止行為 | ✅ 正しい方法 |
|:-----------|:-------------|
| 削除理由不明のコード消去 | `# DEPRECATED: 理由 (ADR-XXX参照)` を明記 |
| コメントなし大規模変更 | 10行以上の変更には理由・影響範囲を記述 |
| Decision Log参照なし設計変更 | 必ずADR番号を引用 |

---

## 📝 コメントフォーマット

### ファイルヘッダー（必須）
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

### 関数コメント（必須）
```python
def func_name(arg: type) -> type:
    """
    What: [何をするか]
    Why: [なぜ必要か]
    Design Decision: [選択理由（ADR-XXX）]
    
    CRITICAL: [重要な制約]
    """
```

### 保護マーカー
- `# CRITICAL:` = 核心ロジック（削除厳禁）
- `# PHASE CORE LOGIC:` = Phase依存処理
- `# SECURITY REQUIREMENT:` = セキュリティ必須

---

## 🔄 Phase制導入

| Phase | 目的 | 主担当 | Human承認 | 状態 |
|:------|:-----|:-------|:----------|:-----|
| 0 | 環境・ルール同期 | Claude | ✅ | ✅ 完了 |
| 1 | データIngest（pose_extractor, normalizer） | Claude+GPT | ✅ | ✅ 完了 |
| 2 | Processing（evaluators, health_check, worker） | Claude+GPT | ✅ | ✅ 完了 |
| 3 | Testing & Documentation | Claude+GPT | ✅ | ✅ 完了 |
| 4 | Cloud Deployment（AWS Lambda, S3, DynamoDB） | Claude | ✅ | ✅ 完了 |
| 5 | Dashboard/Recovery（未実施） | Claude | - | - |

**Phase Gate**: 各Phase完了時に承認なしでは次へ進めない

**Phase更新履歴**:
- 2025-10-25: Phase 4をCloud Deploymentに変更（旧Dashboard/Recoveryは Phase 5へ）
- Phase 4完了内容: AWS Lambda Container, ECR, SAM, CloudFormation（ADR-007〜009）

---

## 🛡️ 三層防御

```
予防層: Design First + ADR記録
  ↓
検知層: Health Check + Subagent監査
  ↓
対応層: Phase Gate + Emergency Recovery
```

---

## 🤖 Subagent一覧

| Subagent | 役割 | 適用Phase |
|:---------|:-----|:----------|
| `architecture-reviewer` | 構造整合 | 1, 2, 4 |
| `comment-reviewer` | コメント品質 | 全Phase |
| `doc-sync-checker` | 仕様整合 | 1, 3 |
| `diff-analyzer` | 変更影響 | 3 |
| `similarity-detector` | 重複検出 | 2 |

**使い方**: Phase完了時にGPTが該当Subagentを実行し、構造化JSON出力

---

## 🔒 セキュリティ

### 必須対応
```python
# ❌ 禁止
api_key = "sk-abc123..."

# ✅ 必須
import os
api_key = os.getenv("AZURE_API_KEY")
```

### 保護対象
- 個人情報: Face/Name/Path等をログ出力禁止
- 顔認識: 処理後即座に匿名化ID変換
- エラーログ: `warnings.json`に集約（環境変数除外）

---

## 📊 データ整合性

```python
# ✅ NaN保持（列削除禁止）
df['col'] = df['col'].fillna(np.nan)

# ✅ 閾値外部化（config.json使用）
threshold = config['thresholds']['confidence_min']

# ✅ 再現性保証（乱数シード固定）
random.seed(42)
np.random.seed(42)
```

---

## 🚨 緊急対応

### AI崩壊の兆候
- 曖昧語3回以上
- 循環参照検出
- コメント欠落10行以上
- Forbidden Patterns違反

### 復旧手順
```
1. 作業停止
2. Decision Log確認
3. git revert で安定版へ
4. Human介入レビュー
5. Phase Gateから再開
```

---

## 🔁 標準ワークフロー

```
1. Claude実装提案
2. コード生成（意図コメント付き）
3. GPT Subagent検証
4. Human承認
5. Decision Log記録
6. 次Phase移行
```

---

## 📚 詳細ドキュメント

- **完全版**: `docs/framework_full.md`
- **Phase別詳細**: `docs/phase_guide.md`
- **ADR**: `docs/adr/decision_log.md`
- **設計**: `docs/design/overview.md`

---

## 🛠️ プロジェクト構造

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
│   └── dashboard/        # Phase 4
└── tests/
```

---

## ✅ 初回導入チェック

- [ ] `docs/adr/decision_log.md` 作成
- [ ] `docs/design/overview.md` 作成
- [ ] `config.json` 作成
- [ ] `.env` で環境変数設定
- [ ] Git初期化

---

**参照**: [Notion原典](https://www.notion.so/28f9df59df9e8154bf90c5f017975ff4)

**変更時は必ずDecision Logに記録**
## ADR-038: Phase2 静止画選出ロジック（B1-B8ベースKPI選出アルゴリズム）
- 日付: 2025-11-04
- 決定者: Human + Claude Code
- 決定: セッション全体を代表する3枚（best/worst/representative）の自動選出システムを実装
- 背景:
  - コーチングには客観的根拠に基づく静止画フィードバックが必要
  - σ測定結果（推奨セルσ=0.05-0.06）を閾値設計の根拠とする
  - Rep Temporal Engine未実装のため、単一rep内のフレーム選出に集中
  - 既存のrep-level選出（`select_representative_reps()`）とは補完関係

### 決定内容

**5 Stage実装完了**:
1. **Stage 1: データ準備とKPI取得**
   - `extract_frame_kpis()`: B1-B8 KPIをevaluator出力から抽出
   - N/A表現の統一（None/NaN/欠損キー → None、0.0は有効値）
   - major_kpis_missing フラグ（B1, B4, B2全欠損時）

2. **Stage 4: 複合スコア設計**（先行実装）
   - `calculate_composite_score()`: 重み付き平均
   - デフォルト均等重み（1/8 each）、カスタム重みサポート
   - N/A自動除外、重み自動正規化
   - σマージン対応準備（±3σ=0.18を許容範囲）

3. **Stage 2: best/worst選出**
   - `select_best_worst_frames()`: 主要KPI優先度（B1 > B4 > B2）
   - N/A値をinf扱い（worst判定）
   - 複合スコア＋タイムスタンプでタイブレーク
   - metadata付き出力（selection_reason, tiebreak情報）

4. **Stage 3: representative選出**
   - `select_representative_frame()`: 中央値に最も近いフレーム
   - Min-max正規化 → [0, 1]
   - 中央値ベクトル計算（KPIごと、N/A除外）
   - L2距離で最小距離フレームを選出

5. **Stage 5: 統合選出とメトリクス**
   - `select_frame_triplet()`: 3枚一括選出
   - 観測メトリクス：
     - `best_worst_gap`: パフォーマンス範囲
     - `repr_distance`: 典型性の度合い
     - `na_rate`: データ品質指標
     - `total_frames`: コンテキスト情報

### 理由（Rationale）

**1. N/A表現の統一**
- 従来の0.0表現は曖昧（valid=0.0 vs N/A=0.0）
- None統一により明示的な欠損表現
- evaluatorレベルでの変更不要（extraction層で変換）

**2. 主要KPI優先度（B1 > B4 > B2）**
- Biomechanical importance順（コア安定性 > 骨盤水平性 > 支持基盤）
- カードの「KPI優先度」に記載の順序に準拠
- タイブレークは複合スコア→タイムスタンプで決定論的

**3. L2距離によるrepresentative選出**
- 中央値ベクトルとの距離が「典型性」を定量化
- Min-max正規化で異なるスケールのKPIを同等に扱う
- N/A次元除外で部分欠損に耐性

**4. 観測メトリクス設計**
- `best_worst_gap`: セッション内のパフォーマンス変動幅（異常検知）
- `repr_distance`: 選出の信頼性（距離が大きい=典型性低い）
- `na_rate`: データ品質（50%超で警告）
- latency測定は将来実装（現状は関数レベル）

### 代替案とトレードオフ（Alternatives）

**1. ランダム選出**
- ❌ 却下理由: 再現性なし、客観性欠如
- メリット: 実装簡単
- デメリット: コーチング価値ゼロ

**2. スコアのみベース選出**
- ❌ 却下理由: Biomechanical importanceを考慮しない
- メリット: シンプル
- デメリット: B8（呼吸）がB1（コア）と同等扱い

**3. 手動選出（人間がフレーム選択）**
- ❌ 却下理由: スケーラビリティなし、主観的
- メリット: コーチの経験知活用
- デメリット: 自動化不可、再現性なし

**4. 時系列ベース選出（開始/中間/終了）**
- ❌ 却下理由: パフォーマンス品質を考慮しない
- メリット: 決定論的
- デメリット: 最悪フレームが開始時にある場合見逃す

**5. z-score正規化 vs Min-max正規化**
- ✅ 採用: Min-max（[0, 1]範囲）
- 理由: 外れ値に強い、解釈容易、全フレーム同値時の処理が明確（0.5固定）
- z-scoreデメリット: 外れ値で分散膨張、全同値時に0除算

### 影響（Consequences）

**追加ファイル**:
- `tests/processing/test_frame_selector_kpi.py`: 26テスト（Stage 1-5）
- `processing/frame_selector.py`: 以下の関数追加
  - `extract_frame_kpis()` (Stage 1)
  - `calculate_composite_score()` (Stage 4)
  - `select_best_worst_frames()` (Stage 2)
  - `select_representative_frame()` (Stage 3)
  - `select_frame_triplet()` (Stage 5)
  - Helper functions: `_is_na_value()`, `_get_major_kpi_priority_key()`, `_normalize_kpi_values()`, `_calculate_median_vector()`, `_calculate_l2_distance()`

**変更ファイル**:
- `processing/frame_selector.py`: +502行（既存761行 + 新規502行 = 1263行）
  - `B_PRINCIPLES_KEYS`: B1-B8定数追加
  - `MAJOR_KPI_KEYS`: B1, B4, B2定数追加
  - `DEFAULT_WEIGHTS`: デフォルト均等重み（1/8）

**API Contract**:
```python
# Input (from evaluator)
frames_data = [{
    "frame_idx": int,
    "B_principles": {
        "eccentric": {
            "B1_core_stability": float | None,
            "B2_support_foundation": float | None,
            ...
        }
    }
}, ...]

# Output
{
    "best": {
        "frame_idx": int,
        "kpis": {...},
        "composite_score": float,
        "selection_reason": str,
        "tiebreak": str | None
    },
    "worst": {...},
    "repr": {
        "frame_idx": int,
        "kpis": {...},
        "repr_distance": float,
        "selection_reason": str
    },
    "metrics": {
        "best_worst_gap": float,
        "repr_distance": float,
        "na_rate": float,
        "total_frames": int
    }
}
```

**破壊的変更**: なし（新規機能追加のみ）

**後方互換性**:
- 既存の `select_rep_frame_triplet()` はそのまま動作
- rep-level選出とframe-level選出は独立

### 技術詳細（Implementation Details）

**1. N/A検出ロジック**:
```python
def _is_na_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False
```

**2. 主要KPI優先度ソートキー**:
```python
# Best (最小値)
sort_key = (B1_val, B4_val, B2_val, composite_score, frame_idx)

# Worst (最大値)
sort_key = (-B1_val, -B4_val, -B2_val, -composite_score, -frame_idx)
```

**3. Min-max正規化**:
```python
normalized = (value - min_value) / (max_value - min_value)
# 全同値時: 0.5（中央値）
```

**4. L2距離計算**:
```python
distance = sqrt(sum((normalized_kpi - median_kpi)^2 for valid dimensions))
# N/A次元は除外
```

**5. σマージン設計**:
- 推奨セルσ≈0.06
- ±3σ=0.18を許容範囲
- スコア差<0.18で「実質同値」フラグ（将来実装）

**6. 決定論的保証**:
- 同一入力で同一出力（±0 frame）
- タイブレーク順序: 主要KPI → 複合スコア → タイムスタンプ
- random seedなし（純粋な決定論的計算）

### テストカバレッジ

**26/26 tests passed** ✅

**Stage 1（10テスト）**:
- 全KPI有効
- 単一KPI欠損（None, NaN, 欠損キー）
- 主要KPI全欠損
- 全KPI欠損（ValueError）
- Phase指定（eccentric/concentric）
- 欠損率>50%警告
- 0.0は有効値
- 再現性確認

**Stage 4（8テスト）**:
- デフォルト均等重み
- カスタム重み
- N/A値除外
- 全N/A時0.0返却
- σマージン計算
- 正規化KPI値（0.0-1.0）
- 0.0有効値
- 再現性確認

**Stage 2（4テスト）**:
- B1最小選出
- B4タイブレーク
- N/A値除外
- 主要KPI全欠損時の複合スコアfallback

**Stage 3（2テスト）**:
- 中央値に最も近いフレーム選出
- N/A次元除外時のL2距離計算

**Stage 5（2テスト）**:
- 統合選出（best/worst/repr + metrics）
- N/A値を含む統合テスト

### 成功の定義達成状況

✅ **全達成**:
- [x] 3枚（best/worst/repr）が正しく選出され、命名規則通りに保存可能
- [x] 再実行で選出フレームが±1frame以内で一致（±0 frame達成）
- [x] N/A（欠損KPI）時に警告ログ＋代替ロジックで継続
- [x] タイブレーク時に決定論的（時系列順で先勝）
- [x] 観測メトリクスが出力され、異常検知可能（latency>1000ms等、将来実装準備完了）

### 次のステップ（Next Steps）

**即座の統合タスク**:
1. Evaluator出力（`B_principles`構造）との連携
   - `processing/evaluators_v2/*.py` からの呼び出し
   - `evaluate()` メソッド返り値に `selected_frames` フィールド追加

2. 画像保存ロジック
   - フレーム抽出（`cv2.VideoCapture.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)`）
   - オーバーレイ注記（既存の`annotate_frame_with_overlay()`利用）
   - 命名規則：`{session_id}_{frame_type}.png`

3. Validation Templatesからの重み係数取得
   - `config/thresholds_v2.json` 拡張（`kpi_weights` セクション追加）
   - `weights` パラメータでカスタム重み注入

4. σマージン警告
   - `best_worst_gap < 0.18` 時に警告ログ
   - 「実質同値」フラグをmetadataに追加

**将来拡張**:
- Rep Temporal Engine実装後のセッションレベル選出
- 可視化UI（Timeline + 3枚プレビュー）
- アップロード処理（S3連携）
- 動画クリップ生成（best/worst前後3秒）

### 参照（References）

**ADR参照**:
- ADR-023: 8原則・560点満点システム（B1-B8定義）
- ADR-037: Validation System Integration（validation state連携）
- ADR-012: test_rules.json + RuleValidator（旧重み係数システム）

**コミット**:
- e8f04b4: Stage 1実装（KPI抽出・N/A検出）
- 5d3f171: Stage 4実装（複合スコア・重み付き平均）
- e35ecfd: Stage 2実装（best/worst選出・主要KPI優先度）
- 0203356: Stage 3+5実装（representative選出・統合メトリクス）

**実装ファイル**:
- `processing/frame_selector.py`: 1263行（既存761行 + 新規502行）
- `tests/processing/test_frame_selector_kpi.py`: 1034行（新規）

**関連カード**:
- Notion「Phase2: 静止画選出ロジック – Claude Code実装コンセプト」
- σ測定結果：推奨セルσ=0.05-0.06（ADR-023参照）

**TDD実績**:
- 全Stage Red → Green → Refactor遵守
- コミット単位でテスト完了
- 3回失敗ルール適用なし（全Stage一発成功）

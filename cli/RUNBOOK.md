# Rep CLI Runbook

## 緊急対応

### エラー発生時の対処

#### 1. パイプライン失敗
```bash
# エラーログ確認
# 通常、詳細なエラーメッセージが表示される

# 最新の安定版に戻す
git log --oneline | head -5  # 最近のコミット確認
git revert <commit-sha>      # 問題のコミットを revert
```

#### 2. 出力ファイル破損
```bash
# result.json が不正な場合
rm <out-dir>/result.json
python cli/rep_cli.py --video <video> --out-dir <out-dir>  # 再実行
```

#### 3. 依存関係エラー
```bash
# 仮想環境の再構築
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## ロールバック手順

### 最新コミットへのロールバック
```bash
# 変更を破棄して最新コミットに戻る
git status                    # 変更確認
git restore <file>            # 個別ファイルを戻す
git restore .                 # 全ファイルを戻す
```

### 特定バージョンへのロールバック
```bash
# 特定コミットに戻る
git log --oneline             # コミット履歴確認
git checkout <commit-sha>     # 特定コミットへ移動（detached HEAD）
git checkout -b rollback-branch  # ブランチ作成（必要時）
```

## よくある問題と解決

### Q: "ModuleNotFoundError: No module named 'processing'"
**A**: プロジェクトルートから実行しているか確認
```bash
pwd  # /path/to/thf_motion_scan であること
python cli/rep_cli.py --video test.mp4
```

### Q: result.json に versions フィールドがない
**A**: コードバージョンが古い可能性。最新版を pull
```bash
git pull origin main
source .venv/bin/activate
python cli/rep_cli.py --video test.mp4
```

### Q: trace.csv が空
**A**: evaluator が frame_data を提供していない（MVP段階の制約）
- `--dump-trace false` で CSV出力をスキップ
- または evaluator 側の frame_data 実装を待つ

## モニタリング

### 正常動作の確認
```bash
# テスト動画で動作確認
python cli/rep_cli.py --video test_videos/squat/sample.mp4
ls -l <out-dir>/result.json  # ファイル生成確認
cat <out-dir>/result.json | jq '.versions'  # versions確認
```

## エスカレーション

### 以下の場合は開発者へエスカレーション
1. 3回失敗ルール発動（同じエラーで3回失敗）
2. versions フィールドが欠落
3. evaluator が予期しないエラーを返す
4. ドキュメントに記載のない動作

**エスカレーション先**: GitHub Issues
**必要情報**: エラーメッセージ、コマンド、動画ファイルメタデータ

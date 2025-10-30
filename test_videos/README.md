# テスト動画配置ガイド

## 概要
このディレクトリにはローカル評価用のテスト動画を配置します。
各テストタイプに対応するサブディレクトリに動画ファイル（.mp4, .mov等）を配置してください。

## ディレクトリ構造

```
test_videos/
├── balance/                    # single_leg_squat
├── squat/                      # (将来の拡張用)
├── broad_jump/                 # (将来の拡張用)
├── vertical_jump/              # (将来の拡張用)
├── ten_yard_sprint/            # (将来の拡張用)
├── lateral_shuffle/            # (将来の拡張用)
└── overhead_med_ball_throw/    # (将来の拡張用)
```

## 対応テストタイプ

| ディレクトリ | テストタイプ | 対応評価器 |
|------------|------------|----------|
| balance/ | single_leg_squat | 片脚スクワット評価 |
| squat/ | (未実装) | - |
| broad_jump/ | (未実装) | - |
| vertical_jump/ | (未実装) | - |
| ten_yard_sprint/ | (未実装) | - |
| lateral_shuffle/ | (未実装) | - |
| overhead_med_ball_throw/ | (未実装) | - |

## 動画配置例

```bash
# 片脚スクワットの動画を配置
cp ~/Downloads/athlete_balance_test.mp4 test_videos/balance/

# 複数動画も配置可能
cp ~/Downloads/test1.mp4 test_videos/balance/
cp ~/Downloads/test2.mp4 test_videos/balance/
```

## 使用方法

```bash
# 配置した動画を評価
python cli/evaluate.py test_videos/balance/athlete_balance_test.mp4

# テストタイプを明示的に指定
python cli/evaluate.py test_videos/balance/test1.mp4 --test-type single_leg_squat
```

## 注意事項

⚠️ **重要**: 動画ファイル自体はGit管理外です（.gitignoreで除外）
- 動画ファイルは各自のローカル環境で配置してください
- 本番環境の個人情報を含む動画は配置しないでください
- テスト用のサンプル動画のみを使用してください

## 動画要件

- **形式**: .mp4, .mov等（MediaPipeがサポートする形式）
- **フレームレート**: 30fps以上推奨
- **解像度**: 720p以上推奨
- **撮影角度**: 全身が映るように正面または側面から撮影
- **照明**: 明るく、姿勢が明確に識別できること

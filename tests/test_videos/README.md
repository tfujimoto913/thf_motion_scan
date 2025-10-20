# Test Videos

## Purpose

THF Motion Scan評価器のテストに使用する動画ファイル配置ディレクトリ

## Usage

### 動画配置

テスト動画をこのディレクトリに配置します：

```bash
tests/test_videos/
├── sample_squat.mp4           # 片脚スタンススクワット
├── sample_upper_body_swing.mp4 # 上半身スイング
├── sample_skater_lunge.mp4    # スケーターランジ
└── ...
```

### サンプルデータ生成

動画からランドマークJSONを生成：

```bash
python -m processing.pose_extractor \
  --input tests/test_videos/sample_squat.mp4 \
  --output tests/fixtures/sample_landmarks.json
```

## Important

- **動画ファイルは.gitignore除外対象** (大容量のためGit管理外)
- **JSONファイルはGit管理対象** (tests/fixtures/に配置)
- テスト動画は以下の条件を満たすこと:
  - 解像度: 720p以上推奨
  - フレームレート: 30fps推奨
  - 長さ: 5-10秒程度
  - 被写体: 全身が映るように撮影

## File Formats

サポートされる動画形式:
- `.mp4` (H.264推奨)
- `.avi`
- `.mov`

## Security

- **個人情報除外**: 顔が明確に映らないように撮影
- **匿名化**: 動画ファイル名に個人名を含めない
- **公開禁止**: テスト動画は外部共有禁止

## Reference

- MediaPipe Pose: https://google.github.io/mediapipe/solutions/pose.html
- ADR-005: pose_extractor.pyのCLAUDE.md準拠化

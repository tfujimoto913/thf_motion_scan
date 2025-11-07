#!/usr/bin/env python3
"""
Purpose: sample_dataset/のmanifest.jsonにメタ情報（test_code, versions）を付与
Responsibility: dev環境準備のための一時スクリプト
Created: 2025-11-04 by Claude Code
Decision Log: ADR-TBD（dev環境サンプルデータ整備）

CRITICAL: 元のフィールド（seed, dataset, notes）は保持する
"""

import json
from pathlib import Path

# What: 3種目のマッピング定義
# Why: test_code（01/04/07）を自動判定するため
TEST_CODE_MAPPING = {
    "SLS": "01",
    "JUMP_LANDING": "04",
    "CROSSOVER": "07",
}

# What: 全種目共通のversions情報
# Why: Dry-run段階では全て1.0.0で統一（将来の拡張性確保）
VERSIONS = {
    "data_version": "1.0.0",
    "rules_version": "1.0.0",
    "schema_version": "1.0.0",
}


def add_metadata(base_dir: Path = Path("sample_dataset")) -> dict[str, bool]:
    """
    What: 各種目のmanifest.jsonにtest_codeとversionsを追加
    Why: dev環境でのバリデーション・識別のため

    Returns:
        dict: 種目名 → 成功/失敗のマップ
    """
    results = {}

    for folder_name, test_code in TEST_CODE_MAPPING.items():
        manifest_path = base_dir / folder_name / "manifest.json"

        if not manifest_path.exists():
            print(f"⚠️  {manifest_path} が見つかりません")
            results[folder_name] = False
            continue

        # 既存のmanifestを読み込み
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # メタ情報を追加（既存フィールドは保持）
        manifest["test_code"] = test_code
        manifest["versions"] = VERSIONS

        # 保存（インデント2、改行コード統一）
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            f.write("\n")  # 末尾改行

        print(f"✅ {folder_name} (test_code={test_code}) - メタ情報追加完了")
        results[folder_name] = True

    return results


if __name__ == "__main__":
    print("🔧 manifest.json メタ情報付与スクリプト開始")
    print("-" * 50)

    results = add_metadata()

    print("-" * 50)
    success_count = sum(results.values())
    total_count = len(results)

    if success_count == total_count:
        print(f"✅ 全{total_count}種目のメタ情報付与が完了しました")
    else:
        print(f"⚠️  {success_count}/{total_count}種目が完了（一部失敗）")
        exit(1)

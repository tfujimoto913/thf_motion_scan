#!/usr/bin/env python3
"""
Purpose: dev環境サンプルデータの受入条件確認
Responsibility: 配置完了確認・品質保証
Created: 2025-11-04 by Claude Code

CRITICAL: 全ての受入条件を満たしているかチェック
"""

import json
from pathlib import Path

# 受入条件
REQUIRED_SAMPLES = {
    "01_sls": {"test_code": "01", "min_records": 10},
    "04_jumplanding": {"test_code": "04", "min_records": 5},
    "07_crossover": {"test_code": "07", "min_records": 5},
}

REQUIRED_VERSION_FIELDS = ["data_version", "rules_version", "schema_version"]


def check_acceptance(base_dir: Path = Path("dev/samples")) -> bool:
    """
    What: 受入条件の確認

    受入条件:
    - 3種目のサンプル配置
    - 各種目に適切なデータ件数
    - versions付与済み（全フィールド）

    Returns:
        bool: 全条件を満たせばTrue
    """
    all_pass = True

    print("=" * 70)
    print("📋 受入条件確認 (Acceptance Criteria Check)")
    print("=" * 70)

    # 1. dev/samples/ ディレクトリ存在確認
    if not base_dir.exists():
        print(f"❌ {base_dir}/ が存在しません")
        return False
    print(f"✅ {base_dir}/ 存在確認")
    print()

    # 2. 各種目フォルダとファイルの確認
    for folder_name, criteria in REQUIRED_SAMPLES.items():
        print(f"📂 {folder_name}/ の確認:")
        print("-" * 70)

        folder_path = base_dir / folder_name
        data_csv = folder_path / "data.csv"
        manifest_json = folder_path / "manifest.json"

        # 2-1. フォルダ存在確認
        if not folder_path.exists():
            print(f"  ❌ フォルダが存在しません: {folder_path}")
            all_pass = False
            print()
            continue
        print(f"  ✅ フォルダ存在")

        # 2-2. data.csv 存在確認
        if not data_csv.exists():
            print(f"  ❌ data.csv が存在しません")
            all_pass = False
            print()
            continue
        print(f"  ✅ data.csv 存在")

        # 2-3. データ件数確認
        with open(data_csv, "r", encoding="utf-8") as f:
            lines = f.readlines()
            record_count = len(lines) - 1  # ヘッダー除く

        min_records = criteria["min_records"]
        if record_count >= min_records:
            print(f"  ✅ データ件数: {record_count}件 (最低{min_records}件)")
        else:
            print(f"  ❌ データ件数不足: {record_count}件 (最低{min_records}件)")
            all_pass = False

        # 2-4. manifest.json 存在確認
        if not manifest_json.exists():
            print(f"  ❌ manifest.json が存在しません")
            all_pass = False
            print()
            continue
        print(f"  ✅ manifest.json 存在")

        # 2-5. manifest.json 内容確認
        with open(manifest_json, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # test_code確認
        expected_test_code = criteria["test_code"]
        if manifest.get("test_code") == expected_test_code:
            print(f"  ✅ test_code: {expected_test_code}")
        else:
            print(
                f"  ❌ test_code不一致: {manifest.get('test_code')} (期待値: {expected_test_code})"
            )
            all_pass = False

        # versions確認
        if "versions" not in manifest:
            print(f"  ❌ versions フィールドが存在しません")
            all_pass = False
        else:
            versions = manifest["versions"]
            missing_fields = [
                f for f in REQUIRED_VERSION_FIELDS if f not in versions
            ]
            if missing_fields:
                print(f"  ❌ versions に欠落: {', '.join(missing_fields)}")
                all_pass = False
            else:
                print(
                    f"  ✅ versions付与済み: {', '.join(REQUIRED_VERSION_FIELDS)}"
                )

        print()

    # 3. 最終判定
    print("=" * 70)
    if all_pass:
        print("✅ 全ての受入条件を満たしています")
        print()
        print("【受入条件確認結果】")
        print("  ✅ 3種目のサンプル配置完了")
        print("  ✅ 各種目に適切なデータ件数")
        print("  ✅ versions付与済み（data/rules/schema version）")
    else:
        print("❌ 一部の受入条件を満たしていません")

    print("=" * 70)

    return all_pass


if __name__ == "__main__":
    success = check_acceptance()
    exit(0 if success else 1)

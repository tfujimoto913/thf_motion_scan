#!/usr/bin/env python3
"""
Purpose: sample_dataset/のmanifest.json必須フィールドをバリデーション
Responsibility: dev環境準備時の品質保証
Created: 2025-11-04 by Claude Code
Decision Log: ADR-TBD（dev環境サンプルデータ整備）

CRITICAL: test_code, versions全フィールド、dataset存在が必須
"""

import json
from pathlib import Path
from typing import Optional

# What: バリデーション対象の必須フィールド
# Why: dev環境での識別・バージョン管理に必要
REQUIRED_FIELDS = [
    "test_code",
    "dataset",
    "versions",
]

REQUIRED_VERSION_FIELDS = [
    "data_version",
    "rules_version",
    "schema_version",
]


def validate_manifest(manifest_path: Path) -> tuple[bool, list[str]]:
    """
    What: manifest.jsonの必須フィールド検証
    Why: 欠落・不整合を早期検出するため

    Returns:
        tuple: (成功/失敗, エラーメッセージリスト)
    """
    errors = []

    # ファイル存在確認
    if not manifest_path.exists():
        return False, [f"ファイルが存在しません: {manifest_path}"]

    # JSON読み込み
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"JSON解析エラー: {e}"]

    # 必須フィールド確認
    for field in REQUIRED_FIELDS:
        if field not in manifest:
            errors.append(f"必須フィールド欠落: {field}")

    # versions詳細確認
    if "versions" in manifest:
        versions = manifest["versions"]
        if not isinstance(versions, dict):
            errors.append("versions は辞書型である必要があります")
        else:
            for field in REQUIRED_VERSION_FIELDS:
                if field not in versions:
                    errors.append(f"versions.{field} が欠落しています")

    # dataset存在確認（指定されたCSVファイルの実在確認）
    if "dataset" in manifest:
        data_file = manifest_path.parent / manifest["dataset"]
        if not data_file.exists():
            errors.append(f"datasetファイルが存在しません: {data_file.name}")

    return len(errors) == 0, errors


def validate_all(base_dir: Path = Path("sample_dataset")) -> bool:
    """
    What: 全種目のmanifest.jsonをバリデーション
    Why: 配置前の品質保証

    Returns:
        bool: 全件成功ならTrue
    """
    all_success = True
    test_folders = ["SLS", "JUMP_LANDING", "CROSSOVER"]

    print("🔍 manifest.json バリデーション開始")
    print("-" * 60)

    for folder in test_folders:
        manifest_path = base_dir / folder / "manifest.json"
        success, errors = validate_manifest(manifest_path)

        if success:
            print(f"✅ {folder}/manifest.json - 検証成功")
        else:
            print(f"❌ {folder}/manifest.json - 検証失敗")
            for error in errors:
                print(f"   - {error}")
            all_success = False

    print("-" * 60)

    if all_success:
        print("✅ 全種目のバリデーションが成功しました")
    else:
        print("❌ 一部のバリデーションが失敗しました")

    return all_success


if __name__ == "__main__":
    success = validate_all()
    exit(0 if success else 1)

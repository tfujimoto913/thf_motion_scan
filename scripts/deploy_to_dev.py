#!/usr/bin/env python3
"""
Purpose: sample_dataset/をdev/samples/に配置（メタ情報付与済み）
Responsibility: dev環境準備の最終ステップ
Created: 2025-11-04 by Claude Code
Decision Log: ADR-TBD（dev環境サンプルデータ整備）

CRITICAL: 既存のdev/samples/を上書きする（再実行可能）
"""

import shutil
from pathlib import Path

# What: 種目フォルダとdev配置先のマッピング
# Why: test_code準拠の命名規則（{test_code}_{lowercase_name}）
DEPLOYMENT_MAP = {
    "SLS": "01_sls",
    "JUMP_LANDING": "04_jumplanding",
    "CROSSOVER": "07_crossover",
}


def deploy_to_dev(
    source_dir: Path = Path("sample_dataset"),
    target_dir: Path = Path("dev/samples"),
) -> dict[str, Path]:
    """
    What: 各種目フォルダをdev/samples/に配置
    Why: Threshold Review UI用のサンプルデータ提供

    Returns:
        dict: 種目名 → 配置先パスのマップ
    """
    deployed_paths = {}

    # dev/samples/ 作成（存在しない場合）
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 {target_dir}/ を作成（既存なら再利用）")
    print("-" * 60)

    for source_name, target_name in DEPLOYMENT_MAP.items():
        source_path = source_dir / source_name
        target_path = target_dir / target_name

        if not source_path.exists():
            print(f"⚠️  {source_path} が見つかりません（スキップ）")
            continue

        # 既存の配置先を削除（クリーンな再配置）
        if target_path.exists():
            shutil.rmtree(target_path)
            print(f"🗑️  既存の {target_name}/ を削除")

        # ディレクトリごとコピー
        shutil.copytree(source_path, target_path)
        deployed_paths[source_name] = target_path
        print(f"✅ {source_name}/ → {target_name}/ 配置完了")

    return deployed_paths


if __name__ == "__main__":
    print("📦 dev環境への配置開始")
    print("=" * 60)

    deployed = deploy_to_dev()

    print("=" * 60)
    print(f"✅ {len(deployed)}/{len(DEPLOYMENT_MAP)}種目の配置が完了しました\n")

    # 配置先パス一覧を出力
    print("📂 配置完了パス一覧:")
    print("-" * 60)
    for source_name, path in deployed.items():
        print(f"  {source_name:15} → {path}")
    print("-" * 60)

    # 成功判定
    if len(deployed) == len(DEPLOYMENT_MAP):
        print("✅ 全種目の配置に成功しました")
        exit(0)
    else:
        print(f"⚠️  一部の種目が配置されませんでした")
        exit(1)

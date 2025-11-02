"""
Purpose: Build thresholds_v2.json from Notion Templates (唯一の真実源)
Responsibility: Automated thresholds generation with SemVer metadata injection
Dependencies: jsonschema, utils.logger
Created: 2025-11-03 by Claude Code
Decision Log: Task A - thresholds_v2 自動生成

CRITICAL:
- Notion Templates を唯一の真実源とする
- versionsメタデータを自動注入
- JSON Schema検証を実行
- 構造化ログで変換差分を記録
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

try:
    import jsonschema
    from jsonschema import validate
except ImportError:
    print("ERROR: jsonschema is required. Install with: pip install jsonschema", file=sys.stderr)
    sys.exit(1)

# utils.loggerをインポート（プロジェクトルートからの相対パス）
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.logger import make_logger


def load_notion_templates(src_path: Path) -> Dict[str, Any]:
    """
    What: Notion exportsからテンプレートデータを読み込み
    Why: 唯一の真実源からthresholds生成
    Design Decision: JSON形式を仮定（CSV等は将来対応）

    Args:
        src_path: Notion export JSONファイルパス

    Returns:
        Dict: テンプレートデータ

    Raises:
        FileNotFoundError: ファイルが存在しない
        json.JSONDecodeError: JSON不正

    CRITICAL: templates配列が必須
    """
    if not src_path.exists():
        raise FileNotFoundError(f"Source file not found: {src_path}")

    with open(src_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "templates" not in data:
        raise ValueError(f"Invalid format: 'templates' key missing in {src_path}")

    return data


def _normalize_numeric(value: Union[str, int, float]) -> Union[int, float]:
    """Convert raw numeric strings to float if needed."""
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            # Allow integers represented as strings
            numeric = float(value)
            if numeric.is_integer():
                return int(numeric)
            return numeric
        except ValueError:
            raise ValueError(f"Value '{value}' is not a valid number")
    raise ValueError(f"Unsupported numeric type: {type(value)}")


def _normalize_band_value(raw_value: Any) -> Any:
    """
    Normalize band value definitions from Notion templates.

    Templates may store values as numbers, strings, booleans, or JSON-like strings.
    This helper converts them into schema-compliant Python types.
    """
    # Booleans are valid as-is
    if isinstance(raw_value, bool):
        return raw_value

    # Range encoded as list/tuple
    if isinstance(raw_value, (list, tuple)):
        if len(raw_value) != 2:
            raise ValueError(f"Range thresholds must contain exactly 2 elements: {raw_value}")
        return [
            _normalize_numeric(raw_value[0]),
            _normalize_numeric(raw_value[1]),
        ]

    # Numeric types or numeric strings
    if isinstance(raw_value, (int, float, str)):
        # Some exports may encode list-like values as JSON strings
        if isinstance(raw_value, str) and raw_value.strip().startswith("["):
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise ValueError(f"Unable to parse range value '{raw_value}'") from exc
            return _normalize_band_value(parsed)

        if isinstance(raw_value, str):
            lowered = raw_value.strip().lower()
            if lowered in {"true", "false"}:
                return lowered == "true"
        return _normalize_numeric(raw_value)

    raise ValueError(f"Unsupported threshold value type: {type(raw_value)} ({raw_value})")


def _build_bands(bands_definition: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Construct ordered band definitions from raw template data."""
    ordered_names = ["pass", "border", "fail"]
    result: List[Dict[str, Any]] = []

    for name in ordered_names:
        if name not in bands_definition:
            continue
        band_def = bands_definition[name]
        if "op" not in band_def or "value" not in band_def:
            raise ValueError(f"Band '{name}' requires 'op' and 'value': {band_def}")
        normalized_value = _normalize_band_value(band_def["value"])
        result.append(
            {
                "name": name,
                "op": band_def["op"],
                "value": normalized_value,
            }
        )

    if not result:
        raise ValueError("At least one band definition is required (pass/border/fail)")
    return result


def convert_to_thresholds_v2(templates: List[Dict[str, Any]], versions: Dict[str, str]) -> Dict[str, Any]:
    """
    What: Notion templates を thresholds_v2 形式に変換
    Why: ValidationEngineが期待するフォーマットへ変換
    Design Decision: primary/secondary bandsを明示的に分離

    Args:
        templates: Notion templateデータ
        versions: versionsメタデータ（rules_version, thresholds_version等）

    Returns:
        Dict: thresholds_v2形式のデータ

    CRITICAL: bandsの順序は保証しない（ValidationEngineが判定）
    """
    tests: List[Dict[str, Any]] = []
    seen_codes: Dict[str, Dict[str, Any]] = {}

    for template in templates:
        test_code = template.get("test_code")
        metric = template.get("metric")
        unit = template.get("unit")
        thresholds = template.get("thresholds", {})

        if not all([test_code, metric, unit]):
            raise ValueError(f"Missing required fields in template: {template}")

        if test_code in seen_codes:
            raise ValueError(f"Duplicate test_code detected: {test_code}")

        primary_bands = _build_bands(thresholds)

        test_entry = {
            "code": test_code,
            "metric": metric,
            "unit": unit,
            "primary": {
                "bands": primary_bands
            }
        }

        # secondaryがある場合は追加
        if "secondary" in template:
            secondary_definition = template["secondary"]
            if not isinstance(secondary_definition, dict):
                raise ValueError(f"secondary must be an object: {secondary_definition}")
            secondary_bands = _build_bands(secondary_definition)
            test_entry["secondary"] = {"bands": secondary_bands}

        tests.append(test_entry)
        seen_codes[test_code] = test_entry

    sorted_tests = sorted(tests, key=lambda item: item["code"])

    return {
        "versions": versions,
        "tests": sorted_tests
    }


def validate_schema(data: Dict[str, Any], schema_path: Path) -> None:
    """
    What: JSON Schemaでthresholds_v2を検証
    Why: 出力前に構造の正しさを保証
    Design Decision: jsonschemaライブラリ使用（draft-07）

    Args:
        data: 検証対象データ
        schema_path: JSON Schemaファイルパス

    Raises:
        jsonschema.ValidationError: スキーマ違反
        FileNotFoundError: スキーマファイルが存在しない

    CRITICAL: 検証失敗時はプログラム終了（不正データは出力しない）
    """
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    validate(instance=data, schema=schema)


def write_output(data: Dict[str, Any], out_path: Path, dry_run: bool = False) -> None:
    """
    What: thresholds_v2.jsonをファイル出力
    Why: ValidationEngineが読み込むファイルを生成
    Design Decision: 可読性のためindent=2、ensure_ascii=False

    Args:
        data: 出力データ
        out_path: 出力先パス
        dry_run: Trueの場合は標準出力のみ（ファイル出力しない）

    CRITICAL: dry-runモードはCI用（実ファイル生成なし）
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    if dry_run:
        print(json_str)
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json_str)


def _band_signature(band: Dict[str, Any]) -> Tuple[str, str, Any]:
    """Create a hashable signature for change detection."""
    value = band["value"]
    if isinstance(value, list):
        normalized_value: Any = tuple(value)
    else:
        normalized_value = value
    return (band["name"], band["op"], normalized_value)


def _summarize_diff(new: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Iterable[str]]:
    """Return diff summary between newly generated thresholds and existing data."""
    new_tests = {test["code"]: test for test in new.get("tests", [])}
    old_tests = {test["code"]: test for test in existing.get("tests", [])}

    added = sorted(set(new_tests) - set(old_tests))
    removed = sorted(set(old_tests) - set(new_tests))

    changed: List[str] = []
    common_codes = set(new_tests) & set(old_tests)
    for code in sorted(common_codes):
        new_bands = [_band_signature(band) for band in new_tests[code]["primary"]["bands"]]
        old_bands = [_band_signature(band) for band in old_tests[code]["primary"]["bands"]]
        if new_bands != old_bands:
            changed.append(code)
            continue
        new_secondary = new_tests[code].get("secondary", {}).get("bands", [])
        old_secondary = old_tests[code].get("secondary", {}).get("bands", [])
        if [
            _band_signature(band) for band in new_secondary
        ] != [
            _band_signature(band) for band in old_secondary
        ]:
            changed.append(code)

    version_changed = new.get("versions") != existing.get("versions")

    summary: Dict[str, Iterable[str]] = {
        "added_tests": added,
        "removed_tests": removed,
        "changed_tests": changed,
    }
    if version_changed:
        summary["version_diff"] = [
            f"old={existing.get('versions')}",
            f"new={new.get('versions')}",
        ]
    return summary


def main() -> int:
    """
    What: build_thresholds.pyのエントリーポイント
    Why: CLI I/Fで thresholds_v2.json 生成を自動化
    Design Decision: argparseで標準的なCLI提供

    Returns:
        int: 終了コード（0=成功、1=失敗）

    CRITICAL: 構造化ログで変換差分・エラーを記録
    """
    parser = argparse.ArgumentParser(
        description="Build thresholds_v2.json from Notion Templates"
    )
    parser.add_argument("--src", required=True, type=Path, help="Source Notion export JSON path")
    parser.add_argument("--out", required=True, type=Path, help="Output thresholds_v2.json path")
    parser.add_argument("--rules-version", required=True, help="Rules version (SemVer, e.g., 0.2.0)")
    parser.add_argument("--thresholds-version", required=True, help="Thresholds version (SemVer, e.g., 2.0.0)")
    parser.add_argument("--normalization-version", default="none", help="Normalization version (default: none)")
    parser.add_argument("--artifact-sha", required=True, help="Git commit SHA (short or full)")
    parser.add_argument("--dry-run", action="store_true", help="Print output to stdout without writing file")
    parser.add_argument("--log-level", default="INFO", help="Log level (DEBUG, INFO, WARN, ERROR)")
    parser.add_argument("--log-file", type=Path, help="Log output file (optional)")

    args = parser.parse_args()

    # 構造化ログ初期化
    logger = make_logger(
        component="tools:build_thresholds",
        default_context={
            "test_code": "N/A",
            "rules_version": args.rules_version,
            "normalization_version": args.normalization_version,
            "artifact_sha": args.artifact_sha,
        },
        log_level=args.log_level,
        log_file=str(args.log_file) if args.log_file else None,
    )

    try:
        logger.info(
            "Starting thresholds_v2 build",
            src_path=str(args.src),
            out_path=str(args.out),
            dry_run=args.dry_run,
        )

        # 1. Notion templatesを読み込み
        notion_data = load_notion_templates(args.src)
        templates = notion_data["templates"]
        logger.info(
            "Loaded Notion templates",
            template_count=len(templates),
        )

        # 2. versionsメタデータを構築
        versions = {
            "rules_version": args.rules_version,
            "thresholds_version": args.thresholds_version,
            "normalization_version": args.normalization_version,
            "artifact_sha": args.artifact_sha,
        }

        # 3. thresholds_v2形式に変換
        thresholds_v2 = convert_to_thresholds_v2(templates, versions)
        logger.info(
            "Converted to thresholds_v2 format",
            test_count=len(thresholds_v2["tests"]),
        )

        # 4. JSON Schema検証
        schema_path = Path(__file__).parent.parent / "schema" / "thresholds_v2.schema.json"
        validate_schema(thresholds_v2, schema_path)
        logger.info(
            "Schema validation passed",
            schema_path=str(schema_path),
        )

        # 5. 既存ファイルとの diff サマリを記録
        if args.out.exists():
            try:
                existing_data = json.loads(args.out.read_text(encoding="utf-8"))
                diff_summary = _summarize_diff(thresholds_v2, existing_data)
                logger.info("Comparison with existing output", **diff_summary)
            except json.JSONDecodeError:
                logger.warn(
                    "Existing thresholds_v2.json is not valid JSON; diff skipped",
                    existing_path=str(args.out),
                )

        # 6. 出力
        write_output(thresholds_v2, args.out, dry_run=args.dry_run)

        if args.dry_run:
            logger.info("Dry-run completed (no file written)")
        else:
            logger.info(
                "Thresholds build completed",
                output_path=str(args.out),
            )

        return 0

    except FileNotFoundError as e:
        logger.error(
            "File not found",
            error_code="FILE_NOT_FOUND",
            error_message=str(e),
        )
        return 1
    except json.JSONDecodeError as e:
        logger.error(
            "JSON decode error",
            error_code="JSON_DECODE_ERROR",
            error_message=str(e),
        )
        return 1
    except jsonschema.ValidationError as e:
        logger.error(
            "Schema validation failed",
            error_code="SCHEMA_VALIDATION_FAILED",
            error_message=str(e),
        )
        return 1
    except ValueError as e:
        logger.error(
            "Invalid data",
            error_code="INVALID_DATA",
            error_message=str(e),
        )
        return 1
    except Exception as e:
        logger.error(
            "Unexpected error",
            error_code="UNEXPECTED_ERROR",
            error_message=str(e),
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

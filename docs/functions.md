# Functions & Classes Index

_Auto-generated. Edit code/docstrings, not this file._


## `config.compat`

- **function** `check_compat` — Check compatibility between current and required version sets.  
  `./src/config/compat.py:144`
- **function** `compare_versions` — Compare two semantic versions and determine compatibility.  
  `./src/config/compat.py:51`
- **function** `parse_semver` — Parse semantic version string into (major, minor, patch) tuple.  
  `./src/config/compat.py:19`

## `config.loader`

- **function** `get_versions` — required_versions.json があれば拾い、無ければ unknown を返す。  
  `./src/config/loader.py:12`
- **function** `load_thresholds` — thresholds.json を読み込む（デフォルトは config/thresholds/thresholds.json）。  
  `./src/config/loader.py:7`

## `handler`

- **function** `convert_float_to_decimal` — DynamoDB用にfloatをDecimalに変換  
  `./src/handler.py:273`
- **function** `extract_test_type` — S3キーからテストタイプを抽出  
  `./src/handler.py:231`
- **function** `lambda_handler` — Lambda関数のメインハンドラー  
  `./src/handler.py:56`
- **function** `save_results_to_s3` — 処理結果をS3に保存  
  `./src/handler.py:243`
- **function** `save_to_dynamodb` — 処理結果をDynamoDBに保存  
  `./src/handler.py:292`

## `monitoring.config_loader`

- **function** `deep_merge` — Deep merge two dictionaries, with override taking precedence.  
  `./src/monitoring/config_loader.py:27`
- **function** `get_threshold` — Get threshold value from config using dot-notation path.  
  `./src/monitoring/config_loader.py:120`
- **function** `load_monitoring_config` — Load monitoring configuration with environment-specific overrides.  
  `./src/monitoring/config_loader.py:67`
- **function** `load_yaml_file` — Load YAML file with error handling.  
  `./src/monitoring/config_loader.py:45`

## `monitoring.event_logger`

- **class** `MonitoringEventLogger` — What: Logger for monitoring events (alarms, thresholds, rollbacks)  
  `./src/monitoring/event_logger.py:24`
- **function** `get_event_logger` — What: Get or create global MonitoringEventLogger instance  
  `./src/monitoring/event_logger.py:213`
- **function** `log_alarm_triggered` — What: Log CloudWatch alarm trigger event  
  `./src/monitoring/event_logger.py:236`
- **function** `log_rollback` — What: Log rollback event  
  `./src/monitoring/event_logger.py:274`
- **function** `log_threshold_breach` — What: Log threshold breach event  
  `./src/monitoring/event_logger.py:306`

## `monitoring.sns_notifier`

- **class** `MessageValidationError` — Raised when message payload fails validation.  
  `./src/monitoring/sns_notifier.py:44`
- **class** `SNSNotificationError` — Base exception for SNS notification errors.  
  `./src/monitoring/sns_notifier.py:39`
- **function** `build_message_payload` — Build standardized message payload conforming to contract.  
  `./src/monitoring/sns_notifier.py:99`
- **function** `send_notification` — Send notification to SNS topic with contract validation.  
  `./src/monitoring/sns_notifier.py:144`
- **function** `send_test_notification` — Send a test notification for delivery verification.  
  `./src/monitoring/sns_notifier.py:249`
- **function** `validate_message` — Validate message payload against contract specification.  
  `./src/monitoring/sns_notifier.py:49`

## `thresholds_editor.change_logger`

- **class** `ChangeLogger` — What: 閾値変更履歴のロガー（idempotency保証）  
  `./src/thresholds_editor/change_logger.py:26`
- **function** `get_logger` — What: ChangeLoggerインスタンスを取得（シングルトン）  
  `./src/thresholds_editor/change_logger.py:296`

## `thresholds_editor.changelog`

- **class** `ChangeLogEntry` — _no doc_  
  `./src/thresholds_editor/changelog.py:13`
- **function** `append_jsonl` — JSON Lines 形式でログを1行追加する（ファイルが無ければ作成）  
  `./src/thresholds_editor/changelog.py:112`
- **function** `iso_now` — UTC ISO8601 タイムスタンプを返す  
  `./src/thresholds_editor/changelog.py:100`
- **function** `iso_now_id` — 変更IDを生成（chg_ + ISO8601）  
  `./src/thresholds_editor/changelog.py:104`
- **function** `log_undo` — 直前の変更をロールバックした時のログエントリを追記する。  
  `./src/thresholds_editor/changelog.py:84`

## `thresholds_editor.models`

- **class** `Band` — Single half-open band boundary definition.  
  `./src/thresholds_editor/models.py:14`
- **class** `MetricThreshold` — Per-metric threshold configuration.  
  `./src/thresholds_editor/models.py:46`
- **class** `ThreeTierBands` — Three-tier half-open band definition (OK / ATTENTION / NG).  
  `./src/thresholds_editor/models.py:25`
- **class** `ThresholdDocument` — Root document for schema_version 2.0 thresholds.  
  `./src/thresholds_editor/models.py:92`
- **function** `load_document_from_file` — _no doc_  
  `./src/thresholds_editor/models.py:173`
- **function** `load_threshold_document` — _no doc_  
  `./src/thresholds_editor/models.py:106`
- **function** `save_document_to_file` — _no doc_  
  `./src/thresholds_editor/models.py:178`
- **function** `serialize_threshold_document` — _no doc_  
  `./src/thresholds_editor/models.py:156`

## `thresholds_editor.preview`

- **class** `PreviewResult` — _no doc_  
  `./src/thresholds_editor/preview.py:36`
- **class** `RepresentativeSample` — _no doc_  
  `./src/thresholds_editor/preview.py:26`
- **function** `analyse_reclassification` — Calculate reclassification metrics and representatives.  
  `./src/thresholds_editor/preview.py:43`
- **function** `classify_value` — Classify a numeric value into OK/ATTN/NG (half-open bands).  
  `./src/thresholds_editor/preview.py:14`

## `thresholds_editor.safeguards`

- **class** `ConfirmationError` — Raised when the apply confirmation token is missing or invalid.  
  `./src/thresholds_editor/safeguards.py:10`
- **class** `EnvironmentError` — Raised when an operation is attempted outside the allowed environment.  
  `./src/thresholds_editor/safeguards.py:6`
- **function** `ensure_dev_environment` — _no doc_  
  `./src/thresholds_editor/safeguards.py:14`
- **function** `require_apply_confirmation` — _no doc_  
  `./src/thresholds_editor/safeguards.py:19`
- **function** `should_block_apply` — _no doc_  
  `./src/thresholds_editor/safeguards.py:24`

## `thresholds_editor.snapshots`

- **function** `snapshot_thresholds` — _no doc_  
  `./src/thresholds_editor/snapshots.py:11`

## `validation_engine.apply`

- **class** `ValidationResult` — _no doc_  
  `./src/validation_engine/apply.py:25`
- **function** `apply_rep` — What: Compute validation state for a single rep evaluation.  
  `./src/validation_engine/apply.py:206`
- **function** `apply_session` — What: Compute validation state for session-level aggregates (e.g., best-of-three reps).  
  `./src/validation_engine/apply.py:236`

## `validation_engine.compat`

- **class** `CompatibilityStatus` — _no doc_  
  `./src/validation_engine/compat.py:38`
- **class** `SemVer` — _no doc_  
  `./src/validation_engine/compat.py:21`
- **function** `aggregate_status` — What: Aggregate multiple compatibility results into a single status.  
  `./src/validation_engine/compat.py:67`
- **function** `compare_version_map` — What: Compare multiple versions (rules, thresholds, normalization) at once.  
  `./src/validation_engine/compat.py:82`
- **function** `compare_versions` — What: Compare two SemVer strings and return compatibility status.  
  `./src/validation_engine/compat.py:44`

## `validation_engine.validator_rep`

- **function** `validate_rep` — What: Validate a single rep result and return validation state with violations.  
  `./src/validation_engine/validator_rep.py:32`

## `validation_engine.validator_session`

- **function** `aggregate_session` — What: Aggregate multiple rep results into session-level summary.  
  `./src/validation_engine/validator_session.py:29`
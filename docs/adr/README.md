# Architecture Decision Records

This directory contains the codified decisions that guide the THF Motion Scan project.

## Index

| ADR | Title | Date | Status |
| --- | ----- | ---- | ------ |
| ADR-001 | [AI協働開発フレームワーク導入](0001-ai.md) | 2025-10-19 | Accepted |
| ADR-002 | [THF評価閾値のconfig.json管理](0002-thfconfig-json.md) | 2025-10-19 | Accepted |
| ADR-003 | [身体スケール正規化処理の実装](0003-adr-003.md) | 2025-10-19 | Accepted |
| ADR-004 | [Health Check実装とwarnings.json管理](0004-health-checkwarnings-json.md) | 2025-10-19 | Accepted |
| ADR-005 | [pose_extractor.pyのCLAUDE.md準拠化とCLI機能追加](0005-pose-extractor-pyclaude-mdcli.md) | 2025-10-21 | Accepted |
| ADR-006 | [Phase 2完了レポート作成とREADME充実](0006-phase-2readme.md) | 2025-10-21 | Accepted |
| ADR-007 | [AWS Lambda Container Architectureの選択](0007-aws-lambda-container-architecture.md) | 2025-10-24 | Accepted |
| ADR-008 | [CloudFormation循環依存の解決](0008-cloudformation.md) | 2025-10-25 | Accepted |
| ADR-009 | [Docker Multi-Platform Build対応（arm64→amd64）](0009-docker-multi-platform-build-arm64amd64.md) | 2025-10-25 | Accepted |
| ADR-010 | [Azure関連記述の削除とドキュメント整理](0010-azure.md) | 2025-10-25 | Accepted |
| ADR-011 | [出力物生成機能の実装](0011-adr-011.md) | 2025-10-25 | Accepted |
| ADR-012 | [Phase 3 - ルール定義ファイルの充実](0012-phase-3.md) | 2025-10-25 | Accepted |
| ADR-013 | [セキュリティポリシーの明文化](0013-adr-013.md) | 2025-10-26 | Accepted |
| ADR-014 | [Phase 5 - Streamlit Dashboard実装](0014-phase-5-streamlit-dashboard.md) | 2025-10-26 | Accepted |
| ADR-015 | [84点満点システムの完全実装とDashboard UI/UX改善](0015-84dashboard-ui-ux.md) | 2025-10-27 | Accepted |
| ADR-017 | [worker.py出力形式の標準化（score.json + manifest.json）](0017-worker-py-score-json-manifest-json.md) | 2025-10-27 | Accepted |
| ADR-018 | [チーム一括受付システム](0018-adr-018.md) | 2025-10-27 | Accepted |
| ADR-019 | [統一評価器インターフェース](0019-adr-019.md) | 2025-10-27 | Accepted |
| ADR-020 | [選手登録フィールド拡張とDynamoDBキー構造修正](0020-dynamodb.md) | 2025-10-27 | Accepted |
| ADR-021 | [Phase 2.5 Stage 1 - 管理者編集API + 身長フィールド](0021-phase-2-5-stage-1-api.md) | 2025-10-29 | Accepted |
| ADR-022 | [8原則・Eccentric/Concentric評価システム（evaluators_v2導入）](0022-8eccentric-concentric-evaluators-v2.md) | 2025-10-30 | Accepted |
| ADR-023 | [v2.1移行 - 560点満点統一配点システム](0023-v2-1-560.md) | 2025-10-30 | Accepted |
| ADR-024 | [Lambda v2.1統合とCloudWatch監視基盤](0024-lambda-v2-1cloudwatch.md) | 2025-10-30 | Accepted |
| ADR-025 | [Phase 5 Docker Deployment完了 + 本番運用監視基盤強化](0025-phase-5-docker-deployment.md) | 2025-11-01 | Successful（CodeSha: f0e46cf512...） |
| ADR-026 | [Phase 5 Ops Guardrails（CloudWatch Dashboards / DLQ Runbook / Structured Logging）](0026-phase-5-ops-guardrails-cloudwatch-dashboards-dlq-runbook-structured-logging.md) | 2025-11-07 | Accepted |
| ADR-027 | [Dashboard Session Detail Enhancements（Radar NA / Version Header / UI Metrics）](0027-dashboard-session-detail-enhancements-radar-na-version-header-ui-metrics.md) | 2025-11-07 | Accepted |
| ADR-028 | [thresholds.json v1.0.0 初版エクスポート（Versions付与・SemVer管理基盤）](0028-thresholds-json-v1-0-0-versionssemver.md) | 2025-11-02 | Accepted |
| ADR-029 | [Rep CLI MVP実装（単一動画評価エンドツーエンド）](0029-rep-cli-mvp.md) | 2025-11-03 | Accepted |
| ADR-030 | [thresholds.json バリデータ自動化（jsonschema + pre-commit + CI）](0030-thresholds-json-jsonschema-pre-commit-ci.md) | 2025-11-04 | Accepted |
| ADR-031 | [thresholds.json バージョン互換性チェッカー（SemVer準拠）](0031-thresholds-json-semver.md) | 2025-11-03 | Accepted |
| ADR-032 | [構造化ログ規約の固定（統一キースキーマ・基盤実装）](0032-adr-032.md) | 2025-11-03 | Accepted |
| ADR-033 | [Validate Workflow 段階的ロールアウト（schema 必須・lint/test 警告化）](0033-validate-workflow-schema-lint-test.md) | 2025-11-06 | Accepted |
| ADR-034 | [Phase 0-4 Validation Pipeline 運用開始（QC Gate / ドキュメント整備）](0034-phase-0-4-validation-pipeline-qc-gate.md) | 2025-11-06 | Accepted |
| ADR-034 | [Dashboard Version Compatibility UI統合（v2.1 MVP）](0034-dashboard-version-compatibility-ui-v2-1-mvp.md) | 2025-11-03 | Accepted |
| ADR-035 | [CLI Export Pipeline統合（rep/session validation state付与）](0035-cli-export-pipeline-rep-session-validation-state.md) | 2025-11-03 | Accepted |
| ADR-036 | [Validation State Badge UI統合（Dashboard v2.1 Task D）](0036-validation-state-badge-ui-dashboard-v2-1-task-d.md) | 2025-11-03 | Accepted |
| ADR-037 | [Validation System Integration（Task A〜D統合）](0037-validation-system-integration-task-ad.md) | 2025-11-03 | Accepted |
| ADR-038 | [Phase2 静止画選出ロジック（B1-B8ベースKPI選出アルゴリズム）](0038-phase2-b1-b8kpi.md) | 2025-11-04 | Accepted |
| ADR-039 | [Dev Billing Guardrails Thresholds & Follow-Ups](0039-dev-billing-guardrails-thresholds-and-followups.md) | 2025-11-08 | Accepted |

## How to Create a New ADR

1. Copy `template.md` to a new file named `XXXX-your-slug.md` where `XXXX` is the next sequential number.
2. Update the heading (`# ADR-XXXX: Title`) and complete each section of the template.
3. Link related ADRs in the References section to maintain traceability.
4. Submit the ADR in a pull request; once merged, update this README table.

## Template

- See [`template.md`](template.md) for the canonical ADR structure.
- Fields follow [Michael Nygard's ADR format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

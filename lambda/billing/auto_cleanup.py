"""EBS unattached volume cleanup Lambda."""
from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .common import emit_billing_event, utc_now, _normalise_tag_value

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

ec2 = boto3.client("ec2")
sns = boto3.client("sns")

SNS_ARN = os.getenv("SNS_ARN")
DRY_RUN = os.getenv("DRY_RUN", "true").strip().lower() == "true"
TTL_HOURS = max(int(os.getenv("UNATTACHED_TTL_H", "48")), 1)
TAG_KEY = os.getenv("AUTOCLEANUP_TAG_KEY", "AutoCleanup")
TAG_VALUE = os.getenv("AUTOCLEANUP_TAG_VALUE", "allow")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")


def _volume_tags(volume: Dict[str, Any]) -> Dict[str, str]:
    tags = {}
    for tag in volume.get("Tags", []) or []:
        key = tag.get("Key")
        value = tag.get("Value")
        if key is not None and value is not None:
            tags[str(key)] = str(value)
    return tags


def _eligible_volumes() -> List[Dict[str, Any]]:
    cutoff = utc_now() - timedelta(hours=TTL_HOURS)

    paginator = ec2.get_paginator("describe_volumes")
    eligible: List[Dict[str, Any]] = []

    for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
        for volume in page.get("Volumes", []):
            created_at = volume.get("CreateTime")
            if not created_at or created_at >= cutoff:
                continue

            tags = _volume_tags(volume)
            if tags:
                tag_value = tags.get(TAG_KEY)
                if tag_value is None:
                    continue  # Explicit opt-out
                if _normalise_tag_value(tag_value) != _normalise_tag_value(TAG_VALUE):
                    continue

            eligible.append(volume)

    return eligible


def _format_report(volume: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "VolumeId": volume.get("VolumeId"),
        "SizeGiB": volume.get("Size"),
        "CreateTime": volume.get("CreateTime").isoformat() if volume.get("CreateTime") else None,
        "Tags": _volume_tags(volume),
    }


def _publish(topic_arn: str, subject: str, message: Dict[str, Any]) -> None:
    try:
        sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=json.dumps(message, ensure_ascii=False, default=str),
        )
    except (ClientError, BotoCoreError) as exc:
        LOGGER.warning("Failed to publish SNS notification: %s", exc)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    event_dry_run: Optional[bool] = None
    if isinstance(event, dict) and "dry_run" in event:
        event_dry_run = bool(event.get("dry_run"))

    effective_dry_run = DRY_RUN if event_dry_run is None else event_dry_run

    volumes = _eligible_volumes()
    report = [_format_report(volume) for volume in volumes]

    summary = {
        "environment": ENVIRONMENT,
        "dry_run": effective_dry_run,
        "ttl_hours": TTL_HOURS,
        "count": len(report),
        "volumes": report,
    }

    emit_billing_event(
        kind="ebs_unattached",
        source="auto_cleanup",
        payload=summary,
        context=context,
    )

    if not volumes:
        return {"ok": True, "deleted": 0, **summary}

    if effective_dry_run:
        if SNS_ARN:
            _publish(
                SNS_ARN,
                subject="[WARN] EBS unattached volumes > threshold",
                message={"environment": ENVIRONMENT, "volumes": report},
            )
        return {"ok": True, "dry_run": True, **summary}

    deleted = 0
    errors: List[Dict[str, Any]] = []

    for volume in volumes:
        volume_id = volume.get("VolumeId")
        if not volume_id:
            continue

        try:
            snapshot = ec2.create_snapshot(
                VolumeId=volume_id,
                Description="AutoCleanup pre-delete snapshot",
            )
            snapshot_id = snapshot.get("SnapshotId")
            if snapshot_id:
                ec2.create_tags(
                    Resources=[snapshot_id],
                    Tags=[
                        {"Key": "OriginVolumeId", "Value": volume_id},
                        {"Key": "CleanupAt", "Value": utc_now().isoformat().replace("+00:00", "Z")},
                        {"Key": "Environment", "Value": ENVIRONMENT},
                    ],
                )
        except (ClientError, BotoCoreError) as exc:
            LOGGER.error("Snapshot creation failed for %s: %s", volume_id, exc)
            errors.append({"volume": volume_id, "error": str(exc)})
            continue

        try:
            ec2.delete_volume(VolumeId=volume_id)
            deleted += 1
        except (ClientError, BotoCoreError) as exc:
            LOGGER.error("Failed to delete volume %s: %s", volume_id, exc)
            errors.append({"volume": volume_id, "error": str(exc)})

    if SNS_ARN:
        level = "INFO" if not errors else "WARN"
        _publish(
            SNS_ARN,
            subject=f"[{level}] EBS cleanup completed",
            message={
                "environment": ENVIRONMENT,
                "deleted": deleted,
                "errors": errors,
                "volumes": report,
            },
        )

    result = {"ok": True, "deleted": deleted, "errors": errors, **summary}

    emit_billing_event(
        kind="ebs_cleanup",
        source="auto_cleanup",
        payload={**summary, "deleted": deleted, "errors": errors},
        context=context,
    )

    return result

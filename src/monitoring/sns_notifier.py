"""
SNS Notification Helper for Monitoring Alerts

Purpose: Send standardized WARN/FAIL notifications to SNS topics
Responsibility: Message formatting, validation, and delivery
Created: 2025-11-04
Decision Log: ADR-040 (UI Monitoring 2-Tier Alert System)

Contract: contracts/sns_notification.yaml (version 1.0.0)

CRITICAL: All messages must conform to the contract specification
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Contract version
MESSAGE_CONTRACT_VERSION = "1.0.0"

# Required keys per contract
REQUIRED_KEYS = ["env", "overall", "source", "reason", "url"]

# Allowed values per contract
ALLOWED_ENV = ["dev", "stg", "prod"]
ALLOWED_OVERALL = ["OK", "WARN", "FAIL"]
ALLOWED_SOURCE = ["metrics_monitor", "billing_monitor", "ui_monitor", "lambda_errors"]
ALLOWED_SEVERITY = ["INFO", "WARN", "FAIL", "CRITICAL"]


class SNSNotificationError(Exception):
    """Base exception for SNS notification errors."""
    pass


class MessageValidationError(SNSNotificationError):
    """Raised when message payload fails validation."""
    pass


def validate_message(payload: Dict[str, Any]) -> None:
    """
    Validate message payload against contract specification.

    Args:
        payload: Message payload dictionary

    Raises:
        MessageValidationError: If validation fails

    Contract: contracts/sns_notification.yaml
    """
    # Check required keys
    missing_keys = set(REQUIRED_KEYS) - set(payload.keys())
    if missing_keys:
        raise MessageValidationError(f"Missing required keys: {missing_keys}")

    # Validate env
    if payload["env"] not in ALLOWED_ENV:
        raise MessageValidationError(
            f"Invalid env: {payload['env']}. Allowed: {ALLOWED_ENV}"
        )

    # Validate overall
    if payload["overall"] not in ALLOWED_OVERALL:
        raise MessageValidationError(
            f"Invalid overall: {payload['overall']}. Allowed: {ALLOWED_OVERALL}"
        )

    # Validate source
    if payload["source"] not in ALLOWED_SOURCE:
        raise MessageValidationError(
            f"Invalid source: {payload['source']}. Allowed: {ALLOWED_SOURCE}"
        )

    # Validate reason length
    if len(payload["reason"]) > 500:
        raise MessageValidationError("reason exceeds 500 characters")

    # Validate URL format (basic check)
    if not payload["url"].startswith(("http://", "https://")):
        raise MessageValidationError(f"Invalid URL format: {payload['url']}")

    # Validate severity if present
    if "severity" in payload and payload["severity"] not in ALLOWED_SEVERITY:
        raise MessageValidationError(
            f"Invalid severity: {payload['severity']}. Allowed: {ALLOWED_SEVERITY}"
        )


def build_message_payload(
    env: str,
    overall: str,
    source: str,
    reason: str,
    url: str,
    *,
    severity: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build standardized message payload conforming to contract.

    Args:
        env: Environment (dev, stg, prod)
        overall: Overall state (OK, WARN, FAIL)
        source: Monitoring source
        reason: Human-readable alert reason
        url: Deep link to dashboard/runbook
        severity: Optional severity level
        metadata: Optional additional context

    Returns:
        Message payload dictionary

    Contract: contracts/sns_notification.yaml
    """
    payload = {
        "env": env,
        "overall": overall,
        "source": source,
        "reason": reason,
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if severity:
        payload["severity"] = severity

    if metadata:
        payload["metadata"] = metadata

    return payload


def send_notification(
    topic_arn: str,
    payload: Dict[str, Any],
    *,
    subject: Optional[str] = None,
    validate: bool = True,
) -> Dict[str, Any]:
    """
    Send notification to SNS topic with contract validation.

    Args:
        topic_arn: SNS topic ARN
        payload: Message payload (must conform to contract)
        subject: Optional email subject (max 100 chars)
        validate: Whether to validate payload (default: True)

    Returns:
        SNS publish response

    Raises:
        MessageValidationError: If payload validation fails
        SNSNotificationError: If SNS publish fails

    Examples:
        >>> payload = build_message_payload(
        ...     env="prod",
        ...     overall="WARN",
        ...     source="metrics_monitor",
        ...     reason="BCR has been in WARN state for 15 minutes",
        ...     url="https://console.aws.amazon.com/cloudwatch/",
        ...     severity="WARN"
        ... )
        >>> response = send_notification(
        ...     topic_arn="arn:aws:sns:us-east-1:123456789012:thf-alerts-prod",
        ...     payload=payload,
        ...     subject="[WARN] BCR Alert - Production"
        ... )
    """
    # Validate payload
    if validate:
        validate_message(payload)
        logger.info("Message payload validation passed")

    # Build SNS message
    message_body = json.dumps(payload, ensure_ascii=False, indent=2)

    # Build SNS message attributes for filtering
    message_attributes = {
        "Environment": {
            "DataType": "String",
            "StringValue": payload["env"],
        },
        "Source": {
            "DataType": "String",
            "StringValue": payload["source"],
        },
        "ContractVersion": {
            "DataType": "String",
            "StringValue": MESSAGE_CONTRACT_VERSION,
        },
    }

    # Add severity attribute if present
    if "severity" in payload:
        message_attributes["Severity"] = {
            "DataType": "String",
            "StringValue": payload["severity"],
        }

    # Default subject if not provided
    if subject is None:
        subject = f"[{payload['overall']}] {payload['source']} - {payload['env']}"

    # Truncate subject to 100 chars (SNS limit)
    subject = subject[:100]

    # Publish to SNS
    try:
        sns_client = boto3.client("sns")
        response = sns_client.publish(
            TopicArn=topic_arn,
            Message=message_body,
            Subject=subject,
            MessageAttributes=message_attributes,
        )

        logger.info(
            f"SNS notification sent successfully. MessageId: {response['MessageId']}"
        )

        return response

    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        error_msg = exc.response.get("Error", {}).get("Message", str(exc))

        logger.error(
            f"Failed to send SNS notification. Code: {error_code}, Message: {error_msg}"
        )

        raise SNSNotificationError(
            f"SNS publish failed: {error_code} - {error_msg}"
        ) from exc


def send_test_notification(
    topic_arn: str,
    env: str = "dev",
) -> Dict[str, Any]:
    """
    Send a test notification for delivery verification.

    Args:
        topic_arn: SNS topic ARN
        env: Environment (default: dev)

    Returns:
        SNS publish response
    """
    payload = build_message_payload(
        env=env,
        overall="OK",
        source="metrics_monitor",
        reason=f"Test notification - Delivery verification for {env} environment",
        url="https://github.com/anthropics/thf-motion-scan",
        severity="INFO",
        metadata={
            "test": True,
            "purpose": "Delivery verification",
            "contract_version": MESSAGE_CONTRACT_VERSION,
        },
    )

    subject = f"[TEST] Delivery Verification - {env}"

    return send_notification(topic_arn=topic_arn, payload=payload, subject=subject)

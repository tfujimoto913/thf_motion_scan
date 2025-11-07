#!/usr/bin/env python3
"""
SNS Delivery Test Script

Purpose: Send test notifications to verify SNS topic delivery
Usage:
    python tools/test_sns_delivery.py --env dev
    python tools/test_sns_delivery.py --env prod --topic-arn arn:aws:sns:us-east-1:123456789012:thf-alerts-prod

Decision Log: ADR-040 (UI Monitoring 2-Tier Alert System)
Contract: contracts/sns_notification.yaml (v1.0.0)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from monitoring.sns_notifier import (
    build_message_payload,
    send_notification,
    send_test_notification,
    MessageValidationError,
    SNSNotificationError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def get_topic_arn(env: str, region: str = "us-east-1", account_id: str = None) -> str:
    """
    Build SNS topic ARN from environment.

    Args:
        env: Environment (dev, stg, prod)
        region: AWS region
        account_id: AWS account ID (if None, must provide explicit ARN)

    Returns:
        SNS topic ARN
    """
    if account_id:
        return f"arn:aws:sns:{region}:{account_id}:thf-alerts-{env}"

    # Attempt to get account ID from AWS CLI
    try:
        import boto3
        sts = boto3.client("sts")
        account_id = sts.get_caller_identity()["Account"]
        return f"arn:aws:sns:{region}:{account_id}:thf-alerts-{env}"
    except Exception as exc:
        logger.error(f"Failed to get AWS account ID: {exc}")
        raise ValueError(
            "Please provide --topic-arn explicitly or configure AWS credentials"
        )


def send_test_message(
    topic_arn: str,
    env: str,
    test_type: str = "simple"
) -> None:
    """
    Send test message and display results.

    Args:
        topic_arn: SNS topic ARN
        env: Environment
        test_type: Type of test (simple, warn, fail)
    """
    logger.info(f"Sending {test_type} test message to {topic_arn}")

    try:
        if test_type == "simple":
            # Simple delivery test
            response = send_test_notification(topic_arn=topic_arn, env=env)

        elif test_type == "warn":
            # WARN alert simulation
            payload = build_message_payload(
                env=env,
                overall="WARN",
                source="metrics_monitor",
                reason="Test: BCR in WARN state for 15 minutes (simulated)",
                url="https://console.aws.amazon.com/cloudwatch/",
                severity="WARN",
                metadata={
                    "test": True,
                    "metric_name": "BCR",
                    "current_value": 0.48,
                    "warn_threshold": 0.5,
                },
            )
            response = send_notification(
                topic_arn=topic_arn,
                payload=payload,
                subject=f"[TEST-WARN] BCR Alert - {env}"
            )

        elif test_type == "fail":
            # FAIL alert simulation
            payload = build_message_payload(
                env=env,
                overall="FAIL",
                source="billing_monitor",
                reason="Test: Billing threshold exceeded (simulated)",
                url="https://notion.so/runbooks/billing-emergency-stop",
                severity="CRITICAL",
                metadata={
                    "test": True,
                    "current_cost_usd": 5.5,
                    "fail_threshold_usd": 5.0,
                },
            )
            response = send_notification(
                topic_arn=topic_arn,
                payload=payload,
                subject=f"[TEST-FAIL] Billing Alert - {env}"
            )

        else:
            raise ValueError(f"Unknown test type: {test_type}")

        # Display success
        print("\n✅ Message sent successfully!")
        print(f"   MessageId: {response['MessageId']}")
        print(f"   Topic ARN: {topic_arn}")
        print(f"   Test Type: {test_type}")
        print("\n📧 Check your email (or configured endpoint) for delivery confirmation.")
        print("   It may take 1-2 minutes for the message to arrive.")

    except MessageValidationError as exc:
        logger.error(f"Message validation failed: {exc}")
        print(f"\n❌ Message validation error: {exc}")
        sys.exit(1)

    except SNSNotificationError as exc:
        logger.error(f"SNS notification failed: {exc}")
        print(f"\n❌ SNS delivery error: {exc}")
        print("\nTroubleshooting:")
        print("  - Verify SNS topic exists: aws sns list-topics")
        print("  - Verify subscription exists: aws sns list-subscriptions")
        print("  - Check IAM permissions for sns:Publish")
        sys.exit(1)

    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        print(f"\n❌ Unexpected error: {exc}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Send test notifications to SNS topic for delivery verification"
    )

    parser.add_argument(
        "--env",
        choices=["dev", "stg", "prod"],
        default="dev",
        help="Environment (default: dev)"
    )

    parser.add_argument(
        "--topic-arn",
        help="SNS topic ARN (if not provided, will auto-detect from AWS account)"
    )

    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)"
    )

    parser.add_argument(
        "--test-type",
        choices=["simple", "warn", "fail"],
        default="simple",
        help="Test message type (default: simple)"
    )

    args = parser.parse_args()

    # Get topic ARN
    if args.topic_arn:
        topic_arn = args.topic_arn
    else:
        try:
            topic_arn = get_topic_arn(env=args.env, region=args.region)
            logger.info(f"Auto-detected topic ARN: {topic_arn}")
        except ValueError as exc:
            print(f"\n❌ {exc}")
            print("\nPlease provide --topic-arn explicitly:")
            print(f"  python {sys.argv[0]} --env {args.env} --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:thf-alerts-{args.env}")
            sys.exit(1)

    # Send test message
    send_test_message(
        topic_arn=topic_arn,
        env=args.env,
        test_type=args.test_type
    )


if __name__ == "__main__":
    main()

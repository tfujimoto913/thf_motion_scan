#!/usr/bin/env bash
#
# Test Script: Metrics Monitor Lambda Manual Invocation
#
# Purpose: Manually invoke MetricsMonitorFunction for SNS notification testing
# Usage:
#   ./tools/test_metrics_monitor_lambda.sh --env dev
#   ./tools/test_metrics_monitor_lambda.sh --env prod --function-name MetricsMonitorFunction-prod
#
# Decision Log: ADR-040 (UI Monitoring 2-Tier Alert System)
# Contract: contracts/sns_notification.yaml (v1.0.0)

set -euo pipefail

# Default values
ENV="dev"
FUNCTION_NAME=""
REGION="us-east-1"
OUTPUT_FILE="/tmp/metrics_monitor_test_$(date +%Y%m%d_%H%M%S).json"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --env)
      ENV="$2"
      shift 2
      ;;
    --function-name)
      FUNCTION_NAME="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --env ENV                Environment (dev, stg, prod). Default: dev"
      echo "  --function-name NAME     Lambda function name (optional, auto-detected)"
      echo "  --region REGION          AWS region. Default: us-east-1"
      echo "  --output FILE            Output file path. Default: /tmp/metrics_monitor_test_YYYYMMDD_HHMMSS.json"
      echo "  --help                   Show this help message"
      echo ""
      echo "Examples:"
      echo "  $0 --env dev"
      echo "  $0 --env prod --function-name MetricsMonitorFunction-prod"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Auto-detect function name if not provided
if [ -z "$FUNCTION_NAME" ]; then
  echo "🔍 Auto-detecting Lambda function name for environment: $ENV"
  STACK_NAME="thf-motion-scan-${ENV}"

  # Try to get function name from CloudFormation stack outputs
  FUNCTION_NAME=$(aws cloudformation describe-stacks \
    --region "$REGION" \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='MetricsMonitorFunctionName'].OutputValue" \
    --output text 2>/dev/null || echo "")

  if [ -z "$FUNCTION_NAME" ]; then
    # Fallback: try common naming pattern
    FUNCTION_NAME="MetricsMonitorFunction-${ENV}"
    echo "⚠️  Could not auto-detect from CloudFormation, using fallback: $FUNCTION_NAME"
  else
    echo "✅ Detected function: $FUNCTION_NAME"
  fi
fi

# Verify function exists
echo ""
echo "📋 Verifying Lambda function exists..."
if ! aws lambda get-function \
  --region "$REGION" \
  --function-name "$FUNCTION_NAME" \
  --query 'Configuration.[FunctionName,Runtime,LastModified]' \
  --output table >/dev/null 2>&1; then
  echo "❌ Lambda function '$FUNCTION_NAME' not found in region '$REGION'"
  echo ""
  echo "Available functions:"
  aws lambda list-functions \
    --region "$REGION" \
    --query 'Functions[?contains(FunctionName, `Metrics`)].FunctionName' \
    --output table
  exit 1
fi

echo "✅ Function exists"

# Invoke Lambda
echo ""
echo "🚀 Invoking Lambda function..."
echo "   Function: $FUNCTION_NAME"
echo "   Region: $REGION"
echo "   Environment: $ENV"
echo "   Output: $OUTPUT_FILE"
echo ""

aws lambda invoke \
  --region "$REGION" \
  --function-name "$FUNCTION_NAME" \
  --cli-binary-format raw-in-base64-out \
  --log-type Tail \
  --query 'LogResult' \
  --output text \
  "$OUTPUT_FILE" | base64 --decode

echo ""
echo "📄 Lambda Response:"
cat "$OUTPUT_FILE" | jq '.'

echo ""
echo "✅ Invocation complete!"
echo ""
echo "📧 Next Steps:"
echo "   1. Check your email/SNS endpoint for notifications"
echo "   2. Verify CloudWatch Logs:"
echo "      aws logs tail /aws/lambda/$FUNCTION_NAME --region $REGION --since 5m"
echo "   3. Check SNS delivery metrics:"
echo "      aws cloudwatch get-metric-statistics \\"
echo "        --namespace AWS/SNS \\"
echo "        --metric-name NumberOfNotificationsDelivered \\"
echo "        --dimensions Name=TopicName,Value=thf-alerts-$ENV \\"
echo "        --start-time \$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \\"
echo "        --end-time \$(date -u +%Y-%m-%dT%H:%M:%S) \\"
echo "        --period 300 --statistics Sum \\"
echo "        --region $REGION"
echo ""
echo "   4. View DynamoDB state table:"
echo "      aws dynamodb scan --table-name metrics-monitoring-state-$ENV --region $REGION"

#!/bin/bash
# Pre-commit hook for validating thresholds.json
#
# Purpose: Prevent invalid thresholds.json from being committed
# Responsibility: Run validation before commit
# Created: 2025-11-02
# Decision Log: ADR-028
#
# Installation:
#   cp scripts/pre-commit-thresholds.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit

# CRITICAL: Exit on first error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Checking thresholds.json..."

# Check if thresholds.json is staged
if git diff --cached --name-only | grep -q "config/thresholds.json"; then
    echo "📝 thresholds.json changes detected"

    # Run validation
    python3 scripts/validate-thresholds.py config/thresholds.json

    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ thresholds.json validation failed. Commit aborted.${NC}"
        echo ""
        echo "To fix:"
        echo "  1. Review validation errors above"
        echo "  2. Edit config/thresholds.json"
        echo "  3. Run: python3 scripts/validate-thresholds.py config/thresholds.json"
        echo "  4. Try commit again"
        exit 1
    fi

    # Check for MAJOR changes (optional warning)
    if git rev-parse --verify HEAD >/dev/null 2>&1; then
        # Not initial commit, compare with HEAD
        git show HEAD:config/thresholds.json > /tmp/old-thresholds.json 2>/dev/null || true

        if [ -f /tmp/old-thresholds.json ]; then
            python3 scripts/diff-thresholds.py /tmp/old-thresholds.json config/thresholds.json > /tmp/diff-output.txt 2>&1 || true

            if grep -q "MAJOR changes" /tmp/diff-output.txt; then
                echo -e "${YELLOW}⚠️  WARNING: MAJOR changes detected (breaking compatibility)${NC}"
                echo "Diff summary:"
                cat /tmp/diff-output.txt
                echo ""
                echo -e "${YELLOW}Are you sure you want to commit? (y/n)${NC}"
                read -r response
                if [ "$response" != "y" ]; then
                    echo "Commit aborted by user"
                    exit 1
                fi
            fi

            rm -f /tmp/old-thresholds.json /tmp/diff-output.txt
        fi
    fi

    echo -e "${GREEN}✅ thresholds.json validation passed${NC}"
else
    echo "✅ No thresholds.json changes"
fi

exit 0

#!/bin/bash

# Environment-aware start script
# Detects environment and delegates to appropriate start script

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect environment (default: development)
ENVIRONMENT="${ENVIRONMENT:-dev}"

echo "🔍 Detected environment: $ENVIRONMENT"

case "$ENVIRONMENT" in
    "dev"|"development")
        echo "🔄 Delegating to development start script..."
        exec "${SCRIPT_DIR}/start-dev.sh"
        ;;
    "prod"|"production")
        echo "🔄 Delegating to production start script..."
        exec "${SCRIPT_DIR}/start-prod.sh"
        ;;
    *)
        echo "⚠️  Unknown environment '$ENVIRONMENT', defaulting to development..."
        exec "${SCRIPT_DIR}/start-dev.sh"
        ;;
esac


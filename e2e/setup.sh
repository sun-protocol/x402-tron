#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check .env
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "⚠️  No .env file found. Copy .env.example to .env and configure."
  exit 1
fi

# Validate required variables
source "$SCRIPT_DIR/.env"
MISSING_VARS=()
[ -z "$TRON_PRIVATE_KEY" ] && MISSING_VARS+=("TRON_PRIVATE_KEY")
[ -z "$MERCHANT_CONTRACT_ADDRESS" ] && MISSING_VARS+=("MERCHANT_CONTRACT_ADDRESS")

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
  echo "⚠️  Missing required variables: ${MISSING_VARS[*]}"
  exit 1
fi

echo "✅ Setup complete"

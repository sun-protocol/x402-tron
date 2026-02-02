#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TYPESCRIPT_DIR="$REPO_ROOT/typescript"

echo "🚀 Starting x402 TypeScript Client Demo"
echo ""

# Check if .env exists
if [ ! -f "$REPO_ROOT/.env" ]; then
  echo "❌ Error: .env file not found at $REPO_ROOT/.env"
  echo ""
  echo "Please create .env file with:"
  echo "  TRON_PRIVATE_KEY=your_private_key_here"
  echo ""
  exit 1
fi

# Check if TRON_PRIVATE_KEY is set
if ! grep -q "TRON_PRIVATE_KEY" "$REPO_ROOT/.env"; then
  echo "❌ Error: TRON_PRIVATE_KEY not found in .env file"
  echo ""
  echo "Please add to .env file:"
  echo "  TRON_PRIVATE_KEY=your_private_key_here"
  echo ""
  exit 1
fi

# Install workspace dependencies and build TypeScript packages
echo "📦 Installing workspace dependencies and building packages..."
echo ""
cd "$TYPESCRIPT_DIR"
pnpm install
pnpm build
echo ""
echo "✅ TypeScript packages built and dependencies linked"
echo ""

echo "▶️  Running client..."
echo ""

cd "$SCRIPT_DIR"
pnpm start

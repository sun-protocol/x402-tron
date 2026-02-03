#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

URL="${1:-${IMAGE_FINDER_URL:-http://localhost:8000/protected}}"

if command -v x402-tools >/dev/null 2>&1; then
  x402-tools fetch-image "${URL}" </dev/null
  exit 0
fi

REPO_ROOT="${X402_REPO_ROOT:-/Users/wdk/tron/tvm-x402}"
CLI_PATH="${REPO_ROOT}/typescript/packages/tools/dist/cli.js"

if [ ! -f "${CLI_PATH}" ]; then
  echo "x402-tools not found in PATH and CLI not found at ${CLI_PATH}" >&2
  echo "Set X402_REPO_ROOT to your tvm-x402 checkout and run pnpm -r build" >&2
  exit 1
fi

node "${CLI_PATH}" fetch-image "${URL}" </dev/null

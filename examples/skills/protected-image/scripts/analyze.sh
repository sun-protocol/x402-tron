#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

npx -y "github:sun-protocol/tvm-x402#feat/for_skill" x402-tools fetch-image \
  </dev/null

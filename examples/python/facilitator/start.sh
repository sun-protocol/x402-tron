#!/bin/bash

# Start x402 Facilitator
# This script starts the facilitator service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Starting x402 Facilitator"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "../../../.env" ]; then
    echo "Error: .env file not found in project root"
    echo "Please create .env file with required variables:"
    echo "  FACILITATOR_PRIVATE_KEY=<your_private_key>"
    echo "  TRON_NETWORK=<network>"
    echo ""
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "../../../.venv" ]; then
    echo "Error: Virtual environment not found"
    echo "Please run: python -m venv .venv"
    echo ""
    exit 1
fi

# Activate virtual environment
source "../../../.venv/bin/activate"

# Install dependencies if needed
if ! python -c "import x402" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -e ../../../python/x402
    pip install -r requirements.txt
fi

echo "Starting facilitator on http://localhost:8001"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the facilitator
python main.py

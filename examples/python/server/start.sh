#!/bin/bash

# Start x402 Server
# This script starts the protected resource server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Starting x402 Server"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "../../../.env" ]; then
    echo "Error: .env file not found in project root"
    echo "Please create .env file with required variables:"
    echo "  MERCHANT_CONTRACT_ADDRESS=<your_contract_address>"
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

echo "Starting server on http://localhost:8000"
echo "Protected endpoint: http://localhost:8000/protected"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the server
python main.py

#!/bin/bash

set -e

if [ ! -d "node_modules" ]; then
  echo "📦 Installing dependencies..."
  npm install
fi

echo "🔨 Building @open-aibank/x402-tron..."
cd ../../../typescript/packages/x402
npm run build
cd -

npm run dev

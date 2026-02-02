import fs from 'fs';
import path from 'path';

import TronWebPkg from 'tronweb';

import { X402Client } from '@tvm-x402/core';
import { X402FetchClient } from '@tvm-x402/http-fetch';
import { UptoTronClientMechanism } from '@tvm-x402/mechanism-tron';
import { TronClientSigner } from '@tvm-x402/signer-tron';

const TronWebCtor = (
  (TronWebPkg as unknown as { TronWeb?: unknown }).TronWeb ??
  (TronWebPkg as unknown as { default?: unknown }).default ??
  (TronWebPkg as unknown)
) as unknown;

if (typeof TronWebCtor !== 'function') {
  throw new Error('Unable to load TronWeb constructor from tronweb package');
}

function loadPrivateKey(): string {
  const envKey = process.env.TRON_PRIVATE_KEY || process.env.X402_PRIVATE_KEY;
  if (envKey) return envKey;

  const configLocations = [
    path.join(process.cwd(), 'x402-config.json'),
    path.join(process.env.HOME || '', '.x402-config.json'),
    path.join(process.env.PWD || process.cwd(), 'x402-config.json'),
  ];

  for (const p of configLocations) {
    try {
      if (!p || !fs.existsSync(p)) continue;
      const data = JSON.parse(fs.readFileSync(p, 'utf8')) as Record<string, unknown>;
      const key = data.tron_private_key || data.TRON_PRIVATE_KEY || data.private_key;
      if (typeof key === 'string' && key.length > 0) return key;
    } catch {
      continue;
    }
  }

  throw new Error(
    'Missing TRON private key. Set TRON_PRIVATE_KEY (preferred) or X402_PRIVATE_KEY, or create ~/.x402-config.json'
  );
}

function parseTronNetwork(): 'mainnet' | 'nile' | 'shasta' {
  const network = process.env.TRON_NETWORK || 'tron:nile';
  const tronNetworkName = network.split(':').at(-1) || 'nile';

  if (tronNetworkName === 'mainnet' || tronNetworkName === 'nile' || tronNetworkName === 'shasta') {
    return tronNetworkName;
  }

  throw new Error(`Unsupported TRON_NETWORK=${network}. Expected tron:mainnet|tron:nile|tron:shasta`);
}

function tronFullHost(network: 'mainnet' | 'nile' | 'shasta'): string {
  switch (network) {
    case 'mainnet':
      return 'https://api.trongrid.io';
    case 'shasta':
      return 'https://api.shasta.trongrid.io';
    case 'nile':
      return 'https://nile.trongrid.io';
  }
}

export async function fetchImage(): Promise<void> {
  const resolvedUrl = 'http://localhost:8000/protected';

  const privateKey = loadPrivateKey();
  const tronNetwork = parseTronNetwork();

  const tronWeb = new (TronWebCtor as new (...args: any[]) => any)({
    fullHost: tronFullHost(tronNetwork),
  });

  const signer = TronClientSigner.withPrivateKey(tronWeb as unknown as never, privateKey, tronNetwork);
  const x402Client = new X402Client().register('tron:*', new UptoTronClientMechanism(signer));
  const client = new X402FetchClient(x402Client);

  const response = await client.get(resolvedUrl);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${response.statusText}`);
  }

  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('image/')) {
    throw new Error(`Expected image response, got content-type=${contentType} status=${response.status}`);
  }

  const outDir = process.env.IMAGE_FINDER_OUTPUT_DIR || process.cwd();
  fs.mkdirSync(outDir, { recursive: true });

  const ext = contentType.includes('png') ? '.png' : '.bin';
  const outPath = path.join(outDir, `protected_image${ext}`);

  const bytes = Buffer.from(await response.arrayBuffer());
  fs.writeFileSync(outPath, bytes);

  const result = {
    url: resolvedUrl,
    content_type: contentType,
    file_path: outPath,
    bytes: bytes.length,
    base64: bytes.toString('base64'),
  };

  process.stdout.write(JSON.stringify(result));
}

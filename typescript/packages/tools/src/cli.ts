#!/usr/bin/env node

import { fetchImage } from './commands/fetchImage.js';

function usage(): void {
  process.stderr.write('Usage: x402-tools fetch-image\n');
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const cmd = args[0];

  if (!cmd || cmd === '-h' || cmd === '--help') {
    usage();
    process.exitCode = cmd ? 0 : 1;
    return;
  }

  if (cmd === 'fetch-image') {
    await fetchImage();
    return;
  }

  process.stderr.write(`Unknown command: ${cmd}\n`);
  usage();
  process.exitCode = 1;
}

main().catch(err => {
  process.stderr.write(String(err instanceof Error ? err.message : err));
  process.stderr.write('\n');
  process.exitCode = 1;
});

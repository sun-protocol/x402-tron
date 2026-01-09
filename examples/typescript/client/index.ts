import { config } from "dotenv";
import { X402Client } from "@x402/core";
import { UptoTronClientMechanism } from "@x402/mechanism-tron";
import { TronClientSigner } from "@x402/signer-tron";
import { X402FetchClient } from "@x402/http-fetch";

config();

const TRON_PRIVATE_KEY = process.env.TRON_PRIVATE_KEY || "";
const RESOURCE_URL = process.env.RESOURCE_SERVER_URL + (process.env.ENDPOINT_PATH || "/protected");

async function main() {
  // 1. 设置客户端
  const signer = TronClientSigner.fromPrivateKey(TRON_PRIVATE_KEY);
  const x402Client = new X402Client().register("tron:*", new UptoTronClientMechanism(signer));
  const client = new X402FetchClient(x402Client);

  console.log(`Requesting protected resource: ${RESOURCE_URL}`);

  try {
    // 2. 发起请求（自动处理 402 支付）
    const response = await client.get(RESOURCE_URL);
    const data = await response.json();

    console.log("Status:", response.status);
    console.log("Response:", data);
  } catch (error) {
    console.error("Error:", error);
  }
}

main();

import os
import logging
import time
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from x402.server import X402Server
from x402.fastapi import x402_protected
from x402.facilitator import FacilitatorClient
from x402.config import NetworkConfig

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set specific loggers to DEBUG for detailed output
logging.getLogger("x402").setLevel(logging.DEBUG)
logging.getLogger("x402.server").setLevel(logging.DEBUG)
logging.getLogger("x402.fastapi").setLevel(logging.DEBUG)
logging.getLogger("x402.utils").setLevel(logging.DEBUG)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI(title="X402 Server", description="Protected resource server")

# Add CORS middleware to allow cross-origin requests from client-web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Configuration
MERCHANT_CONTRACT_ADDRESS = os.getenv("MERCHANT_CONTRACT_ADDRESS", "")
# Hardcoded server configuration
FACILITATOR_URL = "http://localhost:8001"
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# Path to protected image
PROTECTED_IMAGE_PATH = Path(__file__).parent / "protected.png"

if not MERCHANT_CONTRACT_ADDRESS:
    raise ValueError("MERCHANT_CONTRACT_ADDRESS environment variable is required")

# Initialize server (TRON mechanisms auto-registered by default)
server = X402Server()
# Add facilitator
facilitator = FacilitatorClient(base_url=FACILITATOR_URL)
server.add_facilitator(facilitator)

print(f"Server Configuration:")
print(f"  Network: {NetworkConfig.TRON_NILE}")
print(f"  Merchant Contract: {MERCHANT_CONTRACT_ADDRESS}")
print(f"  Facilitator URL: {FACILITATOR_URL}")

@app.get("/")
async def root():
    """Service info"""
    return {
        "service": "X402 Protected Resource Server",
        "status": "running",
        "merchant_contract": MERCHANT_CONTRACT_ADDRESS,
        "facilitator": FACILITATOR_URL,
    }

@app.get("/protected")
@x402_protected(
    server=server,
    price="1 USDT",  # 1 USDT = 1000000 (6 decimals)
    network=NetworkConfig.TRON_NILE,
    pay_to=MERCHANT_CONTRACT_ADDRESS,
)
async def protected_endpoint(request: Request):
    """Serve the protected image directly"""
    if not PROTECTED_IMAGE_PATH.exists():
        return {"error": "Protected image not found"}
    return FileResponse(PROTECTED_IMAGE_PATH, media_type="image/png")

@app.get("/protected-delivery")
@x402_protected(
    server=server,
    price="1 USDT",
    network=NetworkConfig.TRON_NILE,
    pay_to=MERCHANT_CONTRACT_ADDRESS,
    delivery_mode=True,  # Enable delivery mode
)
async def protected_delivery_endpoint(request: Request):
    """Serve protected content with delivery mode (PAYMENT_AND_DELIVERY)"""
    if not PROTECTED_IMAGE_PATH.exists():
        return {"error": "Protected image not found"}
    return FileResponse(PROTECTED_IMAGE_PATH, media_type="image/png")

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "=" * 80)
    print("Starting X402 Protected Resource Server")
    print("=" * 80)
    print(f"Host: {SERVER_HOST}")
    print(f"Port: {SERVER_PORT}")
    print(f"Endpoints:")
    print(f"  /protected          - Payment only (1 USDT)")
    print(f"  /protected-with-fee - Payment with fee (2 USDT + 1 USDT fee)")
    print(f"  /protected-delivery - Payment and delivery mode")
    print("=" * 80 + "\n")
    
    uvicorn.run(
        app, 
        host=SERVER_HOST, 
        port=SERVER_PORT,
        log_level="info",
        access_log=True,
    )

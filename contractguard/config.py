"""ContractGuard configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# MiMo LLM (OpenAI-compatible)
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "http://localhost:20128/v1")
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "sk-local")
MIMO_MODEL = os.getenv("MIMO_MODEL", "xmtp/mimo-v2.5-pro")

# Block explorer API keys (free tier OK)
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "")
BASESCAN_API_KEY = os.getenv("BASESCAN_API_KEY", "")
ARBISCAN_API_KEY = os.getenv("ARBISCAN_API_KEY", "")
POLYGONSCAN_API_KEY = os.getenv("POLYGONSCAN_API_KEY", "")

# Chain → explorer config
EXPLORERS = {
    "ethereum": {
        "name": "Ethereum",
        "chain_id": 1,
        "api_url": "https://api.etherscan.io/api",
        "explorer_url": "https://etherscan.io",
        "api_key": ETHERSCAN_API_KEY,
    },
    "bsc": {
        "name": "BNB Smart Chain",
        "chain_id": 56,
        "api_url": "https://api.bscscan.com/api",
        "explorer_url": "https://bscscan.com",
        "api_key": BSCSCAN_API_KEY,
    },
    "base": {
        "name": "Base",
        "chain_id": 8453,
        "api_url": "https://api.basescan.org/api",
        "explorer_url": "https://basescan.org",
        "api_key": BASESCAN_API_KEY,
    },
    "arbitrum": {
        "name": "Arbitrum One",
        "chain_id": 42161,
        "api_url": "https://api.arbiscan.io/api",
        "explorer_url": "https://arbiscan.io",
        "api_key": ARBISCAN_API_KEY,
    },
    "polygon": {
        "name": "Polygon",
        "chain_id": 137,
        "api_url": "https://api.polygonscan.com/api",
        "explorer_url": "https://polygonscan.com",
        "api_key": POLYGONSCAN_API_KEY,
    },
}

# Public RPC endpoints (no key needed) for bytecode fetching
RPC_ENDPOINTS = {
    "ethereum": os.getenv("ETH_RPC", "https://ethereum-rpc.publicnode.com"),
    "bsc": os.getenv("BSC_RPC", "https://bsc-rpc.publicnode.com"),
    "base": os.getenv("BASE_RPC", "https://base-rpc.publicnode.com"),
    "arbitrum": os.getenv("ARB_RPC", "https://arbitrum-one-rpc.publicnode.com"),
    "polygon": os.getenv("POLYGON_RPC", "https://polygon-bor-rpc.publicnode.com"),
}

# GoPlus (free) — supplementary risk data
GOPLUS_API_URL = "https://api.gopluslabs.io/api/v1"

# Cache
CACHE_DIR = Path(os.getenv("CACHE_DIR", "./cache"))
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour

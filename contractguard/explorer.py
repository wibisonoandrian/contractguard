"""Block explorer client using Etherscan V2 unified API."""
import httpx
from typing import Dict, Optional
from .config import EXPLORERS, GOPLUS_API_URL, ETHERSCAN_API_KEY


# Etherscan V2 unified endpoint — one key works for all supported chains
ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api"


class ExplorerError(Exception):
    pass


async def get_contract_source(chain: str, address: str) -> Dict:
    """Fetch verified source code via Etherscan V2 unified API."""
    cfg = EXPLORERS.get(chain.lower())
    if not cfg:
        raise ExplorerError(f"Unsupported chain: {chain}")

    if not ETHERSCAN_API_KEY:
        raise ExplorerError(
            "ETHERSCAN_API_KEY not set. Get a free key at https://etherscan.io/apis "
            "and add to .env (one key works for all chains via Etherscan V2)."
        )

    params = {
        "chainid": cfg["chain_id"],
        "module": "contract",
        "action": "getsourcecode",
        "address": address,
        "apikey": ETHERSCAN_API_KEY,
    }

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(ETHERSCAN_V2_URL, params=params)
        r.raise_for_status()
        data = r.json()

    if data.get("status") != "1":
        raise ExplorerError(f"API error: {data.get('result') or data.get('message', 'unknown')}")

    result = data["result"][0] if data.get("result") else {}
    return {
        "verified": bool(result.get("SourceCode")),
        "source_code": result.get("SourceCode", ""),
        "abi": result.get("ABI", ""),
        "contract_name": result.get("ContractName", ""),
        "compiler_version": result.get("CompilerVersion", ""),
        "optimization": result.get("OptimizationUsed", ""),
        "runs": result.get("Runs", ""),
        "constructor_args": result.get("ConstructorArguments", ""),
        "evm_version": result.get("EVMVersion", ""),
        "library": result.get("Library", ""),
        "license": result.get("LicenseType", ""),
        "proxy": result.get("Proxy") == "1",
        "implementation": result.get("Implementation", ""),
    }


async def get_contract_creator(chain: str, address: str) -> Optional[Dict]:
    """Get contract creator + creation tx via V2."""
    cfg = EXPLORERS.get(chain.lower())
    if not cfg or not ETHERSCAN_API_KEY:
        return None

    params = {
        "chainid": cfg["chain_id"],
        "module": "contract",
        "action": "getcontractcreation",
        "contractaddresses": address,
        "apikey": ETHERSCAN_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(ETHERSCAN_V2_URL, params=params)
            data = r.json()
        if data.get("status") == "1" and data.get("result"):
            res = data["result"][0]
            return {"creator": res.get("contractCreator"), "tx_hash": res.get("txHash")}
    except Exception:
        pass
    return None


async def get_goplus_risk(chain_id: int, address: str) -> Optional[Dict]:
    """Get GoPlus risk data (free, no key needed)."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                f"{GOPLUS_API_URL}/token_security/{chain_id}",
                params={"contract_addresses": address.lower()},
            )
            data = r.json()
        if data.get("code") == 1:
            return data.get("result", {}).get(address.lower(), {})
    except Exception:
        pass
    return None

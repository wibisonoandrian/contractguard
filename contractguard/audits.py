"""Audit & reputation lookup — DefiLlama, CertiK, Coingecko."""
import asyncio
import httpx
from typing import Dict, Optional, List


async def get_defillama_protocol(address: str) -> Optional[Dict]:
    """Search DefiLlama for protocol matching this contract."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            # DefiLlama protocols list
            r = await c.get("https://api.llama.fi/protocols")
            data = r.json()
        addr_lower = address.lower()
        for proto in data:
            # Check if contract appears in any of the protocol's metadata
            for field in ("address", "rugged", "audits", "audit_links"):
                v = proto.get(field)
                if isinstance(v, str) and addr_lower in v.lower():
                    return {
                        "name": proto.get("name"),
                        "category": proto.get("category"),
                        "tvl": proto.get("tvl"),
                        "audits": proto.get("audits"),
                        "audit_links": proto.get("audit_links"),
                        "audit_note": proto.get("audit_note"),
                        "url": f"https://defillama.com/protocol/{proto.get('slug', '')}",
                    }
    except Exception:
        pass
    return None


async def get_coingecko_token(chain_id: int, address: str) -> Optional[Dict]:
    """Get CoinGecko data — confirms token is publicly known/listed."""
    chain_map = {1: "ethereum", 56: "binance-smart-chain", 8453: "base",
                 42161: "arbitrum-one", 137: "polygon-pos"}
    platform = chain_map.get(chain_id)
    if not platform:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                f"https://api.coingecko.com/api/v3/coins/{platform}/contract/{address.lower()}",
                params={"localization": "false", "tickers": "false",
                        "market_data": "false", "community_data": "false",
                        "developer_data": "false"},
            )
            if r.status_code != 200:
                return None
            data = r.json()
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "symbol": data.get("symbol"),
            "rank": data.get("market_cap_rank"),
            "categories": data.get("categories", [])[:5],
            "homepage": (data.get("links", {}) or {}).get("homepage", [None])[0],
            "url": f"https://www.coingecko.com/en/coins/{data.get('id')}",
        }
    except Exception:
        return None


async def get_audits(address: str, chain_id: int) -> Dict:
    """Aggregate audit + reputation data."""
    defillama, cg = await asyncio.gather(
        get_defillama_protocol(address),
        get_coingecko_token(chain_id, address),
        return_exceptions=False,
    )
    return {
        "defillama": defillama,
        "coingecko": cg,
    }

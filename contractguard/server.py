"""FastAPI server for ContractGuard."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import time

from .llm import MiMoClient
from .explorer import get_contract_source, get_contract_creator, get_goplus_risk, ExplorerError
from .analyzer import analyze_source
from .config import EXPLORERS, CACHE_TTL_SECONDS

app = FastAPI(
    title="ContractGuard AI",
    description="Smart contract risk analyzer powered by MiMo V2.5 Pro",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory cache (replace with redis for prod)
_cache: Dict[str, tuple[float, dict]] = {}


def _cache_get(key: str) -> Optional[dict]:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL_SECONDS:
            return data
        del _cache[key]
    return None


def _cache_set(key: str, data: dict):
    _cache[key] = (time.time(), data)


class AnalysisResponse(BaseModel):
    chain: str
    address: str
    contract_name: Optional[str]
    verified: bool
    is_proxy: bool
    risk_score: int
    verdict: str
    summary: str
    issues: List[Dict]
    owner_privileges: List[str]
    is_renounced: Optional[bool]
    is_honeypot_likely: bool
    creator: Optional[Dict] = None
    explorer_url: str
    cached: bool = False


@app.get("/")
def root():
    return {
        "service": "contractguard-ai",
        "status": "ok",
        "supported_chains": list(EXPLORERS.keys()),
    }


@app.get("/analyze/{chain}/{address}", response_model=AnalysisResponse)
async def analyze(chain: str, address: str, refresh: bool = False):
    """Analyze a smart contract for security risks."""
    chain = chain.lower()
    address = address.lower()

    if chain not in EXPLORERS:
        raise HTTPException(400, f"Unsupported chain. Use one of: {list(EXPLORERS.keys())}")

    if not (address.startswith("0x") and len(address) == 42):
        raise HTTPException(400, "Invalid EVM address format")

    cache_key = f"{chain}:{address}"
    if not refresh:
        cached = _cache_get(cache_key)
        if cached:
            return {**cached, "cached": True}

    try:
        # Fetch source + creator + goplus in parallel
        import asyncio
        cfg = EXPLORERS[chain]
        source_task = get_contract_source(chain, address)
        creator_task = get_contract_creator(chain, address)
        goplus_task = get_goplus_risk(cfg["chain_id"], address)
        source_data, creator_data, goplus_data = await asyncio.gather(
            source_task, creator_task, goplus_task,
            return_exceptions=True,
        )

        if isinstance(source_data, Exception):
            raise HTTPException(502, f"Explorer error: {source_data}")
        if isinstance(creator_data, Exception):
            creator_data = None
        if isinstance(goplus_data, Exception):
            goplus_data = None

        # Run MiMo analysis
        llm = MiMoClient()
        try:
            analysis = await analyze_source(llm, source_data, goplus_data)
        finally:
            await llm.close()

        result = {
            "chain": chain,
            "address": address,
            "contract_name": source_data.get("contract_name") or None,
            "verified": source_data.get("verified", False),
            "is_proxy": source_data.get("proxy", False),
            "risk_score": analysis.get("risk_score", 50),
            "verdict": analysis.get("verdict", "CAUTION"),
            "summary": analysis.get("summary", ""),
            "issues": analysis.get("issues", []),
            "owner_privileges": analysis.get("owner_privileges", []),
            "is_renounced": analysis.get("is_renounced"),
            "is_honeypot_likely": analysis.get("is_honeypot_likely", False),
            "creator": creator_data,
            "explorer_url": f"{cfg['explorer_url']}/address/{address}",
            "cached": False,
        }

        _cache_set(cache_key, {**result, "cached": False})
        return result

    except ExplorerError as e:
        raise HTTPException(404, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {e}")

"""Bytecode analysis fallback — opcode pattern scanning when source unavailable."""
import re
import httpx
from typing import Dict, List, Optional


# Known dangerous opcodes/patterns in EVM bytecode
DANGEROUS_PATTERNS = {
    "selfdestruct": (rb"\xff", "SELFDESTRUCT opcode found — contract can be destroyed"),
    "delegatecall": (rb"\xf4", "DELEGATECALL found — contract can execute code from another address"),
    "callcode": (rb"\xf2", "CALLCODE (deprecated) found — legacy code execution from another address"),
}


# Function selectors of common dangerous functions
DANGEROUS_SELECTORS = {
    "0x40c10f19": "mint(address,uint256)",
    "0x42966c68": "burn(uint256)",
    "0x6a627842": "mint(address)",  
    "0x9dc29fac": "burn(address,uint256)",
    "0xa9059cbb": "transfer(address,uint256)",
    "0x23b872dd": "transferFrom(address,address,uint256)",
    "0x8456cb59": "pause()",
    "0x3f4ba83a": "unpause()",
    "0xf2fde38b": "transferOwnership(address)",
    "0x715018a6": "renounceOwnership()",
    "0xf9f92be4": "_blacklist(address)",
    "0x537df3b6": "addToBlacklist(address)",
    "0x537df3b7": "removeFromBlacklist(address)",
    "0x4f1ef286": "upgradeToAndCall(address,bytes)",
    "0x3659cfe6": "upgradeTo(address)",
    "0x5c975abb": "paused()",
    "0xfca3b5aa": "setMinter(address)",
}


# ERC-20 standard selectors (presence = likely a token)
ERC20_SELECTORS = {
    "0x70a08231": "balanceOf",
    "0xa9059cbb": "transfer",
    "0x23b872dd": "transferFrom",
    "0xdd62ed3e": "allowance",
    "0x095ea7b3": "approve",
    "0x18160ddd": "totalSupply",
    "0x06fdde03": "name",
    "0x95d89b41": "symbol",
    "0x313ce567": "decimals",
}


async def fetch_bytecode(rpc_url: str, address: str) -> Optional[str]:
    """Fetch deployed bytecode via eth_getCode."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(rpc_url, json={
                "jsonrpc": "2.0", "method": "eth_getCode",
                "params": [address, "latest"], "id": 1,
            })
            data = r.json()
        return data.get("result", "0x")
    except Exception:
        return None


def extract_function_selectors(bytecode_hex: str) -> List[str]:
    """Extract potential function selectors from bytecode (PUSH4 patterns)."""
    if not bytecode_hex or len(bytecode_hex) < 10:
        return []
    bc = bytecode_hex[2:] if bytecode_hex.startswith("0x") else bytecode_hex
    selectors = set()
    # PUSH4 = 0x63 + 4 bytes selector
    pattern = re.compile(r"63([0-9a-f]{8})", re.IGNORECASE)
    for m in pattern.finditer(bc):
        selectors.add("0x" + m.group(1).lower())
    return sorted(selectors)


def analyze_bytecode(bytecode_hex: str) -> Dict:
    """Static analysis of EVM bytecode."""
    if not bytecode_hex or bytecode_hex == "0x":
        return {
            "is_contract": False,
            "size_bytes": 0,
            "warnings": ["Address has no deployed bytecode (EOA or self-destructed)"],
            "selectors": [],
            "dangerous_functions": [],
            "is_likely_token": False,
        }

    bc = bytecode_hex[2:] if bytecode_hex.startswith("0x") else bytecode_hex
    size = len(bc) // 2

    warnings = []
    raw_bytes = bytes.fromhex(bc)

    # Pattern checks
    for name, (pattern, msg) in DANGEROUS_PATTERNS.items():
        if pattern in raw_bytes:
            warnings.append(f"{name.upper()}: {msg}")

    # Selector extraction
    selectors = extract_function_selectors(bytecode_hex)
    dangerous_found = []
    for sel in selectors:
        if sel in DANGEROUS_SELECTORS:
            dangerous_found.append({
                "selector": sel,
                "function": DANGEROUS_SELECTORS[sel],
            })

    # Token detection
    token_selectors_found = sum(1 for s in selectors if s in ERC20_SELECTORS)
    is_likely_token = token_selectors_found >= 6

    # Proxy detection (EIP-1967 storage slot or DELEGATECALL pattern)
    is_proxy = b"\xf4" in raw_bytes  # DELEGATECALL opcode

    return {
        "is_contract": True,
        "size_bytes": size,
        "size_kb": round(size / 1024, 2),
        "n_selectors": len(selectors),
        "selectors": selectors[:50],
        "dangerous_functions": dangerous_found,
        "is_likely_token": is_likely_token,
        "is_proxy_likely": is_proxy,
        "warnings": warnings,
    }

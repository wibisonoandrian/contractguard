"""LLM-based contract risk analyzer using MiMo."""
from typing import Dict, List
from .llm import MiMoClient


ANALYZER_SYSTEM = """You are a senior smart contract auditor specializing in EVM security.
You analyze Solidity source code (when available) AND on-chain risk data (GoPlus) for risks: rug pulls, honeypots, hidden mints, owner privileges, fee manipulation, transfer restrictions, and other malicious patterns.

For each contract, identify ALL issues found with severity and concrete evidence (function names where possible, GoPlus flags otherwise).

If source code is NOT available, work with GoPlus flags only and note the unverified status as a major issue.

Severity levels:
- CRITICAL: Direct rug/honeypot/total loss capability (mint without limit, blacklist transfers, drainOwner functions, hidden upgradeable proxy, is_honeypot=1)
- HIGH: Significant centralization risk (changeable fees up to 100%, pause transfers, transfer_pausable, hidden_owner, cannot_sell_all)
- MEDIUM: Concerning but not immediately exploitable (high but capped fees, owner privileges with limits, is_anti_whale, is_mintable)
- LOW: Minor concerns (no events on critical state changes, owner_change_balance, magic numbers)
- INFO: Observations not necessarily issues (custom token type, slippage_modifiable)

Return JSON:
{
  "risk_score": 0-100,
  "verdict": "SAFE" | "CAUTION" | "DANGEROUS",
  "summary": "1-2 sentence overall assessment in plain English",
  "issues": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
      "category": "honeypot|rug|centralization|fees|proxy|access_control|transparency|other",
      "title": "Short title",
      "description": "What's wrong and why it matters (plain English, 1-2 sentences)",
      "evidence": "Specific function/code reference or GoPlus flag"
    }
  ],
  "owner_privileges": ["list of capabilities owner has"],
  "is_renounced": true|false|null,
  "is_proxy": true|false,
  "is_honeypot_likely": true|false
}

Be specific, evidence-based, no speculation. If unsure mark severity LOW. Output ONLY valid JSON, no markdown."""


async def analyze_source(
    llm: MiMoClient,
    contract_data: Dict,
    goplus_data: Dict = None,
    audit_data: Dict = None,
) -> Dict:
    """Analyze verified contract source code."""
    if not contract_data.get("verified") or not contract_data.get("source_code"):
        # No source code — analyze using GoPlus + bytecode data
        if not goplus_data and not contract_data.get("bytecode"):
            return {
                "risk_score": 70,
                "verdict": "CAUTION",
                "summary": "Contract is NOT verified and no on-chain risk data available.",
                "issues": [{
                    "severity": "HIGH",
                    "category": "transparency",
                    "title": "Unverified contract",
                    "description": "Source code is not publicly available and no GoPlus risk data found. Cannot assess behavior.",
                    "evidence": "No source code, no GoPlus data",
                }],
                "owner_privileges": [],
                "is_renounced": None,
                "is_proxy": False,
                "is_honeypot_likely": True,
            }
        # Have GoPlus or bytecode data — use GoPlus + bytecode analysis
        bytecode_text = ""
        bc = contract_data.get("bytecode")
        if bc:
            bytecode_text = f"""

Bytecode analysis (since source unavailable):
- Contract size: {bc.get('size_kb', 0)} KB ({bc.get('size_bytes', 0)} bytes)
- Function selectors found: {bc.get('n_selectors', 0)}
- Likely a token: {bc.get('is_likely_token')}
- Proxy detected (DELEGATECALL): {bc.get('is_proxy_likely')}
- Bytecode warnings: {bc.get('warnings', [])}
- Dangerous functions detected: {[d['function'] for d in bc.get('dangerous_functions', [])][:10]}"""

        prompt = f"""Contract: {contract_data.get('contract_name', 'unknown')}
Source code: NOT AVAILABLE (unverified)

GoPlus on-chain risk data:
{_format_goplus(goplus_data) if goplus_data else 'No GoPlus data.'}{bytecode_text}

Analyze using available data. Note unverified status as a critical transparency issue.
Return JSON only."""
        return await llm.chat_json(prompt, system=ANALYZER_SYSTEM, temperature=0.2, max_tokens=3072)

    source = contract_data["source_code"]
    # Truncate very long source to fit context
    if len(source) > 60000:
        source = source[:60000] + "\n\n[... truncated for length ...]"

    goplus_text = ""
    if goplus_data:
        flags = []
        for k, v in goplus_data.items():
            if v in ("1", 1, True) and k in (
                "is_honeypot", "cannot_sell_all", "cannot_buy",
                "transfer_pausable", "is_blacklisted", "is_anti_whale",
                "is_mintable", "is_proxy", "is_open_source",
                "external_call", "hidden_owner", "selfdestruct",
            ):
                flags.append(k)
        if flags:
            goplus_text = f"\n\nGoPlus flags raised: {', '.join(flags)}"

    audit_text = ""
    if audit_data:
        cg = audit_data.get("coingecko")
        dl = audit_data.get("defillama")
        if cg:
            audit_text += f"\n\nCoinGecko verified: {cg.get('name')} ({cg.get('symbol', '').upper()}) rank #{cg.get('rank')}"
            if cg.get("categories"):
                audit_text += f", categories: {', '.join(cg['categories'])}"
        if dl:
            audit_text += f"\n\nDefiLlama protocol: {dl.get('name')} ({dl.get('category')}) TVL ${dl.get('tvl', 0):,.0f}"
            if dl.get("audits"):
                audit_text += f", audits: {dl['audits']}"
            if dl.get("audit_links"):
                audit_text += f", audit_links: {dl['audit_links']}"

    prompt = f"""Contract: {contract_data.get('contract_name', 'unknown')}
Compiler: {contract_data.get('compiler_version', 'unknown')}
Proxy: {contract_data.get('proxy', False)}
{goplus_text}{audit_text}

Source Code:
```solidity
{source}
```

Analyze for security risks. If audit/CoinGecko data shows this is a well-known established project, factor that in (lower risk for legitimate centralization features in regulated stables/major protocols). Return JSON only."""

    return await llm.chat_json(prompt, system=ANALYZER_SYSTEM, temperature=0.2, max_tokens=4096)


def _format_goplus(goplus_data: dict) -> str:
    """Format GoPlus data as readable text for LLM."""
    if not goplus_data:
        return "No data."
    important = [
        "token_name", "token_symbol", "total_supply",
        "is_honeypot", "is_open_source", "is_proxy", "is_mintable",
        "cannot_buy", "cannot_sell_all", "transfer_pausable",
        "is_blacklisted", "is_anti_whale", "anti_whale_modifiable",
        "buy_tax", "sell_tax", "slippage_modifiable",
        "owner_address", "owner_balance", "owner_change_balance",
        "hidden_owner", "external_call", "selfdestruct",
        "is_in_dex", "lp_holder_count", "holder_count",
        "creator_address", "creator_balance", "creator_percent",
    ]
    lines = []
    for k in important:
        if k in goplus_data:
            v = goplus_data[k]
            lines.append(f"  {k}: {v}")
    return "\n".join(lines) if lines else "No relevant flags."

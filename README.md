# ContractGuard AI

Smart contract risk analyzer — paste contract address, get plain-English security verdict via MiMo V2.5 Pro reasoning.

## Why

Existing tools (GoPlus, Honeypot.is) are rule-based — gampang di-bypass attacker yang tau cara hide red flags dari regex. ContractGuard pakai LLM yang baca semantic Solidity, deteksi novel attack patterns yang gak masuk static rule.

## Features

- **Source code analysis** — verified contracts via Etherscan V2 unified API
- **Bytecode fallback** — function selector + opcode pattern scan when source unavailable
- **GoPlus integration** — supplementary on-chain risk flags
- **Audit cross-reference** — DefiLlama protocols, CoinGecko verified tokens
- **MiMo reasoning layer** — semantic LLM analysis, not just regex
- **Risk score 0-100** + verdict (SAFE / CAUTION / DANGEROUS)
- **Issue list** with severity (CRITICAL/HIGH/MEDIUM/LOW/INFO), category, evidence
- **Owner privilege detection** — list what deployer can do
- **Multi-interface** — CLI, REST API, Telegram bot, Chrome extension

## Architecture

```
User → POST /analyze/{chain}/{address}
   ↓
[1] GoPlus API           →  on-chain risk flags (always)
[2] Etherscan V2         →  source code (if API key)
[3] RPC eth_getCode      →  bytecode (fallback when unverified)
[4] DefiLlama/CoinGecko  →  audit + reputation cross-ref
   ↓
[5] MiMo Analyzer        →  semantic LLM risk analysis
   ↓
Output: verdict + risk_score + issues[] + summary
```

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# (optional) get free Etherscan V2 key — works for all 5 chains

# CLI
python -m contractguard.cli analyze ethereum 0xdAC17F958D2ee523a2206206994597C13D831ec7

# REST API server
python -m contractguard.cli serve --port 8766
curl http://localhost:8766/analyze/ethereum/0xdAC...

# Telegram bot (set TELEGRAM_BOT_TOKEN in .env first)
python -m contractguard.cli bot

# Chrome extension
# Load extension/ folder via chrome://extensions in dev mode
```

## Supported Chains

- Ethereum (chain id 1)
- BNB Smart Chain (56)
- Base (8453)
- Arbitrum One (42161)
- Polygon (137)

## Risk Detection

**Source-based (verified contracts):**
- Hidden mints, unlimited mint privileges
- Owner-controlled blacklist/transfer pause
- Modifiable fees up to 100%
- Hidden upgradeable proxy
- Drain functions, selfdestruct
- Centralization risks

**Bytecode-based (unverified contracts):**
- Function selector match against dangerous functions
- SELFDESTRUCT / DELEGATECALL opcode detection
- ERC-20 standard selector detection (token classification)
- Contract size + proxy heuristics

**On-chain flags (GoPlus):**
- is_honeypot, cannot_buy, cannot_sell_all
- transfer_pausable, hidden_owner, blacklist
- buy_tax, sell_tax, slippage_modifiable

## Sample Output

```
🚨 DANGEROUS  Risk Score: 85/100  Contract: ScamToken

Summary: Honeypot detected — owner can blacklist any address and pause
all transfers. Source code is also unverified.

Issues (4):
🚨 CRITICAL  honeypot       Cannot Sell All
🔴 HIGH      centralization Transfer Pausable
🔴 HIGH      transparency   Source Not Verified
🟡 MEDIUM    fees           Modifiable Slippage

Owner can:
  • Blacklist any address
  • Pause all token transfers
  • Modify slippage parameters
```

## Configuration

`.env`:
- `MIMO_BASE_URL` — default `http://localhost:20128/v1`
- `MIMO_MODEL` — default `xmtp/mimo-v2.5-pro`
- `ETHERSCAN_API_KEY` — V2 unified key for all 5 chains
- `TELEGRAM_BOT_TOKEN` — for bot mode
- `ETH_RPC`, `BSC_RPC`, etc — override default public RPCs

## License

MIT

## Contact

- **GitHub:** [@wibisonoandrian](https://github.com/wibisonoandrian)
- **Email:** wibisono10969@gmail.com
- **Issues:** [github.com/wibisonoandrian/contractguard/issues](https://github.com/wibisonoandrian/contractguard/issues)

Maintained by Andri Wibisono. Open to collaboration, security audits, and integration partnerships.

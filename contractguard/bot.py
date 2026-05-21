"""ContractGuard Telegram bot. Paste address, get instant verdict."""
import asyncio
import os
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from .llm import MiMoClient
from .explorer import get_contract_source, get_contract_creator, get_goplus_risk, ExplorerError
from .analyzer import analyze_source
from .config import EXPLORERS

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s")
log = logging.getLogger("contractguard.bot")

ADDR_RE = re.compile(r"0x[a-fA-F0-9]{40}")
CHAIN_ALIASES = {
    "eth": "ethereum", "ethereum": "ethereum",
    "bsc": "bsc", "bnb": "bsc",
    "base": "base",
    "arb": "arbitrum", "arbitrum": "arbitrum",
    "polygon": "polygon", "matic": "polygon", "poly": "polygon",
}

VERDICT_EMOJI = {"SAFE": "✅", "CAUTION": "⚠️", "DANGEROUS": "🚨"}
SEVERITY_EMOJI = {"CRITICAL": "🚨", "HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵", "INFO": "⚪"}


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡️ *ContractGuard AI*\n\n"
        "Smart contract risk analyzer powered by MiMo V2.5 Pro\n\n"
        "*Cara pakai:*\n"
        "Paste contract address — bot otomatis tanya chainnya\n\n"
        "Atau langsung:\n"
        "`/check eth 0x...`\n"
        "`/check bsc 0x...`\n"
        "`/check base 0x...`\n\n"
        "Chain tersedia: eth, bsc, base, arbitrum, polygon",
        parse_mode="Markdown",
    )


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Format: `/check <chain> <address>`", parse_mode="Markdown")
        return

    chain = CHAIN_ALIASES.get(args[0].lower())
    if not chain:
        await update.message.reply_text(f"Unknown chain. Use: {', '.join(set(CHAIN_ALIASES.values()))}")
        return

    addr_match = ADDR_RE.search(args[1])
    if not addr_match:
        await update.message.reply_text("Invalid address. Must be 0x followed by 40 hex chars.")
        return

    await run_analysis(update, chain, addr_match.group(0).lower())


async def msg_address(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Detect address in any text — ask which chain."""
    text = update.message.text or ""
    match = ADDR_RE.search(text)
    if not match:
        return
    address = match.group(0).lower()

    keyboard = [[
        InlineKeyboardButton("ETH", callback_data=f"chain|ethereum|{address}"),
        InlineKeyboardButton("BSC", callback_data=f"chain|bsc|{address}"),
        InlineKeyboardButton("Base", callback_data=f"chain|base|{address}"),
    ], [
        InlineKeyboardButton("Arbitrum", callback_data=f"chain|arbitrum|{address}"),
        InlineKeyboardButton("Polygon", callback_data=f"chain|polygon|{address}"),
    ]]
    await update.message.reply_text(
        f"📍 Address: `{address}`\n\nPilih chain:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def cb_chain(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    if len(parts) != 3:
        return
    _, chain, address = parts
    await q.edit_message_text(f"🔍 Analyzing `{address}` on {chain}...", parse_mode="Markdown")
    await run_analysis_callback(q, chain, address)


def format_verdict_message(chain: str, address: str, result: dict) -> str:
    verdict = result.get("verdict", "UNKNOWN")
    score = result.get("risk_score", "?")
    emoji = VERDICT_EMOJI.get(verdict, "❓")
    name = result.get("contract_name") or "Unknown"

    lines = [
        f"{emoji} *{verdict}* — Risk Score: *{score}/100*",
        f"📋 Contract: `{name}`",
        f"🔗 [{chain[:3].upper()}: {address[:10]}...{address[-6:]}]({EXPLORERS[chain]['explorer_url']}/address/{address})",
        "",
        f"*Summary:* {result.get('summary', '')}",
    ]

    issues = result.get("issues", [])
    if issues:
        lines.append("")
        lines.append(f"*Issues ({len(issues)}):*")
        for i in issues[:6]:
            sev = i.get("severity", "INFO")
            ico = SEVERITY_EMOJI.get(sev, "⚪")
            title = i.get("title", "")
            desc = i.get("description", "")[:120]
            lines.append(f"{ico} *{sev}* — {title}")
            lines.append(f"   _{desc}_")
        if len(issues) > 6:
            lines.append(f"... +{len(issues) - 6} more")

    privs = result.get("owner_privileges", [])
    if privs:
        lines.append("")
        lines.append("*Owner can:*")
        for p in privs[:5]:
            lines.append(f"  • {p}")

    flags = []
    if result.get("verified"): flags.append("✓ verified")
    else: flags.append("✗ unverified")
    if result.get("is_proxy"): flags.append("🔄 proxy")
    if result.get("is_renounced"): flags.append("🔓 renounced")
    if result.get("is_honeypot_likely"): flags.append("🍯 honeypot risk")
    lines.append("")
    lines.append("`" + "  ".join(flags) + "`")

    return "\n".join(lines)[:4000]  # Telegram limit


async def _do_analysis(chain: str, address: str) -> dict:
    cfg = EXPLORERS[chain]
    goplus_data = await get_goplus_risk(cfg["chain_id"], address)
    source_data = None
    try:
        source_data = await get_contract_source(chain, address)
    except ExplorerError:
        source_data = {
            "verified": False, "source_code": "",
            "contract_name": (goplus_data or {}).get("token_name", "Unknown"),
            "proxy": (goplus_data or {}).get("is_proxy") == "1",
        }

    llm = MiMoClient()
    try:
        analysis = await analyze_source(llm, source_data, goplus_data)
    finally:
        await llm.close()

    return {
        "contract_name": source_data.get("contract_name"),
        "verified": source_data.get("verified", False),
        "is_proxy": source_data.get("proxy", False),
        **analysis,
    }


async def run_analysis(update: Update, chain: str, address: str):
    msg = await update.message.reply_text(f"🔍 Analyzing `{address}` on {chain}...", parse_mode="Markdown")
    try:
        result = await _do_analysis(chain, address)
        text = format_verdict_message(chain, address, result)
        await msg.edit_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        log.exception("analysis failed")
        await msg.edit_text(f"❌ Error: {e}")


async def run_analysis_callback(query, chain: str, address: str):
    try:
        result = await _do_analysis(chain, address)
        text = format_verdict_message(chain, address, result)
        await query.edit_message_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        log.exception("analysis failed")
        await query.edit_message_text(f"❌ Error: {e}")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN not set in .env")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CallbackQueryHandler(cb_chain, pattern="^chain\\|"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_address))

    log.info("ContractGuard Telegram bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

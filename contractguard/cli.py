"""ContractGuard CLI."""
import asyncio
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import httpx
import json

from .llm import MiMoClient
from .explorer import get_contract_source, get_contract_creator, get_goplus_risk, ExplorerError
from .analyzer import analyze_source
from .config import EXPLORERS

app = typer.Typer(help="ContractGuard AI — smart contract risk analyzer")
console = Console()


VERDICT_COLORS = {
    "SAFE": "green",
    "CAUTION": "yellow",
    "DANGEROUS": "red bold",
}

SEVERITY_COLORS = {
    "CRITICAL": "red bold",
    "HIGH": "red",
    "MEDIUM": "yellow",
    "LOW": "cyan",
    "INFO": "dim",
}


def render_analysis(result: dict):
    """Pretty-print analysis result."""
    verdict = result.get("verdict", "UNKNOWN")
    color = VERDICT_COLORS.get(verdict, "white")
    score = result.get("risk_score", "?")
    name = result.get("contract_name") or "Unknown"

    header = f"[{color}]{verdict}[/{color}]  Risk Score: [bold]{score}/100[/bold]  Contract: [cyan]{name}[/cyan]"
    console.print(Panel(header, title="ContractGuard Analysis", expand=False))
    console.print(f"\n[bold]Summary:[/bold] {result.get('summary', '')}\n")

    # Issues table
    issues = result.get("issues", [])
    if issues:
        table = Table(title=f"Issues Found ({len(issues)})", box=box.ROUNDED, show_lines=True)
        table.add_column("Sev", style="bold", width=10)
        table.add_column("Category", width=14)
        table.add_column("Title", width=30)
        table.add_column("Description")
        for issue in issues:
            sev = issue.get("severity", "INFO")
            sev_color = SEVERITY_COLORS.get(sev, "white")
            table.add_row(
                f"[{sev_color}]{sev}[/{sev_color}]",
                issue.get("category", ""),
                issue.get("title", ""),
                issue.get("description", "")[:200],
            )
        console.print(table)
    else:
        console.print("[green]No issues found.[/green]")

    # Owner privileges
    privs = result.get("owner_privileges", [])
    if privs:
        console.print(f"\n[bold yellow]Owner privileges:[/bold yellow]")
        for p in privs:
            console.print(f"  • {p}")

    # Misc flags
    console.print(f"\n[dim]Verified: {result.get('verified')} | Proxy: {result.get('is_proxy')} | Renounced: {result.get('is_renounced')} | Honeypot risk: {result.get('is_honeypot_likely')}[/dim]")
    console.print(f"[dim]Explorer: {result.get('explorer_url', '')}[/dim]")


async def _analyze(chain: str, address: str, json_out: bool):
    cfg = EXPLORERS[chain]
    
    if not json_out:
        console.print(f"[yellow]Fetching contract data for {cfg['name']}...[/yellow]")
    
    # GoPlus first (always works, no key needed)
    goplus_data = await get_goplus_risk(cfg["chain_id"], address)

    # Audits + CoinGecko reputation
    from .audits import get_audits
    audit_data = await get_audits(address, cfg["chain_id"])

    # Try Etherscan V2 — may fail if no API key
    source_data = None
    explorer_error = None
    try:
        source_data = await get_contract_source(chain, address)
    except ExplorerError as e:
        explorer_error = str(e)
        if not json_out:
            console.print(f"[yellow]⚠ Source code unavailable: {e}[/yellow]")
            console.print(f"[yellow]Falling back to GoPlus + bytecode analysis.[/yellow]")

    creator_data = None
    if source_data:
        creator_data = await get_contract_creator(chain, address)

    # Bytecode analysis when source unavailable
    bytecode_data = None
    if not source_data:
        from .bytecode import fetch_bytecode, analyze_bytecode
        from .config import RPC_ENDPOINTS
        rpc_url = RPC_ENDPOINTS.get(chain)
        if rpc_url:
            bc = await fetch_bytecode(rpc_url, address)
            if bc:
                bytecode_data = analyze_bytecode(bc)

    if not json_out:
        console.print(f"[yellow]Running MiMo analysis...[/yellow]")

    # If no source, build minimal contract_data for analyzer
    if not source_data:
        source_data = {
            "verified": False,
            "source_code": "",
            "contract_name": (goplus_data or {}).get("token_name", "Unknown"),
            "proxy": (goplus_data or {}).get("is_proxy") == "1" or (bytecode_data or {}).get("is_proxy_likely", False),
            "bytecode": bytecode_data,
        }

    llm = MiMoClient()
    try:
        analysis = await analyze_source(llm, source_data, goplus_data, audit_data)
    finally:
        await llm.close()

    result = {
        "chain": chain,
        "address": address,
        "contract_name": source_data.get("contract_name"),
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
        "audits": audit_data,
        "explorer_url": f"{cfg['explorer_url']}/address/{address}",
    }

    if json_out:
        print(json.dumps(result, indent=2))
    else:
        render_analysis(result)


@app.command()
def analyze(
    chain: str = typer.Argument(..., help=f"Chain: {', '.join(EXPLORERS.keys())}"),
    address: str = typer.Argument(..., help="Contract address (0x...)"),
    json_out: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Analyze a contract for security risks."""
    chain = chain.lower()
    if chain not in EXPLORERS:
        console.print(f"[red]Unsupported chain. Use one of: {list(EXPLORERS.keys())}[/red]")
        raise typer.Exit(1)
    if not (address.startswith("0x") and len(address) == 42):
        console.print("[red]Invalid EVM address format[/red]")
        raise typer.Exit(1)
    asyncio.run(_analyze(chain, address, json_out))


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8766):
    """Start FastAPI server."""
    import uvicorn
    from .server import app as fastapi_app
    uvicorn.run(fastapi_app, host=host, port=port)


@app.command()
def bot():
    """Start Telegram bot (requires TELEGRAM_BOT_TOKEN in .env)."""
    from .bot import main
    main()


if __name__ == "__main__":
    app()

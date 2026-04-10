"""
main.py – CLI version (optional, for terminal use)
Run: python main.py
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from engine import run_analysis

console = Console()


def display(result):
    colors = {"BULLISH": "green", "BEARISH": "red", "NEUTRAL": "yellow"}
    emoji = {"BULLISH": "🟢🐂", "BEARISH": "🔴🐻", "NEUTRAL": "🟡⏸"}
    c = colors.get(result.signal, "white")

    console.print(Panel(
        f"[bold {c}]{emoji.get(result.signal, '')}  {result.signal}  "
        f"(confidence: {result.confidence:.0%})[/bold {c}]",
        title=f"[bold]{result.company_name} ({result.ticker})[/bold]",
        subtitle=f"${result.price:,.2f}  ({result.change_pct:+.2f}%)",
        border_style=c,
    ))
    console.print(f"\n[bold]Summary:[/bold] {result.summary}\n")

    if result.key_factors:
        t = Table(title="Key Factors", show_lines=True)
        t.add_column("#", style="dim", width=3)
        t.add_column("Factor")
        for i, f in enumerate(result.key_factors, 1):
            t.add_row(str(i), f)
        console.print(t)

    sb = result.source_breakdown
    if sb:
        console.print(
            f"\n  [green]Positive: {sb.get('positive_count', 0)}[/green]  "
            f"[red]Negative: {sb.get('negative_count', 0)}[/red]  "
            f"[yellow]Neutral: {sb.get('neutral_count', 0)}[/yellow]"
        )
    console.print(f"\n[dim]Sources analyzed: {result.sources_used}[/dim]\n")


if __name__ == "__main__":
    ticker = input("Enter stock ticker (e.g. AAPL, TSLA, NVDA): ").strip()
    if ticker:
        def log(name, count):
            console.print(f"[dim]  📡 {name}... → {count} items[/dim]")
        result = run_analysis(ticker, progress_callback=log)
        display(result)

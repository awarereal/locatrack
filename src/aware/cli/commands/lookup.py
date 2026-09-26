"""
OSINT lookup commands.

Comprehensive intelligence gathering with premium CLI interface.
"""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich import box

app = typer.Typer(help="OSINT lookup commands")
console = Console()
err_console = Console(stderr=True)

# ASCII Art Banner (Calvin S style)
BANNER = """
[bold cyan]
╦  ╔═╗╔═╗╔═╗╔╦╗╦═╗╔═╗╔═╗╦╔═
║  ║ ║║  ╠═╣ ║ ╠╦╝╠═╣║  ╠╩╗
╩═╝╚═╝╚═╝╩ ╩ ╩ ╩╚═╩ ╩╚═╝╩ ╩[/bold cyan]
[dim]OSINT Intelligence Gathering[/dim]
"""

PHONE_BANNER = """
[bold magenta]
╔═╗╦ ╦╔═╗╔╗╔╔═╗  ╔═╗╔═╗╦╔╗╔╔╦╗
╠═╝╠═╣║ ║║║║║╣   ║ ║╚═╗║║║║ ║
╩  ╩ ╩╚═╝╝╚╝╚═╝  ╚═╝╚═╝╩╝╚╝ ╩ [/bold magenta]
"""


def print_banner():
    """Print the main banner."""
    console.print(BANNER)


@app.command("ip")
def ip_lookup(
    ip_address: str = typer.Argument(..., help="IP address to look up"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Look up geolocation information for an IP address.

    Example:
        locatrack lookup ip 8.8.8.8
    """
    from aware.lookups.ip_info import lookup_ip

    if not json_output:
        print_banner()

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[cyan]Scanning target...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description="", total=None)
        result = asyncio.run(lookup_ip(ip_address))

    if result.error:
        err_console.print(f"[red]✗ Error:[/red] {result.error}")
        raise typer.Exit(1)

    if json_output:
        import json
        console.print(json.dumps(result.model_dump(exclude_none=True), indent=2))
        return

    # Create rich output
    table = Table(
        show_header=False,
        box=box.ROUNDED,
        border_style="cyan",
        padding=(0, 2),
        expand=True,
    )
    table.add_column("Field", style="bold cyan", width=15)
    table.add_column("Value", style="white")

    table.add_row("IP", f"[bold white]{result.ip}[/bold white]")
    table.add_row("Type", result.ip_type or "Unknown")
    table.add_row("─" * 12, "─" * 40)

    table.add_row("Country", f"{result.country} ({result.country_code})" if result.country else "Unknown")
    table.add_row("Region", f"{result.region}" if result.region else "Unknown")
    table.add_row("City", result.city or "Unknown")
    table.add_row("Postal", result.postal or "Unknown")

    if result.latitude and result.longitude:
        table.add_row("Coordinates", f"[green]{result.latitude}, {result.longitude}[/green]")
        maps_url = f"https://www.google.com/maps/@{result.latitude},{result.longitude},12z"
        table.add_row("Maps", f"[link={maps_url}][blue]{maps_url}[/blue][/link]")

    table.add_row("─" * 12, "─" * 40)
    table.add_row("ISP", result.isp or "Unknown")
    table.add_row("Organization", result.org or "Unknown")
    table.add_row("ASN", str(result.asn) if result.asn else "Unknown")

    table.add_row("─" * 12, "─" * 40)
    table.add_row("Timezone", result.timezone_id or "Unknown")
    table.add_row("UTC Offset", result.utc_offset or "Unknown")

    console.print()
    console.print(Panel(
        table,
        title=f"[bold white]TARGET: {ip_address}[/bold white]",
        subtitle="[dim]IP Geolocation[/dim]",
        border_style="cyan",
    ))


@app.command("phone")
def phone_lookup(
    phone_number: str = typer.Argument(..., help="Phone number with country code"),
    deep_scan: bool = typer.Option(True, "--deep/--quick", help="Perform deep OSINT scan"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Comprehensive phone number OSINT.

    Gathers carrier info, generates Google dorks, social media links,
    and checks online presence.

    Example:
        locatrack lookup phone +14155551234
        locatrack lookup phone +6281234567890 --quick
    """
    from aware.lookups.phone import phone_osint

    if not json_output:
        console.print(PHONE_BANNER)

    with Progress(
        SpinnerColumn(style="magenta"),
        TextColumn("[magenta]Running OSINT scan...[/magenta]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description="", total=None)
        result = asyncio.run(phone_osint(phone_number, deep_scan=deep_scan))

    if result.error:
        err_console.print(f"[red]✗ Error:[/red] {result.error}")
        raise typer.Exit(1)

    if json_output:
        import json
        console.print(json.dumps(result.model_dump(exclude_none=True), indent=2))
        return

    # Basic Info Table
    info_table = Table(
        show_header=False,
        box=box.ROUNDED,
        border_style="magenta",
        padding=(0, 2),
    )
    info_table.add_column("Field", style="bold magenta", width=15)
    info_table.add_column("Value", style="white")

    valid_style = "[green]✓ Valid[/green]" if result.valid else "[red]✗ Invalid[/red]"
    info_table.add_row("Status", valid_style)
    info_table.add_row("International", f"[bold]{result.international}[/bold]" if result.international else "—")
    info_table.add_row("E.164", result.e164 or "—")
    info_table.add_row("National", result.national or "—")
    info_table.add_row("─" * 12, "─" * 40)
    info_table.add_row("Country", f"{result.country} ({result.region_code})" if result.country else "—")
    info_table.add_row("Carrier", result.carrier or "Unknown")
    info_table.add_row("Line Type", result.line_type or "Unknown")
    info_table.add_row("Timezone", result.timezone or "—")

    console.print()
    console.print(Panel(
        info_table,
        title=f"[bold white]TARGET: {phone_number}[/bold white]",
        subtitle="[dim]Basic Info[/dim]",
        border_style="magenta",
    ))

    # Google Dorks
    if result.google_dorks:
        console.print()
        console.print("[bold yellow]📡 GOOGLE DORKS[/bold yellow]")
        dork_table = Table(box=box.SIMPLE, padding=(0, 1))
        dork_table.add_column("Name", style="yellow")
        dork_table.add_column("Query", style="dim")

        for dork in result.google_dorks[:6]:  # Show top 6
            dork_table.add_row(dork["name"], dork["query"])

        console.print(dork_table)
        console.print(f"[dim]Run: Click links above or copy dorks to Google[/dim]")

    # Social Links
    if result.social_links:
        console.print()
        console.print("[bold blue]🔗 LOOKUP SERVICES[/bold blue]")

        # Group into rows of 3
        links = result.social_links
        for i in range(0, len(links), 3):
            row = links[i:i+3]
            row_text = "  ".join([f"[blue]{l['platform']}[/blue]" for l in row])
            console.print(f"  {row_text}")

        console.print()
        console.print("[dim]Services: Truecaller, Sync.me, WhitePages, etc.[/dim]")

    # Online Presence
    if result.online_presence:
        console.print()
        console.print("[bold green]📱 ONLINE PRESENCE[/bold green]")

        for p in result.online_presence:
            status = "[green]✓ Found[/green]" if p.get("registered") else "[dim]Not found[/dim]"
            console.print(f"  {p['service']}: {status}")

    # Summary
    console.print()
    console.print(Panel(
        f"[bold]Scan complete.[/bold] {len(result.google_dorks)} dorks • {len(result.social_links)} services • {len(result.online_presence)} presence checks",
        border_style="dim",
    ))


@app.command("user")
def username_lookup(
    username: str = typer.Argument(..., help="Username to search for"),
    timeout: float = typer.Option(5.0, "--timeout", "-t", help="Timeout per site"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Search for a username across social media platforms.

    Example:
        locatrack lookup user johndoe
    """
    from aware.lookups.username import search_username

    if not json_output:
        print_banner()

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn(f"[cyan]Hunting '{username}'...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description="", total=None)
        results = asyncio.run(search_username(username, timeout=timeout))

    if json_output:
        import json
        output = [r.model_dump(exclude_none=True) for r in results]
        console.print(json.dumps(output, indent=2))
        return

    found = [r for r in results if r.found]
    not_found = [r for r in results if not r.found and not r.error]

    console.print()

    if found:
        table = Table(box=box.ROUNDED, border_style="green", padding=(0, 2))
        table.add_column("Platform", style="bold green")
        table.add_column("URL", style="white")

        for r in found:
            table.add_row(r.platform, f"[link={r.url}]{r.url}[/link]")

        console.print(Panel(
            table,
            title=f"[bold green]✓ FOUND ({len(found)})[/bold green]",
            border_style="green",
        ))
    else:
        console.print("[yellow]No accounts found for this username.[/yellow]")

    if not_found:
        console.print(f"\n[dim]Not found on: {', '.join(r.platform for r in not_found[:10])}{'...' if len(not_found) > 10 else ''}[/dim]")

    console.print(f"\n[bold]Summary:[/bold] Found on {len(found)}/{len(results)} platforms")


@app.command("myip")
def my_ip(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Show your public IP address and location.

    Example:
        locatrack lookup myip
    """
    from aware.lookups.ip_info import get_my_ip

    if not json_output:
        print_banner()

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[cyan]Detecting your IP...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description="", total=None)
        my_ip_result = asyncio.run(get_my_ip())

    if my_ip_result.error:
        err_console.print(f"[red]✗ Error:[/red] {my_ip_result.error}")
        raise typer.Exit(1)

    console.print(f"\n[bold green]Your IP:[/bold green] [bold white]{my_ip_result.ip}[/bold white]\n")

    # Get full details
    ip_lookup(my_ip_result.ip, json_output=json_output)

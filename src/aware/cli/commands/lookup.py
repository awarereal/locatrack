"""
OSINT lookup commands with integrated tracking.
"""

import asyncio
import re
import webbrowser
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

app = typer.Typer(help="OSINT lookup commands")
console = Console()
err_console = Console(stderr=True)

BANNER = """
[bold cyan]
╦  ╔═╗╔═╗╔═╗╔╦╗╦═╗╔═╗╔═╗╦╔═
║  ║ ║║  ╠═╣ ║ ╠╦╝╠═╣║  ╠╩╗
╩═╝╚═╝╚═╝╩ ╩ ╩ ╩╚═╩ ╩╚═╝╩ ╩[/bold cyan]
"""

TRACK_BANNER = """
[bold red]
╔╦╗╦═╗╔═╗╔═╗╦╔═  ╔╦╗╔═╗╦═╗╔═╗╔═╗╔╦╗
 ║ ╠╦╝╠═╣║  ╠╩╗   ║ ╠═╣╠╦╝║ ╦║╣  ║
 ╩ ╩╚═╩ ╩╚═╝╩ ╩   ╩ ╩ ╩╩╚═╚═╝╚═╝ ╩ [/bold red]
"""


@app.command("phone")
def phone_lookup(
    phone_number: str = typer.Argument(..., help="Phone number with country code"),
    track: bool = typer.Option(False, "--track", "-t", help="Create tracking link"),
    send: bool = typer.Option(False, "--send", "-s", help="Open WhatsApp to send link"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Phone OSINT + optional GPS tracking.

    To get their ACTUAL LOCATION, use --track to create a link.
    Send the link, when they click it, you get their GPS.

    Example:
        locatrack lookup phone +14155551234
        locatrack lookup phone +14155551234 --track
        locatrack lookup phone +14155551234 --track --send
    """
    from aware.lookups.phone import phone_osint

    console.print(TRACK_BANNER if track else BANNER)

    tracking_url = None
    tracking_code = None

    # Create tracking link if requested
    if track:
        console.print("[yellow]Creating tracking link...[/yellow]")
        try:
            tracking_url, tracking_code = _create_tracking_link(phone_number)
            if not tracking_url:
                err_console.print("[red]Failed to create tracking link. Is server running?[/red]")
                err_console.print("[dim]Start with: locatrack server start[/dim]")
        except Exception as e:
            err_console.print(f"[red]Tracking link error: {e}[/red]")

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[cyan]Scanning...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        result = asyncio.run(phone_osint(
            phone_number,
            deep_scan=True,
            tracking_url=tracking_url,
            tracking_code=tracking_code,
        ))

    if result.error:
        err_console.print(f"[red]✗ {result.error}[/red]")
        raise typer.Exit(1)

    if json_output:
        import json
        console.print(json.dumps(result.model_dump(exclude_none=True), indent=2))
        return

    # Basic Info
    console.print()
    info = Table(show_header=False, box=box.ROUNDED, border_style="cyan", padding=(0, 2))
    info.add_column("", style="bold cyan", width=14)
    info.add_column("", style="white")

    info.add_row("Number", f"[bold]{result.international}[/bold]")
    info.add_row("Status", "[green]✓ Valid[/green]" if result.valid else "[red]✗ Invalid[/red]")
    info.add_row("Country", f"{result.country} ({result.region_code})" if result.country else "Unknown")
    info.add_row("Carrier", result.carrier or "Unknown")
    info.add_row("Type", result.line_type or "Unknown")
    info.add_row("Timezone", result.timezone or "—")

    console.print(Panel(info, title=f"[bold]TARGET[/bold]", border_style="cyan"))

    # Platform detection
    if result.whatsapp is not None or result.telegram is not None:
        console.print()
        console.print("[bold]📱 Messaging Platforms[/bold]")
        if result.whatsapp:
            console.print("  [green]✓[/green] WhatsApp")
        if result.telegram:
            console.print("  [green]✓[/green] Telegram")

    # Tracking link section
    if tracking_url:
        console.print()
        console.print(Panel(
            f"[bold green]{tracking_url}[/bold green]",
            title="[bold red]🎯 TRACKING LINK[/bold red]",
            subtitle="[dim]Send this link to get their GPS location[/dim]",
            border_style="red",
        ))

        console.print()
        console.print("[bold]Send via:[/bold]")

        clean = re.sub(r"[^\d]", "", result.e164 or phone_number)

        # WhatsApp
        wa_url = f"https://wa.me/{clean}?text={tracking_url}"
        console.print(f"  📱 WhatsApp: [link={wa_url}][blue]Click to send[/blue][/link]")

        # SMS
        sms_url = f"sms:{result.e164}?body={tracking_url}"
        console.print(f"  💬 SMS: [link={sms_url}][blue]Click to send[/blue][/link]")

        # Telegram
        console.print(f"  ✈️  Telegram: [blue]https://t.me/+{clean}[/blue]")

        console.print()
        console.print("[yellow]When they click the link and allow location, you'll see:[/yellow]")
        console.print("  • Their GPS coordinates (latitude/longitude)")
        console.print("  • Their IP address")
        console.print("  • Approximate city from IP")
        console.print()
        console.print(f"[dim]Check results: locatrack link show {tracking_code}[/dim]")

        if send:
            console.print()
            console.print("[yellow]Opening WhatsApp...[/yellow]")
            webbrowser.open(wa_url)

    # Lookup services
    if result.lookup_services and not track:
        console.print()
        console.print("[bold]🔍 Lookup Services[/bold]")
        for svc in result.lookup_services[:4]:
            console.print(f"  [blue]{svc['name']}[/blue]: {svc['url']}")

    # Google dorks
    if result.google_dorks and not track:
        console.print()
        console.print("[bold]📡 Google Dorks[/bold]")
        for dork in result.google_dorks[:3]:
            console.print(f"  {dork['name']}: [dim]{dork['url']}[/dim]")

    if not track:
        console.print()
        console.print("[dim]To track their location, run with --track flag[/dim]")


def _create_tracking_link(label: str) -> tuple[Optional[str], Optional[str]]:
    """Create a tracking link via the API."""
    import httpx
    from aware.config import settings

    # Check if server is running
    try:
        resp = httpx.get(f"http://127.0.0.1:{settings.port}/health", timeout=2.0)
        if resp.status_code != 200:
            return None, None
    except:
        # Try to start server
        from aware.cli.app import start_background_server
        if not start_background_server():
            return None, None

    # Get auth token
    token = _get_token()
    if not token:
        console.print("[yellow]Not logged in. Register/login first:[/yellow]")
        console.print("  locatrack auth register")
        console.print("  locatrack auth login")
        return None, None

    # Create link
    try:
        resp = httpx.post(
            f"http://127.0.0.1:{settings.port}/track",
            headers={"Authorization": f"Bearer {token}"},
            json={"label": label, "expires_hours": 24, "single_use": True},
            timeout=10.0,
        )
        if resp.status_code == 201:
            data = resp.json()
            return data["url"], data["code"]
    except Exception as e:
        err_console.print(f"[red]Error: {e}[/red]")

    return None, None


def _get_token() -> Optional[str]:
    """Get stored auth token."""
    import os
    token_file = os.path.expanduser("~/.locatrack_token")
    if os.path.exists(token_file):
        with open(token_file) as f:
            return f.read().strip()
    return None


@app.command("ip")
def ip_lookup(
    ip_address: str = typer.Argument(..., help="IP address to look up"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    IP geolocation lookup.

    Example:
        locatrack lookup ip 8.8.8.8
    """
    from aware.lookups.ip_info import lookup_ip

    console.print(BANNER)

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[cyan]Scanning...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        result = asyncio.run(lookup_ip(ip_address))

    if result.error:
        err_console.print(f"[red]✗ {result.error}[/red]")
        raise typer.Exit(1)

    if json_output:
        import json
        console.print(json.dumps(result.model_dump(exclude_none=True), indent=2))
        return

    table = Table(show_header=False, box=box.ROUNDED, border_style="cyan", padding=(0, 2))
    table.add_column("", style="bold cyan", width=12)
    table.add_column("", style="white")

    table.add_row("IP", f"[bold]{result.ip}[/bold]")
    table.add_row("Country", f"{result.country} ({result.country_code})" if result.country else "Unknown")
    table.add_row("Region", result.region or "Unknown")
    table.add_row("City", result.city or "Unknown")

    if result.latitude and result.longitude:
        table.add_row("Coords", f"[green]{result.latitude}, {result.longitude}[/green]")
        maps_url = f"https://www.google.com/maps/@{result.latitude},{result.longitude},12z"
        table.add_row("Maps", f"[link={maps_url}][blue]{maps_url}[/blue][/link]")

    table.add_row("─" * 10, "─" * 40)
    table.add_row("ISP", result.isp or "Unknown")
    table.add_row("ASN", str(result.asn) if result.asn else "Unknown")
    table.add_row("Timezone", result.timezone_id or "Unknown")

    console.print()
    console.print(Panel(table, title=f"[bold]TARGET: {ip_address}[/bold]", border_style="cyan"))


@app.command("user")
def username_lookup(
    username: str = typer.Argument(..., help="Username to search"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Search for username across platforms.

    Example:
        locatrack lookup user johndoe
    """
    from aware.lookups.username import search_username

    console.print(BANNER)

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn(f"[cyan]Hunting '{username}'...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        results = asyncio.run(search_username(username, timeout=5.0))

    if json_output:
        import json
        console.print(json.dumps([r.model_dump(exclude_none=True) for r in results], indent=2))
        return

    found = [r for r in results if r.found]

    console.print()

    if found:
        table = Table(box=box.ROUNDED, border_style="green", padding=(0, 2))
        table.add_column("Platform", style="bold green")
        table.add_column("URL", style="white")

        for r in found:
            table.add_row(r.platform, f"[link={r.url}]{r.url}[/link]")

        console.print(Panel(table, title=f"[bold green]✓ FOUND ({len(found)})[/bold green]", border_style="green"))
    else:
        console.print("[yellow]No accounts found.[/yellow]")

    console.print(f"\n[bold]Summary:[/bold] Found on {len(found)}/{len(results)} platforms")


@app.command("myip")
def my_ip(json_output: bool = typer.Option(False, "--json", "-j")) -> None:
    """Show your public IP and location."""
    from aware.lookups.ip_info import get_my_ip

    console.print(BANNER)

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[cyan]Detecting...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("", total=None)
        result = asyncio.run(get_my_ip())

    if result.error:
        err_console.print(f"[red]✗ {result.error}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold green]Your IP:[/bold green] [bold]{result.ip}[/bold]\n")
    ip_lookup(result.ip, json_output=json_output)

"""
OSINT lookup commands.

Commands for IP geolocation, phone number parsing, and username enumeration.
"""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(help="OSINT lookup commands")
console = Console()
err_console = Console(stderr=True)


@app.command("ip")
def ip_lookup(
    ip_address: str = typer.Argument(..., help="IP address to look up"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Look up geolocation information for an IP address.

    Uses the ipwho.is API to retrieve location data including country,
    city, ISP, timezone, and coordinates.

    Example:
        aware lookup ip 8.8.8.8
    """
    import asyncio

    from aware.lookups.ip_info import lookup_ip

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description="Looking up IP...", total=None)
        result = asyncio.run(lookup_ip(ip_address))

    if result.error:
        err_console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)

    if json_output:
        import json

        console.print(json.dumps(result.model_dump(exclude_none=True), indent=2))
        return

    # Display as formatted table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("IP", result.ip)
    table.add_row("Type", result.ip_type or "Unknown")
    table.add_row("Country", f"{result.country} ({result.country_code})" if result.country else "Unknown")
    table.add_row("Region", f"{result.region} ({result.region_code})" if result.region else "Unknown")
    table.add_row("City", result.city or "Unknown")
    table.add_row("Postal", result.postal or "Unknown")
    table.add_row("Coordinates", f"{result.latitude}, {result.longitude}" if result.latitude else "Unknown")

    if result.latitude and result.longitude:
        maps_url = f"https://www.google.com/maps/@{result.latitude},{result.longitude},12z"
        table.add_row("Maps", f"[link={maps_url}]{maps_url}[/link]")

    table.add_row("", "")  # Separator
    table.add_row("ISP", result.isp or "Unknown")
    table.add_row("Organization", result.org or "Unknown")
    table.add_row("ASN", str(result.asn) if result.asn else "Unknown")
    table.add_row("Domain", result.domain or "Unknown")

    table.add_row("", "")  # Separator
    table.add_row("Timezone", result.timezone_id or "Unknown")
    table.add_row("UTC Offset", result.utc_offset or "Unknown")
    table.add_row("Current Time", result.current_time or "Unknown")

    console.print(Panel(table, title=f"[bold]IP Geolocation: {ip_address}[/bold]", border_style="cyan"))


@app.command("phone")
def phone_lookup(
    phone_number: str = typer.Argument(..., help="Phone number with country code (e.g., +14155551234)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Parse and validate a phone number.

    Extracts carrier, region, timezone, and format information.
    Uses the phonenumbers library for offline parsing.

    Example:
        aware lookup phone +14155551234
        aware lookup phone +6281234567890
    """
    from aware.lookups.phone import parse_phone_number

    result = parse_phone_number(phone_number)

    if result.error:
        err_console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)

    if json_output:
        import json

        console.print(json.dumps(result.model_dump(exclude_none=True), indent=2))
        return

    # Display as formatted table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Original", result.original)
    table.add_row("Valid", "[green]Yes[/green]" if result.is_valid else "[red]No[/red]")
    table.add_row("Possible", "[green]Yes[/green]" if result.is_possible else "[yellow]No[/yellow]")

    table.add_row("", "")  # Separator
    table.add_row("Country Code", f"+{result.country_code}" if result.country_code else "Unknown")
    table.add_row("National Number", str(result.national_number) if result.national_number else "Unknown")
    table.add_row("Region", f"{result.location} ({result.region_code})" if result.location else result.region_code or "Unknown")

    table.add_row("", "")  # Separator
    table.add_row("Carrier", result.carrier or "Unknown")
    table.add_row("Type", result.number_type or "Unknown")
    table.add_row("Timezone", result.timezone or "Unknown")

    table.add_row("", "")  # Separator
    table.add_row("International", result.international_format or "Unknown")
    table.add_row("E.164", result.e164_format or "Unknown")
    table.add_row("National", result.national_format or "Unknown")

    console.print(Panel(table, title=f"[bold]Phone Number Info[/bold]", border_style="cyan"))


@app.command("user")
def username_lookup(
    username: str = typer.Argument(..., help="Username to search for"),
    timeout: float = typer.Option(5.0, "--timeout", "-t", help="Timeout per site in seconds"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Search for a username across social media platforms.

    Checks if the username exists on various platforms by making
    HTTP requests to profile URLs.

    Example:
        aware lookup user johndoe
    """
    import asyncio

    from aware.lookups.username import search_username

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description=f"Searching for '{username}'...", total=None)
        results = asyncio.run(search_username(username, timeout=timeout))

    if json_output:
        import json

        output = [r.model_dump(exclude_none=True) for r in results]
        console.print(json.dumps(output, indent=2))
        return

    # Separate found and not found
    found = [r for r in results if r.found]
    not_found = [r for r in results if not r.found and not r.error]
    errors = [r for r in results if r.error]

    # Display found
    if found:
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Platform", style="cyan")
        table.add_column("URL", style="green")

        for r in found:
            table.add_row(r.platform, f"[link={r.url}]{r.url}[/link]")

        console.print(Panel(table, title=f"[bold green]Found ({len(found)})[/bold green]", border_style="green"))

    # Display not found (collapsed)
    if not_found:
        platforms = ", ".join(r.platform for r in not_found)
        console.print(f"\n[dim]Not found on: {platforms}[/dim]")

    # Display errors
    if errors:
        console.print(f"\n[yellow]Errors checking: {', '.join(r.platform for r in errors)}[/yellow]")

    # Summary
    console.print(f"\n[bold]Summary:[/bold] Found on {len(found)}/{len(results)} platforms")


@app.command("myip")
def my_ip(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """
    Show your public IP address and location.

    Example:
        aware lookup myip
    """
    import asyncio

    from aware.lookups.ip_info import get_my_ip, lookup_ip

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(description="Getting your IP...", total=None)
        my_ip_result = asyncio.run(get_my_ip())

    if my_ip_result.error:
        err_console.print(f"[red]Error:[/red] {my_ip_result.error}")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Your IP:[/bold cyan] {my_ip_result.ip}")

    # Also show location info
    console.print()
    ip_lookup(my_ip_result.ip, json_output=json_output)

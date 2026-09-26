"""
Tracking link commands.
"""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aware.cli.commands.auth import get_auth_headers, get_server_url

app = typer.Typer(help="Tracking link commands")
console = Console()
err_console = Console(stderr=True)


def _check_auth() -> dict[str, str]:
    """Check if logged in and return headers."""
    headers = get_auth_headers()
    if not headers:
        err_console.print("[red]Not logged in[/red]")
        err_console.print("[dim]Login with: aware auth login[/dim]")
        raise typer.Exit(1)
    return headers


@app.command("create")
def create_link(
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Label for the link"),
    expires: Optional[int] = typer.Option(24, "--expires", "-e", help="Hours until expiry (default: 24)"),
    reusable: bool = typer.Option(False, "--reusable", "-r", help="Allow multiple uses"),
) -> None:
    """
    Create a tracking link.

    Send this link to someone - when they open it and allow location,
    you'll see their GPS coordinates.

    Example:
        aware link create
        aware link create --label "John's location"
        aware link create --expires 48 --reusable
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    try:
        response = httpx.post(
            f"{server_url}/track",
            headers=headers,
            json={
                "label": label,
                "expires_hours": expires,
                "single_use": not reusable,
            },
            timeout=10.0,
        )

        if response.status_code == 201:
            data = response.json()

            console.print()
            console.print(Panel(
                f"[bold cyan]{data['url']}[/bold cyan]",
                title="[bold green]✓ Tracking Link Created[/bold green]",
                subtitle=f"[dim]Code: {data['code']}[/dim]",
                border_style="green",
            ))
            console.print()

            console.print("[bold]Send this link to your friend.[/bold]")
            console.print("When they open it and tap 'Verify', you'll see their location.")
            console.print()
            console.print(f"[dim]Expires: {data.get('expires_at', 'Never')}[/dim]")
            console.print(f"[dim]Single use: {data.get('single_use', True)}[/dim]")
            console.print()
            console.print("[dim]Check status with: aware link list[/dim]")
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
        err_console.print("[dim]Start server with: aware server start[/dim]")
        raise typer.Exit(1)


@app.command("list")
def list_links() -> None:
    """
    List all your tracking links.

    Shows which links have captured a location.

    Example:
        aware link list
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    try:
        response = httpx.get(
            f"{server_url}/track",
            headers=headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            links = response.json()

            if not links:
                console.print("[yellow]No tracking links yet[/yellow]")
                console.print("[dim]Create one with: aware link create[/dim]")
                return

            table = Table(title="Your Tracking Links")
            table.add_column("Label", style="cyan")
            table.add_column("Code", style="white")
            table.add_column("Status", style="white")
            table.add_column("Location", style="green")
            table.add_column("Created", style="dim")

            for link in links:
                label = link.get("label") or "[dim]No label[/dim]"
                code = link.get("code", "???")

                # Status
                if link.get("captured_at"):
                    status = "[green]✓ Captured[/green]"
                elif not link.get("is_active"):
                    status = "[red]Expired[/red]"
                else:
                    status = "[yellow]Waiting...[/yellow]"

                # Location
                if link.get("latitude") and link.get("longitude"):
                    lat = link["latitude"]
                    lon = link["longitude"]
                    location = f"{lat:.6f}, {lon:.6f}"
                else:
                    location = "-"

                # Created
                created = link.get("created_at", "")[:10] if link.get("created_at") else ""

                table.add_row(label, code, status, location, created)

            console.print(table)
            console.print()
            console.print("[dim]View details: aware link show <code>[/dim]")
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")


@app.command("show")
def show_link(
    code: str = typer.Argument(..., help="Link code to show"),
) -> None:
    """
    Show details of a tracking link.

    Example:
        aware link show ABC123
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    try:
        response = httpx.get(
            f"{server_url}/track",
            headers=headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            links = response.json()
            link = next((l for l in links if l.get("code") == code), None)

            if not link:
                err_console.print(f"[red]Link '{code}' not found[/red]")
                raise typer.Exit(1)

            # Build info table
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Code", link.get("code", ""))
            table.add_row("URL", link.get("url", ""))
            table.add_row("Label", link.get("label") or "[dim]None[/dim]")
            table.add_row("Status", "[green]Active[/green]" if link.get("is_active") else "[red]Inactive[/red]")
            table.add_row("Single Use", "Yes" if link.get("single_use") else "No")
            table.add_row("Expires", str(link.get("expires_at") or "Never"))
            table.add_row("Created", link.get("created_at", "")[:19] if link.get("created_at") else "")

            console.print(Panel(table, title="[bold]Link Details[/bold]", border_style="cyan"))

            # If captured, show location
            if link.get("captured_at"):
                console.print()
                loc_table = Table(show_header=False, box=None, padding=(0, 2))
                loc_table.add_column("Field", style="cyan")
                loc_table.add_column("Value", style="green")

                lat = link.get("latitude")
                lon = link.get("longitude")
                acc = link.get("accuracy_meters")

                loc_table.add_row("Captured At", link.get("captured_at", "")[:19])
                loc_table.add_row("Latitude", f"{lat:.6f}" if lat else "Unknown")
                loc_table.add_row("Longitude", f"{lon:.6f}" if lon else "Unknown")
                loc_table.add_row("Accuracy", f"{acc:.0f} meters" if acc else "Unknown")
                loc_table.add_row("IP Address", link.get("ip_address") or "Unknown")

                if lat and lon:
                    maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                    loc_table.add_row("Google Maps", f"[link={maps_url}]{maps_url}[/link]")

                console.print(Panel(loc_table, title="[bold green]✓ Location Captured[/bold green]", border_style="green"))
            else:
                console.print()
                console.print("[yellow]Location not yet captured[/yellow]")
                console.print("[dim]Share the link and wait for them to open it[/dim]")
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")


@app.command("delete")
def delete_link(
    code: str = typer.Argument(..., help="Link code to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """
    Delete a tracking link.

    Example:
        aware link delete ABC123
    """
    import httpx
    from rich.prompt import Confirm

    headers = _check_auth()
    server_url = get_server_url()

    if not force:
        if not Confirm.ask(f"Delete tracking link '{code}'?"):
            raise typer.Exit()

    try:
        response = httpx.delete(
            f"{server_url}/track/{code}",
            headers=headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            console.print(f"[green]✓ Link '{code}' deleted[/green]")
        elif response.status_code == 404:
            err_console.print(f"[red]Link '{code}' not found[/red]")
            raise typer.Exit(1)
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
        raise typer.Exit(1)

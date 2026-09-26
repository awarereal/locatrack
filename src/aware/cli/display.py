"""
Display utilities for CLI output.

Functions for rendering live dashboards, tables, and formatted output.
"""

from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from aware.cli.commands.auth import get_auth_headers, get_server_url

console = Console()
err_console = Console(stderr=True)


def show_live_dashboard(refresh_interval: int = 5) -> None:
    """
    Show a live dashboard of shared locations.

    Args:
        refresh_interval: How often to refresh in seconds
    """
    import asyncio
    import httpx

    headers = get_auth_headers()
    if not headers:
        console.print("[yellow]Not logged in[/yellow]")
        console.print("[dim]Login with: aware auth login[/dim]")
        return

    server_url = get_server_url()
    console.print("[dim]Press Ctrl+C to exit[/dim]\n")

    async def fetch_and_display() -> None:
        last_error: Optional[str] = None

        def make_dashboard() -> Panel:
            # Create locations table
            loc_table = Table(show_header=True, expand=True)
            loc_table.add_column("User", style="cyan")
            loc_table.add_column("Device", style="white")
            loc_table.add_column("Location", style="white")
            loc_table.add_column("Updated", style="dim")

            if cached_locations:
                for loc in cached_locations:
                    user = loc.get("user", {}).get("username", "Unknown")
                    device = loc.get("device", {}).get("name", "Unknown")

                    # Format location
                    city = loc.get("city", "")
                    country = loc.get("country", "")
                    location_str = f"{city}, {country}" if city else "Unknown"

                    # Format time
                    updated = loc.get("recorded_at", "")
                    if updated:
                        try:
                            dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                            updated = dt.strftime("%H:%M:%S")
                        except Exception:
                            pass

                    loc_table.add_row(user, device, location_str, updated)
            else:
                loc_table.add_row("[dim]No locations available[/dim]", "", "", "")

            # Build panel
            status = f"[green]Connected[/green]" if not last_error else f"[red]{last_error}[/red]"
            return Panel(
                loc_table,
                title=f"[bold]Shared Locations[/bold] ({len(cached_locations)})",
                subtitle=f"Status: {status} | Refresh: {refresh_interval}s",
                border_style="cyan",
            )

        cached_locations: list = []

        with Live(make_dashboard(), console=console, refresh_per_second=1) as live:
            async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
                while True:
                    try:
                        response = await client.get(f"{server_url}/locations/live")

                        if response.status_code == 200:
                            cached_locations = response.json()
                            last_error = None
                        else:
                            last_error = f"HTTP {response.status_code}"

                    except httpx.RequestError as e:
                        last_error = str(e)
                    except Exception as e:
                        last_error = str(e)

                    live.update(make_dashboard())
                    await asyncio.sleep(refresh_interval)

    try:
        asyncio.run(fetch_and_display())
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard closed[/dim]")


def show_history(limit: int = 50, device_filter: Optional[str] = None) -> None:
    """
    Show location history.

    Args:
        limit: Maximum number of entries to show
        device_filter: Optional device name to filter by
    """
    import httpx

    headers = get_auth_headers()
    if not headers:
        console.print("[yellow]Not logged in[/yellow]")
        console.print("[dim]Login with: aware auth login[/dim]")
        return

    server_url = get_server_url()

    try:
        params = {"limit": limit}
        if device_filter:
            params["device"] = device_filter

        response = httpx.get(
            f"{server_url}/locations/me",
            headers=headers,
            params=params,
            timeout=10.0,
        )

        if response.status_code == 200:
            locations = response.json()

            if not locations:
                console.print("[yellow]No location history[/yellow]")
                console.print("[dim]Start tracking with: aware track start[/dim]")
                return

            table = Table(title="Location History")
            table.add_column("Time", style="dim")
            table.add_column("Device", style="cyan")
            table.add_column("Location", style="white")
            table.add_column("Source", style="dim")
            table.add_column("Accuracy", style="dim")

            for loc in locations:
                # Format time
                recorded = loc.get("recorded_at", "")
                if recorded:
                    try:
                        dt = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
                        recorded = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

                device = loc.get("device", {}).get("name", "Unknown")

                # Format location
                lat = loc.get("latitude")
                lon = loc.get("longitude")
                city = loc.get("metadata", {}).get("city", "")
                if city:
                    location_str = city
                elif lat and lon:
                    location_str = f"{lat:.4f}, {lon:.4f}"
                else:
                    location_str = "Unknown"

                source = loc.get("source", "unknown")
                accuracy = loc.get("accuracy_meters")
                accuracy_str = f"{accuracy:.0f}m" if accuracy else "-"

                table.add_row(recorded, device, location_str, source, accuracy_str)

            console.print(table)
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
    except Exception as e:
        err_console.print(f"[red]Error: {e}[/red]")


def format_location(lat: float, lon: float, city: Optional[str] = None) -> str:
    """Format a location for display."""
    if city:
        return city
    return f"{lat:.4f}, {lon:.4f}"


def format_time_ago(dt: datetime) -> str:
    """Format a datetime as relative time."""
    now = datetime.now(dt.tzinfo)
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        mins = int(seconds / 60)
        return f"{mins}m ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}h ago"
    else:
        days = int(seconds / 86400)
        return f"{days}d ago"

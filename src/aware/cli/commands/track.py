"""
Location tracking commands.
"""

import asyncio
import signal
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from aware.cli.commands.auth import get_auth_headers, get_server_url
from aware.config import settings

app = typer.Typer(help="Location tracking commands")
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


@app.command("start")
def start_tracking(
    interval: int = typer.Option(
        30, "--interval", "-i", help="Update interval in seconds"
    ),
    source: str = typer.Option(
        "ip", "--source", "-s", help="Location source: ip, manual"
    ),
    device_name: Optional[str] = typer.Option(
        None, "--device", "-d", help="Device name"
    ),
    background: bool = typer.Option(
        False, "--background", "-b", help="Run in background"
    ),
) -> None:
    """
    Start sending location updates to the server.

    Example:
        aware track start
        aware track start --interval 60
        aware track start --source ip
    """
    import platform

    headers = _check_auth()
    server_url = get_server_url()

    # Default device name
    if not device_name:
        device_name = f"{platform.node()}-cli"

    console.print(f"[cyan]Starting location tracking...[/cyan]")
    console.print(f"[dim]Device: {device_name}[/dim]")
    console.print(f"[dim]Interval: {interval}s[/dim]")
    console.print(f"[dim]Source: {source}[/dim]")
    console.print()
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    # Run the tracking loop
    try:
        asyncio.run(_tracking_loop(
            server_url=server_url,
            headers=headers,
            device_name=device_name,
            interval=interval,
            source=source,
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]Tracking stopped[/yellow]")


async def _tracking_loop(
    server_url: str,
    headers: dict[str, str],
    device_name: str,
    interval: int,
    source: str,
) -> None:
    """Main tracking loop."""
    import httpx

    from aware.lookups.ip_info import get_my_ip, lookup_ip

    update_count = 0
    last_error: Optional[str] = None

    def make_status_table() -> Table:
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="cyan")
        table.add_column("Value")

        table.add_row("Status", "[green]Running[/green]")
        table.add_row("Updates sent", str(update_count))
        table.add_row("Last error", last_error or "[dim]None[/dim]")
        return table

    with Live(Panel(make_status_table(), title="Tracking"), console=console, refresh_per_second=1) as live:
        async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
            while True:
                try:
                    # Get current location
                    if source == "ip":
                        my_ip = await get_my_ip()
                        if my_ip.error:
                            last_error = f"IP lookup failed: {my_ip.error}"
                            live.update(Panel(make_status_table(), title="Tracking"))
                            await asyncio.sleep(interval)
                            continue

                        location_data = await lookup_ip(my_ip.ip)
                        if not location_data.success:
                            last_error = f"Geolocation failed: {location_data.error}"
                            live.update(Panel(make_status_table(), title="Tracking"))
                            await asyncio.sleep(interval)
                            continue

                        payload = {
                            "device_name": device_name,
                            "latitude": location_data.latitude,
                            "longitude": location_data.longitude,
                            "accuracy_meters": 5000.0,  # IP-based is ~5km accuracy
                            "source": "ip",
                            "metadata": {
                                "ip": my_ip.ip,
                                "city": location_data.city,
                                "country": location_data.country,
                            },
                        }
                    else:
                        last_error = f"Unknown source: {source}"
                        live.update(Panel(make_status_table(), title="Tracking"))
                        await asyncio.sleep(interval)
                        continue

                    # Send to server
                    response = await client.post(
                        f"{server_url}/locations",
                        json=payload,
                    )

                    if response.status_code in (200, 201):
                        update_count += 1
                        last_error = None
                    else:
                        last_error = f"Server error: {response.status_code}"

                    live.update(Panel(make_status_table(), title="Tracking"))

                except httpx.RequestError as e:
                    last_error = f"Network error: {e}"
                    live.update(Panel(make_status_table(), title="Tracking"))
                except Exception as e:
                    last_error = f"Error: {e}"
                    live.update(Panel(make_status_table(), title="Tracking"))

                await asyncio.sleep(interval)


@app.command("stop")
def stop_tracking() -> None:
    """
    Stop the tracking daemon (if running in background).

    Example:
        aware track stop
    """
    # For now, just inform about Ctrl+C
    console.print("[dim]If tracking is running in foreground, press Ctrl+C to stop[/dim]")
    console.print("[dim]Background daemon mode coming soon[/dim]")


@app.command("status")
def tracking_status() -> None:
    """
    Show current tracking status.

    Example:
        aware track status
    """
    import httpx

    headers = get_auth_headers()
    if not headers:
        console.print("[yellow]Not logged in[/yellow]")
        console.print("[dim]Login with: aware auth login[/dim]")
        return

    server_url = get_server_url()

    try:
        # Get devices
        response = httpx.get(
            f"{server_url}/devices",
            headers=headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            devices = response.json()
            if not devices:
                console.print("[yellow]No registered devices[/yellow]")
                console.print("[dim]Start tracking with: aware track start[/dim]")
                return

            table = Table(title="Your Devices")
            table.add_column("Name", style="cyan")
            table.add_column("Last Seen", style="white")
            table.add_column("Last Location", style="dim")

            for device in devices:
                last_seen = device.get("last_seen_at", "Never")
                last_loc = device.get("last_location")
                if last_loc:
                    loc_str = f"{last_loc.get('city', 'Unknown')}, {last_loc.get('country', '')}"
                else:
                    loc_str = "Unknown"

                table.add_row(
                    device.get("name", "Unknown"),
                    last_seen,
                    loc_str,
                )

            console.print(table)
        else:
            err_console.print(f"[red]Error getting devices: {response.status_code}[/red]")

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
    except Exception as e:
        err_console.print(f"[red]Error: {e}[/red]")


@app.command("send")
def send_location(
    latitude: float = typer.Argument(..., help="Latitude"),
    longitude: float = typer.Argument(..., help="Longitude"),
    accuracy: float = typer.Option(10.0, "--accuracy", "-a", help="Accuracy in meters"),
    device_name: Optional[str] = typer.Option(None, "--device", "-d", help="Device name"),
) -> None:
    """
    Send a single location update manually.

    Example:
        aware track send 37.7749 -122.4194
        aware track send 51.5074 -0.1278 --accuracy 5
    """
    import platform

    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    if not device_name:
        device_name = f"{platform.node()}-manual"

    # Validate coordinates
    if not (-90 <= latitude <= 90):
        err_console.print("[red]Latitude must be between -90 and 90[/red]")
        raise typer.Exit(1)
    if not (-180 <= longitude <= 180):
        err_console.print("[red]Longitude must be between -180 and 180[/red]")
        raise typer.Exit(1)

    try:
        response = httpx.post(
            f"{server_url}/locations",
            headers=headers,
            json={
                "device_name": device_name,
                "latitude": latitude,
                "longitude": longitude,
                "accuracy_meters": accuracy,
                "source": "manual",
            },
            timeout=10.0,
        )

        if response.status_code in (200, 201):
            console.print(f"[green]✓ Location sent[/green]")
            console.print(f"[dim]Coordinates: {latitude}, {longitude}[/dim]")
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
        raise typer.Exit(1)

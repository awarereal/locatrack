"""
Server management commands.
"""

import typer
from rich.console import Console

from aware.config import settings

app = typer.Typer(help="Server management commands")
console = Console()
err_console = Console(stderr=True)


@app.command("start")
def start_server(
    host: str = typer.Option(None, "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(None, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
    workers: int = typer.Option(None, "--workers", "-w", help="Number of workers"),
) -> None:
    """
    Start the Aware API server.

    Example:
        aware server start
        aware server start --port 8080
        aware server start --reload
    """
    import uvicorn

    # Use settings as defaults, override with CLI args
    final_host = host or settings.host
    final_port = port or settings.port
    final_workers = workers or settings.workers

    console.print(f"[cyan]Starting Aware server...[/cyan]")
    console.print(f"[dim]Host: {final_host}[/dim]")
    console.print(f"[dim]Port: {final_port}[/dim]")
    console.print(f"[dim]Workers: {final_workers}[/dim]")
    console.print(f"[dim]Reload: {reload}[/dim]")
    console.print()
    console.print(f"[green]API docs: http://{final_host}:{final_port}/docs[/green]")
    console.print()

    uvicorn.run(
        "aware.server.app:app",
        host=final_host,
        port=final_port,
        reload=reload,
        workers=final_workers if not reload else 1,
        log_level="info" if settings.debug else "warning",
    )


@app.command("status")
def server_status(
    url: str = typer.Option(None, "--url", "-u", help="Server URL to check"),
) -> None:
    """
    Check if the server is running.

    Example:
        aware server status
    """
    import httpx

    server_url = url or f"http://{settings.host}:{settings.port}"

    try:
        response = httpx.get(f"{server_url}/health", timeout=5.0)
        if response.status_code == 200:
            console.print(f"[green]✓ Server is running at {server_url}[/green]")
            data = response.json()
            if data.get("version"):
                console.print(f"[dim]Version: {data['version']}[/dim]")
        else:
            console.print(f"[yellow]Server responded with status {response.status_code}[/yellow]")
    except httpx.ConnectError:
        console.print(f"[red]✗ Server is not running at {server_url}[/red]")
        console.print("[dim]Start with: aware server start[/dim]")
    except Exception as e:
        err_console.print(f"[red]Error checking server: {e}[/red]")


@app.command("config")
def show_config() -> None:
    """
    Show current server configuration.

    Example:
        aware server config
    """
    from rich.table import Table

    table = Table(show_header=True, title="Server Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    table.add_column("Source", style="dim")

    # Show relevant settings
    table.add_row("Host", settings.host, "AWARE_HOST or default")
    table.add_row("Port", str(settings.port), "AWARE_PORT or default")
    table.add_row("Workers", str(settings.workers), "AWARE_WORKERS or default")
    table.add_row("Debug", str(settings.debug), "AWARE_DEBUG or default")
    table.add_row("Environment", settings.environment, "AWARE_ENVIRONMENT or default")
    table.add_row("Database", _mask_url(settings.database_url), "AWARE_DATABASE_URL or default")

    console.print(table)


def _mask_url(url: str) -> str:
    """Mask sensitive parts of a database URL."""
    if "@" in url:
        # Mask password in connection string
        parts = url.split("@")
        prefix = parts[0]
        if ":" in prefix:
            # Has password
            proto_user = prefix.rsplit(":", 1)[0]
            return f"{proto_user}:****@{parts[1]}"
    return url

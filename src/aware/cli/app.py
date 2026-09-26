"""
Locatrack CLI application.

Premium OSINT and location tracking tool.
"""

import os
import signal
import subprocess
import sys
import time
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from aware import __version__
from aware.cli.commands import auth, circle, link, lookup, server, track
from aware.config import settings

# Main CLI app
app = typer.Typer(
    name="locatrack",
    help="OSINT intelligence & location tracking tool.",
    no_args_is_help=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=settings.debug,
)

# Register command groups
app.add_typer(server.app, name="server", help="Manage the API server")
app.add_typer(auth.app, name="auth", help="Authentication")
app.add_typer(track.app, name="track", help="Location tracking")
app.add_typer(circle.app, name="circle", help="Sharing circles")
app.add_typer(link.app, name="link", help="Tracking links")
app.add_typer(lookup.app, name="lookup", help="OSINT lookups")

console = Console()
err_console = Console(stderr=True)

# Calvin S style ASCII banner
BANNER = r"""
[bold cyan]
╦  ╔═╗╔═╗╔═╗╔╦╗╦═╗╔═╗╔═╗╦╔═
║  ║ ║║  ╠═╣ ║ ╠╦╝╠═╣║  ╠╩╗
╩═╝╚═╝╚═╝╩ ╩ ╩ ╩╚═╩ ╩╚═╝╩ ╩[/bold cyan]
[dim]OSINT Intelligence & Location Tracking[/dim]
"""

SERVER_PID_FILE = os.path.expanduser("~/.locatrack_server.pid")


def print_banner() -> None:
    """Print the main banner."""
    console.print(BANNER)
    console.print(f"[dim]v{__version__}[/dim]\n")


def is_server_running() -> bool:
    """Check if server is running."""
    import httpx
    try:
        resp = httpx.get(f"http://127.0.0.1:{settings.port}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def start_background_server() -> bool:
    """Start server in background if not running."""
    if is_server_running():
        return True

    console.print("[dim]Starting server in background...[/dim]")

    try:
        # Start uvicorn in background
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "aware.server.app:app",
                "--host", "127.0.0.1",
                "--port", str(settings.port),
                "--log-level", "error",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Save PID
        with open(SERVER_PID_FILE, "w") as f:
            f.write(str(proc.pid))

        # Wait for startup
        for _ in range(20):
            time.sleep(0.25)
            if is_server_running():
                console.print(f"[green]✓ Server running on port {settings.port}[/green]")
                return True

        err_console.print("[yellow]Server started but not responding yet[/yellow]")
        return False

    except Exception as e:
        err_console.print(f"[red]Failed to start server: {e}[/red]")
        return False


def stop_background_server() -> None:
    """Stop background server if running."""
    if os.path.exists(SERVER_PID_FILE):
        try:
            with open(SERVER_PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            os.remove(SERVER_PID_FILE)
            console.print("[dim]Server stopped[/dim]")
        except Exception:
            pass


def ensure_server() -> bool:
    """Ensure server is running for features that need it."""
    if not is_server_running():
        return start_background_server()
    return True


def print_menu() -> None:
    """Print the interactive menu."""
    table = Table(
        show_header=False,
        box=box.ROUNDED,
        border_style="cyan",
        padding=(0, 2),
    )
    table.add_column("Key", style="bold cyan", width=4)
    table.add_column("Action", style="white")

    table.add_row("1", "📱 Phone OSINT lookup")
    table.add_row("2", "🌐 IP geolocation")
    table.add_row("3", "👤 Username search")
    table.add_row("4", "🔗 Create tracking link")
    table.add_row("5", "📍 View captured locations")
    table.add_row("6", "⚙️  Server management")
    table.add_row("0", "Exit")

    console.print(Panel(table, title="[bold]MENU[/bold]", border_style="cyan"))


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
) -> None:
    """
    Locatrack - OSINT intelligence & location tracking.

    Run without arguments for interactive mode.
    """
    if version:
        console.print(f"Locatrack v{__version__}")
        raise typer.Exit()

    if ctx.invoked_subcommand is not None:
        return

    run_interactive()


def run_interactive() -> None:
    """Run the interactive menu loop."""
    print_banner()

    while True:
        print_menu()

        try:
            choice = console.input("\n[cyan]>[/cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        console.print()

        if choice == "0":
            console.print("[dim]Goodbye![/dim]")
            break
        elif choice == "1":
            _interactive_phone()
        elif choice == "2":
            _interactive_ip()
        elif choice == "3":
            _interactive_user()
        elif choice == "4":
            _interactive_link()
        elif choice == "5":
            _interactive_locations()
        elif choice == "6":
            _server_menu()
        else:
            err_console.print(f"[red]Invalid option[/red]")

        console.print()


def _interactive_phone() -> None:
    """Phone OSINT lookup."""
    try:
        phone = console.input("[magenta]Enter phone number:[/magenta] ").strip()
        if phone:
            _run_command(["lookup", "phone", phone])
    except (KeyboardInterrupt, EOFError):
        pass


def _interactive_ip() -> None:
    """IP geolocation lookup."""
    try:
        ip = console.input("[cyan]Enter IP address (or 'me'):[/cyan] ").strip()
        if ip:
            if ip.lower() == "me":
                _run_command(["lookup", "myip"])
            else:
                _run_command(["lookup", "ip", ip])
    except (KeyboardInterrupt, EOFError):
        pass


def _interactive_user() -> None:
    """Username search."""
    try:
        username = console.input("[cyan]Enter username:[/cyan] ").strip()
        if username:
            _run_command(["lookup", "user", username])
    except (KeyboardInterrupt, EOFError):
        pass


def _interactive_link() -> None:
    """Create tracking link."""
    if not ensure_server():
        err_console.print("[red]Server required for tracking links[/red]")
        return

    try:
        label = console.input("[cyan]Label (optional):[/cyan] ").strip()
        args = ["link", "create"]
        if label:
            args.extend(["--label", label])
        _run_command(args)
    except (KeyboardInterrupt, EOFError):
        pass


def _interactive_locations() -> None:
    """View captured locations."""
    if not ensure_server():
        err_console.print("[red]Server required[/red]")
        return
    _run_command(["link", "list"])


def _server_menu() -> None:
    """Server management submenu."""
    status = "[green]Running[/green]" if is_server_running() else "[red]Stopped[/red]"
    console.print(f"Server status: {status}")
    console.print()
    console.print("[1] Start server")
    console.print("[2] Stop server")
    console.print("[3] Open dashboard")
    console.print("[0] Back")

    try:
        choice = console.input("\n[cyan]>[/cyan] ").strip()
        if choice == "1":
            start_background_server()
        elif choice == "2":
            stop_background_server()
        elif choice == "3":
            if ensure_server():
                import webbrowser
                webbrowser.open(f"http://127.0.0.1:{settings.port}/dashboard")
                console.print("[green]Opened dashboard in browser[/green]")
    except (KeyboardInterrupt, EOFError):
        pass


def _run_command(args: list[str]) -> None:
    """Run a CLI command."""
    try:
        original_argv = sys.argv
        sys.argv = ["locatrack"] + args
        try:
            app(standalone_mode=False)
        finally:
            sys.argv = original_argv
    except typer.Exit:
        pass
    except Exception as e:
        err_console.print(f"[red]Error: {e}[/red]")


@app.command()
def scan(
    target: str = typer.Argument(..., help="Phone number, IP address, or username"),
) -> None:
    """
    Quick scan - auto-detect target type.

    Example:
        locatrack scan +14155551234
        locatrack scan 8.8.8.8
        locatrack scan johndoe
    """
    import re

    target = target.strip()

    # Phone number (starts with + or contains country code patterns)
    if target.startswith("+") or re.match(r"^\d{10,15}$", target.replace("-", "").replace(" ", "")):
        console.print("[magenta]Detected: Phone number[/magenta]\n")
        _run_command(["lookup", "phone", target])

    # IP address
    elif re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", target):
        console.print("[cyan]Detected: IP address[/cyan]\n")
        _run_command(["lookup", "ip", target])

    # Username
    else:
        console.print("[blue]Detected: Username[/blue]\n")
        _run_command(["lookup", "user", target])


@app.command()
def dashboard() -> None:
    """Open the web dashboard in browser."""
    if ensure_server():
        import webbrowser
        url = f"http://127.0.0.1:{settings.port}/dashboard"
        webbrowser.open(url)
        console.print(f"[green]Opened {url}[/green]")


def main() -> None:
    """Main entry point."""
    try:
        app()
    except KeyboardInterrupt:
        err_console.print("\n[dim]Interrupted[/dim]")
        raise SystemExit(130)


if __name__ == "__main__":
    main()

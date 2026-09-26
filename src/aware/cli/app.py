"""
Aware CLI application.

Main entry point for all CLI commands.
"""

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aware import __version__
from aware.cli.commands import auth, circle, lookup, server, track
from aware.config import settings

# Main CLI app
app = typer.Typer(
    name="aware",
    help="Consent-based location sharing and OSINT lookup tool.",
    no_args_is_help=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=settings.debug,
)

# Register command groups
app.add_typer(server.app, name="server", help="Start and manage the API server")
app.add_typer(auth.app, name="auth", help="Authentication commands")
app.add_typer(track.app, name="track", help="Location tracking commands")
app.add_typer(circle.app, name="circle", help="Manage sharing circles")
app.add_typer(lookup.app, name="lookup", help="OSINT lookup commands")

# Console for output
console = Console()
err_console = Console(stderr=True)


def print_banner() -> None:
    """Print the Aware banner."""
    banner = r"""
[bold cyan]    ___
   /   |_      ______ _________
  / /| | | /| / / __ `/ ___/ _ \
 / ___ | |/ |/ / /_/ / /  /  __/
/_/  |_|__/|__/\__,_/_/   \___/[/bold cyan]
    """
    console.print(banner)
    console.print(f"[dim]v{__version__} • Consent-based location sharing[/dim]\n")


def print_menu() -> None:
    """Print the interactive menu."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan bold", width=6)
    table.add_column("Action", style="white")

    table.add_row("[1]", "Start/stop location tracking")
    table.add_row("[2]", "View shared locations")
    table.add_row("[3]", "Manage sharing circles")
    table.add_row("[4]", "IP geolocation lookup")
    table.add_row("[5]", "Phone number lookup")
    table.add_row("[6]", "Username search")
    table.add_row("[7]", "Server management")
    table.add_row("[0]", "Exit")

    console.print(Panel(table, title="[bold]Menu[/bold]", border_style="cyan"))


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version and exit"
    ),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Start interactive mode"
    ),
) -> None:
    """
    Aware - Consent-based location sharing and OSINT lookup tool.

    Run without arguments for interactive mode, or use subcommands directly.
    """
    if version:
        console.print(f"Aware v{__version__}")
        raise typer.Exit()

    # If a subcommand was invoked, let it handle things
    if ctx.invoked_subcommand is not None:
        return

    # Interactive mode
    run_interactive()


def run_interactive() -> None:
    """Run the interactive menu loop."""
    print_banner()

    while True:
        print_menu()

        try:
            choice = console.input("\n[cyan]Select option:[/cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if choice == "0":
            console.print("[dim]Goodbye![/dim]")
            break
        elif choice == "1":
            _run_command(["track", "status"])
        elif choice == "2":
            _run_command(["live"])
        elif choice == "3":
            _run_command(["circle", "list"])
        elif choice == "4":
            _interactive_ip_lookup()
        elif choice == "5":
            _interactive_phone_lookup()
        elif choice == "6":
            _interactive_username_lookup()
        elif choice == "7":
            _run_command(["server", "status"])
        else:
            err_console.print(f"[red]Invalid option: {choice}[/red]")

        console.print()  # Blank line before next menu


def _interactive_ip_lookup() -> None:
    """Interactive IP geolocation lookup."""
    try:
        ip = console.input("[cyan]Enter IP address:[/cyan] ").strip()
        if ip:
            _run_command(["lookup", "ip", ip])
    except (KeyboardInterrupt, EOFError):
        pass


def _interactive_phone_lookup() -> None:
    """Interactive phone number lookup."""
    try:
        phone = console.input("[cyan]Enter phone number (with country code):[/cyan] ").strip()
        if phone:
            _run_command(["lookup", "phone", phone])
    except (KeyboardInterrupt, EOFError):
        pass


def _interactive_username_lookup() -> None:
    """Interactive username search."""
    try:
        username = console.input("[cyan]Enter username:[/cyan] ").strip()
        if username:
            _run_command(["lookup", "user", username])
    except (KeyboardInterrupt, EOFError):
        pass


def _run_command(args: list[str]) -> None:
    """Run a CLI command programmatically."""
    try:
        # Save original argv and replace
        original_argv = sys.argv
        sys.argv = ["aware"] + args
        try:
            app(standalone_mode=False)
        finally:
            sys.argv = original_argv
    except typer.Exit:
        pass
    except Exception as e:
        err_console.print(f"[red]Error: {e}[/red]")


@app.command()
def live(
    refresh: int = typer.Option(5, "--refresh", "-r", help="Refresh interval in seconds"),
) -> None:
    """Show live dashboard of shared locations."""
    from aware.cli.display import show_live_dashboard

    show_live_dashboard(refresh_interval=refresh)


@app.command()
def history(
    limit: int = typer.Option(50, "--limit", "-n", help="Number of entries to show"),
    device: Optional[str] = typer.Option(None, "--device", "-d", help="Filter by device"),
) -> None:
    """Show location history."""
    from aware.cli.display import show_history

    show_history(limit=limit, device_filter=device)


def main() -> None:
    """Main entry point."""
    try:
        app()
    except KeyboardInterrupt:
        err_console.print("\n[dim]Interrupted[/dim]")
        raise SystemExit(130)


if __name__ == "__main__":
    main()

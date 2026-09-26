"""
Authentication commands.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from aware.config import settings

app = typer.Typer(help="Authentication commands")
console = Console()
err_console = Console(stderr=True)

# Token storage location
TOKEN_FILE = settings.data_dir / "auth.json"


def _ensure_data_dir() -> None:
    """Ensure the data directory exists."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)


def _save_tokens(access_token: str, refresh_token: str, server_url: str) -> None:
    """Save tokens to local storage."""
    import json
    import os

    _ensure_data_dir()
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "server_url": server_url,
    }
    TOKEN_FILE.write_text(json.dumps(data, indent=2))
    TOKEN_FILE.chmod(0o600)  # Secure permissions

    # Also save simple token file for quick access
    simple_token = Path(os.path.expanduser("~/.locatrack_token"))
    simple_token.write_text(access_token)
    simple_token.chmod(0o600)


def _load_tokens() -> Optional[dict]:
    """Load tokens from local storage."""
    import json

    if not TOKEN_FILE.exists():
        return None
    try:
        return json.loads(TOKEN_FILE.read_text())
    except Exception:
        return None


def _clear_tokens() -> None:
    """Clear stored tokens."""
    import os
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    # Also clear simple token
    simple_token = Path(os.path.expanduser("~/.locatrack_token"))
    if simple_token.exists():
        simple_token.unlink()


def get_auth_headers() -> Optional[dict[str, str]]:
    """Get authorization headers if logged in."""
    tokens = _load_tokens()
    if tokens and tokens.get("access_token"):
        return {"Authorization": f"Bearer {tokens['access_token']}"}
    return None


def get_server_url() -> str:
    """Get the server URL from tokens or default."""
    tokens = _load_tokens()
    if tokens and tokens.get("server_url"):
        return tokens["server_url"]
    return f"http://{settings.host}:{settings.port}"


@app.command("register")
def register(
    server: str = typer.Option(None, "--server", "-s", help="Server URL"),
    username: str = typer.Option(None, "--username", "-u", help="Username"),
    email: str = typer.Option(None, "--email", "-e", help="Email address"),
) -> None:
    """
    Create a new account on the server.

    Example:
        aware auth register
        aware auth register --username myname --email me@example.com
    """
    import httpx

    server_url = server or get_server_url()

    # Interactive prompts if not provided
    if not username:
        username = Prompt.ask("[cyan]Username[/cyan]")
    if not email:
        email = Prompt.ask("[cyan]Email[/cyan]")
    password = Prompt.ask("[cyan]Password[/cyan]", password=True)
    password_confirm = Prompt.ask("[cyan]Confirm password[/cyan]", password=True)

    if password != password_confirm:
        err_console.print("[red]Passwords do not match[/red]")
        raise typer.Exit(1)

    try:
        response = httpx.post(
            f"{server_url}/auth/register",
            json={
                "username": username,
                "email": email,
                "password": password,
            },
            timeout=10.0,
        )

        if response.status_code == 201:
            data = response.json()
            console.print(f"[green]✓ Account created successfully![/green]")
            console.print(f"[dim]User ID: {data.get('id')}[/dim]")

            # Auto-login after registration
            if Confirm.ask("Login now?", default=True):
                _do_login(server_url, username, password)
        elif response.status_code == 409:
            err_console.print("[red]Username or email already exists[/red]")
            raise typer.Exit(1)
        else:
            err_console.print(f"[red]Registration failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print(f"[red]Cannot connect to server at {server_url}[/red]")
        err_console.print("[dim]Is the server running? Start with: aware server start[/dim]")
        raise typer.Exit(1)
    except Exception as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("login")
def login(
    server: str = typer.Option(None, "--server", "-s", help="Server URL"),
    username: str = typer.Option(None, "--username", "-u", help="Username"),
) -> None:
    """
    Login to the server.

    Example:
        aware auth login
        aware auth login --username myname
    """
    server_url = server or get_server_url()

    if not username:
        username = Prompt.ask("[cyan]Username[/cyan]")
    password = Prompt.ask("[cyan]Password[/cyan]", password=True)

    _do_login(server_url, username, password)


def _do_login(server_url: str, username: str, password: str) -> None:
    """Perform login and save tokens."""
    import httpx

    try:
        response = httpx.post(
            f"{server_url}/auth/login",
            data={
                "username": username,
                "password": password,
            },
            timeout=10.0,
        )

        if response.status_code == 200:
            data = response.json()
            _save_tokens(
                data["access_token"],
                data.get("refresh_token", ""),
                server_url,
            )
            console.print(f"[green]✓ Logged in as {username}[/green]")
        elif response.status_code == 401:
            err_console.print("[red]Invalid username or password[/red]")
            raise typer.Exit(1)
        else:
            err_console.print(f"[red]Login failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print(f"[red]Cannot connect to server at {server_url}[/red]")
        raise typer.Exit(1)


@app.command("logout")
def logout() -> None:
    """
    Logout and clear stored credentials.

    Example:
        aware auth logout
    """
    import httpx

    tokens = _load_tokens()
    if tokens:
        # Try to invalidate on server
        try:
            httpx.post(
                f"{tokens['server_url']}/auth/logout",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                timeout=5.0,
            )
        except Exception:
            pass  # Ignore errors, still clear local tokens

    _clear_tokens()
    console.print("[green]✓ Logged out[/green]")


@app.command("status")
def auth_status() -> None:
    """
    Show current authentication status.

    Example:
        aware auth status
    """
    import httpx

    tokens = _load_tokens()
    if not tokens:
        console.print("[yellow]Not logged in[/yellow]")
        console.print("[dim]Login with: aware auth login[/dim]")
        return

    server_url = tokens.get("server_url", "Unknown")
    console.print(f"[cyan]Server:[/cyan] {server_url}")

    # Try to get current user info
    try:
        response = httpx.get(
            f"{server_url}/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            timeout=5.0,
        )

        if response.status_code == 200:
            user = response.json()
            console.print(f"[green]✓ Logged in as {user.get('username')}[/green]")
            console.print(f"[dim]Email: {user.get('email')}[/dim]")
            console.print(f"[dim]User ID: {user.get('id')}[/dim]")
        elif response.status_code == 401:
            console.print("[yellow]Session expired, please login again[/yellow]")
            _clear_tokens()
        else:
            console.print(f"[yellow]Could not verify session: {response.status_code}[/yellow]")

    except httpx.ConnectError:
        console.print("[yellow]Cannot reach server (offline?)[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Error checking status: {e}[/yellow]")


@app.command("refresh")
def refresh_token() -> None:
    """
    Refresh the access token.

    Example:
        aware auth refresh
    """
    import httpx

    tokens = _load_tokens()
    if not tokens or not tokens.get("refresh_token"):
        err_console.print("[red]No refresh token available, please login[/red]")
        raise typer.Exit(1)

    try:
        response = httpx.post(
            f"{tokens['server_url']}/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
            timeout=10.0,
        )

        if response.status_code == 200:
            data = response.json()
            _save_tokens(
                data["access_token"],
                data.get("refresh_token", tokens["refresh_token"]),
                tokens["server_url"],
            )
            console.print("[green]✓ Token refreshed[/green]")
        else:
            err_console.print("[red]Refresh failed, please login again[/red]")
            _clear_tokens()
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
        raise typer.Exit(1)

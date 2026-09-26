"""
Sharing circle management commands.
"""

from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from aware.cli.commands.auth import get_auth_headers, get_server_url

app = typer.Typer(help="Sharing circle management")
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
def create_circle(
    name: str = typer.Argument(..., help="Name for the circle"),
) -> None:
    """
    Create a new sharing circle.

    Example:
        aware circle create "Family"
        aware circle create "Work Team"
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    try:
        response = httpx.post(
            f"{server_url}/circles",
            headers=headers,
            json={"name": name},
            timeout=10.0,
        )

        if response.status_code == 201:
            data = response.json()
            console.print(f"[green]✓ Circle '{name}' created[/green]")
            console.print(f"[dim]ID: {data.get('id')}[/dim]")
            console.print()
            console.print("[dim]Invite members with: aware circle invite \"" + name + "\"[/dim]")
        elif response.status_code == 409:
            err_console.print(f"[red]A circle named '{name}' already exists[/red]")
            raise typer.Exit(1)
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
        raise typer.Exit(1)


@app.command("list")
def list_circles() -> None:
    """
    List your sharing circles.

    Example:
        aware circle list
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    try:
        response = httpx.get(
            f"{server_url}/circles",
            headers=headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            circles = response.json()
            if not circles:
                console.print("[yellow]No circles yet[/yellow]")
                console.print("[dim]Create one with: aware circle create \"Name\"[/dim]")
                return

            table = Table(title="Your Circles")
            table.add_column("Name", style="cyan")
            table.add_column("Role", style="white")
            table.add_column("Members", style="white")
            table.add_column("Sharing", style="white")

            for circle in circles:
                role = "Owner" if circle.get("is_owner") else "Member"
                members = str(circle.get("member_count", 0))
                sharing = "[green]On[/green]" if circle.get("is_sharing") else "[yellow]Paused[/yellow]"

                table.add_row(
                    circle.get("name", "Unknown"),
                    role,
                    members,
                    sharing,
                )

            console.print(table)
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")


@app.command("invite")
def invite_to_circle(
    circle_name: str = typer.Argument(..., help="Circle name"),
    expires_hours: int = typer.Option(24, "--expires", "-e", help="Hours until invite expires"),
    max_uses: int = typer.Option(1, "--uses", "-u", help="Maximum number of uses"),
) -> None:
    """
    Generate an invite code for a circle.

    Example:
        aware circle invite "Family"
        aware circle invite "Family" --expires 48 --uses 5
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    try:
        response = httpx.post(
            f"{server_url}/circles/{circle_name}/invite",
            headers=headers,
            json={
                "expires_hours": expires_hours,
                "max_uses": max_uses,
            },
            timeout=10.0,
        )

        if response.status_code == 201:
            data = response.json()
            code = data.get("code")
            console.print(f"[green]✓ Invite created for '{circle_name}'[/green]")
            console.print()
            console.print(f"[bold cyan]Invite Code: {code}[/bold cyan]")
            console.print()
            console.print(f"[dim]Expires in: {expires_hours} hours[/dim]")
            console.print(f"[dim]Max uses: {max_uses}[/dim]")
            console.print()
            console.print("[dim]Share this code. Others can join with:[/dim]")
            console.print(f"[dim]  aware circle join {code}[/dim]")
        elif response.status_code == 404:
            err_console.print(f"[red]Circle '{circle_name}' not found[/red]")
            raise typer.Exit(1)
        elif response.status_code == 403:
            err_console.print(f"[red]You don't have permission to invite to this circle[/red]")
            raise typer.Exit(1)
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
        raise typer.Exit(1)


@app.command("join")
def join_circle(
    code: str = typer.Argument(..., help="Invite code"),
) -> None:
    """
    Join a circle using an invite code.

    Example:
        aware circle join ABC123
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    try:
        response = httpx.post(
            f"{server_url}/circles/join",
            headers=headers,
            json={"code": code},
            timeout=10.0,
        )

        if response.status_code == 200:
            data = response.json()
            circle_name = data.get("circle", {}).get("name", "Unknown")
            console.print(f"[green]✓ Joined circle '{circle_name}'[/green]")
            console.print()
            console.print("[dim]You can now see locations from other members.[/dim]")
            console.print("[dim]Start sharing your location with: aware track start[/dim]")
        elif response.status_code == 404:
            err_console.print("[red]Invalid or expired invite code[/red]")
            raise typer.Exit(1)
        elif response.status_code == 409:
            err_console.print("[yellow]You're already a member of this circle[/yellow]")
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
        raise typer.Exit(1)


@app.command("leave")
def leave_circle(
    circle_name: str = typer.Argument(..., help="Circle name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """
    Leave a sharing circle.

    Example:
        aware circle leave "Work Team"
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    if not force:
        if not Confirm.ask(f"Leave circle '{circle_name}'?"):
            raise typer.Exit()

    try:
        response = httpx.delete(
            f"{server_url}/circles/{circle_name}/leave",
            headers=headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            console.print(f"[green]✓ Left circle '{circle_name}'[/green]")
        elif response.status_code == 404:
            err_console.print(f"[red]Circle '{circle_name}' not found[/red]")
            raise typer.Exit(1)
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
        raise typer.Exit(1)


@app.command("pause")
def pause_sharing(
    circle_name: str = typer.Argument(..., help="Circle name"),
) -> None:
    """
    Pause sharing your location in a circle.

    Example:
        aware circle pause "Work Team"
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    try:
        response = httpx.patch(
            f"{server_url}/circles/{circle_name}/sharing",
            headers=headers,
            json={"is_sharing": False},
            timeout=10.0,
        )

        if response.status_code == 200:
            console.print(f"[yellow]⏸ Paused sharing in '{circle_name}'[/yellow]")
            console.print("[dim]Resume with: aware circle resume \"" + circle_name + "\"[/dim]")
        elif response.status_code == 404:
            err_console.print(f"[red]Circle '{circle_name}' not found[/red]")
            raise typer.Exit(1)
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
        raise typer.Exit(1)


@app.command("resume")
def resume_sharing(
    circle_name: str = typer.Argument(..., help="Circle name"),
) -> None:
    """
    Resume sharing your location in a circle.

    Example:
        aware circle resume "Work Team"
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    try:
        response = httpx.patch(
            f"{server_url}/circles/{circle_name}/sharing",
            headers=headers,
            json={"is_sharing": True},
            timeout=10.0,
        )

        if response.status_code == 200:
            console.print(f"[green]▶ Resumed sharing in '{circle_name}'[/green]")
        elif response.status_code == 404:
            err_console.print(f"[red]Circle '{circle_name}' not found[/red]")
            raise typer.Exit(1)
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
        raise typer.Exit(1)


@app.command("members")
def list_members(
    circle_name: str = typer.Argument(..., help="Circle name"),
) -> None:
    """
    List members of a circle.

    Example:
        aware circle members "Family"
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    try:
        response = httpx.get(
            f"{server_url}/circles/{circle_name}/members",
            headers=headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            members = response.json()
            if not members:
                console.print("[yellow]No members in this circle[/yellow]")
                return

            table = Table(title=f"Members of '{circle_name}'")
            table.add_column("Username", style="cyan")
            table.add_column("Role", style="white")
            table.add_column("Sharing", style="white")
            table.add_column("Last Location", style="dim")

            for member in members:
                role = "Owner" if member.get("is_owner") else "Member"
                sharing = "[green]On[/green]" if member.get("is_sharing") else "[yellow]Paused[/yellow]"
                last_loc = member.get("last_location", {})
                if last_loc:
                    loc_str = f"{last_loc.get('city', 'Unknown')}"
                else:
                    loc_str = "Unknown"

                table.add_row(
                    member.get("username", "Unknown"),
                    role,
                    sharing,
                    loc_str,
                )

            console.print(table)
        elif response.status_code == 404:
            err_console.print(f"[red]Circle '{circle_name}' not found[/red]")
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")


@app.command("delete")
def delete_circle(
    circle_name: str = typer.Argument(..., help="Circle name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """
    Delete a circle you own.

    Example:
        aware circle delete "Old Circle"
    """
    import httpx

    headers = _check_auth()
    server_url = get_server_url()

    if not force:
        console.print(f"[yellow]Warning: This will remove all members from '{circle_name}'[/yellow]")
        if not Confirm.ask("Delete this circle?"):
            raise typer.Exit()

    try:
        response = httpx.delete(
            f"{server_url}/circles/{circle_name}",
            headers=headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            console.print(f"[green]✓ Circle '{circle_name}' deleted[/green]")
        elif response.status_code == 404:
            err_console.print(f"[red]Circle '{circle_name}' not found[/red]")
            raise typer.Exit(1)
        elif response.status_code == 403:
            err_console.print("[red]You don't own this circle[/red]")
            raise typer.Exit(1)
        else:
            err_console.print(f"[red]Failed: {response.text}[/red]")
            raise typer.Exit(1)

    except httpx.ConnectError:
        err_console.print("[red]Cannot connect to server[/red]")
        raise typer.Exit(1)

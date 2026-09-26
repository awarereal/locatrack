"""
Username enumeration across social platforms.

Checks if a username exists on various social media platforms.
"""

import asyncio
from typing import Optional

import httpx
from pydantic import BaseModel

from aware.config import settings


class UsernameResult(BaseModel):
    """Result for a single platform check."""

    platform: str
    url: str
    found: bool = False
    error: Optional[str] = None


# Platform configurations
# Each platform has a URL template and optional check method
PLATFORMS = [
    {"name": "GitHub", "url": "https://github.com/{}", "method": "status"},
    {"name": "Twitter/X", "url": "https://twitter.com/{}", "method": "status"},
    {"name": "Instagram", "url": "https://instagram.com/{}", "method": "status"},
    {"name": "Facebook", "url": "https://facebook.com/{}", "method": "status"},
    {"name": "LinkedIn", "url": "https://linkedin.com/in/{}", "method": "status"},
    {"name": "TikTok", "url": "https://tiktok.com/@{}", "method": "status"},
    {"name": "YouTube", "url": "https://youtube.com/@{}", "method": "status"},
    {"name": "Reddit", "url": "https://reddit.com/user/{}", "method": "status"},
    {"name": "Pinterest", "url": "https://pinterest.com/{}", "method": "status"},
    {"name": "Tumblr", "url": "https://{}.tumblr.com", "method": "status"},
    {"name": "Medium", "url": "https://medium.com/@{}", "method": "status"},
    {"name": "Twitch", "url": "https://twitch.tv/{}", "method": "status"},
    {"name": "SoundCloud", "url": "https://soundcloud.com/{}", "method": "status"},
    {"name": "Spotify", "url": "https://open.spotify.com/user/{}", "method": "status"},
    {"name": "Dribbble", "url": "https://dribbble.com/{}", "method": "status"},
    {"name": "Behance", "url": "https://behance.net/{}", "method": "status"},
    {"name": "DeviantArt", "url": "https://deviantart.com/{}", "method": "status"},
    {"name": "Flickr", "url": "https://flickr.com/people/{}", "method": "status"},
    {"name": "Vimeo", "url": "https://vimeo.com/{}", "method": "status"},
    {"name": "Snapchat", "url": "https://snapchat.com/add/{}", "method": "status"},
    {"name": "Telegram", "url": "https://t.me/{}", "method": "status"},
    {"name": "Discord", "url": "https://discord.com/users/{}", "method": "status"},  # Won't work for usernames
    {"name": "Steam", "url": "https://steamcommunity.com/id/{}", "method": "status"},
    {"name": "Product Hunt", "url": "https://producthunt.com/@{}", "method": "status"},
    {"name": "Quora", "url": "https://quora.com/profile/{}", "method": "status"},
    {"name": "GitLab", "url": "https://gitlab.com/{}", "method": "status"},
    {"name": "Bitbucket", "url": "https://bitbucket.org/{}", "method": "status"},
    {"name": "NPM", "url": "https://npmjs.com/~{}", "method": "status"},
    {"name": "PyPI", "url": "https://pypi.org/user/{}", "method": "status"},
    {"name": "Hacker News", "url": "https://news.ycombinator.com/user?id={}", "method": "status"},
]


async def check_platform(
    client: httpx.AsyncClient,
    platform: dict,
    username: str,
    timeout: float,
) -> UsernameResult:
    """
    Check if a username exists on a single platform.

    Args:
        client: HTTP client to use
        platform: Platform configuration dict
        username: Username to check
        timeout: Request timeout in seconds

    Returns:
        UsernameResult with found status
    """
    url = platform["url"].format(username)

    try:
        response = await client.get(
            url,
            timeout=timeout,
            follow_redirects=True,
        )

        # Different platforms return different status codes
        # 200 = found, 404 = not found, 3xx redirects to login = not found
        found = response.status_code == 200

        # Some platforms return 200 but with "not found" page
        # We could check response content, but that's fragile
        # For now, trust status code

        return UsernameResult(
            platform=platform["name"],
            url=url,
            found=found,
        )

    except httpx.TimeoutException:
        return UsernameResult(
            platform=platform["name"],
            url=url,
            found=False,
            error="Timeout",
        )
    except httpx.RequestError as e:
        return UsernameResult(
            platform=platform["name"],
            url=url,
            found=False,
            error=str(e),
        )
    except Exception as e:
        return UsernameResult(
            platform=platform["name"],
            url=url,
            found=False,
            error=f"Error: {e}",
        )


async def search_username(
    username: str,
    timeout: float = 5.0,
    platforms: list[dict] | None = None,
) -> list[UsernameResult]:
    """
    Search for a username across multiple platforms.

    Args:
        username: Username to search for
        timeout: Timeout per platform in seconds
        platforms: Optional list of platform configs (uses defaults if None)

    Returns:
        List of UsernameResult for each platform
    """
    if platforms is None:
        platforms = PLATFORMS

    # Common headers to look like a browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    # Create semaphore to limit concurrency
    semaphore = asyncio.Semaphore(settings.username_check_concurrency)

    async def check_with_semaphore(platform: dict) -> UsernameResult:
        async with semaphore:
            return await check_platform(client, platform, username, timeout)

    async with httpx.AsyncClient(headers=headers) as client:
        tasks = [check_with_semaphore(p) for p in platforms]
        results = await asyncio.gather(*tasks)

    return list(results)

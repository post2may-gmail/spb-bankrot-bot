from __future__ import annotations

import httpx

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SpbBankrotBot/1.0; +https://github.com/)"
        " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def make_client(timeout: float = 30.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        timeout=httpx.Timeout(timeout, connect=15.0),
        follow_redirects=True,
    )

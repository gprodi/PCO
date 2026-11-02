"""Client HTTP commun : User-Agent identifié, délais, relances exponentielles sur 429/5xx."""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

USER_AGENT = "MicroForge-collecte/0.1 (projet pédagogique Simplon ; contact via GitHub gprodi/PCO)"


def make_client(timeout: float = 20.0, **kwargs) -> httpx.Client:
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    return httpx.Client(timeout=timeout, headers=headers, follow_redirects=True, **kwargs)


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


http_retry = retry(
    retry=retry_if_exception(_retryable),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)

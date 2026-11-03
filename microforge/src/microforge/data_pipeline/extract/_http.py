"""Client HTTP commun : User-Agent identifié, délais, relances sur 429/5xx.

Le délai de relance suit l'en-tête ``Retry-After`` quand le serveur le donne (secondes ou date HTTP,
plafonné à 120 s), sinon un recul exponentiel 1 → 30 s.
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx
from tenacity import RetryCallState, retry, retry_if_exception, stop_after_attempt, wait_exponential

# En-tête HTTP : ASCII obligatoire (httpx refuse « é » -> toute requête réelle échouait).
USER_AGENT = "MicroForge-collecte/0.2 (projet pedagogique Simplon; +https://github.com/gprodi/PCO)"


def make_client(timeout: float = 20.0, **kwargs) -> httpx.Client:
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    return httpx.Client(timeout=timeout, headers=headers, follow_redirects=True, **kwargs)


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


_backoff = wait_exponential(multiplier=1, min=1, max=30)
MAX_RETRY_AFTER_S = 120.0


def retry_after_seconds(value: str | None) -> float | None:
    """« 7 » ou « Wed, 21 Oct 2026 07:28:00 GMT » -> secondes à attendre (None si illisible)."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return min(float(value), MAX_RETRY_AFTER_S)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, min((when - datetime.now(UTC)).total_seconds(), MAX_RETRY_AFTER_S))


def wait_retry_after(state: RetryCallState) -> float:
    exc = state.outcome.exception() if state.outcome else None
    if isinstance(exc, httpx.HTTPStatusError):
        delay = retry_after_seconds(exc.response.headers.get("Retry-After"))
        if delay is not None:
            return delay
    return _backoff(state)


http_retry = retry(
    retry=retry_if_exception(_retryable),
    wait=wait_retry_after,
    stop=stop_after_attempt(4),
    reraise=True,
)

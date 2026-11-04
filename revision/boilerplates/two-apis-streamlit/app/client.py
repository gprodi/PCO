"""Appels aux deux API ; toute erreur réseau devient une ``ApiError`` lisible."""

import httpx

from common.settings import get_settings


class ApiError(RuntimeError):
    pass


def _call(method: str, url: str, **kwargs) -> dict | list:
    headers = {"X-API-Key": get_settings().api_key}
    try:
        r = httpx.request(method, url, headers=headers, timeout=10, **kwargs)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as exc:
        raise ApiError(f"{url} a répondu {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise ApiError(f"{url} injoignable ({type(exc).__name__})") from exc


def predict(texte: str) -> dict:
    return _call("POST", f"{get_settings().ia_url}/predict", json={"texte": texte})


def save(texte: str, sentiment: str, score: float) -> dict:
    payload = {"texte": texte, "sentiment": sentiment, "score": score}
    return _call("POST", f"{get_settings().data_url}/avis", json=payload)


def latest(limit: int = 10) -> list:
    return _call("GET", f"{get_settings().data_url}/avis", params={"limit": limit})

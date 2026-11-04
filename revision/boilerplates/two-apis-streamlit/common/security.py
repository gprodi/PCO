"""Clé d'API partagée entre services (en-tête X-API-Key), comparée à temps constant."""

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from common.settings import get_settings


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if x_api_key is None or not secrets.compare_digest(x_api_key, get_settings().api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Clé d'API invalide")

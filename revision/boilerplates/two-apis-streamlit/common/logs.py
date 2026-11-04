"""Journaux loguru : lisibles en développement, JSON (une ligne par événement) en production."""

import sys

from loguru import logger

from common.settings import get_settings


def setup_logging(service: str) -> None:
    logger.remove()
    logger.add(sys.stderr, serialize=get_settings().log_json, level="INFO")
    logger.configure(extra={"service": service})

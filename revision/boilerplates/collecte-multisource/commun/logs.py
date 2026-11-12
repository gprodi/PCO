"""Journaux loguru : lisibles en développement, JSON en production (APP_LOG_JSON=1)."""

import sys

from loguru import logger


def configurer(json: bool = False, niveau: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stderr, level=niveau, serialize=json, backtrace=False, diagnose=False)

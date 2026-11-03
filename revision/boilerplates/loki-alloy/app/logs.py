"""loguru en JSON : une ligne par événement, que Loki sait découper."""

import os
import sys

from loguru import logger


def setup_logging(sink=sys.stdout) -> None:
    logger.remove()
    logger.add(sink, serialize=True, level=os.environ.get("LOG_LEVEL", "INFO"), backtrace=False, diagnose=False)

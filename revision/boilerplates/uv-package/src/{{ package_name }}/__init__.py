"""Utilitaires de texte."""

from importlib.metadata import PackageNotFoundError, version

from .core import slugify

try:
    __version__ = version(__name__.replace("_", "-"))
except PackageNotFoundError:  # exécuté depuis les sources, sans installation
    __version__ = "0.0.0"

__all__ = ["__version__", "slugify"]

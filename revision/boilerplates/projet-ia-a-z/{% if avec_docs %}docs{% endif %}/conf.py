"""Configuration Sphinx : uv run --group docs sphinx-build docs docs/_build/html"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

project = "Assistant IA"
language = "fr"
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
]
myst_fence_as_directive = ["mermaid"]
autodoc_typehints = "description"
autodoc_mock_imports = ["pyspark", "prefect", "langfuse"]
html_theme = "furo"
exclude_patterns = ["_build"]

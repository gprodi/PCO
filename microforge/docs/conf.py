"""Configuration Sphinx (cours « IA DOCS Sphinx ») : Furo + MyST (Markdown) + Mermaid + autodoc."""

project = "MicroForge"
author = "Gaël Prodi"
language = "fr"
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
]
myst_enable_extensions = ["colon_fence", "deflist", "tasklist"]
myst_fence_as_directive = ["mermaid"]
myst_heading_anchors = 3
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
html_theme = "furo"
html_title = "MicroForge — documentation"
exclude_patterns = ["_build"]
suppress_warnings = ["myst.header", "myst.xref_missing"]

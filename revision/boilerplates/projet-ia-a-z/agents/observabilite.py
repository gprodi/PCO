"""Traces Langfuse : chaque nœud, sa durée et ses appels, quand les clés Langfuse sont définies.

Variables : LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST (http://localhost:3000 en local).
Paquet : ``uv sync --extra langfuse``. Sans clés ni paquet : aucune trace, rien ne casse.
"""

import os
from typing import Any

from loguru import logger


def config_execution(session: str | None = None, utilisateur: str | None = None) -> dict[str, Any]:
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return {}
    try:
        from langfuse.langchain import CallbackHandler
    except ImportError:
        logger.warning("Clés Langfuse présentes mais paquet absent : uv sync --extra langfuse")
        return {}
    metadonnees = {"langfuse_session_id": session, "langfuse_user_id": utilisateur}
    return {"callbacks": [CallbackHandler()], "metadata": {k: v for k, v in metadonnees.items() if v}}

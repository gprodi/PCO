"""Passerelle vers les modèles de langage : Ollama (local) d'abord, Gemini (offre gratuite) ensuite.

Les deux exposent l'API compatible OpenAI (``/chat/completions``, ``/embeddings``) : un seul client.
Aucune API payante. Si aucun fournisseur ne répond : ``LLMIndisponible`` (l'appelant se replie).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from loguru import logger
from pydantic import BaseModel, ValidationError

from commun.config import Settings

_PENSEE = re.compile(r"<think>.*?</think>", re.DOTALL)


class LLMIndisponible(Exception):
    """Aucun fournisseur n'a répondu."""


@dataclass(frozen=True)
class Fournisseur:
    nom: str
    url: str
    cle: str
    modele: str
    modele_embed: str


@dataclass(frozen=True)
class Generation:
    texte: str
    fournisseur: str


class Passerelle:
    def __init__(
        self,
        fournisseurs: list[Fournisseur],
        client: httpx.Client | None = None,
        timeout: float = 60.0,
        suivi: Callable[[str, str], None] | None = None,
    ) -> None:
        self.fournisseurs = fournisseurs
        self.client = client or httpx.Client(timeout=timeout)
        #: appelé avec (fournisseur, "ok" | "echec") : métriques Prometheus
        self.suivi = suivi or (lambda _f, _r: None)

    @classmethod
    def depuis_reglages(cls, s: Settings, client: httpx.Client | None = None, **options) -> "Passerelle":
        fournisseurs = [Fournisseur("ollama", s.ollama_url, "ollama", s.ollama_model, s.ollama_embed_model)]
        if s.gemini_api_key:
            fournisseurs.append(
                Fournisseur("gemini", s.gemini_url, s.gemini_api_key, s.gemini_model, s.gemini_embed_model)
            )
        return cls(fournisseurs, client, s.llm_timeout_s, **options)

    def _post(self, f: Fournisseur, chemin: str, corps: dict) -> dict:
        reponse = self.client.post(
            f"{f.url.rstrip('/')}{chemin}", json=corps, headers={"Authorization": f"Bearer {f.cle}"}
        )
        reponse.raise_for_status()
        return reponse.json()

    def generer(self, systeme: str, consigne: str, temperature: float = 0.2) -> Generation:
        messages = [{"role": "system", "content": systeme}, {"role": "user", "content": consigne}]
        for f in self.fournisseurs:
            try:
                donnees = self._post(
                    f, "/chat/completions", {"model": f.modele, "messages": messages, "temperature": temperature}
                )
                texte = _PENSEE.sub("", donnees["choices"][0]["message"]["content"] or "").strip()
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as erreur:
                logger.warning("{} indisponible : {}", f.nom, type(erreur).__name__)
                self.suivi(f.nom, "echec")
                continue
            self.suivi(f.nom, "ok")
            return Generation(texte, f.nom)
        raise LLMIndisponible("aucun modèle de langage n'a répondu")

    def generer_json[T: BaseModel](self, systeme: str, consigne: str, schema: type[T]) -> tuple[T, str]:
        """Réponse JSON validée par Pydantic ; une relance avec l'erreur si la première est invalide."""
        consigne_json = (
            f"{consigne}\n\nRéponds uniquement avec un objet JSON conforme à ce schéma : {schema.model_json_schema()}"
        )
        for _ in range(2):
            generation = self.generer(systeme, consigne_json, temperature=0)
            brut = generation.texte.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
            try:
                return schema.model_validate_json(brut), generation.fournisseur
            except ValidationError as erreur:
                consigne_json += f"\n\nTa réponse précédente était invalide : {erreur.errors()[:3]}. Corrige-la."
        raise LLMIndisponible("réponse JSON invalide deux fois de suite")

    def encoder(self, textes: list[str]) -> list[list[float]]:
        """Vecteurs du premier fournisseur seulement : mélanger deux modèles d'embeddings fausserait l'index."""
        f = self.fournisseurs[0]
        try:
            donnees = self._post(f, "/embeddings", {"model": f.modele_embed, "input": textes})
            return [d["embedding"] for d in sorted(donnees["data"], key=lambda d: d["index"])]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as erreur:
            raise LLMIndisponible(f"embeddings indisponibles ({type(erreur).__name__})") from erreur

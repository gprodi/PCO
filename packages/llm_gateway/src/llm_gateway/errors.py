"""Exceptions du gateway."""


class LLMError(RuntimeError):
    """Erreur générique : aucun fournisseur n'a pu répondre."""


class ProviderUnavailableError(LLMError):
    """Le fournisseur est injoignable, non configuré, ou a refusé la requête : on passe au suivant."""


class StructuredOutputError(LLMError):
    """La réponse ne respecte pas le schéma demandé."""

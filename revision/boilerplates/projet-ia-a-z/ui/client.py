"""Client de l'API d'IA pour l'interface : jetons gardés en session, renouvelés sur 401."""

from typing import Any

import httpx


class ErreurAPI(Exception):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


def _detail(reponse: httpx.Response) -> str:
    try:
        detail = reponse.json().get("detail")
    except ValueError:
        return reponse.text[:200] or f"erreur {reponse.status_code}"
    if isinstance(detail, list):  # erreurs de validation FastAPI
        return "; ".join(str(e.get("msg", e)) for e in detail)
    return str(detail)


class ClientAPI:
    def __init__(self, url: str, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(base_url=url, timeout=120)
        self.acces: str | None = None
        self.rafraichissement: str | None = None

    @property
    def connecte(self) -> bool:
        return self.acces is not None

    def _envoyer(self, methode: str, chemin: str, **options: Any) -> httpx.Response:
        try:
            return self.client.request(methode, chemin, **options)
        except httpx.HTTPError as erreur:
            raise ErreurAPI(f"API d'IA injoignable ({type(erreur).__name__})") from erreur

    def inscrire(self, email: str, mot_de_passe: str) -> None:
        reponse = self._envoyer("POST", "/auth/inscription", json={"email": email, "mot_de_passe": mot_de_passe})
        if reponse.status_code != 201:
            raise ErreurAPI(_detail(reponse), reponse.status_code)

    def connecter(self, email: str, mot_de_passe: str) -> None:
        reponse = self._envoyer("POST", "/auth/jeton", data={"username": email, "password": mot_de_passe})
        if reponse.status_code != 200:
            raise ErreurAPI(_detail(reponse), reponse.status_code)
        self._garder(reponse.json())

    def _garder(self, jetons: dict[str, str]) -> None:
        self.acces, self.rafraichissement = jetons["access_token"], jetons["refresh_token"]

    def _renouveler(self) -> bool:
        if not self.rafraichissement:
            return False
        reponse = self._envoyer("POST", "/auth/rafraichir", json={"refresh_token": self.rafraichissement})
        if reponse.status_code != 200:
            self.acces = self.rafraichissement = None
            return False
        self._garder(reponse.json())
        return True

    def poser(self, question: str, session: str | None = None) -> dict[str, Any]:
        if not self.connecte:
            raise ErreurAPI("Connectez-vous d'abord", 401)
        corps = {"question": question, "session": session}
        reponse = self._envoyer("POST", "/chat", json=corps, headers={"Authorization": f"Bearer {self.acces}"})
        if reponse.status_code == 401 and self._renouveler():
            reponse = self._envoyer("POST", "/chat", json=corps, headers={"Authorization": f"Bearer {self.acces}"})
        if reponse.status_code != 200:
            raise ErreurAPI(_detail(reponse), reponse.status_code)
        return reponse.json()

    def deconnecter(self) -> None:
        if self.rafraichissement:
            self._envoyer("POST", "/auth/deconnexion", json={"refresh_token": self.rafraichissement})
        self.acces = self.rafraichissement = None

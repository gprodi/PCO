"""Index des passages : en mémoire (par défaut) ou PostgreSQL + pgvector (HNSW, distance cosinus).

``BM25`` sert de repli lexical quand le modèle d'embeddings ne répond pas.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

from collecte.normalise import cle_titre

_MOTS = re.compile(r"[a-z0-9]+")
_VIDES = (
    "a au aux avec c ce ces cet cette d dans de des du elle elles en est et etait ete etre il ils je l la le les "
    "leur leurs m ma mais me mes moi mon n ne nous on ou par pas plus pour qu quand que quel quelle quelles quels "
    "qui quoi s sa se ses son sont sur t ta te tes toi ton tu un une vous y "
    "an and are as at be by for from how in is it of on or that the this to was were what which who with"
)
#: mots trop fréquents pour départager les passages (comparés sans accents)
MOTS_VIDES = frozenset(_VIDES.split())


def termes(texte: str) -> list[str]:
    """Mots utiles, pluriels ramenés au singulier (« vampires » → « vampire ») : racinisation minimale."""
    mots = [m for m in _MOTS.findall(cle_titre(texte)) if m not in MOTS_VIDES]
    return [m[:-1] if len(m) > 3 and m[-1] in "sx" else m for m in mots]


@dataclass(frozen=True)
class Passage:
    id: str
    oeuvre_id: int
    titre: str
    texte: str


def produit(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class IndexMemoire:
    """Recherche exacte par produit scalaire (vecteurs normés = cosinus). Jusqu'à quelques dizaines de milliers de passages."""

    def __init__(self) -> None:
        self.passages: list[Passage] = []
        self.vecteurs: list[list[float]] = []

    def __len__(self) -> int:
        return len(self.passages)

    def vider(self) -> None:
        self.passages, self.vecteurs = [], []

    def ajouter(self, passages: list[Passage], vecteurs: list[list[float]]) -> None:
        self.passages += passages
        self.vecteurs += vecteurs

    def chercher(self, vecteur: list[float], k: int) -> list[tuple[Passage, float]]:
        scores = [(p, produit(vecteur, v)) for p, v in zip(self.passages, self.vecteurs, strict=True)]
        return sorted(scores, key=lambda x: x[1], reverse=True)[:k]

    def vecteurs_de(self, oeuvre_id: int) -> list[list[float]]:
        return [v for p, v in zip(self.passages, self.vecteurs, strict=True) if p.oeuvre_id == oeuvre_id]


class IndexPgVector:  # pragma: no cover - testé seulement avec APP_TEST_PGVECTOR_URL (tests/test_rag.py)
    """Même interface, dans PostgreSQL : extension vector, index HNSW ``vector_cosine_ops``.

    Le nom de table est validé (expression régulière) : seules les valeurs passent en paramètres liés.
    """

    def __init__(self, url: str, dimension: int, table: str = "passage") -> None:
        from sqlalchemy import create_engine, text

        if not re.fullmatch(r"[a-z_][a-z0-9_]*", table):
            raise ValueError("nom de table invalide")
        self.text, self.table, self.dimension = text, table, dimension
        self.moteur = create_engine(url, pool_pre_ping=True)
        with self.moteur.begin() as c:
            c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            c.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS {table} (id text PRIMARY KEY, oeuvre_id integer NOT NULL, "
                    f"titre text NOT NULL, texte text NOT NULL, embedding vector({dimension}) NOT NULL)"
                )
            )
            c.execute(
                text(f"CREATE INDEX IF NOT EXISTS {table}_hnsw ON {table} USING hnsw (embedding vector_cosine_ops)")
            )

    @staticmethod
    def _litteral(vecteur: list[float]) -> str:
        return "[" + ",".join(f"{x:.7g}" for x in vecteur) + "]"

    def __len__(self) -> int:
        with self.moteur.connect() as c:
            return c.execute(self.text(f"SELECT count(*) FROM {self.table}")).scalar_one()  # noqa: S608 - nom de table validé

    def vider(self) -> None:
        with self.moteur.begin() as c:
            c.execute(self.text(f"TRUNCATE {self.table}"))

    def ajouter(self, passages: list[Passage], vecteurs: list[list[float]]) -> None:
        lignes = [
            {"id": p.id, "o": p.oeuvre_id, "t": p.titre, "x": p.texte, "e": self._litteral(v)}
            for p, v in zip(passages, vecteurs, strict=True)
        ]
        with self.moteur.begin() as c:
            c.execute(
                self.text(
                    f"INSERT INTO {self.table} (id, oeuvre_id, titre, texte, embedding) "  # noqa: S608 - nom validé
                    "VALUES (:id, :o, :t, :x, CAST(:e AS vector)) ON CONFLICT (id) DO UPDATE "
                    "SET texte = excluded.texte, embedding = excluded.embedding"
                ),
                lignes,
            )

    def chercher(self, vecteur: list[float], k: int) -> list[tuple[Passage, float]]:
        with self.moteur.connect() as c:
            lignes = c.execute(
                self.text(
                    f"SELECT id, oeuvre_id, titre, texte, 1 - (embedding <=> CAST(:v AS vector)) AS score "  # noqa: S608
                    f"FROM {self.table} ORDER BY embedding <=> CAST(:v AS vector) LIMIT :k"
                ),
                {"v": self._litteral(vecteur), "k": k},
            ).all()
        return [(Passage(r.id, r.oeuvre_id, r.titre, r.texte), float(r.score)) for r in lignes]

    def vecteurs_de(self, oeuvre_id: int) -> list[list[float]]:
        with self.moteur.connect() as c:
            lignes = c.execute(
                self.text(f"SELECT embedding::text FROM {self.table} WHERE oeuvre_id = :o"),  # noqa: S608
                {"o": oeuvre_id},
            ).scalars()
            return [[float(x) for x in ligne.strip("[]").split(",")] for ligne in lignes]


class BM25:
    """Classement lexical Okapi BM25 (k1 = 1,5 ; b = 0,75), sans dépendance."""

    def __init__(self, passages: list[Passage], k1: float = 1.5, b: float = 0.75) -> None:
        self.passages = passages
        self.k1, self.b = k1, b
        self.docs = [Counter(termes(f"{p.titre} {p.texte}")) for p in passages]
        self.longueur_moyenne = sum(sum(d.values()) for d in self.docs) / max(len(self.docs), 1)
        frequences = Counter(mot for d in self.docs for mot in d)
        n = len(self.docs)
        self.idf = {mot: math.log(1 + (n - f + 0.5) / (f + 0.5)) for mot, f in frequences.items()}

    def chercher(self, question: str, k: int) -> list[tuple[Passage, float]]:
        mots = set(termes(question))
        resultats = []
        for passage, doc in zip(self.passages, self.docs, strict=True):
            longueur = sum(doc.values())
            score = 0.0
            for terme in mots & doc.keys():
                tf = doc[terme]
                norme = tf + self.k1 * (1 - self.b + self.b * longueur / self.longueur_moyenne)
                score += self.idf[terme] * tf * (self.k1 + 1) / norme
            if score > 0:
                resultats.append((passage, score))
        return sorted(resultats, key=lambda x: x[1], reverse=True)[:k]

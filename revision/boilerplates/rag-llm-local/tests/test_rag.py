"""RAG : découpage, embeddings hors ligne, recherche, repli lexical, similaires, index des titres."""

import os

import pytest

from llm.passerelle import LLMIndisponible
from rag.decoupage import decouper
from rag.embeddings import EmbeddeurHache, EmbeddeurModele
from rag.index import BM25, IndexMemoire, Passage
from rag.moteur import MoteurRAG
from rag.titres import IndexTitres
from tests.faux import FauxLLM, passerelle

OEUVRES = [
    {"id": 1, "titre": "Dracula", "annee": 1897, "auteur": "Bram Stoker",
     "resume": "Un comte vampire quitte la Transylvanie pour Londres. Van Helsing traque le vampire."},
    {"id": 2, "titre": "Carmilla", "annee": 1872, "auteur": "Le Fanu",
     "resume": "Une vampire séduit la jeune Laura dans un château de Styrie."},
    {"id": 3, "titre": "Frankenstein", "annee": 1818, "auteur": "Mary Shelley",
     "resume": "Un savant donne vie à une créature assemblée, puis l'abandonne."},
    {"id": 4, "titre": "Le Horla", "annee": 1887, "auteur": None, "resume": None},
]  # fmt: skip


def test_decoupage_par_phrases_avec_recouvrement():
    texte = " ".join(f"Phrase numéro {i} assez longue pour compter." for i in range(30))
    passages = decouper(texte, taille=200, recouvrement=60)
    assert len(passages) > 3 and all(len(p) <= 200 for p in passages)
    assert passages[1].split(".")[0] in passages[0]  # la fin du précédent est reprise
    assert decouper("") == [] and decouper("Une seule phrase.") == ["Une seule phrase."]


def test_embeddings_haches_normes_et_deterministes():
    e = EmbeddeurHache(dimension=64)
    a, b = e.encoder(["le comte vampire", "le comte vampire"])
    assert a == b and abs(sum(x * x for x in a) - 1) < 1e-9


def test_recherche_vectorielle_et_seuil():
    moteur = MoteurRAG(EmbeddeurHache(), seuil=0.05)
    assert moteur.indexer(OEUVRES) == 4
    resultats = moteur.chercher("Quel vampire vient de Transylvanie ?", k=2)
    assert resultats[0].passage.oeuvre_id == 1 and resultats[0].mode == "vecteurs"
    assert MoteurRAG(EmbeddeurHache(), seuil=0.99).chercher("rien", 2) == []
    assert MoteurRAG.passages([OEUVRES[3]])[0].texte == "Le Horla (1887, auteur inconnu)."


class EmbeddeurEnPanne:
    nom = "panne"

    def encoder(self, textes):
        raise LLMIndisponible("arrêté")


def test_repli_lexical_sans_modele_d_embeddings():
    moteur = MoteurRAG(EmbeddeurEnPanne())
    moteur.indexer(OEUVRES)
    resultats = moteur.chercher("créature savant", k=3)
    assert resultats[0].passage.titre == "Frankenstein" and resultats[0].mode == "lexical"
    assert moteur.similaires(3) == []


class EmbeddeurCapricieux(EmbeddeurHache):
    """Indexe, puis tombe en panne au moment de la question."""

    def __init__(self):
        super().__init__()
        self.appels = 0

    def encoder(self, textes):
        self.appels += 1
        if self.appels > 1:
            raise LLMIndisponible("arrêté")
        return super().encoder(textes)


def test_repli_lexical_quand_le_modele_tombe_apres_l_indexation():
    moteur = MoteurRAG(EmbeddeurCapricieux())
    moteur.indexer(OEUVRES)
    assert moteur.chercher("vampire Styrie", 1)[0].mode == "lexical"


def test_oeuvres_similaires():
    moteur = MoteurRAG(EmbeddeurHache())
    moteur.indexer(OEUVRES)
    similaires = moteur.similaires(1, k=2)
    assert similaires[0]["titre"] == "Carmilla" and all(s["id"] != 1 for s in similaires)
    assert moteur.similaires(99) == []


def test_bm25_et_index_memoire():
    passages = [Passage("a", 1, "A", "Le chat noir de la maison"), Passage("b", 2, "B", "Un chien blanc dans la cour")]
    assert BM25(passages).chercher("chat", 5)[0][0].id == "a"
    # Question hors sujet : les mots vides (« la », « des ») ne suffisent pas à ramener un passage.
    assert BM25(passages).chercher("Quelle est la recette des crêpes ?", 5) == []
    assert BM25(passages).chercher("des chats ?", 5)[0][0].id == "a"  # pluriel ramené au singulier
    assert BM25([]).chercher("chat", 5) == []
    index = IndexMemoire()
    index.ajouter(passages, [[1.0, 0.0], [0.0, 1.0]])
    assert len(index) == 2 and index.chercher([0.0, 1.0], 1)[0][0].id == "b"
    index.vider()
    assert len(index) == 0


def test_embeddeur_modele_via_la_passerelle():
    embeddeur = EmbeddeurModele(passerelle(FauxLLM()))
    assert embeddeur.nom == "bge-m3"
    assert embeddeur.encoder(["x"]) == [[1.0, 0.0]]


def test_index_des_titres():
    titres = IndexTitres([(1, "Dracula"), (2, "Le Horla"), (3, "Emma"), (4, "Frankenstein ou le Prométhée moderne")])
    assert titres.trouver("Parle-moi de Drakula")[0] == 1  # faute de frappe tolérée
    assert titres.trouver("que se passe-t-il dans le horla ?")[0] == 2
    assert titres.trouver("Frankenstein, c'est qui ?")[0] == 4
    assert titres.trouver("Une femme et un dilemme") is None  # « emma » pas en mot entier
    assert titres.trouver("Qui a écrit Emma ?")[0] == 3
    assert titres.trouver("rien à voir") is None and len(titres) == 4


@pytest.mark.pgvector
@pytest.mark.skipif(not os.getenv("APP_TEST_PGVECTOR_URL"), reason="APP_TEST_PGVECTOR_URL non définie")
def test_index_pgvector_meme_comportement():  # pragma: no cover - PostgreSQL requis
    from rag.index import IndexPgVector

    index = IndexPgVector(os.environ["APP_TEST_PGVECTOR_URL"], dimension=512, table="passage_test")
    moteur = MoteurRAG(EmbeddeurHache(), index, seuil=0.05)
    moteur.indexer(OEUVRES)
    assert len(index) == 4
    assert moteur.chercher("vampire de Transylvanie", 1)[0].passage.oeuvre_id == 1
    assert moteur.similaires(1, 1)[0]["titre"] == "Carmilla"
    index.vider()

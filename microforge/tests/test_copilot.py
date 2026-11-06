"""Copilote RAG : corpus issu du catalogue, réponses citées, refus sous le seuil, repli sans LLM."""

from __future__ import annotations

import os
import uuid

import pytest
from llm_gateway import FakeProvider, Gateway, LLMError
from llm_gateway.vectorstore import MemoryVectorStore, PgVectorStore
from microforge.common.security import create_access_token, signing_keys
from microforge.copilot import Copilot, build_corpus, fingerprint
from microforge.copilot.service import SYSTEM, UNKNOWN
from microforge.core import get_catalog

CAT = get_catalog()


def cites_first(request) -> str:
    return "Sur l'ESP32 DevKit V1, l'I2C est sur D21 (SDA) et D22 (SCL) [1]."


def gateway(**kw) -> tuple[Gateway, FakeProvider]:
    fake = FakeProvider(embed_dim=1024, **kw)  # moins de collisions de hachage
    return Gateway.fake(fake), fake


# ---------------------------------------------------------------- corpus
def test_corpus_covers_the_whole_catalog():
    records = build_corpus(CAT)
    ids = [r.id for r in records]
    assert len(ids) == len(set(ids))
    assert {f"composant:{c}" for c in CAT.components} <= set(ids)
    assert {f"carte:{b}" for b in CAT.boards} <= set(ids)
    assert {f"projet:{t}" for t in CAT.templates} <= set(ids)
    assert {r.group for r in records} >= {"composant", "carte", "famille", "projet", "idee"}
    devkit = next(r for r in records if r.id == "carte:esp32-devkit-v1")
    assert "SDA=D21" in devkit.text and "entrée seule" in devkit.text and "ADC2" in devkit.text
    ds = next(r for r in records if r.id == "composant:ds18b20")
    assert "ESP32-C6" in ds.text and "ESP32-H2" in ds.text and "OneWire" in ds.text
    assert "gpio_" not in "".join(r.text for r in records)  # rôles traduits


def test_fingerprint_changes_with_the_catalog():
    records = build_corpus(CAT)
    fp = fingerprint(records)
    assert fp == fingerprint(build_corpus(CAT))
    records[0].text += " (modifié)"
    assert fingerprint(records) != fp


# ---------------------------------------------------------------- réponses
def test_cited_answer_from_catalog_passages():
    gw, fake = gateway(responder=cites_first)
    cop = Copilot(gw, CAT, min_score=0.2)
    ans = cop.ask("broches I2C par défaut ESP32 DevKit V1 SDA SCL")
    assert ans.mode == "llm" and ans.index == "mémoire"
    assert "carte:esp32-devkit-v1" in [s.id for s in ans.sources]
    assert ans.sources[0].n == 1 and ans.sources[0].cited
    assert not any(s.cited for s in ans.sources[1:])
    request = fake.calls[-1]
    assert request.system == SYSTEM and "DONNÉES" in request.system
    assert "[1]" in request.prompt and "Question : broches I2C" in request.prompt


def test_unknown_below_threshold_without_calling_the_llm():
    gw, fake = gateway()
    ans = Copilot(gw, CAT, min_score=0.3).ask("zxqv plorbix wug frumious")
    assert ans.mode == "inconnu" and ans.answer == UNKNOWN and ans.sources == []
    assert fake.calls == []


def test_extractive_fallback_when_no_llm():
    gw, _ = gateway(fail=True)  # chat en panne, embeddings disponibles
    ans = Copilot(gw, CAT, min_score=0.2).ask("sonde de température étanche DS18B20 1-Wire")
    assert ans.mode == "extractif" and "[1]" in ans.answer
    assert any("ds18b20" in s.id for s in ans.sources)  # composant ou projet : passages cités


def _no_embeddings(gw: Gateway) -> list[int]:
    """Gateway dont les embeddings échouent (ni Ollama ni clé Gemini) ; renvoie le compteur d'essais."""
    tries = []

    def embed(_texts):
        tries.append(1)
        raise LLMError("aucun fournisseur d'embeddings joignable")

    gw.embed = embed
    return tries


def test_keyword_search_when_no_embeddings():
    """Installation Docker sans profil « ai » : le copilote répond par mots-clés au lieu de 503."""
    gw, _ = gateway(fail=True)  # ni embeddings ni modèle de langage
    tries = _no_embeddings(gw)
    copilot = Copilot(gw, CAT, min_score=0.3)
    ans = copilot.ask("sonde de température étanche DS18B20 1-Wire")
    assert ans.index == "mots-clés" and ans.mode == "extractif"
    assert "mots-clés" in ans.answer and "[1]" in ans.answer
    assert "ds18b20" in ans.sources[0].id and ans.sources[0].score == 1.0
    # Les vecteurs ne sont pas retentés à chaque question (au plus une fois par minute).
    copilot.ask("broches I2C de l'ESP32 DevKit V1")
    assert len(tries) == 1


def test_extractive_answer_quotes_the_answering_line():
    """Sans aucun modèle : la ligne qui répond (SDA/SCL), pas le début de la fiche de la carte."""
    gw, _ = gateway(fail=True)
    _no_embeddings(gw)
    ans = Copilot(gw, CAT).ask("Broches I2C par défaut de l'ESP32 DevKit V1 ?")
    first = ans.answer.splitlines()[1]
    assert first.startswith("[1] ESP32 DevKit V1") and "SDA=D21, SCL=D22" in first


def test_keyword_search_with_a_language_model():
    """Embeddings absents mais modèle de langage joignable : réponse rédigée et citée."""
    gw, _ = gateway(responder=cites_first)
    _no_embeddings(gw)
    ans = Copilot(gw, CAT).ask("broches I2C par défaut de l'ESP32 DevKit V1")
    assert ans.index == "mots-clés" and ans.mode == "llm"
    assert any("esp32-devkit-v1" in s.id for s in ans.sources)


def test_keyword_search_unknown_words():
    gw, _ = gateway()
    _no_embeddings(gw)
    ans = Copilot(gw, CAT).ask("zxqv plorbix wug frumious")
    assert ans.mode == "inconnu" and ans.answer == UNKNOWN and ans.index == "mots-clés"


def test_stock_adds_feasible_projects_as_a_source():
    gw, _ = gateway(responder=lambda r: "Avec ton stock : station météo OLED [1].")
    stock = {"dht22": 1, "ssd1306-i2c": 1, "esp32-devkit-v1": 1}
    ans = Copilot(gw, CAT, min_score=0.2).ask("Que puis-je construire avec mon stock ?", stock)
    stock_src = next(s for s in ans.sources if s.kind == "stock")
    assert "Station météo OLED" in stock_src.excerpt


def test_index_is_built_once_and_rebuilt_when_catalog_changes():
    gw, _ = gateway()
    store = MemoryVectorStore()
    cop = Copilot(gw, CAT, store)
    n = cop.ensure_index()
    assert n == len(build_corpus(CAT))
    calls = gw.stats["embed:fake"]
    cop.ensure_index()
    Copilot(gw, CAT, store).ensure_index()  # même empreinte : rien à recalculer
    assert gw.stats["embed:fake"] == calls
    first = build_corpus(CAT)[0].id
    store.get(first).meta["fp"] = "ancienne"
    Copilot(gw, CAT, store).ensure_index()
    assert gw.stats["embed:fake"] > calls and store.get(first).meta["fp"] != "ancienne"


# ---------------------------------------------------------------- API
def _auth() -> dict:
    return {"Authorization": f"Bearer {create_access_token(1, 'user', signing_keys())}"}


def test_copilot_route(ia_client):
    url = "/v1/copilot/ask"
    assert ia_client.post(url, json={"question": "broches I2C ?"}).status_code == 401
    assert ia_client.post(url, json={"question": "?"}, headers=_auth()).status_code == 422
    r = ia_client.post(
        url,
        json={"question": "écran OLED SSD1306 I2C adresse", "inventory": {"dht22": 1}},
        headers=_auth(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] in {"llm", "inconnu"} and body["index"] == "mémoire"
    assert {"n", "id", "kind", "title", "score", "excerpt", "url", "cited"} <= set(
        body["sources"][0]
    )
    assert "intelligence artificielle" in body["notice"]  # AI Act, art. 50(1)
    assert ia_client.get("/v1/models/current", headers=_auth()).json()["copilot_index"] == "mémoire"


def test_copilot_route_without_embeddings_is_503(ia_client, monkeypatch):
    from microforge.api_ia.deps import services

    def boom(*_a, **_k):
        raise LLMError("aucun modèle d'embeddings")

    monkeypatch.setattr(services().copilot, "ask", boom)
    r = ia_client.post("/v1/copilot/ask", json={"question": "DHT22 ?"}, headers=_auth())
    assert r.status_code == 503


def test_unreachable_pgvector_falls_back_to_memory(mf_env, monkeypatch):
    from microforge.api_ia import deps
    from microforge.common import settings

    monkeypatch.setenv("MF_COPILOT_VECTOR_URL", "postgresql+psycopg://u:p@127.0.0.1:1/x")
    settings.get_settings.cache_clear()
    deps.services.cache_clear()
    assert deps.services().copilot.backend == "mémoire"


# ---------------------------------------------------------------- PostgreSQL + pgvector
PG_URL = os.environ.get("PGVECTOR_TEST_URL")


@pytest.mark.pgvector
@pytest.mark.skipif(not PG_URL, reason="PGVECTOR_TEST_URL non défini (base PostgreSQL + pgvector)")
def test_copilot_on_pgvector_reindexes_when_embedding_model_changes():
    store = PgVectorStore(PG_URL, f"mf_{uuid.uuid4().hex[:10]}")
    try:
        gw, _ = gateway(responder=cites_first)
        cop = Copilot(gw, CAT, store, min_score=0.2)
        ans = cop.ask("broches I2C par défaut ESP32 DevKit V1 SDA SCL")
        assert ans.index == "pgvector" and store.dimension() == 1024
        assert "carte:esp32-devkit-v1" in [s.id for s in ans.sources]
        # Nouveau modèle d'embeddings (autre dimension) : réindexation automatique
        other = Gateway.fake(FakeProvider(embed_dim=128, responder=cites_first))
        ans2 = Copilot(other, CAT, store, min_score=0.2).ask("broches I2C ESP32 DevKit V1")
        assert store.dimension() == 128 and ans2.sources
        assert len(store) == len(build_corpus(CAT))
    finally:
        store.reset()
        store.engine.dispose()

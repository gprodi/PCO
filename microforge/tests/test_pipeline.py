"""Tests du pipeline E1 : extracteurs (5 types de sources), règles C3, agrégation, import, purge."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from microforge.data_pipeline.aggregate.aggregate import (
    Aggregator,
    guess_category,
    load_raw,
    write_outputs,
)
from microforge.data_pipeline.aggregate.rules import (
    clean_text,
    normalize_date,
    normalize_interfaces,
    normalize_manufacturer,
    normalize_mpn,
    normalize_package,
    parse_number,
    parse_stock,
    parse_voltage_range,
    to_eur,
)
from microforge.data_pipeline.extract.db_jlcparts import JlcpartsExtractor
from microforge.data_pipeline.extract.file_arduino_index import ArduinoIndexExtractor, version_key
from microforge.data_pipeline.extract.file_fritzing import FritzingExtractor
from microforge.data_pipeline.extract.rest_digikey import DigiKeyExtractor
from microforge.data_pipeline.extract.rest_fx import FrankfurterExtractor
from microforge.data_pipeline.extract.rest_github import GitHubLibrariesExtractor
from microforge.data_pipeline.extract.rest_mouser import MouserExtractor
from microforge.data_pipeline.extract.scrape_shop import (
    ShopScraper,
    load_shop_config,
    parse_listing,
)
from sqlmodel import Session, SQLModel, create_engine, select

FIX = Path(__file__).parent / "fixtures" / "pipeline"


def fixture_json(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# ------------------------------------------------------------------ règles C3
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3V3", (3.3, 3.3)),
        ("3.3V", (3.3, 3.3)),
        ("3,3 V", (3.3, 3.3)),
        ("2.7V ~ 5.5V", (2.7, 5.5)),
        ("3.3-5V", (3.3, 5.0)),
        ("5 VDC", (5.0, 5.0)),
        ("1800mV", (1.8, 1.8)),
        (None, None),
        ("n/a", None),
    ],
)
def test_parse_voltage_range(text, expected):
    assert parse_voltage_range(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3,50 €", 3.5),
        ("1 234,50", 1234.5),
        ("1,234.50", 1234.5),
        ("1.234,50 €", 1234.5),
        ("$0.12", 0.12),
        (7, 7.0),
        ("gratuit", None),
        (None, None),
    ],
)
def test_parse_number(text, expected):
    assert parse_number(text) == expected


def test_stock_text_and_fx_and_misc():
    assert parse_stock("1 234 En stock") == 1234
    assert parse_stock("Rupture") == 0
    assert parse_stock(None) is None
    assert to_eur(10.0, "USD", {"USD": 0.9259}) == 9.259
    assert to_eur(10.0, "EUR", {"EUR": 1.0}) == 10.0
    assert to_eur(10.0, "JPY", {"EUR": 1.0}) is None
    assert clean_text("<b>Capteur</b>&nbsp;  DHT22 ") == "Capteur DHT22"
    assert normalize_mpn(" am2302-tr ") == "AM2302"
    assert normalize_manufacturer("ESPRESSIF SYSTEMS (SHANGHAI) CO., LTD.") == "Espressif"
    assert normalize_manufacturer("Acme Widgets Co., Ltd.") == "Acme Widgets"
    assert normalize_interfaces("Digital, I²C / IIC, analog out") == "I2C,ADC,GPIO"
    assert normalize_package("DIP8") == "DIP-8"
    assert normalize_package("Plugin") == "MODULE"
    assert normalize_date("30/10/2026").startswith("2026-10-30")
    assert normalize_date("pas une date") is None
    assert guess_category("Display Modules", None) == "afficheur"
    assert version_key("1.10.2") > version_key("1.9.0")


# ------------------------------------------------------------------ REST
def test_digikey_extractor(tmp_path):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "abc"})
        assert req.headers["X-DIGIKEY-Locale-Currency"] == "EUR"
        assert req.headers["Authorization"] == "Bearer abc"
        return httpx.Response(200, json=fixture_json("digikey_search.json"))

    records, manifest = DigiKeyExtractor(
        out_dir=tmp_path,
        client_id="id",
        client_secret="secret",
        keywords=["DHT22"],
        http=mock_client(handler),
    ).run()
    assert manifest.status == "success" and manifest.rows == 2
    assert records[0]["mpn"] == "AM2302" and records[0]["supply_text"] == "3.3V ~ 5.5V"
    saved = json.loads((next(tmp_path.glob("digikey/*/manifest.json"))).read_text())
    assert saved["rows"] == 2 and "client_secret" not in saved["params"]


def test_digikey_without_credentials_fails_cleanly(tmp_path, monkeypatch):
    monkeypatch.delenv("DIGIKEY_CLIENT_ID", raising=False)
    monkeypatch.delenv("DIGIKEY_CLIENT_SECRET", raising=False)
    _, manifest = DigiKeyExtractor(out_dir=tmp_path).run()
    assert manifest.status == "failed" and "DIGIKEY" in manifest.message


def test_mouser_extractor_and_quota_retry(tmp_path, monkeypatch):
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "quota"})
        return httpx.Response(200, json=fixture_json("mouser_search.json"))

    from tenacity import wait_none

    monkeypatch.setattr(MouserExtractor._search.retry, "wait", wait_none())  # pas d'attente réelle
    records, manifest = MouserExtractor(
        out_dir=tmp_path, api_key="k", keywords=["HC-SR04"], delay_s=0, http=mock_client(handler)
    ).run()
    assert manifest.status == "success" and calls["n"] == 2
    assert records[0]["price"] == "3,50 €" and records[0]["stock"].strip() == "1 234"


def test_github_and_fx_extractors(tmp_path):
    gh = mock_client(lambda r: httpx.Response(200, json=fixture_json("github_search.json")))
    records, _ = GitHubLibrariesExtractor(
        out_dir=tmp_path, libraries=["DHT sensor library"], http=gh
    ).run()
    assert records[0]["stars"] == 1900 and records[0]["license"] == "MIT"
    fx = mock_client(lambda r: httpx.Response(200, json=fixture_json("fx.json")))
    rates, _ = FrankfurterExtractor(out_dir=tmp_path, http=fx).run()
    by_cur = {r["currency"]: r["eur_per_unit"] for r in rates}
    assert by_cur["EUR"] == 1.0 and abs(by_cur["USD"] - 1 / 1.08) < 1e-6


# ------------------------------------------------------------------ fichiers
def test_arduino_index_keeps_latest_and_skips_corrupted(tmp_path):
    records, _manifest = ArduinoIndexExtractor(
        out_dir=tmp_path, path=str(FIX / "library_index.json")
    ).run()
    by_name = {r["name"]: r for r in records}
    assert set(by_name) == {"DHT sensor library", "Adafruit SSD1306"}
    assert by_name["DHT sensor library"]["version"] == "1.4.10"
    assert by_name["DHT sensor library"]["includes"] == ["DHT.h", "DHT_U.h"]


def test_fritzing_parses_and_ignores_broken(tmp_path):
    records, manifest = FritzingExtractor(out_dir=tmp_path, path=str(FIX)).run()
    assert manifest.status == "success"
    assert [c["name"] for c in records[0]["connectors"]] == ["VCC", "DATA", "GND"]
    _, failed = FritzingExtractor(out_dir=tmp_path, path=str(tmp_path / "absent")).run()
    assert failed.status == "failed"


# ------------------------------------------------------------------ scraping
def test_parse_listing():
    cfg = load_shop_config("exemple")
    parts = parse_listing(
        (FIX / "shop_listing.html").read_text(encoding="utf-8"),
        cfg,
        "https://boutique-exemple.fr/recherche?q=dht",
    )
    assert len(parts) == 2
    assert parts[0].url == "https://boutique-exemple.fr/p/dht22.html"
    assert parse_number(parts[0].price) == 6.9 and parse_stock(parts[1].stock) == 0


def test_scraper_respects_robots_and_archives_html(tmp_path):
    html = (FIX / "shop_listing.html").read_text(encoding="utf-8")
    client = mock_client(lambda r: httpx.Response(200, text=html))
    records, manifest = ShopScraper(
        out_dir=tmp_path,
        shop="exemple",
        queries=["dht22"],
        robots_txt="User-agent: *\nAllow: /\n",
        http=client,
    ).run()
    assert manifest.status == "success" and len(records) == 2
    assert list(tmp_path.glob("shop/*/html/*.html"))
    blocked, _ = ShopScraper(
        out_dir=tmp_path,
        shop="exemple",
        queries=["dht22"],
        robots_txt="User-agent: *\nDisallow: /\n",
        http=client,
    ).run()
    assert blocked == []


# ------------------------------------------------------------------ base de données (C2)
@pytest.fixture
def jlc_db(tmp_path) -> Path:
    path = tmp_path / "cache.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE categories (id INTEGER PRIMARY KEY, category TEXT, subcategory TEXT);
        CREATE TABLE manufacturers (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE components (lcsc INTEGER PRIMARY KEY, category_id INTEGER, mfr TEXT, package TEXT,
            joints INTEGER, manufacturer_id INTEGER, basic INTEGER, description TEXT, datasheet TEXT,
            stock INTEGER, price TEXT, last_update INTEGER, extra TEXT, flag INTEGER, last_on_stock INTEGER, preferred INTEGER);
        INSERT INTO categories VALUES (1, 'Sensors', 'Temperature and Humidity Sensor'), (2, 'Resistors', 'Chip Resistor - Surface Mount'),
                                      (3, 'Optoelectronics', 'OLED Display');
        INSERT INTO manufacturers VALUES (1, 'Aosong(Guangzhou) Elec'), (2, 'UNI-ROYAL');
        INSERT INTO components (lcsc, category_id, mfr, package, manufacturer_id, basic, description, datasheet, stock, price) VALUES
          (12345, 1, 'AM2302', 'Plugin', 1, 0, 'Humidity sensor DHT22', 'https://x/ds.pdf', 500, '[{"qFrom":1,"qTo":9,"price":3.2}]'),
          (12346, 1, 'AM2302', 'Plugin', 1, 0, 'Humidity sensor DHT22 (bulk)', '', 50, '[{"qFrom":1,"qTo":9,"price":3.0}]'),
          (22222, 2, '0603WAF1002T5E', '0603', 2, 1, '10k resistor', '', 999999, '[{"qFrom":100,"price":0.0005}]'),
          (33333, 3, 'UG-2864', 'Module', NULL, 0, 'OLED 0.96 128x64', '', 120, 'pas du json');
        CREATE INDEX idx_components_cat_stock ON components(category_id, stock);
        """
    )
    conn.commit()
    conn.close()
    return path


def test_jlcparts_sql_extraction(tmp_path, jlc_db):
    records, _manifest = JlcpartsExtractor(out_dir=tmp_path, path=str(jlc_db), min_stock=100).run()
    refs = {r["source_ref"] for r in records}
    assert refs == {"C12345", "C33333"}  # filtre stock + sous-catégories ; résistance exclue
    oled = next(r for r in records if r["source_ref"] == "C33333")
    assert oled["price"] is None and oled["manufacturer"] is None  # LEFT JOIN + JSON corrompu


def test_jlcparts_best_offer_window_and_plan(jlc_db):
    from microforge.data_pipeline.extract.db_jlcparts import read_sql

    conn = sqlite3.connect(jlc_db)
    rows = conn.execute(read_sql("jlcparts_best_offer.sql")).fetchall()
    best = {r[1]: r[0] for r in rows}
    assert best["AM2302"] == 12345  # plus de stock
    ex = JlcpartsExtractor(path=str(jlc_db))
    ex.setup()
    plan = " ".join(ex.explain())
    ex.teardown()
    assert "components" in plan.lower() or "c" in plan.lower()


def test_spark_extractor_skips_without_pyspark(tmp_path):
    pytest.importorskip("polars")
    from microforge.data_pipeline.extract.bigdata_spark import SparkCategoryStats, export_parquet

    sqlite_path = tmp_path / "db.sqlite3"
    conn = sqlite3.connect(sqlite_path)
    conn.executescript(
        "CREATE TABLE categories (id INTEGER, category TEXT, subcategory TEXT);"
        "CREATE TABLE components (lcsc INTEGER, category_id INTEGER, mfr TEXT, package TEXT, stock INTEGER, price TEXT);"
        "INSERT INTO categories VALUES (1, 'Sensors', 'T');"
        "INSERT INTO components VALUES (1, 1, 'A', 'DIP-8', 10, '[{\"price\": 1.0}]'), (2, 1, 'B', '0603', 0, '[]');"
    )
    conn.commit()
    conn.close()
    assert export_parquet(sqlite_path, tmp_path / "pq", batch_size=1) == 2
    assert len(list((tmp_path / "pq").glob("*.parquet"))) == 2
    try:
        import pyspark  # noqa: F401
    except ImportError:
        _, manifest = SparkCategoryStats(out_dir=tmp_path, parquet_dir=str(tmp_path / "pq")).run()
        assert manifest.status == "failed" and "pyspark" in manifest.message


# ------------------------------------------------------------------ agrégation
def raw_records(tmp_path, jlc_db) -> tuple[list[dict], dict]:
    def dk(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "abc"})
        return httpx.Response(200, json=fixture_json("digikey_search.json"))

    raw = tmp_path / "raw"
    DigiKeyExtractor(
        out_dir=raw, client_id="i", client_secret="s", keywords=["x"], http=mock_client(dk)
    ).run()
    MouserExtractor(
        out_dir=raw,
        api_key="k",
        keywords=["x"],
        delay_s=0,
        http=mock_client(lambda r: httpx.Response(200, json=fixture_json("mouser_search.json"))),
    ).run()
    JlcpartsExtractor(out_dir=raw, path=str(jlc_db)).run()
    FrankfurterExtractor(
        out_dir=raw, http=mock_client(lambda r: httpx.Response(200, json=fixture_json("fx.json")))
    ).run()
    ShopScraper(
        out_dir=raw,
        shop="exemple",
        queries=["dht"],
        robots_txt="",
        http=mock_client(
            lambda r: httpx.Response(200, text=(FIX / "shop_listing.html").read_text())
        ),
    ).run()
    ArduinoIndexExtractor(out_dir=raw, path=str(FIX / "library_index.json")).run()
    return load_raw(raw)


def test_aggregation_end_to_end(tmp_path, jlc_db):
    records, fx = raw_records(tmp_path, jlc_db)
    assert "USD" in fx and len(records) >= 7
    corrupted = {"source": "test", "source_ref": "x", "name": None, "mpn": None}
    negative = {"source": "test", "source_ref": "y", "name": "Truc", "stock": -5}
    components, offers, report = Aggregator(fx).run([*records, corrupted, negative])
    rep = report.to_dict()
    assert rep["rejected_by_rule"]["identite_manquante"] == 1
    assert rep["rejected_by_rule"]["stock_negatif"] == 1
    assert rep["rejected_by_rule"]["prix_invalide"] >= 2  # prix nul Mouser + JSON LCSC corrompu
    keys = {c["component_key"] for c in components}
    assert {"dht22", "hc-sr04", "ssd1306-i2c"} <= keys  # rapprochement avec le catalogue
    dht = next(c for c in components if c["component_key"] == "dht22")
    assert set(dht["sources"]) >= {"digikey", "jlcparts", "shop"}
    assert dht["manufacturer"] == "Aosong" and dht["supply_min_v"] == 3.3
    lcsc = next(o for o in offers if o["supplier"] == "LCSC")
    assert lcsc["currency_original"] == "USD" and lcsc["unit_price_eur"] < lcsc["price_original"]
    write_outputs(components, offers, report, tmp_path / "clean")
    assert (tmp_path / "clean" / "components_clean.parquet").exists()
    assert (
        json.loads((tmp_path / "clean" / "rejects_report.json").read_text())["rows_in"]
        == len(records) + 2
    )


def test_price_outliers_removed():
    agg = Aggregator({"USD": 0.9})
    recs = [
        {
            "source": "s",
            "source_ref": f"r{i}",
            "name": f"LED {i}",
            "supplier": "S",
            "price": 0.1 + i * 0.01,
            "currency": "EUR",
        }
        for i in range(10)
    ]
    recs.append(
        {
            "source": "s",
            "source_ref": "cher",
            "name": "LED dorée",
            "supplier": "S",
            "price": 999,
            "currency": "EUR",
        }
    )
    _, offers, report = agg.run(recs)
    assert report.rejected["prix_aberrant"] == 1 and all(o["unit_price_eur"] < 10 for o in offers)


# ------------------------------------------------------------------ import & purge (C4)
@pytest.fixture
def session(tmp_path):
    import microforge.api_data.db  # noqa: F401 — enregistre les tables dans la métadonnée

    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_import_clean_is_idempotent(tmp_path, jlc_db, session):
    from microforge.api_data.db import Component, IngestionRun, Library, Offer, Supplier
    from microforge.data_pipeline.load.importer import import_clean

    records, fx = raw_records(tmp_path, jlc_db)
    components, offers, _ = Aggregator(fx).run(records)
    libs, _ = ArduinoIndexExtractor(out_dir=tmp_path, path=str(FIX / "library_index.json")).run()
    import_clean(session, components, offers, libs)
    n_offers = len(session.exec(select(Offer)).all())
    import_clean(session, components, offers, libs)
    assert len(session.exec(select(Offer)).all()) == n_offers
    assert session.get(Component, "dht22").datasheet_url
    assert (
        session.exec(select(Supplier).where(Supplier.name == "LCSC")).one().collection_method
        == "base de données"
    )
    assert session.get(Library, "DHT sensor library").latest_version == "1.4.10"
    assert len(session.exec(select(IngestionRun)).all()) == 2


def test_rgpd_purge(session):
    from microforge.api_data.db import Feedback, IngestionRun, Photo, RefreshToken, User

    old = datetime.now(UTC) - timedelta(days=800)
    active = User(
        username="actif",
        email_encrypted="x",
        email_index="a",
        password_hash="h",
        last_login_at=datetime.now(UTC),
    )
    dormant = User(
        username="dormant",
        email_encrypted="x",
        email_index="b",
        password_hash="h",
        created_at=old,
        last_login_at=old,
    )
    session.add_all([active, dormant])
    session.commit()
    session.add_all(
        [
            Photo(
                user_id=active.id,
                sha256="a" * 64,
                width=1,
                height=1,
                delete_after=date.today() - timedelta(days=1),
            ),
            Photo(
                user_id=active.id,
                sha256="b" * 64,
                width=1,
                height=1,
                delete_after=date.today() + timedelta(days=10),
            ),
            Feedback(user_id=active.id, kind="correct", created_at=old),
            RefreshToken(
                jti="t1",
                user_id=active.id,
                family="f",
                expires_at=datetime.now(UTC) - timedelta(days=1),
            ),
            RefreshToken(
                jti="t2",
                user_id=active.id,
                family="f",
                expires_at=datetime.now(UTC) + timedelta(days=1),
            ),
        ]
    )
    session.commit()
    from microforge.data_pipeline.load.purge import purge

    counts = purge(session)
    assert counts == {"photos": 1, "retours": 1, "jetons": 1, "comptes": 1}
    assert session.exec(select(User)).all()[0].username == "actif"
    assert (
        session.exec(select(IngestionRun).where(IngestionRun.flow == "purge_rgpd")).one().status
        == "success"
    )


# ------------------------------------------------------------------ flow & CLI
def test_flow_and_cli(tmp_path, monkeypatch):
    from microforge.data_pipeline import flows
    from microforge.data_pipeline.cli import app
    from typer.testing import CliRunner

    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(
        flows.EXTRACTORS,
        "fx",
        lambda out_dir, **p: FrankfurterExtractor(
            out_dir=out_dir,
            http=mock_client(lambda r: httpx.Response(200, json=fixture_json("fx.json"))),
        ),
    )
    result = flows.collect_flow(
        sources={"fx": {}, "arduino_index": {"path": str(FIX / "library_index.json")}},
        raw_dir=str(tmp_path / "raw"),
        out_dir=str(tmp_path / "clean"),
    )
    assert all(r["status"] == "success" for r in result["extractions"])
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "extract",
            "arduino_index",
            "--path",
            str(FIX / "library_index.json"),
            "--raw-dir",
            str(tmp_path / "raw2"),
        ],
    )
    assert res.exit_code == 0, res.output
    res = runner.invoke(
        app,
        [
            "extract",
            "fritzing",
            "--path",
            str(tmp_path / "absent"),
            "--raw-dir",
            str(tmp_path / "raw2"),
        ],
    )
    assert res.exit_code == 1
    monkeypatch.setenv("MF_DATABASE_URL", f"sqlite:///{tmp_path / 'cli.db'}")
    from microforge.api_data import db
    from microforge.common import settings

    settings.get_settings.cache_clear()
    db.get_engine.cache_clear()
    assert runner.invoke(app, ["purge"]).exit_code == 0
    db.get_engine.cache_clear()
    settings.get_settings.cache_clear()

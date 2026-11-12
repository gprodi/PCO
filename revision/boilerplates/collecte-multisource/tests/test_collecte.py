"""Collecte : normalisation, cinq types de sources, fusion, pipeline et ligne de commande."""

import importlib.util
import shutil
from pathlib import Path

import httpx
import pytest

from collecte import normalise, sources
from collecte.fusion import fusionner
from collecte.modele import Enregistrement
from collecte.pipeline import executer, lire_config, preparer_sqlite

RACINE = Path(__file__).resolve().parents[1]
EXEMPLES = RACINE / "donnees_exemple"


def test_normalisation_des_textes_dates_et_notes():
    assert normalise.texte("  <b>Le&nbsp;Horla</b>\n ") == "Le Horla"
    assert normalise.texte("   ") is None and normalise.texte(None) is None
    assert normalise.cle_titre("L'Étrange Cas du Dr Jekyll !") == "etrange cas du dr jekyll"
    assert normalise.cle_titre("Le") == "le"
    assert normalise.date_iso("1897") == "1897-01-01"
    assert normalise.date_iso(1897.0) == "1897-01-01"
    assert normalise.date_iso("1897-05-26") == "1897-05-26"
    assert normalise.date_iso("26/05/1897") == "1897-05-26"
    assert normalise.date_iso("1897-13-40") is None and normalise.date_iso("vers 1900") is None
    assert normalise.annee("") is None
    assert normalise.note_sur_10("87%", echelle=100) == 8.7
    assert normalise.note_sur_10("7,5") == 7.5
    assert normalise.note_sur_10("12") is None and normalise.note_sur_10("n/a") is None
    assert normalise.dans_le_theme("Horreur|Gothique", {"épouvante", "gothique"})
    assert not normalise.dans_le_theme("Roman sentimental", {"horreur"})
    assert not normalise.dans_le_theme(None, {"horreur"})


def transport(routes: dict[str, list[httpx.Response]]) -> httpx.Client:
    def repondre(requete: httpx.Request) -> httpx.Response:
        file = routes[requete.url.path]
        return file.pop(0) if len(file) > 1 else file[0]

    return httpx.Client(transport=httpx.MockTransport(repondre), base_url="https://api.test")


def test_api_paginee_avec_reprise_sur_429():
    page = {"docs": [{"title": "Dracula", "first_publish_year": 1897, "author_name": ["Bram Stoker", "x"], "key": "/works/OL1"},
                     {"title": None}]}  # fmt: skip
    client = transport({"/search.json": [
        httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(200, json=page), httpx.Response(200, json={"docs": []}),
    ]})  # fmt: skip
    attentes: list[float] = []
    resultat = sources.depuis_api(
        client, "https://api.test/search.json", {"titre": "title", "annee": "first_publish_year", "auteur": "author_name", "id:openlibrary": "key"},
        liste="docs", pages=3, genre_par_defaut="Horreur", pause=attentes.append,
    )  # fmt: skip
    assert attentes == [3.0]
    assert [(e.titre, e.annee, e.auteur, e.genre, e.ids) for e in resultat] == [
        ("Dracula", 1897, "Bram Stoker", "Horreur", {"openlibrary": "/works/OL1"})
    ]


def test_attente_retry_after_date_ou_absente():
    date_http = httpx.Response(503, headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})
    assert sources._attente(date_http, 0) == 0.0
    assert sources._attente(httpx.Response(503, headers={"Retry-After": "plus tard"}), 2) == 4.0
    client = transport({"/x": [httpx.Response(500)]})
    with pytest.raises(httpx.HTTPStatusError):
        sources.obtenir(client, "https://api.test/x")


PAGE = """<table class="oeuvres">
<tr class="oeuvre"><td class="titre">Carmilla</td><td class="annee">1872</td><td class="auteur">Le Fanu</td>
<td><a class="lien" href="https://exemple.org/carmilla">fiche</a></td></tr>
<tr class="oeuvre"><td class="annee">1900</td></tr></table>"""
SELECTEURS = {"ligne": "tr.oeuvre", "titre": "td.titre", "annee": "td.annee", "auteur": "td.auteur", "url": "a.lien"}


@pytest.mark.parametrize(
    ("robots", "attendu"),
    [(httpx.Response(200, text="User-agent: *\nDisallow: /prive/"), 1), (httpx.Response(404), 1)],
)
def test_page_web_autorisee(robots, attendu):
    client = transport({"/robots.txt": [robots], "/catalogue": [httpx.Response(200, text=PAGE)]})
    lignes = sources.depuis_page_web(client, "https://api.test/catalogue", SELECTEURS, genre_par_defaut="Horreur")
    assert len(lignes) == attendu
    assert lignes[0].url == "https://exemple.org/carmilla" and lignes[0].annee == 1872


@pytest.mark.parametrize("robots", [httpx.Response(200, text="User-agent: *\nDisallow: /"), httpx.Response(503)])
def test_page_web_interdite_par_robots(robots):
    client = transport({"/robots.txt": [robots], "/catalogue": [httpx.Response(200, text=PAGE)]})
    with pytest.raises(sources.SourceInterdite):
        sources.depuis_page_web(client, "https://api.test/catalogue", SELECTEURS)


def test_csv_lu_par_polars_sans_doublon():
    colonnes = lire_config()["source"][2]["colonnes"]
    lignes = sources.depuis_csv(EXEMPLES / "catalogue.csv", colonnes)
    assert len(lignes) == 10  # 11 lignes, un doublon titre + date
    dracula = lignes[0]
    assert dracula.ids == {"ref_catalogue": "OEU-001"} and dracula.annee == 1897 and dracula.note == 8.1


def test_sql_parametre_et_seuil_de_votes(tmp_path):
    url = f"sqlite:///{tmp_path / 'base.db'}"
    preparer_sqlite(url, EXEMPLES / "base_existante.sql")
    preparer_sqlite(url, EXEMPLES / "base_existante.sql")  # déjà là : rien n'est rejoué
    requete = lire_config()["source"][3]["requete"]
    lignes = sources.depuis_sql(url, requete, params={"genre": "%horror%", "votes_min": 1000})
    titres = {e.titre for e in lignes}
    assert "Nosferatu" in titres and "Un film d'horreur confidentiel" not in titres  # 40 votes
    assert "Le Tour du monde en quatre-vingts jours" not in titres
    assert next(e for e in lignes if e.titre == "Nosferatu").ids == {"imdb": "tt0013442"}


def test_gros_volume_polars_filtre_et_dedoublonne():
    colonnes = lire_config()["source"][4]["colonnes"]
    lignes = sources.depuis_gros_volume(str(EXEMPLES / "gros_volume/*.csv"), colonnes, genres=["horror", "gothic"])
    titres = sorted(e.titre for e in lignes)
    assert titres.count("The Monk") == 1 and "Emma" not in titres and "Moby Dick" not in titres
    assert len(titres) == 5


@pytest.mark.skipif(
    importlib.util.find_spec("pyspark") is None or shutil.which("java") is None, reason="pyspark ou Java absent"
)
def test_gros_volume_spark_donne_le_meme_resultat():
    colonnes = lire_config()["source"][4]["colonnes"]
    motif = str(EXEMPLES / "gros_volume/*.csv")
    polars = sorted(e.titre for e in sources.depuis_gros_volume(motif, colonnes, genres=["horror", "gothic"]))
    spark = sorted(
        e.titre for e in sources.depuis_gros_volume(motif, colonnes, genres=["horror", "gothic"], moteur="spark")
    )
    assert spark == polars


def e(source: str, titre: str, annee: int | None, **champs) -> Enregistrement:
    return Enregistrement(source=source, titre=titre, annee=annee, **champs)


def test_fusion_par_identifiant_puis_titre_approche():
    fiches, ecartees = fusionner(
        [
            e("sql", "L'étrange cas du Dr Jekyll et de Mr Hyde", 1886, genre="Horror", note=7.9, ids={"imdb": "tt2"}),
            e("csv", "L'Étrange Cas du docteur Jekyll et de M. Hyde", 1886, genre="Horreur", resume="Utterson enquête.", ids={"ref": "OEU-6"}),
            e("gros_volume", "Jekyll (version longue)", None, ids={"ref": "OEU-6"}, auteur="R. L. Stevenson"),
            e("csv", "Orgueil et Préjugés", 1813, genre="Roman"),
            e("sql", "Nosferatu", 1922, genre="Horror"),
        ],
        priorite=["csv", "sql", "gros_volume"],
        seuil_titre=80,
        genres={"horreur", "horror"},
    )  # fmt: skip
    assert ecartees == 1
    jekyll = next(f for f in fiches if "Jekyll" in f.titre)
    assert jekyll.titre == "L'Étrange Cas du docteur Jekyll et de M. Hyde"  # csv prioritaire
    assert jekyll.note == 7.9 and jekyll.provenance["note"] == "sql"  # complété par la source suivante
    assert jekyll.auteur == "R. L. Stevenson" and jekyll.sources == ["csv", "sql", "gros_volume"]
    assert jekyll.ids == {"ref": "OEU-6", "imdb": "tt2"}
    assert [f.titre for f in fiches].count("Nosferatu") == 1


def test_fusion_sans_filtre_et_annee_completee_plus_tard():
    fiches, ecartees = fusionner(
        [e("csv", "Carmilla", None), e("sql", "Carmilla", 1872), e("web", "Carmilla", 1872)], ["csv", "sql", "web"]
    )
    assert ecartees == 0 and len(fiches) == 1 and fiches[0].annee == 1872


def config_locale() -> dict:
    config = lire_config()
    for source in config["source"]:
        source["actif"] = source["type"] in {"csv", "sql", "gros_volume"}
    return config


def test_pipeline_complet_sur_les_exemples(tmp_path: Path):
    config = config_locale()
    config["source"].append({"type": "csv", "nom": "cassee", "chemin": "absent.csv", "colonnes": {"titre": "t"}})
    config["source"].append({"type": "inconnu", "nom": "bizarre"})
    shutil.copytree(EXEMPLES, tmp_path / "donnees_exemple")
    rapport = executer(config, racine=tmp_path)
    assert rapport.par_source["api"] == "désactivée"
    assert rapport.par_source["csv"] == 10 and rapport.par_source["sql"] == 4
    assert rapport.par_source["cassee"].startswith("échec") and rapport.par_source["bizarre"].startswith("échec")
    titres = {f.titre for f in rapport.fiches}
    assert {"Dracula", "Nosferatu", "The Monk"} <= titres and "Orgueil et Préjugés" not in titres
    dracula = next(f for f in rapport.fiches if f.titre == "Dracula")
    assert set(dracula.sources) == {"csv", "sql", "gros_volume"}
    assert "fiches gardées" in rapport.resume()

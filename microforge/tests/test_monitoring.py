"""Supervision (C11 modèle, C20 application) : cohérence entre le code, Prometheus, Alertmanager,
Grafana et le compose. Les règles d'alerte elles-mêmes sont testées par promtool
(monitoring/prometheus/alerts.test.yml, job CI « monitoring »).

Défauts trouvés en lançant réellement la pile (06/11/2026), gardés ici en tests de non-régression :
- Grafana refusait de démarrer sans DISCORD_WEBHOOK_URL (point de contact Discord vide) ;
- les alertes de Prometheus n'étaient envoyées nulle part (aucun Alertmanager) ;
- la latence p95 lisait un histogramme dont le dernier seau fini est 1 s : seuil de 2 s inatteignable ;
- les compteurs de détection n'existaient qu'après la première photo (rate() aveugle) ;
- « objets hors catalogue » divisait par les seules détections reconnues.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MON = ROOT / "monitoring"
COMPOSE = ROOT / "infra" / "docker-compose.yml"
CI = ROOT.parent / ".github" / "workflows" / "ci.yml"

METRIC = re.compile(r"\b((?:mf|http)_[a-z0-9_]+)\b")


def _alert_rules() -> list[dict]:
    doc = yaml.safe_load((MON / "prometheus" / "alerts.yml").read_text(encoding="utf-8"))
    return [r for g in doc["groups"] for r in g["rules"]]


def _dashboards() -> dict[str, dict]:
    return {
        p.name: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((MON / "grafana" / "dashboards").glob("*.json"))
    }


def _dashboard_exprs() -> list[str]:
    return [
        t["expr"]
        for d in _dashboards().values()
        for panel in d["panels"]
        for t in panel.get("targets", [])
        if "expr" in t
    ]


def _exposed(text: str) -> set[str]:
    """Noms de séries qu'un /metrics peut produire (y compris les métriques à étiquettes encore vides)."""
    names = {ln.split("{")[0].split(" ")[0] for ln in text.splitlines() if ln and ln[0] != "#"}
    for name, kind in re.findall(r"^# TYPE (\S+) (\S+)$", text, flags=re.M):
        names.add(name)
        if kind == "counter":
            names.add(f"{name}_total")
        if kind == "histogram":
            names |= {f"{name}_bucket", f"{name}_sum", f"{name}_count"}
    return names


@pytest.fixture
def exposed(data_client, ia_client) -> set[str]:
    for client in (data_client, ia_client):  # une requête : l'instrumentation crée ses séries
        client.get("/health")
    return _exposed(data_client.get("/metrics").text) | _exposed(ia_client.get("/metrics").text)


def test_chaque_metrique_des_alertes_et_tableaux_existe(exposed):
    used = {
        m
        for expr in [r["expr"] for r in _alert_rules()] + _dashboard_exprs()
        for m in METRIC.findall(expr)
    }
    assert used, "aucune métrique trouvée"
    assert used - exposed == set(), f"métriques absentes des /metrics : {sorted(used - exposed)}"


def test_series_de_detection_presentes_des_le_demarrage(ia_client):
    """Sans série créée au démarrage, la première photo n'apparaît pas dans rate()."""
    text = ia_client.get("/metrics").text
    for source in ("yolo", "vlm"):
        for name in ("mf_detection_confidence_count", "mf_detections_unknown_total"):
            # Valeur quelconque : le registre Prometheus est partagé par toute la session de tests.
            assert re.search(rf'^{name}\{{source="{source}"\}} \d', text, flags=re.M), (
                name,
                source,
            )


def test_latence_sur_l_histogramme_fin(exposed):
    rules = {r["alert"]: r["expr"] for r in _alert_rules()}
    assert "http_request_duration_highr_seconds_bucket" in rules["LatenceP95Elevee"]
    assert all("http_request_duration_seconds_bucket" not in e for e in _dashboard_exprs())


def test_objets_inconnus_rapportes_a_toutes_les_detections():
    rules = {r["alert"]: r["expr"] for r in _alert_rules()}
    assert "mf_detection_confidence_count" in rules["ObjetsInconnusEnHausse"]
    assert "mf_detections_total" not in rules["ObjetsInconnusEnHausse"]


def test_alertes_documentees_et_sans_api_payante():
    for rule in _alert_rules():
        assert rule["labels"]["severity"] in {"critical", "warning", "info"}, rule["alert"]
        assert rule["annotations"]["summary"], rule["alert"]
    assert "Claude" not in (MON / "prometheus" / "alerts.yml").read_text(encoding="utf-8")


def test_chaque_alerte_a_son_test_promtool():
    tests = yaml.safe_load((MON / "prometheus" / "alerts.test.yml").read_text(encoding="utf-8"))
    tested = {a["alertname"] for t in tests["tests"] for a in t["alert_rule_test"]}
    assert tested == {r["alert"] for r in _alert_rules()}


def test_prometheus_envoie_a_alertmanager():
    conf = yaml.safe_load((MON / "prometheus" / "prometheus.yml").read_text(encoding="utf-8"))
    targets = conf["alerting"]["alertmanagers"][0]["static_configs"][0]["targets"]
    assert targets == ["alertmanager:9093"]


def test_alertmanager_meme_routage_avec_ou_sans_discord():
    base = yaml.safe_load((MON / "alertmanager" / "alertmanager.yml").read_text(encoding="utf-8"))
    discord = yaml.safe_load(
        (MON / "alertmanager" / "alertmanager-discord.yml").read_text(encoding="utf-8")
    )
    assert base["route"] | {"receiver": None} == discord["route"] | {"receiver": None}
    assert base["inhibit_rules"] == discord["inhibit_rules"]
    (receiver,) = discord["receivers"]
    (cfg,) = receiver["discord_configs"]
    assert "webhook_url" not in cfg and cfg["webhook_url_file"].startswith("/alertmanager/")
    start = (MON / "alertmanager" / "start.sh").read_text(encoding="utf-8")
    assert "alertmanager-discord.yml" in start and "alertmanager.yml" in start
    assert cfg["webhook_url_file"] in start
    # Le secret n'est jamais écrit dans le dépôt.
    for path in (MON / "alertmanager").iterdir():
        assert "discord.com/api/webhooks" not in path.read_text(encoding="utf-8")


def test_grafana_provisionne_sans_secret_obligatoire():
    sources = yaml.safe_load(
        (MON / "grafana/provisioning/datasources/datasources.yml").read_text(encoding="utf-8")
    )["datasources"]
    uids = {s["uid"] for s in sources}
    assert {s["type"] for s in sources} == {"prometheus", "loki", "alertmanager"}
    # Plus de point de contact Discord dans Grafana : vide, il empêchait Grafana de démarrer.
    assert not (MON / "grafana/provisioning/alerting").exists() or not any(
        (MON / "grafana/provisioning/alerting").glob("*.y*ml")
    )
    dashboards = _dashboards()
    assert len({d["uid"] for d in dashboards.values()}) == len(dashboards)
    for name, d in dashboards.items():
        for panel in d["panels"]:
            assert panel["datasource"]["uid"] in uids, (name, panel.get("title"))


def test_compose_et_ci_utilisent_les_memes_images():
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    am = services["alertmanager"]
    assert am["profiles"] == ["monitoring"]
    assert am["environment"] == {"DISCORD_WEBHOOK_URL": "${DISCORD_WEBHOOK_URL:-}"}
    assert "DISCORD_WEBHOOK_URL" not in services["grafana"]["environment"]
    ci_env = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]["monitoring"]["env"]
    assert ci_env["PROMETHEUS"] == services["prometheus"]["image"]
    assert ci_env["ALERTMANAGER"] == am["image"]
    assert ci_env["GRAFANA"] == services["grafana"]["image"]
    assert ci_env["LOKI"] == services["loki"]["image"]


def test_loki_alerte_sur_les_echecs_de_connexion():
    """La règle cherche le message réellement écrit par api_data, et part vers Alertmanager."""
    conf = yaml.safe_load((MON / "loki" / "loki.yml").read_text(encoding="utf-8"))
    assert conf["ruler"]["alertmanager_url"] == "http://alertmanager:9093"
    assert conf["analytics"]["reporting_enabled"] is False
    rules = yaml.safe_load((MON / "loki/rules/fake/securite.yml").read_text(encoding="utf-8"))
    (rule,) = rules["groups"][0]["rules"]
    message = re.search(r'\|= "([^"]+)"', rule["expr"]).group(1)
    auth = (ROOT / "src/microforge/api_data/routers/auth.py").read_text(encoding="utf-8")
    assert auth.count(f'"{message}') >= 2  # identifiant inconnu et mauvais mot de passe
    assert rule["expr"].endswith("> 20")
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    assert services["loki"]["command"] == "-config.file=/etc/loki/loki.yml"


def test_verifier_pile_utilisable_et_lance_par_la_ci():
    """Le script de vérification de la pile (CI « Pile complète », fumée en préproduction)."""
    import subprocess
    import sys

    script = ROOT / "infra" / "verifier_pile.py"
    out = subprocess.run(
        [sys.executable, str(script), "--help"], capture_output=True, text=True, check=True
    ).stdout
    assert "--force-brute" in out and "--grafana-password" in out
    job = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]["pile"]
    runs = "\n".join(step.get("run", "") for step in job["steps"])
    assert "verifier_pile.py --force-brute" in runs and "set -o pipefail" in runs
    assert "e2e/parcours-pwa.cjs http://localhost:5173/" in runs
    assert "--profile core --profile monitoring" in runs

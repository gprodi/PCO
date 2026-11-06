"""Vérifie la pile MicroForge lancée avec les profils « core » et « monitoring ».

    cd microforge/infra
    docker compose --profile core --profile monitoring up -d
    python3 verifier_pile.py                       # Grafana : mot de passe par défaut (change-me)
    python3 verifier_pile.py --force-brute         # + alerte « échecs de connexion » (≈ 1 à 2 min)

Bibliothèque standard seulement. Contrôles : santé des services, en-têtes de sécurité réels de la
PWA (nginx), collecte Prometheus par nom de service et liaison à Alertmanager, tableaux et sources
Grafana, journaux des conteneurs dans Loki (Alloy) avec leur niveau ; avec ``--force-brute`` :
25 mauvais mots de passe sur api_data, puis l'alerte doit arriver dans Alertmanager. Le limiteur
d'api_data (10 essais/min par adresse) doit alors être relevé (``MF_RATE_LIMIT_TOKEN`` dans
``microforge/.env``) : sinon il bloque l'essai avant la règle, ce qui est le comportement voulu.
Code de sortie 1 si un contrôle échoue ; une ligne par contrôle.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Les services sont joints en local : jamais par un proxy HTTP du poste ou de la CI.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http(url: str, data: bytes | None = None, headers: dict | None = None, timeout: float = 10):
    """(code, en-têtes, corps) ; code 0 si le service ne répond pas."""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"adresse HTTP attendue : {url}")
    req = urllib.request.Request(url, data=data, headers=headers or {})  # noqa: S310 (schéma vérifié)
    try:
        with OPENER.open(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return 0, {}, b""


def wait(what: str, check, timeout: float, every: float = 3) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(every)
    print(f"   (délai dépassé : {what})")
    return False


class Pile:
    def __init__(self, args: argparse.Namespace) -> None:
        self.a = args
        self.failures: list[str] = []
        token = base64.b64encode(f"admin:{args.grafana_password}".encode()).decode()
        self.grafana_auth = {"Authorization": f"Basic {token}"}

    def ok(self, label: str, cond: bool, detail: str = "") -> None:
        print(f"{'OK   ' if cond else 'ÉCHEC'} {label}{f' — {detail}' if detail else ''}")
        if not cond:
            self.failures.append(label)

    def json(self, url: str, headers: dict | None = None):
        code, _, body = http(url, headers=headers)
        return json.loads(body) if code == 200 else None

    # ------------------------------------------------------------------ contrôles
    def services(self) -> None:
        for name, url in {
            "api_data": f"{self.a.api_data}/health",
            "api_ia": f"{self.a.api_ia}/health",
            "pwa": f"{self.a.pwa}/",
            "grafana": f"{self.a.grafana}/api/health",
            "prometheus": f"{self.a.prometheus}/-/ready",
            "alertmanager": f"{self.a.alertmanager}/-/ready",
            "loki": f"{self.a.loki}/ready",
        }.items():
            up = wait(name, lambda u=url: http(u)[0] == 200, self.a.attente)
            self.ok(f"{name} répond", up, url)

    def nginx(self) -> None:
        def csp(path: str) -> dict[str, str]:
            _, headers, _ = http(f"{self.a.pwa}{path}")
            value = {k.lower(): v for k, v in headers.items()}.get("content-security-policy", "")
            return dict(d.strip().split(" ", 1) for d in value.split(";") if d.strip())

        app, cadre = csp("/"), csp("/atelier/index.html")
        self.ok(
            "CSP de l'application sans unsafe-eval", bool(app) and "unsafe-eval" not in str(app)
        )
        self.ok(
            "CSP de l'application : frame-ancestors 'none'", app.get("frame-ancestors") == "'none'"
        )
        self.ok(
            "CSP du cadre de l'atelier",
            cadre.get("script-src") == "'self' 'unsafe-eval'"
            and cadre.get("connect-src") == "'none'"
            and cadre.get("frame-ancestors") == "'self'",
            str({k: cadre.get(k) for k in ("script-src", "connect-src", "frame-ancestors")}),
        )
        code, _, body = http(f"{self.a.pwa}/atelier/wokwi-elements.bundle.min.js")
        self.ok("dessins Wokwi servis dans le cadre", code == 200 and len(body) > 100_000)

    def prometheus(self) -> None:
        def targets() -> dict[str, str]:
            data = self.json(f"{self.a.prometheus}/api/v1/targets") or {
                "data": {"activeTargets": []}
            }
            return {t["labels"]["job"]: t["health"] for t in data["data"]["activeTargets"]}

        wait(
            "cibles Prometheus",
            lambda: all(targets().get(j) == "up" for j in ("api_data", "api_ia")),
            90,
        )
        found = targets()
        for job in ("api_data", "api_ia"):
            self.ok(f"Prometheus collecte {job}", found.get(job) == "up", found.get(job, "absente"))
        managers = (self.json(f"{self.a.prometheus}/api/v1/alertmanagers") or {}).get("data", {})
        self.ok(
            "Prometheus relié à Alertmanager", len(managers.get("activeAlertmanagers", [])) == 1
        )

    def grafana(self) -> None:
        boards = self.json(f"{self.a.grafana}/api/search?type=dash-db", self.grafana_auth) or []
        sources = self.json(f"{self.a.grafana}/api/datasources", self.grafana_auth) or []
        self.ok(
            "Grafana : 2 tableaux de bord", len(boards) == 2, ", ".join(b["title"] for b in boards)
        )
        self.ok("Grafana : 3 sources", len(sources) == 3, ", ".join(s["type"] for s in sources))

    def loki(self) -> None:
        def levels() -> set[str]:
            q = urllib.parse.urlencode({"match[]": '{service=~"api_data|api_ia"}'})
            data = self.json(f"{self.a.loki}/loki/api/v1/series?{q}") or {"data": []}
            return {f"{s.get('service')}:{s.get('level', '-')}" for s in data["data"]}

        wait("journaux dans Loki", lambda: {"api_data:INFO", "api_ia:INFO"} <= levels(), 120)
        found = levels()
        self.ok(
            "Loki reçoit les journaux JSON des API (Alloy, niveau extrait)",
            {"api_data:INFO", "api_ia:INFO"} <= found,
            ", ".join(sorted(found)) or "aucun",
        )
        rules = http(f"{self.a.loki}/loki/api/v1/rules")[2].decode(errors="replace")
        self.ok("Loki : règle EchecsConnexionNombreux chargée", "EchecsConnexionNombreux" in rules)

    def _alert_active(self) -> bool:
        alerts = self.json(f"{self.a.alertmanager}/api/v2/alerts") or []
        return any(a["labels"].get("alertname") == "EchecsConnexionNombreux" for a in alerts)

    def force_brute(self) -> None:
        # Une alerte encore active (essai précédent) validerait le contrôle à tort : on attend qu'elle
        # soit résolue (règle sans dépassement + délai de résolution d'Alertmanager, 5 min).
        wait("fin d'une alerte précédente", lambda: not self._alert_active(), 420, every=10)
        codes = []
        for i in range(25):
            data = urllib.parse.urlencode({"username": f"essai-pile-{i}", "password": "mauvais"})
            codes.append(http(f"{self.a.api_data}/v1/auth/token", data.encode())[0])
        self.ok(
            "25 mauvais mots de passe refusés (401)",
            codes.count(401) == 25,
            f"codes {sorted(set(codes))}",
        )
        start = time.monotonic()

        arrived = wait("alerte EchecsConnexionNombreux", self._alert_active, 180, every=5)
        self.ok(
            "alerte « échecs de connexion » reçue par Alertmanager",
            arrived,
            f"{time.monotonic() - start:.0f} s" if arrived else "",
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--api-data", default="http://localhost:8000")
    p.add_argument("--api-ia", default="http://localhost:8001")
    p.add_argument("--pwa", default="http://localhost:5173")
    p.add_argument("--grafana", default="http://localhost:3000")
    p.add_argument("--prometheus", default="http://localhost:9090")
    p.add_argument("--alertmanager", default="http://localhost:9093")
    p.add_argument("--loki", default="http://localhost:3100")
    p.add_argument(
        "--grafana-password", default=os.environ.get("GRAFANA_ADMIN_PASSWORD", "change-me")
    )
    p.add_argument("--attente", type=float, default=180, help="délai de démarrage par service (s)")
    p.add_argument("--force-brute", action="store_true", help="essai de l'alerte sur les journaux")
    pile = Pile(p.parse_args())
    for step in (pile.services, pile.nginx, pile.prometheus, pile.grafana, pile.loki):
        step()
    if pile.a.force_brute:
        pile.force_brute()
    print(
        f"\n{'Pile vérifiée' if not pile.failures else f'{len(pile.failures)} contrôle(s) en échec'}"
    )
    return 1 if pile.failures else 0


if __name__ == "__main__":
    sys.exit(main())

"""``python -m collecte`` : lance la collecte, écrit le fichier « gold » et l'envoie à l'API de données.

Exemples ::

    uv run python -m collecte --sortie sortie/gold.json
    uv run python -m collecte --envoyer          # APP_DATA_API_URL et APP_DATA_API_KEY lus dans .env
"""

import argparse
from pathlib import Path

import httpx

from collecte.pipeline import CONFIG, ecrire, envoyer, executer, lire_config
from commun.config import get_settings
from commun.logs import configurer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="collecte", description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--sortie", type=Path, default=Path("sortie/gold.json"))
    parser.add_argument("--envoyer", action="store_true", help="importer les fiches dans l'API de données")
    args = parser.parse_args(argv)
    reglages = get_settings()
    configurer(json=reglages.log_json)
    rapport = executer(lire_config(args.config), racine=Path.cwd(), agent=reglages.user_agent)
    print(rapport.resume())
    ecrire(rapport.fiches, args.sortie)
    print(f"Fichier gold : {args.sortie}")
    if args.envoyer:
        with httpx.Client(
            base_url=reglages.data_api_url, headers={"X-API-Key": reglages.data_api_key}, timeout=60
        ) as client:
            print(envoyer(rapport.fiches, client))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

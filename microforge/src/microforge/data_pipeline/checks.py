"""Contrôles du catalogue MicroForge contre les données collectées (C3/C5).

``check_libraries`` : chaque bibliothèque citée par un composant (toutes variantes de code) doit
exister, sous ce nom exact, dans l'index officiel du gestionnaire de bibliothèques Arduino collecté.
Sinon ``arduino-cli lib install`` échouerait chez l'utilisateur.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from microforge.core.catalog import Catalog, get_catalog


def catalog_libraries(catalog: Catalog | None = None) -> dict[str, list[str]]:
    """{bibliothèque: [composants qui la citent]}."""
    catalog = catalog or get_catalog()
    out: dict[str, list[str]] = {}
    for comp in catalog.components.values():
        for tpl in comp.code.values():
            for lib in tpl.libraries:
                users = out.setdefault(lib, [])
                if comp.id not in users:
                    users.append(comp.id)
    return out


def check_libraries(clean_dir: Path, catalog: Catalog | None = None) -> dict[str, Any]:
    import polars as pl

    path = clean_dir / "libraries_clean.parquet"
    if not path.exists():
        return {"status": "non_verifie", "message": "libraries_clean.parquet absent"}
    index = pl.read_parquet(path)
    names = index["name"].to_list()
    versions = dict(zip(names, index["version"].to_list(), strict=True))
    cited = catalog_libraries(catalog)
    missing = {lib: comps for lib, comps in cited.items() if lib not in versions}
    return {
        "status": "ecart" if missing else "ok",
        "index": len(versions),
        "citees": len(cited),
        "manquantes": missing,
        "versions": {lib: versions[lib] for lib in sorted(cited) if lib in versions},
    }

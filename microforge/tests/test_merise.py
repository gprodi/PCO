"""Le MCD (docs/E1/merise.mcd, format Mocodo) reste aligné sur le schéma SQLModel (C4).

Chaque entité, et chaque association n,n, est une table. Chaque association avec un côté 0,1 ou 1,1
est une clé étrangère de ce côté vers l'autre entité.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from microforge.api_data import db  # noqa: F401  (enregistre les tables)
from sqlmodel import SQLModel

MCD = Path(__file__).resolve().parents[1] / "docs" / "E1" / "merise.mcd"
ASSOC = re.compile(r"^([^:,]+),\s*(.+)$")
LEG = re.compile(r"^([01][1N])\s+(.+)$")


def norm(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"\W+", "_", ascii_name.strip()).strip("_").lower()


def parse() -> tuple[set[str], list[tuple[str, list[tuple[str, str]]]]]:
    entities, associations = set(), []
    for raw in MCD.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        head = line.split(":", 1)[0]
        if "," not in head:  # « ENTITÉ: attributs »
            entities.add(norm(head))
            continue
        name, legs = ASSOC.match(line).groups()
        parsed = [LEG.match(leg.strip()).groups() for leg in legs.split(":")[0].split(",")]
        associations.append((norm(name), [(card, norm(ent)) for card, ent in parsed]))
    return entities, associations


def test_mcd_tables_match_sqlmodel():
    entities, associations = parse()
    many_to_many = {name for name, legs in associations if all(c[1] == "N" for c, _ in legs)}
    assert many_to_many == {"utilise"}
    assert entities | many_to_many == set(SQLModel.metadata.tables)
    assert len(SQLModel.metadata.tables) == 14


def test_mcd_associations_match_foreign_keys():
    _, associations = parse()
    expected = set()
    for name, legs in associations:
        (c1, e1), (c2, e2) = legs
        if c1[1] == "N" and c2[1] == "N":
            expected |= {(name, e1), (name, e2)}
        elif c1[1] == "1":
            expected.add((e1, e2))
        else:
            expected.add((e2, e1))
    actual = {
        (table.name, fk.column.table.name)
        for table in SQLModel.metadata.tables.values()
        for fk in table.foreign_keys
    }
    assert expected == actual


def test_optional_foreign_keys_are_nullable_columns():
    """0,1 dans le MCD ⇔ clé étrangère facultative dans le schéma."""
    _, associations = parse()
    optional = {
        (e, other)
        for _, ((c1, e1), (c2, e2)) in associations
        for (c, e), (_, other) in (((c1, e1), (c2, e2)), ((c2, e2), (c1, e1)))
        if c == "01"
    }
    nullable = {
        (table.name, fk.column.table.name)
        for table in SQLModel.metadata.tables.values()
        for fk in table.foreign_keys
        if fk.parent.nullable
    }
    assert optional == nullable == {("composant", "fabricant"), ("retour_detection", "photo")}

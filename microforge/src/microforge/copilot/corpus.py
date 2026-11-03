"""Corpus du copilote : le catalogue MicroForge mis en passages indexables.

Une source de vérité unique : les mêmes YAML que le moteur (composants, cartes, familles, modèles de
projets, idées, parcours, vitrine). Le copilote répond donc avec les règles réellement appliquées par
le câblage et l'ERC (broches réservées, bus par défaut, tensions, compatibilités), pas avec des
souvenirs génériques d'un modèle de langage.
"""

from __future__ import annotations

import hashlib

from llm_gateway.vectorstore import Record

from microforge.core.catalog import Catalog, get_catalog
from microforge.core.ideas import load_path, load_showcase, load_themes
from microforge.core.models import BoardDef, ComponentDef, SignalRole

ROLE_FR = {
    SignalRole.POWER: "alimentation",
    SignalRole.GROUND: "masse",
    SignalRole.GPIO_IN: "entrée numérique",
    SignalRole.GPIO_OUT: "sortie numérique",
    SignalRole.GPIO_IO: "entrée/sortie bidirectionnelle",
    SignalRole.PWM: "sortie PWM",
    SignalRole.ADC: "entrée analogique",
    SignalRole.I2C_SDA: "I2C SDA",
    SignalRole.I2C_SCL: "I2C SCL",
    SignalRole.SPI_MOSI: "SPI MOSI",
    SignalRole.SPI_MISO: "SPI MISO",
    SignalRole.SPI_SCK: "SPI SCK",
    SignalRole.SPI_CS: "SPI CS",
    SignalRole.UART_TX: "UART TX, vers le RX de la carte",
    SignalRole.UART_RX: "UART RX, vers le TX de la carte",
    SignalRole.NC: "non connectée",
}


def _num(v: float) -> str:
    return f"{v:g}".replace(".", ",")


def _volts(v: float) -> str:
    return f"{_num(v)} V"


def component_record(comp: ComponentDef, catalog: Catalog) -> Record:
    lo, hi = comp.supply_v
    pins = "; ".join(
        f"{p.name} ({ROLE_FR[p.role]}{', ' + p.description if p.description else ''})"
        for p in comp.pins
    )
    code = comp.code_for("default")
    lines = [
        f"{comp.name} — catégorie {comp.category}. {comp.description}",
        f"Alimentation {_volts(lo)} à {_volts(hi)}, consommation typique {_num(comp.current_ma)} mA"
        + (f", pic {_num(comp.peak_ma)} mA" if comp.peak_ma else "")
        + ".",
        f"Broches : {pins}." if pins else "",
        "Adresses I2C : " + ", ".join(hex(a) for a in comp.i2c_addresses) + "."
        if comp.i2c_addresses
        else "",
        f"Bibliothèques Arduino : {', '.join(code.libraries)}." if code.libraries else "",
        f"Variantes de code par famille : {', '.join(k for k in comp.code if k != 'default')}."
        if len(comp.code) > 1
        else "",
        f"Autres noms : {', '.join(comp.aliases)}." if comp.aliases else "",
    ]
    excluded = [b.name for b in catalog.boards.values() if not comp.supports(b)]
    if excluded:
        lines.append(
            f"Incompatible avec : {', '.join(excluded)}. {comp.compat_note}".strip()
            if len(excluded) <= 6
            else f"Incompatible avec {len(excluded)} cartes. {comp.compat_note}".strip()
        )
    lines += [f"Conseil : {n}" for n in comp.notes]
    if comp.price_eur:
        lines.append(f"Prix indicatif : {_num(comp.price_eur)} €.")
    return Record(
        f"composant:{comp.id}",
        "composant",
        comp.name,
        "\n".join(x for x in lines if x),
        {"ref": comp.id},
    )


def board_record(board: BoardDef, catalog: Catalog) -> Record:
    fam = catalog.families[board.family]

    def label(gpio: int) -> str:
        return next((p.label for p in board.pins if p.gpio == gpio), str(gpio))

    def bus(d: dict[str, int]) -> str:
        return ", ".join(f"{k.upper()}={label(v)}" for k, v in d.items())

    io = [
        ("entrée seule", [p.label for p in board.pins if p.input_only]),
        ("démarrage (strapping)", [p.label for p in board.pins if p.strapping]),
        (
            "réservées",
            [f"{p.label}{' (' + p.note + ')' if p.note else ''}" for p in board.pins if p.reserved],
        ),
    ]
    radio = [
        n
        for n, ok in (
            ("Wi-Fi", board.wifi),
            ("Bluetooth", board.bluetooth),
            ("Zigbee/Thread", board.zigbee_thread),
        )
        if ok
    ]
    lines = [
        f"{board.name} — famille {fam.label}, microcontrôleur {board.mcu}.",
        f"Logique {_volts(board.logic_v)}, "
        + ("tolérante 5 V" if board.five_v_tolerant else "NON tolérante 5 V")
        + f", {_num(board.gpio_max_ma)} mA max par broche.",
        f"Radio : {', '.join(radio)}." if radio else "Pas de radio intégrée.",
        f"Rails : {', '.join(f'{k} = {_volts(v)}' for k, v in board.rails.items())}.",
        f"I2C par défaut : {bus(board.default_i2c)}." if board.default_i2c else "",
        f"SPI par défaut : {bus(board.default_spi)}." if board.default_spi else "",
        f"UART par défaut : {bus(board.default_uart)}." if board.default_uart else "",
        *(f"Broches {k} : {', '.join(v)}." for k, v in io if v),
        "ADC2 inutilisable quand le Wi-Fi est actif : lire l'analogique sur ADC1."
        if board.adc2_wifi_conflict
        else "",
        f"FQBN arduino-cli : {board.fqbn}." if board.fqbn else "",
        *(f"Note : {n}" for n in board.notes),
        f"Brochage officiel : {board.source}" if board.source else "",
    ]
    return Record(
        f"carte:{board.id}",
        "carte",
        board.name,
        "\n".join(x for x in lines if x),
        {"ref": board.id, "url": board.source},
    )


def build_corpus(catalog: Catalog | None = None) -> list[Record]:
    """Tous les passages du copilote, dans un ordre stable."""
    catalog = catalog or get_catalog()
    out: list[Record] = [component_record(c, catalog) for c in catalog.components.values()]
    out += [board_record(b, catalog) for b in catalog.boards.values()]
    for fam in catalog.families.values():
        boards = [b.name for b in catalog.boards.values() if b.family == fam.id]
        out.append(
            Record(
                f"famille:{fam.id}",
                "famille",
                fam.label,
                f"Famille {fam.label} (cœur arduino-cli {fam.core}, PlatformIO {fam.platformio}). "
                f"Cartes : {', '.join(boards)}. "
                + (
                    "Projets Wi-Fi générés. "
                    if fam.wifi_supported
                    else "Pas de projet Wi-Fi généré. "
                )
                + " ".join(fam.notes),
                {"ref": fam.id},
            )
        )
    for tpl in catalog.templates.values():
        comps = ", ".join(f"{p.name} = {catalog.component(p.component).name}" for p in tpl.parts)
        fams = catalog.template_families(tpl.id)
        refs = "; ".join(f"{r.title} ({r.url})" for r in tpl.references)
        text = (
            f"{tpl.description}\nDifficulté {tpl.difficulty}/3. Composants : {comps}.\n"
            f"Familles compatibles : {', '.join(catalog.families[f].label for f in fams)}."
            + (" Wi-Fi nécessaire." if tpl.requires_wifi else "")
            + (f"\nCe qu'on apprend : {'; '.join(tpl.learning)}." if tpl.learning else "")
            + (f"\nTutoriels publics : {refs}." if refs else "")
        )
        out.append(
            Record(
                f"projet:{tpl.id}",
                "projet",
                f"Projet « {tpl.title} »",
                text,
                {"ref": tpl.id, "url": tpl.references[0].url if tpl.references else ""},
            )
        )
    for theme in load_themes():
        for i, idea in enumerate(theme.idees):
            names = [
                catalog.component(c).name if c in catalog.components else c for c in idea.composants
            ]
            out.append(
                Record(
                    f"idee:{theme.id}:{i}",
                    "idee",
                    f"Idée « {idea.titre} » ({theme.titre})",
                    f"{idea.description} Composants : {', '.join(names)}. Difficulté {idea.difficulte}/3."
                    + (
                        f" Modèle générable : {idea.template}."
                        if idea.template
                        else " À concevoir avec l'IA."
                    ),
                    {"ref": idea.template or ""},
                )
            )
    for step in load_path():
        out.append(
            Record(
                f"parcours:{step.etape}",
                "parcours",
                f"Parcours, étape {step.etape} : {step.titre}",
                f"{step.objectif} Notions : {', '.join(step.notions)}. "
                f"Projets : {', '.join(catalog.templates[t].title for t in step.templates if t in catalog.templates)}.",
            )
        )
    for i, show in enumerate(load_showcase()):
        out.append(
            Record(
                f"vitrine:{i}",
                "vitrine",
                f"Projet open source « {show.nom} »",
                f"{show.description} Catégorie : {show.categorie}. Carte : {show.carte}. {show.url}"
                + (
                    f" Commencer par : {', '.join(show.commencer_par)}."
                    if show.commencer_par
                    else ""
                ),
                {"url": show.url},
            )
        )
    return out


def fingerprint(records: list[Record]) -> str:
    """Empreinte du corpus : l'index est reconstruit quand le catalogue change."""
    h = hashlib.sha256()
    for r in records:
        h.update(f"{r.id}\x1f{r.title}\x1f{r.text}\x1e".encode())
    return h.hexdigest()[:16]

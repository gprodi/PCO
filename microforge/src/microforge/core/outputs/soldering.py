"""Guide de montage et de soudure pas-à-pas (Markdown accessible)."""

from __future__ import annotations

from microforge.core.allocator import Allocation
from microforge.core.catalog import Catalog
from microforge.core.models import BoardDef, ERCIssue, Net, ProjectSpec, Severity

TROUBLESHOOTING = {
    "dht22": "Valeur `nan` : vérifier DATA, attendre 2 s entre deux lectures, contrôler la pull-up.",
    "dht11": "Valeur `nan` : vérifier DATA et l'alimentation.",
    "ssd1306-i2c": "Écran noir : lancer un scanner I2C (adresse 0x3C ou 0x3D), vérifier SDA/SCL inversés.",
    "lcd1602-i2c": "Carrés blancs : tourner le potentiomètre de contraste au dos ; adresse 0x27 ou 0x3F.",
    "bme280": "« introuvable » : adresse 0x76/0x77 (broche SDO), module 3,3 V uniquement.",
    "hc-sr04": "Toujours -1 : TRIG/ECHO inversés, ou pont diviseur mal câblé sur ESP32.",
    "sg90-servo": "Tremblements/reset de la carte : alimentation insuffisante, ajouter 5 V externe + 470 µF.",
    "ws2812-ring-12": "Couleurs aléatoires : masse commune, résistance 330 Ω sur DIN, level shifter.",
    "relay-module-1ch": "Le relais claque à l'envers : changer ACTIF_BAS dans mf_components.h.",
    "rc522-rfid": "Aucun badge lu : alimentation 3,3 V (jamais 5 V), câblage SPI complet.",
    "mpu6050": "« introuvable » : vérifier l'adresse (AD0), SDA/SCL.",
    "ds18b20": "-127 °C : pull-up 4,7 kΩ manquante ou fil DQ débranché.",
    "pushbutton": "Toujours appuyé : bouton tourné de 90° (pattes reliées deux à deux).",
}


def _net_line(net: Net) -> str:
    nodes = ", ".join(f"{n.ref}.{n.pin}" for n in net.nodes)
    return f"- [ ] **{net.name}** : {nodes}"


def soldering_guide(
    spec: ProjectSpec,
    board: BoardDef,
    alloc: Allocation,
    catalog: Catalog,
    nets: list[Net],
    issues: list[ERCIssue],
) -> str:
    """Guide complet : matériel, sécurité, breadboard, soudure, contrôles, mise en service."""
    comps = [(p.name, catalog.component(p.component)) for p in spec.parts]
    power_nets = [n for n in nets if n.kind == "power"]
    md: list[str] = [
        f"# Guide de montage — {spec.title}",
        "",
        spec.description or "",
        "",
        "## 1. Outillage",
        "",
        "- Fer à souder thermostaté (300–350 °C), panne fine conique ou biseautée",
        "- Étain 0,8 mm avec flux (sans plomb de préférence), éponge laiton",
        "- Tresse ou pompe à dessouder, pince coupante, pince à dénuder",
        "- Multimètre (continuité, tension), support « troisième main »",
        "- Lunettes de protection, pièce aérée (fumées de flux)",
        "",
        "## 2. Sécurité",
        "",
        "- Toujours débrancher l'USB et les piles avant de souder ou de recâbler.",
        "- Le fer chauffe à plus de 300 °C : le reposer sur son support, jamais sur la table.",
        "- Se laver les mains après la soudure (étain/flux).",
    ]
    errors = [i for i in issues if i.severity == Severity.ERROR]
    warnings = [i for i in issues if i.severity == Severity.WARNING]
    if errors or warnings:
        md += ["", "## 3. Points d'attention électriques (à lire avant de câbler)", ""]
        for i in errors + warnings:
            tag = "⛔ BLOQUANT" if i.severity == Severity.ERROR else "⚠️ Attention"
            md.append(f"- **{tag}** — {i.message} *Correctif :* {i.fix}")
    md += [
        "",
        "## 4. Étape 1 — Prototype sur breadboard (sans soudure)",
        "",
        "1. Placer la carte à cheval sur la rainure centrale de la breadboard.",
        "2. Relier les rails : "
        + ", ".join(f"**{n.name}**" for n in power_nets)
        + " et **GND** (fil noir) aux lignes d'alimentation de la plaque.",
        "3. Câbler en suivant le **tableau de câblage** (`cablage.md`) ligne par ligne, "
        "dans l'ordre : masse, alimentations, bus, signaux.",
    ]
    if alloc.added_parts:
        md.append("4. Insérer les résistances ajoutées automatiquement :")
        for p in alloc.added_parts:
            low = f" et {p.value_low} vers GND" if p.value_low else ""
            md.append(f"   - `{p.name}` {p.value}{low} — {p.reason}")
    md += [
        f"{5 if alloc.added_parts else 4}. Téléverser le firmware et valider le fonctionnement "
        "(moniteur série 115200 bauds) **avant** de souder quoi que ce soit.",
        "",
        "## 5. Étape 2 — Montage définitif sur plaque à pastilles",
        "",
        "1. Souder des **barrettes femelles** pour la carte (elle reste amovible) et des "
        "barrettes mâles/femelles pour chaque module.",
        "2. Tracer les **rails d'alimentation** au fil rigide (rouge/orange) et la **masse** (noir) "
        "le long de la plaque.",
        "3. Souder les **bus partagés** (I2C/SPI) en étoile depuis la carte.",
        "4. Souder les **signaux** un par un en cochant le tableau de câblage.",
        "5. Souder les **résistances** au plus près de la broche protégée.",
        "",
        "### Geste de soudure",
        "",
        "1. Chauffer **en même temps** la pastille et la patte (1–2 s).",
        "2. Apporter l'étain sur la jonction (pas sur la panne).",
        "3. Retirer l'étain puis le fer ; ne pas bouger pendant 2 s.",
        "4. Contrôler : soudure brillante en forme de petit volcan, aucun pont avec la pastille voisine.",
        "",
        "## 6. Contrôles au multimètre AVANT la mise sous tension",
        "",
        "Mode continuité (bip). Chaque ligne doit biper entre toutes ses broches :",
        "",
        *(_net_line(n) for n in nets),
        "",
        "Puis, en mode ohmmètre, **aucun court-circuit** :",
        *(f"- [ ] entre **{n.name}** et **GND** : résistance > 1 kΩ" for n in power_nets),
        "",
        "## 7. Première mise sous tension",
        "",
        "1. Brancher l'USB seul (pas de piles) ; toucher les composants après 10 s : rien ne doit chauffer.",
        f"2. Téléverser `{'le sketch'}` (carte **{board.name}**, FQBN `{board.fqbn}`).",
        "3. Ouvrir le moniteur série (115200 bauds) et vérifier les messages d'initialisation.",
        "",
        "## 8. Dépannage",
        "",
    ]
    tips = {c.id: TROUBLESHOOTING[c.id] for _, c in comps if c.id in TROUBLESHOOTING}
    md += [f"- **{cid}** : {tip}" for cid, tip in tips.items()] or [
        "- Vérifier masse commune et alimentation."
    ]
    md += [
        "- Rien ne marche : vérifier la **masse commune** entre carte, modules et alimentation externe."
    ]
    for _, comp in comps:
        for note in comp.notes:
            md.append(f"- *{comp.name}* : {note}")
    return "\n".join(md).replace("\n\n\n", "\n\n") + "\n"

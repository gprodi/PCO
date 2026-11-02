"""Génère les brouillons des rapports professionnels E1 à E5 à partir des MODÈLES OFFICIELS.

    uv run python microforge/docs/rapports/generer_rapports.py            # les 5 rapports
    uv run python microforge/docs/rapports/generer_rapports.py E3         # un seul

Principe : on ouvre ``referentiel/modeles/E<n>_template.docx`` (mise en page, page de garde, sommaire
automatique conservés), on parcourt les titres, et on remplace les paragraphes d'exemple (« blah »,
« API », « le projet consiste en »…) par le contenu de ``contenu_E<n>.yaml``.

Conventions du contenu (liste de chaînes par titre) :
  * ``- texte``             -> puce
  * ``| a | b |`` (lignes)  -> tableau bordé (1re ligne = en-tête)
  * bloc commençant par ```` ``` ```` -> code (police à chasse fixe)
  * ``[À COMPLÉTER : …]``    -> surligné en jaune (captures, mesures réelles à ajouter)
  * clé ``Parent > Titre``  -> pour les titres en double (« Définition » sous MCD/MLD/MPD)

Après ouverture dans Word/LibreOffice : clic droit sur le sommaire > « Mettre à jour la table ».
"""

from __future__ import annotations

import copy
import re
import sys
import unicodedata
from pathlib import Path

import yaml
from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docx.text.paragraph import Paragraph

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
MODELES = ROOT / "referentiel" / "modeles"

PLACEHOLDERS = {
    "blah",
    "le projet consiste en",
    "api",
    "fichiers",
    "webscraping",
    "base de donnees",
    "big data",
    "technologie qui vont etre utilisees, contraintes specifiques",
    "sqlalchemy orm + test",
    "equivalent en sql",
    "pipeline automatique d'agregation des donnees",
    "crud en annexe + qui a le droit a quoi",
    "routes, pydantic, pytest",
    "prometheus / grafana / uptime kuma etc...",
    "route doc de fastapi",
    "technologie qui vont etre utilisees, contraintes specifiques, architecture et documentation",
    "je tiens a remercier personne",
}
TODO = re.compile(r"(\[À COMPLÉTER[^\]]*\])")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.replace("’", "'").replace("…", "...").lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(" .:")


def is_heading(p: Paragraph) -> bool:
    name = p.style.name if p.style is not None and p.style.name else ""
    return name.startswith("Heading") or (
        name == "Title" and p.text.strip() in {"Introduction", "Remerciements"}
    )


def heading_level(p: Paragraph) -> int:
    name = p.style.name or ""
    return int(name.split()[-1]) if name.startswith("Heading") and name.split()[-1].isdigit() else 1


# ------------------------------------------------------------------ insertion
def _new_paragraph_after(anchor, parent) -> Paragraph:
    new_p = OxmlElement("w:p")
    anchor.addnext(new_p)
    return Paragraph(new_p, parent)


def _add_runs(p: Paragraph, text: str, mono: bool = False, bold: bool = False) -> None:
    for part in TODO.split(text):
        if not part:
            continue
        run = p.add_run(part)
        run.bold = bold or None
        if mono:
            run.font.name = "Consolas"
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
        if TODO.fullmatch(part):
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW
            run.bold = True


def _bordered_table(doc, rows: list[list[str]]):
    table = doc.add_table(rows=len(rows), cols=max(len(r) for r in rows))
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "808080")
        borders.append(el)
    tbl_pr.append(borders)
    for i, row in enumerate(rows):
        for j, cell_text in enumerate(row):
            cell = table.cell(i, j)
            cell.paragraphs[0].text = ""
            _add_runs(cell.paragraphs[0], cell_text, bold=(i == 0))
            for r in cell.paragraphs[0].runs:
                r.font.size = Pt(9)
    return table


def insert_blocks(doc, anchor, blocks: list[str], body_style) -> None:
    """Insère les blocs après ``anchor`` (élément XML), dans l'ordre."""
    for block in blocks:
        block = block.rstrip()
        if block.startswith("|"):
            rows = [
                [c.strip() for c in line.strip().strip("|").split("|")]
                for line in block.splitlines()
                if line.strip().startswith("|") and not re.fullmatch(r"\|[\s:|-]+\|?", line.strip())
            ]
            table = _bordered_table(doc, rows)
            anchor.addnext(table._tbl)
            anchor = table._tbl
            spacer = _new_paragraph_after(anchor, doc._body)
            spacer.style = body_style
            anchor = spacer._p
            continue
        if block.startswith("```"):
            for line in block.strip("`").split("\n")[1:]:
                p = _new_paragraph_after(anchor, doc._body)
                p.style = body_style
                _add_runs(p, line or " ", mono=True)
                anchor = p._p
            continue
        for line in block.split("\n"):
            p = _new_paragraph_after(anchor, doc._body)
            p.style = body_style
            if line.startswith("- "):
                p.paragraph_format.left_indent = Pt(18)
                p.paragraph_format.first_line_indent = Pt(-10)
                _add_runs(p, "• " + line[2:])
            else:
                _add_runs(p, line)
            anchor = p._p


# ------------------------------------------------------------------ remplissage
def fill(epreuve: str, out_dir: Path) -> Path:
    template = MODELES / f"{epreuve}_template.docx"
    data = yaml.safe_load((HERE / f"contenu_{epreuve}.yaml").read_text(encoding="utf-8"))
    sections: dict[str, list[str]] = {norm(k): v for k, v in data["sections"].items()}
    doc = Document(str(template))
    body_style = next((p.style for p in doc.paragraphs if (p.style.name or "") == "normal"), None)

    # Page de garde : titre du projet
    for p in doc.paragraphs:
        if p.text.strip() == "Titre du projet":
            for r in p.runs[1:]:
                r.text = ""
            p.runs[0].text = data["titre"]
            p.runs[0].bold = True
            break

    used: set[str] = set()
    stack: list[tuple[int, str]] = []
    paragraphs = list(doc.paragraphs)
    for idx, p in enumerate(paragraphs):
        if not is_heading(p):
            continue
        level = heading_level(p) if (p.style.name or "").startswith("Heading") else 1
        title = p.text.strip()
        if norm(title).startswith("annexe 1"):
            p.runs[0].text = data.get("annexe_titre", "Annexe 1")
            for r in p.runs[1:]:
                r.text = ""
            title = "Annexes"
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else ""
        stack.append((level, title))
        key = next(
            (
                k
                for k in (norm(f"{parent} > {title}"), norm(title))
                if k in sections and k not in used
            ),
            None,
        )
        if key is None:
            continue
        used.add(key)
        # Supprime les paragraphes d'exemple qui suivent ce titre (jusqu'au titre suivant)
        for nxt in paragraphs[idx + 1 :]:
            if is_heading(nxt):
                break
            if norm(nxt.text) in PLACEHOLDERS and not is_heading(nxt):
                nxt._p.getparent().remove(nxt._p)
        insert_blocks(doc, p._p, sections[key], body_style)

    missing = sorted(set(sections) - used)
    if missing:
        print(f"⚠️ {epreuve} : sections sans titre correspondant : {missing}")
    # Remplace les « blah » restants par un repère visible
    for p in doc.paragraphs:
        if norm(p.text) in PLACEHOLDERS and not is_heading(p):
            for r in p.runs[1:]:
                r.text = ""
            if p.runs:
                p.runs[0].text = "[À COMPLÉTER]"
                p.runs[0].font.highlight_color = WD_COLOR_INDEX.YELLOW
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{epreuve}_MicroForge_brouillon.docx"
    doc.save(str(out))
    return out


def outline(epreuve: str) -> list[dict]:
    """Plan du rapport attendu (titres du modèle) — exporté vers le site de révision."""
    doc = Document(str(MODELES / f"{epreuve}_template.docx"))
    plan: list[dict] = []
    current = None
    for p in doc.paragraphs:
        name = p.style.name or ""
        text = p.text.strip()
        if not name.startswith("Heading") or not text:
            continue
        level = heading_level(p)
        m = re.match(r"(C\d+)\.", text)
        if m:
            current = {"competence": m.group(1), "titre": text, "sections": []}
            plan.append(current)
        elif current is not None and level >= 3 and not norm(text).startswith("annexe"):
            current["sections"].append(("  " * (level - 3)) + text)
        elif level <= 2:
            current = None
    return plan


def main(argv: list[str]) -> None:
    targets = argv or ["E1", "E2", "E3", "E4", "E5"]
    for ep in targets:
        print("Rapport :", fill(ep, HERE))


if __name__ == "__main__":
    main(sys.argv[1:])
    _ = copy  # (module conservé pour d'éventuelles duplications de blocs)

"""Convertisseurs par format (md, txt, pdf, pptx, html, docx, ipynb, URL).

Particularité des cours fournis : certains .md exportés de Google Docs contiennent des images en
base64 (plus de 99 % du poids de « HorRAGor BOT Partie 1.md ») ; elles sont retirées du texte et
remplacées par un repère ``[image]`` (option : extraction en fichiers pour description par VLM).
"""

from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path

_B64_REF = re.compile(r"^\[[^\]]+\]:\s*<data:image/[^>]+>\s*$", re.M)
_B64_INLINE = re.compile(r"!\[[^\]]*\]\(data:image/[^)]+\)")
_IMG_REF = re.compile(r"!\[\]\[image\d+\]")
_ESCAPES = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|&>~=])")
_ANCHORS = re.compile(r"\s*\{#[^}]*\}")


def extract_base64_images(text: str, out_dir: Path | None = None) -> tuple[str, int]:
    """Retire les images base64 ; les écrit dans ``out_dir`` si fourni. Renvoie (texte, nombre)."""
    count = 0
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for m in re.finditer(r"data:image/(png|jpe?g|gif|webp);base64,([A-Za-z0-9+/=]+)", text):
            count += 1
            try:
                (out_dir / f"image{count}.{m.group(1).replace('jpeg', 'jpg')}").write_bytes(
                    base64.b64decode(m.group(2))
                )
            except ValueError:
                continue
    else:
        count = len(_B64_REF.findall(text)) + len(_B64_INLINE.findall(text))
    text = _B64_REF.sub("", text)
    text = _B64_INLINE.sub("[image]", text)
    text = _IMG_REF.sub("[image]", text)
    return text, count


def clean_markdown(text: str) -> str:
    """Nettoie les exports Google Docs : échappements, ancres {#...}, lignes vides en série."""
    text = _ESCAPES.sub(r"\1", text)
    text = _ANCHORS.sub("", text)
    text = re.sub(
        r"\[([^\]]+)\s+\d+\]\(#[^)]+\)", r"\1", text
    )  # entrées de sommaire « [Titre 3](#ancre) »
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def from_markdown(path: Path, images_dir: Path | None = None) -> str:
    text, _ = extract_base64_images(path.read_text(encoding="utf-8", errors="replace"), images_dir)
    return clean_markdown(text)


def from_text(path: Path) -> str:
    return clean_markdown(path.read_text(encoding="utf-8", errors="replace"))


def from_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, 1):
        txt = (page.extract_text() or "").strip()
        if txt:
            pages.append(f"## Page {i}\n\n{txt}")
    return clean_markdown("\n\n".join(pages))


def from_pptx(path: Path) -> str:
    from pptx import Presentation

    prs = Presentation(str(path))
    slides = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = "".join(run.text for run in para.runs).strip()
                    if line:
                        texts.append(line)
        notes = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        if texts or notes:
            title = texts[0] if texts else f"Diapositive {i}"
            body = "\n".join(f"- {t}" for t in texts[1:])
            slides.append(
                f"## {i}. {title}\n\n{body}" + (f"\n\n> Notes : {notes}" if notes else "")
            )
    return clean_markdown("\n\n".join(slides))


def from_html(path_or_html: Path | str, is_raw: bool = False) -> str:
    from bs4 import BeautifulSoup
    from markdownify import markdownify

    html = (
        path_or_html if is_raw else Path(path_or_html).read_text(encoding="utf-8", errors="replace")
    )
    soup = BeautifulSoup(html, "lxml")
    scripts = [s.string or "" for s in soup.find_all("script")]
    for tag in soup(["script", "style", "nav", "footer", "svg", "noscript"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    markdown = clean_markdown(markdownify(str(main), heading_style="ATX", code_language=""))
    if len(markdown.strip()) < 300 and any(len(s) > 1000 for s in scripts):
        markdown = clean_markdown(markdown + "\n\n" + strings_from_scripts(scripts))
    return markdown


_JS_STRING = re.compile(
    r"`((?:[^`\\]|\\.)*)`|\"((?:[^\"\\\n]|\\.){30,})\"|'((?:[^'\\\n]|\\.){30,})'"
)


def strings_from_scripts(scripts: list[str]) -> str:
    """Présentations « tout en JavaScript » : récupère le texte des chaînes littérales."""
    from bs4 import BeautifulSoup

    lines = ["## Contenu extrait de la présentation interactive"]
    for script in scripts:
        for m in _JS_STRING.finditer(script):
            raw = next(g for g in m.groups() if g is not None)
            text = raw.replace("\\n", "\n").replace("\\'", "'").replace('\\"', '"')
            text = BeautifulSoup(text, "lxml").get_text(" ") if "<" in text else text
            text = text.strip()
            if len(text) >= 20 and not re.fullmatch(r"[\w./#:-]+", text):
                lines.append(
                    f"```python\n{text}\n```"
                    if text.lstrip().startswith(("class ", "from ", "import ", "def ", "#"))
                    else text
                )
    return "\n\n".join(lines)


def from_docx(path: Path) -> str:
    import docx

    doc = docx.Document(str(path))
    out = []
    for p in doc.paragraphs:
        style = (p.style.name or "").lower() if p.style else ""
        if not p.text.strip():
            continue
        if style.startswith("heading"):
            level = int(re.sub(r"\D", "", style) or 1)
            out.append("#" * min(level + 1, 6) + " " + p.text.strip())
        else:
            out.append(p.text.strip())
    return clean_markdown("\n\n".join(out))


def from_ipynb(path: Path) -> str:
    nb = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for cell in nb.get("cells", []):
        src = "".join(cell.get("source", []))
        if cell.get("cell_type") == "markdown":
            out.append(src)
        elif cell.get("cell_type") == "code" and src.strip():
            out.append(f"```python\n{src}\n```")
    return clean_markdown("\n\n".join(out))


SUPPORTED = {
    ".md": from_markdown,
    ".markdown": from_markdown,
    ".txt": from_text,
    ".pdf": from_pdf,
    ".pptx": from_pptx,
    ".html": from_html,
    ".htm": from_html,
    ".docx": from_docx,
    ".ipynb": from_ipynb,
}


def convert_file(path: Path, images_dir: Path | None = None) -> str:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"Format non pris en charge : {suffix} (formats : {', '.join(SUPPORTED)})")
    if suffix in (".md", ".markdown"):
        return from_markdown(path, images_dir)
    return SUPPORTED[suffix](path)


def convert_url(url: str, client=None) -> str:
    """Page web -> Markdown (contenu principal)."""
    import httpx

    http = client or httpx.Client(
        timeout=30, follow_redirects=True, headers={"User-Agent": "RevisionsDevIA/0.1"}
    )
    resp = http.get(url)
    resp.raise_for_status()
    return from_html(resp.text, is_raw=True)


def convert_bytes(data: bytes, filename: str) -> str:
    """Upload depuis l'API : écrit temporairement puis convertit."""
    import tempfile

    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return convert_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


__all__ = ["SUPPORTED", "convert_bytes", "convert_file", "convert_url", "io"]

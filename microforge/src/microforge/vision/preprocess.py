"""Prétraitement des photos : validation, orientation, redimensionnement, suppression des métadonnées.

RGPD : la photo est ré-encodée en JPEG **sans EXIF** (donc sans coordonnées GPS ni modèle
d'appareil). Seule son empreinte SHA-256 est conservée en base ; l'image n'est pas stockée.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "MPO"}
MAX_SIDE = 1280
Image.MAX_IMAGE_PIXELS = 40_000_000  # protection contre les « bombes de décompression »


class InvalidImageError(ValueError):
    """Fichier refusé (format, taille, contenu)."""


@dataclass(frozen=True)
class CleanImage:
    image: Image.Image
    jpeg: bytes
    width: int
    height: int
    sha256: str


def clean_image(
    data: bytes, max_bytes: int = 8 * 1024 * 1024, max_side: int = MAX_SIDE
) -> CleanImage:
    """Valide et nettoie une image envoyée par un client."""
    if not data:
        raise InvalidImageError("Fichier vide")
    if len(data) > max_bytes:
        raise InvalidImageError(f"Image trop lourde (> {max_bytes // (1024 * 1024)} Mo)")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("Fichier image illisible") from exc
    if fmt not in ALLOWED_FORMATS:
        raise InvalidImageError(f"Format {fmt} non accepté (JPEG, PNG, WEBP)")
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)  # pas d'exif= : métadonnées supprimées
    jpeg = buf.getvalue()
    return CleanImage(img, jpeg, img.width, img.height, hashlib.sha256(jpeg).hexdigest())


def crop_jpeg(
    img: Image.Image, box: tuple[float, float, float, float], margin: float = 0.08
) -> bytes:
    """Découpe une zone (x1, y1, x2, y2 en pixels) avec une marge, pour l'identification fine."""
    x1, y1, x2, y2 = box
    mx, my = (x2 - x1) * margin, (y2 - y1) * margin
    region = img.crop(
        (max(0, x1 - mx), max(0, y1 - my), min(img.width, x2 + mx), min(img.height, y2 + my))
    )
    buf = io.BytesIO()
    region.save(buf, format="JPEG", quality=90)
    return buf.getvalue()

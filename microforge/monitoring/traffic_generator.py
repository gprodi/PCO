"""Générateur de trafic pour le bac à sable de monitoring (C11) : simule des utilisateurs.

    uv run python microforge/monitoring/traffic_generator.py --n 50          # trafic normal
    uv run python microforge/monitoring/traffic_generator.py --n 50 --drift  # injecte une dérive

Avec ``--drift`` : images très sombres et 60 % de retours « wrong_label » -> le taux de
corrections dépasse 25 % et l'alerte TauxCorrectionsEleve doit se déclencher dans Grafana.
"""

from __future__ import annotations

import argparse
import io
import random
import uuid

import httpx
from PIL import Image


def image(dark: bool) -> bytes:
    color = (8, 8, 8) if dark else tuple(random.randint(60, 220) for _ in range(3))
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), color).save(buf, format="JPEG")
    return buf.getvalue()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="http://localhost:8000")
    p.add_argument("--ia", default="http://localhost:8001")
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--drift", action="store_true")
    args = p.parse_args()

    user = f"sandbox_{uuid.uuid4().hex[:6]}"
    data, ia = (
        httpx.Client(base_url=args.data, timeout=30),
        httpx.Client(base_url=args.ia, timeout=120),
    )
    data.post(
        "/v1/auth/register",
        json={"username": user, "email": f"{user}@example.org", "password": "motdepasse123"},
    ).raise_for_status()
    tok = data.post("/v1/auth/token", data={"username": user, "password": "motdepasse123"}).json()[
        "access_token"
    ]
    h = {"Authorization": f"Bearer {tok}"}
    wrong_ratio = 0.6 if args.drift else 0.1
    for i in range(args.n):
        scan = ia.post(
            "/v1/vision/scan",
            files={"image": ("s.jpg", image(args.drift), "image/jpeg")},
            headers=h,
        )
        if scan.status_code != 200:
            print("scan", scan.status_code)
            continue
        body = scan.json()
        photo = data.post(
            "/v1/photos",
            json={"sha256": body["sha256"], "width": body["width"], "height": body["height"]},
            headers=h,
        ).json()["id"]
        kind = "wrong_label" if random.random() < wrong_ratio else "correct"
        data.post(
            "/v1/feedback",
            json={
                "kind": kind,
                "photo_id": photo,
                "source": "vlm",
                "confidence": 0.3 if args.drift else 0.8,
            },
            headers=h,
        )
        print(f"{i + 1}/{args.n} {kind}")


if __name__ == "__main__":
    main()

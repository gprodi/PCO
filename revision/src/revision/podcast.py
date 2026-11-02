"""Podcast à deux voix : synthèse vocale LOCALE avec Piper (extra « podcast »).

Sans Piper, le site lit le script avec la synthèse vocale du navigateur (Web Speech API).

    uv run revise podcast mlflow --voice-a fr_FR-siwis-medium --voice-b fr_FR-upmc-medium
"""

from __future__ import annotations

import io
import shutil
import subprocess
import wave
from pathlib import Path

from revision.schemas import Podcast


def synthesize(
    podcast: Podcast, out_mp3: Path, voice_a: str, voice_b: str, models_dir: Path
) -> Path:
    try:
        from piper import PiperVoice
    except ImportError as exc:
        raise RuntimeError("Piper non installé : uv sync --extra podcast") from exc
    voices = {
        "A": PiperVoice.load(str(models_dir / f"{voice_a}.onnx")),
        "B": PiperVoice.load(str(models_dir / f"{voice_b}.onnx")),
    }
    wav_path = out_mp3.with_suffix(".wav")
    with wave.open(str(wav_path), "wb") as out:
        params_set = False
        for rep in podcast.repliques:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as part:
                voices.get(rep.voix, voices["A"]).synthesize_wav(rep.texte, part)
            buf.seek(0)
            with wave.open(buf, "rb") as part:
                if not params_set:
                    out.setparams(part.getparams())
                    params_set = True
                out.writeframes(part.readframes(part.getnframes()))
                out.writeframes(
                    b"\x00\x00" * int(part.getframerate() * 0.35)
                )  # silence entre répliques
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        subprocess.run(  # noqa: S603 — chemins contrôlés, pas d'entrée utilisateur
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(wav_path),
                "-b:a",
                "64k",
                str(out_mp3),
            ],
            check=True,
        )  # noqa: S603, S607
        wav_path.unlink()
        return out_mp3
    return wav_path

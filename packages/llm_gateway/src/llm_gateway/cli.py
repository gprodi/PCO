"""``llm-gateway doctor`` : affiche le matériel détecté, le profil et les fournisseurs actifs."""

from __future__ import annotations

import argparse
import sys

from llm_gateway.config import GatewaySettings
from llm_gateway.gateway import Gateway
from llm_gateway.profiles import available_profiles, choose_profile_name, detect_hardware


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llm-gateway")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="diagnostic matériel + fournisseurs")
    ask = sub.add_parser("ask", help="poser une question au gateway")
    ask.add_argument("prompt")
    ask.add_argument("--role", default="text", choices=["text", "code"])
    args = parser.parse_args(argv)

    settings = GatewaySettings()
    if args.cmd == "doctor":
        hw = detect_hardware()
        print(f"Système     : {hw.system} {hw.machine}")
        print(f"RAM         : {hw.ram_gb} Go")
        print(f"GPU         : {hw.gpu_name or 'aucun GPU NVIDIA'} ({hw.vram_gb or '-'} Go)")
        print(f"Profil auto : {choose_profile_name(hw)}  (disponibles : {available_profiles()})")
        gw = Gateway.from_settings(settings)
        print(f"Profil      : {gw.profile.name} — {gw.profile.description}")
        print("Chaîne      : " + " -> ".join(p.name for p in gw.providers))
        for role in ("text", "code", "vision", "embed"):
            print(f"  {role:6s} -> {gw.profile.model_for('ollama', role)} (ollama)")
        return 0
    gw = Gateway.from_settings(settings)
    print(gw.chat(args.prompt, role=args.role))
    return 0


if __name__ == "__main__":
    sys.exit(main())

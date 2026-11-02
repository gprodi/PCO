"""Orchestration : ProjectSpec -> BuildResult (allocation, ERC, netlist, firmware, sorties, BOM)."""

from __future__ import annotations

import io
import json
import zipfile

from microforge.core.allocator import PinAllocator
from microforge.core.catalog import Catalog, get_catalog
from microforge.core.codegen import FirmwareGenerator, sketch_name
from microforge.core.erc import run_erc
from microforge.core.models import BuildResult, ERCIssue, ProjectSpec, Severity
from microforge.core.netlist import build_nets
from microforge.core.outputs.bom import build_bom
from microforge.core.outputs.kicad import kicad_netlist
from microforge.core.outputs.soldering import soldering_guide
from microforge.core.outputs.svg import wiring_svg
from microforge.core.outputs.wiring import wiring_table
from microforge.core.outputs.wokwi import wokwi_diagram

PIO_PLATFORM = {
    "esp32": "espressif32",
    "avr": "atmelavr",
    "rp2040": "https://github.com/maxgerhardt/platform-raspberrypi.git",
}
PIO_LIBS = {
    "DHT sensor library": "adafruit/DHT sensor library",
    "Adafruit Unified Sensor": "adafruit/Adafruit Unified Sensor",
    "Adafruit SSD1306": "adafruit/Adafruit SSD1306",
    "Adafruit GFX Library": "adafruit/Adafruit GFX Library",
    "Adafruit BME280 Library": "adafruit/Adafruit BME280 Library",
    "Adafruit MPU6050": "adafruit/Adafruit MPU6050",
    "Adafruit NeoPixel": "adafruit/Adafruit NeoPixel",
    "RTClib": "adafruit/RTClib",
    "OneWire": "paulstoffregen/OneWire",
    "DallasTemperature": "milesburton/DallasTemperature",
    "LiquidCrystal I2C": "marcoschwartz/LiquidCrystal_I2C",
    "TM1637": "avishorp/TM1637",
    "ESP32Servo": "madhephaestus/ESP32Servo",
    "Servo": "arduino-libraries/Servo",
    "Stepper": "arduino-libraries/Stepper",
    "Keypad": "chris--a/Keypad",
    "MFRC522": "miguelbalboa/MFRC522",
    "HX711": "bogde/HX711",
    "SD": "arduino-libraries/SD",
}


class ProjectBuilder:
    """Génère tous les livrables d'un projet."""

    def __init__(self, catalog: Catalog | None = None) -> None:
        self.catalog = catalog or get_catalog()
        self.allocator = PinAllocator(self.catalog)
        self.firmware = FirmwareGenerator(self.catalog)

    def spec_from_template(self, template_id: str, board: str) -> ProjectSpec:
        """Instancie un modèle de projet sur une carte donnée."""
        tpl = self.catalog.templates[template_id]
        return ProjectSpec(
            title=tpl.title,
            description=tpl.description,
            board=self.catalog.board(board).id,
            parts=tpl.parts,
            uses_wifi=tpl.requires_wifi,
            logic=tpl.logic,
            setup_extra=tpl.setup_extra,
            globals_extra=tpl.globals_extra,
            template_id=tpl.id,
        )

    def build(self, spec: ProjectSpec) -> BuildResult:
        """Construit tous les livrables. Les erreurs électriques sont signalées, pas levées."""
        board = self.catalog.board(spec.board)
        alloc = self.allocator.allocate(spec)
        issues = [*alloc.issues, *run_erc(spec, alloc, self.catalog)]
        nets = build_nets(board, alloc)
        files: dict[str, str] = {}
        try:
            files = self.firmware.generate(spec, alloc)
        except ValueError as exc:
            issues.append(
                ERCIssue(
                    code="CODEGEN",
                    severity=Severity.ERROR,
                    message=str(exc),
                    fix="Corriger l'affectation des broches signalée ci-dessus.",
                )
            )
        firmware = next((v for k, v in files.items() if k.endswith(".ino")), "")
        result = BuildResult(
            spec=spec,
            board=board,
            assignments=alloc.assignments,
            added_parts=alloc.added_parts,
            nets=nets,
            issues=issues,
            bom=build_bom(spec, alloc, self.catalog),
            firmware=firmware,
            firmware_files=files,
            libraries=self.firmware.libraries(spec),
            wiring_table_md=wiring_table(spec, board, alloc, self.catalog),
            soldering_guide_md=soldering_guide(spec, board, alloc, self.catalog, nets, issues),
            wiring_svg=wiring_svg(spec, board, alloc, self.catalog),
            wokwi_diagram=wokwi_diagram(spec, board, alloc, self.catalog),
            kicad_netlist=kicad_netlist(spec, board, alloc, self.catalog, nets),
        )
        return result

    # ------------------------------------------------------------------ fichiers
    def files(self, result: BuildResult) -> dict[str, str]:
        """Tous les fichiers du projet, prêts à écrire ou zipper."""
        spec, board = result.spec, result.board
        name = sketch_name(spec.title)
        fw = result.firmware_files
        out = dict(fw)
        ino = fw.get(f"{name}/{name}.ino", "")
        header = fw.get(f"{name}/mf_components.h", "")
        out["cablage.md"] = result.wiring_table_md
        out["guide-montage.md"] = result.soldering_guide_md
        out["cablage.svg"] = result.wiring_svg
        out["wokwi/diagram.json"] = json.dumps(result.wokwi_diagram, indent=2, ensure_ascii=False)
        out["wokwi/sketch.ino"] = ino
        out["wokwi/mf_components.h"] = header
        if f"{name}/secrets.h" in fw:
            out["wokwi/secrets.h"] = fw[f"{name}/secrets.h"]
        out["wokwi/libraries.txt"] = "\n".join(result.libraries) + "\n"
        out["kicad/projet.net"] = result.kicad_netlist
        out["nomenclature.csv"] = "composant;désignation;quantité;prix unitaire €\n" + "".join(
            f"{b.component};{b.name};{b.quantity};{b.unit_price_eur or ''}\n" for b in result.bom
        )
        lib_deps = "\n    ".join(PIO_LIBS.get(lib, lib) for lib in result.libraries)
        out["platformio.ini"] = (
            f"; PlatformIO — {spec.title}\n[platformio]\nsrc_dir = {name}\n\n"
            f"[env:{board.platformio_board}]\nplatform = {PIO_PLATFORM[board.family]}\n"
            f"board = {board.platformio_board}\nframework = arduino\nmonitor_speed = 115200\n"
            + (f"lib_deps =\n    {lib_deps}\n" if result.libraries else "")
        )
        out["README.md"] = self.readme(result)
        return out

    def readme(self, result: BuildResult) -> str:
        spec, board = result.spec, result.board
        name = sketch_name(spec.title)
        status = "✅ aucun problème bloquant" if result.ok else "⛔ problèmes bloquants à corriger"
        issues = (
            "\n".join(
                f"- **{i.severity.value.upper()}** `{i.code}` — {i.message}"
                + (f" → {i.fix}" if i.fix else "")
                for i in result.issues
            )
            or "- aucun"
        )
        libs = " ".join(f'"{lib}"' for lib in result.libraries)
        return f"""# {spec.title}

{spec.description}

- Carte : **{board.name}** (`{board.fqbn}`)
- Contrôle électrique : {status}

## Contenu
| Fichier | Rôle |
|---|---|
| `{name}/{name}.ino` | programme principal (logique modifiable) |
| `{name}/mf_components.h` | broches, objets et fonctions des composants |
| `cablage.md` / `cablage.svg` | tableau et schéma de câblage |
| `guide-montage.md` | guide pas-à-pas breadboard -> soudure -> contrôles |
| `wokwi/` | simulation : créer un projet sur wokwi.com et y coller ces fichiers |
| `kicad/projet.net` | netlist à importer dans l'éditeur de PCB KiCad |
| `nomenclature.csv` | liste du matériel |
| `platformio.ini` | compilation avec PlatformIO |

## Compiler et téléverser (arduino-cli)
```bash
arduino-cli lib install {libs}
arduino-cli compile --fqbn {board.fqbn} {name}
arduino-cli upload --fqbn {board.fqbn} -p <PORT> {name}
```

## Contrôle électrique
{issues}

---
*Généré automatiquement par MicroForge (logique et textes pouvant provenir d'une IA — transparence AI Act art. 50). Vérifiez toujours le câblage avant la mise sous tension.*
"""

    def bundle(self, result: BuildResult) -> bytes:
        """Archive zip du projet complet."""
        buf = io.BytesIO()
        root = sketch_name(result.spec.title)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, content in self.files(result).items():
                zf.writestr(f"{root}/{path}", content)
        return buf.getvalue()

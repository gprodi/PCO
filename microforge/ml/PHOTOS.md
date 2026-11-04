# Photographier ses composants (jeu de test réel du détecteur, E3)

Le détecteur apprend d'abord sur **IoTKITs** (3 200 images publiques de cartes et kits, CC BY 4.0).
Tes photos servent à mesurer honnêtement ce qu'il vaut **sur ton matériel**, et à l'adapter (fine-tuning).
Une trentaine de composants suffit, à condition de varier les prises de vue.

## Combien de photos

| | Conseil |
|---|---|
| Par composant | 15 à 20 photos (≈ 450 à 600 images pour 30 composants) |
| Scènes mélangées | en plus, 30 à 50 photos de plusieurs composants ensemble (tiroir, plan de travail, montage sur breadboard) |
| Sans composant | une dizaine de photos du décor seul (images « négatives » : moins de fausses détections) |

## Varier (c'est ce qui compte)

- **Fonds** : bureau, table en bois, tapis de découpe, papier blanc, breadboard.
- **Lumière** : jour, lampe, pénombre ; un peu de reflets sur les écrans OLED et LCD.
- **Angles et distances** : de dessus, à 45°, de près (le composant remplit la photo) et de loin (petit).
- **Faces** : recto et verso des modules, broches visibles ou non.
- **Occultation** : composant à moitié caché par un fil ou un autre composant.

## Ranger les fichiers

```
microforge/data/sources/photos-gael/
├── source.yaml
├── arduino_uno/
│   └── uno-01/          ← un dossier par composant PHYSIQUE (pas par photo)
│       ├── IMG_0001.jpg
│       └── IMG_0001.txt ← labels YOLO (exportés par Label Studio)
├── resistor/
│   ├── r220-01/
│   └── r10k-01/
└── scenes/              ← photos de plusieurs composants : utiliser « scenes/<prise>/ »
    └── tiroir-01/
```

Le nom du dossier de premier niveau est indicatif ; c'est le label YOLO qui fixe la classe. Le dossier
`<composant>` sert de **groupe** : toutes ses photos vont dans le même split, sinon le modèle serait testé
sur un objet qu'il a déjà vu (fuite, score trop beau).

`source.yaml` :

```yaml
nom: photos-gael
licence: personnelle
attribution: "Gaël Prodi"
groupes: composant
ratios: [0.6, 0.2, 0.2]        # 30 composants -> ~18 entraînement, 6 validation, 6 test
names: [arduino_uno, resistor, led]   # ordre des classes de TON export Label Studio (classes.txt)
classes: {arduino_uno: arduino_uno, resistor: resistor, led: led}
```

## Annoter avec Label Studio (en local, avec Docker)

```bash
docker run -it -p 8080:8080 -v "$(pwd)/label-studio:/label-studio/data" heartexlabs/label-studio:1.23.2
```

1. http://localhost:8080 → nouveau projet → *Object Detection with Bounding Boxes* ;
   étiquettes = les noms de classes MicroForge (`arduino_uno`, `resistor`… liste dans `ml/data/dataset.yaml`).
2. Importer les photos d'un composant, tracer un rectangle serré autour de **chaque** composant visible.
3. *Export → YOLO* : copier les `.txt` à côté des photos et `classes.txt` dans `photos-gael/`.

Les photos restent sur ton ordinateur. `prepare.py` applique l'orientation puis **supprime les métadonnées
EXIF** (position GPS, modèle du téléphone) des images du dataset. Évite les visages, papiers et écrans
personnels dans le champ.

## Composants sans classe

Les 51 classes actuelles couvrent les cartes, modules, capteurs et passifs courants (condensateurs, diode,
transistor, quartz, bornier…). Si un de tes composants n'y est pas, envoie la liste : la classe est ajoutée à
`ml/data/dataset.yaml`, `src/microforge/vision/classes.yaml` et reliée au catalogue (vérifié par
`tests/test_ml_data.py`) **avant** l'annotation.

En priorité, photographie ce que les jeux publics couvrent mal (voir « Assez de données ? » dans
[`README.md`](README.md)) : modules et capteurs sans aucune image, puis quartz, bornier, trimmer, diode.

## Ensuite

```bash
uv run python microforge/ml/prepare.py --sources microforge/data/sources --out microforge/data/dataset --remplacer
uv run python microforge/ml/train.py --epochs 80                                   # PC avec GPU ou Colab
```

Le rapport E3 présente alors deux scores : sur le test IoTKITs (données publiques) et sur **tes 6 composants
de test jamais vus** (le chiffre qui compte pour l'application).

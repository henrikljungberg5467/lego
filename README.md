# John Deere Z315E ZTrak i LEGO

En byggbar LEGO-modell av nollsvängsklipparen John Deere Z315E med 42-tums klippaggregat, i skala 1:8. Chassi, länkhjul, klippaggregatets upphängning och styrspakar är byggda med Technic. Kaross, säte och klippaggregatets skal är byggda med vanliga klossar, på samma sätt som i LEGOs egna John Deere-set.

![Modellen sedd snett framifrån höger](renders/z315e-hero.png)

| | |
|---|---|
| Skala | 1:8 (bakdäck 56 mm = 18" i verkligheten, framhjul 30 mm) |
| Antal delar | 443 (111 olika del/färg-kombinationer) |
| Mått | ca 23 × 18 × 14 cm (L × B × H) |
| Färger | grön, gul, svart, mörk och ljus blågrå, en orange detalj |
| Filformat | LDraw MPD – öppnas i BrickLink Studio, LeoCAD eller LDCad |

## Funktioner

- Framhjulen är länkhjul som svänger fritt 360°. Gaffeln har efterföljning, så hjulen ställer in sig själva när modellen rullas.
- Bakhjulen sitter på var sin axel och rullar oberoende av varandra. Modellen kan därför snurra på stället, precis som en riktig zero-turn.
- Styrspakarna (lap bars) är ledade och kan fällas ut i parkeringsläge, som på fotot, eller fällas in i körläge.
- Klippaggregatet hänger i fyra stänger under ramen, som på originalet, och har rundade framhörn, kåpa över remskivan och utkastartrumma på höger sida.
- Fotstöd med John Deere-skylt, lyftpedal för klippaggregatet och tankkåpa.

## Bygga modellen

1. **Instruktioner:** öppna [`model/z315e.mpd`](model/z315e.mpd) i [BrickLink Studio](https://www.bricklink.com/v3/studio/download.page) (gratis). Filen innehåller byggstegen i nio delmoduler: bakram, drivhjul, golv och fotstöd, främre ram, länkhjul, klippaggregat, kaross, säte och styrspakar. Studios instruktionsläge gör en utskrivbar PDF av dem.
2. **3D-visare:** `viewer/index.html` visar modellen steg för steg med dellista för varje steg. Den publiceras även som Claude-artefakt.
3. **Köpa delar:**
   - BrickLink: ladda upp [`docs/bricklink_wanted.xml`](docs/bricklink_wanted.xml) under *Want → Upload*.
   - Rebrickable: importera [`docs/parts.csv`](docs/parts.csv) (Part, Color, Quantity). Därifrån kan listan skickas vidare till BrickLink eller LEGO Pick a Brick.
   - Hela listan med svenska färgnamn finns i [`docs/parts.md`](docs/parts.md).

Den enda ovanligare delen är den gröna Technic-balken 1 × 15 (32278). Den har funnits i sex set, bland annat LEGO 42157 John Deere 948L-II.

## Hur modellen är kontrollerad

Modellen är inte provbyggd fysiskt än, men den har kontrollerats digitalt med verktygen i `tools/`:

- **Delar och färger:** varje del/färg-kombination har slagits upp i Rebrickables lagerdata. Alla förekommer i officiella LEGO-set, och de automatiskt utlagda plattorna och klossarna använder bara kombinationer som funnits i minst tre set.
- **Anslutningar:** alla stift, axlar, hål och knoppar matchas mot anslutningsdata från LDCad Shadow Library. Alla 443 delar hänger ihop i en enda struktur, och inga stift sitter i fel sorts hål.
- **Kollisioner:** varje del voxeliseras med 1 LDU (0,4 mm) upplösning. Inga delar går in i varandra.

Saker som är förenklade jämfört med originalet:

- Dekalerna ingår inte som LEGO-delar. [`stickers/z315e_stickers.svg`](stickers/z315e_stickers.svg) är ett ark i skala 1:1 med "JOHN DEERE", "Z315E" och varningsetiketter, som kan skrivas ut på klisteretikettpapper. Hjortlogotyperna är inte med; den gröna runda brickan på sätet sitter där logotypen ska vara.
- Den gula randen på sidopanelen är rak. På originalet lutar den.
- Klippaggregatet sitter på fast höjd. Lyftpedalen är bara en detalj.

## Struktur

```
model/z315e.py        generator: hela modellen beskriven i Python (koordinater i LDU)
model/z315e.mpd       den genererade LDraw-modellen
docs/                 dellistor (BrickLink, Rebrickable, Markdown)
stickers/             dekalark att skriva ut
renders/              renderingar
viewer/               3D-visare med byggsteg (three.js + LDrawLoader)
tools/check.py        kontroll av anslutningar, kollisioner och färger
tools/render.mjs      rendering i headless Chromium
tools/partlist.py     dellistor
tools/build_viewer.py packar modellen med alla LDraw-delar för visaren
```

### Generera om

Verktygen behöver LDraw-biblioteket, [LDCad Shadow Library](https://github.com/RolandMelkert/LDCadShadowLibrary) och Rebrickables databas. Den sista finns som SQLite i npm-paketet `lego-oracle`. Sökvägarna anges med `LDRAW_LIB`, `LDCAD_SHADOW` och `REBRICKABLE_DB`.

```sh
npm install                                   # three.js + playwright
python3 model/z315e.py                        # skriver model/z315e.mpd
python3 tools/check.py model/z315e.mpd        # anslutningar, kollisioner, färger
python3 tools/partlist.py model/z315e.mpd docs
tools/views.sh model/z315e.mpd tmp/view       # granskningsbilder
python3 tools/build_viewer.py
```

## Fler vyer

| | |
|---|---|
| ![Framifrån vänster](renders/z315e-front-left.png) | ![Bakifrån](renders/z315e-rear.png) |
| ![Från sidan](renders/z315e-side.png) | ![Ovanifrån](renders/z315e-top.png) |

LDraw-delarna i `viewer/z315e_packed.mpd` kommer från LDraw.org-biblioteket (CC BY 4.0).

John Deere och ZTrak är varumärken som tillhör Deere & Company. LEGO är ett varumärke som tillhör LEGO Group. Det här är ett fristående hobbyprojekt.

# Experiment de visió (opcional)

**Estat:** preparat a la branca `berta/visio`, **desactivat** (`PREDICT_VISION=off`). Mentre estigui a `off`, `predict.py` fa exactament el mateix que abans.

## Què fa

El Qwen3.5 0.8B veu imatges si s'arrenca amb el fitxer projector (`mmproj`, 205 MB). L'experiment arrenca un **segon** `llama-server` (port 8083) amb el mateix model i el projector. El servei oficial `math-llm` (8081) no es toca. El model és el mateix fitxer i es comparteix a la RAM (mmap): el projector i el context són l'únic extra.

Amb `PREDICT_VISION=figure`, `solve()` envia la imatge del problema **només** quan el text no hi arriba:

- `text_only` és fals (el problema té figura), o
- l'OCR no ha trobat les 5 opcions (avui aquests reben la D sense preguntar al model).

Si no es compleixen aquestes condicions, el problema va per la via de text de sempre:

- falta la imatge;
- el servidor no respon o no veu imatges;
- queden menys de `VISION_SECONDS` (40 s);
- la crida amb imatge falla.

Amb imatge mai es fan rotacions (cada passada tornaria a llegir la imatge, ~30 s).

**On busca la imatge `predict.py`** (`<id>_<language>.png`):
1. El camp `image` de la línia del JSONL, si n'hi ha.
2. La carpeta `images/` al costat del fitxer d'entrada.
3. La mateixa carpeta del fitxer d'entrada.
4. `data/images`.

## Abans de res: preguntar als organitzadors

> Els 20 problemes del test final, porten la imatge? En quin format: un camp `image` al JSONL, una carpeta `images/` amb `<id>_<language>.png` al costat del fitxer, o res? I porten el camp `text_only`?

**Si no porten imatge, l'experiment no serveix per al test**: no el feu i expliqueu-ho al README com a "no fet". Si en porten però amb un altre nom o format, cal adaptar `image_path()` a `copilot/pipeline.py` (és curt).

## Passos

### 1. Portàtil: les imatges (sense placa, uns 20–30 min)

Des de `projecte/`, amb les mateixes opcions que es van fer servir per a les dades (shard 0, `eng,cat`). Les opcions no cal tornar-les a llegir:

```bash
python laptop/prepare_m3kang.py --languages eng,cat --no-ocr --save-images --out data/_imgs
python prep/pick_images.py --images data/_imgs/images --out data/images data/dev50.jsonl data/dev100.jsonl data/val.jsonl
```

`pick_images.py` copia només les imatges dels problemes amb figura i diu quantes en falten (n'han de faltar 0). Les imatges són M3Kang: **mai es pugen** (`data/` ja és a `.gitignore`).

### 2. Portar-ho a la placa

Copieu a `~/Datathon_FME/projecte/` de la placa (amb `adb push` o `scp`):
- el codi: `copilot/pipeline.py`, `predict.py`, `eval.py`, `config.env`;
- els fitxers de la placa: `board/07_vision.sh`, `board/systemd/math-vision.service`;
- la carpeta `data/images/`.

**Compte, fitxers de Windows:** al portàtil tenen finals de línia CRLF, i bash no els entén. A la placa, després de copiar:

```bash
cd ~/Datathon_FME/projecte
sed -i 's/\r$//' config.env board/*.sh board/systemd/*.service
chmod +x board/07_vision.sh
```

Avisa l'equip abans de copiar res (vegeu `PROBLEMES.md` 14): durant l'experiment, ningú més no fa servir la placa.

### 3. Placa: engegar el servidor de visió (uns 5 min)

```bash
sudo systemctl stop math-tutor           # allibera RAM i el model; el tornem a engegar al final
./board/07_vision.sh download            # 205 MB, comprova el SHA256 (cal xarxa a la placa)
./board/07_vision.sh start               # comprova la RAM, arrenca al 8083 i que "vegi" imatges
./board/07_vision.sh status
```

Apunta la RAM disponible que surt després de `start`.

### 4. Placa: prova curta (2 min)

```bash
python3 eval.py --input data/dev50.jsonl --only-figure --vision figure --limit 2 --name vision-smoke
```

A la taula "By whether the image was sent" hi ha de sortir `1`, i cap temps per sobre de 57 s.

### 5. Placa: l'experiment (uns 35–60 min)

Feu servir els **mateixos** paràmetres que la configuració triada a la segona ronda (per exemple `--debias auto`, `--rag …`), i canvieu només `--vision`.

**A. Problemes amb figura i amb opcions** (`dev100`: 38 problemes, ~6 min sense imatge i ~22 min amb):

```bash
python3 eval.py --input data/dev100.jsonl --only-figure --limit 0 --name fig-dev100-text
python3 eval.py --input data/dev100.jsonl --only-figure --limit 0 --vision figure --name fig-dev100-vision
```

**B. Problemes amb figura, amb opcions i sense** (on hi ha més a guanyar: sense opcions, avui és la D). Feu-ho només si queda temps (uns 25 min):

```bash
python3 eval.py --input data/val.jsonl --only-figure --languages eng --limit 40 --name fig-val40-text
python3 eval.py --input data/val.jsonl --only-figure --languages eng --limit 40 --vision figure --name fig-val40-vision
```

Tot queda a `results/ablations.csv`. A la sortida, comproveu:
- `worst` (pitjor temps) i `over 60 s` (`over_limit` a `ablations.csv`);
- l'encert "By whether OCR found the options";
- "By whether the image was sent".

### 6. Placa: deixar-la com estava

```bash
./board/07_vision.sh stop
sudo systemctl start math-tutor
```

## Com es decideix

S'adopta **només si es compleixen totes quatre condicions**:
1. Els organitzadors confirmen que el test porta la imatge.
2. Amb imatge s'encerta clarament més que sense, en A (i en B si s'ha fet). Amb 38–40 problemes, menys de 4–5 encerts de diferència és soroll: en aquest cas no s'adopta.
3. `worst_s` ≤ 57 s i `over_limit` = 0.
4. La RAM disponible es manté per sobre de ~500 MB amb tot engegat (també el tutor).

**Si s'adopta**, abans del *last call*:

```bash
# config.env: PREDICT_VISION=figure
./board/07_vision.sh install-service      # arrenca sol amb la placa
sudo reboot                               # i comproveu-ho: ./board/07_vision.sh status
python3 eval.py --input data/demo/train.jsonl --limit 0 --name practica-vision   # conjunt de pràctica: troba data/demo/images sol
```

I afegiu la decisió a `DECISIONS.md`.

**Per desfer-ho:** `PREDICT_VISION=off` a `config.env` i `./board/07_vision.sh remove-service`.

## Proves sense placa

`python -m unittest tests.test_all.Vision -v`: 9 proves amb el servidor simulat. Comproven que la imatge només s'envia quan toca, i que qualsevol fallada torna a la via de text. **No diuen res de l'encert real.**

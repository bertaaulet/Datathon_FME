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

## Execució del 15 de novembre (pas a pas)

Durada: **~1 h** (part A) i **+25 min** si es fa la B. Mentrestant la placa està ocupada i el tutor aturat. Els passos generals de més avall són la referència; aquí hi ha les comandes exactes d'avui.

**0. Abans.** Pregunteu als organitzadors si el test porta la imatge (secció anterior). Aviseu l'equip.

**1. Portàtil (20–30 min, en paral·lel amb els passos 2–4).** GitHub Desktop: *Fetch origin* i branca `berta/visio`. Des de `projecte/`:

```bash
python laptop/prepare_m3kang.py --languages eng,cat --no-ocr --save-images --out data/_imgs
python prep/pick_images.py --images data/_imgs/images --out data/images data/dev50.jsonl data/dev100.jsonl data/val.jsonl
```

Ha de dir que en falten 0.

**2. Placa: còpia de seguretat i codi (10 min).**

```bash
adb shell
cd ~/Datathon_FME/projecte
cat ~/Datathon_FME/DESPLEGAT
mkdir -p ~/visio-backup && cp copilot/pipeline.py predict.py eval.py config.env ~/visio-backup/
echo "visio · <nom> · berta/visio · $(date)" > ~/Datathon_FME/DESPLEGAT
exit
```

Des del portàtil, a `projecte/`:

```bash
adb push copilot/pipeline.py /home/arduino/Datathon_FME/projecte/copilot/
adb push predict.py eval.py /home/arduino/Datathon_FME/projecte/
adb push board/07_vision.sh /home/arduino/Datathon_FME/projecte/board/
adb push board/systemd/math-vision.service /home/arduino/Datathon_FME/projecte/board/systemd/
```

**No copieu `config.env`**: el de la placa té `HINTGEN=off` i `KANGAROO_LANG=cat`. Afegiu-hi només la visió (a la placa, una línia cada vegada):

```bash
adb shell
cd ~/Datathon_FME/projecte
echo "PREDICT_VISION=off" >> config.env
echo "PREDICT_IMAGES=data/images" >> config.env
echo "VISION_PORT=8083" >> config.env
echo "VISION_SECONDS=40" >> config.env
echo "VISION_IMAGE_TOKENS=128" >> config.env
echo "MMPROJ_FILE=mmproj-Qwen_Qwen3.5-0.8B-f16.gguf" >> config.env
echo "MMPROJ_SHA256=1dc1351c82e41b48edb55fd6ddfa7ca60fb5a16b3d5abf3ce7054880dd022847" >> config.env
sed -i 's/\r$//' config.env board/*.sh board/systemd/*.service copilot/pipeline.py predict.py eval.py
chmod +x board/07_vision.sh
grep -E '^PREDICT_(DEBIAS|RAG_K)|^HINTGEN' config.env
ls data/dev100.jsonl
```

El `grep` ha de mostrar `HINTGEN=off`.

**3. Placa: part A sense imatge (6 min).** Configuració guanyadora de la segona ronda: biaix del fitxer, sense RAG. Les tasques llargues sempre amb `systemd-run` (`PROBLEMES.md` 15):

```bash
echo 'cd ~/Datathon_FME/projecte && python3 eval.py --input data/dev100.jsonl --only-figure --limit 0 --debias auto --rag 0 --name fig-dev100-text > ~/visio-text.log 2>&1' > ~/visio-text.sh
XDG_RUNTIME_DIR=/run/user/1000 systemd-run --user --unit=visio-text bash ~/visio-text.sh
tail -f ~/visio-text.log
```

Espereu que acabi (Ctrl+C només talla el `tail`, no l'experiment).

**4. Placa: servidor de visió (5–10 min).**

```bash
sudo systemctl stop math-tutor
./board/07_vision.sh download
./board/07_vision.sh start
./board/07_vision.sh status
free -m
```

Apunteu la RAM disponible. Si la placa no té xarxa: baixeu al portàtil `https://huggingface.co/bartowski/Qwen_Qwen3.5-0.8B-GGUF/resolve/f36b1ea49a332ede8fe5f389bbf5b3575ef71f48/mmproj-Qwen_Qwen3.5-0.8B-f16.gguf`, feu `adb push` a `/home/arduino/models/` i torneu a fer `download` (comprova el SHA256).

**5. Imatges i prova curta (5 min).** Des del portàtil: `adb push data/images /home/arduino/Datathon_FME/projecte/data/`. A la placa:

```bash
python3 eval.py --input data/dev50.jsonl --only-figure --vision figure --limit 2 --debias auto --rag 0 --name vision-smoke
```

"By whether the image was sent" ha de mostrar `1` i cap temps per sobre de 57 s. Si no, pareu i aviseu.

**6. Part A amb imatge (~22 min).**

```bash
echo 'cd ~/Datathon_FME/projecte && python3 eval.py --input data/dev100.jsonl --only-figure --limit 0 --debias auto --rag 0 --vision figure --name fig-dev100-vision > ~/visio-vision.log 2>&1' > ~/visio.sh
XDG_RUNTIME_DIR=/run/user/1000 systemd-run --user --unit=visio bash ~/visio.sh
tail -f ~/visio-vision.log
```

Part B (opcional, +25 min): el mateix amb `--input data/val.jsonl --only-figure --languages eng --limit 40`, sense i amb `--vision figure` (noms `fig-val40-text` i `fig-val40-vision`).

**7. Deixar la placa com estava (2 min).**

```bash
./board/07_vision.sh stop
sudo systemctl start math-tutor
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/api/state
echo "tutor restaurat · visio off · $(date)" >> ~/Datathon_FME/DESPLEGAT
```

`curl` ha de dir `200`. Amb `PREDICT_VISION=off`, `predict.py` fa el mateix que abans. Si hi ha dubtes, es pot tornar enrere amb els fitxers de `~/visio-backup/`.

**8. Resultats a Git.** Des del portàtil:

```bash
adb pull /home/arduino/Datathon_FME/projecte/results/ablations.csv ablations-placa.csv
```

Fora de `projecte/` (per no barrejar-lo). Després, a GitHub Desktop: branca nova des de `main` (`<nom>/visio-resultats`); afegiu al final de `projecte/results/ablations.csv` només les files noves (`fig-dev100-*`, `vision-smoke` i, si n'hi ha, `fig-val40-*`); una línia a `docs/STATUS.md` amb els resultats i la RAM, i la decisió (s'adopta o no, amb el criteri de més avall) a `docs/DECISIONS.md`. A *Changes* només hi pot haver aquests tres fitxers: res de `data/` (imatges), cap `results/eval-*.csv` ni `config.env`. Commit, *Push origin* i PR a `main`.

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
- el codi: `copilot/pipeline.py`, `predict.py`, `eval.py`. **No copieu `config.env`**: el de la placa té valors propis (`HINTGEN=off`, `KANGAROO_LANG=cat`). Afegiu-hi només les línies de visió (`PREDICT_VISION` … `MMPROJ_SHA256`) al final;
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

Llanceu les comandes llargues dins d'un script amb `XDG_RUNTIME_DIR=/run/user/1000 systemd-run --user --unit=visio bash ~/visio.sh`, no directament des d'`adb shell`: si cau l'USB, moririen (`PROBLEMES.md` 15).

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

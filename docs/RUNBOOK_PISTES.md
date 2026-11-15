# Preparar les pistes: passos per executar (portàtil i placa)

Per a qui tingui **llama.cpp i els dos models al portàtil** (com quan es va fer el primer `tutor.db`). Si en algun pas el que surt no s'assembla a l'esperat, para i avisa la Berta abans de continuar.

**Per què cal fer-ho.** El codi nou de pistes ([`PISTES.md`](PISTES.md)) necessita una base del tutor (`data/tutor.db`) actualitzada: només problemes del train, el Cangur calculat en català i les 2 pistes de l'agent per a cada problema.

**Temps total:** uns 30 minuts de màquina, més el temps de l'agent i de revisar-ne les pistes.

> **Mai pujar a Git** `data/tutor.db`, res de `data/agent/` ni `results/*.csv` amb ids: porten text o etiquetes de M3Kang. `.gitignore` ja els exclou; no facis `git add -f`.

---

## 0. Abans de començar

Tot es fa des de la carpeta `projecte/` del repo, al mateix entorn (WSL o Windows) on vas fer el `tutor.db` la primera vegada.

```bash
git fetch
git checkout berta/pistes-flux-nou        # o main, si ja s'ha fusionat
python3 -m unittest discover -s tests     # ha d'acabar amb "OK"
ls data/train.jsonl data/val.jsonl data/tutor.db
cp data/tutor.db data/tutor-backup.db     # còpia de seguretat
```

- [ ] Les proves diuen `OK`.
- [ ] Hi ha `train.jsonl`, `val.jsonl` i `tutor.db` (si `train.jsonl` és de la primera volta d'OCR, avisa: s'hauria de fer amb el de la segona).

## 1. Engegar els dos servidors

Són els dos models, engegats com a programes que esperen preguntes. Cal **un terminal per a cadascun**, i s'han de deixar oberts fins al pas 5.

| Servidor | Model | Per a què | Port |
|---|---|---|---|
| Del model | Qwen 0,8B | Fa de Cangur | 8081 |
| D'embeddings | bge-small | Troba problemes semblants | 8082 |

Les comandes són les de [`PLA.md`](PLA.md), apartat "El model al portàtil" (o el binari de Windows `b12311` que diu `DECISIONS.md`). Comprova que responen, des d'un tercer terminal:

```bash
curl -s http://127.0.0.1:8081/health     # {"status":"ok"}
curl -s http://127.0.0.1:8082/health     # {"status":"ok"}
python3 prep/check_model.py              # comprova que el model dona les probabilitats de les lletres
```

- [ ] Tots dos diuen `ok`.

## 2. Refer la base del tutor (~5 min)

Necessita el servidor d'embeddings.

```bash
python3 prep/build_tutor_db.py --show-topics 50
```

**Què fa:** marca com a utilitzables només els problemes del **train** que tenen text, les 5 opcions llegibles i versió en català, i en recalcula els 5 veïns. No esborra l'alumne, els intents ni les pistes que ja hi hagi.

**Què ha de sortir:** una línia com `the tutor can use N (training only, text-only, five readable options, with eng and cat versions)` i `neighbours: embeddings`.

- [ ] Apunta **N** (problemes utilitzables): ______
- [ ] Diu `neighbours: embeddings` (si diu `same topic, closest rating`, el servidor d'embeddings no responia: torna'l a engegar i repeteix el pas).
- [ ] Mira els 50 problemes que imprimeix: el tema és correcte? Apunta quants sí: ____ / 50

## 3. El Cangur en català (~5 min al portàtil)

Necessita el servidor del model.

```bash
python3 prep/kangaroo_baseline.py --redo
```

**Què fa:** per a cada problema, pregunta al model (en català, amb la pista neutra "Pensa-ho bé.") quina opció tria, i ho desa. Si s'atura, torna-ho a executar **sense** `--redo` i continua on era.

**Què ha de sortir:** `N problems measured in cat. The model prefers a wrong option in X of them; in the other Y the Kangaroo pretends.`

- [ ] Apunta **X** i **Y**: ______ / ______ (abans, en anglès, era 78 % / 22 %).

## 4. El banc de pistes de l'agent

Dues pistes ordenades per problema (pas 1: per on començar; pas 2: el pas següent). Les escriu un agent (Claude Code al portàtil, o la Berta amb Claude si li passes la carpeta). Es fa **per lots de 100**, numerats `01`, `02`…, fins que l'export doni 0 línies.

### 4a. Exportar un lot

```bash
python3 prep/agent/export_batch.py --kind hint_bank --n 100 \
  --out data/agent/hint_bank_in_01.jsonl --skip data/agent/hint_bank_out_*.jsonl
```

Ha de dir `Wrote 100 lines to data/agent/hint_bank_in_01.jsonl`. Al lot següent, canvia `01` per `02` (el `--skip` ja deixa fora els problemes fets).

### 4b. L'agent escriu les pistes

Obre Claude Code a `projecte/` i demana-li exactament:

> Llegeix `prep/agent/README.md` i `prep/agent/hint_bank.md`. Processa `data/agent/hint_bank_in_01.jsonl` i escriu el resultat a `data/agent/hint_bank_out_01.jsonl`: dues pistes per problema, una amb `"step": 1` i una amb `"step": 2`, seguint totes les regles. No facis commits ni copiïs cap text de problema fora de `data/`.

### 4c. Validar

```bash
python3 prep/check_agent_output.py data/agent/hint_bank_out_01.jsonl --kind hint_bank
```

Escriu les vàlides a `data/agent/hint_bank_out_01_ok.jsonl` i diu `hint_bank: K/200 lines passed`.

- Si n'hi ha de rebutjades, passa-li a l'agent les línies d'error ("torna a escriure aquestes pistes amb aquests motius") i torna a validar.
- [ ] Lot 01: ____ / 200 vàlides.

### 4d. Revisar-ne 20 a mà

Obre `data/agent/hint_bank_out_01_ok.jsonl` i, per a 20 pistes a l'atzar, mira el problema (a `data/train.jsonl`, pel mateix `id`) i comprova:

- és correcta matemàticament per a aquest problema;
- no dona la resposta ni descarta opcions;
- el pas 2 continua el pas 1 i, llegides juntes, no deixen el problema resolt.

- [ ] Lot 01: ____ / 20 correctes. (Aquest número es publica.)

### 4e. Importar

```bash
python3 prep/import_hints.py data/agent/hint_bank_out_01_ok.jsonl
```

Ha de dir `Added K hints with source='agent'`. Si el tornes a executar no duplica res.

**Repeteix 4a–4e per a cada lot** fins que l'export digui `Wrote 0 lines`.

## 5. Passar les pistes de l'agent pel Cangur (~10 min al portàtil)

Necessita el servidor del model i el pas 3 fet.

```bash
python3 prep/kangaroo_agent_hints.py
```

**Què ha de sortir:** `M agent hints measured. Where the Kangaroo was really wrong (R), C convinced it.` També escriu `results/agent-hints-kangaroo.csv` (per al dashboard; no es puja).

- [ ] Apunta **M**, **R** i **C**: ______ / ______ / ______

Ja pots tancar els dos servidors.

## 6. Copiar la base a la placa

Això **substitueix** la base de la placa (també l'alumne i els intents de proves). Amb la placa connectada per USB:

```bash
adb shell cp /home/arduino/Datathon_FME/projecte/data/tutor.db /home/arduino/Datathon_FME/projecte/data/tutor-backup.db
adb push data/tutor.db /home/arduino/Datathon_FME/projecte/data/tutor.db
```

La placa també ha de tenir **el codi nou**: copia-hi el repo actualitzat (la branca o `main` un cop fusionada), com es va fer la primera vegada, i després reinicia el tutor:

```bash
adb shell sudo systemctl restart math-tutor
adb shell systemctl is-active math-tutor     # active
```

## 7. Comprovar-ho a la placa

`adb forward tcp:8090 tcp:8090` i obre <http://127.0.0.1:8090>. Prova:

- [ ] **Fallar un problema i demanar ajuda 5 vegades:** tema i mètode → "Una pista: «…»" → "Una altra pista: «…»" → un problema semblant amb botons, sense la resposta → la solució.
- [ ] Al problema semblant, respondre: surt la resposta i ja no deixa tornar a respondre.
- [ ] **Encertar un problema:** el Cangur diu una opció incorrecta i "n'estic un X % segur". Escriure una pista amb la resposta ("és la C"): la rebutja i no gasta cap intent. Escriure una pista bona: el Cangur respon en ~10 s.
- [ ] **Vista del docent:** mostra els comptadors de pistes ("N l'han convençut, …").
- [ ] **Problema extern** (enganxa un problema inventat amb opcions A–E): surt l'avís; demana ajuda al cap d'uns 60 s i mira si el graó 2 és una pista escrita pel model. Apunta quant ha trigat: ______ s
- [ ] La matriu LED mostra el tic, la creu i la barra.

## 8. Al final

Passa a la Berta (o apunta a `docs/STATUS.md`, fila "Pistes") els números de les caselles: N, temes correctes, X/Y, vàlides i correctes per lot, M/R/C, i el temps de la pista generada. **Només números**, mai text de problemes.

---

### Si alguna cosa falla

| Missatge | Què vol dir | Què fer |
|---|---|---|
| `The embedding server didn't answer` | El servidor 8082 no respon | Engega'l (pas 1) i repeteix el pas 2 |
| `The stored answers were measured in eng…` | Falta `--redo` | `python3 prep/kangaroo_baseline.py --redo` |
| `Run prep/kangaroo_baseline.py first` | El pas 5 abans del 3 | Fes el pas 3 |
| `Connection refused` en qualsevol script | El servidor del model no està engegat | Pas 1 |
| `this problem isn't eligible` a la validació | L'export és d'abans de refer la base | Torna a exportar després del pas 2 |
| L'export diu `Wrote 0 lines` al primer lot | No hi ha problemes utilitzables | Revisa el pas 2 (N no pot ser 0) |

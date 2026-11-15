# Arduino Project Hub: text per enganxar

_2026-11-15. Esborrany preparat a partir de `projecte/README.md` (versió de `main` a les 10:45). Quan el README estigui revisat, cal **repassar les xifres marcades amb ⟳** perquè coincideixin._

## Com es publica

1. Inicia sessió a <https://projecthub.arduino.cc/> amb un compte d'Arduino i prem **+ New project**.
2. Omple els camps de la fitxa (secció A) i els components (secció B).
3. A la descripció del projecte, enganxa les seccions C1–C7 en ordre. Cada `##` és un títol de secció de l'editor.
4. Puja les imatges de la secció D on diu `[IMATGE: …]`.
5. A **Code**, enllaça el repositori de GitHub: ha de ser **públic** abans d'enviar l'enllaç.
6. Desa'l com a esborrany, revisa'l amb la vista prèvia i publica'l. Envia els dos enllaços (GitHub i Project Hub) als organitzadors.

**Llicència de M3Kang (només recerca):** cap enunciat, imatge ni resposta de M3Kang al Hub. Les captures del tutor s'han de fer amb els **problemes inventats** (secció D). Res de `imatges_visio_nit/`.

---

## A. La fitxa del projecte

- **Title:** Teach the Kangaroo: an offline math tutor on the Arduino UNO Q
- **Short description:** A math tutor that runs fully offline on an Arduino UNO Q. Students solve Kangaroo problems, then teach a weak AI classmate, without giving the answer away.
- **Cover image:** `[IMATGE 1]` (la placa amb la matriu LED i el tutor obert al costat)
- **Difficulty:** Advanced
- **Duration:** about 6 hours on a board already set up with the organizers' steps 0–12
- **Tags:** Arduino UNO Q, LLM, edge AI, llama.cpp, education, math, offline, LED matrix
- **License:** MIT
- **Code:** <https://github.com/bertaaulet/Datathon_FME> (the code is in `projecte/`)

## B. Components and supplies

**Hardware**

| Component | Quantity |
| --- | --- |
| Arduino UNO Q 4 GB | 1 |
| USB-C power supply (a stable one: a weak USB link rebooted our board during long runs) | 1 |
| A laptop, to prepare the data and open the tutor over USB | 1 |

**Software apps and online services**

| Software | What for |
| --- | --- |
| Arduino App Lab | Board setup and the LED matrix app |
| llama.cpp (commit `2cbe0ec`) | Runs both models on the board |
| Qwen3.5 0.8B, Q8_0 GGUF (bartowski) | The language model: the Kangaroo, and `predict.py` |
| bge-small-en-v1.5, Q8_0 GGUF (CompendiumLabs) | Embeddings: similar problems |
| Python 3, standard library only | The tutor, the web page and `predict.py` |
| RapidOCR (laptop only) | Reads the answer options from the M3Kang images |
| M3Kang dataset (Qualcomm, research use only) | The problems, their answers, levels and languages |

---

## C1. Introduction

PISA and Kangaroo problems are long texts. A student who doesn't read the classroom language well fails before the maths even starts. And a classroom can't always rely on the internet, or send its students' data to a cloud service.

**Teach the Kangaroo** is a math tutor that runs entirely on an Arduino UNO Q 4 GB, offline. Built for the Qualcomm challenge "Math on the Edge" at the Datathon FME 2026 (UPC).

The language model that fits on the board, Qwen3.5 0.8B, answers Kangaroo problems close to random: the organizers measured 22.5% on 40 problems, below always answering "D". So it can't be the teacher. We turned that around:

1. **The student solves a problem** from the M3Kang bank. M3Kang knows the right answer, so checking is exact.
2. **If they're wrong**, they get help one rung at a time: the topic and a method, a first hint, a second hint, a similar easier problem to try, and the solution only if they ask for it.
3. **If they're right**, they **teach the Kangaroo**: a weak classmate played by the model, which always starts with a wrong answer. The student writes a hint, and a leak filter rejects any hint that gives the answer away. A clean hint convinces the Kangaroo, and its bar goes up on the screen and on the LED matrix.
4. **A language bridge** helps students who are still learning Catalan: the problem in their language next to Catalan, then Catalan with a button, then Catalan only.
5. **The next problem** is chosen with Elo ratings: hard enough to learn from, easy enough to keep going.

The model never writes text for the student. It only reports how likely it finds each letter, in one token. Everything the Kangaroo says is a sentence written by the team.

`[IMATGE 2]` · `[VÍDEO]` (el vídeo de la demo, si es publica)

## C2. Architecture

`[IMATGE 3: diagrama d'arquitectura]`

| Piece | Runs on | What it does |
| --- | --- | --- |
| Web page (`app/index.html`) | The student's browser | Shows the problem, takes the answer and the hint |
| Tutor (`app/server.py`, `copilot/tutor.py`) | Linux on the board, port 8090 | The flow, the leak filter, Elo ratings, calls to the model |
| Language model server (llama.cpp) | Linux on the board, port 8081 | Returns a probability for each letter A–E |
| Embedding server (llama.cpp) | Linux on the board, port 8082 | Finds similar problems |
| SQLite (`data/tutor.db`) | Linux on the board | The student, attempts, hints, ratings, problem texts |
| App Lab app (`applab/math-matrix`) | Linux + microcontroller | Reads the tutor's picture and draws it on the 8×13 LED matrix through the Bridge |

**How the LED matrix works.** The tutor decides what to show (a question mark, a cross, a tick, the Kangaroo's bar) and serves it as an 8×13 grid at `/api/led`. The App Lab app, in Python on the Linux side, reads that grid a few times a second and sends it to the microcontroller through the Bridge. All the logic stays in the tutor, so the tutor also works without the matrix.

**How we use M3Kang:**
- as the **answer key**, so checking is exact;
- as a **difficulty map**: the level and the position in the paper give each problem a fixed Elo rating;
- as a **library of similar problems**, with embeddings;
- as the **same problem in several languages**, for the language bridge;
- as the base of a **bank of hints** written ahead of time by an agent on the laptop (two ordered hints per problem, all through the leak filter).

## C3. Step by step

Start from a board set up with steps 0 to 12 of the organizers' guide (`projecte/docs/SETUP.md` in our repository): llama.cpp built, both models running as services, `data/train.jsonl` and `data/val.jsonl` on the board, and `data/index.db` built. All the commands below run on the board, from the `projecte/` folder, unless they say otherwise.

### Step 1: Check the model server

```bash
python3 prep/check_model.py
```

It checks that the server reports a probability for each letter, and that a second call with a hint only reads the hint. Takes about 2 minutes.

### Step 2: Measure the baseline and the letter bias

```bash
python3 eval.py --limit 50 --name baseline
python3 prep/letter_bias.py
python3 eval.py --limit 50 --name debias
```

`letter_bias.py` measures how often the model says each letter whatever the problem (about 10 minutes). `predict.py` divides by it. Every run adds a line to `results/ablations.csv`.

### Step 3: Build the tutor's database

On the laptop, prepare the languages you want, then copy `data/` to the board:

```bash
python laptop/prepare_m3kang.py --languages eng,cat,esp,fra,arb,zho --save-images
```

On the board:

```bash
python3 prep/build_tutor_db.py --show-topics 50
```

It prints 50 problems with their topic: check them by hand.

### Step 4: Ask the Kangaroo every problem once, and import the hints

```bash
python3 prep/kangaroo_baseline.py
python3 prep/import_hints.py data/agent_hints.jsonl
python3 prep/kangaroo_agent_hints.py
```

The first one runs overnight on the board and continues where it stopped. The hint bank is written on the laptop by an agent (`prep/agent/hint_bank.md`) and checked with `prep/check_agent_output.py`.

### Step 5: The go / no-go test for the hints

```bash
python3 prep/hint_experiment.py --make-template 25
python3 prep/hint_experiment.py
```

Fill in a good hint, a nonsense hint and a hint with the answer for each problem. If good and nonsense hints move the Kangaroo alike, the bar can't judge hints (that's what we found, see Results).

### Step 6: Start the tutor as a service

```bash
TUTOR_HOST=0.0.0.0 ./board/06_install_tutor_service.sh
```

On the laptop, over USB:

```bash
adb forward tcp:8090 tcp:8090
```

Then open <http://127.0.0.1:8090>. You should see "Hola! Comencem?".

`[IMATGE 4]`

### Step 7: The LED matrix

Copy `applab/math-matrix` to `/home/arduino/ArduinoApps/` on the board and start it from App Lab as the default app. You should see a question mark; a tick or a cross after each answer; and the Kangaroo's bar when you teach it. It also starts after a reboot.

`[IMATGE 5]`

### Step 8: The official run

```bash
python3 predict.py --input problems.jsonl --output predictions.csv
```

One letter per problem, at most 60 seconds each, and it never stops on an error. The settings are in `config.env`.

## C4. Results

All measured on the board. With 100 problems, the 95% interval is about ±8 points: we say when a difference is noise. ⟳

**`predict.py` on the organizers' 100 practice problems** (20 with each right letter, 50 English and 50 Catalan):

| Configuration | Accuracy (95% interval) | Letters said A/B/C/D/E | Mean / worst time |
| --- | --- | --- | --- |
| Organizers' baseline (their 40 problems, for reference) | 22.5% | — | 8.7 / 12.7 s |
| The model's letter, no correction | 22% (15–31%) | 18/7/0/73/2 | 7.6 / 11.9 s |
| **Final: letter bias corrected** | **25% (18–34%)** | 21/24/20/18/17 | 7.6 / 12.2 s |

No problem got near the 60 s limit. The correction spreads the letters out (D falls from 73 to 18) and wins 3 problems, but that is within noise (16 won, 13 lost on the same problems, p = 0.71). ⟳

**The tutor on the board:**
- **Can the Kangaroo tell a good hint from a nonsense one?** 25 problems where it's wrong, three hints each. Median shift towards the right answer: good +0.11, nonsense +0.10, with the answer +0.26. Same problem, good against nonsense: 13 to 11, p = 0.84. **No.** So a clean hint now convinces the Kangaroo, and the shift is only stored.
- **Leak filter:** it stopped 23 of the 24 hints that gave the answer away, and none of the good or nonsense ones.
- **Time:** the Kangaroo reads a hint in 11.5 s (median), 15.0 s at worst. A help rung without the model is instant.
- **End to end** (`prep/tutor_smoke.py`): 67/67 checks passed, with at least 2.7 GB of RAM free.

`[IMATGE 6: captura del dashboard]`

## C5. Error analysis

The final configuration on the organizers' 100 practice problems. Groups under 10 problems only point a direction. ⟳

| By language | Right | Accuracy (95% interval) |
| --- | --- | --- |
| Catalan | 14/50 | 28% (17–42%) |
| English | 11/50 | 22% (13–35%) |

| By level | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Right | 2/16 | 6/16 | 4/14 | 4/12 | 1/12 | 3/10 | 1/10 | 4/10 |

| By topic (keywords) | Right | Accuracy |
| --- | --- | --- |
| Numbers and divisibility | 10/38 | 26.3% |
| Geometry | 3/18 | 16.7% |
| Time and calendar | 4/12 | 33.3% |
| Arithmetic and word problems | 2/10 | 20% |

What it says:
- **The model barely reads the problem.** Every group sits inside the interval of random guessing (20%). Level 0, the easiest, gets 12.5%.
- **Its errors are a letter preference, not a maths mistake.** Without the correction it answers D 73 times out of 100. The correction removes that, and that's all it can do.
- **Geometry is the weakest topic** (3/18): the problems depend on the figure, which the model never sees. Sending it the image didn't help (4/10 against 5/10 for the most common letter, at 36 s per problem).

That's why the model plays a classmate to teach, and M3Kang is the answer key.

## C6. What didn't work, and what we learned

- **Similar solved problems in the prompt (RAG):** 20% instead of 24%, twice the time; the model copied the neighbour's letter.
- **An expression computed by Python:** the same accuracy, three times slower.
- **The image:** 4/10 against 5/10, at 36 s per problem.
- **The Kangaroo as a judge of hints:** a 0.8B model moves as much with nonsense as with a good hint. The bar now rewards a hint that doesn't give the answer away, which the board *can* check.
- **Hints written by the model on the board:** 28–34 s each, and weak. We use an agent's hint bank, written ahead of time, instead.
- **A flaky USB power supply** rebooted the board four times. Long runs now go through `systemd-run --user`.

**What we learned:** a small model can't teach, but it can be taught. Measuring everything on the board, and saying when a difference is noise, mattered more than any trick.

**Next:** measure the hints with real students (do they solve the next problem?), label topics with more care, and try a bigger model with the image on a board with more memory.

## C7. Data, license and team

M3Kang is for research use only: this project publishes none of its problems, images or labels. Dataset card: <https://huggingface.co/datasets/qualcomm/M3Kang>. Paper: Torres-Camps et al., 2026, [arXiv:2601.16218](https://arxiv.org/abs/2601.16218).

Our code is under the MIT license. It builds on the organizers' base repository, [mpous/datathon-UPC-maths-qualcomm-arduino-unoq](https://github.com/mpous/datathon-UPC-maths-qualcomm-arduino-unoq), and uses llama.cpp (MIT), Qwen3.5 0.8B and bge-small-en-v1.5 (see their model cards), and RapidOCR (Apache 2.0).

**The team:** Berta Aulet, Irene Miralles, Marc Igual and Berta Vidal.

---

## D. Imatges per fer

| # | Què | Com | Estat |
| --- | --- | --- | --- |
| 1 | Portada: la placa amb la matriu LED encesa i el tutor al portàtil | Foto amb el mòbil | Per fer |
| 2 | Ensenyar el Cangur: la barra pujant després d'una pista neta | Captura del tutor amb un problema **inventat** (p. ex. "Tinc un problema meu" amb el del tren de `demo/GUIO_DEMO.md`) | Per fer |
| 3 | Diagrama d'arquitectura | `docs/img/arquitectura.png` (font editable: `arquitectura.svg`). També serveix per a la secció d'arquitectura del README | Fet |
| 4 | La pantalla de benvinguda "Hola! Comencem?" | Captura | Per fer |
| 5 | La matriu LED: interrogant, tic i barra | Fotos o un GIF curt | Per fer |
| 6 | El dashboard Tukey | Captura de `projecte/dashboard/dashboard.html` (només xifres agregades) | Per fer |
| 7 | El pont d'idioma (opcional) | `capturas_pont_idioma/*.jpg` (fetes amb una base inventada). Són d'una versió anterior: mostren l'ordre antic de l'ajuda (el problema semblant primer). Millor refer-ne una amb la interfície actual | Fetes, antigues |

**No pujar:** captures o vídeos amb enunciats reals de M3Kang (els problemes del banc de la demo, com `lvl-0_2019_1`), ni res de `imatges_visio_nit/`.

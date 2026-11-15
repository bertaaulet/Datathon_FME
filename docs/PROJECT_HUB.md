# Arduino Project Hub: text per enganxar

_2026-11-15, 11:30. Alineat amb `projecte/README.md` de `main` (commit `32b88a9`): mateixa idea, mateixes xifres i mateixos límits. Si canvia el README, canvia això._

## Com es publica

1. Inicia sessió a <https://projecthub.arduino.cc/> amb un compte d'Arduino i prem **+ New project**.
2. Omple els camps de la fitxa (secció A) i els components (secció B).
3. A la descripció del projecte, enganxa les seccions C1–C8 en ordre. Cada `##` és un títol de secció de l'editor.
4. Puja les imatges de la secció D on diu `[IMATGE: …]`.
5. A **Code**, enllaça el repositori de GitHub: ha de ser **públic** abans d'enviar l'enllaç.
6. Desa'l com a esborrany, revisa'l amb la vista prèvia i publica'l. Envia els dos enllaços (GitHub i Project Hub) als organitzadors.

**Llicència de M3Kang (només recerca):** cap enunciat, imatge ni resposta de M3Kang al Hub. Les captures del tutor s'han de fer amb els **problemes inventats** (secció D). Res de `imatges_visio_nit/`.

---

## A. La fitxa del projecte

- **Title:** Teach the Kangaroo: learn maths by teaching an AI classmate, offline on the Arduino UNO Q
- **Short description:** Learn maths by teaching it. An offline tutor on the Arduino UNO Q where the AI isn't the teacher but the classmate: students solve Kangaroo problems, then help the Kangaroo without giving the answer away.
- **Cover image:** la captura de la pantalla de benvinguda (`docs/img/benvinguda.png`)
- **Difficulty:** Advanced
- **Duration:** about 6 hours on a board already set up with the organizers' steps 0–12
- **Tags:** Arduino UNO Q, LLM, edge AI, llama.cpp, education, math, offline, LED matrix
- **License:** MIT
- **Code:** <https://github.com/bertaaulet/ensenya-el-cangur> (the code is in `projecte/`)

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

**Learn maths by teaching it.** Explaining something to someone else is one of the best ways to understand it. So in this project the AI isn't the teacher. **It's the classmate.**

PISA and Kangaroo problems are long texts, and a student who doesn't read the classroom language well fails before the maths even starts. A classroom also can't always rely on the internet, or send its students' data to a cloud service. **Teach the Kangaroo** is a maths tutor that runs entirely on an Arduino UNO Q 4 GB, offline: nothing leaves the board. Built for the Qualcomm challenge "Math on the Edge" at the Datathon FME 2026 (UPC).

The language model that fits on the board, Qwen3.5 0.8B, gets Kangaroo problems right about as often as a guess. Instead of hiding that, we made it a character: **the Kangaroo**, a classmate who always gets the problem wrong first and needs the student's help.

1. **Solve.** The student gets a real Kangaroo competition problem from M3Kang, chosen for their level. M3Kang knows the right answer, so checking is exact.
2. **Stuck? Climb the ladder.** Help comes one rung at a time: the topic and a method, a hint, a second hint, a similar and easier problem, and the solution only if they ask for it. Never the answer first.
3. **Got it? Teach the Kangaroo.** The Kangaroo answers wrong. The student writes a hint to help it, without giving the answer away. If the hint is good enough, the Kangaroo gets it, and its bar goes up on the screen and on the board's LED matrix.
4. **Language at their own pace.** The problem in the student's language next to Catalan, then Catalan with a button, then Catalan only.
5. **Next.** An Elo rating picks the next problem: hard enough to learn from, easy enough to keep going.

The model never writes text for the student. It only reports how likely it finds each letter, in one token. Everything the Kangaroo says is a sentence written by the team.

`[IMATGE 1b: foto de la placa amb el tutor]`

## C2. A session with the Kangaroo

`[IMATGE 2]`

**1. Welcome.** The student types their name (if they want), their school year (from 5th of primary to the last year of secondary) and the language they understand best: Catalan, Spanish, English, French, Arabic or Chinese. The screen tells them: *"Everything you do stays on this board."* The Kangaroo says hello: *"Hi! I'm the Kangaroo. Shall we solve problems together? Fair warning: I get things wrong quite often, so you may have to help me!"*

**2. The problem.** It arrives in two steps: the statement first, then the options one by one. The student answers with a click or the A–E keys. Next to it is the Kangaroo's yard: the Kangaroo, drawn in dots like the board's LEDs, on a road of 13 lamps (as many as the matrix has columns), with a cross at one end and a ✓ at the other. A mirror of the LED matrix shows on screen what the board is showing.

**3. Wrong? The help ladder.** *"That's not it. You can ask for a hint and try again."* Each button climbs one rung: *Ask for a hint* (the topic and a method), *Another hint*, a similar, easier problem to try before seeing its answer, and finally *Show me the solution*. The screen counts the hints asked for and the tries left.

**4. Right? Teach the Kangaroo.** *"Well, I said B… (I'm 62% sure). Will you help me? Give me a hint, but don't tell me the answer!"* The student writes a hint. If it gives the answer away, the Kangaroo says so and the try isn't spent. If not, *"Aah, now I see it!"*: the Kangaroo hops along the road towards the ✓, the lamps light up and the board's LED matrix shows it.

**5. My progress.** A drawer with the problems solved on the first try, the streak, the score per topic and the list of failed problems to try again (without touching the rating). The student can also choose the topic they want to practise.

**6. My own problem.** With *I have a problem of my own*, the student pastes a problem from their homework or a book, with options A) … E). The Kangaroo tells them which topic it looks like and its level, and they work through it the same way, with a warning always on screen to check the solution with their teacher.

**7. Language, at their own pace.** At first the problem shows in Catalan and in the student's language, side by side. After a run of right answers it moves to *Catalan with help*, with a *See it in my language* button, and then to *Catalan only*. Arabic reads right to left, the language can be changed without losing progress, and anything machine-translated is marked on screen.

**8. For the teacher.** A panel with the summary per topic, how many hints convinced the Kangaroo and how many were rejected, outside problems counted apart and, after 30 answers per language, an estimate of how much the language costs the student.

**Made for the classroom:** it works on a phone and on a computer, follows the device's light or dark mode, can be used with the keyboard and a screen reader, and if the link to the board drops it says so and lets the student try again.

## C3. Architecture

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
- as the base of our **hint bank** (two ordered hints per problem, all through the leak filter).

## C4. Step by step

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

The first one runs overnight on the board and continues where it stopped. The hint bank is prepared on the laptop (`prep/agent/hint_bank.md`) and checked with `prep/check_agent_output.py`.

### Step 5: The go / no-go test for the hints

```bash
python3 prep/hint_experiment.py --make-template 25
python3 prep/hint_experiment.py
```

Fill in a good hint, a nonsense hint and a hint with the answer for each problem. If good and nonsense hints move the Kangaroo alike, the bar can't judge hints, and a hint is scored by whether it gives the answer away.

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

## C5. Results

Measured on the board with the final configuration, on the organizers' practice set (100 problems, 20 with each right answer, in English and Catalan).

| Configuration | Accuracy (95% interval) | Letters said A/B/C/D/E | Mean / worst time |
| --- | --- | --- | --- |
| Organizers' baseline (their 40 English problems) | 22.5% | — | 8.7 / 12.7 s |
| The model's letter, no correction | 22% (15–31%) | 18/7/0/73/2 | 7.6 / 11.9 s |
| **Final configuration: letter bias corrected** | **25% (18–34%)** | 21/24/20/18/17 | 7.6 / 12.2 s |

- **Balanced letters.** Without the correction the model answers D 73 times out of 100. With it, each letter comes up between 17 and 24 times, close to the 20 of each in the set.
- **Fast and far from the limit:** 7.6 s per problem on average and 12.2 s at worst, against the 60 s allowed.
- **Chosen by measuring.** Every alternative was run on the board before choosing: similar solved problems (RAG), an expression computed by Python and the image. None beat this configuration.

**The tutor on the board:**
- **Leak filter:** it stopped 23 of the 24 hints that gave the answer away, and let all 48 clean hints of the same test through.
- **Time:** the Kangaroo reads a hint in 11.5 s (median) and 15.0 s at worst. An outside problem is ready in about 23 s. A help rung is instant.
- **End to end** (`prep/tutor_smoke.py`: 4 failed problems through the 5 help rungs, 6 problems teaching the Kangaroo, 1 outside problem): 67/67 checks passed, with at least 2.7 GB of RAM free.
- **Ready in a minute:** plug the board in, and the tutor, both models and the LED matrix start on their own.

`[IMATGE 6: captura del dashboard]`

## C6. Error analysis

The final configuration on the organizers' 100 practice problems. Groups under 10 problems only point a direction.

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
- **Geometry is the weakest topic** (3/18): the problems depend on the figure, which the model never sees.

That's why the model plays a classmate to teach, and M3Kang is the answer key.

## C7. Known limits, and what we learned


- **The model.** Qwen3.5 0.8B is the biggest model that fits on the board next to the tutor, and on Kangaroo problems it barely beats guessing. A better model would make `predict.py` work well. Today this hits problems typed in by the student directly: their "right answer" is the harness's, so the tutor can mark as right an answer that isn't. That's why the warning stays on screen for outside problems.
- **A weakness we turned into the idea.** That same limit gave us the Kangaroo, the classmate who gets it wrong and needs the student's help, which is the core of the project. But the whole flow only works when we know the right answer: problems from the M3Kang bank.
- **Hints for new problems.** Problems typed in by the student now get predefined method hints for their topic. Our plan was for the model to write a hint from the statement, the solution and a few examples from the bank. We couldn't make it work well within the model's limits, so it's off.
- **Scoring hints.** The idea is to score a hint by how much it changes the model's certainty in the right answer. Right now that measure is also limited by the model's low performance, so the bar rewards a hint that doesn't give the answer away.
- **OCR and figures.** In M3Kang the options are drawn in the image, and we read them with OCR. Some can't be read (fractions, options that are drawings or charts): those problems reach `predict.py` without options and get the most common letter, and the tutor doesn't use them. Many problems also depend on a figure the language model never sees; we tried the board's vision model, but at about 36 s per problem it didn't improve the answer.

**What we learned:** a small model can't teach, but it can be taught. That limit gave us the Kangaroo, and measuring everything on the board told us which ideas really helped.

**Next:** a better model on the board, so `predict.py` can check problems typed in by students and write hints for new problems from the statement, the solution and examples; measure hints with real students (do they solve the next problem?); and read options and figures better.

## C8. Data, license and team

M3Kang is for research use only: this project publishes none of its problems, images or labels. Dataset card: <https://huggingface.co/datasets/qualcomm/M3Kang>. Paper: Torres-Camps et al., 2026, [arXiv:2601.16218](https://arxiv.org/abs/2601.16218).

Our code is under the MIT license. It builds on the organizers' base repository, [mpous/datathon-UPC-maths-qualcomm-arduino-unoq](https://github.com/mpous/datathon-UPC-maths-qualcomm-arduino-unoq), and uses llama.cpp (MIT), Qwen3.5 0.8B and bge-small-en-v1.5 (see their model cards), and RapidOCR (Apache 2.0).

**The team:** Berta Aulet, Irene Miralles, Marc Igual and Berta Vidal.

---

## D. Imatges per fer

| # | Què | Com | Estat |
| --- | --- | --- | --- |
| 1b | Una foto de la placa amb el tutor obert (per a C1) | Foto | Per fer |
| 2 | Ensenyar el Cangur: la barra pujant després d'una pista neta | Captura del tutor amb un problema **inventat** (p. ex. "Tinc un problema meu" amb el del tren de `demo/GUIO_DEMO.md`) | Per fer |
| 3 | Diagrama d'arquitectura | `docs/img/arquitectura.png` (font editable: `arquitectura.svg`). També serveix per a la secció d'arquitectura del README | Fet |
| 4 | La pantalla de benvinguda "Hola! Comencem?" | Captura | Per fer |
| 5 | La matriu LED: interrogant, tic i barra | Fotos o un GIF curt | Per fer |
| 6 | El dashboard Tukey | Captura de `projecte/dashboard/dashboard.html` (només xifres agregades) | Per fer |
| 7 | El pont d'idioma (opcional) | `capturas_pont_idioma/*.jpg` (fetes amb una base inventada). Són d'una versió anterior: mostren l'ordre antic de l'ajuda (el problema semblant primer). Millor refer-ne una amb la interfície actual | Fetes, antigues |
| 8 | El meu progrés: el calaix amb ratxa, temes i fallats (opcional) | Captura amb un alumne de prova | Per fer |

**No pujar:** captures o vídeos amb enunciats reals de M3Kang (els problemes del banc de la demo, com `lvl-0_2019_1`), ni res de `imatges_visio_nit/`.

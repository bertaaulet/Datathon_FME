# Ensenya el Cangur (Teach the Kangaroo)

A math copilot that runs entirely on an Arduino UNO Q, offline. Built for the Qualcomm challenge "Math on the Edge" at the Datathon FME 2026 (UPC).

> **Status: written and tested on a laptop against a stand-in model. Nothing has been run on the board or on M3Kang yet.** Every section that needs a measurement says so. Replace each `TODO (measure)` with a number from your own runs before you publish.

<!-- TODO: a photo or a short video of the copilot working on the board -->

## What it does

The language model that fits on the board (Qwen3.5 0.8B) answers Kangaroo problems close to random: the organizers measured 22.5% on 40 problems, below always answering "D". So it can't be the teacher. This project turns that around:

1. **The student solves a problem** from the M3Kang bank. M3Kang knows the right answer, so checking is exact.
2. **If they're wrong**, they get help one rung at a time: a similar, easier problem; the topic and a method; a hint left by another student; and the solution only if they ask for it.
3. **If they're right**, they teach the Kangaroo, a weak classmate played by the model. The Kangaroo always starts with a wrong answer. The student writes a hint that mustn't give the answer away, and the board measures whether the hint moved the Kangaroo towards the right option. A bar on the LED matrix goes up or down.
4. **Hints that work are kept** on the board, and become the third rung of help for the next student.
5. **The next problem** is chosen with Elo ratings, so it's hard enough to learn from and easy enough to keep going.

The model never writes text for the student. It only reports how likely it finds each letter, in one token. Everything the Kangaroo "says" is a sentence written by the team.

### The language bridge

PISA and Kangaroo problems are long texts. A student who doesn't yet read the classroom language well fails before the maths starts. M3Kang has every problem in many languages with the same `id`, so:

- **Three stages.** The problem in the student's language next to Catalan; then Catalan with a button to see it in their language (each use is counted); then Catalan only. The student moves up after four right answers in a row without the button.
- **Language or maths?** The student has two ratings, one per language. The difference estimates how much the language costs them. It's shown to the teacher only after 30 answers per language, as a rough range, and nobody is labelled: the student chooses the language, and the data stay on the board.

### Problems from outside the bank

A student can type their own problem. Nobody knows its answer, so the tutor doesn't check it. It shows the topic, an estimated level and similar problems from the bank to practise with. Only if the student asks does the Kangaroo give its guess, with a warning that it can't be confirmed.

### `predict.py`

The official entry point answers one letter per problem, as the challenge requires. On top of the baseline it can: correct the model's letter bias, ask again with the options rotated and average, answer the most common letter when a problem has no readable options, and it never stops on an error. Each of these is a setting in `config.env`. Until you measure them, the defaults behave like the baseline, except for problems without options.

## Architecture

| Piece | Runs on | What it does |
| --- | --- | --- |
| Web page (`app/index.html`) | The student's browser | Shows the problem, takes the answer and the hint |
| Tutor (`app/server.py`, `copilot/tutor.py`) | Linux on the board | The flow, the leak filter, Elo, calls to the model |
| Language model server, port 8081 | Linux on the board | Returns a probability per letter |
| Embedding server, port 8082 | Linux on the board | Finds similar problems (preparation, and outside problems) |
| SQLite (`data/tutor.db`) | Linux on the board | The student, attempts, hints, ratings, problem texts |
| App Lab app (`applab/math-matrix`) | Linux + microcontroller | Draws the tutor's picture on the 8x13 LED matrix |

How M3Kang is used: as the answer key, as a difficulty map (level and position in the paper give each problem a first rating), as a library of similar problems (embeddings), as the same problem in several languages, and as the base of a bank of hints written by students.

```text
predict.py            official entry point (same command line as the base repository)
eval.py               accuracy and latency, by level, topic and language
copilot/llm.py        letter_probs(): a probability for each letter A to E
copilot/pipeline.py   solve(): bias correction, rotations, time budget
copilot/tutor.py      the tutor's flow
copilot/leak.py       does a hint give the answer away?
copilot/elo.py        ratings and the choice of the next problem
copilot/topics.py     a topic per problem, from keywords, and method hints
copilot/store.py      the SQLite file
copilot/led.py        pictures for the LED matrix
prep/                 preparation scripts
sim/students.py       simulated students
app/                  the tutor's web page
applab/math-matrix/   App Lab app for the LED matrix
dashboard/            the decisions dashboard (Side Challenge Tukey)
tests/                tests, a stand-in model server, invented problems
docs/SETUP.md         the organizers' guide: board setup, models, M3Kang
```

## How to replicate it

Start from a board set up with steps 0 to 12 of [docs/SETUP.md](docs/SETUP.md): llama.cpp built, both models running as services, `data/train.jsonl` and `data/val.jsonl` on the board, and `data/index.db` built. Then, on the board, from this folder:

**1. Check the model server gives what the project needs** (2 minutes).

```bash
python3 prep/check_model.py
```

It checks that the server reports a probability for each letter, and that a second call with a hint only reads the hint.

**2. Measure the baseline.**

```bash
python3 eval.py --limit 50 --name baseline
```

**3. Measure the letter bias and the most common answers** (about 10 minutes), then measure again.

```bash
python3 prep/letter_bias.py
```

```bash
python3 eval.py --limit 50 --name debias
```

```bash
python3 eval.py --limit 50 --rotations 2 --name rotations-2
```

Fifty problems only rule things out. Confirm a candidate on the whole validation set with `--limit 0` (about 45 minutes), then set `PREDICT_ROTATIONS` in `config.env`.

**4. Build the tutor's database.** Prepare the languages you want on your laptop first (`laptop/prepare_m3kang.py --languages eng,cat,esp,arb --save-images`) and copy `data/` over.

```bash
python3 prep/build_tutor_db.py --show-topics 50
```

Read the 50 problems it prints, and check the topics by hand.

**5. Ask the Kangaroo every problem once.** Run it overnight; it continues where it stopped.

```bash
python3 prep/kangaroo_baseline.py
```

**6. The go / no-go experiment for the hints** (about 1 hour).

```bash
python3 prep/hint_experiment.py --make-template 25
```

Fill in `data/hints_experiment.jsonl` with a good hint, a nonsense hint and a hint that gives the answer away for each problem, then:

```bash
python3 prep/hint_experiment.py
```

If good and nonsense hints move the Kangaroo alike, the bar means nothing. Keep the rest of the tutor and judge hints only by how many students solve the problem after seeing them.

**7. Start the tutor.**

```bash
python3 app/server.py --host 0.0.0.0
```

On your laptop, over USB: `adb forward tcp:8090 tcp:8090`, then open <http://127.0.0.1:8090>.

**8. The LED matrix.** Copy `applab/math-matrix` to `/home/arduino/ArduinoApps/` on the board and start it from App Lab. It reads the tutor's picture and draws it. *Not tested on a board yet*: check first that the app can reach the tutor (see the comment at the top of `python/main.py`).

**9. Simulated students and the dashboard.**

```bash
python3 sim/students.py
```

```bash
python3 dashboard/build.py
```

### Try it without a board

```bash
python3 -m unittest discover -s tests
```

```bash
python3 tests/demo_data.py --out data/demo
```

```bash
python3 tests/fake_llama.py --answers data/demo/train.jsonl data/demo/val.jsonl
```

With the stand-in servers running, build a database from `data/demo/` and start `app/server.py`. The stand-in is not a language model and the demo problems are invented: nothing measured with them is a result.

## Results

`TODO (measure)`: the table from `results/ablations.csv`, each experiment against the baseline, with the number of problems, accuracy with its 95% interval, mean and worst latency.

| Experiment | Problems | Accuracy | Mean time | Worst time |
| --- | --- | --- | --- | --- |
| Organizers' baseline (40 English problems with OCR options) | 40 | 22.5% | 8.7 s | 12.7 s |
| Our baseline | TODO | TODO | TODO | TODO |

The hint experiment, the leak filter's score and the time of each step go here too.

### What the simulated students showed

These are simulations of the method, not real students (`sim/students.py`, 200 simulated students per setting, an invented problem bank).

- With a constant Elo step of 32, a student who starts 300 points from their level is still about 170 points off after 20 answers. With a step that starts large and shrinks, about 65. One Kangaroo level is 150 points. We use the second.
- A language gap of 200 points is measured as about 160 after 15 answers per language and about 185 after 30, and the middle half of students spans roughly 120 to 260. That's why the gap is shown only after 30 answers per language, and as a range.

## Error analysis

`TODO (measure)`: accuracy by topic, language and level, each with its number of problems, from `eval.py` and the dashboard. Look at 10 wrong answers one by one in the explorer and explain them here.

M3Kang has no topic field. Topics come from keywords (`copilot/topics.py`): fast and easy to explain, but rough. Say how many of the 50 problems you checked by hand had the right topic.

## Known limits

- The Kangaroo's first answer is forced: it's always the likeliest *wrong* option, even when the model prefers the right one. In that case the tutor skips the teaching step.
- The bar measures whether a hint moved the model, not whether it's good teaching. The second signal, how many students solve the problem after seeing a hint, needs real use to build up.
- The leak filter is rules. It catches the letter, the value and the position of the answer, not indirect leaks such as "it's twice five".
- The tutor only uses problems that are text-only and whose five options OCR could read.
- The embedding model is English-only: an outside problem typed in Catalan finds worse neighbours.
- One student at a time. The model server has one slot and its cache holds one problem.
- `cache_prompt` can make the model's numbers differ very slightly between a cached and an uncached call (see the llama.cpp server documentation). The base repository already uses it.

## What didn't work

`TODO`: write what you tried and dropped, as plainly as what worked.

## Data and license

M3Kang is licensed for research use only. This repository holds none of it: no problem texts, images, `index.db`, `tutor.db` or hint files. `.gitignore` excludes them, and the scripts rebuild them. The problems in `data/sample_problems.jsonl` and `tests/demo_data.py` are invented.

The code is under the MIT license (see `LICENSE`). It builds on the organizers' base repository, [mpous/datathon-UPC-maths-qualcomm-arduino-unoq](https://github.com/mpous/datathon-UPC-maths-qualcomm-arduino-unoq).

- **M3Kang**: Torres-Camps et al., 2026, [arXiv:2601.16218](https://arxiv.org/abs/2601.16218). [Dataset card](https://huggingface.co/datasets/qualcomm/M3Kang).
- **llama.cpp**: [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp), MIT license.
- **Qwen3.5 0.8B** (GGUF by bartowski) and **bge-small-en-v1.5** (GGUF by CompendiumLabs): see their model cards.
- **RapidOCR**: Apache 2.0 license.

## The team

`TODO`: names.

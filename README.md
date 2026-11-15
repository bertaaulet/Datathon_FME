# Ensenya el Cangur (Teach the Kangaroo)

A math copilot that runs entirely on an Arduino UNO Q 4 GB, offline. Built for the Qualcomm challenge "Math on the Edge" at the Datathon FME 2026 (UPC).

A student solves Kangaroo problems from the M3Kang dataset. When they're wrong, they get help one rung at a time, never the answer first. When they're right, they teach the Kangaroo, a weak classmate played by a small language model on the board, with a hint that mustn't give the answer away. A bridge between languages helps students who don't yet read Catalan well. The LED matrix shows the Kangaroo's reaction.

**The full documentation is in [`projecte/README.md`](projecte/README.md):** what it does, the architecture, how to replicate it on a board, the results measured on the board, the error analysis, and what didn't work.

## What's where

| Folder | What it holds |
| --- | --- |
| [`projecte/`](projecte/) | All the code: `predict.py` (the official entry point), the tutor, the LED matrix app, board setup scripts, tests and the decisions dashboard |
| [`projecte/docs/SETUP.md`](projecte/docs/SETUP.md) | The organizers' guide to set up the board, the models and M3Kang |
| [`docs/`](docs/) | The team's working notes, in Catalan: status, decisions, problems found on the board, plans and board runbooks |

## Results in one line

On the organizers' 100 practice problems, `predict.py` answers **25%** (95% interval 18–34%) in 7.6 s on average, against 22.5% for the organizers' baseline and 20% for guessing. The details, and why the model plays a classmate instead of a teacher, are in [`projecte/README.md`](projecte/README.md#results).

## Data and license

M3Kang is for research use only: this repository holds none of its problems, images or labels. See the [dataset card](https://huggingface.co/datasets/qualcomm/M3Kang) and Torres-Camps et al., 2026, [arXiv:2601.16218](https://arxiv.org/abs/2601.16218).

The code is under the [MIT license](LICENSE). It builds on the organizers' base repository, [mpous/datathon-UPC-maths-qualcomm-arduino-unoq](https://github.com/mpous/datathon-UPC-maths-qualcomm-arduino-unoq).

## The team

Berta Aulet, Irene Miralles, Marc Igual and Berta Vidal.

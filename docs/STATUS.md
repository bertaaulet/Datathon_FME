# Estat actual

_Última actualització: 2026-11-14 16:50 — Berta (amb Claude)_

## Fase
Tot el codi de la v1 és a `projecte/`, però **no hi ha cap resultat real**: només s'ha provat contra un model simulat. El pla d'execució és a [`docs/PLA.md`](PLA.md) (harness de `predict.py`, pistes amb agent i model, problemes externs amb el mateix recorregut, què va al portàtil i què a la placa). Comencem a treballar en paral·lel en tres línies.

| Part | Escrit | Provat amb el simulador | Provat a la placa |
| --- | --- | --- | --- |
| `predict.py` i `eval.py` | Sí | Sí | No |
| Tutor i web (port 8090) | Sí | Sí, també al navegador | No |
| Scripts de preparació (`prep/`) | Sí | Sí | No |
| Pont d'idioma i doble Elo | Sí | Sí | No |
| Alumnes simulats (`sim/`) | Sí | Sí (no cal el model) | — |
| Dashboard Tukey (`dashboard/`) | Sí | Sí, amb dades de prova | — |
| App de la matriu LED (`applab/`) | Sí | No | No |
| Harness de `predict.py` (etapes 1–4, 6–7) | No | — | — |
| Banc de l'agent i pistes generades pel model | No | — | — |

## Qui fa què
| Línia | Persona | Primera tasca | Estat |
| --- | --- | --- | --- |
| A · Millorar `predict.py` (harness) | Berta | Fitxers de calibració al repo, nivell tret de l'`id`, llama.cpp al portàtil | 🟡 Fet a `berta/predict-calib`: excepcions al `.gitignore` (també `ablations.csv`), nivell de l'`id`, `eval.py` amb columna `machine` i `--debias batch` (38 proves OK). Falta: llama.cpp al portàtil (WSL) i esperar `data/` de B |
| B · Dades, agent i pistes | | `prepare_m3kang.py --languages eng,cat` i passar `data/` a la resta (fora de Git) | ⬜ |
| C · Placa Arduino | | Passos 0–8 de `projecte/docs/SETUP.md` i `prep/check_model.py` | ⬜ |
| Sense assignar | | Tutor (problemes externs, integrar pistes generades), dashboard, README, Project Hub, pitch | ⬜ |

## Placa
- Passos 0–8 de `projecte/docs/SETUP.md`: ⬜
- `check_model.py` (decisió D1): ⬜
- IP / accés:

## Millor resultat fins ara
| Experiment | Encert | n | Latència mitjana |
| --- | --- | --- | --- |
| baseline (organitzadors) | 22,5% | 40 | 8,7 s |

## Bloquejos / dubtes oberts
- **Preguntes per als organitzadors** (llista a `docs/PLA.md`): on s'executa el test ocult, si porta opcions i `level`, si es poden publicar xifres agregades i un model ajustat amb M3Kang, si es poden preparar pistes amb un model gran, i com i quan es lliura el dashboard.
- **Per decidir com a equip:** validació (15% a l'atzar o `--val-years 2023,2024`), llengües, les tres propostes de Claude a `DECISIONS.md`, el llindar de D4, l'idioma del README i el nom a la `LICENSE`.
- L'app de la matriu LED pot no arribar al tutor per `127.0.0.1` si App Lab l'executa en un contenidor.

## Resolt
- Importar el repo base: còpia sense historial a `projecte/` (commit `d6e3f1b` dels organitzadors).
- Idea final: Teach ("Ensenya el Cangur") amb `predict.py` millorat com a part del projecte.
- Pla d'execució escrit a `docs/PLA.md`.

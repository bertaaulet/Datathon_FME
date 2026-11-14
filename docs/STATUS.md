# Estat actual

_Última actualització: 2026-11-14 — Elsa (amb Claude)_

## Fase
Idea triada i **tot el pla escrit** a `projecte/` (vegeu `pla_projecte.md` i `projecte/README.md`). Falta provar-ho a la placa: fins ara només s'ha executat contra un servidor de model simulat i problemes inventats. **No hi ha cap resultat real.**

| Part | Escrit | Provat amb el simulador | Provat a la placa |
| --- | --- | --- | --- |
| `predict.py` i `eval.py` | Sí | Sí | No |
| Tutor i web (port 8090) | Sí | Sí, també al navegador | No |
| Scripts de preparació (`prep/`) | Sí | Sí | No |
| Pont d'idioma i doble Elo | Sí | Sí | No |
| Alumnes simulats (`sim/`) | Sí | Sí (no cal el model) | — |
| Dashboard Tukey (`dashboard/`) | Sí | Sí, amb dades de prova | — |
| App de la matriu LED (`applab/`) | Sí | No | No |

## Qui fa què
| Persona | Tasca actual | Estat |
| --- | --- | --- |
| Berta | Organització del repo i memòria compartida | En curs |
| Elsa | Pla del projecte i implementació inicial de tot el codi | Fet; pendent de proves a la placa |
| <membre 3> | | |
| <membre 4> | | |

## Placa
- Passos 1–8 de `projecte/docs/SETUP.md`: ⬜ pendent de confirmar
- IP / accés: 

## Pròxims passos (en ordre, a la placa, des de `projecte/`)
1. `python3 prep/check_model.py` — comprova que el servidor dona probabilitats per lletra i que la memòria cau funciona.
2. `python3 eval.py --limit 50 --name baseline` — el nostre baseline.
3. `python3 prep/letter_bias.py` i tornar a mesurar (`--name debias`, després `--rotations 2`).
4. `python3 prep/build_tutor_db.py --show-topics 50` i revisar els temes a mà.
5. `python3 prep/kangaroo_baseline.py` — de nit.
6. Experiment de pistes (`prep/hint_experiment.py`): decideix si la barra de confiança del Cangur es manté.
7. `python3 app/server.py --host 0.0.0.0` i provar l'app de la matriu LED.
8. `python3 sim/students.py` i `python3 dashboard/build.py`.

## Millor resultat fins ara
| Experiment | Encert | n | Latència mitjana |
| --- | --- | --- | --- |
| baseline (organitzadors) | 22,5% | 40 | 8,7 s |

## Bloquejos / dubtes oberts
- **Preguntes per als organitzadors**: el test ocult porta opcions en text? En quins idiomes? S'executa a la nostra placa? Es pot generar un banc de pistes al portàtil amb un model gran? Com i quan es lliura el dashboard, i ha de ser públic?
- **`projecte/README.md` és en anglès** (pensant en el Project Hub), però la convenció de l'equip diu documentació en català. Cal decidir.
- **Llicència MIT** posada com a proposta a `projecte/LICENSE`, amb un nom d'equip provisional. Cal confirmar-la.
- Les pistes de mètode per tema (`projecte/copilot/topics.py`) les ha escrit Claude: cal revisar-les.
- L'app de la matriu LED pot no arribar al tutor per `127.0.0.1` si App Lab l'executa en un contenidor (vegeu el comentari a `applab/math-matrix/python/main.py`).
- Aquest primer commit del codi s'ha fet directament a `main`, no en una branca `nom/tema`.

## Resolt
- Importar el repo base: còpia sense historial a `projecte/` (commit `d6e3f1b` dels organitzadors).
- Idea final: Teach ("Ensenya el Cangur") amb `predict.py` millorat com a part del projecte.

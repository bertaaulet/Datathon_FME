# Lot `problem_types` — tipus de problema

## Objectiu
El tipus de **tots** els problemes del train i de la validació, per a la línia A:
- triar quins solucionadors de Python escriure (etapa 2 del harness): els tipus més freqüents i amb `python_solvable: true` primer;
- l'anàlisi d'errors del baseline per tipus, nivell i idioma.

## Entrada
`python prep/agent/export_batch.py --kind problem_types --n 0` (train i val, **sense etiqueta**).

## Sortida: `data/agent/problem_types_out.jsonl`

```json
{"id": "<id>", "kind": "problem_types", "source": "agent", "type": "ages",
 "topic": "aritmetica", "python_solvable": true}
```

| Camp | Tipus | Obligatori | Contingut |
| --- | --- | --- | --- |
| `id`, `kind`, `source` | text | sí | `kind` = `"problem_types"`, `source` = `"agent"` |
| `type` | text | sí | Un dels tipus de sota |
| `topic` | text | no | Una clau de `copilot/topics.py` |
| `python_solvable` | booleà | no | Es pot resoldre amb un càlcul de Python a partir del text, sense mirar la figura |

Tipus (`PROBLEM_TYPES` a `prep/agent_lots.py`):

| Tipus | Quan |
| --- | --- |
| `arithmetic` | Un càlcul escrit a l'enunciat |
| `percent_ratio` | Percentatges, fraccions d'una quantitat, proporcions, escales |
| `units_measure` | Canvis d'unitat, velocitat, diners, pesos |
| `multiples_divisors` | Divisibilitat, primers, residus, mcd/mcm |
| `digits` | Propietats de les xifres d'un nombre |
| `clock_calendar` | Hores, durades, dies de la setmana, dates |
| `ages` | Edats ara, abans o després |
| `equations` | Incògnites, sistemes, balances |
| `sequences_patterns` | Successions, patrons que es repeteixen |
| `counting` | Ordenacions, combinacions, camins, casos |
| `probability` | Probabilitat |
| `logic` | Mentiders i veraços, deducció, ordenar persones o objectes |
| `geometry_plane` | Longituds, angles, àrees i perímetres en 2D |
| `geometry_space` | Cubs, desenvolupaments, sòlids, vistes |
| `visual` | Cal la figura: no es pot resoldre només amb el text |
| `other` | Cap dels anteriors |

## Regles
- El tipus és el del **mètode** per resoldre'l, no el de les paraules de l'enunciat.
- No es resol el problema ni s'escriu cap resposta: els problemes de validació no poden deixar rastre de la solució.
- Un registre per problema.

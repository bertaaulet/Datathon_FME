# Lot `hint_bank` — banc de pistes de referència

## Objectiu
Dues pistes de **mètode** en català, **ordenades**, per a cada problema elegible del train (només text i amb les cinc opcions; la validació no, perquè l'agent no en veu mai la resposta). El tutor les mostra quan l'alumne falla i demana ajuda (`docs/PISTES.md`):

- **Pas 1** (`step: 1`, graó 2): per on començar. La més general.
- **Pas 2** (`step: 2`, graó 3): el pas següent, més concret, sense arribar a la resposta.

La pista del pas 1 també fa d'exemple quan el model de la placa escriu la pista d'un problema extern semblant (`copilot/hintgen.py`).

## Entrada
`python prep/agent/export_batch.py --kind hint_bank --n 200 [--skip data/agent/hint_bank_out.jsonl]`

Cada línia de `data/agent/hint_bank_in.jsonl`:

```json
{"id": "<id>", "level": 3, "split": "train", "label": "C",
 "texts": {"eng": {"text": "...", "options": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}},
           "cat": {"text": "...", "options": {...}}}}
```

## Sortida: `data/agent/hint_bank_out.jsonl`
**Una línia per pista** (dues per problema, una de cada pas):

```json
{"id": "<id>", "kind": "hint_bank", "source": "agent", "lang": "cat", "step": 1,
 "hint": "Fes una taula amb les edats d'ara i les de d'aquí a tres anys."}
{"id": "<id>", "kind": "hint_bank", "source": "agent", "lang": "cat", "step": 2,
 "hint": "Escriu que la suma de les edats d'aquí a tres anys és la que diu l'enunciat."}
```

| Camp | Tipus | Obligatori | Contingut |
| --- | --- | --- | --- |
| `id` | text | sí | El de l'entrada |
| `kind` | text | sí | `"hint_bank"` |
| `source` | text | sí | `"agent"` |
| `lang` | text | sí | Sempre `"cat"` |
| `step` | enter | sí | `1` (per on començar) o `2` (el pas següent); un de cada per problema |
| `hint` | text | sí | La pista |
| `label` | text | no | Si hi és, ha de coincidir amb les dades |

## Regles
- **Pista de mètode**: explica com començar o què mirar, no fa el càlcul. No diu ni la **lletra**, ni el **valor** de l'opció correcta (ni en xifres ni en lletres), ni la seva **posició** («la tercera», «la del mig», «l'última»).
- Tampoc pot descartar opcions fins a deixar-ne una, ni donar un resultat intermedi que sigui la resposta.
- Català correcte, **una sola frase**, de 8 a **200 caràcters**, en segona persona («Fixa't…», «Prova…»).
- Les dues pistes d'un problema han de ser diferents de debò: el pas 2 continua el pas 1, no el repeteix amb altres paraules. Llegides en ordre, no han de deixar la resposta feta.
- Ha de ser correcta matemàticament per a aquest problema; si el problema necessita la figura i el text no n'hi ha prou, no s'escriu cap pista per a aquest problema.
- `check_agent_output.py` passa cada pista per `copilot.leak.check` amb les opcions de totes les llengües, i rebutja un `step` que no sigui 1 o 2, dos pistes amb el mateix `step`, la tercera pista d'un problema i les repetides.
- Després de validar: `python prep/import_hints.py data/agent_hints.jsonl`, i, amb el Cangur ja calculat en català, `python prep/kangaroo_agent_hints.py` per saber quantes el convencen.

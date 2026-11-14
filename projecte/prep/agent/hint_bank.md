# Lot `hint_bank` — banc de pistes de referència

## Objectiu
Dues pistes de **mètode** en català per a cada problema elegible del banc (només text i amb les cinc opcions). Serveixen d'exemples quan el model de la placa genera pistes noves (`copilot/hintgen.py`), de referència per comparar-les i de **reserva** al graó 3 del tutor quan una pista generada es rebutja.

## Entrada
`python prep/agent/export_batch.py --kind hint_bank --n 200 [--skip data/agent/hint_bank_out.jsonl]`

Cada línia de `data/agent/hint_bank_in.jsonl`:

```json
{"id": "<id>", "level": 3, "split": "train", "label": "C",
 "texts": {"eng": {"text": "...", "options": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}},
           "cat": {"text": "...", "options": {...}}}}
```

## Sortida: `data/agent/hint_bank_out.jsonl`
**Una línia per pista** (dues per problema):

```json
{"id": "<id>", "kind": "hint_bank", "source": "agent", "lang": "cat",
 "hint": "Fes una taula amb les edats d'ara i les de d'aquí a tres anys."}
```

| Camp | Tipus | Obligatori | Contingut |
| --- | --- | --- | --- |
| `id` | text | sí | El de l'entrada |
| `kind` | text | sí | `"hint_bank"` |
| `source` | text | sí | `"agent"` |
| `lang` | text | sí | Sempre `"cat"` |
| `hint` | text | sí | La pista |
| `label` | text | no | Si hi és, ha de coincidir amb les dades |

## Regles
- **Pista de mètode**: explica com començar o què mirar, no fa el càlcul. No diu ni la **lletra**, ni el **valor** de l'opció correcta (ni en xifres ni en lletres), ni la seva **posició** («la tercera», «la del mig», «l'última»).
- Tampoc pot descartar opcions fins a deixar-ne una, ni donar un resultat intermedi que sigui la resposta.
- Català correcte, **una sola frase**, de 8 a **200 caràcters**, en segona persona («Fixa't…», «Prova…»).
- Les dues pistes d'un problema han de ser diferents de debò (dues idees o dos passos), no la mateixa amb altres paraules.
- Ha de ser correcta matemàticament per a aquest problema; si el problema necessita la figura i el text no n'hi ha prou, no s'escriu cap pista per a aquest problema.
- `check_agent_output.py` passa cada pista per `copilot.leak.check` amb les opcions de totes les llengües, i rebutja la tercera pista d'un problema i les repetides.
- Després de validar: `python prep/import_hints.py data/agent_hints.jsonl`.

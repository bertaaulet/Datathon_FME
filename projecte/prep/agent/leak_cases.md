# Lot `leak_cases` — casos de prova del filtre de fuites

## Objectiu
Mesurar l'encert de `copilot/leak.py`: quantes fuites atrapa i quantes pistes netes deixa passar. 200 casos: **100 amb fuita** i **100 nets**, incloent-hi **fuites indirectes** («és el doble de cinc»), que el filtre no sap veure i que cal comptar.

## Entrada
`python prep/agent/export_batch.py --kind leak_cases --n 100`. Dos casos per problema (un amb fuita i un de net) donen els 200. També es poden fer casos sobre problemes inventats, amb `id` que comenci per `inv-`.

## Sortida: `data/agent/leak_cases_out.jsonl`
El format de `copilot.leak.evaluate()` més els camps comuns:

```json
{"id": "<id>", "kind": "leak_cases", "source": "agent", "lang": "cat",
 "hint": "Si multipliques les bosses per les pomes i en restes dues, ja ho tens: deu.",
 "label": "C", "leak": true, "category": "valor"}
```

| Camp | Tipus | Obligatori | Contingut |
| --- | --- | --- | --- |
| `id`, `kind`, `source` | text | sí | `kind` = `"leak_cases"` |
| `hint` | text | sí | La pista que es prova |
| `label` | text | sí | La lletra correcta (ha de coincidir amb les dades) |
| `leak` | booleà | sí | `true` si la pista dona la resposta |
| `category` | text | no | `lletra`, `valor`, `posicio`, `indirecta` (fuita que el filtre no pot veure) o `neta` (va amb `leak: false`) |
| `lang` | text | no | Idioma de la pista; per defecte `cat` |
| `options`, `text` | | sí per a `inv-…` | Per als problemes de M3Kang els afegeix el validador des de les dades |

El fitxer validat (`--ok data/leak_cases.jsonl`) ja té `options` i `text` i es pot passar a `python -m copilot.leak data/leak_cases.jsonl results/leak.json`.

## Regles
- Repartiment orientatiu de les 100 fuites: 25 de lletra, 30 de valor (xifres, en lletres, amb unitats, decimals amb coma), 15 de posició, 30 indirectes.
- Les 100 netes han de ser difícils per al filtre: que usin números de l'enunciat, la paraula «opció», lletres que són noms de punts (A, B…), o el valor d'una opció **incorrecta**.
- `leak` diu la veritat sobre la pista, no el que creus que farà el filtre: el validador **no** comprova el resultat del filtre, perquè el que volem és mesurar-lo.
- Sense casos repetits.

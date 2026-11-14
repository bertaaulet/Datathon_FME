# Lot `invented_problems` — problemes inventats

## Objectiu
Uns 100 problemes **nous**, escrits per l'agent, amb la seva resposta. Serveixen per provar el recorregut dels **problemes externs** (els que l'alumne introdueix i no són al banc) amb una resposta coneguda, i com a exemples **publicables** (README, demo, dashboard) si una persona els revisa abans. No són de M3Kang: els números que en surtin no es poden presentar mai com a resultats amb M3Kang.

## Entrada
`python prep/agent/export_batch.py --kind invented_problems --n 100` escriu un pla sense cap text de M3Kang: `{"id": "inv-001", "language": "cat", "level": 0, "topic": "geometria"}` per línia, amb nivells de 0 a 7 i els temes de `copilot/topics.py` repartits.

## Sortida: `data/agent/invented_problems_out.jsonl`
El format de `data/sample_problems.jsonl` més els camps comuns:

```json
{"id": "inv-001", "kind": "invented_problems", "source": "agent", "language": "cat", "level": 0,
 "text": "La Laia té 4 caixes amb 5 llapis cadascuna i en regala 3. Quants llapis li queden?",
 "options": {"A": "15", "B": "17", "C": "18", "D": "20", "E": "23"}, "label": "B",
 "topic": "aritmetica", "solution": "4 × 5 = 20 llapis; 20 − 3 = 17."}
```

| Camp | Tipus | Obligatori | Contingut |
| --- | --- | --- | --- |
| `id` | text | sí | El del pla, comença per `inv-` |
| `kind`, `source` | text | sí | `"invented_problems"`, `"agent"` |
| `language` | text | sí | `"cat"` o `"eng"` |
| `level` | enter | sí | 0–7, com a M3Kang (0 el més fàcil) |
| `text` | text | sí | L'enunciat, sense figura |
| `options` | objecte | sí | Exactament `A`–`E`, cinc valors diferents |
| `label` | text | sí | La lletra correcta |
| `topic` | text | no | Clau de `copilot/topics.py` |
| `solution` | text | no | Solució breu (per revisar-lo) |

## Regles
- **Originals**: no es pot copiar, traduir ni adaptar cap problema de M3Kang ni de cap altra font amb drets. El validador rebutja el que comparteixi més del 60% de les paraules amb un problema de les dades.
- Només text (el tutor no mostra figures per als problemes externs), amb una sola resposta correcta i els distractors plausibles (errors típics).
- La lletra correcta repartida entre A–E (aproximadament 20% cadascuna), perquè el biaix de lletra no faci trampa.
- Dificultat d'acord amb el nivell: 0–1 primària, 2–3 cicle superior, 4–5 ESO, 6–7 batxillerat.

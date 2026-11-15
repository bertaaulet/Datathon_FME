# Lot `hint_experiment` — pistes de l'experiment D2

## Objectiu
Decidir si la barra de confiança del Cangur té sentit i fixar el llindar τ: per a cada problema calen una pista **bona**, una **absurda** i una **amb fuita**. `prep/hint_experiment.py` mesura quant mou cadascuna el marge del model, que llegeix el problema i la pista en català, com al tutor (`KANGAROO_LANG`). Només es fan servir problemes on el model prefereix una opció incorrecta: on ja prefereix la correcta, el Cangur fingeix i el Δ no mesura res. Si les bones no guanyen clarament les absurdes, la barra es treu (decisió D2 de `docs/PLA.md`).

## Entrada
`python prep/hint_experiment.py --make-template 25` escriu `data/hints_experiment.jsonl` amb 25 problemes que el model falla. Cada línia té `id`, `text`, `options`, `label` i els camps `good`, `bad` i `leak` buits. Si encara no hi ha `tutor.db`, també serveix `python prep/agent/export_batch.py --kind hint_experiment --n 25`.

## Sortida: `data/agent/hint_experiment_out.jsonl`
Una línia per problema:

```json
{"id": "<id>", "kind": "hint_experiment", "source": "agent",
 "good": "Compta primer quantes pomes hi ha en total abans de restar les que es menja.",
 "bad": "Pensa en el teu color preferit i en com et fa sentir.",
 "leak": "La resposta és la C."}
```

| Camp | Tipus | Obligatori | Contingut |
| --- | --- | --- | --- |
| `id` | text | sí | El de l'entrada |
| `kind` | text | sí | `"hint_experiment"` |
| `source` | text | sí | `"agent"` |
| `good` | text | sí | Una pista real que ajuda i no dona la resposta |
| `bad` | text | sí | Una pista absurda, de llargada semblant, sense relació amb el problema |
| `leak` | text | sí | Una pista que dona la resposta clarament: la lletra («és la C»), el valor o la posició |
| `label`, `text`, `options`, `lang` | | no | Es poden copiar de l'entrada; si hi són, han de coincidir amb les dades |

Després de validar-lo amb `--ok data/hints_experiment.jsonl`, el fitxer torna a tenir `text`, `options` i `label`, que és el que llegeix `hint_experiment.py`.

## Regles
- En català (`TUTOR_LANG`), una frase cadascuna, de 8 a 200 caràcters.
- `good` i `bad` han de **passar** `copilot.leak.check`. `leak` l'ha de **fallar** per lletra, valor o posició (no val que falli només per ser massa curta).
- `bad` ha de tenir una llargada semblant a `good` (±50%), perquè l'efecte no sigui només de llargada.
- `good` ha de ser correcta matemàticament i no fer el càlcul final.
- Un sol registre per problema.

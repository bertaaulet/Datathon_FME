# Lot `topics_reference` — temes de referència

## Objectiu
Mesurar l'encert de `copilot/topics.py` (classificació per paraules clau) amb 100 problemes etiquetats per l'agent. Amb aquest número decidim si la taula per temes del dashboard i el graó 2 del tutor són fiables.

## Entrada
`python prep/agent/export_batch.py --kind topics_reference --n 100` (train i val, sense etiqueta).

## Sortida: `data/agent/topics_reference_out.jsonl`

```json
{"id": "<id>", "kind": "topics_reference", "source": "agent", "topic": "geometria", "alt": null}
```

| Camp | Tipus | Obligatori | Contingut |
| --- | --- | --- | --- |
| `id`, `kind`, `source` | text | sí | `kind` = `"topics_reference"` |
| `topic` | text | sí | El tema principal: una clau vàlida de `copilot/topics.py` |
| `alt` | text o null | no | Un segon tema si el problema en barreja dos (diferent de `topic`) |

Claus vàlides (`copilot.topics.NAMES`): `geometria`, `comptar`, `nombres`, `fraccions`, `temps`, `mesura`, `logica`, `probabilitat`, `patrons`, `aritmetica` (per defecte, càlcul i problemes amb nombres).

## Regles
- Tria el tema pel **mètode** que cal per resoldre'l, no per les paraules: un problema de rellotges que es resol comptant és `comptar` amb `alt: "temps"`.
- **No miris** el que diu `topics.classify()` abans de decidir: l'objectiu és comparar-s'hi.
- Un registre per problema.
- El validador informa de quantes vegades coincideix `topics.py` amb `topic` o `alt`.

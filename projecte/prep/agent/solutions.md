# Lot `solutions` — solucions breus

## Objectiu
Una **solució breu** per a cada problema del **train**, per a la línia A (`predict.py`):
- etapa 4 del harness (RAG amb raonament): el model rep el problema més semblant amb la seva solució i després el problema nou;
- etapa 3: una **expressió aritmètica** opcional que Python pot calcular;
- ajust fi (problema → solució → lletra).

El tipus de problema va en un lot a part: [problem_types.md](problem_types.md).

## Entrada
`python prep/agent/export_batch.py --kind solutions --n 0` (tot el train, amb `label`). L'exportador no accepta problemes de validació.

## Sortida: `data/agent/solutions_out.jsonl`
Una línia per problema:

```json
{"id": "<id>", "kind": "solutions", "source": "agent",
 "solution": "3 bags of 4 apples are 12 apples; after eating 2, 12 - 2 = 10 are left.",
 "answer": "C", "expression": "3 * 4 - 2"}
```

| Camp | Tipus | Obligatori | Contingut |
| --- | --- | --- | --- |
| `id`, `kind`, `source` | text | sí | `kind` = `"solutions"`, `source` = `"agent"` |
| `solution` | text | sí | Solució en **anglès** (el model raona en anglès), ≤ 600 caràcters, 1–3 frases, que acaba amb el valor |
| `answer` | text | sí | La lletra; ha de coincidir amb `label` |
| `expression` | text | no | Expressió amb números, `+ - * / // % **` i parèntesis el valor de la qual és el de l'opció correcta |

## Com ho fa servir el RAG
Un registre per `id` (l'ordre no importa). La clau és `id`, sense idioma: la solució val per a totes les llengües del problema. El prompt de l'etapa 4 serà `Problem: <text del veí>\nSolution: <solution>\nAnswer: <answer>` i després el problema nou. Per això la solució:
- és curta: a la placa, llegir costa ≈ 1 s per cada 11 tokens;
- no fa referència a la figura si el text n'hi ha prou;
- no diu «opció C» dins del text: el valor final sí, la lletra només a `answer`.

## Regles
- **Mai** una solució per a un problema de validació: entraria al RAG i l'encert d'`eval.py` deixaria de ser vàlid. El validador ho rebutja.
- `answer` ha de coincidir amb l'etiqueta. Si hi ha `expression` i l'opció correcta és un número, l'expressió l'ha de donar exactament.
- Si l'agent no sap resoldre el problema (per exemple, perquè depèn de la figura), no escriu cap línia per a aquest problema.

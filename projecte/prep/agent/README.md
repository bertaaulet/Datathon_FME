# Lots de l'agent

Un agent (Claude Code o un altre model gran) prepara al **portàtil**, per endavant, els textos que el projecte necessita i que no escrivim a mà: pistes, solucions breus, tipus de problema, casos de prova del filtre de fuites, temes de referència i problemes inventats. A la placa no hi ha cap agent: només arriben els resultats validats, dins de `data/`.

Aquesta carpeta té les **instruccions** (es pugen al repo). El que l'agent llegeix i escriu va a `data/agent/` i als fitxers finals de `data/`, i **no es puja mai a Git**: porta text de M3Kang o etiquetes per problema. `projecte/.gitignore` ja ignora tot `data/` (comprova-ho amb `git check-ignore -v data/agent/x.jsonl`).

## Flux

Tot s'executa des de `projecte/`.

```text
data/train.jsonl, val.jsonl, tutor.db
        │  1. prep/agent/export_batch.py --kind <lot>
        ▼
data/agent/<lot>_in.jsonl          (només els camps necessaris)
        │  2. l'agent llegeix prep/agent/<lot>.md i escriu una línia JSON per resultat
        ▼
data/agent/<lot>_out.jsonl
        │  3. prep/check_agent_output.py --kind <lot>   (esquema, ids i regles)
        ▼
data/agent/<lot>_out_ok.jsonl  →  fitxer final (taula de sota)
        │  4. importar o fer-lo servir
        ▼
tutor.db (pistes, amb source='agent'), harness, filtre de fuites, dashboard
```

1. **Exportar.** `python prep/agent/export_batch.py --kind hint_bank --n 200`. Escriu `data/agent/hint_bank_in.jsonl`. Amb `--skip data/agent/hint_bank_out.jsonl` es deixen fora els problemes ja fets, per treballar per lots de 50–200.
2. **Processar.** S'obre l'agent a `projecte/` i se li demana: «Llegeix `prep/agent/hint_bank.md` i processa `data/agent/hint_bank_in.jsonl`; escriu el resultat a `data/agent/hint_bank_out.jsonl`». L'agent no pot fer servir xarxa per buscar els problemes, i no pot copiar el text de cap problema a fitxers fora de `data/`.
3. **Validar.** `python prep/check_agent_output.py data/agent/hint_bank_out.jsonl --kind hint_bank`. Informa dels errors per línia (sense mostrar el text dels problemes) i escriu les línies vàlides a `data/agent/hint_bank_out_ok.jsonl`. Amb `--ok <fitxer>` s'escriu directament al fitxer final. Les línies rebutjades es poden tornar a passar a l'agent amb el motiu.
4. **Revisar i fer-lo servir.** Una persona en revisa 20 línies de cada lot, i el nombre de correctes es publica. Després:
   - banc de pistes: `python prep/import_hints.py data/agent_hints.jsonl` (idempotent);
   - pistes de l'experiment: `python prep/hint_experiment.py` (llegeix `data/hints_experiment.jsonl`);
   - casos de fuites: `python -m copilot.leak data/leak_cases.jsonl results/leak.json`.

## Lots

| Lot (`--kind`) | Instruccions | Entrada | Fitxer final | Qui el fa servir |
| --- | --- | --- | --- | --- |
| `hint_experiment` | [hint_experiment.md](hint_experiment.md) | `hint_experiment.py --make-template 25` | `data/hints_experiment.jsonl` | Experiment D2 |
| `hint_bank` | [hint_bank.md](hint_bank.md) | problemes elegibles del train | `data/agent_hints.jsonl` | `import_hints.py`: graons 2 i 3 del tutor, i exemple de `hintgen` per als problemes externs |
| `solutions` | [solutions.md](solutions.md) | tot el train (mai la validació) | `data/agent_solutions.jsonl` | Línia A: RAG (etapa 4), expressió (etapa 3), ajust fi |
| `problem_types` | [problem_types.md](problem_types.md) | train i val, sense etiqueta | `data/problem_types.jsonl` | Línia A: solucionadors de Python (etapa 2), anàlisi d'errors |
| `leak_cases` | [leak_cases.md](leak_cases.md) | problemes elegibles del train | `data/leak_cases.jsonl` | `python -m copilot.leak` |
| `topics_reference` | [topics_reference.md](topics_reference.md) | 100 problemes, train i val | `data/topics_gold.jsonl` | Encert de `copilot/topics.py` |
| `invented_problems` | [invented_problems.md](invented_problems.md) | pla d'ids, nivells i temes (sense text de M3Kang) | `data/invented.jsonl` | Problemes externs, exemples publicables |

## Regles per a tots els lots

- **Una línia JSON per resultat**, en UTF-8, amb `ensure_ascii` desactivat (accents tal qual). Cap comentari ni text fora del JSON.
- Camps comuns obligatoris: `id` (el de l'entrada), `kind` (el nom del lot) i `source` (sempre `"agent"`). Opcionals: `model` (quin model l'ha escrit) i `note`. Qualsevol altre camp que no surti a l'esquema del lot fa que es rebutgi la línia.
- Les sortides **no es pugen mai** a Git, ni tampoc fragments en missatges de commit, issues o el README. Només es poden publicar xifres agregades (quantes línies passen, encert del filtre, Δ). Els problemes inventats es poden publicar si una persona els revisa abans.
- Pistes: en català, una sola frase, sense la lletra, el valor ni la posició de l'opció correcta. Ho comprova `copilot/leak.py`.
- La validació (`split: "val"`) no porta mai etiqueta ni solució: si l'agent les veiés, l'encert mesurat amb `eval.py` deixaria de ser vàlid.

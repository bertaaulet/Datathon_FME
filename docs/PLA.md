# Ensenya el Cangur — estat del projecte i guia d'execució

14 nov 2026 · Basat en el commit `316547d` ("v1") de `bertaaulet/Datathon_FME`

## Resum

Tot el codi del projecte "Ensenya el Cangur" està escrit, però **encara no tenim cap resultat real**: no s'ha executat res amb M3Kang ni a la placa. Les 35 proves automàtiques només s'han passat contra un model simulat.

El pla té dues apostes. La primera és construir un **harness** que porti `predict.py` molt per sobre del 22,5% actual. La segona és que el model de la placa generi pistes. El 22,5% és el punt de partida i no l'acceptem com a límit: cada etapa del harness es mesura per separat. Els **problemes externs funcionen igual que els del banc**: el harness calcula la resposta, i el tutor sempre mostra un avís que diu que no la podem assegurar. Explicarem amb transparència què funciona i què no.

El document inclou tot el que diu el pla del projecte, sense deixar res per si sobra temps, i al final el compara amb els requisits del repte. La repartició de tasques i el calendari els decideix l'equip. La presentació és **diumenge**.

## Com funciona el projecte i què expliquem

L'alumne resol problemes de M3Kang. Quan n'encerta un, ensenya el Cangur, el company fluix que fa el model: li escriu una pista que no pot donar la resposta, i la placa mesura si la pista l'ha mogut cap a la resposta correcta. Si l'alumne falla, l'ajuda arriba per graons: un problema semblant més fàcil, el tema i el mètode, una pista, i la solució només si la demana. El pont d'idioma i el doble Elo ajuden l'alumne que encara no domina el català.

### Què fa el model i amb quines dades

| Part | Qui ho fa | Problemes del banc (M3Kang) | Problemes externs |
| --- | --- | --- | --- |
| Resposta correcta | Banc: l'etiqueta de M3Kang. Externs: el harness de `predict.py` | Segura | La del harness, amb l'avís |
| Correcció de la resposta de l'alumne (✓/✗) | Python | Contra l'etiqueta | Contra la resposta del harness, amb l'avís |
| El Cangur (ensenyar) | El Qwen: probabilitats abans i després de la pista | Igual | Igual, prenent com a correcta la resposta del harness |
| Pistes del graó 3 | El Qwen, amb exemples del banc (en context i RAG) | Pistes generades per endavant | Generades en el moment |
| Filtre de fuites | Python | Amb l'etiqueta | Amb la resposta del harness, i a més el filtre estricte (cap lletra ni valor d'opció) |
| Problema semblant, tema, nivell i Elo | Embeddings (bge), paraules clau i Python | Igual | Igual. El nivell s'estima amb els veïns, i els intents queden marcats com a externs |
| Solució (graó 4) | Python | L'etiqueta | La resposta del harness, amb l'avís |
| Banc de pistes de referència | Un agent (Claude Code) al portàtil, per endavant | Sí | Fa d'exemple per al model |

**Avís per als problemes externs**, sempre visible quan el problema no és del banc: *"No podem assegurar les respostes per a problemes externs. Confirma la solució en fonts oficials o amb el teu professor."*

### Què diem al README, al Project Hub i al pitch

- El model de la placa és petit. Hem construït un harness per treure'n el màxim i publiquem l'encert de cada etapa, també de les que no han funcionat.
- Amb els problemes del banc, la resposta és segura (l'etiqueta de M3Kang). Amb els problemes externs, el tutor funciona igual, però la resposta és la del harness, i per això sempre es mostra l'avís. Publiquem l'encert del harness perquè es pugui saber quant s'hi pot confiar.
- Les pistes generades sempre passen pel filtre de fuites. Publiquem quantes es rebutgen i quantes són incorrectes.

## Estat actual del codi

El commit `316547d` ("v1") afegeix 66 fitxers i unes 8.400 línies. El codi viu a `projecte/`, que és una còpia sense historial del repo dels organitzadors (commit `d6e3f1b`) amb tot el nostre a sobre. `projecte/docs/SETUP.md` és la guia dels organitzadors, sense cap canvi. He comprovat que no s'ha pujat cap dada de M3Kang.

| Part | Fitxers | Estat |
| --- | --- | --- |
| `predict.py` | `copilot/pipeline.py`, `llm.py`, `calib.py` | Escrit. Mai s'atura per un error, corregeix el biaix de lletra, pot rotar les opcions i, si un problema no té opcions, respon la lletra més freqüent |
| Tutor i web (port 8090) | `copilot/tutor.py`, `app/` | Escrit. Inclou l'escala d'ajuda, el Cangur i els problemes externs |
| Filtre de fuites | `copilot/leak.py` | Escrit |
| Elo i tria del problema següent | `copilot/elo.py` | Escrit. K decreixent, de 160 a 40 |
| Temes | `copilot/topics.py` | Escrit. Paraules clau, amb pistes de mètode per a cada tema |
| Pont d'idioma i doble Elo | `copilot/tutor.py` | Escrit. Tres etapes, i es puja d'etapa amb 4 encerts seguits |
| Base de dades | `copilot/store.py` | Escrit (`data/tutor.db`) |
| Matriu LED | `copilot/led.py`, `applab/math-matrix/` | Escrit. Mai provat a la placa |
| Preparació | `prep/` | Escrit: `check_model`, `letter_bias`, `build_tutor_db`, `kangaroo_baseline` i `hint_experiment` |
| Alumnes simulats | `sim/students.py` | Escrit |
| Dashboard Tukey | `dashboard/` | Escrit. Només provat amb dades de prova |
| Proves | `tests/` | 35 proves, que passen contra el model simulat |
| Banc de pistes de l'agent | — | Per fer |
| Generació de pistes amb el model | — | Per fer |

Documents: `pla_projecte.md`, `projecte/README.md` (en anglès), `CLAUDE.md`, `docs/STATUS.md` i `docs/DECISIONS.md`.

## predict.py: un harness per superar el 22,5%

El 22,5% és el model sol, amb un prompt i una crida. Un **harness** és tot el que s'hi posa al voltant perquè encerti més: buscar el problema en dades ja resoltes, resoldre amb Python el que es pugui calcular, donar-li millors exemples, corregir-ne els biaixos i repartir els 60 s amb criteri. El mateix harness fa servir el tutor per als problemes externs, així que cada punt que guanyi millora també el tutor.

### Primer: que les millores arribin al test ocult

- **Fitxers de calibració.** S'afegeixen dues excepcions al `.gitignore` i es pugen `letter_bias.json` i `priors.json`, que només porten xifres agregades.
- **Nivell.** Si falta `level`, es treu de l'`id` (`^lvl-(\d+)_`). Si no es pot, es fa servir la prior global.
- **Prova des d'un clon net**, i qualsevol excepció acaba en una lletra.

### Les etapes del harness

`solve()` passa per aquestes etapes en ordre. Cada etapa es pot activar o desactivar a `config.env`, i les més barates van primer.

| # | Etapa | Idea | Cost | Què s'ha de mesurar abans |
| --- | --- | --- | --- | --- |
| 1 | **Problema gairebé idèntic** | El Cangur repeteix problemes entre nivells i anys amb ids diferents. Si la similitud amb un problema del train és molt alta i les opcions coincideixen per valor, es copia la resposta, adaptant-ne la lletra si les opcions estan en un altre ordre | <1 s | Quants problemes de validació tenen un germà al train, i amb quin llindar l'encert és gairebé del 100%. Excloure els germans de la validació perquè la mesura sigui honesta |
| 2 | **Solucionadors en Python** | Per als tipus de problema que es poden calcular (aritmètica escrita a l'enunciat, percentatges, unitats, comptar múltiples o divisors, rellotges, edats), es calcula el resultat i es compara amb el valor de les opcions. Si només n'hi ha una que encaixa, s'agafa | <1 s | Quins tipus són més freqüents (l'agent els classifica al train), la cobertura i la precisió de cada solucionador |
| 3 | **El model escriu una expressió, Python la calcula** | Per als problemes de càlcul que no cobreix l'etapa 2, una gramàtica obliga el model a escriure només una expressió aritmètica (números i operadors). Python l'avalua de manera segura i la compara amb les opcions. El model planteja i Python calcula, que és on el model falla ("2 + 3 × 4" → 24) | \~10–20 s | Encert en els problemes de càlcul respecte a demanar la lletra directament |
| 4 | **Exemples resolts (RAG amb raonament)** | L'agent escriu al portàtil una solució breu per a cada problema del train. A la placa, el model rep el problema més semblant amb la seva solució i després el problema nou. Ara els exemples només porten la lletra, que no ensenya res | +10–25 s | Encert amb 0, 1 i 2 exemples, amb solució i sense. Cal vigilar els tokens |
| 5 | **Lletra calibrada** | Probabilitats de A–E, correcció del biaix (amb fitxer o calibració per lot), i rotacions de les opcions mentre quedi temps | +2–4 s per rotació | Ja està escrit, excepte la calibració per lot |
| 6 | **Problemes sense opcions** | Millor OCR al portàtil. A la placa, per als que continuïn sense opcions: la imatge amb el servidor de visió (`--image-max-tokens 128`, 28–38 s segons els organitzadors), o la prior del nivell | 28–38 s amb imatge | Encert amb imatge respecte a la prior, i si el test ocult porta imatges |
| 7 | **Pressupost adaptatiu** | Si una etapa barata dóna una resposta segura (etapes 1–2, o una probabilitat alta a l'etapa 5), s'atura. Si no, gasta els segons que queden en la següent. Sempre amb el marge de 3 s | — | Corba d'encert segons el temps gastat |

### Canvis de model

| Opció | Idea | Què s'ha de comprovar |
| --- | --- | --- |
| **Ajust fi del Qwen 0.8B** | LoRA amb el train de M3Kang (problema → lletra, o problema → solució breu → lletra, amb les solucions de l'agent), fet en una GPU fora de la placa. Es converteix a GGUF Q8 i corre amb el mateix llama.cpp. Marc Pous, al vídeo, compta que alguns equips entrenaran models ("how did you train the model") | Encert a la validació sense fuites (per anys), mateixa velocitat, i si es poden publicar uns pesos entrenats amb M3Kang |
| **Un altre model** | Un model de \~1–2B a 4 bits que hi càpiga | RAM, temps de lectura (el pressupost el marca la lectura, no l'escriptura) i llicència. Cal actualitzar `config.env`, els serveis i les skills |
| **Raonament curt** | Raonament amb un límit de tokens. Als organitzadors els va empitjorar, però combinat amb les etapes 3 i 4 pot ser diferent | Encert i temps |

### Com es mesura

- **Abans de construir:** una anàlisi d'errors del baseline per tipus de problema, nivell i idioma, per saber on hi ha més marge. L'agent etiqueta el tipus de problema del train i de la validació.
- **Cada etapa sola i acumulada** amb `eval.py --name`, sobre els mateixos problemes. Amb 50 problemes només es pot descartar; les conclusions es treuen amb `--limit 0` i amb la validació per anys (`--val-years`), que s'assembla més a un test ocult.
- **Referència:** `baseline-org` (`--no-options model --debias off`), comparable amb el 22,5%.
- **Final:** pitjor cas per sota de 57 s a la placa, i `predict.py` passa amb `data/sample_problems.jsonl`.
- **Anàlisi d'errors** per tema, idioma i nivell, amb el nombre de problemes, i 10 errors explicats un per un amb l'explorer.

## Pistes

Les pistes surten de dos llocs. Un agent prepara al portàtil un banc de pistes de referència. Després, el model de la placa genera pistes noves fent servir aquest banc com a exemple. Totes passen pel filtre de fuites i es mesuren. No s'escriu cap pista a mà.

### 1. El banc de l'agent (al portàtil, per endavant)

Un agent (Claude Code) genera els textos que el pla deixava per escriure a mà. Les instruccions (`prep/agent/`) es pugen al repo; el que generi l'agent queda a `data/` i no es puja.

| Lot | Quantitat | Fitxer | Per a què serveix |
| --- | --- | --- | --- |
| Pistes de l'experiment | 25 problemes × 3 (bona, absurda, amb fuita) | `data/hints_experiment.jsonl` | Decidir si es manté la barra de confiança (D2) |
| Banc de pistes | 2 pistes en català per a cada problema elegible | `data/agent_hints.jsonl` | Exemples per al model, referència amb què comparar, i reserva |
| Solucions breus | Una per a cada problema del train | `data/agent_solutions.jsonl` | Etapa 4 del harness i ajust fi |
| Tipus de problema | Tots els problemes del train i de la validació | `data/problem_types.jsonl` | Triar quins solucionadors de Python fer (etapa 2) i l'anàlisi d'errors |
| Casos de prova del filtre | 200 (100 amb fuita i 100 netes), incloent-hi fuites indirectes | `data/leak_cases.jsonl` | Encert del filtre |
| Temes de referència | 100 problemes | `data/topics_gold.jsonl` | Encert de `topics.py` |
| Problemes inventats | \~100, amb la resposta | `data/invented.jsonl` | Exemples publicables i proves dels problemes externs (la seva resposta permet mesurar el tutor en mode extern) |

Control de qualitat:

- `prep/check_agent_output.py` comprova l'esquema i passa `leak.py` per totes les pistes.
- `kangaroo_baseline.py` i `hint_experiment.py` en calculen el Δ.
- Una persona en revisa 20 de cada lot. El nombre de pistes correctes es publica.

### 2. Generació amb el model (a la placa)

El Qwen escriu una pista d'una frase per a qualsevol problema, també per als que introdueix l'alumne. Els exemples són les pistes del banc dels problemes més semblants (en context i RAG). És el graó 3 que proposen els organitzadors a `SETUP.md` 13.1.

1. **Cerca.** Es fa l'embedding del problema amb bge i es busquen els 1 o 2 problemes del banc més semblants. Per als problemes del banc, la cerca es fa amb la versió anglesa.
2. **Prompt.** Una instrucció fixa, els veïns com a parells problema → pista, la pista de mètode del tema i el problema nou. La part fixa va al principi perquè `cache_prompt` la reaprofiti.
3. **Generació.** Temperatura 0, `SEED=42`, uns 40 tokens com a màxim, i una gramàtica que obliga a escriure una sola frase.
4. **Filtre.** Si el problema és del banc, es fa servir `leak.py` amb la resposta correcta. Si és extern, un filtre més estricte rebutja qualsevol lletra d'opció, qualsevol valor d'opció i els números que surten a les opcions però no a l'enunciat.
5. **Reserva.** Si la pista es rebutja, surt la pista del banc de l'agent (problemes del banc) o la pista de mètode del tema (problemes externs).

**Temps estimat** amb les xifres dels organitzadors (llegeix uns 11 tokens/s i escriu uns 6 tokens/s; s'ha de verificar amb `prompt_n`):

| Prompt | Tokens a llegir | Total aproximat |
| --- | --- | --- |
| 2 veïns complets + problema | \~560 | \~56 s |
| 1 veí + problema | \~350 | \~37 s |
| 2 veïns, només la pista + problema | \~250 | \~28 s |

Per als problemes del banc, les pistes es generen per endavant i es desen a `tutor.db`. Com que la sortida és determinista, es poden generar en un portàtil amb el mateix model, comprovant en uns quants casos que el text és idèntic al de la placa. Per als problemes externs, la generació comença en segon pla quan l'alumne introdueix el problema.

**Codi nou** (separat de `predict.py`): `copilot/hintgen.py`, el filtre estricte a `leak.py`, `prep/pregen_hints.py` i `prep/import_hints.py`, la columna `source` a la taula `hints`, i el graó 3 i els problemes externs del tutor fent servir aquestes pistes.

### Com es mesuren les pistes

| Què | Com |
| --- | --- |
| Fuites | Percentatge de pistes rebutjades pel filtre, i fuites que se li escapen en una mostra revisada |
| Correcció matemàtica | L'agent fa de jutge de 100 pistes generades, i una persona en revisa 20 |
| Utilitat | Δ del Cangur amb cada tipus de pista: generada, de l'agent, neutra i de mètode. Com que el model que escriu la pista és el mateix que la valora, aquest senyal s'interpreta amb cura |
| Temps | Lectura (`prompt_n`) i escriptura a la placa, amb 1 i 2 veïns |
| Problemes externs | Amb els problemes inventats: qualitat de la cerca, fuites i correcció |
| Llengua | Si la pista surt millor en català o en anglès |
| Senyal humà | Quants alumnes resolen el problema després de veure la pista |

## Dades: què es pot pujar i què no

Els organitzadors prohibeixen publicar les dades de M3Kang i qualsevol cosa que contingui el text dels problemes (`SETUP.md` 9.4 i 15: "research use only"). No diuen res de les xifres agregades, i ells mateixos en publiquen una: `FALLBACK_ANSWER=D`, la lletra més freqüent.

| No es puja mai | Es pot pujar |
| --- | --- |
| `train.jsonl`, `val.jsonl`, `data/images/` | `data/letter_bias.json`, `data/priors.json` |
| `index.db`, `tutor.db` | `results/ablations.csv` (només xifres) |
| `results/eval-*.csv` (porta l'etiqueta de cada problema) | Les instruccions de l'agent (`prep/agent/`) |
| Tot el que generi l'agent, i les pistes generades | Els problemes inventats per l'agent, si es revisen abans |

La regla del `CLAUDE.md` "Tampoc pujar res derivat de M3Kang" es treu. La substitueix aquesta: "Mai pujar res que contingui text de M3Kang ni les etiquetes per problema".

## Què s'executa al portàtil i què a la placa

El que necessita internet o `pip` va al **portàtil**. El que necessita el model es pot fer a la **placa** o en un **portàtil amb llama.cpp i el mateix model**, però els temps només compten si s'han mesurat a la placa. Tot s'executa des de `projecte/`.

| Què | On | Necessita | Produeix | Temps |
| --- | --- | --- | --- | --- |
| `laptop/prepare_m3kang.py` | Portàtil | Internet, `laptop/requirements.txt` | `train.jsonl`, `val.jsonl`, `images/` | \~15 min per idioma |
| `prep/letter_bias.py --priors-only` | Qualsevol | `train.jsonl` | `priors.json` | segons |
| Agent: els cinc lots | Portàtil | Claude Code, `tutor.db` | `data/*.jsonl` | \~15 min per lot |
| Proves (`tests/`) | Qualsevol | Res | Res que es pugui publicar | \~4 s |
| Posada a punt (passos 0–8) | Placa | Internet a la placa | Serveis 8081 i 8082 | \~1 h |
| `build_index.py` | Model\* | `math-embed` | `index.db` | \~4 min |
| `prep/check_model.py` | Model\* | `math-llm` | Diagnòstic | 2 min |
| `eval.py` | Model\* | `val.jsonl` | `ablations.csv`, `eval-*.csv` | 10 min (50), 45 min (tots) |
| `prep/letter_bias.py` | Model\* | `train.jsonl` | `letter_bias.json`, `priors.json` | \~10 min |
| `prep/build_tutor_db.py` | Model\* | `train`, `val`, `math-embed` | `tutor.db` | minuts |
| `prep/kangaroo_baseline.py` | Model\* | `tutor.db` | Respostes del Cangur | \~9 s per problema |
| `prep/hint_experiment.py` | Model\* | Pistes de l'agent | `hints-*.csv`, `τ` | \~1 min per problema |
| `prep/pregen_hints.py` | Model\* | `tutor.db`, banc de l'agent | Pistes generades | \~30–55 s per problema |
| `python3 -m copilot.leak` | Qualsevol | Casos de prova | `leak.json` | segons |
| `app/server.py` i `applab/math-matrix` | Placa | `tutor.db`, models | Tutor (8090) i matriu LED | — |
| `sim/students.py` | Qualsevol | `tutor.db` (opcional) | `sim-*.csv` | \~1 s |
| `dashboard/build.py` | Qualsevol | `results/` | `dashboard.html` | segons |

\* Model: placa, o portàtil amb llama.cpp i el mateix model.

**Com es mouen els fitxers.** Del portàtil a la placa: `scp data/... arduino@<ip>:~/<repo>/projecte/data/` (o `adb push`). Els resultats tornen amb `scp -r arduino@<ip>:~/<repo>/projecte/results .`.

## Decisions de control i comandes

Hi ha quatre resultats que poden canviar el pla. El servidor del model només atén una petició alhora (`--parallel 1`), així que cada màquina només pot fer una cosa que faci servir el model a la vegada.

- **D1 · `check_model.py`.** Si el servidor no dona les probabilitats de les cinc lletres, es prova `/completion` amb `n_probs`. Si tampoc funciona, el biaix es corregeix comptant les lletres que respon el model, i la barra del Cangur només pot mostrar si la lletra canvia.
- **D2 · Experiment de pistes.** Si les pistes bones i les absurdes mouen el Cangur igual, la barra es treu. Les pistes i el senyal humà es mantenen.
- **D3 · Configuració final de `predict.py`.** Només s'accepta una millora que surti del soroll amb `--limit 0` i que, a la placa, tingui el pitjor cas per sota de 57 s.
- **D4 · Pistes generades.** Si fallen massa (per fuites, errors matemàtics o temps), el graó 3 torna a fer servir el banc de l'agent (problemes del banc) i la pista de mètode (problemes externs). El llindar el fixa l'equip abans de mesurar.

### El model al portàtil

Amb el mateix commit i el mateix fitxer de model, l'encert hauria de ser igual que a la placa. Es comprova abans de res: amb el `baseline` de 50 problemes, el portàtil i la placa han de donar les mateixes lletres.

```bash
git clone https://github.com/ggml-org/llama.cpp ~/llama.cpp && cd ~/llama.cpp
git checkout 2cbe0ec429b849a88664e0f62388fc92a5abd699
cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j --target llama-server
mkdir -p ~/models && cd ~/models
wget https://huggingface.co/bartowski/Qwen_Qwen3.5-0.8B-GGUF/resolve/f36b1ea49a332ede8fe5f389bbf5b3575ef71f48/Qwen_Qwen3.5-0.8B-Q8_0.gguf
wget https://huggingface.co/CompendiumLabs/bge-small-en-v1.5-gguf/resolve/d32f8c040ea3b516330eeb75b72bcc2d3a780ab7/bge-small-en-v1.5-q8_0.gguf
sha256sum *.gguf   # han de coincidir amb config.env

~/llama.cpp/build/bin/llama-server -m ~/models/Qwen_Qwen3.5-0.8B-Q8_0.gguf --host 127.0.0.1 --port 8081 \
  --threads 4 --ctx-size 4096 --parallel 1 --cache-ram 0 --ctx-checkpoints 2 --jinja \
  --reasoning off --reasoning-budget 0 --alias qwen3.5-0.8b
~/llama.cpp/build/bin/llama-server -m ~/models/bge-small-en-v1.5-q8_0.gguf --embedding --host 127.0.0.1 \
  --port 8082 --threads 4 --ctx-size 512 --parallel 1 --cache-ram 0 --batch-size 512 --ubatch-size 512
```

Mentre `eval.py` no guardi la màquina, s'afegeix `-laptop` al nom dels experiments fets al portàtil.

### Comandes principals

```bash
# Portàtil: dades
python3 laptop/prepare_m3kang.py --languages eng,cat [--val-years 2023,2024]
python3 prep/letter_bias.py --priors-only

# Placa o portàtil amb el model
python3 build_index.py --only-with-options
python3 prep/check_model.py
python3 eval.py --limit 50 --no-options model --debias off --name baseline-org
python3 eval.py --limit 50 --name baseline
python3 prep/letter_bias.py && python3 eval.py --limit 50 --name debias
python3 eval.py --limit 50 --rotations 2 --name rotations-2
python3 prep/build_tutor_db.py --show-topics 50
python3 prep/kangaroo_baseline.py
python3 prep/hint_experiment.py --make-template 25   # l'agent l'omple
python3 prep/hint_experiment.py

# Placa
python3 app/server.py --host 0.0.0.0                 # al portàtil: adb forward tcp:8090 tcp:8090

# Qualsevol
python3 sim/students.py --db data/tutor.db
python3 -m copilot.leak data/leak_cases.jsonl results/leak.json
python3 dashboard/build.py --baseline baseline-org
```

Si es preparen més llengües, `val.jsonl` es sobreescriu. Per tant, `predict.py` es mesura sempre amb el mateix `--languages`.

## Què queda pendent

Aquesta és la llista completa, agrupada per àrees. Inclou tot el pla del projecte, les mesures que demanen els organitzadors i les dues apostes (`predict.py` i pistes generades).

**Placa i màquines**

- [x] Posada a punt de la placa: passos 0–8 de `SETUP.md`, amb les actualitzacions d'App Lab i els serveis `math-llm` i `math-embed`
- [x] Accés al repo des de la placa (còpia dels fitxers, sense token)
- [x] `check_model.py` (D1)
- [x] Als portàtils: llama.cpp (binari `b12311`, vegeu `DECISIONS.md`) i els mateixos GGUF. Placa i portàtil: 47/50 lletres iguals; els números finals es mesuren a la placa
- [ ] Serveis systemd perquè el tutor (`app/server.py`) i l'app de la matriu LED arrenquin amb la placa, pujats al repo
- [ ] El tutor i la matriu LED funcionant a la placa: l'app arriba al tutor, i el tutor arriba als models
- [ ] RAM amb tot engegat (`free -m`)

**predict.py**

- [x] Excepcions al `.gitignore` per a `letter_bias.json`, `priors.json` i `ablations.csv`
- [ ] La prova des d'un clon net
- [x] El nivell tret de l'`id` quan falta `level`, amb una prova
- [x] `eval.py`: guardar la màquina (`machine`), `--debias batch`, `--expression`, i les columnes `stage`, `shortened` i `expr*`
- [x] Guardrails de `predict.py`: línies trencades, índex absent, problemes massa llargs escurçats, temps planificat abans de cada crida, `PREDICT_DEBIAS=batch`
- [ ] `baseline-org` i `baseline`, i l'anàlisi d'errors del baseline per tipus de problema
- [ ] Etapa 1: anàlisi de problemes gairebé idèntics entre train i validació, llindar, i validació sense germans
- [ ] Etapa 2: solucionadors en Python per als tipus més freqüents
- [ ] Etapa 3: expressió escrita pel model i calculada per Python (codi fet a `copilot/mathexpr.py`, desactivat per defecte; falta comprovar la gramàtica a la placa i mesurar-la)
- [ ] Etapa 4: RAG amb les solucions de l'agent
- [ ] Etapa 5: biaix, calibració per lot i rotacions
- [ ] Etapa 6: millor OCR, i la imatge per als problemes sense opcions
- [ ] Etapa 7: pressupost adaptatiu
- [ ] Ajust fi (LoRA) del Qwen 0.8B, convertit a GGUF i mesurat
- [ ] Un altre model de \~1–2B, i el raonament curt
- [ ] Mesura en català i en anglès amb els mateixos problemes
- [ ] Configuració final confirmada a la placa amb `--limit 0` i `--val-years` (D3)
- [ ] Anàlisi d'errors final per tema, idioma i nivell, amb n, i 10 errors explicats

**Dades i pistes**

- [ ] `prepare_m3kang.py` amb les llengües del pla i les imatges
- [ ] `prep/agent/` i els cinc lots, validats amb `check_agent_output.py`, i 20 textos de cada lot revisats per una persona
- [ ] La columna `source`, `import_hints.py`, i el graó 3 llegint el banc
- [ ] La línia base del Cangur per a tots els problemes elegibles
- [ ] L'experiment de pistes i el valor de `τ` (D2)
- [ ] La regressió logística per valorar les pistes (pla 6.4)
- [ ] `copilot/hintgen.py`, el filtre estricte per als problemes externs i `prep/pregen_hints.py`
- [ ] Temps de la generació a la placa amb 1 i 2 veïns, i triar el prompt
- [ ] Pistes generades per endavant per a tot el banc, comprovant en uns quants casos que la placa i el portàtil donen el mateix text
- [ ] Mesures de les pistes (fuites, correcció, utilitat, temps, llengua) (D4)
- [ ] L'encert de `topics.py` contra els temes de referència, i les pistes de mètode corregides
- [ ] L'encert del filtre de fuites amb els 200 casos
- [ ] Graó 1: en 20 problemes, el problema semblant és més fàcil i del mateix tema?
- [ ] El temps de cada graó d'ajuda i de cada crida del Cangur a la placa (`prompt_n`)

**Tutor**

- [ ] Problemes externs amb el mateix recorregut que els del banc: el harness calcula la resposta, i a partir d'aquí hi ha la correcció, el Cangur, les pistes generades i la solució
- [ ] L'avís dels problemes externs sempre visible, amb el text exacte (substitueix el `DISCLAIMER` de `copilot/tutor.py`)
- [ ] Els intents amb problemes externs marcats a `tutor.db`, per poder-los separar a les mesures
- [ ] Problemes externs provats amb els problemes inventats: encert del harness, i el recorregut sencer
- [ ] El pont d'idioma complet: tres etapes, amb la imatge original en la llengua d'origen
- [ ] El doble Elo: `sim/students.py --db data/tutor.db`
- [ ] Tot el recorregut a la placa: respondre, els quatre graons, ensenyar el Cangur, una pista rebutjada, una pista acceptada, i la matriu LED

**Documentació i lliurables**

- [ ] Les correccions de la secció "Documentació a corregir", i `STATUS.md` i `DECISIONS.md` al dia
- [ ] Dashboard Tukey: cada panell amb una pregunta, un gràfic, l'evidència i la decisió. Inclou un panell per a les pistes generades i les conclusions a `notes.json`
- [ ] Revisar el dashboard amb els tres criteris del jurat (utilitat, adequació i coherència), i que els números coincideixin amb els del README i el pitch
- [ ] README, en l'ordre de `publish-project`: què fa (amb foto o vídeo), l'arquitectura (amb diagrama), com replicar-ho, els resultats contra el 22,5%, l'anàlisi d'errors, què no ha funcionat, i l'equip. Ha d'explicar les limitacions tal com diu la secció "Com funciona el projecte"
- [ ] Comprovar el README clonant el repo en una carpeta nova
- [ ] `LICENSE` amb els noms i els crèdits, citant M3Kang
- [ ] Arduino Project Hub amb les sis seccions, amb fotos i captures de l'equip
- [ ] Repo públic: les comprovacions de `publish-project`, cap secret, i confirmar si es poden publicar `descripcio_main_challenge/` i `descripcio_side_challenge/`
- [ ] Enviar els enllaços de GitHub i del Project Hub als organitzadors
- [ ] Pitch de 3 minuts: el problema (20 s), la demo (90 s), els números (40 s) i què hem après (30 s). Les xifres de PISA, comprovades
- [ ] Demo: problemes provats el mateix dia, Wi-Fi apagat, dos assajos amb cronòmetre i un vídeo de reserva

## Documentació a corregir

| Document | Què no quadra | Correcció |
| --- | --- | --- |
| `CLAUDE.md` | "El model no escriu text per a l'alumne" | El model només escriu pistes d'una frase, sempre filtrades, i si una pista es rebutja en surt una de mètode |
| `CLAUDE.md` | "Un problema extern mai es respon d'entrada" | Els problemes externs segueixen el mateix recorregut que els del banc, amb la resposta del harness i l'avís sempre visible. La resposta tampoc es mostra fins que l'alumne respon o demana la solució |
| `CLAUDE.md` | "Tampoc pujar res derivat de M3Kang" | Mai pujar res que contingui text de M3Kang ni les etiquetes per problema |
| `CLAUDE.md` | Diu que `results/ablations.csv` és la font de veritat, però el `.gitignore` exclou `results/*` | Afegir una excepció per a `ablations.csv` |
| `copilot/tutor.py` | El `DISCLAIMER` actual i el flux dels problemes externs (només tema, nivell i problemes semblants; la suposició només si l'alumne la demana) | El mateix flux que els problemes del banc, amb l'avís nou |
| `docs/STATUS.md` | Als pròxims passos hi falten la preparació al portàtil i la posada a punt de la placa. A "Qui fa què" hi falten dos membres | Actualitzar-ho amb aquest document |
| `docs/DECISIONS.md` | Tres propostes de Claude pendents. Hi falten les decisions noves: validació, agent, pistes generades, problemes externs, harness i dades. La de 14 nov sobre problemes externs queda substituïda | Afegir-les. Com que el fitxer només admet afegir línies, la decisió antiga es deixa i se n'hi afegeix una de nova que la substitueix |
| `pla_projecte.md` | Secció 3: problemes externs "prioritat baixa" i sense resposta d'entrada. Secció 4: `app/` és la web (la matriu és a `applab/`). Secció 5: no hi ha el harness. Secció 8: "k-means". Secció 12: `adb forward tcp:7000` (ha de ser **8090**). Secció 13: el brick `web_ui`. Secció 7.1: falta dir que calen 4 encerts seguits. Tampoc hi són l'agent ni les pistes generades | Actualitzar-ho |
| `pla_projecte.md` / `README.md` | Llengües: `eng,cat,esp,arb,zho,fra` en un lloc i `eng,cat,esp,arb` a l'altre | Fer-les coincidir |
| `README.md` / `elo.py` | L'error de l'Elo surt com "\~65" en un lloc i "about 70" a l'altre | Tornar a executar `sim/students.py` |
| `README.md` | Està en anglès, i la convenció de l'equip és documentar en català. Hi ha molts `TODO`. La secció dels problemes externs ha quedat antiga | Decidir l'idioma i omplir-lo amb els resultats |
| `LICENSE` | "TODO: replace with your names" | Posar-hi els noms |
| `.skills/unoq-hardware-ui` | Explica la web amb el brick `web_ui` al port 7000 | Afegir que el nostre tutor és `app/server.py`, al port 8090 |

## Riscos

1. **`check_model.py` és el punt únic de fallada.** La correcció del biaix, les rotacions i la barra del Cangur depenen de les probabilitats de les cinc lletres. Encara no s'ha comprovat (D1).
2. **Pistes generades falses o amb fuites.** El model encerta un 22,5%, i amb els problemes externs la resposta de referència és la del harness, que pot fallar. Ho controlen el filtre estricte, l'agent fent de jutge, la revisió humana i la pista de reserva. Els problemes de la demo s'han de provar abans.
3. **El temps de la generació.** Entre 28 i 56 s per pista, segons l'estimació. Per als problemes externs, l'alumne pot haver d'esperar.
4. **El portàtil i la placa podrien no donar les mateixes lletres** per diferències d'arrodoniment entre CPU. Es comprova amb 50 problemes, i els resultats finals es fan sempre a la placa.
5. **La mostra de validació pot canviar** si s'afegeixen llengües a `val.jsonl`. Cal mesurar sempre amb el mateix `--languages`.
6. **Un sol torn per al model a cada màquina.** Durant la demo, a la placa no ha de córrer res més.
7. **El soroll.** Amb 50 problemes, l'interval és d'uns ±12 punts. Cap millora es confirma sense `--limit 0`.
8. **La matriu LED pot no arribar al tutor** si App Lab executa l'app en un contenidor on `127.0.0.1` no és la placa.
9. **Números que no es poden fer servir:** els mesurats amb `tests/fake_llama.py`, els dels problemes inventats presentats com si fossin de M3Kang, i qualsevol temps mesurat al portàtil. Cap d'aquests pot sortir al README, al dashboard ni al pitch.
10. **Resposta equivocada en un problema extern.** Si el harness s'equivoca, el tutor corregirà malament i el Cangur "ensenyarà" cap a una resposta incorrecta. L'avís ho diu sempre, i l'encert publicat del harness indica quant s'hi pot confiar.
11. **Germans entre train i validació.** Si l'etapa 1 troba problemes repetits, la validació actual sobreestima l'encert. S'ha de mesurar també sense germans, i explicar-ho.
12. **Ajust fi.** Es pot sobreajustar al train, i no sabem si es poden publicar uns pesos entrenats amb M3Kang (llicència de recerca).

## Decisions i preguntes obertes

**Per decidir com a equip**

- [ ] Com es fa la validació: el 15% a l'atzar o `--val-years 2023,2024`
- [ ] Les llengües que es preparen
- [ ] Confirmar o descartar les tres propostes de Claude: el port 8090, els temes per paraules clau i la K de l'Elo
- [ ] Les regles noves del `CLAUDE.md` (dades i pistes generades), apuntades a `DECISIONS.md`
- [ ] El llindar de la decisió D4
- [ ] En quin idioma va el README, i el nom de l'equip a la `LICENSE`

**Supòsits sobre el test ocult** (14 nov: no podem fer preguntes als organitzadors; ens guiem per `SETUP.md` i les presentacions)

- El jurat carrega el nostre repo i executa `predict.py`. Per tant, `predict.py` ha de funcionar només amb el que es pot pujar (codi, `priors.json`, `letter_bias.json`). Si falta un fitxer (`index.db`, `train.jsonl`), salta l'etapa, mai peta.
- Format: el de `prepare_m3kang.py` (mateix OCR de les opcions, camp `level`, ids `lvl-X_ANY_N`).
- Idiomes: de moment treballem amb `eng` i `cat`. La resta queda aparcada fins que tinguem més informació.
- Xifres agregades: es pugen (decisió del 14 nov). Pistes amb un model gran fora de la placa: confirmat (Marc).
- **Per decidir com a equip:** el lliurament del dashboard Tukey, i si fem servir (i publiquem) un model ajustat amb el train de M3Kang.

## Validació contra els requisits

He comparat el pla amb `SETUP.md` (passos 13–15), la skill `publish-project`, els dos vídeos dels organitzadors i l'enunciat del Side Challenge Tukey. **Tots els requisits hi són coberts.** N'hi ha dos que depenen de preguntes als organitzadors.

| Requisit | Font | On és al pla | Estat |
| --- | --- | --- | --- |
| Funciona del tot a la placa, sense xarxa | Repte | Tutor, models i pistes generades a la placa. L'agent només prepara textos per endavant. Serveis que arrenquen amb la placa | Cobert |
| Fa servir M3Kang de manera innovadora | Repte | Clau de respostes, mapa de dificultat, veïns, el mateix problema en diversos idiomes, i un banc de pistes que fa d'exemple per al model | Cobert |
| Guia sense donar la resposta | Repte | Filtre de fuites, filtre estricte per als problemes externs, la solució només si l'alumne la demana | Cobert i mesurat |
| La part de Teach es mesura amb números | `SETUP.md` 13 | Δ, fuites, correcció de les pistes, simulació de l'Elo, temps per graó i graó 1 | Cobert |
| `predict.py` compleix el contracte i es puntua al test ocult | `SETUP.md` 11, 13.3 | Secció "predict.py" | Cobert. Falta saber on s'executa |
| Superar el baseline del 22,5% | `SETUP.md` 11 | Harness de 7 etapes i canvis de model | Cobert. El resultat no està garantit, i es dirà |
| 60 s per problema, 4 GB de RAM, cap dependència nova a la placa | `SETUP.md` 11, 14 | Temps a la placa, `free -m`, només la llibreria estàndard | Cobert |
| Matriu LED i web, sense mòduls externs | `SETUP.md` 14.4 | `applab/math-matrix` i la web al port 8090 | Cobert |
| Anàlisi d'errors per tema, idioma i nivell, amb n i 10 errors explicats | `SETUP.md` 14.3 | Secció "predict.py" i temes de referència | Cobert |
| Repo públic amb el codi, `config.env`, els serveis i l'app; README de 7 parts, provat amb un clon net; llicència i crèdits | `SETUP.md` 15.1, `publish-project` | Documentació i lliurables | Cobert |
| Cap dada de M3Kang, tampoc a l'historial | `SETUP.md` 15 | Secció "Dades" i comprovacions de `publish-project` | Cobert |
| Project Hub de 6 seccions, i enllaços enviats | `SETUP.md` 15.2 | Documentació i lliurables | Cobert |
| Pitch de 3 minuts i demo amb el Wi-Fi apagat | `SETUP.md` 14.5 | Documentació i lliurables | Cobert |
| Documentar-ho tot, també el que no funciona | Vídeo de Marc Pous | Secció "Com funciona el projecte" i README | Cobert |
| Dashboard: utilitat, adequació i coherència | Tukey | Dashboard i revisió amb els tres criteris | Cobert. Falta saber el format i el termini |

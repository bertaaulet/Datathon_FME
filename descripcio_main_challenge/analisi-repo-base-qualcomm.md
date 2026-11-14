# Anàlisi del repo base — Datathon FME 2026, repte Qualcomm "Math on the Edge"

> **Repo analitzat:** https://github.com/mpous/datathon-UPC-maths-qualcomm-arduino-unoq
> Estat revisat: commit `d6e3f1b` (13 nov 2026), 14 commits entre l'11 i el 13 de novembre de 2026, autor Marc Pous (`mpous`).
> Data de l'anàlisi: 14 nov 2026.

---

## Índex

1. [El repte en una frase](#1-el-repte-en-una-frase)
2. [Context i motivació](#2-context-i-motivació)
3. [Què es demana: Teach i Reason](#3-què-es-demana-teach-i-reason)
4. [La placa: Arduino UNO Q](#4-la-placa-arduino-uno-q)
5. [El pressupost de temps i memòria](#5-el-pressupost-de-temps-i-memòria)
6. [Els models](#6-els-models)
7. [El dataset M3Kang](#7-el-dataset-m3kang)
8. [Estructura del repo](#8-estructura-del-repo)
9. [Com funciona el pipeline per dins](#9-com-funciona-el-pipeline-per-dins)
10. [Regles de l'execució oficial (contracte de predict.py)](#10-regles-de-lexecució-oficial-contracte-de-predictpy)
11. [El baseline i per què és dolent](#11-el-baseline-i-per-què-és-dolent)
12. [Els 15 passos del README](#12-els-15-passos-del-readme)
13. [Idees que proposen els organitzadors](#13-idees-que-proposen-els-organitzadors)
14. [Lliurables i demo](#14-lliurables-i-demo)
15. [Com es puntua (el que se'n sap)](#15-com-es-puntua-el-que-se-nen-sap)
16. [Observacions pròpies: riscos i oportunitats](#16-observacions-pròpies-riscos-i-oportunitats)
17. [Referència ràpida de comandes](#17-referència-ràpida-de-comandes)
18. [Enllaços](#18-enllaços)

---

## 1. El repte en una frase

> Dissenyar i construir un copilot de matemàtiques que funcioni **del tot a l'Arduino UNO Q** i que faci servir **M3Kang** d'una manera innovadora per ajudar els alumnes a aprendre a raonar matemàticament.

Els usos més originals de M3Kang són els que més puntuen.

## 2. Context i motivació

- El nivell de matemàtiques a Catalunya baixa a les avaluacions internacionals (PISA).
- Els docents no donen l'abast, i molts alumnes es despengen en classes on tothom fa el mateix.
- La IA hi pot ajudar amb dues condicions:
  - ha de **guiar el raonament**, no fer els deures;
  - les **dades de l'alumne no poden sortir del dispositiu**, perquè tot és offline.

## 3. Què es demana: Teach i Reason

El copilot ha de fer **una** d'aquestes dues coses:

| Via | Què vol dir | Com es mesura |
| --- | --- | --- |
| **Teach** | Una experiència que desperti curiositat i guiï l'alumne **sense donar la resposta**: pistes, pràctica adaptativa, anàlisi d'errors, interacció física, col·laboració… | Demo, documentació i mesures pròpies |
| **Reason** | Davant d'un problema tipus Cangur, triar la resposta correcta (A–E) | Objectivament, amb un **test ocult** dels organitzadors |

**Matís important:** el README (passos 13.3 i 14) diu que el `predict.py` de **tots** els equips es puntua contra el test ocult, sigui quina sigui la via. Per tant, a la pràctica hi ha dues notes: l'encert de `predict.py` i la qualitat i originalitat de la proposta.

Usos de M3Kang que suggereixen: base de coneixement per a RAG, conjunt d'entrenament, font d'embeddings, mapa de dificultat, pont multilingüe "o una cosa que encara no s'hagi acudit a ningú".

## 4. La placa: Arduino UNO Q

L'Arduino UNO Q (4 GB) té **dos cervells** a la mateixa placa:

| Part | Maquinari | Què hi funciona |
| --- | --- | --- |
| **Linux** (Debian) | Qualcomm QRB2210, 4 nuclis Arm Cortex-A53 | Servidors de models (llama.cpp), cerca, codi Python, part Python de l'app d'App Lab |
| **Microcontrolador** | STM32, temps real | El *sketch* Arduino, que controla la **matriu LED de 8×13** |

- Les dues parts es comuniquen amb el **Bridge** (crides remotes): `Bridge.call(...)` i `Bridge.provide(...)`.
- **Cap mòdul extern**: ni Modulino, ni botons, ni sensors. L'alumne interactua amb una **pàgina web servida per la placa** (o la terminal) i la placa respon amb la **matriu LED**: una lletra, ✓/✗, un nivell, vots…
- Connexió: SSH per Wi-Fi (`ssh arduino@<ip>`) o `adb shell` per USB, que és la via de reserva i la que s'ha de fer servir a la demo amb el Wi-Fi apagat.
- Contrasenya de la configuració inicial a App Lab: `opensource`.
- Per apagar-la: sempre `sudo poweroff`. Desendollar-la en calent pot corrompre fitxers.

## 5. El pressupost de temps i memòria

### Velocitat mesurada a la placa

| Operació | Cost |
| --- | --- |
| Llegir el prompt (prefill) | ~11 tokens/s |
| Escriure (generació) | ~6 tokens/s |
| Problema amb opcions (80–300 tokens), només llegir-lo | 7–25 s |
| Respondre amb 1 lletra | ~9 s de mitjana (8,7 s) |
| Amb 2 exemples RAG | ~30 s |
| 1 línia de raonament + lletra | ~26 s |
| Imatge amb `--image-max-tokens 128` | 28–38 s |
| Imatge per defecte (292 / 656 tokens) | 68 s / 185 s (no hi cap) |
| Embedding d'un problema i cerca | menys d'1 s |
| Indexar 911 problemes | ~4 min |

**Límit:** 60 s per problema. El codi reserva 3 s de marge (`MARGIN = 3.0`).

**Regla general:** embeddings, cerca, Python i maquinari són gairebé gratis; el model de llenguatge és car. Cada token del prompt costa ~0,09 s de lectura i cada token generat ~0,17 s.

Càlcul ràpid del pressupost: temps ≈ tokens_prompt / 11 + tokens_generats / 6 ≤ 57 s.

### Memòria

- Total utilitzable: ~3,6 GB, més 1,8 GB de swap.
- Els dos servidors junts ocupen ~1,1 GB i en deixen ~2,5 GB lliures, que s'han de compartir amb App Lab, l'app i el vostre codi.
- Sense `--parallel 1 --cache-ram 0` (i, al model de llenguatge, `--ctx-checkpoints 2`), llama.cpp reservava fins a 8 GB de memòria cau i el sistema el matava (OOM).
- Disc: calen ~2–3 GB lliures (llama.cpp ~350 MB, models ~870 MB, paquets).

## 6. Els models

Tot està fixat a versions concretes perquè els resultats dels equips siguin comparables. Els valors són a `config.env`.

| Rol | Model | Fitxer | Mida | Port |
| --- | --- | --- | --- | --- |
| Model de llenguatge | Qwen3.5 0.8B, Q8_0 (GGUF de bartowski) | `Qwen_Qwen3.5-0.8B-Q8_0.gguf` | 835 MB | 8081 |
| Embeddings | bge-small-en-v1.5, Q8_0 (CompendiumLabs) | `bge-small-en-v1.5-q8_0.gguf` | 37 MB | 8082 |
| Visió (opcional) | Qwen3.5 0.8B + `mmproj-Qwen_Qwen3.5-0.8B-f16.gguf` | projector | 205 MB | 8083 |

- **Motor:** llama.cpp al commit `2cbe0ec429b849a88664e0f62388fc92a5abd699`, compilat a la placa amb `-DGGML_NATIVE=ON` (instruccions NEON). La compilació triga uns 30 minuts.
- **Revisions de Hugging Face:**
  - LLM: `f36b1ea49a332ede8fe5f389bbf5b3575ef71f48`
  - Embeddings: `d32f8c040ea3b516330eeb75b72bcc2d3a780ab7`
- **SHA256:**
  - LLM: `7182e2362766bb9569209bbc24cf1a4cdfbb8ab161babdb2080c84fa62c08c2f`
  - Embeddings: `ec38e8da142596baa913124ae50550de284b6916bf59577ef2f0cb9660c2f514`
  - mmproj: `1dc1351c82e41b48edb55fd6ddfa7ca60fb5a16b3d5abf3ce7054880dd022847`
- **Opcions clau del model de llenguatge:** `--ctx-size 4096 --threads 4 --parallel 1 --cache-ram 0 --ctx-checkpoints 2 --jinja --reasoning off --reasoning-budget 0`. El "pensament ocult" està desactivat.
- **Embeddings:** `--embedding --ctx-size 512 --batch-size 512 --ubatch-size 512`. bge treballa amb textos de fins a 512 tokens; el codi talla l'entrada a 1.400 caràcters.
- bge necessita el prefix `"Represent this sentence for searching relevant passages: "` a les **consultes**, però no als documents desats.
- **bge-small només està entrenat en anglès.**
- Els servidors escolten només a `127.0.0.1` i funcionen com a serveis systemd (`math-llm`, `math-embed`) que arrenquen amb la placa.
- Es pot canviar de model si cap a la RAM, respon a temps i la llicència ho permet. En aquest cas cal actualitzar repositori, revisió, fitxer i SHA256 a `config.env` i als fitxers de servei.

## 7. El dataset M3Kang

- **Font:** https://huggingface.co/datasets/qualcomm/M3Kang (Torres-Camps et al., 2026, arXiv:2601.16218).
- **Contingut:** 1.747 problemes del **Cangur matemàtic** de 2007 a 2024, en **8 nivells** (el nivell 0 és 5è de primària) i **108 idiomes**, català inclòs.
- Cada problema té 5 opcions (A–E) i una etiqueta amb la lletra correcta.
- Splits: `high_quality` (4 fitxers parquet) i `standard` (10). El primer fitxer de `high_quality` té els 1.747 en anglès i català, i menys en altres idiomes: `fra` 1.427, `esp` 1.368, `deu` 716…
- El mateix problema té el **mateix `id` en tots els idiomes**, per exemple `lvl-0_2015_13`, amb format `lvl-<nivell>_<any>_<número>`.
- **Lletra més freqüent:** D (24,6–25%). És el valor de `FALLBACK_ANSWER`.
- **No hi ha camp de tema.** Per a l'anàlisi d'errors per tema us l'heu de construir (clústers d'embeddings, paraules clau o etiquetatge manual) i explicar com.

### El parany: les opcions són a la imatge

El camp `text` té l'enunciat, però **les opcions A–E estan dibuixades a la imatge**. `laptop/prepare_m3kang.py` les llegeix amb OCR (RapidOCR, offline) al portàtil:

- Llegeix les 5 opcions en el **62%** dels problemes (1.078/1.747), i en el 74% dels `text_only` (601/811).
- Per a la resta, `"options": {}` i el model només veu la pregunta.
- Errors típics: opcions que són figures o gràfics, fraccions mal llegides (`1/2` → `12`), opcions duplicades.
- Segons el README, **millorar l'OCR és una de les maneres més fàcils de pujar nota**.
- L'OCR triga uns 15 minuts per idioma i es desa a `data/.ocr_cache.jsonl`.

### Format de les dades

```json
{"id": "lvl-0_2015_13", "language": "eng", "level": 0, "year": 2015, "text_only": true,
 "text": "13. For 3 days, the cat Joy has been catching mice. ...",
 "options": {"A": "12", "B": "15", "C": "18", "D": "20", "E": "24"}, "label": "C"}
```

### Train i validació

- Per defecte, un hash de l'`id` envia el 15% a validació. Amb l'anglès surten 1.466 de train i 281 de validació.
- Les traduccions d'un mateix problema mai queden repartides entre train i validació.
- `--val-years 2023,2024` reserva anys sencers per a validació, cosa més semblant a un test no vist.

### Llicència

**Només per a recerca.** No es pot publicar: `train.jsonl`, `val.jsonl`, `data/images/` ni `index.db` (conté el text dels problemes). El `.gitignore` ja ho exclou. Cal enllaçar el dataset card i citar el paper.

## 8. Estructura del repo

```text
config.env                 configuració compartida per bash i Python (models, ports, regles)
predict.py                 ENTRADA OFICIAL: problemes .jsonl -> CSV amb una lletra per problema
eval.py                    mesura encert i latència a la validació; registra a results/ablations.csv
build_index.py             fa l'embedding del train -> data/index.db (SQLite)
copilot/
  pipeline.py              solve(): un problema -> una lletra (el fitxer que s'ha de canviar primer)
  llm.py                   format del prompt, missatges, crida amb gramàtica [A-E]
  rag.py                   índex SQLite i cerca per similitud de cosinus
  embed.py                 crida al servidor d'embeddings i normalitza els vectors
  client.py                POST/GET JSON amb urllib (només stdlib)
  config.py                llegeix config.env (les variables d'entorn tenen prioritat)
laptop/
  prepare_m3kang.py        descàrrega + OCR + split train/val (al portàtil)
  requirements.txt         huggingface_hub, pyarrow, rapidocr_onnxruntime
board/
  00_check_board.sh        diagnòstic (RAM, disc, rellotge, SSH, apt, xarxa)
  01_install_packages.sh   apt-get dels paquets de compilació
  02_build_llama_cpp.sh    llama.cpp al commit fixat
  03_download_models.sh    descàrrega + verificació SHA256
  04_install_services.sh   serveis systemd math-llm i math-embed
  05_smoke_test.sh         prova de punta a punta
  common.sh, systemd/      utilitats i plantilles dels serveis
explorer/
  server.py, index.html    web (port 8000) per explorar problemes, preguntar al model i veure veïns
data/
  sample_problems.jsonl    5 problemes inventats per a proves ràpides
.skills/                   4 skills per a Claude (vegeu més avall)
```

**Restricció important:** a la placa, el codi només fa servir la **llibreria estàndard de Python**. No hi ha `pip`.

### Skills incloses (`.skills/`)

| Skill | Per a què |
| --- | --- |
| `unoq-board` | Connectar-se, revisar serveis i RAM, i resoldre problemes de la placa |
| `m3kang-copilot` | Canviar el copilot, fer experiments i analitzar errors |
| `unoq-hardware-ui` | App d'App Lab amb web (port 7000) i matriu LED via Bridge; inclou una app completa d'exemple |
| `publish-project` | Preparar el repo públic i la pàgina a Project Hub, amb comprovacions de llicència |

Per fer-les servir amb Claude Code: `mkdir -p .claude && ln -s ../.skills .claude/skills`.

## 9. Com funciona el pipeline per dins

Per a cada problema, `predict.py` crida `copilot.pipeline.solve()`:

1. **Recuperació (opcional, `--rag K`).** `rag.Index.search()` fa l'embedding del problema (amb el prefix de consulta), calcula el producte escalar amb tots els vectors del train carregats a memòria i n'agafa els K millors. A `eval.py`, `exclude_id` evita recuperar el mateix problema en un altre idioma.
2. **Prompt.** `llm.build_messages()`:
   - *System:* "You solve multiple-choice math competition problems for school students. Read the problem and the options, then reply with the letter of the correct option." Es manté fix perquè `cache_prompt` reutilitzi aquesta part.
   - Cada exemple RAG va com un torn usuari/assistent: l'enunciat amb `Answer:`, i la lletra.
   - El problema: enunciat, `A) …` a `E) …` i `Answer:`. Si no hi ha opcions, s'hi afegeix "(The options are in a picture that you can't see. Pick the most likely letter.)".
   - Si s'envia una imatge, va en base64 cap al servidor de visió.
3. **Crida al model** amb `grammar: "root ::= [A-E]"`, `max_tokens: 1`, `temperature: 0`, `seed: 42`, `cache_prompt: true`. La gramàtica fa **impossible** qualsevol sortida que no sigui una lletra A–E.
4. **Temps.** El timeout de la crida és el temps que queda menys el marge de 3 s. Si hi ha timeout o `URLError`, respon `D` amb `status` = `timeout` o `error: …`.
5. **Sortida.** Una fila al CSV: `id, language, answer, seconds, status`.

### `eval.py`

- Agafa una mostra de la validació, sempre la mateixa (`random.Random(42)`). Per defecte `--limit 50`; amb `--limit 0` fa els 281 problemes en ~45 min.
- Mostra:
  - encert, comparat amb "sempre D" i amb l'atzar (20%);
  - latència: mitjana, mediana, pitjor i nombre de casos per sobre del límit;
  - encert per idioma, per nivell i segons si hi havia opcions;
  - recompte de lletres predites contra reals, per detectar biaixos.
- Desa `results/eval-<hora>-<nom>.csv` (detall per problema) i afegeix una línia a `results/ablations.csv` amb el commit de Git.

## 10. Regles de l'execució oficial (contracte de `predict.py`)

```bash
python3 predict.py --input problems.jsonl --output predictions.csv [--rag K]
```

- **Entrada:** JSONL amb, com a mínim, `id` i `text`, i amb `options` i `language` quan n'hi hagi.
- **Sortida:** CSV amb `id, language, answer, seconds, status`.
- **Una lletra A–E per a cada problema.**
- **Com a màxim 60 s per problema** (`TIME_LIMIT_SECONDS`).
- **Sense xarxa:** només servidors a `127.0.0.1`, sense descàrregues ni APIs al núvol.
- **Determinista:** temperatura 0 i `SEED=42`.
- **Cap dependència nova a la placa**, si no s'instal·la amb un pas documentat i funciona offline.
- El codi per ensenyar ha d'anar separat, per exemple a `copilot/tutor.py`, perquè l'execució oficial no canviï per accident.

## 11. El baseline i per què és dolent

Mesures dels organitzadors amb 40 problemes en anglès, `text_only`, amb les opcions llegides per OCR:

| Enfocament | Encert | Temps mitjà | Temps pitjor |
| --- | --- | --- | --- |
| Sempre `D` | ~25% (train) | 0 s | 0 s |
| **Baseline: 1 lletra amb gramàtica A–E** | **22,5%** (9/40) | 8,7 s | 12,7 s |
| Valor de l'opció en lloc de la lletra | 17,5% (7/40) | 9,3 s | 13,5 s |
| 1 línia de raonament + lletra | 17,5% (7/40) | 26,3 s | 35,0 s |

Conclusions:

- El baseline queda **per sota de "sempre D"** i és pràcticament igual que l'atzar.
- **Biaix de lletra fort:** 21 D i 14 A de 40, quan les respostes reals estaven repartides.
- Raonar triplica el temps i no millora l'encert.
- Exemple del README: davant de "2 + 3 × 4", el model respon C (24) en lloc de B (14).
- Amb RAG, els problemes semblants sovint són del mateix tema (per exemple, cubs), però la seva resposta no diu res de la d'aquest.

## 12. Els 15 passos del README

| Pas | On | Què | Temps |
| --- | --- | --- | --- |
| 0 | Portàtil | Configuració a App Lab (nom, contrasenya, Wi-Fi, **actualitzacions**), IP, SSH/adb | 15 min |
| 1 | Placa | Comprovar memòria, disc, rellotge sincronitzat i internet | 2 min |
| 2 | Placa | `apt-get install` de les eines de compilació. Si diu "not installable", esborrar `/var/lib/apt/lists/*` | 5 min |
| 3 | Placa | Compilar llama.cpp al commit fixat (fer-ho dins `tmux`) | 30 min |
| 4 | Placa | Descarregar els models i verificar el SHA256 | 5 min |
| 5 | Placa | Hello world amb el model de llenguatge (`llama-server`, `curl`, gramàtica A–E) | 10 min |
| 6 | Placa | Hello world amb els embeddings (384 dimensions) | 5 min |
| 7 | Placa | Serveis systemd `math-llm` i `math-embed` | 5 min |
| 8 | Placa | Clonar el repo i fer `predict.py` amb els 5 problemes d'exemple | 5 min |
| 9 | Portàtil | `prepare_m3kang.py --languages eng,cat` (OCR) | 30 min |
| 10 | Portàtil | Copiar `train.jsonl` i `val.jsonl` a la placa (`scp` o `adb push`) | 1 min |
| 11 | Placa | `eval.py --limit 50 --name baseline` | 10 min |
| 12 | Placa | `build_index.py --only-with-options` i `eval.py --rag 1` | 15 min |
| Opcional | Placa + navegador | Explorer (`explorer/server.py`, port 8000) i servidor de visió | 10 min |
| 13 | Equip | Pluja d'idees: triar una idea i com mesurar-la | 1 h |
| 14 | Placa | Implementar, mesurar, matriu LED + web, preparar la demo | La major part de la datathon |
| 15 | Portàtil | Publicar a GitHub i a Arduino Project Hub | 2 h |

**Els passos 1–8 són el mínim que tots els equips han de tenir funcionant.**

## 13. Idees que proposen els organitzadors

### Per ensenyar (Teach)

**Escala de pistes.** Cada petició d'ajuda puja un graó:

1. un problema semblant i més fàcil, ja resolt (veí per embeddings, de nivell inferior);
2. el tema o el mètode, a partir del que tenen en comú els veïns;
3. una pista d'una frase generada pel model; el codi la rebutja si conté el valor de l'opció correcta;
4. la solució, només si l'alumne la demana expressament.

Els graons 1 i 2 costen menys d'1 s. *Com mesurar-ho:* quantes pistes filtren la resposta, temps per graó, i qualitat dels veïns en 20 problemes jutjats a mà.

**Entrenador adaptatiu.** Un mapa de M3Kang amb embeddings, nivells i temes. Si l'alumne encerta, el següent problema és un veí de nivell superior; si falla, un del mateix tema i nivell inferior. Respon a la web, i la matriu mostra ✓/✗ i el nivell. No hi ha LLM al bucle. El perfil de l'alumne es desa en SQLite. *Com mesurar-ho:* temps per pas i alumnes simulats (es manté al tema? s'estabilitza al nivell adequat?).

**Caixa de debat per a la classe.** Els equips voten a la web i la matriu mostra els vots. Després el model defensa una altra resposta en dues frases, i es torna a votar. El problema s'envia al model quan surt a la pantalla, perquè `cache_prompt` ja el tingui llegit. *Com mesurar-ho:* temps entre el final de la votació i l'argument (`prompt_n`), i qualitat dels arguments en 20 problemes.

**Pont multilingüe.** L'alumne treballa en català i la cerca es fa amb la versió anglesa del mateix `id`. *Com mesurar-ho:* `eval.py --languages cat` contra `--languages eng` amb els mateixos problemes.

**Problemes adaptats per a dislèxia i discalcúlia.**

- *Dislèxia:* frases curtes, una idea per línia, la pregunta al final i les opcions una per línia, amb una lletra gran instal·lada a la placa (no carregada d'internet).
- *Discalcúlia:* nombres més petits, quantitats representades a la matriu, un pas cada vegada.
- Les versions es generen **per endavant**, perquè reescriure costa 10–20 s per problema, i es desen en SQLite.
- El codi comprova que es conserven tots els nombres i opcions i que la resposta no canvia.
- L'alumne o el docent tria el mode; ningú queda etiquetat.
- *Com mesurar-ho:* quantes reescriptures passen la comprovació, si l'encert del model sobre les versions adaptades es manté, mètriques de llegibilitat i, si és possible, l'opinió d'un docent o especialista.

### Per raonar (Reason)

- **Corregir el biaix de lletra** amb `"logprobs": true, "top_logprobs": 5`.
- Demanar el valor o fer raonar, però combinat amb un prompt millor o exemples.
- **Descompondre:** classificar el tipus de problema i calcular amb Python el que es pugui.
- **Llegir millor les opcions:** millorar l'OCR o retallar la part de baix de la imatge.
- **Fer servir la imatge** amb el servidor de visió, mesurant RAM i temps.
- **Millorar la cerca:** embeddings + paraules clau, o un llindar de similitud.
- **Canviar de model**, si hi cap i respon a temps.

### Criteris per triar idea (pas 13.4)

- Fa servir M3Kang d'una manera que els altres equips no faran?
- Guia l'alumne sense donar la resposta?
- Aprofita la placa (matriu LED, offline)?
- Es pot mesurar amb un número, abans i després?
- Cap en 60 s per pas i 4 GB de RAM?
- Es pot ensenyar en directe en 3 minuts?

## 14. Lliurables i demo

### 1. Repo públic a GitHub

- Codi complet i reproduïble: `config.env` amb els models fixats, fitxers de servei, app d'App Lab.
- Llicència pròpia (per exemple MIT) i crèdits del que s'ha reutilitzat.
- README amb aquest ordre:
  1. què fa, amb foto o vídeo;
  2. l'arquitectura: Linux, microcontrolador, Bridge, servidors i ús de M3Kang;
  3. com replicar-ho a partir d'una placa amb els passos 0–12;
  4. resultats de `ablations.csv` comparats amb el baseline del 22,5%;
  5. **anàlisi d'errors per tema, idioma i nivell**, amb el nombre de problemes al costat de cada percentatge i alguns errors explicats;
  6. què no ha funcionat;
  7. l'equip.
- **Res de dades de M3Kang**, també a l'historial de Git. La skill `publish-project` porta les comandes per comprovar-ho.

### 2. Projecte a Arduino Project Hub

Introducció, components, arquitectura, pas a pas, resultats i anàlisi d'errors, i què heu après. Un exemple de format: el tutorial de Marc (Edge Impulse) sobre LLM a l'UNO Q.

### 3. Demo en directe i pitch de 3 minuts amb la placa

| Part | Temps | Contingut |
| --- | --- | --- |
| El problema | 20 s | A qui ajuda el copilot i per què és offline |
| La demo | 90 s | El copilot funcionant en directe a la placa |
| Els números | 40 s | Encert contra el 22,5%, latència, anàlisi d'errors |
| Què heu après | 30 s | Què no ha funcionat i què faríeu després |

Per a la demo:

- **Wi-Fi apagat**, serveis arrencats amb la placa, i el portàtil sense fer cap feina. Si cal mostrar la web al portàtil, fer servir `adb forward tcp:7000 tcp:7000`.
- Problemes triats i provats a la placa el mateix dia.
- Assajar amb cronòmetre almenys dues vegades.
- Gravar un vídeo de reserva.

## 15. Com es puntua (el que se'n sap)

El repo **no inclou cap rúbrica numèrica**. El que es dedueix del text:

- **Reason:** encert de `predict.py` al test ocult, complint el contracte. No sabem quins idiomes, nivells ni anys tindrà, ni si hi haurà opcions.
- **Teach:** demo i documentació, especialment l'**originalitat en l'ús de M3Kang**, que guiï sense donar la resposta, i que estigui **mesurat**.
- En tots dos casos: reproductibilitat, qualitat de l'anàlisi d'errors i honestedat en els resultats, incloent-hi el que ha anat malament.
- Amb 50 problemes o menys, una diferència d'una o dues respostes és soroll. Els resultats finals s'han de confirmar amb `--limit 0`.

## 16. Observacions pròpies: riscos i oportunitats

Aquestes observacions surten de llegir el codi. **Les marcades com a "sense verificar" s'han de comprovar a la placa o amb les dades.**

1. **El biaix de lletra és un guany gairebé gratis.** El baseline perd contra "sempre D". Es poden demanar les probabilitats de les lletres A–E (`logprobs`) en la mateixa crida i calibrar-les amb la distribució del train o amb un prompt sense contingut. No costa temps extra.
2. **Possible fuga de dades entre nivells (sense verificar).** `exclude_id` només exclou el mateix `id`. El Cangur comparteix problemes entre categories del mateix any amb ids diferents (`lvl-0_2015_x` i `lvl-1_2015_y`). Si és així:
   - la validació amb RAG queda inflada, i caldria excloure també els quasi duplicats;
   - si el test ocult surt de M3Kang, una cerca per similitud alta podria trobar el problema "germà" i la seva etiqueta.

   *Comprovació:* calcular la similitud màxima de cada problema de validació amb el train.
3. **Robustesa de `predict.py`.** `solve()` només captura `socket.timeout`, `TimeoutError` i `URLError`. Un `ConnectionResetError` o `http.client.RemoteDisconnected` (si el servidor reinicia), o un JSON inesperat, **aturarien tota l'execució oficial**. Cal un `except Exception` final que respongui la lletra per defecte.
4. **Timeouts encadenats (sense verificar).** Amb `--parallel 1`, si el client es cansa d'esperar, el servidor podria seguir processant la petició abandonada i endarrerir la següent. Cal mirar-ho a `journalctl -u math-llm` en provocar un timeout.
5. **Els embeddings són anglesos.** Per al català (i el test ocult, si és multilingüe), és millor cercar amb el text anglès del mateix `id` quan hi sigui, o traduir només la cerca.
6. **Els exemples RAG porten només la lletra**, sense cap explicació. Aporten format, però poc raonament. Una alternativa és fer servir els veïns per **inferir el tipus de problema** i triar l'estratègia: calcular amb Python, un prompt específic…
7. **El 38% dels problemes no té opcions.** El model hi endevina a cegues. Per a aquests casos, una prior per nivell o per posició (o la imatge, si hi cap en temps) és millor que deixar-ho al model.
8. **La cerca és un bucle en Python pur** sobre ~1.500–2.000 vectors de 384 dimensions. Va bé a aquesta escala, però si s'indexen molts idiomes, convé precalcular o filtrar per idioma i nivell.
9. **Inconsistència menor al README:** arrenca l'explorer amb `--host 0.0.0.0` però diu que només escolta a la placa.
10. **Validació més realista:** fer servir `--val-years 2023,2024` per acostar-se a un test d'anys no vistos.

## 17. Referència ràpida de comandes

```bash
# --- Placa: serveis ---
systemctl status math-llm math-embed --no-pager
curl -s http://127.0.0.1:8081/health ; curl -s http://127.0.0.1:8082/health
journalctl -u math-llm -f
sudo systemctl restart math-llm math-embed
free -m

# --- Placa: execució oficial i avaluació ---
cd ~/datathon-UPC-maths-qualcomm-arduino-unoq
python3 predict.py --input data/sample_problems.jsonl --output results/check.csv
python3 eval.py --limit 50 --name <experiment>
python3 eval.py --limit 0 --name <experiment>-full
python3 eval.py --languages cat --limit 100

# --- Placa: RAG ---
python3 build_index.py --input data/train.jsonl --db data/index.db --only-with-options
python3 eval.py --limit 50 --rag 1 --name rag1

# --- Placa: explorer ---
python3 explorer/server.py --host 0.0.0.0
# al portàtil: ssh -L 8000:127.0.0.1:8000 arduino@<ip>   o   adb forward tcp:8000 tcp:8000

# --- Portàtil: dades ---
python3 -m venv .venv && source .venv/bin/activate
pip install -r laptop/requirements.txt
python3 laptop/prepare_m3kang.py --languages eng,cat [--val-years 2023,2024] [--save-images]
scp data/train.jsonl data/val.jsonl arduino@<ip>:~/datathon-UPC-maths-qualcomm-arduino-unoq/data/

# --- App Lab ---
arduino-app-cli app new "math-matrix"
arduino-app-cli app start user:math-matrix
arduino-app-cli app logs /home/arduino/ArduinoApps/math-matrix --all

# --- Apagar ---
sudo poweroff
```

## 18. Enllaços

- **Repo base:** https://github.com/mpous/datathon-UPC-maths-qualcomm-arduino-unoq
- **Dataset M3Kang:** https://huggingface.co/datasets/qualcomm/M3Kang
- **Paper M3Kang:** https://arxiv.org/abs/2601.16218
- **Arduino UNO Q:** https://store.arduino.cc/pages/uno-q
- **Arduino App Lab:** https://www.arduino.cc/en/software/#app-lab-section
- **Exemples oficials d'App Lab:** https://github.com/arduino/app-bricks-examples
- **Arduino Project Hub:** https://projecthub.arduino.cc/
- **Tutorial de referència, LLM a l'UNO Q:** https://projecthub.arduino.cc/marc-edgeimpulse/running-local-llms-and-vlms-on-the-arduino-uno-q-with-yzma-74e288
- **Llibre de Marcelo Rovai, RAG a l'UNO Q:** https://mjrovai.github.io/genai-uno-q/content/rag/rag.html
- **llama.cpp:** https://github.com/ggml-org/llama.cpp
- **Qwen3.5 0.8B GGUF:** https://huggingface.co/bartowski/Qwen_Qwen3.5-0.8B-GGUF
- **bge-small-en-v1.5 GGUF:** https://huggingface.co/CompendiumLabs/bge-small-en-v1.5-gguf
- **RapidOCR:** https://github.com/RapidAI/RapidOCR

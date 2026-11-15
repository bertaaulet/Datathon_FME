# Estat actual

_Última actualització: 2026-11-15 04:05 — Irene (amb Claude): proves B1 (D2) i B3 del paquet de la Berta a la placa (secció "Pont d'idioma i pistes"). 03:15 — Irene (amb Codex i Claude): banc de pistes de l'agent i desplegament del tutor a la placa (secció "Pont d'idioma i pistes"). 02:45 — Irene (amb Claude): segona ronda de `predict.py` a la placa amb `dev50` (resultats i incidència USB). Pont d'idioma: Irene (amb Codex). La resta, de les 01:45 (Berta)._

## Fase
- **Tutor:** funciona a la placa amb el banc real (`tutor.db`, 601 problemes utilitzables, el Cangur precalculat), arrenca sol amb la placa i amb la matriu LED, i els problemes externs segueixen el mateix recorregut que els del banc (provat amb problemes inventats).
- **`predict.py`:** primera ronda (validació antiga) i **segona ronda amb `dev50` feta a la placa** (taules de sota). Cap configuració surt del soroll; el RAG no ajuda i dobla el temps. **Pendent: decidir el pas 4** (confirmació amb el conjunt de pràctica, `data/demo.jsonl`) i triar `config.env`.
- **Test final:** 20 problemes nous, executats amb el nostre `predict.py` **a la nostra placa** després del *last call* de les 12:00 (detall a `PLA.md`).
- **Lliuraments** (README, `LICENSE`, pitch, vídeo, Project Hub, dashboard): sense començar.
- La presentació és **diumenge**. El pla és a [`PLA.md`](PLA.md), i els problemes trobats a la placa a [`PROBLEMES.md`](PROBLEMES.md).

## Ara mateix
| Què | Estat |
| --- | --- |
| Segona ronda a la placa amb `dev50` (codi de `main` `c34427e`): `build_index.py --only-with-options --skip-suspect` (2.111 files) i `dev-nodebias`, `dev-debias`, `dev-debias-rag1`, `dev-debias-rag1-letter`. `letter_bias.json` no es va refer (ja havia acabat a les 23:33) | ✅ 01:33 |
| Pas 4: confirmació amb el conjunt de pràctica (`data/demo.jsonl`, 100 files): `demo-nodebias` i una segona línia per decidir amb la taula de la segona ronda (proposta: `demo-debias`, sense RAG) | ⏳ cal decidir-ho |
| Triar la configuració de `config.env` per al *last call* (no s'ha tocat) | ⏳ després del pas 4 |

## Línies de feina
Les tasques s'assignen en veu alta a l'equip; aquí només hi ha què queda i de què depèn. La llista completa és a `PLA.md`.

| Línia | Fet | Pendent | Depèn de |
| --- | --- | --- | --- |
| `predict.py` | Calibració, guardrails, biaix per lot, expressió (descartada), RAG amb pregunta + valor correcte, biaix robust | Segona ronda d'experiments; triar la configuració de `config.env`; `letter_bias.json` bo a la placa; confirmar amb el conjunt de pràctica; anàlisi d'errors; placa a punt per al *last call* | La placa |
| Pistes (Berta) | Infraestructura (lots, validació, importació, rànquing, similitud, pistes de mètode en 6 llengües). **Flux nou decidit** ([`PISTES.md`](PISTES.md)): sense companys, escala nova, Cangur en català, es guarden només les pistes que convencen | ~~Implementar-ho al codi; banc de pistes de l'agent~~ fet i desplegat (1232 pistes); ~~τ (D2)~~ fet a la placa: **les pistes bones no mouen el Cangur més que les absurdes** (p = 0,84), τ = 0,49; pistes generades pel model (desactivades: ~30 s i fluixes) | **Decidir què es fa amb la barra del Cangur (D2)** |
| Tutor (Teach) | Escala d'ajuda, Cangur, pont d'idioma, Elo de l'alumne (el dels problemes és fix), problemes externs, interfície nova, servei i reinici | Problemes 11–14 de `PROBLEMES.md`; revisar l'Elo i el pont d'idioma; reconstruir `tutor.db` amb les dades noves de l'OCR (si es vol) | — |
| Lliuraments | — | README, `LICENSE`, xifres de PISA, pitch, vídeo de reserva, Project Hub, dashboard Tukey | Resultats per als números |

## Pont d'idioma i pistes (desplegat a la placa el 2026-11-15)
- **Desplegat (03:01):** el servei `math-tutor` corre amb el codi de `c786d64` (pont d'idioma + flux nou de pistes; `main` només hi afegeix `prep/options_coverage.py` i documents) i la `tutor.db` nova. `api/state` respon 200. Instal·lat amb `install-pistes.sh` (verifica la base, atura el servei, canvia la carpeta i torna enrere sol si no arrenca). Còpia completa anterior a la placa: `~/Datathon_FME/projecte-backup-pistes-20261115-020117` (hora de la placa). S'hi han portat de l'oficial `data/` (train/val/dev/test, `priors.json` bo) i `results/`; el `priors.json` de git queda com `data/priors.json.from-git`.
- **`tutor.db` nova:** 616 problemes elegibles (només train; 56 apartats per dades dubtoses), Cangur en català precalculat (al portàtil: 528 realment equivocats, 88 fingits) i **1232 pistes de l'agent** (2 per problema, 7 lots). `HINTGEN=off` i `KANGAROO_LANG=cat` a `config.env` de la placa. **Es perd el progrés de l'alumne de prova `marc`** (27 intents): queda a la còpia anterior.
- **Revisió:** Codex va revisar 20 pistes per lot (20/20) i 50 temes (38/50 correctes). **Cap revisió humana** de pistes ni de temes.
- **Efecte de les pistes (portàtil, no placa):** de 1056 pistes sobre casos on el Cangur s'equivoca de veritat, **només 1 el convenç** (`HINT_TAU=1.0`). O les pistes no mouen el model o el llindar/la mesura no és adequada: **cal entendre-ho abans de fer-ne servir el número**. CSV per problema fora del repo.
- **D2 a la placa (B1, 2026-11-15 ~03:40):** 25 problemes on el Cangur s'equivoca, 3 pistes per problema escrites per Claude (bona de mètode, absurda de la mateixa llargada, amb fuita); 1 saltat perquè el model ja encertava. Mediana de Δ: bones +0,11 (13/24 cap a la bona resposta), absurdes +0,10 (14/24), amb fuita +0,26 (18/24). Mateix problema, bona contra absurda: **13 a 11, p = 0,84**. τ suggerit = **0,49** (desat a `tutor.db` de la placa; el tutor el fa servir després de `sudo systemctl restart math-tutor`). Pistes bones per sobre de τ: 5/24. Crida amb pista: mediana 12,5 s, màxim 22,1 s. El filtre de fuites no rebutja cap pista bona ni absurda i atura 23/24 de les de fuita. **Conclusió:** el model de 0,8B no distingeix una pista bona d'una absurda; la barra del Cangur no mesura la qualitat de la pista (cas previst a `PISTES.md`: treure-la o explicar-la com a limitació). També explica l'1/1056 del portàtil (`HINT_TAU=1.0` era massa alt, però baixar-lo no ho arregla). Una primera execució es va tallar per un reinici sol de la placa a les 02:33 (14/25, mateixos valors).
- **Pista generada a la placa (B3, 3 problemes inventats, `prep/hintgen_timing.py`):** amb `HINTGEN=on` (en una còpia del codi), pista en 2/3: 28,3 s i 34,1 s; total fins a tenir-la 51,5 s (el pitjor, 70,2 s, amb el model compartit amb una altra prova, inflat). El tercer problema no té veïns. Les pistes són fluixes (una gairebé fa el càlcul). Amb `HINTGEN=off`, `tutor.py` ni ho intenta i l'script escriu "no neighbour with agent hints", que és enganyós. **Es manté `HINTGEN=off`.**
- **Pendent:** decidir la barra del Cangur (D2); `sudo systemctl restart math-tutor` per carregar τ; revisió visual de la matriu LED; revisió humana d'una mostra de pistes.

- **Fet i provat al portàtil** (135 proves, totes amb dades inventades i servidors simulats): importació de traduccions a `tutor.db` amb controls (números, opcions, llargada; una traducció d'un altre traductor es manté si no es passa `--replace`), estat per llengua (`student_lang`: Elo, etapa i ratxa), avís quan falta la traducció (mai es canvia al català en silenci), opcions en la llengua d'origen, canvi de llengua sense perdre el progrés, frases del Cangur segons l'etapa, filtre de fuites en 6 llengües, i la marca "traducció automàtica" amb la procedència a l'enunciat, a cada frase del xat i a l'avís dels problemes externs. Interfície revisada al navegador amb una base inventada (àrab de dreta a esquerra, xinès, etapa 2 amb el botó).
- **Interfície acabada a partir del treball de Claude Fable i Opus:** taula `ui_text.py` servida per `/api/ui`, benvinguda, controls, camps, placeholders, avisos i etiquetes accessibles. Les traduccions són d'un LLM, sense revisió nadiua; l'avís i la procedència es mantenen també quan a l'etapa 2 només es tradueix el botó. El panell del docent, el seu botó i les seves etiquetes accessibles continuen en català. El títol del producte i els noms propis de les llengües no es tradueixen. Si falla la càrrega de la taula, es reintenta amb l'estat i s'avisa de la connexió.
- **Regles conservades:** etapa 1 bilingüe; etapa 2 català amb botó i un problema de cada tres en origen (segons els intents), ajuda en origen quan no hi ha botó; etapa 3 només català. Ara l'etapa 3 s'aplica també al problema actual, al xat antic i a l'anunci del lector de pantalla en el mateix canvi d'etapa o llengua. Les traduccions antigues d'una altra llengua no es reutilitzen.
- **Verificació nova de Codex:** execució aïllada de les 135 proves després d'integrar `origin/main` (`6a9d7e5`, inclòs el flux nou de pistes i totes les decisions conservades); contracte de `predict.py` amb les 5 files de `data/sample_problems.jsonl` i servidors simulats propis, totes amb lletra A–E i esquema CSV correcte. Cap canvi propi al harness oficial ni a `config.env`, índexs, conjunts d'avaluació o `letter_bias.json`; es conserven els canvis de l'equip ja integrats a `main` (la configuració és idèntica a `origin/main`). Això verifica lògica i contracte, no encert ni rendiment del model.
- **Integració del flux nou de pistes de `main` (`6a9d7e5`):** es conserven els cinc graons, el Cangur en català (real o fingit), les pistes d’agent ordenades i la retenció nova (text només de pistes que convencen en casos no fingits; la resta, comptadors). El graó 4 també segueix el pont: enunciat i opcions traduïts quan existeixen, avisos si falten, resposta amagada fins a provar o demanar-la. Les pistes d’agent o generades disponibles només en català es mantenen en català amb un avís traduït, sense fingir una traducció. Hi ha proves noves de les cinc llengües d’origen × tres etapes per al problema semblant, i de les opcions de reserva quan el text català no en té. La còpia local antiga encara té 601 elegibles: no s’ha reconstruït amb la política nova de només train ni recalculat el Cangur en català.
- **Navegador amb dades sintètiques:** sis llengües × tres etapes a 1440×1000 i 375×812; benvinguda en les sis llengües; botó de revelació en les cinc llengües d'origen; problema només en origen de l'etapa 2; formulari de pistes, resposta errònia i ajuda, extern amb avís, traducció absent, opcions sense traducció, error de connexió i recuperació, canvi de llengua després de resoldre i panell docent. Sense desbordament horitzontal observat; àrab RTL, xinès llegible i lletres A–E estables. Després de la integració, repetida la matriu de 36 casos amb el problema semblant del quart graó, sense desbordament ni origen a l’etapa 3, i provats els seus botons de resposta. Etiquetes comprovades a l'arbre accessible; no és una prova amb un lector de pantalla real.
- **Còpia de la base real:** `PRAGMA integrity_check = ok`; cobertura confirmada 601/601 cat i eng, 598 esp, 591 fra, 486 arb i 485 zho; 18 files de Haiku conservades. 18 recorreguts (sis llengües × tres etapes), sense crides de xarxa al model, correctes. Diagnòstics confirmats: 2 textos esp iguals al català i 15 textos zho amb més lletres llatines que caràcters xinesos. Hi ha 17 files traduïdes de problemes utilitzables sense opcions pròpies (esp 12, fra 3, arb 1, zho 1); també falten en català i existeixen en anglès: 14 mapes només numèrics i 3 amb lletres (no s'ha validat si són fórmules). La interfície avisa quan mostra les opcions disponibles en lloc d'un mapa traduït. Cap reimportació ni correcció de dades; hash de la base real igual abans i després de la còpia.
- **Frases del Cangur:** `copilot/phrases_mt.json` (OPUS-MT, sense tocar) + `copilot/phrases_fix.json` (correccions escrites per un LLM on la revisió va trobar errors: sentit contrari a `etapa1_torna`, l'avís dels externs il·legible en xinès, paraules inventades al costat dels marcadors, l'àrab sense 6 frases, tu i vous barrejats). Un control automàtic descarta les traduccions amb aquests símptomes. Resultat: les 43 frases i els 10 temes en les 5 llengües. **Cap parlant nadiu les ha revisades.**
- **Traduccions dels problemes** (`translate_ocr.py`, `m3kang_translated_v2`, fora del repo): les 4 llengües acabades. Importades a la `tutor.db` **del portàtil** després de provar-ho en una còpia aïllada (mateix resultat; repetir la importació no canvia res) i amb còpia de seguretat de la base anterior fora del repo. Problemes que el tutor pot fer servir amb text en cada llengua: esp 598/601, fra 591/601, arb 486/601, zho 485/601. Rebutjades pels controls: arb 243, zho 321, fra 15, esp 4. Es conserven les 18 traduccions del pilot de Haiku. `tutor.db` passa d'1,98 a 3,64 MB. Recorregut del tutor sobre una còpia, en les 6 llengües i sense model: enunciat i opcions en la llengua de l'alumne, marca de traducció automàtica, etapes 1 → 2 → 3. Senyals per revisar: 2 files d'esp iguals a l'original i 15 de zho amb més lletres llatines que caràcters xinesos (probablement fórmules).
- **Arreglat:** a l'etapa 3 encara sortien problemes només en la llengua d'origen (un de cada tres, codi anterior a la branca); ara l'etapa 3 és només català.
- **Pendent:** comprovar a la placa temps i memòria del flux complet amb la base nova; mesurar a la placa l'efecte de les pistes escrites en altres llengües (protocol a `DECISIONS.md`). **No verificat:** la qualitat lingüística de cap traducció.

## Placa
- **Muntatge:** passos 0–8 fets. llama.cpp `2cbe0ec`, serveis `math-llm` (8081), `math-embed` (8082) i `math-tutor` (8090, a `0.0.0.0`), tots habilitats. Accés per `adb shell` (USB). Repo a la placa: còpia dels fitxers a `~/Datathon_FME/projecte`, sense token.
- **Reinici:** la placa torna en 12 s i en menys d'un minut ho té tot a punt (serveis, models, tutor amb el banc real i matriu). Per a la demo n'hi ha prou d'endollar-la i esperar un minut.
- **Velocitat:** lectura 10,8 tok/s, escriptura 5,8 tok/s. **La caché no es reaprofita** si el prompt canvia: cada crida paga la lectura sencera (8–10 s; D1 i `PROBLEMES.md` 2).
- **RAM:** com a mínim 2,66 GB disponibles en totes les proves (models, tutor i matriu).
- **Placa contra portàtil:** 47/50 lletres iguals. El portàtil serveix per explorar; els números i els temps finals es mesuren a la placa.
- **Temps del tutor** (banc real): problema nou 9,7 s de mitjana (màxim 15,6 s); el Cangur amb una pista 10,7 s (màxim 12,6 s); els graons d'ajuda, instantanis. Problemes externs: `solve()` 7,2 s, referència del Cangur 8,1 s, pista 9,5 s (detall a `PROBLEMES.md`).
- **Temps de `predict.py`:** per defecte, mitjana 5,3 s i màxim 12,4 s (els problemes sense opcions són instantanis). Amb l'expressió, màxim 35 s. Amb `dev50` (tots amb opcions): sense RAG 10,5 / 18,2 s; RAG 1 (resposta) 18,0 / 29,4 s; RAG 1 (lletra) 23,0 / 34,1 s. Cap problema per sobre de 57 s.
- **Alimentació / USB:** el 2026-11-15 la connexió USB va caure a les 00:37 i la placa es va reiniciar sola ("crash", sense apagada neta) a les 00:57; hi ha dues arrencades "crash" més del dia 14. Les tasques llançades des d'`adb shell` (també dins de tmux) moren quan cau `adbd`: cal llançar-les amb `systemd-run --user` (`PROBLEMES.md` 15).
- **`tutor.db`** (des del 2026-11-15 03:01): la del banc de pistes de l'agent, 616 problemes de train (secció "Pont d'idioma i pistes"). Està a la placa i no es puja mai a Git.

## Resultats de `predict.py`
**Primera ronda** (placa, 50 problemes de la validació **antiga**, 22 d'ells sense opcions; interval de ±13 punts: cap diferència entre configuracions surt del soroll). **No es poden comparar amb els de la segona ronda.**

| Experiment | Encert | Amb opcions | Temps mitjà / pitjor |
| --- | --- | --- | --- |
| baseline dels organitzadors (repo base) | 22,5% (n = 40) | — | 8,7 s |
| `baseline-org` (el model també sense opcions) | 20% | 6/28 | 9,6 / 15,4 s |
| `baseline` (lletra de reserva sense opcions) | 30% | 6/28 | 5,3 / 12,4 s |
| `debias` (biaix del fitxer) | 32% | 7/28 | 5,3 / 12,4 s |
| `debias-batch` (biaix del lot) | 34% | 8/28 | 5,3 / 12,4 s |
| `expr-override` (expressió + Python) | 30% | 6/28 | 14,2 / 35,0 s |

Conclusions: no preguntar al model sense opcions; el `letter_bias.json` d'aquesta ronda era dolent (C = 0,005) i no es puja; l'expressió es descarta. Detall a `DECISIONS.md`.

**Dades noves:** la lletra de reserva és la global del train (D). "Sempre D" encerta 65/280 (23,2%) a la validació nova en anglès.

**Segona ronda** (placa, `data/dev50.jsonl`: 50 problemes de la validació nova, tots amb les 5 opcions, un idioma cada un — 25 eng i 25 cat — i 10 de cada lletra; codi `c34427e`; índex del RAG amb `--skip-suspect`; `letter_bias.json` de 60 problemes, fet a les 23:33). Amb lletres equilibrades, l'atzar i "sempre D" donen el 20%. Interval del 95% d'uns ±11–12 punts: **cap diferència surt del soroll** (McNemar exacte, p ≥ 0,21). **No es pot comparar amb la primera ronda.**

| Experiment | Encert | eng / cat | Lletres predites A/B/C/D/E | Temps mitjà / pitjor |
| --- | --- | --- | --- | --- |
| `dev-nodebias` (`--debias off`) | 22% (11/50) | 7/25 · 4/25 | 17/2/0/29/2 | 10,5 / 18,1 s |
| `dev-debias` (biaix del fitxer) | **24% (12/50)** | 7/25 · 5/25 | 18/11/5/2/14 | 10,5 / 18,2 s |
| `dev-debias-rag1` (RAG 1 veí, resposta) | 20% (10/50) | 4/25 · 6/25 | 2/34/10/2/2 | 18,0 / 29,4 s |
| `dev-debias-rag1-letter` (RAG 1 veí, lletra) | 12% (6/50) | 3/25 · 3/25 | 7/10/12/13/8 | 23,0 / 34,1 s |

Lectura: el biaix del fitxer reparteix millor les lletres (treu el pic de D), però no guanya encerts de manera fiable (+1). El RAG dobla el temps i no millora: amb la resposta del veí, el model s'enganxa a la B (34/50); amb la lletra, cau al 12%. `dev-debias-rag1` es va tallar al problema 32 per la caiguda USB i es va repetir sencer: les 32 primeres lletres van sortir idèntiques (és determinista). Els CSV per problema no es pugen; `ablations.csv` té les xifres agregades. Les files `nou-nodebias` (28%) i `nou-debias` (24%) d'`ablations.csv` són d'una tanda anterior interrompuda, amb `data/val.jsonl` (amb opcions, lletres no equilibrades) i l'índex sense `--skip-suspect`: no es comparen amb aquesta taula.

## Experiments al portàtil (sense placa ni model)
Fets per l'Elsa (amb Claude) i repetits per la Berta (amb Claude) sobre `main` (`1d1fc0b`), amb les dades de la segona volta d'OCR. Només xifres agregades; els casos i els temes de referència no es pugen.

| Experiment | Resultat |
| --- | --- |
| C1 · Filtre de fuites (`copilot/leak.py`, 100 fuites i 100 pistes netes, totes en català) | Amb el codi de `main`: 63/100 fuites detectades i 98/100 netes acceptades. Amb les correccions de `berta/experiments-portatil`: **67/100 i 99/100**. Per tipus: lletra 25/25, posició 15/15, valor 27/30, indirecta 0/30 (no les pot veure per disseny). Les 3 de valor que passen: dues perquè el número ja surt a l'enunciat (el filtre ho permet a propòsit) i una per una opció mal llegida per l'OCR. El fals positiu que queda: un número en lletres a l'enunciat ("els quatre jugadors"). Les xifres després de les correccions estan mesurades amb els mateixos casos que les han motivat: són optimistes |
| C2 · Temes (`copilot/topics.py` contra 100 temes de referència de l'agent) | 100/100 referències vàlides; `topics.py` coincideix amb el tema principal o l'alternatiu en **65/100** |
| C3 · Simulació de l'Elo (`sim/students.py`, 200 alumnes simulats per punt de partida, banc inventat) | Error després de 20 respostes, començant a 300 punts: K fix = 32, **147** (140–172); K decreixent, **65** (58–84). El README i `elo.py` deien "about 160/170" per a K = 32: corregit a ~150. La bretxa d'idioma del README (163 i 185; 121–261) es reprodueix |
| C4 · Problemes sense opcions (`prep/options_coverage.py`, validació) | **205/280 problemes (73,2%)** tenen les 5 opcions, igual en eng i cat. Els 75 restants no arriben al model i reben la D, que n'encerta 20 (26,7%). Pitjor al nivell 2 (51,7% amb opcions) |

Revisió humana de mostra (Berta, 20 línies de cada, triades a l'atzar amb llavor 42): **20/20 etiquetes de fuites i 20/20 temes correctes**. La de Codex havia donat 19/20 i 19/20.

## Bloquejos i riscos
- **Lliuraments sense començar**, i són el que veurà el jurat.
- **Una sola placa:** experiments de `predict.py`, la mesura final amb el test i les proves del tutor l'han de compartir. Desplegaments que es trepitgen: `PROBLEMES.md` 14.
- **Abast:** `PLA.md` té moltes tasques obertes. Cal decidir què es fa per diumenge i què s'explica com a "no fet".
- **Les opcions del test final passen per l'OCR:** els problemes amb figura o mal llegits es queden sense opcions i reben la lletra de reserva. Cal mesurar-ho amb el conjunt de pràctica.
- **Amb 20 problemes, la correcció per lot no s'aplica:** el que compta és `letter_bias.json` a la placa.
- **`letter_bias.json` actual de la placa** (60 problemes, 23:33): C = 0,004 i D = 0,56, el mateix patró que el de la primera ronda que es va considerar dolent (C = 0,005). Amb `dev50` encara prediu poc la C (5/50). Cal decidir si és prou bo per al *last call*.
- **Placa inestable per USB/alimentació** (`PROBLEMES.md` 15): un tall durant el *last call* o la demo és un risc. Un altre reinici sol el 2026-11-15 a les 02:33 (hora de la placa), amb el model treballant (D2).

## Per decidir com a equip
- Què entra per diumenge i què s'aparca (pistes generades pel model, ajust fi, imatge…).
- **La barra del Cangur:** D2 diu que les pistes bones no el mouen més que les absurdes (13 a 11, p = 0,84). Treure-la, o deixar-la i explicar-ho com a limitació.
- Quan es fa el dashboard Tukey.
- L'ordre d'ús de la placa fins a la presentació.
- Si es reconstrueix `tutor.db` amb les dades de la segona volta d'OCR.
- Si es manté la taula per temes del dashboard: `topics.py` només coincideix amb la referència en 65/100 (C2).
- Les tres propostes de Claude a `DECISIONS.md` (port 8090, temes per paraules clau, K de l'Elo), el llindar de D4, l'idioma del README.

## Resolt
- Repo base importat a `projecte/` (commit `d6e3f1b` dels organitzadors). Idea final: "Ensenya el Cangur" amb `predict.py` millorat.
- Dades: `eng` i `cat`, segona volta d'OCR (75% de files amb les 5 opcions; sempre 5 o cap) i la partició de `prepare_m3kang.py`: train 1.461 i validació 280 problemes. Test: el conjunt de pràctica dels organitzadors (50 problemes nous).
- Placa: passos 0–8, D1, placa contra portàtil, matriu LED, servei del tutor i reinici.
- Es poden preparar pistes i altres lots amb un model gran fora de la placa (Marc).
- `predict.py`: etapa 1 i expressió descartades; reserva global (D).
- Tutor: Elo dels problemes fix; problemes externs pel mateix recorregut, amb l'avís i els intents marcats a part.

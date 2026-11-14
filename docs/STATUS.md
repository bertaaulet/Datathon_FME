# Estat actual

_Última actualització: 2026-11-14 21:05 — Berta (amb Claude)_

## Fase
Codi de la v1, harness de `predict.py` i arreglos del tutor a `main` (76 proves OK). La placa està a punt i el harness s'hi ha provat (temps i gramàtica). **Encara no hi ha cap encert mesurat amb M3Kang**: s'està mesurant ara. La presentació és **diumenge**. El pla és a [`PLA.md`](PLA.md), i els problemes trobats a la placa a [`PROBLEMES.md`](PROBLEMES.md).

## Ara mateix
| Què | On | Estat |
| --- | --- | --- |
| Experiments de `predict.py` amb la validació real (`baseline-org`, `baseline`, `letter_bias`, `debias`, `debias-batch`, `expr-override`, `--limit 50`) | Placa | ⏳ ~70 min |
| Segona volta d'OCR de les opcions | Portàtil | ⏳ |

**Aparcat fins que acabin:** tot el que depèn dels resultats o de les dades noves (anàlisi d'errors, configuració final de `predict.py`, `index.db`, `tutor.db`). Si l'OCR canvia `val.jsonl`, els resultats d'abans i de després **no es poden comparar**: cal fixar quina validació és la definitiva.

## Línies de feina
Les tasques s'assignen en veu alta a l'equip; aquí només hi ha què queda i de què depèn. La llista completa és a `PLA.md`.

| Línia | Fet | Pendent | Depèn de |
| --- | --- | --- | --- |

| A · Millorar `predict.py` (harness) | Berta | Fitxers de calibració al repo, nivell tret de l'`id`, llama.cpp al portàtil | 🟡 A `main` (PR #1 i #3): calibració al repo, nivell de l'`id`, `eval.py` amb `machine`, guardrails, `PREDICT_DEBIAS=batch` i l'etapa de l'expressió (`PREDICT_EXPRESSION`, desactivada fins mesurar-la). 71 proves OK. **Esperant:** la Irene comprova a la placa la gramàtica de l'expressió i els temps; amb les dades, `priors`, `baseline-org`, `baseline`, `letter_bias` a la placa i les comparacions de biaix i expressió |
| B · Dades, agent i pistes | | `prepare_m3kang.py --languages eng,cat` i passar `data/` a la resta (fora de Git) | ⬜ |
| C · Placa Arduino | Irene | Passos 0–8 de `projecte/docs/SETUP.md` i `prep/check_model.py` | ✅ passos 0–8, D1, comparació placa-portàtil, matriu LED, `tutor.db` real, servei del tutor, reinici de prova, mesures definitives i experiments d'A a la placa |
| Sense assignar | | Tutor (problemes externs, integrar pistes generades), dashboard, README, Project Hub, pitch | ⬜ |

## Placa
- Passos 0–8 de `projecte/docs/SETUP.md`: ✅ llama.cpp `2cbe0ec` compilat, serveis `math-llm` (8081) i `math-embed` (8082) actius i arrencant amb la placa. Lectura 10,8 tok/s, escriptura 5,8 tok/s. `predict.py` amb `sample_problems.jsonl`: 5/5 `ok`, com a màxim 6,8 s, però **respon A a tots cinc** (0/5 encerts): falta `letter_bias.json` (`PROBLEMES.md` 1).
- RAM amb els dos serveis en marxa: 874 MB usats, 2.795 MB disponibles.
- **Placa contra portàtil, 50 problemes** (`compare50.jsonl`: 50 problemes en anglès, 39 amb opcions, la majoria del train. Només serveix per comparar, no per mesurar l'encert): **47/50 lletres iguals** (36/39 de les que fan servir el model). Difereixen en `lvl-0_2016_9`, `lvl-0_2019_1` i `lvl-0_2019_10`. Conclusió: el portàtil (x86, GCC 13) va bé per explorar, però **els números finals s'han de mesurar a la placa**, i el text de les pistes generades al portàtil s'ha de comprovar a la placa. La placa només ha respost D (41) i A (9), un biaix fort. Temps a la placa amb opcions: mitjana 8,1 s, màxim 11,8 s.
- **Proves del harness de la Berta a la placa** (2026-11-14, `main` `f5bbc51`, que ja inclou `berta/harness`, més `irene/tutor-fixes`; mateixos `compare50.jsonl`; **sense encerts**, perquè són problemes inventats o del train):
  1. **Proves automàtiques:** 75/75 OK. N'hi ha 75 i no 49 perquè la placa té tot `main` (A, Marc) més `irene/tutor-fixes`.
  2. **Gramàtica de l'expressió:** el llama.cpp `2cbe0ec` l'accepta, sense cap error. Amb els 5 problemes de `sample_problems.jsonl`, de 6,3 a 13,6 s per crida (`prompt_n` de 58 a 114). En 2 de 5 el valor no coincideix amb cap opció (`None`), i una expressió surt estranya (`15 - 6 + 6 + 6 …`).
  3. **Temps amb `PREDICT_EXPRESSION=on`:** 50/50 `ok`, **cap per sobre de 57 s**. Amb opcions (39): mitjana 25,1 s, mediana 27,0 s, màxim 34,6 s. Els 11 sense opcions surten a l'instant (prior). És unes 3 vegades el temps sense l'expressió.
  - **`main` per defecte:** les mateixes 50 lletres que el `predict.py` del matí (A 9 · D 30 de les 39 amb opcions). Mitjana 8,4 s, màxim 12,0 s: els guardrails no canvien res i costen ~0,3 s.
  - **`PREDICT_DEBIAS=batch`:** canvia 22 de 50 respostes. Amb opcions, A 6 · B 6 · C 5 · D 12 · E 10: corregeix el biaix D/A sense cost de temps (mitjana 8,4 s, màxim 12,4 s). L'encert es mesurarà amb la validació real.
  - **RAM** durant la prova amb l'expressió: com a mínim 2.664 MB disponibles.
- Repo a la placa: còpia dels fitxers (sense token) a `~/Datathon_FME/projecte`, commit `0751155`.
- Serveis nous: `board/06_install_tutor_service.sh` i `board/systemd/math-tutor.service` (tutor al port 8090). Escrits, encara no instal·lats (cal `sudo`).
- **Matriu LED:** l'app `applab/math-matrix` s'instal·la i s'engega des de la terminal (`arduino-app-cli app start user:math-matrix`, sense App Lab). La primera vegada descarrega la imatge `python-apps-base`. App Lab executa l'app en un **contenidor Docker amb xarxa pròpia** (`172.18.0.0/16`). Des d'allà, `127.0.0.1` i `host.docker.internal` **no** arriben al tutor; `172.17.0.1:8090` sí, però **només si el tutor escolta a `0.0.0.0`**. Per tant, el servei s'ha d'instal·lar amb `TUTOR_HOST=0.0.0.0 ./board/06_install_tutor_service.sh`. Provat amb un `tutor-test.db` de 60 problemes, que no és per mesurar res: l'app troba el tutor. Comprovat a ull: l'interrogant, la creu, el tic i la barra es veuen bé. L'app ja és l'**app per defecte**, i arrenca amb la placa. **Provat amb un reinici:** vegeu més avall.
- **Arreglos del tutor** (problemes 3, 8, 9 i 10 de [`PROBLEMES.md`](PROBLEMES.md)) a la branca `irene/tutor-fixes`, provats a la placa i pendents de PR: comptador de caràcters de la pista, botó "Prou, següent problema" a la fase d'ensenyar el Cangur (desa els abandonaments a `teach_exits`), cap canvi a l'anglès sense avisar i el script 06 comprova `tutor.db`.
- **Mesures provisionals** (amb `tutor-test.db`; s'han de repetir amb el banc real; vegeu `PROBLEMES.md` §7): cada crida al Cangur triga ~10 s (màxim 16,7 s). Els graons d'ajuda són instantanis, perquè no fan servir el model. Queden 2,7 GB de RAM lliures amb tot en marxa. **La generació de pistes amb el model encara no existeix al codi.**
- **`tutor.db` real** (2026-11-14): construït al portàtil amb les dades de B (`build_tutor_db.py` amb el servidor d'embeddings a WSL; mateix llama.cpp `2cbe0ec` i mateix GGUF que la placa). Té 1.747 problemes en català i anglès, i el tutor en pot fer servir 601. Les respostes del Cangur ja estan calculades per endavant (`kangaroo_baseline.py`, **al portàtil**, a 0,5 s per problema): en 467 dels 601 (78 %) prefereix una opció equivocada. Com que la placa i el portàtil difereixen en unes 3 lletres de cada 50, alguna resposta del Cangur pot no coincidir amb la de la placa. Copiat a la placa; no es puja mai a Git.
- **Servei del tutor instal·lat** (`TUTOR_HOST=0.0.0.0 ./board/06_install_tutor_service.sh`): `math-tutor`, `math-llm` i `math-embed` actius i habilitats. La matriu troba el tutor real a `172.17.0.1:8090`.
- **Reinici de prova (`sudo reboot`): ✅** La placa torna en 12 s, i en menys d'un minut ho té tot a punt sense tocar res: els tres serveis, els dos models responent, el tutor amb el banc real i la matriu connectada. **Per a la demo n'hi ha prou d'endollar la placa i esperar un minut.**
- **Mesures definitives del tutor**, amb el banc real (vegeu `PROBLEMES.md` §7): problema nou 9,7 s de mitjana (màxim 15,6 s); el Cangur amb una pista 10,7 s (màxim 12,6 s); els graons d'ajuda i respondre, instantanis; RAM, com a mínim 2.785 MB lliures. **Problema nou (11):** el tutor torna a preguntar al model en cada problema encara que el Cangur estigui precalculat.
- **Experiments d'A amb la validació real** (`baseline-org`, `baseline`, `letter_bias`, `debias`, `debias-batch`, `expr-override`): fets a la placa en 42 min, sense errors, cap problema per sobre de 57 s (el pitjor, 35,0 s, amb l'expressió). Els resultats s'han lliurat a A per un canal privat; les xifres les reporta A.
- `check_model.py` (decisió D1): ✅ fet al portàtil i **confirmat a la placa**. Els resultats són els mateixos. A la placa, la primera crida triga 10,3 s i la crida amb pista 8,2 s.
  1. **Probabilitats: OK.** Les 5 lletres surten dins del top 64.
  2. **Caché: NO funciona per a les pistes.** Si el prompt canvia en qualsevol punt, encara que sigui després del problema, només es reaprofiten els primers 33 tokens i es torna a llegir tot el problema. Només es reaprofita tot quan el prompt és idèntic. Prova: sense pista 70 tokens llegits; la mateixa sense pista 4; pista 1 83; pista 1 un altre cop 4; pista 2 83. Probablement és perquè Qwen3.5 és un model híbrid, que no pot tallar la caché en qualsevol punt. **Conseqüència per a A i B:** cada crida amb pista paga la lectura sencera del problema.
  3. Temps: els del portàtil no compten. Els de la placa són els de dalt.
- IP / accés: `adb shell` per USB.

| `predict.py` | Calibració, guardrails, biaix per lot, expressió (desactivada fins mesurar). Etapa 1 descartada | Decidir el biaix i l'expressió; anàlisi d'errors; RAG des de `config.env`; problemes sense opcions; configuració final i `--limit 0` | Experiments i segona volta d'OCR |
| Pistes | Infraestructura (lots, validació, importació, rànquing, similitud, pistes de mètode en 6 llengües) | Banc de pistes de l'agent; solucions breus i tipus de problema; τ (D2); revisar la similitud i l'escala d'ajuda; decidir les pistes generades pel model | `tutor.db` i la placa per a D2 |
| Tutor (Teach) | Escala d'ajuda, Cangur, pont d'idioma, Elo, arreglos de la placa | Visualització i experiència; revisar l'Elo i el pont d'idioma; problemes externs; `tutor.db`; servei i recorregut a la placa | Dades definitives i la placa |
| Lliuraments | — | README, `LICENSE`, xifres de PISA, pitch, vídeo de reserva, Project Hub, dashboard Tukey (més endavant) | Resultats per als números |

## Placa
- **Muntatge:** passos 0–8 fets. llama.cpp `2cbe0ec`, serveis `math-llm` (8081) i `math-embed` (8082) que arrenquen amb la placa. Accés per `adb shell` (USB). Repo a la placa: còpia dels fitxers a `~/Datathon_FME/projecte`, sense token.
- **Velocitat:** lectura 10,8 tok/s, escriptura 5,8 tok/s. **La caché no es reaprofita** si el prompt canvia: cada crida paga la lectura sencera (8–10 s; D1 i `PROBLEMES.md` 2).
- **RAM:** 2,7–2,8 GB disponibles amb els dos models, i ≥ 2,66 GB amb l'expressió activada.
- **Placa contra portàtil:** 47/50 lletres iguals. El portàtil serveix per explorar; els números i els temps finals es mesuren a la placa.
- **`predict.py` a la placa** (`compare50.jsonl`, problemes del train o inventats, **sense encerts**): sense biaix corregit respon gairebé sempre D o A. Per defecte, mitjana 8,4 s i màxim 12,0 s. `PREDICT_DEBIAS=batch` reparteix les lletres (A 6 · B 6 · C 5 · D 12 · E 10) sense cost. `PREDICT_EXPRESSION=on`: la gramàtica funciona, mitjana 25 s i màxim 34,6 s amb opcions, cap per sobre de 57 s.
- **Tutor i matriu LED:** la matriu arriba al tutor si escolta a `0.0.0.0` (`172.17.0.1:8090`). L'app és l'app per defecte i arrenca amb la placa. Servei del tutor escrit (`board/06_install_tutor_service.sh`, cal `TUTOR_HOST=0.0.0.0` i `sudo`) però no instal·lat: espera `tutor.db`.
- **Mesures provisionals del tutor** (amb `tutor-test.db`, s'han de repetir): ~10 s per crida del Cangur (màxim 16,7 s); els graons d'ajuda són instantanis.


## Millor resultat fins ara
| Experiment | Encert | n | Latència mitjana |
| --- | --- | --- | --- |
| baseline (organitzadors) | 22,5% | 40 | 8,7 s |
| Lletra més freqüent per nivell (`priors.json`, sense model) | 24,6% | 281 | 0 s |

## Bloquejos i riscos
- **Lliuraments sense començar:** README (7 `TODO`, i diu que no s'ha executat res), `LICENSE` sense noms, Project Hub, pitch i vídeo de reserva.
- **Una sola placa:** experiments de `predict.py`, `build_index.py`, `tutor.db`, la línia base del Cangur i la mesura final amb `--limit 0` (hores, si porta l'expressió) l'han de compartir. Cal acordar-ne l'ordre.
- **`tutor.db` no existeix:** sense ell no hi ha demo amb el banc real. Depèn de les dades i dels embeddings de la placa.
- **Abast:** `PLA.md` té ~55 tasques obertes. Cal decidir què es fa per diumenge i què s'explica com a "no fet".
- **No podem preguntar als organitzadors:** supòsits a `PLA.md` (el jurat carrega el nostre repo; `eng` i `cat`; format de `prepare_m3kang.py`).

## Per decidir com a equip
- Què entra per diumenge i què s'aparca (pistes generades pel model, ajust fi, imatge, problemes externs complets…).
- Quan es fa el dashboard Tukey.
- L'ordre d'ús de la placa fins a la presentació.
- Quina validació és la definitiva si la segona volta d'OCR canvia `val.jsonl`.
- Les tres propostes de Claude a `DECISIONS.md` (port 8090, temes per paraules clau, K de l'Elo), el llindar de D4, l'idioma del README.

## Resolt
- Repo base importat a `projecte/` (commit `d6e3f1b` dels organitzadors). Idea final: "Ensenya el Cangur" amb `predict.py` millorat.
- Dades: `eng` i `cat`, validació del 15% a l'atzar per id (1.466 de train i 281 de validació per idioma).
- Placa: passos 0–8, D1 (probabilitats OK), placa contra portàtil, matriu LED.
- Es poden preparar pistes i altres lots amb un model gran fora de la placa (Marc).
- Etapa 1 de `predict.py` descartada; `priors.json` al repo.

# Estat actual

_Última actualització: 2026-11-15 00:05 — Berta (amb Claude)_

## Fase
- **Tutor:** funciona a la placa amb el banc real (`tutor.db`, 601 problemes utilitzables, el Cangur precalculat), arrenca sol amb la placa i amb la matriu LED, i els problemes externs segueixen el mateix recorregut que els del banc (provat amb problemes inventats).
- **`predict.py`:** primera ronda d'experiments feta (taula de sota). Ara hi ha **dades noves** (segona volta d'OCR; train 85% i validació 15%), el **conjunt de pràctica dels organitzadors com a test**, i el codi del RAG i del biaix robust a la PR de `berta/rag-split`. **Cal repetir els experiments a la placa.**
- **Test final:** 20 problemes nous, executats amb el nostre `predict.py` **a la nostra placa** després del *last call* de les 12:00 (detall a `PLA.md`).
- **Lliuraments** (README, `LICENSE`, pitch, vídeo, Project Hub, dashboard): sense començar.
- La presentació és **diumenge**. El pla és a [`PLA.md`](PLA.md), i els problemes trobats a la placa a [`PROBLEMES.md`](PROBLEMES.md).

## Ara mateix
| Què | Estat |
| --- | --- |
| Fusionar la PR de `berta/rag-split` (RAG des de `config.env`, biaix robust, `priors.json` nou, `--only-with-options`, documents) | ⏳ |
| Preparar el conjunt de pràctica amb la comanda dels organitzadors (`prepare_m3kang.py --parquet … --val-fraction 0 --out data/demo --save-images`) | ⏳ |
| Segona ronda d'experiments a la placa: `build_index.py`, `letter_bias.py`, i `nou-nodebias`, `nou-debias`, `nou-debias-rag1`, `nou-debias-rag1-letter` (50 problemes de validació amb opcions); després, la configuració triada amb el conjunt de pràctica | ⏳ ~2 h, quan la PR sigui a `main` |

## Línies de feina
Les tasques s'assignen en veu alta a l'equip; aquí només hi ha què queda i de què depèn. La llista completa és a `PLA.md`.

| Línia | Fet | Pendent | Depèn de |
| --- | --- | --- | --- |
| `predict.py` | Calibració, guardrails, biaix per lot, expressió (descartada), RAG amb pregunta + valor correcte, biaix robust | Segona ronda d'experiments; triar la configuració de `config.env`; `letter_bias.json` bo a la placa; confirmar amb el conjunt de pràctica; anàlisi d'errors; placa a punt per al *last call* | La placa |
| Pistes (Berta) | Infraestructura (lots, validació, importació, rànquing, similitud, pistes de mètode en 6 llengües). **Flux nou decidit** ([`PISTES.md`](PISTES.md)): sense companys, escala nova, Cangur en català, es guarden només les pistes que convencen | Implementar-ho al codi; banc de pistes de l'agent; τ (D2); pistes generades pel model | `tutor.db` i la placa per a D2 |
| Tutor (Teach) | Escala d'ajuda, Cangur, pont d'idioma, Elo de l'alumne (el dels problemes és fix), problemes externs, interfície nova, servei i reinici | Problemes 11–14 de `PROBLEMES.md`; revisar l'Elo i el pont d'idioma; reconstruir `tutor.db` amb les dades noves de l'OCR (si es vol) | — |
| Lliuraments | — | README, `LICENSE`, xifres de PISA, pitch, vídeo de reserva, Project Hub, dashboard Tukey | Resultats per als números |

## Placa
- **Muntatge:** passos 0–8 fets. llama.cpp `2cbe0ec`, serveis `math-llm` (8081), `math-embed` (8082) i `math-tutor` (8090, a `0.0.0.0`), tots habilitats. Accés per `adb shell` (USB). Repo a la placa: còpia dels fitxers a `~/Datathon_FME/projecte`, sense token.
- **Reinici:** la placa torna en 12 s i en menys d'un minut ho té tot a punt (serveis, models, tutor amb el banc real i matriu). Per a la demo n'hi ha prou d'endollar-la i esperar un minut.
- **Velocitat:** lectura 10,8 tok/s, escriptura 5,8 tok/s. **La caché no es reaprofita** si el prompt canvia: cada crida paga la lectura sencera (8–10 s; D1 i `PROBLEMES.md` 2).
- **RAM:** com a mínim 2,66 GB disponibles en totes les proves (models, tutor i matriu).
- **Placa contra portàtil:** 47/50 lletres iguals. El portàtil serveix per explorar; els números i els temps finals es mesuren a la placa.
- **Temps del tutor** (banc real): problema nou 9,7 s de mitjana (màxim 15,6 s); el Cangur amb una pista 10,7 s (màxim 12,6 s); els graons d'ajuda, instantanis. Problemes externs: `solve()` 7,2 s, referència del Cangur 8,1 s, pista 9,5 s (detall a `PROBLEMES.md`).
- **Temps de `predict.py`:** per defecte, mitjana 5,3 s i màxim 12,4 s (els problemes sense opcions són instantanis). Amb l'expressió, màxim 35 s. Amb el RAG, encara per mesurar.
- **`tutor.db`** es va construir amb les dades de la **primera** volta d'OCR. Està a la placa i no es puja mai a Git.

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

## Bloquejos i riscos
- **Lliuraments sense començar**, i són el que veurà el jurat.
- **Una sola placa:** experiments de `predict.py`, la mesura final amb el test i les proves del tutor l'han de compartir. Desplegaments que es trepitgen: `PROBLEMES.md` 14.
- **Abast:** `PLA.md` té moltes tasques obertes. Cal decidir què es fa per diumenge i què s'explica com a "no fet".
- **Les opcions del test final passen per l'OCR:** els problemes amb figura o mal llegits es queden sense opcions i reben la lletra de reserva. Cal mesurar-ho amb el conjunt de pràctica.
- **Amb 20 problemes, la correcció per lot no s'aplica:** el que compta és `letter_bias.json` a la placa.

## Per decidir com a equip
- Què entra per diumenge i què s'aparca (pistes generades pel model, ajust fi, imatge…).
- Quan es fa el dashboard Tukey.
- L'ordre d'ús de la placa fins a la presentació.
- Si es reconstrueix `tutor.db` amb les dades de la segona volta d'OCR.
- Les tres propostes de Claude a `DECISIONS.md` (port 8090, temes per paraules clau, K de l'Elo), el llindar de D4, l'idioma del README.

## Resolt
- Repo base importat a `projecte/` (commit `d6e3f1b` dels organitzadors). Idea final: "Ensenya el Cangur" amb `predict.py` millorat.
- Dades: `eng` i `cat`, segona volta d'OCR (75% de files amb les 5 opcions; sempre 5 o cap) i la partició de `prepare_m3kang.py`: train 1.461 i validació 280 problemes. Test: el conjunt de pràctica dels organitzadors (50 problemes nous).
- Placa: passos 0–8, D1, placa contra portàtil, matriu LED, servei del tutor i reinici.
- Es poden preparar pistes i altres lots amb un model gran fora de la placa (Marc).
- `predict.py`: etapa 1 i expressió descartades; reserva global (D).
- Tutor: Elo dels problemes fix; problemes externs pel mateix recorregut, amb l'avís i els intents marcats a part.

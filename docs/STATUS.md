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

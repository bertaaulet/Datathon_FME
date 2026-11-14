# Estat actual

_Última actualització: 2026-11-14 16:50 — Berta (amb Claude)_

## Fase
Tot el codi de la v1 és a `projecte/`, però **no hi ha cap resultat real**: només s'ha provat contra un model simulat. El pla d'execució és a [`docs/PLA.md`](PLA.md) (harness de `predict.py`, pistes amb agent i model, problemes externs amb el mateix recorregut, què va al portàtil i què a la placa). Comencem a treballar en paral·lel en tres línies.

| Part | Escrit | Provat amb el simulador | Provat a la placa |
| --- | --- | --- | --- |
| `predict.py` i `eval.py` | Sí | Sí | No |
| Tutor i web (port 8090) | Sí | Sí, també al navegador | No |
| Scripts de preparació (`prep/`) | Sí | Sí | No |
| Pont d'idioma i doble Elo | Sí | Sí | No |
| Alumnes simulats (`sim/`) | Sí | Sí (no cal el model) | — |
| Dashboard Tukey (`dashboard/`) | Sí | Sí, amb dades de prova | — |
| App de la matriu LED (`applab/`) | Sí | No | No |
| Harness de `predict.py` (etapes 1–4, 6–7) | No | — | — |
| Banc de l'agent i pistes generades pel model | No | — | — |

## Qui fa què
| Línia | Persona | Primera tasca | Estat |
| --- | --- | --- | --- |
| A · Millorar `predict.py` (harness) | Berta | Fitxers de calibració al repo, nivell tret de l'`id`, llama.cpp al portàtil | 🟡 Fusionat: calibració al repo, nivell de l'`id`, `machine` i `--debias batch` a `eval.py`. A `berta/harness`: guardrails (entrada trencada, índex absent, problemes massa llargs escurçats, temps planificat abans de cada crida) i `PREDICT_DEBIAS=batch` a `predict.py` (44 proves OK). Següent: etapa de l'expressió. Esperant `data/` de B i les respostes dels organitzadors (on s'executa el test, idiomes) |
| B · Dades, agent i pistes | | `prepare_m3kang.py --languages eng,cat` i passar `data/` a la resta (fora de Git) | ⬜ |
| C · Placa Arduino | Irene | Passos 0–8 de `projecte/docs/SETUP.md` i `prep/check_model.py` | ✅ passos 0–8, D1 i comparació placa-portàtil. Següent: tutor i matriu LED |
| Sense assignar | | Tutor (problemes externs, integrar pistes generades), dashboard, README, Project Hub, pitch | ⬜ |

## Placa
- Passos 0–8 de `projecte/docs/SETUP.md`: ✅ llama.cpp `2cbe0ec` compilat, serveis `math-llm` (8081) i `math-embed` (8082) actius i arrencant amb la placa. Lectura 10,8 tok/s, escriptura 5,8 tok/s. `predict.py` amb `sample_problems.jsonl`: 5/5 `ok`, com a màxim 6,8 s, però **respon A a tots cinc** (0/5 encerts). Ho ha de mirar A.
- RAM amb els dos serveis en marxa: 874 MB usats, 2.795 MB disponibles.
- **Placa contra portàtil, 50 problemes** (`compare50.jsonl`: 50 problemes en anglès, 39 amb opcions, la majoria del train. Només serveix per comparar, no per mesurar l'encert): **47/50 lletres iguals** (36/39 de les que fan servir el model). Difereixen en `lvl-0_2016_9`, `lvl-0_2019_1` i `lvl-0_2019_10`. Conclusió: el portàtil (x86, GCC 13) va bé per explorar, però **els números finals s'han de mesurar a la placa**, i el text de les pistes generades al portàtil s'ha de comprovar a la placa. La placa només ha respost D (41) i A (9), un biaix fort. Temps a la placa amb opcions: mitjana 8,1 s, màxim 11,8 s.
- Repo a la placa: còpia dels fitxers (sense token) a `~/Datathon_FME/projecte`, commit `0751155`.
- Serveis nous: `board/06_install_tutor_service.sh` i `board/systemd/math-tutor.service` (tutor al port 8090). Escrits, encara no instal·lats (cal `sudo`).
- **Matriu LED:** l'app `applab/math-matrix` s'instal·la i s'engega des de la terminal (`arduino-app-cli app start user:math-matrix`, sense App Lab). La primera vegada descarrega la imatge `python-apps-base`. App Lab executa l'app en un **contenidor Docker amb xarxa pròpia** (`172.18.0.0/16`). Des d'allà, `127.0.0.1` i `host.docker.internal` **no** arriben al tutor; `172.17.0.1:8090` sí, però **només si el tutor escolta a `0.0.0.0`**. Per tant, el servei s'ha d'instal·lar amb `TUTOR_HOST=0.0.0.0 ./board/06_install_tutor_service.sh`. Provat amb un `tutor-test.db` de 60 problemes, que no és per mesurar res: l'app troba el tutor. Comprovat a ull: l'interrogant de repòs, la creu i la barra del Cangur es veuen bé a la matriu. Falta veure el tic.
- **Error del tutor:** les pistes es tallen a 200 caràcters (`HINT_MAX_CHARS`) sense avisar l'alumne, i el Cangur rep una frase a mitges. Cal limitar la caixa de text a 200 caràcters i mostrar-ho, o pujar el límit.
- El tutor no arrenca sense `tutor.db` ("has no problems"). El de debò depèn de les dades de B.
- `check_model.py` (decisió D1): ✅ fet al portàtil i **confirmat a la placa**. Els resultats són els mateixos. A la placa, la primera crida triga 10,3 s i la crida amb pista 8,2 s.
  1. **Probabilitats: OK.** Les 5 lletres surten dins del top 64.
  2. **Caché: NO funciona per a les pistes.** Si el prompt canvia en qualsevol punt, encara que sigui després del problema, només es reaprofiten els primers 33 tokens i es torna a llegir tot el problema. Només es reaprofita tot quan el prompt és idèntic. Prova: sense pista 70 tokens llegits; la mateixa sense pista 4; pista 1 83; pista 1 un altre cop 4; pista 2 83. Probablement és perquè Qwen3.5 és un model híbrid, que no pot tallar la caché en qualsevol punt. **Conseqüència per a A i B:** cada crida amb pista paga la lectura sencera del problema.
  3. Temps: els del portàtil no compten. Els de la placa són els de dalt.
- IP / accés: `adb shell` per USB.

## Millor resultat fins ara
| Experiment | Encert | n | Latència mitjana |
| --- | --- | --- | --- |
| baseline (organitzadors) | 22,5% | 40 | 8,7 s |

## Bloquejos / dubtes oberts
- **Preguntes per als organitzadors** (llista a `docs/PLA.md`): on s'executa el test ocult, si porta opcions i `level`, si es poden publicar xifres agregades i un model ajustat amb M3Kang, i com i quan es lliura el dashboard.
- **Per decidir com a equip:** validació (15% a l'atzar o `--val-years 2023,2024`), llengües, les tres propostes de Claude a `DECISIONS.md`, el llindar de D4, l'idioma del README i el nom a la `LICENSE`.
- L'app de la matriu LED pot no arribar al tutor per `127.0.0.1` si App Lab l'executa en un contenidor.

## Resolt
- Importar el repo base: còpia sense historial a `projecte/` (commit `d6e3f1b` dels organitzadors).
- Idea final: Teach ("Ensenya el Cangur") amb `predict.py` millorat com a part del projecte.
- Pla d'execució escrit a `docs/PLA.md`.
- Es poden preparar pistes i els altres lots amb un model gran fora de la placa (confirmat per Marc, 14 nov).

# Nit final a la placa — informe (15/11/2026, 04:04–04:41 UTC)

Repo portàtil: `main` a `cd5112b`. La placa queda **engegada**, en l'estat final. Segueix [`NIT_FINAL.md`](NIT_FINAL.md).

Només xifres agregades. Els fitxers per problema (`tutor-smoke-*.csv`, `vision-nit.log`, `results/eval-*.csv`) són fora del repo (zip `resultats_nit_final_20261115.zip`), perquè porten ids o etiquetes de M3Kang.

## Bloc A — Pistes (`PROVES_FINALS_PISTES.md`)
**Què s'ha provat:** el tutor "Ensenya el Cangur" amb els paràmetres definitius: el Cangur es convenç amb qualsevol pista que passi el filtre de fuites (`KANGAROO_RULE=clean`), τ = 0,49 només per decidir quin text es guarda, i sense generar pistes amb el model (`HINTGEN=off`). En tres nivells: (1) les 139 proves unitàries sense model; (2) `tutor_smoke.py`, que amb els models reals i una còpia de `tutor.db` recorre 4 problemes fallats (els 5 graons d'ajuda), 6 problemes per ensenyar el Cangur (una pista amb la lletra que s'ha de rebutjar i una de bona que l'ha de convèncer) i 1 problema extern, i mesura temps i RAM; (3) un recorregut a mà a la interfície web, per veure el que l'script no veu.

- Pas 1: còpia a `backup-final/`, fitxers desplegats, `KANGAROO_RULE=clean`, `KANGAROO_LANG=cat`, `HINTGEN=off`. τ = `('0.4855',)` ✓
- Pas 2: [x] `OK` (139 proves)
- Pas 3: [x] Checks **67/67** · Mediana pista **11,5 s** · Pitjor **15,0 s** · RAM disponible mínima **2717 MB**
  - Capçalera: `KANGAROO_RULE=clean  tau=0.49  HINTGEN=off  KANGAROO_LANG=cat  Kangaroo measured in cat`
  - Pistes: 6 rebutjades (lletra), 6 convençut, 1 fingit, 0 no convençut. Extern: 23,0 s.
  - ⚠️ `math-tutor` **no** es va aturar durant el smoke (al principi `sudo` demanava contrasenya; estava en repòs).
- Pas 4 (fet per Claude al navegador intern):
  - [x] Ensenyar el Cangur: pista neta → "Aaah, ara ho veig!", la barra passa de la meitat a la pantalla i al **mirall** de la matriu en pantalla. La matriu LED física no la vaig poder veure.
  - [x] Pista "és la D" → missatge de fuita, no gasta intent.
  - [x] Fallar i ajuda: els 5 graons; al graó 4, problema semblant respost (correcte) → la solució.
  - [x] Vista del docent: "1 l'han convençut, 0 no, i 1 s'han rebutjat".
  - [~] Pont d'idioma: canviat a Castellano des del selector (no amb el formulari d'alumne nou): problema en les dues llengües i avís "Aquesta pista només està disponible en català" ✓.
  - [x] Problema extern (inventat): avís sempre visible; graons 2–3 = frases de mètode.
- Després: `math-tutor` reiniciat, `/api/state` → `{"phase": "ready", ...}`.
- Fitxer: `tutor-smoke-20261115-040640.csv`

## Bloc B — Visió (fet al matí, 08:07–08:17 UTC)
**Què s'ha provat:** si en problemes **sense opcions però amb figura** (els 10 primers en anglès de `val.jsonl` sense opcions) enviar la imatge del problema a un segon servidor del Qwen 3.5 0.8B amb projector de visió (`mmproj` f16, `--image-max-tokens 128`, port 8083, temporal) encerta més que la lletra de la prior que fa servir ara `predict.py`. Sense tocar la configuració final.

**Com:** a la nit es va saltar (no hi havia `data/images/` ni internet a la placa). Al matí: 15 imatges extretes al portàtil del parquet de M3Kang de la memòria cau de HuggingFace (mateix nom que `prepare_m3kang.py --save-images`) i el `mmproj` descarregat al portàtil (SHA256 OK, també a la placa), tot copiat amb `adb push`. `math-tutor` es va quedar engegat en repòs (RAM disponible 2318 MB amb el servidor de visió).

**Resultat:**
| | Encert | Temps per problema |
|---|---|---|
| Amb imatge (visió) | **4/10** | 31,6–40,3 s (mitjana 36,1 s), tots `ok` |
| Prior (sempre D) | **5/10** | instantani |

La imatge **no millora** la prior en aquests 10 (4 contra 5; amb 10 problemes és soroll) i costa ~36 s per problema. Conclusió proposada: la imatge no entra a `predict.py`.

**Desmuntat (B.4):** `vision-test` aturat (`/health` no respon), `vision_test.py` esborrat, `free -m` available 2729 MB, serveis actius, D.1 `0 auto` i D.2 amb les mateixes 5 lletres. A la placa queden `~/models/mmproj-…gguf` i `data/images/` (15 PNG): `predict.py` no els llegeix i no són al repo.

## Bloc C — Conjunt de pràctica (`data/demo.jsonl`, 100 problemes)
**Què s'ha provat:** el conjunt de pràctica dels organitzadors (100 problemes, 20 de cada lletra correcta) passat per `eval.py` a la placa amb el mateix pipeline de `predict.py`, en dues configuracions: **demo-debias** = la configuració final (una lletra pel model, correcció del biaix de lletra amb `data/letter_bias.json`, sense RAG, sense expressió/Python); **demo-nodebias** = la mateixa sense corregir el biaix (`--debias off`), per veure què aporta la correcció. Es mesura encert, temps mitjà i pitjor, i que cap problema passi de 57 s.

| Execució | Encert | Temps mitjà | Pitjor | > 57 s |
|---|---|---|---|---|
| **demo-debias** (oficial) | **25/100 = 25,0 %** | 7,6 s | 12,2 s | 0 |
| demo-nodebias | 22/100 = 22,0 % | 7,6 s | 11,9 s | 0 |

Lletres (predites/reals): debias A 21/20, B 24/20, C 20/20, D 18/20, E 17/20 · nodebias A 18, B 7, C 0, **D 73**, E 2.
Línies noves d'`ablations.csv`: `ablations_noves_linies.csv` (la columna commit queda buida: la placa no és un repo git).

## Bloc D — `predict.py` final + reinici
**Què s'ha provat:** que la placa queda en l'estat del *last call*: configuració per defecte (`PREDICT_RAG_K=0`, debias `auto`), `letter_bias.json` present, `predict.py` dona 5 lletres `ok` amb `sample_problems.jsonl`, i que després d'un reinici els tres serveis arrenquen sols i `predict.py` dona el mateix.

- D.1 (abans i després): `0 auto`; `data/letter_bias.json` hi és (162 B); `PREDICT_RAG_K=0` només a la línia 60 (cap línia afegida). No s'ha copiat res del RAG.
- D.2: `check-abans-reboot.csv` i `check-despres-reboot.csv`: 5/5 `ok`, mateixes lletres (A, A, A, E, B), 5,3–9,4 s.
- Reinici 04:38: `math-llm`, `math-embed`, `math-tutor` → `active (running)`.
- `last -x`: `shutdown system down … 04:38` i el boot anterior tancat `02:32 - 04:38` (net). La línia `lightdm … crash` és la sessió gràfica, no el sistema.
- `free -m` després: available 2888 MB.

## Incidents
- 04:05 — `sudo` a la placa demana contrasenya (no previst al document). Solució: script temporal `~/sudo_helper.sh` (contrasenya escrita per la Irene un sol cop) que només podia fer stop/start/restart de `math-tutor` i `reboot`. Esborrat després del reinici.
- Cap tall d'USB, cap reinici sol, cap OOM.

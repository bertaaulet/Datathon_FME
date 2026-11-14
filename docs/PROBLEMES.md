# Problemes detectats i pla per resoldre'ls

_Creat: 2026-11-14 — Irene (línia C, placa), amb Claude. Surt de les primeres proves a la placa (passos 0–8, D1, comparació placa-portàtil i matriu LED)._

Cada problema porta què passa, la causa (comprovada o no), l'arreglo, de qui és, de què depèn i com es comprova que està resolt. Quan se'n resolgui un, marqueu-lo aquí i a `docs/STATUS.md`.

**Recordatori:** les proves s'han fet amb `data/tutor-test.db` i `data/compare50.jsonl`: 60 problemes en anglès, la majoria del train. Serveixen per veure que les peces funcionen, **no per mesurar l'encert**. No es pot publicar cap número d'aquestes proves.

## Resum

| # | Problema | Gravetat | De qui | Depèn de | Estat |
|---|---|---|---|---|---|
| 1 | `predict.py` només respon D o A | Alta | A (+ C) | Dades de B | ⬜ |
| 2 | La caché no serveix per a les pistes | Alta | A i B | — | 🟡 A: decidit; B: pendent |
| 3 | Les pistes es tallen a 200 caràcters sense avisar | Mitjana | Tutor | — | 🟨 fet a `irene/tutor-fixes`, provat a la placa |
| 4 | El Cangur gairebé mai es convenç | Mitjana | B i tutor | Dades de B | ⬜ |
| 5 | La matriu LED necessita el tutor a `0.0.0.0` i no arrenca sola | Mitjana | C | `tutor.db` real | 🟨 app per defecte configurada; falta el servei del tutor i el reinici |
| 6 | `prepare_m3kang.py` falla a Windows i hi va lent | Baixa | B | — | 🟨 arreglo de Marc a `marc/agent-lots` |
| 7 | Falten les mesures de temps i de RAM | Mitjana | C | `tutor.db` real | 🟨 provisionals fetes; cal repetir-les amb el banc real |
| 8 | El servei del tutor fallaria en bucle sense `tutor.db` | Baixa | C | — | 🟨 fet a `irene/tutor-fixes`, provat a la placa |
| 9 | El tutor passa a l'anglès en silenci si falta el català | Mitjana | Tutor | — | 🟨 fet a `irene/tutor-fixes`, provat a la placa |
| 10 | No es pot sortir de la fase "ensenyar el Cangur" | Mitjana | Tutor | — | 🟨 fet a `irene/tutor-fixes`, provat a la placa |

## Ordre de treball

1. **Ara, sense esperar ningú:** avisar B del problema 6, i resoldre els problemes 3, 6, 8, 9 i 10. Són canvis petits.
2. **Quan arribin les dades de B:** el problema 1 (`letter_bias.py` a la placa), el `tutor.db` real, el problema 5 (servei del tutor i arrencada de la matriu) i el problema 7 (mesures).
3. **A decidir com a equip, amb les dades de la placa:** els problemes 2 i 4.

Els problemes 3, 9 i 10 toquen els mateixos fitxers (`app/index.html` i `copilot/tutor.py`). Millor fer-los junts, en una sola branca.

---

## 1. `predict.py` només respon D o A

- **Què passa:** a la placa, 41 D i 9 A en 50 problemes. A en els 5 problemes d'exemple (0/5 encerts).
- **Causa (comprovada):** no hi ha `data/letter_bias.json`. `PREDICT_DEBIAS=auto` està activat, però sense aquest fitxer no corregeix res (`copilot/calib.py`). Veiem el biaix pur del model.
- **Arreglo:** amb les dades de B, executar `python3 prep/letter_bias.py` **a la placa**. El portàtil no serveix, perquè les lletres canvien en 3 de cada 50 problemes (vegeu STATUS).
- **Com es comprova:** tornar a passar `compare50.jsonl` i veure que les lletres es reparteixen millor. Després, `eval.py --limit 0 --name debias` contra el baseline.

## 2. La caché no serveix per a les pistes

- **Què passa:** si el prompt canvia en qualsevol punt, encara que sigui després del problema, només es reaprofiten els primers 33 tokens. Una crida amb pista torna a llegir tot el problema: uns 8 s a la placa.
- **Causa (probable, no confirmada):** Qwen3.5 és un model híbrid, i llama.cpp no pot tallar la seva caché en qualsevol punt. No és un error del nostre codi.
- **A (`predict.py`), decidit:** cada crida es planifica com una lectura sencera, amb el `prompt_n` que retorna el servidor. Hi caben unes 5 crides per problema (lletra, expressió, rotacions).
- **Proposta:** acceptar-ho i dissenyar al voltant. Prompts curts i el mínim de crides per pista. Comprovar amb les mesures del problema 7 si la generació de pistes amb 1 i 2 veïns cap dins del temps.
- **Decisió:** A i B. Afecta el pressupost de temps del Cangur i de la generació de pistes.

## 3. Les pistes es tallen a 200 caràcters sense avisar

- **Què passa:** una pista bona va arribar al Cangur a mitja frase ("...que tingui un 5 a les").
- **Causa (comprovada):** el tutor retalla la pista a `HINT_MAX_CHARS=200`, però la caixa de text no té límit ni avís.
- **Arreglo:** a `app/index.html`, `maxlength` a la caixa de la pista, llegit de la configuració, i un comptador ("143/200").
- **Com es comprova:** no es poden escriure més de 200 caràcters, i la pista que es desa a `tutor.db` és sencera.

## 4. El Cangur gairebé mai es convenç

- **Què passa:** amb una pista correcta, el Cangur continua preferint la resposta equivocada.
- **Causes possibles (no comprovades):** el model és molt petit. El problema li arriba en anglès (`MODEL_LANG=eng`) i la pista en català. I en la prova, la pista arribava tallada (problema 3).
- **Com es comprova:** amb `prep/hint_experiment.py`, sobre els mateixos problemes, comparar pistes en anglès amb pistes en català, i provar diferents valors de `HINT_TAU`. Mesurar a la placa.
- **Decisió:** B i qui porti el tutor, després de mesurar.

## 5. La matriu LED necessita el tutor a `0.0.0.0` i no arrenca sola

- **Què passa:** App Lab executa l'app en un contenidor Docker amb xarxa pròpia. Des d'allà, `127.0.0.1:8090` no arriba al tutor; `172.17.0.1:8090` sí, però només si el tutor escolta a `0.0.0.0`.
- **Comprovat:** l'app troba el tutor. A la matriu es veuen bé l'interrogant, la creu, el tic i la barra.
- **Arrencada:** l'app ja és l'app per defecte (`arduino-app-cli properties set default user:math-matrix`): el servei `arduino-app-cli` l'engega en arrencar la placa. Si el tutor encara no hi és, el torna a buscar cada 5 s. Falta provar-ho amb un `sudo reboot` quan el servei del tutor estigui instal·lat.
- **Arreglo:** instal·lar el servei amb `TUTOR_HOST=0.0.0.0 ./board/06_install_tutor_service.sh` (cal `sudo`). Fer que l'app arrenqui amb la placa (mirar `arduino-app-cli` i les opcions d'App Lab). Durant la demo no hi ha Wi-Fi, així que obrir el port no és un risc.
- **Com es comprova:** després de `sudo reboot`, sense tocar res, la matriu mostra l'interrogant i reacciona a les respostes de la web.

## 6. `prepare_m3kang.py` falla a Windows i hi va lent

- **Què passa:** a Windows, l'script peta amb un `UnicodeEncodeError` (un caràcter xinès llegit per l'OCR), si no s'executa amb `PYTHONUTF8=1`. A més, l'OCR va a 0,2 imatges/s: unes 4 hores per a anglès i català.
- **Arreglo:** ja el proposa Marc a la branca `marc/agent-lots` (commit `28e0949`): fitxers en UTF-8, caché d'OCR escrita línia a línia i `--ocr-threads`. No el dupliquem a `irene/tutor-fixes`. Per a la velocitat, executar-lo a Linux, WSL o Mac, o provar `--ocr-threads 4`.
- **Com es comprova:** l'script acaba a Windows sense `PYTHONUTF8`.

## 7. Falten les mesures de temps i de RAM

- **Què falta:** el temps de cada graó d'ajuda (problema semblant, tema, pista, solució), de cada crida del Cangur (`prompt_n` inclòs), de la generació de pistes amb 1 i 2 veïns, i la RAM (`free -m`) amb tot en marxa: models, tutor i app de la matriu.
- **Ja mesurat:** lectura 10,8 tok/s i escriptura 5,8 tok/s; `predict.py` amb opcions, mitjana 8,1 s i màxim 11,8 s; RAM amb els dos models, 2.795 MB disponibles; Cangur amb pista, 8,2 s.
- **Mesures provisionals** (2026-11-14, a la placa, amb `tutor-test.db`: 23 problemes utilitzables, en anglès i català; s'han de repetir amb el `tutor.db` real):

  | Pas | n | Mitjana | Màxim |
  |---|---|---|---|
  | Problema nou: resposta de referència del Cangur (en segon pla, mentre l'alumne llegeix) | 10 | 10,1 s | 16,7 s |
  | Respondre A–E | 10 | 0,00 s | 0,00 s |
  | Graons d'ajuda 1–4 (semblant, tema, pista, solució) | 4 de cada | 0,00 s | 0,00 s |
  | El Cangur llegeix una pista de l'alumne | 4 | 10,8 s | 11,4 s |

  - Totes les crides al model: 14 en total, mitjana 10,3 s, màxim 16,7 s; tokens llegits (`prompt_n`) 110 de mitjana, 139 de màxim. Com que la caché no serveix (problema 2), cada crida llegeix el problema sencer.
  - Els graons d'ajuda no fan servir el model: el graó 3 treu la pista del banc o una plantilla de mètode. La **generació de pistes amb el model encara no existeix**, i per això no s'ha pogut mesurar.
  - **RAM** amb els dos models, el tutor i l'app de la matriu: 2.687 MB disponibles en repòs, i com a mínim 2.674 MB durant les crides al model. Per procés: `llama-server` del model 1.060 MB, el d'embeddings 72 MB, el tutor 26 MB, el contenidor de la matriu 54 MB. Hi ha molt de marge.
- **Depèn de:** el `tutor.db` real, per repetir-ho.

## 8. El servei del tutor fallaria en bucle sense `tutor.db`

- **Què passa:** sense problemes a `tutor.db`, `app/server.py` s'atura ("has no problems"), i `Restart=on-failure` el tornaria a engegar cada 5 s.
- **Arreglo:** que `board/06_install_tutor_service.sh` comprovi que `tutor.db` existeix i té problemes abans d'instal·lar el servei, i que expliqui com construir-lo.
- **Com es comprova:** sense `tutor.db`, l'script s'atura amb un missatge clar.

## 9. El tutor passa a l'anglès en silenci si falta el català

- **Què passa:** amb el català com a llengua de classe, els problemes van sortir en anglès.
- **Causa (comprovada):** el `tutor-test.db` només tenia textos en anglès, i `copilot/tutor.py:181` fa servir el text del model quan no troba el català. Amb les dades de B no passarà, però en la demo podria passar amb qualsevol problema sense traducció.
- **Arreglo:** que el tutor només triï problemes amb text a la llengua de classe. Si no en queda cap, que ho digui ("No hi ha problemes en català") en lloc de canviar de llengua.
- **Com es comprova:** amb una base només en anglès, el tutor avisa en lloc de mostrar anglès.

## 10. No es pot sortir de la fase "ensenyar el Cangur"

- **Què passa:** quan l'alumne encerta, ha d'ensenyar el Cangur, i el botó de problema següent no surt fins que el Cangur es convenç o s'acaben els 3 intents. Com que el Cangur és fluix, sovint obliga a gastar els 3 intents, uns 25 s a la placa. Frustra l'alumne i és un risc en una demo de 3 minuts.
- **Decisió:** **no** es deixa saltar mai mentre es resol o es demana ajuda. Allà la sortida és veure la solució, i queda registrat. **Sí** es pot sortir mentre s'ensenya el Cangur, perquè el problema ja està resolt.
- **Arreglo:** a la fase `teach`, un botó "Prou, següent problema" visible des del principi. Desar a `tutor.db` quantes pistes ha escrit l'alumne abans de sortir, per poder respondre al dashboard: "quants alumnes deixen el Cangur, i després de quants intents?".
- **Com es comprova:** a la fase `teach` es pot passar al problema següent sense escriure cap pista, i l'abandonament queda desat.

# Pla del projecte — "Ensenya el Cangur"

> Datathon FME 2026 · Repte Qualcomm "Math on the Edge" · Side Challenge Tukey
> Versió del 14 de novembre de 2026, contrastada amb el repo base (commit `d6e3f1b`), els dos vídeos d'en Marc Pous i l'enunciat del Side Challenge.
> **Res d'aquest pla s'ha provat encara a la placa.** Les xifres són les dels organitzadors o estimacions, i estan marcades quan cal verificar-les.

## Estat de la implementació (14 nov 2026)

Tot el pla està escrit a `projecte/` (vegeu `projecte/README.md` per als passos). Les proves automàtiques passen, però només contra un servidor de model simulat i problemes inventats.

| Part | Escrit | Provat amb el simulador | Provat a la placa |
| --- | --- | --- | --- |
| `predict.py` i `eval.py` | Sí | Sí | No |
| Tutor i web (port 8090) | Sí | Sí, també al navegador | No |
| Scripts de preparació (`prep/`) | Sí | Sí | No |
| Pont d'idioma i doble Elo | Sí | Sí | No |
| Alumnes simulats | Sí | Sí (no cal el model) | — |
| Dashboard Tukey | Sí | Sí, amb dades de prova | — |
| App de la matriu LED | Sí | No | No |

Diferències respecte al que diu aquest pla més avall:

- La web del tutor és un servidor estàndard de Python al port **8090**, no el brick `web_ui` del 7000. L'app d'App Lab només dibuixa la matriu LED.
- Els temes surten de **paraules clau** (`copilot/topics.py`), no de k-means.
- El llindar `τ` és el percentil 90 de les pistes absurdes; la regressió logística no està feta.
- `K` de l'Elo i el mínim de respostes per a la bretxa d'idioma han canviat després de simular-ho (seccions 6.5 i 7.2).

Pendent: tot el que cal mesurar a la placa (secció 13), els resultats reals al README i al dashboard, i el projecte a Arduino Project Hub.

## 1. Resum

Un copilot de matemàtiques que funciona offline a l'Arduino UNO Q i té tres parts:

1. **`predict.py`** — respon problemes tipus Cangur amb una lletra A–E. Es puntua al test ocult.
2. **El tutor "Ensenya el Cangur"** — l'alumne resol problemes de M3Kang i, quan encerta, ensenya a un company fluix (el Cangur, que és el model) amb una pista que no pot contenir la resposta. La placa mesura si la pista ha ajudat.
3. **El pont d'idioma** — el mateix problema en la llengua de l'alumne i en català, amb retirada progressiva, i un diagnòstic de si el que falla és la llengua o les matemàtiques.

El **dashboard Tukey** recull les mesures de tot plegat i justifica les decisions de disseny.

### Principi de disseny

El model de la placa (Qwen3.5 0.8B) encerta un 22,5 % dels problemes segons els organitzadors, menys que respondre sempre "D". Per tant:

- **No fa de professor.** No genera explicacions ni correccions.
- **Només fa crides d'un token**: se li demanen les probabilitats de A–E.
- La feina de fons la fan **M3Kang** (que ja porta la resposta correcta), els **embeddings** i **Python**.

## 2. El problema que adrecem

- El nivell de matemàtiques a Catalunya baixa a PISA. *Verifiqueu les xifres abans de posar-les al pitch.*
- PISA i el Cangur avaluen amb problemes contextualitzats i amb molt de text. Qui no domina la llengua de l'aula falla abans d'arribar a les matemàtiques.
- Els docents no donen l'abast per atendre cada alumne.
- Les dades de l'alumne no han de sortir del dispositiu.

## 3. L'experiència de l'alumne

Una web servida per la placa, amb forma de xat amb el Cangur, i la matriu LED al costat. Hipòtesi de treball: **un alumne per placa**.

1. **El sistema proposa un problema** segons el nivell de l'alumne.
2. **L'alumne respon** amb botons A–E. La matriu LED mostra ✓ o ✗.
3. **Si falla**, pot demanar ajuda per graons:
   1. un problema semblant i més fàcil, resolt;
   2. el tema o el mètode;
   3. la millor pista del banc per a aquest problema;
   4. la solució, només si la demana expressament.
4. **Si encerta**, primer se li confirma ✓ i després el Cangur diu la seva resposta (sempre incorrecta). L'alumne li escriu una pista.
   - Si la pista conté la resposta, es rebutja i s'explica per què.
   - Si no, el Cangur "s'ho torna a pensar" i una barra a la matriu LED puja o baixa.
   - Màxim tres intents.
5. **Problema següent.**

No és un xat lliure: l'alumne només té els botons A–E, el botó "Pista" i la caixa per escriure la seva pista. **Les frases del Cangur són plantilles escrites per nosaltres**; el model no genera text.

### Problemes externs (prioritat baixa)

Si l'alumne introdueix un problema que no és a M3Kang:

1. Es mostren el tema, el nivell estimat i problemes semblants del banc per practicar.
2. Només si l'alumne ho demana, com a últim graó, el Cangur diu la seva suposició amb l'avís:
   *"Si introdueixes un problema extern no podem confirmar al 100 % la resposta. Consulta-ho a fonts oficials o amb el teu professor!"*

No es dona la resposta d'entrada: el repte demana guiar sense fer els deures.

## 4. Arquitectura

| Peça | On corre | Què fa |
| --- | --- | --- |
| Pàgina web | Navegador de l'alumne | Mostra el problema, recull resposta i pista |
| App Python | Linux de la placa | Lògica, filtre de fuites, Elo, crides al model |
| Servidor del model (8081) | Linux de la placa | Torna les probabilitats de les lletres |
| Servidor d'embeddings (8082) | Linux de la placa | Veïns (només en preparació i problemes externs) |
| SQLite (`tutor.db`) | Linux de la placa | Alumne, intents, pistes, puntuacions, textos |
| Sketch | Microcontrolador | ✓/✗, nivell i barra de confiança a la matriu LED |

Les crides al model van en un fil a part i la web pregunta l'estat cada segon.

### Estructura del codi

```text
predict.py            entrada oficial (no canvia la línia de comandes)
copilot/llm.py        letter_probs(): probabilitats de A–E (compartida)
copilot/pipeline.py   solve(): correcció de biaix, rotacions, pressupost de temps
copilot/tutor.py      confiança del Cangur i efecte d'una pista
copilot/leak.py       filtre de fuites
copilot/elo.py        puntuacions i tria del problema següent
copilot/store.py      accés a SQLite
prep/                 scripts de preparació, un per pas
sim/students.py       alumnes simulats
app/                  app d'App Lab: python/main.py, assets/, sketch/
dashboard/            dashboard Tukey
```

```sql
problems(id, level, year, number, topic, elo, k_answer, k_margin, eligible, neighbours)
texts(id, lang, text)
student(id, lang_origen, elo_cat, elo_origen, etapa)
attempts(problem_id, lang, answer, correct, seconds, ts)
hints(problem_id, text, delta, shown, solved_after, ts)
```

## 5. `predict.py`: resoldre el millor possible

### El contracte, que no es pot trencar

- `python3 predict.py --input … --output …`, CSV amb `id, language, answer, seconds, status`.
- Una lletra A–E per problema.
- **60 s per problema en el pitjor cas**, no de mitjana.
- Sense xarxa, determinista (temperatura 0, `SEED=42`), sense dependències noves a la placa.
- **No canviar el commit de llama.cpp.**
- Si es canvia de model: actualitzar `config.env` (repositori, revisió, fitxer, SHA256), els fitxers de servei i les skills.
- Després de cada canvi: `python3 predict.py --input data/sample_problems.jsonl --output results/check.csv`.

### Experiments, un canvi cada vegada

| # | Canvi | Cost per problema | Comentari |
| --- | --- | --- | --- |
| 0 | `except Exception` final → `D` | Cap | Evita que un error aturi l'execució oficial |
| 1 | Corregir el biaix de lletra amb `logprobs` | Cap | Dividir cada probabilitat per la tendència del model a dir aquella lletra |
| 2 | Rotar les opcions i fer la mitjana | +2–4 s per rotació | Només mentre quedi marge de temps |
| 3 | Problemes sense opcions | Cap | Lletra més freqüent per nivell al train |
| 4 | Model de la mida següent (~2B, 4 bits) | ~2–3× més lent | Comprovar RAM, temps i llicència |
| 5 | Raonament amb límit de tokens | +20–40 s | Als organitzadors els va empitjorar; baixa prioritat |

Cap guany està garantit. Objectiu realista: superar clarament el 25 % de "sempre D" sobre tota la validació.

### Com mesurar

- Amb 50 problemes l'interval de confiança és d'uns ±12 punts: serveix per descartar, no per concloure.
- Els candidats es confirmen amb `eval.py --limit 0` (281 problemes, ~45 min), de nit.
- Comparar configuracions sobre els mateixos problemes.
- Validació amb `--val-years 2023,2024`.
- Avaluar també en català: `eval.py --languages cat`.

## 6. El tutor per dins

### 6.1 Confiança del Cangur

`letter_probs(problem)` demana `logprobs: true, top_logprobs: 5` amb `max_tokens: 1` i torna les probabilitats de A–E normalitzades. *Cal verificar que torna les cinc lletres amb la gramàtica activa; si no, provar `/completion` amb `n_probs`.*

Prompt, amb la pista sempre al final perquè el prefix quedi a la memòria cau:

```text
[instrucció fixa del sistema]
[enunciat en anglès, mateix id]
A) …  B) …  C) …  D) …  E) …
Hint from a classmate: <pista>
Answer:
```

- **Crida de referència**: quan el problema surt a pantalla, amb la pista neutra "Think carefully.".
- **Crida amb pista**: només es rellegeix la pista. Estimació: 3–5 s. *Verificar amb `prompt_n`.*

### 6.2 El Cangur sempre falla

Amb `p` les probabilitats i `c` la lletra correcta:

- Resposta inicial: es treu `c` i es renormalitza, `q_i = p_i / (1 − p_c)`. El Cangur diu la lletra amb `q` més alta.
- Marge: `m = ln(p_c) − ln(max p_i, i ≠ c)`. Negatiu vol dir que prefereix una incorrecta.
- Efecte de la pista: `Δ = m_després − m_abans`.
- El Cangur queda convençut si `Δ > τ` i `m_després > 0`.

Exemple: correcta C; A 0,30 · B 0,10 · C 0,15 · D 0,40 · E 0,05. El Cangur diu D (47 %), `m = −0,98`. Després de la pista: A 0,20 · B 0,10 · C 0,45 · D 0,20 · E 0,05, `m = +0,81`, `Δ = 1,79`: canvia a C.

Els problemes on el model ja preferia la correcta (`m_abans > 0`) no s'ofereixen en mode ensenyar. **Cal documentar que la resposta inicial està forçada.**

### 6.3 Filtre de fuites

Codi Python. Rebutja la pista si:

- anomena la lletra correcta ("la C", "C)", "opció c");
- conté el valor de l'opció correcta, en xifres o en lletres;
- indica la posició ("la tercera", "la del mig");
- té més de ~200 caràcters.

Si el valor correcte ja surt a l'enunciat, la comprovació del valor es desactiva per a aquell problema. El filtre no atura fuites indirectes ("és el doble de 5"); es mesura i s'explica.

### 6.4 Valorar si una pista és bona

1. **Banc llavor**: 2–3 pistes de mètode per tema, escrites a mà.
2. **Negatius**: cada pista aparellada amb un problema que no és el seu, i frases buides.
3. **Senyals**: `Δ`, similitud pista–enunciat, similitud amb les pistes llavor, longitud.
4. **Llindar `τ`**: el canvi que les pistes absurdes gairebé mai superen. Si hi ha temps, una regressió logística sobre els senyals, entrenada al portàtil i executada a la placa com una suma.
5. **Senyal humà**: quants alumnes encerten després de veure cada pista.

*Pendent de preguntar als mentors: es pot ampliar el banc llavor generant pistes al portàtil amb un model gran? Fins que ho confirmin, no es fa.*

### 6.5 Nivell i tria del problema (Elo)

- Probabilitat d'encert: `P = 0,2 + 0,8 / (1 + 10^((R_problema − R_alumne)/400))`.
- Actualització: `R ← R + K·(resultat − P)` per a l'alumne, i el contrari (més lent) per al problema. `K` comença a 160 i baixa fins a 40. *Canviat després de simular-ho: amb K = 32 fix, un alumne que comença 300 punts lluny encara s'equivoca de ~170 punts després de 20 respostes; amb K decreixent, de ~65.*
- Següent problema: l'elegible no vist amb `P` més propera a 0,7. Si l'alumne ha fallat, del mateix tema.
- Elo inicial: `1000 + 150·nivell + 100·tram`. *Verificar amb les dades que el número de pregunta reflecteix dificultat.*

## 7. El pont d'idioma

### 7.1 Pont multilingüe amb retirada progressiva

M3Kang té el mateix problema, amb el mateix `id`, en 108 idiomes.

- Preparació: `prepare_m3kang.py --languages eng,cat,esp,arb,zho,fra --save-images`. Per a altres llengües, `--shards all`.
- Per a la llengua d'origen es mostra la **imatge original** del problema, que ja porta les opcions.
- Tres etapes per alumne:
  1. català i llengua d'origen de costat;
  2. només català, amb un botó "veure en la meva llengua" (es compta cada clic);
  3. només català.
- L'alumne puja d'etapa quan encerta sense fer servir el botó.
- La cerca de veïns es fa sempre amb la versió anglesa del mateix `id`.

### 7.2 Diagnòstic "llengua o matemàtiques?"

- Dues puntuacions: `elo_cat` i `elo_origen`. S'actualitza la de la llengua en què s'ha presentat el problema.
- A partir de l'etapa 2, un de cada tres problemes es presenta en la llengua d'origen, amb dificultat semblant. Mai el mateix problema dues vegades.
- `bretxa = elo_origen − elo_cat`, amb un mínim de 30 problemes per llengua. *Canviat després de simular-ho: amb 15, una bretxa real de 200 punts es mesura com a ~160, i fins i tot amb 30 la meitat central dels alumnes va de ~120 a ~260. Es mostra com a franja orientativa.*
- **Sense etiquetar ningú**: la llengua la tria l'alumne, la bretxa és informació per a ell i el docent, i no surt de la placa.

## 8. Fase de preparació

| Pas | On | Què fa | Temps |
| --- | --- | --- | --- |
| 1 | Portàtil | `prepare_m3kang.py` amb les llengües i les imatges | ~15 min per llengua |
| 2 | Placa | `build_index.py`: embeddings | ~4 min |
| 3 | Placa | Marcar elegibles: `text_only` i cinc opcions llegides | segons |
| 4 | Placa | Desar els 5 veïns de cada problema | minuts |
| 5 | Placa | Temes: k-means (k ≈ 12) o paraules clau, noms posats a mà | minuts |
| 6 | Placa | Elo inicial | segons |
| 7 | Placa | Línia base del Cangur per a tots els elegibles | ~1,5 h, de nit |
| 8 | Placa | Experiment de pistes i càlcul de `τ` | ~1 h |

**Els temes són imprescindibles**: l'anàlisi d'errors per tema és un lliurable obligatori.

## 9. Mesures i validació

| Què | Com |
| --- | --- |
| Encert de predict | `eval.py`, per nivell, tema i idioma, amb el nombre de problemes |
| Latència | Mitjana, mediana i pitjor cas de cada pas |
| Efecte de les pistes | `Δ` de pistes bones contra absurdes, 25 problemes |
| Filtre de fuites | 40 pistes de prova (20 amb fuita, 20 netes) |
| Elo | Alumnes simulats amb habilitat coneguda: convergeix? en quants problemes? |
| Bretxa d'idioma | Alumnes simulats amb penalització coneguda: es recupera? |

## 10. Side Challenge Tukey

Un dashboard de les **nostres decisions de disseny**, no la vista del docent. Quatre o cinc panells, cadascun amb pregunta, evidència i decisió escrita.

| Pregunta | Gràfic | Decisió |
| --- | --- | --- |
| Quina configuració de predict? | Encert contra latència, amb la línia dels 60 s; boxplots de temps | Configuració final |
| On falla? | Encert per nivell, tema i idioma, amb n i interval de confiança | Quins problemes oferir |
| Té biaix de lletra? | Lletres predites contra reals, abans i després | Aplicar o no la correcció |
| Les pistes tenen efecte? | Boxplot de `Δ`, bones contra absurdes | Valor de `τ`, o abandonar la mecànica |
| El filtre funciona? | Fuites aturades i pistes netes rebutjades | Regles del filtre |

- Tots els números surten dels mateixos fitxers de `results/`.
- Cap conclusió afirma una millora que queda dins del soroll.
- Cap enunciat de M3Kang.

## 11. Prioritats

**Imprescindible**
1. Posada a punt de la placa (passos 0–12 del README) i baseline.
2. `letter_probs()` i canvis 0–1 de predict.
3. Experiment de pistes amb `Δ` (go/no-go).
4. Tutor: Elo, Cangur que sempre falla, filtre de fuites, escala de pistes.
5. Temes.
6. Web i matriu LED.
7. Mesures, dashboard, documentació i assaig de la demo.

**Important**
8. Canvis 2–4 de predict, amb execucions completes de nit.
9. Pont multilingüe (tres etapes).
10. Doble Elo.
11. Banc llavor de pistes.

**Si sobra temps**
12. Problemes externs.
13. Raonament a predict; regressió logística per a les pistes.

**Si l'experiment de pistes surt malament**: es manté tot menys la barra de confiança. El Cangur passa a recollir pistes filtrades i a valorar-les només amb el senyal humà.

### Línies de treball

- **A**: predict i mesures.
- **B**: tutor i dades (Elo, temes, idiomes, pistes).
- **C**: placa, web, matriu LED, dashboard i documentació.

## 12. Demo i lliurables

### Demo (90 s dins d'un pitch de 3 min)

Problema en àrab i català → l'alumne encerta → el Cangur diu una lletra errònia → pista amb fuita rebutjada → pista bona, la barra puja. El doble Elo es mostra amb un perfil ja carregat o amb el resultat dels alumnes simulats.

- Wi-Fi apagat, serveis arrencats amb la placa, `adb forward tcp:7000 tcp:7000`.
- Problemes triats i provats el mateix dia.
- Dos assajos amb cronòmetre i vídeo de reserva.

### Lliurables

- Repo públic a GitHub amb llicència oberta (per exemple MIT) i README: què fa, arquitectura, com replicar-ho, resultats contra el 22,5 %, anàlisi d'errors per tema, idioma i nivell, què no ha funcionat, equip.
- Projecte a Arduino Project Hub.
- Dashboard Tukey.

### No publicar mai

`train.jsonl`, `val.jsonl`, `data/images/`, `index.db`, `tutor.db`, textos en altres idiomes, banc de pistes. Es publiquen els scripts que ho regeneren. Afegir-ho al `.gitignore` des del primer dia. La web no pot carregar res d'internet.

## 13. Pendent

### Preguntes per als organitzadors

- El test ocult porta opcions en text? En quins idiomes? S'executa a la nostra placa?
- Es pot generar un banc de pistes al portàtil amb un model gran?
- Com i quan es lliura el dashboard, i ha de ser públic?

### Verificacions a la placa

- `logprobs` torna les cinc lletres amb la gramàtica activa.
- La memòria cau del prefix funciona com s'espera (`prompt_n`).
- El model reacciona diferent a pistes bones i absurdes.
- Enunciat en anglès amb pista en català.
- El brick `web_ui` accepta enviar text; si no, servidor estàndard com el de l'`explorer`.
- Una app d'App Lab arriba a `127.0.0.1:8081`.
- RAM amb tot funcionant (`free -m`).

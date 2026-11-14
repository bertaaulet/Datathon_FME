# Registre de decisions

Append-only. Format: data · decisió · per què · qui.

- 2026-11-14 · `CLAUDE.md` com a memòria compartida + `docs/STATUS.md` i `docs/DECISIONS.md` · mantenir el context curt i tothom al dia · Berta
- 2026-11-14 · Idea: **"Ensenya el Cangur"** (Teach). L'alumne resol problemes de M3Kang i, quan encerta, ensenya amb una pista el Cangur (el model), que fa de company fluix · el model encerta un 22,5 % i no pot fer de professor; així la seva debilitat és la mecànica i tot es pot mesurar · Elsa
- 2026-11-14 · El model només fa crides d'un token (probabilitats de A–E) i mai escriu text per a l'alumne · no pot dir res fals i cada crida és ràpida · Elsa
- 2026-11-14 · `predict.py` forma part del projecte i s'intenta millorar (biaix de lletra, rotació d'opcions, lletra més freqüent sense opcions, mai s'atura) · es puntua al test ocult per a tots els equips · Elsa
- 2026-11-14 · El Cangur **sempre comença equivocat**: diu l'opció incorrecta més probable. L'efecte d'una pista és el canvi del marge `ln P(correcta) − ln P(millor incorrecta)` · dona sempre alguna cosa a ensenyar i es mesura amb un número; cal documentar que la resposta inicial és forçada · Elsa
- 2026-11-14 · Pont d'idioma: tres etapes (dues llengües, català amb botó, només català) i dues puntuacions Elo per alumne (llengua d'origen i català) · adreça la barrera lectora que hi ha darrere de PISA; M3Kang ja té el mateix problema en molts idiomes · Elsa
- 2026-11-14 · Un problema extern (que no és al banc) no es respon d'entrada: tema, nivell estimat i problemes semblants; la suposició del Cangur només si l'alumne la demana, amb avís · el repte demana guiar sense fer els deures, i ningú en sap la resposta segura · Elsa
- 2026-11-14 · El codi viu a `projecte/`, com a còpia sense historial del repo base (commit `d6e3f1b`) · mantenir junts el pla, els enunciats i el codi en un sol repo · Elsa
- 2026-11-14 · Elo amb `K` decreixent (160 → 40) i bretxa d'idioma visible només amb 30 respostes per llengua, com a franja · simulat amb `sim/students.py`: amb K = 32 fix l'error després de 20 respostes era de ~170 punts (ara ~65), i amb 15 respostes una bretxa real de 200 es mesurava com a ~160 · proposta de Claude, pendent de confirmar per l'equip
- 2026-11-14 · Web del tutor amb servidor estàndard de Python al port 8090 (no el brick `web_ui`); l'app d'App Lab només dibuixa la matriu LED · es pot provar sense placa i el tutor funciona encara que l'app de la matriu falli · proposta de Claude, pendent de confirmar per l'equip
- 2026-11-14 · Temes per paraules clau (`copilot/topics.py`), no per k-means · ràpid, determinista i fàcil d'explicar; cal revisar-ne 50 a mà · proposta de Claude, pendent de confirmar per l'equip

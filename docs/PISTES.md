# Pistes: com funcionen (versió 2026-11-15)

> Estat: **implementat al codi** (branca `berta/pistes-flux-nou`, provat amb el simulador). Falta preparar les dades (banc de l'agent, Cangur en català, τ) i mesurar-ho a la placa: vegeu el punt 6. Les decisions són a `DECISIONS.md` (2026-11-14 i 2026-11-15).

## En 30 segons
- Cada alumne té **la seva placa**. No hi ha companys: el que escriu un alumne no ho veu ningú més.
- Hi ha **dos tipus de problemes**: els del **banc** (problemes de M3Kang del train, preparats al portàtil) i els **nous** (que porta l'alumne).
- Si l'alumne **falla**, demana ajuda i rep pistes per **graons**.
- Si l'alumne **encerta**, **ensenya el Cangur** (el Qwen fent de company que s'equivoca) amb una pista seva.
- La **resposta correcta** mai surt del Cangur: al banc és la de M3Kang; als problemes nous, la del harness de `predict.py`.

## 1. L'alumne falla: escala d'ajuda
Cada clic a "ajuda" puja un graó. Entre graó i graó pot tornar a respondre.

| Graó | Problema del banc | Problema nou |
|---|---|---|
| 1 | Tema + frase de mètode ("És un problema de Geometria. Fes un dibuix…") | Igual |
| 2 | Pista del pas 1 de l'agent ("Una pista: «…»") | La pista generada pel Qwen, si ja està feta; si no, una frase de mètode |
| 3 | Pista del pas 2 de l'agent ("Una altra pista: «…»") | La pista generada, si no ha sortit al graó 2; si no, una frase de mètode |
| 4 | Un problema semblant més fàcil, **sense la resposta**: l'alumne el pot intentar, i la resposta surt quan respon o prem "Mostra'n la resposta" | Igual (el veí més proper) |
| 5 | La solució (compta com a no resolt) | La solució "segons els nostres càlculs" + l'avís de sempre |

Si falta alguna cosa (un problema sense pistes de l'agent, cap veí), surt la frase de mètode següent del tema, o se salta al graó 5.

**D'on surt cada cosa**
- **Tema i mètode:** `topics.py`. El tema es dedueix per paraules clau, i cada tema té 3 frases de mètode escrites per l'equip, iguals per a tots els problemes del tema.
- **Pistes de l'agent:** 2 per problema del banc, ordenades (pas 1: per on començar; pas 2: el pas següent), escrites per Claude al portàtil i passades pel filtre de fuites. Només hi ha problemes del train al banc del tutor, perquè l'agent no veu mai la resposta d'un problema de validació.
- **Pista generada (problemes nous):** després de la resposta del harness i de la referència del Cangur, la placa agafa el problema del banc més semblant que tingui pistes (1 veí) i li demana al Qwen: "per a aquest problema, una bona pista era X; escriu-ne una per al nou" (`copilot/hintgen.py`, sense les opcions). Passa pel filtre estricte. Estimat ~37 s, a mesurar. `HINTGEN=off` la desactiva.
- **Problema semblant:** un dels 5 veïns calculats al portàtil, el primer més fàcil (Elo més baix). Va al final perquè, si s'assembla molt, és gairebé la solució.

## 2. L'alumne encerta: ensenyar el Cangur
1. El Cangur **sempre diu una opció incorrecta**. Les probabilitats del Qwen es calculen per endavant amb una pista neutra ("Pensa-ho bé.") i no es toquen:
   - **Cas 1** (el model prefereix una incorrecta, ~78 % del banc): diu la seva opció real ("Jo he dit la B…").
   - **Cas 2** (el model ja prefereix la correcta, ~22 %): **fa veure** que pensa la incorrecta més probable.
   - "N'estic un X % segur" és la probabilitat real del model per a aquella opció.
2. L'alumne escriu una pista d'una frase.
3. **Filtre de fuites:** si diu la lletra, la posició o el resultat, es rebutja, se li explica per què i no perd cap intent.
4. El Cangur torna a llegir el problema, ara amb la pista.
5. Es mesura si s'ha acostat a la correcta. És el **Δ (delta)**:
   - Abans: correcta 10 %, B 40 % → lluny de la correcta.
   - Després: correcta 35 %, B 25 % → ara la prefereix.
   - Δ = quant s'ha mogut cap a la correcta.
6. Si Δ supera el **llindar τ** i ara prefereix la correcta: "Aaah, ara ho veig!". Si s'ha mogut una mica: "M'ho expliques d'una altra manera?". Si no: "No t'he entès…". Té 3 intents.
7. **Cas 2:** el model ja sabia la resposta, així que el Δ no diu res. Es convenç si la pista passa el filtre i el model continua preferint la correcta. La barra LED arrenca per sota de la meitat i salta al valor real quan es convenç.

**τ** es calibra amb l'experiment **D2** (només problemes del cas 1): 25 problemes, cadascun amb una pista bona i una d'absurda. τ ha de ser prou alt perquè una pista absurda gairebé mai el convenci. Mentre no hi hagi D2, τ = 1,0 (provisional).

**Idioma:** el Cangur llegeix **el problema, les instruccions i la pista en català** (`KANGAROO_LANG=cat`). No és perquè encerti (l'encert no importa: la resposta correcta ve de M3Kang o del harness), sinó perquè **entengui la pista**: és l'instrument que la mesura. `predict.py` i la resta segueixen en anglès (`MODEL_LANG=eng`). Les respostes precalculades porten l'idioma en què es van mesurar: si no coincideix, el tutor torna a preguntar al model (~10 s).

## 3. Què es guarda
- **El text d'una pista de l'alumne**, només si és d'un problema del banc, del **cas 1** (el Cangur no fingia) **i** l'ha convençut (Δ > τ). Serveix per a la vista del docent i per poder ampliar el banc més endavant.
- **Comptadors sense text** (taula `hint_events`), per al dashboard i la vista del docent: pistes rebutjades per fuita (i per quin motiu), pistes que no han convençut el Cangur i pistes que sí, i quantes eren de casos fingits. En el cas 2 no es desa el Δ.
- Les pistes dels problemes nous **no es guarden ni es compten**.
- `tutor.db` té text de M3Kang: **mai es puja a Git**.

## 4. Què hem tret
- Les pistes "d'un company" i el seu rànquing.
- La rellevància i els duplicats (`hintsim.py`, `embed_refs.py`, `HINT_DUP_SIM`, `HINT_MIN_REL`): eren per gestionar pistes de molts alumnes.
- La pista d'un veí mostrada tal qual als problemes nous.

## 5. Configuració i scripts
| Què | On |
|---|---|
| `KANGAROO_LANG=cat`, `HINT_TAU`, `HINT_MAX_TRIES`, `HINTGEN`, `HINTGEN_MAX_TOKENS` | `projecte/config.env` |
| Banc de l'agent: instruccions i validació (camp `step`) | `prep/agent/hint_bank.md`, `prep/check_agent_output.py` |
| Importar el banc | `prep/import_hints.py data/agent_hints.jsonl` |
| Respostes del Cangur, en català | `prep/kangaroo_baseline.py` (`--redo` si canvia l'idioma) |
| Δ de cada pista de l'agent | `prep/kangaroo_agent_hints.py` → `results/agent-hints-kangaroo.csv` |
| D2 i τ | `prep/hint_experiment.py` |
| Pista dels problemes nous | `copilot/hintgen.py` |

## 6. Pendents
Els passos de les dades, per a qui els executi, són a [`RUNBOOK_PISTES.md`](RUNBOOK_PISTES.md).

| Què | On | Qui |
|---|---|---|
| Revisar i fusionar `berta/pistes-flux-nou` | Repo | Berta |
| Reconstruir `tutor.db` (només train elegibles) amb `build_tutor_db.py` | Portàtil | Berta |
| Banc de l'agent: 2 pistes ordenades per problema elegible → `check_agent_output.py` → revisar-ne 20 → `import_hints.py` | Portàtil | Berta |
| Recalcular el Cangur en català (`kangaroo_baseline.py --redo`, ~5 min al portàtil) i `kangaroo_agent_hints.py` | Portàtil | Berta |
| D2: pistes bones, absurdes i amb fuita per a 25 problemes (agent) → `hint_experiment.py` → τ | Placa (~25 min) | Berta + placa |
| Mesurar el temps de la pista generada (1 veí) i provar-la amb els problemes inventats | Placa | Berta + placa |
| Recorregut sencer a la placa (5 graons, cas fingit, pista generada, matriu LED) | Placa | Berta + placa |
| Panell de pistes al dashboard (`agent-hints-kangaroo.csv`, `hints-*.csv`) | Repo | — |

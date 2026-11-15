# Pistes: com funcionen (versió 2026-11-15)

> Estat: **implementat, dades preparades i desplegat a la placa** (616 problemes, 1.232 pistes de l'agent, Cangur en català). D2 i la pista generada mesurats a la placa; paràmetres definitius des del 2026-11-15 04:30 (`KANGAROO_RULE=clean`, `HINTGEN=off`). Última prova: [`PROVES_FINALS_PISTES.md`](PROVES_FINALS_PISTES.md). Les decisions són a `DECISIONS.md` (2026-11-14 i 2026-11-15).

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

**Amb el pont d'idioma:** les frases de mètode surten en català i en la llengua d'origen segons l'etapa, i el problema semblant del graó 4 també segueix l'etapa. Les pistes de l'agent i la pista generada només existeixen en català: a les etapes 1 i 2 surten amb un avís traduït que ho diu, i el seu contingut no es tradueix.

**D'on surt cada cosa**
- **Tema i mètode:** `topics.py`. El tema es dedueix per paraules clau, i cada tema té 3 frases de mètode escrites per l'equip, iguals per a tots els problemes del tema.
- **Pistes de l'agent:** 2 per problema del banc, ordenades (pas 1: per on començar; pas 2: el pas següent), escrites per Claude al portàtil i passades pel filtre de fuites. Només hi ha problemes del train al banc del tutor, perquè l'agent no veu mai la resposta d'un problema de validació.
- **Pista generada (problemes nous):** després de la resposta del harness i de la referència del Cangur, la placa agafa el problema del banc més semblant que tingui pistes (1 veí) i li demana al Qwen: "per a aquest problema, una bona pista era X; escriu-ne una per al nou" (`copilot/hintgen.py`, sense les opcions). Passa pel filtre estricte. **Desactivada (`HINTGEN=off`)**: a la placa va trigar 28–34 s (51–70 s des que s'entra el problema) i les pistes eren fluixes o trencades. Els problemes nous mostren frases de mètode als graons 2 i 3.
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
6. **Quan es convenç** (`KANGAROO_RULE` a `config.env`). Per defecte, `clean`: **amb qualsevol pista que passi el filtre de fuites**, al primer intent ("Aaah, ara ho veig!"), i la barra puja com a mínim a 0,85. El model llegeix igualment la pista (~12,5 s a la placa) i el Δ es desa com a dada. Les altres regles: `delta` (Δ > τ) i `strict` (Δ > τ i ara prefereix la correcta; si no: "M'ho expliques d'una altra manera?" / "No t'he entès…", 3 intents).
7. **Cas 2:** el model ja sabia la resposta, així que el Δ no diu res. La barra arrenca per sota de la meitat.

**Per què `clean`:** el D2 a la placa (24 problemes) va mostrar que el Qwen 0.8B no distingeix una pista bona d'una d'absurda (13 a 11, p = 0,84; mediana de Δ +0,11 i +0,10) i que gairebé no canvia d'opinió ni quan li diuen la resposta (1/24): parteix d'un marge mediana de −1,69 i una pista el mou ±0,1–0,5. La placa no pot jutjar si una pista és bona; sí que pot comprovar que no dona la resposta.

**τ = 0,49**, calibrat amb el **D2** a la placa (9 de cada 10 pistes absurdes mouen el Cangur menys que això). Amb `clean`, només decideix quin text es guarda.

**Idioma:** el Cangur llegeix **el problema i les instruccions en català** (`KANGAROO_LANG=cat`). L'alumne pot escriure la pista en qualsevol de les 6 llengües del pont, i el Cangur la llegeix tal com s'ha escrit, sense traduir-la; l'efecte d'una pista que no és en català **no s'ha mesurat** (protocol a `DECISIONS.md`). No és perquè encerti (l'encert no importa: la resposta correcta ve de M3Kang o del harness), sinó perquè **entengui la pista**: és l'instrument que la mesura. `predict.py` i la resta segueixen en anglès (`MODEL_LANG=eng`). Les respostes precalculades porten l'idioma en què es van mesurar: si no coincideix, el tutor torna a preguntar al model (~10 s).

## 3. Què es guarda
- **El text d'una pista de l'alumne**, només si és d'un problema del banc, del **cas 1** (el Cangur no fingia) **i** ha mogut el model de debò (Δ > τ i ara prefereix la correcta), sigui quina sigui `KANGAROO_RULE`. Serveix per a la vista del docent i per poder ampliar el banc més endavant.
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
| `KANGAROO_LANG=cat`, `KANGAROO_RULE=clean`, `HINT_TAU`, `HINT_MAX_TRIES`, `HINTGEN=off`, `HINTGEN_MAX_TOKENS` | `projecte/config.env` |
| Prova de cap a cap a la placa | `prep/tutor_smoke.py` |
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
| ~~Fusionar el codi; refer `tutor.db`; banc de l'agent; Cangur en català; D2; temps de la pista generada~~ | Fet (Irene, 2026-11-15) | — |
| Fusionar `berta/docs-pistes-main` (regla `KANGAROO_RULE`, `HINTGEN=off`, `tutor_smoke.py`) | Repo | Berta |
| Última prova a la placa amb els paràmetres definitius ([`PROVES_FINALS_PISTES.md`](PROVES_FINALS_PISTES.md)), inclosa la matriu LED | Placa (~25 min) | Qui tingui la placa |
| Revisió humana d'una mostra de pistes de l'agent (ara només la de Codex) | Portàtil | — |
| Panell de pistes al dashboard (`agent-hints-kangaroo.csv`, `hints-*.csv`) | Repo | — |

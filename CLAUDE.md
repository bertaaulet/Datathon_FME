# CLAUDE.md — Datathon FME 2026 · Repte Qualcomm "Math on the Edge"

Memòria compartida de l'equip (4 persones). Es carrega a cada sessió de Claude Code: **mantenir-lo curt**. El detall va a `docs/`.

## El repte (resum)
- Copilot de mates que funciona **100% offline a l'Arduino UNO Q** (4 GB, Cortex-A53) i usa el dataset **M3Kang** (Cangur 2007–2024, 8 nivells, 108 idiomes) de manera innovadora.
- Via **Teach** (guiar sense donar la resposta) o **Reason** (encertar A–E). `predict.py` es puntua amb test ocult **sempre**.
- Baseline a batre: **22,5%** (per sota de "sempre D" ≈ 25%).
- Side challenge **Tukey**: dashboard per prendre decisions sobre el repte (utilitat, adequació dels gràfics, coherència). Es construeix a partir de `results/`.
- Anàlisi completa del repo base: `descripcio_main_challenge/analisi-repo-base-qualcomm.md`.

## Restriccions dures (no trencar mai)
- `predict.py`: entrada JSONL → CSV `id,language,answer,seconds,status`; una lletra A–E per problema; **≤ 60 s/problema**; temperatura 0, `SEED=42`; sense xarxa (només `127.0.0.1`).
- A la placa: **només llibreria estàndard de Python**, sense pip.
- Codi de Teach separat (p. ex. `copilot/tutor.py`): no ha d'alterar l'execució oficial.
- Qualsevol excepció a `solve()` ha d'acabar en lletra per defecte, mai en crash.
- Pressupost: temps ≈ tokens_prompt/11 + tokens_generats/6 ≤ 57 s. RAM lliure ≈ 2,5 GB.
- **Llicència M3Kang: només recerca.** Mai pujar `train.jsonl`, `val.jsonl`, `data/images/`, `index.db` ni text de problemes (tampoc a l'historial).
- Placa: apagar sempre amb `sudo poweroff`.
- Tutor: el model **no escriu text per a l'alumne** (només dona probabilitats de lletres; les frases del Cangur són plantilles) i **no es dona la resposta** abans que l'alumne resolgui o demani la solució. Un problema extern mai es respon d'entrada.
- Tampoc pujar res derivat de M3Kang: `tutor.db`, fitxers de pistes, textos traduïts.
- **Mai reportar un número mesurat contra el servidor simulat** (`tests/fake_llama.py`) ni amb els problemes inventats.

## On és cada cosa
- `docs/STATUS.md` — estat actual, qui fa què, bloquejos. **Llegir a l'inici de cada sessió.**
- `docs/DECISIONS.md` — registre de decisions (append-only).
- `pla_projecte.md` — el pla del projecte "Ensenya el Cangur" (Teach + predict + pont d'idioma + dashboard).
- `projecte/` — **tot el codi** (còpia del repo base, commit `d6e3f1b`, més el nostre). Les comandes s'executen des d'aquí.
  - `projecte/README.md` — què fa i els passos per replicar-ho. `projecte/docs/SETUP.md` — la guia dels organitzadors.
  - `projecte/results/ablations.csv` — font única de veritat dels experiments (la genera `eval.py`).
  - `projecte/.skills/` — skills del repo base, ampliades (`ln -s ../projecte/.skills .claude/skills`).
  - Proves sense placa: `python -m unittest discover -s tests`.

## Com treballem amb Claude
1. Inici de sessió: `git pull`, llegir `docs/STATUS.md`.
2. Experiments: sempre amb `eval.py --name <nom-descriptiu>` perquè quedin a `ablations.csv` amb el commit. Resultats finals amb `--limit 0` (amb ≤ 50 problemes, 1–2 encerts és soroll).
3. Final de sessió: actualitzar `docs/STATUS.md` (la teva fila + bloquejos) i afegir a `docs/DECISIONS.md` qualsevol decisió presa. Commit petit i `git push` de seguida.
4. No editar aquest fitxer per coses temporals: només regles i context estables. Canvis aquí = avisar l'equip.
5. Preferències personals → `CLAUDE.local.md` (no es puja).

## Convencions
- Branques: `nom/tema` (p. ex. `berta/logprobs`); merge a `main` quan `predict.py` segueix passant amb `data/sample_problems.jsonl`.
- Commits en català o anglès, en imperatiu i curts.
- Documentació en català; codi i comentaris en anglès (el repo serà públic).

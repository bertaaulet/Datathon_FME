# Pistes: última fase de proves a la placa (~25 min)

Per a qui tingui la placa. És l'última comprovació de les pistes amb els **paràmetres definitius**. Si alguna prova falla, para i avisa la Berta: hi ha marxa enrere al pas 5.

## Què canvia respecte al que hi ha a la placa

| Paràmetre | Abans | Ara | Per què |
|---|---|---|---|
| `KANGAROO_RULE` (nou, `config.env`) | El Cangur es convencia si Δ > τ **i** passava a preferir la correcta | `clean`: es convenç amb **qualsevol pista que passi el filtre de fuites** | D2 a la placa: el Qwen 0.8B no distingeix pistes bones d'absurdes (13 a 11, p = 0,84) i ni tan sols canvia quan li diuen la resposta (1/24). La placa només pot jutjar el que sí que sap: explicar sense donar la resposta |
| Barra del Cangur | Marge real | Marge real, però quan es convenç puja com a mínim a 0,85 | Que la barra no digui "no ho entén" quan el Cangur diu "ara ho veig" |
| Text de les pistes que es guarda | Les que el convencien | Només les que **mouen el model de debò** (Δ > τ i prefereix la correcta) | Amb `clean` totes el "convencen"; el text només es guarda si el model s'ha mogut |
| `HINTGEN` (repo) | `on` | `off` (a la placa ja ho era) | B3: 28–34 s per pista i de mala qualitat |
| τ | 1,0 | 0,49 (ja desat a `tutor.db` per D2) | Només serveix per decidir quin text es guarda |

Els Δ es continuen desant (sense text) per al dashboard. Si l'equip prefereix una altra regla: `KANGAROO_RULE=delta` (Δ > τ, encara que continuï equivocat) o `strict` (la d'abans).

**`predict.py` no canvia**: cap d'aquests fitxers el fa servir.

## 0. Abans de començar

- La placa ha d'estar **lliure** (cap experiment de `predict.py` en marxa) i ben alimentada (`PROBLEMES.md` 15).
- Al portàtil, el repo a `main` amb la branca `berta/docs-pistes-main` ja fusionada: `git checkout main && git pull`.

## 1. Desplegar (~5 min)

Només es copien fitxers del tutor. **No copiïs `config.env` sencer**: el de la placa té la configuració final de `predict.py`.

```bash
B=/home/arduino/Datathon_FME/projecte
# còpia de seguretat dels fitxers que es canvien
adb shell "mkdir -p $B/backup-final && cp $B/copilot/tutor.py $B/copilot/leak.py $B/copilot/elo.py $B/config.env $B/backup-final/"
# el codi nou (des de projecte/ al portàtil)
for f in copilot/tutor.py copilot/leak.py copilot/elo.py prep/tutor_smoke.py prep/hintgen_timing.py prep/hintgen_problems.jsonl; do adb push $f $B/$f; done
adb push tests/. $B/tests/
# la regla nova al config.env de la placa (una línia; HINTGEN ja hi és a off)
adb shell "grep -q '^KANGAROO_RULE=' $B/config.env || echo 'KANGAROO_RULE=clean' >> $B/config.env"
adb shell "grep -E '^(KANGAROO_RULE|KANGAROO_LANG|HINTGEN)=' $B/config.env"
```

Ha de mostrar `KANGAROO_RULE=clean`, `KANGAROO_LANG=cat` i `HINTGEN=off`. Comprova també τ:

```bash
adb shell "cd $B && python3 -c \"import sqlite3;print(sqlite3.connect('data/tutor.db').execute(\\\"SELECT value FROM meta WHERE key='tau'\\\").fetchone())\""
```

Ha de dir `('0.49…',)` (si diu `None`, avisa: s'ha perdut el τ del D2).

## 2. Proves sense model (~1 min)

```bash
adb shell "cd $B && python3 -m unittest discover -s tests 2>&1 | tail -3"
```

- [ ] Acaba amb `OK` (139 proves).

## 3. El tutor de cap a cap, automàtic (~4 min)

Fa servir els models de veritat i una **còpia** de `tutor.db` (la de la placa no es toca). Recorre 4 problemes fallats (els 5 graons), 6 problemes per ensenyar el Cangur (pista amb fuita rebutjada + pista bona) i un problema extern.

En un terminal:

```bash
adb shell
cd /home/arduino/Datathon_FME/projecte
sudo systemctl stop math-tutor
python3 prep/tutor_smoke.py
sudo systemctl start math-tutor
```

En un **segon terminal**, mentre corre: `adb shell free -m` (un parell de vegades).

**Què ha de sortir:**

- Una línia inicial amb `KANGAROO_RULE=clean  tau=0.49  HINTGEN=off  KANGAROO_LANG=cat  Kangaroo measured in cat`.
- Totes les línies `PASS`, i al final `N/N checks passed`.
- Als 6 problemes d'ensenyar: `Kangaroo says a wrong option` PASS i `Kangaroo reads the hint … convinced`.
- `Kangaroo with a hint: median ~12 s, worst < 25 s`.
- `free -m`: columna *available* per sobre de **500 MB**.

- [ ] Checks: ___ / ___ · Mediana pista: ___ s · Pitjor: ___ s · RAM disponible mínima: ___ MB

## 4. Recorregut a mà al navegador (~10 min)

`adb forward tcp:8090 tcp:8090` i obre <http://127.0.0.1:8090>. Comprova el que l'script no veu:

- [ ] **Ensenyar el Cangur:** una pista bona i neta → el Cangur diu "ara ho veig" i **la barra passa de la meitat** (a la pantalla i a la **matriu LED**).
- [ ] Una pista amb la resposta ("és la C") → missatge de fuita, no gasta intent.
- [ ] **Fallar i ajuda:** els 5 graons; al graó 4, respondre el problema semblant.
- [ ] **Vista del docent:** comptadors de pistes.
- [ ] **Pont d'idioma:** comença un alumne nou amb una llengua d'origen (p. ex. castellà): el problema surt en les dues llengües i les pistes de l'agent duen l'avís "només en català".
- [ ] **Problema extern** (enganxa'n un d'inventat amb A–E): avís sempre visible; els graons 2–3 són frases de mètode.

## 5. Si alguna cosa falla: marxa enrere (~1 min)

```bash
B=/home/arduino/Datathon_FME/projecte
adb shell "cp $B/backup-final/tutor.py $B/backup-final/leak.py $B/backup-final/elo.py $B/copilot/ && cp $B/backup-final/config.env $B/config.env"
adb shell sudo systemctl restart math-tutor
```

## 6. Què has de tornar a la Berta

- `results/tutor-smoke-*.csv` (ids, passos, segons; sense text).
- Les caselles d'aquest document (passos 2–4) i el `free -m`.

Temps total: **~20–25 min** (5 de desplegar, 1 de proves, 4 de l'script, 10 a mà).

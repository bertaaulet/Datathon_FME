# Nit final a la placa — ordre complet (~1 h 30)

Per a qui té la placa aquesta nit. Quatre blocs, **en aquest ordre**: pistes → visió → conjunt de pràctica → configuració final de `predict.py` + reinici. L'ordre importa: la placa ha d'acabar la nit **en l'estat final verificat**, perquè el que compta al test és l'estat de la placa després del *last call* de les 12:00.

Si alguna cosa falla i no està coberta aquí, para i avisa la Berta. No improvisis canvis a `config.env` fora dels que es diuen.

## Regles de tota la nit

- **Alimentació pròpia de la placa** i el portàtil amb la suspensió desactivada: ja hem tingut 4 reinicis "crash" per USB/alimentació (`PROBLEMES.md` 15).
- Qualsevol tasca de més de ~2 min es llança **fora d'`adb shell`**, perquè sobrevisqui un tall d'USB:
  ```bash
  XDG_RUNTIME_DIR=/run/user/1000 systemd-run --user --unit=<nom> bash -c '<comanda>'
  # seguiment: systemctl --user status <nom> ; journalctl --user -u <nom> -f
  ```
- **Només una cosa alhora fa servir el model** (els servidors atenen una petició cada vegada).
- Apagar sempre amb `sudo poweroff` (aquesta nit no cal apagar: es deixa engegada al final).
- Mai pujar a git res amb text de M3Kang ni etiquetes per problema (CSV per problema). Les xifres agregades (`ablations.csv`) sí.
- El zip `predict_rag_test_final.zip`, si el tens, **no es fa servir**: el RAG està descartat.

## 0. Abans de començar (~5 min)

Al portàtil:
```bash
cd Datathon_FME && git checkout main && git pull
git log --oneline -1   # ha de ser 910fcfb o posterior
```
La placa lliure (cap experiment en marxa) i amb Wi-Fi o USB amb internet (el bloc B descarrega un fitxer).

---

## Bloc A — Pistes: última fase amb els paràmetres definitius (~25 min)

Segueix **`docs/PROVES_FINALS_PISTES.md`** pas a pas (desplegar `tutor.py`/`leak.py`/`elo.py`, `KANGAROO_RULE=clean`, 139 proves, `tutor_smoke.py`, recorregut al navegador, marxa enrere al pas 5 si falla). Dues notes respecte al document:

- τ = 0,49 **ja és** a la `tutor.db` de la placa (el va desar la D2 d'aquesta nit). La comprovació del pas 1 ha de dir `('0.49…',)`; si diu `None`, para i avisa.
- Quan acabis: `sudo systemctl restart math-tutor` i comprova `curl -s http://127.0.0.1:8090/api/state | head -c 200`.

Apunta les caselles del document i guarda `results/tutor-smoke-*.csv`.

---

## Bloc B — Visió: l'experiment pendent (~25 min)

Objectiu: decidir el punt "imatge" de la llista *Per decidir* i tenir el número per al README. Mesura si, en problemes **sense opcions** però amb figura, enviar la imatge al servidor de visió encerta més que la lletra de la prior. **No toca `predict.py` ni la configuració final**: el servidor de visió és temporal i es para abans del bloc C.

### B.0 Precondicions (si alguna falla, salta el bloc i apunta-ho)

```bash
ls data/images/ 2>/dev/null | head -3       # hi ha d'haver fitxers tipus lvl-X_YYYY_N_eng.png
ls data/val.jsonl
sudo systemctl stop math-tutor              # alliberem RAM i el model
free -m                                     # available > 1800 MB per arrencar el segon servidor
```

### B.1 Descarregar el projector de visió (205 MB, amb SHA256)

```bash
cd ~/models
wget --continue https://huggingface.co/bartowski/Qwen_Qwen3.5-0.8B-GGUF/resolve/f36b1ea49a332ede8fe5f389bbf5b3575ef71f48/mmproj-Qwen_Qwen3.5-0.8B-f16.gguf
sha256sum --check <<'EOF'
1dc1351c82e41b48edb55fd6ddfa7ca60fb5a16b3d5abf3ce7054880dd022847  mmproj-Qwen_Qwen3.5-0.8B-f16.gguf
EOF
```

### B.2 Arrencar el servidor de visió (temporal, com a unitat d'usuari)

```bash
XDG_RUNTIME_DIR=/run/user/1000 systemd-run --user --unit=vision-test \
  ~/llama.cpp/build/bin/llama-server \
  -m ~/models/Qwen_Qwen3.5-0.8B-Q8_0.gguf \
  --mmproj ~/models/mmproj-Qwen_Qwen3.5-0.8B-f16.gguf \
  --image-max-tokens 128 \
  --host 127.0.0.1 --port 8083 \
  --threads 4 --ctx-size 4096 \
  --parallel 1 --cache-ram 0 --ctx-checkpoints 2 \
  --jinja --reasoning off --reasoning-budget 0
sleep 60 && curl -s http://127.0.0.1:8083/health && free -m
```

Si `available` baixa de 300 MB, para el servidor (`systemctl --user stop vision-test`) i salta el bloc: no hi cap.

### B.3 Mesurar (10 problemes, ~8 min)

Des de `~/Datathon_FME/projecte`, guarda això com a `vision_test.py` i llança'l amb `systemd-run` com a dalt (`--unit=vision-run`, `bash -c 'cd ~/Datathon_FME/projecte && python3 vision_test.py > results/vision-nit.log 2>&1'`):

```python
import base64, json, os
from copilot.pipeline import solve
VISION = "http://127.0.0.1:8083/v1/chat/completions"
problems = [json.loads(l) for l in open("data/val.jsonl")]
cand = [p for p in problems if p.get("language") == "eng" and not p.get("options")
        and os.path.exists(f"data/images/{p['id']}_eng.png")][:10]
print(len(cand), "problems without options, with an image")
img_ok = prior_ok = 0
for p in cand:
    img = base64.b64encode(open(f"data/images/{p['id']}_eng.png", "rb").read()).decode()
    r = solve(p, image_b64=img, llm_url=VISION, time_limit=90)
    base = solve(p)  # without image: the prior letter, instant
    img_ok += r["answer"] == p["label"]
    prior_ok += base["answer"] == p["label"]
    print(p["id"], "img:", r["answer"], f'{r["seconds"]:.1f}s', r["status"],
          "| prior:", base["answer"], "| label:", p["label"])
print(f"vision {img_ok}/{len(cand)}  prior {prior_ok}/{len(cand)}")
```

Si els noms de `data/images/` no segueixen el patró `<id>_eng.png`, adapta la línia del `path` al patró que vegis a B.0. El log porta etiquetes per problema: **no es puja a git**; només s'envien a la Berta els dos totals i els temps.

### B.4 Desmuntar (imprescindible abans de seguir)

```bash
systemctl --user stop vision-test
curl -s http://127.0.0.1:8083/health || echo "vision aturat, correcte"
rm -f ~/Datathon_FME/projecte/vision_test.py   # res de nou al repo de la placa
free -m
```

---

## Bloc C — Conjunt de pràctica: el número per al README (~20–40 min)

És el pas 4 pendent: confirmar la configuració triada amb el conjunt de pràctica dels organitzadors.

```bash
cd ~/Datathon_FME/projecte
ls -la data/demo.jsonl        # si no hi és: fes servir el zip predict_actual_placa.zip si el tens; si tampoc, salta el bloc i avisa
sudo systemctl stop math-tutor   # si no ho estava ja
```

Dues execucions (cada una ~17 min amb 100 problemes), llançades amb `systemd-run`:

```bash
XDG_RUNTIME_DIR=/run/user/1000 systemd-run --user --unit=demo-debias \
  bash -c 'cd ~/Datathon_FME/projecte && python3 eval.py --input data/demo.jsonl --limit 0 --name demo-debias'
# quan acabi (journalctl --user -u demo-debias -f):
XDG_RUNTIME_DIR=/run/user/1000 systemd-run --user --unit=demo-nodebias \
  bash -c 'cd ~/Datathon_FME/projecte && python3 eval.py --input data/demo.jsonl --limit 0 --debias off --name demo-nodebias'
```

- `demo-debias` és la configuració final (biaix del fitxer, sense RAG): **aquest és el número oficial**.
- `demo-nodebias` és la comparació que demana l'STATUS. Si vas molt just de temps, només la primera.
- Apunta de cada una: encert, temps mitjà i pitjor, i que **cap problema passi de 57 s**. Queden a `results/ablations.csv` (es puja); els CSV per problema no.
- En acabar: `sudo systemctl start math-tutor`.

---

## Bloc D — Configuració final de `predict.py` + prova de reinici (al final de tot, ~10 min)

La versió final decidida: **per defecte** (una lletra, correcció del biaix amb el `letter_bias.json` de la placa, **sense RAG**). No es copia cap fitxer; només es comprova.

Des de `~/Datathon_FME/projecte`:

### D.1 Configuració

```bash
python3 -c "from copilot.config import CONFIG; print(CONFIG['PREDICT_RAG_K'], CONFIG['PREDICT_DEBIAS'])"
ls -la data/letter_bias.json
```

Ha de sortir `0 auto` i el fitxer hi ha de ser.
- Si surt `1 auto`: hi ha una línia `PREDICT_RAG_K=1` afegida al final de `config.env` (mira-ho amb `grep -n PREDICT_RAG_K config.env`). Esborra **només la línia afegida al final** (la base `PREDICT_RAG_K=0` de la part de dalt es queda) i torna a comprovar. Si tens `data/run_predict_rag.sh`, `bash data/run_predict_rag.sh desfer` fa el mateix.
- Si falta `data/letter_bias.json`: **para i avisa la Berta**.

### D.2 Problemes d'exemple

```bash
python3 predict.py --input data/sample_problems.jsonl --output results/check.csv
cat results/check.csv
```

5 files, cadascuna amb una lletra A–E i `ok`.

### D.3 Reinici

```bash
sudo reboot
```

Espera un minut, torna a entrar i:

```bash
systemctl status math-llm math-embed math-tutor --no-pager | grep -E "math-|Active"
last -x | head -5          # el reboot d'ara ha de ser net, no "crash"
free -m
```
Repeteix D.1 i D.2 (guarda el `check.csv` d'abans i de després). L'estat després d'arrencar és el que compta al test final. **Deixa la placa engegada.**

Si els organitzadors et donen el fitxer del test final:
```bash
python3 predict.py --input data/FITXER.jsonl --output results/predict-final.csv
```

---

## Què tornar a la Berta

1. **Bloc A:** caselles de `PROVES_FINALS_PISTES.md` (passos 2–4), `results/tutor-smoke-*.csv`, el `free -m`.
2. **Bloc B:** els dos totals (`vision X/10` i `prior Y/10`), temps per problema, i la confirmació que el servidor de visió està aturat. O el motiu pel qual s'ha saltat.
3. **Bloc C:** les línies noves d'`ablations.csv` (encert i temps de `demo-debias` i `demo-nodebias`).
4. **Bloc D:** la sortida de D.1 i el `results/check.csv` d'abans i de després del reinici, l'estat dels tres serveis i el `last -x`.
5. Qualsevol incident (talls d'USB, reinicis sols, OOM) amb l'hora.

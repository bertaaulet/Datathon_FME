# Dashboard Tukey · "Ensenya el Cangur"

_2026-11-15. Versió per a la presentació, feta a partir del pla del matí i del que va decidir la Berta: mostrar els resultats bons sense presentar com a millora el que és soroll, sense la barra del Cangur, sense servir-lo des de la placa, i amb els experiments de fine-tuning i de models fora de la placa._

## Com es genera

```
cd projecte
python3 dashboard/build.py        # escriu dashboard/dashboard.html
```

- Només llibreria estàndard, i la pàgina és un sol HTML que funciona sense internet.
- Necessita a `results/` (no es pugen mai): els `eval-*.csv` de cada prova a la placa i `tutor-smoke-*.csv`.
- Si en falta algun, la comprovació corresponent surt en vermell al peu de la pàgina.
- Els números de fora de la placa (fine-tuning, models grans, filtre de fuites, Elo) són a `dashboard/facts.json`, cadascun amb on es va mesurar i la seva font.
- L'HTML només porta xifres agregades: cap enunciat, id ni resposta de M3Kang.

## Què hi ha

Té el mateix estil que el tutor de la placa (colors, lletres de LEDs i el dibuix del Cangur, copiats d'`app/index.html`).

1. **Titulars:**
   - La D passa de 73 a 18 de 100.
   - 54 % d'encert quan el model raona (fora de la placa).
   - 0 de 750 respostes a la placa fora de temps.
   - 40 de 40 pistes amb la lletra o la posició, aturades pel filtre.
2. **Registre de decisions:** 10 decisions, adoptades o descartades, amb l'evidència i un enllaç al panell.
3. **El model tenia una lletra preferida?** Barres o *rootogram* de Tukey, abans i després de la correcció.
4. **Què fa que un model encerti?** Encert de cada model (Qwen 0.8B, amb fine-tuning, Gemma 12B, Qwen3 4B raonant) i el temps que trigaria a la placa. És la justificació de fer un tutor (Teach).
5. **Quina configuració enviem, i ens passarem de temps?** Encert amb el marge del 95 % i boxplot dels segons, per conjunt.
6. **El tutor ajuda sense donar la resposta, i a temps?** Filtre de fuites, segons de cada pas i error de l'Elo.
7. **Què hem provat i hem deixat:** RAG, RAG amb lletra, expressió, imatge, fine-tuning i pistes generades.
8. **D'on surten les dades** i 16 comprovacions automàtiques: cada fila d'`ablations.csv` coincideix amb el seu fitxer per problema, els talls sumen el total, i totes les proves són de la placa.

Els intervals i els tests aparellats (McNemar) queden als plegables "Per què aquest gràfic, i el detall". Cap text presenta una diferència dins del soroll com una millora: el 25 % final es presenta "a l'altura del baseline".

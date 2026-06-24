# Installation und Start

## Voraussetzungen

- Python in Version 3.11 oder neuer.
- Die in `pyproject.toml` aufgeführten Pakete (`numpy`, `scipy`, `lmfit`, `npTDMS`,
  `matplotlib`, `pandas`, `openpyxl`); sie werden bei der Installation automatisch
  aufgelöst.
- Für die grafische Oberfläche zusätzlich `PySide6`.

## Installation

Im Projektverzeichnis (`bbFMR/`):

```bash
# virtuelle Umgebung anlegen und aktivieren (empfohlen)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# bbFMR im editierbaren Modus installieren
pip install -e .

# zusätzlich die grafische Oberfläche
pip install -e ".[gui]"

# zusätzlich die Testwerkzeuge
pip install -e ".[test]"
```

!!! note "Editierbarer Modus"
    Bei der Installation mit der Option `-e` verweist die installierte Bibliothek
    direkt auf die Quelldateien des Projekts. Änderungen am Quelltext werden ohne
    erneute Installation wirksam, was die Anpassung der Parameter erleichtert.

## Programmaufruf

### Grafische Oberfläche

```bash
bbfmr
# gleichbedeutend:
python -m bbfmr.app
```

Ist `PySide6` nicht installiert, gibt das Programm einen erläuternden Hinweis samt
Installationsbefehl aus (siehe `bbfmr/app.py`).

### Programmatische Nutzung

Die Auswertung lässt sich auch ohne grafische Oberfläche aus Python heraus
ansteuern. Dies eignet sich für eigene Auswerteskripte und für Tests:

```python
from bbfmr.io.tdms_laden import lade_tdms
from bbfmr.fit.batch import fitte_alle

# 1) Messdatei laden; das Format wird automatisch erkannt
datensatz = lade_tdms("pfad/zur/Messung.tdms")

# 2) vollständige Auswertung: AutoWindow und Fit für alle Frequenzen
stapel = fitte_alle(datensatz)

# 3) Ergebnisse auswerten
for erg in stapel.ergebnisse[:5]:
    print(f"f = {erg.frequenz/1e9:.2f} GHz   B_res = {erg.B_res:.4f} T   "
          f"alpha = {erg.alpha:.2e}   problematisch: {erg.problematisch}")
```

## Tests

```bash
python -m pytest -q
```

Die Testsuite prüft die physikalischen Modelle, das Laden der Daten, den Fit und die
Bewertung. Vor der Weitergabe eigener Änderungen sollten sämtliche Tests fehlerfrei
durchlaufen.

Für die umfassende Robustheitsprüfung über reale Messdateien steht ein gesondertes
Werkzeug bereit; es ist im Kapitel [Robustheits-Harness](test-harness.md)
beschrieben.

# Installation und Start

```bash
pip install -e ".[gui]"     # im geklonten Ordner, Python >= 3.11 (venv empfohlen)
polderfit                   # GUI
```
Tests: `pip install -e ".[test]"` und `python -m pytest -q`.

Skript ohne GUI:

```python
from polderfit.io.tdms_laden import lade_tdms
from polderfit.fit.batch import fitte_alle
from polderfit.auswertung.uebersicht import auswertung_kittel_llg
ds = lade_tdms("Messung.tdms")
stapel = fitte_alle(ds)                       # AutoWindow + Fit + Nachfenster + Bewertung
info = auswertung_kittel_llg(stapel.ergebnisse_aktiv(), geometrie="ip")
```

Name und Version nur in `pyproject.toml`: `[tool.polderfit] name`, `[project] version` → Anzeige `PolderFit V0.1.0` überall.

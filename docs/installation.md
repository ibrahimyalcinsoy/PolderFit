# Installation und Start

```bash
git clone https://github.com/ibrahimyalcinsoy/PolderFit.git && cd PolderFit
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[gui]"        # + ".[test]" für pytest
polderfit                      # GUI;  python -m polderfit.app gleichbedeutend
python -m pytest -q            # Tests
```

Skript ohne GUI:

```python
from polderfit.io.tdms_laden import lade_tdms
from polderfit.fit.batch import fitte_alle
from polderfit.auswertung.uebersicht import auswertung_kittel_llg
ds = lade_tdms("Messung.tdms")
stapel = fitte_alle(ds)                       # AutoWindow + Fit + Nachfenster + Bewertung
info = auswertung_kittel_llg(stapel.ergebnisse_aktiv(), geometrie="ip")
```

Versionssprung: nur `version` in `pyproject.toml` ändern → Name/Titel/Hilfe/Projektdatei folgen.

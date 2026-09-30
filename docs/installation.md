# Installation and start

Windows step by step: [INSTALLATION_WINDOWS.md](https://github.com/ibrahimyalcinsoy/PolderFit/blob/main/INSTALLATION_WINDOWS.md)

```bash
pip install -e ".[gui]"     # in the cloned folder, Python >= 3.11 (venv recommended)
polderfit                   # GUI
pip install -e ".[test]" && python -m pytest -q
```

Keys: `F11` full screen (`Esc` leaves), `Ctrl+Q` quit, `Ctrl+Shift+R` reset window layout. Settings and auto-backup: Windows `%APPDATA%\PolderFit`, Linux `~/.config/polderfit` ([Settings](ausreisser.md)).

Script without GUI:

```python
from polderfit.io.tdms_laden import lade_tdms
from polderfit.fit.batch import fitte_alle
from polderfit.auswertung.uebersicht import auswertung_kittel_llg
ds = lade_tdms("Messung.tdms")
stapel = fitte_alle(ds)                       # AutoWindow + fit + post-window + rating
info = auswertung_kittel_llg(stapel.ergebnisse_aktiv(), geometrie="ip")
```

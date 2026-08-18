# PolderFit – Auswertung breitbandiger FMR-Messungen

Programmname stets mit Version: `PolderFit V<Version>` (Quelle: `version` in `pyproject.toml`; im Code `polderfit.PROGRAMMNAME`).

TDMS-Messdaten (bbFMR) → je Frequenz `B_res`, `µ0ΔH` (±1σ) → Kittel/LLG → `g`, `µ0M_eff`, `µ0H_u`, `α`, `µ0ΔH_0`.
Konvention: Felder als `µ0H` in T; Plots x = Feld, y = Frequenz.

**Dokumentation:** <https://ibrahimyalcinsoy.github.io/PolderFit/> (Quellen in `docs/`, lokal `mkdocs serve`).

## Schnellstart

```bash
git clone https://github.com/ibrahimyalcinsoy/PolderFit.git && cd PolderFit
python -m venv .venv && source .venv/bin/activate     # Windows (cmd): call .venv\Scripts\activate
pip install -e ".[gui]"
polderfit                                             # oder: python -m polderfit.app
```

Aktualisieren: `git pull && pip install -e ".[gui]"`. Windows-Details: [INSTALLATION_WINDOWS.md](INSTALLATION_WINDOWS.md).

```python
from polderfit.io.tdms_laden import lade_tdms
from polderfit.fit.batch import fitte_alle
stapel = fitte_alle(lade_tdms("Messung.tdms"))   # AutoWindow + Fit + Nachfenster + Bewertung
```

## Stolperstellen

- PowerShell „running scripts is disabled“: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` oder `cmd`.
- Debian 12 „Qt platform plugin xcb“: `sudo apt install -y libxcb-cursor0`.

## Struktur

| Verzeichnis | Inhalt |
|---|---|
| `polderfit/io` | TDMS laden, Kanal-Mapping, Datenmodell |
| `polderfit/physik` | Konstanten, Polder-χ, Fitmodell, Kittel/LLG |
| `polderfit/fit` | AutoWindow, Einzelfit, Stapel/Nachfenster, Kriterien, Nachfit-Werkzeuge |
| `polderfit/auswertung`, `polderfit/persistenz` | Kittel/LLG-Plots, Excel/CSV, Projekt-JSON |
| `polderfit/gui` | PySide6-Oberfläche |
| `tests/` | pytest-Suite, Robustheits-Harness (`autowindow_runner.py`) |
| `benchmark_ftf/` | Vergleich mit dem LabVIEW-FTF (`BERICHT.md`) |

Tests: `python -m pytest -q`.

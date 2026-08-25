# PolderFit – Auswertung breitbandiger FMR-Messungen

TDMS-Messdaten (bbFMR) → je Frequenz `B_res`, `µ0ΔH` (±1σ) → Kittel/LLG → `g`, `µ0M_eff`, `µ0H_u`, `α`, `µ0ΔH_0`.
Konvention: Felder als `µ0H` in T; Plots x = Feld, y = Frequenz.

**Dokumentation:** <https://ibrahimyalcinsoy.github.io/PolderFit/>

## Schnellstart

```bash
pip install -e ".[gui]"
polderfit
```

(Im geklonten Ordner, Python ≥ 3.11; empfohlen in einer venv. Windows-Details: [INSTALLATION_WINDOWS.md](INSTALLATION_WINDOWS.md). Vollbild `F11`.)

Fitten direkt nach dem Laden: Auto-Fit (`F5`), Grenzgeraden (`Strg+L`) oder Bereich (`Strg+B`) – jeweils mit Frequenz/Feld von … bis …; Fit-Status in Signalfarben (grün gut, gelb prüfen, rot fehlgeschlagen, grau ignoriert; DIN EN 60073); Linienbreite und Resonanzfeld in T **und mT** im Export; mehrere Resonanzen je Linescan (`n_moden`); Einstellungen speichern/laden; Auto-Sicherung.

## Name und Version

Beides steht nur in `pyproject.toml`: `[tool.polderfit] name = "PolderFit"` und `[project] version = "0.1.0"` → Anzeigename `PolderFit V0.1.0` (Fenstertitel, Hilfe, Projektdatei; im Code `polderfit.PROGRAMMNAME`). Umbenennen oder Versionssprung = diese Zeilen ändern.

## Struktur

| Verzeichnis | Inhalt |
|---|---|
| `polderfit/io` | TDMS laden, Kanal-Mapping, Datenmodell |
| `polderfit/physik` | Konstanten, Polder-χ, Fitmodell, Kittel/LLG |
| `polderfit/fit` | AutoWindow, Einzelfit, Stapel/Nachfenster, Kriterien, Nachfit-Werkzeuge |
| `polderfit/auswertung`, `polderfit/persistenz` | Kittel/LLG-Plots, Excel/CSV, Projekt-JSON |
| `polderfit/gui` | PySide6-Oberfläche (Farben: `farben.py`) |
| `tests/` | pytest-Suite, Robustheits-Harness |
| `benchmark_ftf/` | Vergleich mit dem LabVIEW-FTF (`BERICHT.md`) |

Tests: `python -m pytest -q`.

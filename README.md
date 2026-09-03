# PolderFit

Auswertung breitbandiger FMR-Messungen: TDMS-Messdaten → je Frequenz `B_res`, `µ0ΔH` → Kittel/LLG → `g`, `µ0M_eff`, `µ0H_u`, `α`, `µ0ΔH_0`.

Dokumentation: <https://ibrahimyalcinsoy.github.io/PolderFit/> · Windows Schritt für Schritt (ohne Vorkenntnisse): [INSTALLATION_WINDOWS.md](INSTALLATION_WINDOWS.md)

## Häufig gebraucht: neueste Version holen und starten

Du bist in der Eingabeaufforderung **bereits im Ordner `PolderFit`** (sonst zuerst z. B. `cd %USERPROFILE%\PolderFit`). Dann diese Zeilen kopieren (Strg+C) und einfügen (Strg+V):

```bat
git fetch origin && git reset --hard origin/main && .venv\Scripts\activate && pip install -q -e ".[gui]" && polderfit
```

Nur starten (ohne Update):

```bat
.venv\Scripts\activate && polderfit
```

## Installation unter Windows

Voraussetzungen: [Python ≥ 3.11](https://www.python.org/downloads/windows/) (bei der Installation **„Add python.exe to PATH“** anhaken) und [Git](https://git-scm.com/download/win). Alle Befehle in der **Eingabeaufforderung** (Startmenü → `cmd` → Enter).

### Neu installieren

```bat
cd %USERPROFILE%
git clone https://github.com/ibrahimyalcinsoy/PolderFit.git
cd PolderFit
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[gui]"
polderfit
```

### Vorhandenen Ordner `PolderFit` auf die neueste Version bringen

Es liegt bereits eine ältere Version im Ordner `PolderFit`. In den Ordner wechseln und die Programmdateien durch den neuesten Stand von GitHub ersetzen:

```bat
cd %USERPROFILE%\PolderFit
git fetch origin
git reset --hard origin/main
.venv\Scripts\activate
pip install -e ".[gui]"
polderfit
```

`git reset --hard origin/main` überschreibt **alle Programmdateien** mit der neuesten Version (selbst geänderte Programmdateien gehen verloren). Eigene Dateien im Ordner, die nicht zum Programm gehören (Messdaten, Projekt-JSON), bleiben erhalten.

Liegt der Ordner woanders, den Pfad anpassen (z. B. `cd D:\Messungen\PolderFit`). Meldet `git fetch` einen Fehler („not a git repository“ – Ordner stammt z. B. aus einer ZIP), den alten Ordner umbenennen und neu installieren:

```bat
cd %USERPROFILE%
ren PolderFit PolderFit_alt
git clone https://github.com/ibrahimyalcinsoy/PolderFit.git
```

Danach weiter wie unter „Neu installieren“ ab `cd PolderFit`.

### Starten (jedes weitere Mal)

```bat
cd %USERPROFILE%\PolderFit
.venv\Scripts\activate
polderfit
```

Wird `polderfit` nicht gefunden: `python -m polderfit.app`.

## Installation unter Linux / macOS

```bash
git clone https://github.com/ibrahimyalcinsoy/PolderFit.git && cd PolderFit
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[gui]"
polderfit
```

Aktualisieren (in aktivierter venv): `cd PolderFit && git fetch origin && git reset --hard origin/main && pip install -e ".[gui]"`

## Bedienung in Kürze

TDMS laden → Auto-Fit (`F5`) → bei mehreren Moden je Mode einen Korridor anlegen (`Strg+L`, Panel *Korridore & Zonen*) und „Korridor fitten …“ → Nachfitten im Linescan-Panel oder Bereich (`Strg+B`) → Kittel/LLG-Auswertung je Mode → Export.

## Name und Version

`pyproject.toml`: `[tool.polderfit] name = "PolderFit"` und `[project] version = "0.1.0"`. Die letzte Stelle der angezeigten Version ist die Anzahl der Git-Commits seit der Erstversion (z. B. `PolderFit V0.1.57`) – sie steigt mit jeder Änderung; ohne Git-Checkout (ZIP) erscheint die pyproject-Version.

## Struktur

| Verzeichnis | Inhalt |
|---|---|
| `polderfit/io` | TDMS laden, Kanal-Mapping, Datenmodell |
| `polderfit/physik` | Konstanten, Polder-χ, Fitmodell, Kittel/LLG |
| `polderfit/fit` | AutoWindow, Einzelfit, Stapel/Nachfenster, Kriterien, Nachfit-Werkzeuge |
| `polderfit/auswertung`, `polderfit/persistenz` | Kittel/LLG-Plots, Excel/CSV, Projekt-JSON |
| `polderfit/gui` | PySide6-Oberfläche |
| `tests/` | pytest-Suite (`python -m pytest -q`) |
| `benchmark_ftf/` | Vergleich mit dem LabVIEW-FTF (`einfacher_vergleich_2026-08-25/VERGLEICH_EINFACH.md`, `BERICHT.md`) |

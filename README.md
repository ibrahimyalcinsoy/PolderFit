# PolderFit

**Version 2.0 · Stand 2026-09-04** · Breitband-FMR-Auswertung: TDMS → je Frequenz `B_res`, `µ0ΔH` → Kittel/LLG → `g`, `µ0M_eff`, `µ0H_u`, `α`, `µ0ΔH_0`.
Dokumentation: <https://ibrahimyalcinsoy.github.io/PolderFit/> · Windows Schritt für Schritt: [INSTALLATION_WINDOWS.md](INSTALLATION_WINDOWS.md)

> [!CAUTION]
> **Neueste Version holen und starten** – in der Eingabeaufforderung im Ordner `PolderFit` (sonst zuerst `cd %USERPROFILE%\PolderFit`), Zeile kopieren und einfügen:
>
> ```bat
> git fetch origin && git reset --hard origin/main && .venv\Scripts\activate && pip install -q -e ".[gui]" && polderfit
> ```

Nur starten: `.venv\Scripts\activate && polderfit`

## Erstinstallation (Windows)

Voraussetzungen: [Python ≥ 3.11](https://www.python.org/downloads/windows/) („Add python.exe to PATH“ anhaken) und [Git](https://git-scm.com/download/win). Befehle in der Eingabeaufforderung (`cmd`):

```bat
cd %USERPROFILE%
git clone https://github.com/ibrahimyalcinsoy/PolderFit.git
cd PolderFit
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[gui]"
polderfit
```

Ordner aus einer ZIP („not a git repository“): umbenennen (`ren PolderFit PolderFit_alt`) und neu installieren. `git reset --hard` ersetzt nur Programmdateien; Messdaten und Projekt-JSON bleiben.

Linux/macOS: `git clone … && cd PolderFit && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[gui]" && polderfit`

## Bedienung in Kürze

TDMS laden → Auto-Fit (`F5`; Resonanzen je Fenster, optional Anzahl per BIC) → bei getrennten Moden je Mode ein Korridor (`Strg+L`, Panel *Korridore*; mehrere Dips je Korridor per Summenfit, Trennlinien im Linescan-Panel) → „Korridor fitten …“ → Nachfitten im Linescan-Panel → Kittel/LLG je Mode (`Strg+K`) → Export.

Version: `pyproject.toml` `[project] version` (2.0) + Anzahl Git-Commits als letzte Stelle (z. B. `V2.0.201`).

## Struktur

| Verzeichnis | Inhalt |
|---|---|
| `polderfit/io` | TDMS laden, Kanal-Mapping, Datenmodell |
| `polderfit/physik` | Konstanten, Polder-χ, Fitmodell, Kittel/LLG |
| `polderfit/fit` | AutoWindow, Einzelfit, Stapel/Nachfenster, Kriterien, Korridore, Nachfit-Werkzeuge |
| `polderfit/auswertung`, `polderfit/persistenz` | Kittel/LLG je Mode, Excel/CSV, Projekt-JSON |
| `polderfit/gui` | PySide6-Oberfläche |
| `tests/` | pytest-Suite (`python -m pytest -q`) |
| `benchmark_ftf/` | Vergleich mit dem LabVIEW-FTF (`FTF_AUTOFIT_2026-09-03.md`, `BERICHT.md`, `regression_vergleich.py`) |
| `docs/` | Dokumentation (mkdocs), inkl. `physik-bewertung-2026-09-03.md` |

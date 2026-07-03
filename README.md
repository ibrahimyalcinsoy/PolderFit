# bbFMR – Auswertung breitbandiger FMR-Messungen

bbFMR wertet breitbandige ferromagnetische Resonanzmessungen quantitativ aus: Es liest
die TDMS-Rohdaten ein, bestimmt je Frequenz das Resonanzfenster, passt das komplexe
Transmissionssignal an die Polder-Suszeptibilität an und gewinnt aus `B_res(f)` und der
Linienbreite die Materialgrößen (`μ0Meff`, `g`, Gilbert-Dämpfung `α`).

## Schnellstart

Voraussetzung: Git und Python ≥ 3.11 sind installiert. Block kopieren, ins Terminal
einfügen, Enter — die virtuelle Umgebung (`.venv`) kapselt alles ab.

**Windows** (Eingabeaufforderung `cmd`):

```bat
git clone https://github.com/ibrahimyalcinsoy/bbFMR.git && cd bbFMR
python -m venv .venv && call .venv\Scripts\activate
pip install -e ".[gui]"
bbfmr
```

**Fedora / Debian** (bash):

```bash
git clone https://github.com/ibrahimyalcinsoy/bbFMR.git && cd bbFMR
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[gui]"
bbfmr
```

Schritt-für-Schritt-Anleitung inkl. Git-/Python-Einrichtung:
[INSTALLATION_WINDOWS.md](INSTALLATION_WINDOWS.md).

## Start und Aktualisierung

```bash
bbfmr                 # grafische Oberfläche (in aktivierter .venv)
python -m bbfmr.app   # gleichbedeutend, zur Fehlersuche

git pull                              # auf neueste Version bringen
pip install -e ".[gui]"               # Abhängigkeiten auffrischen
```

Programmatische Nutzung:

```python
from bbfmr.io.tdms_laden import lade_tdms
from bbfmr.fit.batch import fitte_alle

datensatz = lade_tdms("Messung.tdms")   # Format wird automatisch erkannt
stapel = fitte_alle(datensatz)          # AutoWindow + Fit über alle Frequenzen
```

## Bekannte Stolperstellen

- **PowerShell** lehnt die Aktivierung ab (*„running scripts is disabled"*):
  einmalig `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, oder `cmd` nutzen.
- **Debian 12**, Fenster öffnet nicht (*„Qt platform plugin xcb"*):
  `sudo apt install -y libxcb-cursor0`.

## Dokumentation

Vollständige Beschreibung (Aufbau, physikalische Modelle, Parameter, Fehlersuche) im
Verzeichnis `docs/` (ReadTheDocs-Format); HTML-Vorschau mit `mkdocs serve`.

| Kapitel | Inhalt |
|---|---|
| `docs/index.md` | Überblick und Auswertekette |
| `docs/installation.md` | Installation, Start, Tests |
| `docs/datenformate.md` | TDMS-Formate, Datenmodell |
| `docs/pipeline.md` | Laden → AutoWindow → Fit → Bewertung |
| `docs/autowindow.md` | automatische Resonanzbestimmung |
| `docs/physik-und-fit.md` | Suszeptibilität, S21-Modell, Kittel/LLG, Quellen |
| `docs/bewertung.md` | Gütemaße und Problem-Einstufung |
| `docs/tuning.md` | einstellbare Parameter |
| `docs/troubleshooting.md` | typische Fehlerbilder |
| `docs/test-harness.md` | Robustheitsprüfung über reale Messdaten |

## Architektur

```
bbfmr/
  io/          Einlesen/Schreiben TDMS, Datenstruktur (Linescan, Messdatensatz)
  physik/      Konstanten, Polder-Suszeptibilität, Fitmodell, Kittel/LLG
  fit/         AutoWindow, Einzelfit (lmfit), Stapelverarbeitung, Bewertung
  auswertung/  Resonanz vs. f/T, Kittel-/LLG-Fit, Publikationsplots
  persistenz/  Excel/CSV-Export, Sitzungszustand
  gui/         PySide6-Oberfläche mit eingebettetem Matplotlib
  app.py       Einstiegspunkt
```

Die physikalischen Modelle sind zeichengenaue Portierungen verbindlicher Quellen
(Mathematica-Notebook der Polder-Suszeptibilität, Dissertation M. Müller Kap. 2,
Messprotokoll); die Quellenzuordnung steht in `docs/physik-und-fit.md`.

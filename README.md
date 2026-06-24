# bbFMR – Auswertung breitbandiger FMR-Messungen

bbFMR dient der quantitativen Auswertung breitbandiger ferromagnetischer
Resonanzmessungen (bbFMR). Das Programm liest die TDMS-Rohdaten des Messplatzes ein,
bestimmt je Frequenz das Resonanzfenster, passt das komplexe Transmissionssignal an
die Polder-Suszeptibilität an und gewinnt aus der Dispersion `B_res(f)` sowie der
Linienbreite die Materialgrößen (effektive Magnetisierung, g-Faktor, Gilbert-Dämpfung).

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[gui,test]"
```

Kernabhängigkeiten: `numpy`, `scipy`, `lmfit`, `npTDMS`, `matplotlib`, `pandas`,
`openpyxl`; die grafische Oberfläche zusätzlich `PySide6`.

## Start

```bash
bbfmr                 # grafische Oberfläche
python -m bbfmr.app   # gleichbedeutend
```

Programmatische Nutzung:

```python
from bbfmr.io.tdms_laden import lade_tdms
from bbfmr.fit.batch import fitte_alle

datensatz = lade_tdms("Messung.tdms")   # Format wird automatisch erkannt
stapel = fitte_alle(datensatz)          # AutoWindow + Fit über alle Frequenzen
```

## Dokumentation

Die vollständige Beschreibung des Aufbaus, der physikalischen Modelle, der
einstellbaren Parameter und der Fehlersuche befindet sich im Verzeichnis `docs/`
(Format nach Art von ReadTheDocs). Die HTML-Fassung wird mit
[MkDocs](https://www.mkdocs.org/) erzeugt:

```bash
pip install mkdocs && mkdocs serve   # Vorschau unter http://127.0.0.1:8000
```

| Kapitel | Inhalt |
|---|---|
| `docs/index.md` | Überblick und Auswertekette |
| `docs/datenformate.md` | TDMS-Formate (sortiert/unsortiert), Datenmodell |
| `docs/pipeline.md` | Ablauf: Laden → AutoWindow → Fit → Bewertung |
| `docs/autowindow.md` | automatische Resonanzbestimmung |
| `docs/physik-und-fit.md` | Suszeptibilität, S21-Modell, Kittel/LLG, Quellen |
| `docs/bewertung.md` | Gütemaße und Problem-Einstufung |
| `docs/tuning.md` | sämtliche einstellbaren Parameter |
| `docs/troubleshooting.md` | typische Fehlerbilder |

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
Messprotokoll); die Quellenzuordnung ist in `docs/physik-und-fit.md` dokumentiert.

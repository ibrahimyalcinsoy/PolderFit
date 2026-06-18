# Ananas – Breitband-FMR-Auswertung

Python-Portierung der LabVIEW-Auswertung von Breitband-Ferromagnetische-Resonanz-Messungen
(bbFMR). LabVIEW liefert weiterhin die TDMS-Rohdaten; Ananas übernimmt das Einlesen,
das interaktive Zuschneiden, den Fit an die **Polder-Suszeptibilität** sowie die
übergreifende Auswertung (Kittel-/LLG-Fit) und den Export.

## Installation

```bash
git clone https://github.com/ibrahimyalcinsoy/Ananas.git
cd Ananas
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[gui,test]"
```

Kernabhängigkeiten: `numpy`, `scipy`, `lmfit`, `npTDMS`, `matplotlib`, `pandas`,
`openpyxl`; die GUI zusätzlich `PySide6`.

## Start

```bash
ananas            # GUI (Konsolenskript)
python -m ananas.app
```

Ablauf in der GUI:

1. **TDMS laden** – sortiertes oder unsortiertes Format wird automatisch erkannt.
2. **Auto-Fit (alle)** – AutoWindows sucht je Frequenz die Resonanz, schneidet ein Band
   und fittet Real- und Imaginärteil simultan.
3. Je Frequenz die **zwei grünen Grenzlinien** verschieben → der Datensatz wird sofort
   neu gefittet („rumfitten"). `Zurück` / `Weiter` / `Nochmal fitten` /
   `Nächster Problemfit` steuern den iterativen Korrekturlauf.
4. **Kittel/LLG-Auswertung** – Resonanz vs. Frequenz (+ Kittel-Fit, oop/ip wählbar),
   Linienbreite vs. Frequenz (LLG → α, Hinh) und Resonanz vs. Temperatur.
5. **Export** – zugeschnittene Rohdaten + Fitkurven als TDMS, Parameter + Kennzahlen
   als Excel/CSV.

## Architektur

```
ananas/
  io/          Einlesen/Schreiben TDMS, interne Datenstruktur (Linescan, Messdatensatz)
  physik/      Konstanten, Polder-Suszeptibilität, Linescan-Fitmodell, Kittel/LLG
  fit/         AutoWindows, Einzelfit (lmfit), Stapel + Korrekturlauf
  persistenz/  Excel/CSV-Export, Sitzungszustand (JSON)
  auswertung/  Resonanz vs. f/T, Kittel-/LLG-Fit, Publikationsplots
  gui/         PySide6-Oberfläche mit eingebettetem Matplotlib
  app.py       Einstiegspunkt
```

### Datenfluss

TDMS → `Messdatensatz` (Liste von `Linescan`: ein Feldsweep je Frequenz) → GUI-Band-
auswahl → `fitte_linescan` (Polder-Fit) → `StapelErgebnis` → Export + übergreifende
Auswertung.

## Physik / Konventionen

**Einheiten (verbindlich, exakt wie im Mathematica-Notebook):** Felder durchweg als
`µ0H` in **Tesla** (`mu0H0`, `mu0Meff`), `gamma` in rad·s⁻¹·T⁻¹, Vorfaktor `1/(µ0·γ)`.
Keine Mischung H (A/m) ↔ µ0H (T). Die TDMS-Felder liegen bereits in Tesla vor.

**Linescan-Modell** (pro Frequenz, ω = 2πf):

```
S21(B) = A·e^{iφ} · χ_oop(B; B_res, α, ω, γ)  +  (off_re + i·off_im)
         + (slope_re + i·slope_im)·(B − B̄)
```

`χ_oop` ist die komplexe Polder-Suszeptibilität (Real-/Imaginärteil 1:1 aus dem
Notebook), parametrisiert über das Resonanzfeld `B_res` (intern
`µ0Meff = B_res − ω/γ`). Re und Im werden simultan im Least-Squares gefittet
(`lmfit`, Levenberg-Marquardt). Startwerte (AutoWindows) werden datengetrieben
geschätzt – insbesondere die **Phase φ je Frequenz aus Re/Im am Resonanzpunkt**
(verhindert Peak/Dip-Verwechslung und lokale Minima).

**Übergreifend:**

- Kittel oop (Gl. 2.24): `B_res(f) = µ0Meff + 2πf/γ`
- Kittel ip (Gl. 2.25/2.26)
- Linienbreite/LLG (Gl. 2.28): `µ0ΔH = µ0Hinh + 2·(2πf)·α/γ`

## Fit-Güte und Problem-Erkennung

R² ist als Gütemaß **wertlos**, weil die Gesamtvarianz vom konstanten Offset und vom
feldabhängigen Gradienten über das breite Feldfenster dominiert wird (eine fast gerade
Linie erreicht so R² ≈ 1). Primäres Maß ist daher das **normierte Residuum**
`rmse_norm` = RMSE der Residuen relativ zum Signalhub **nach** Offset-/Gradient-Abzug
(getrennt und kombiniert für Re/Im); zusätzlich wird das reduzierte χ² berechnet. R²
bleibt nur sekundär (Export zeigt `1−R²` in wissenschaftlicher Notation).

Alle Schranken und Schwellwerte liegen zentral in `ananas/fit/kriterien.py`. Ein Fit
gilt als **problematisch**, wenn eines zutrifft: (a) normiertes Residuum zu groß,
(b) ein Parameter an/nahe einer Schranke (alpha ∈ [1e-5, 0.1], B_res im Feldfenster,
phi), (c) B_res außerhalb des Fensters, (d) alpha > 0.05 (unphysikalisch),
(e) keine Konvergenz / keine Kovarianz, (f) δB_res/B_res zu groß. Die GUI zeigt den
konkreten Grund in der Statuszeile und springt per „Nächster Problemfit" gezielt dorthin.
Beispiel (Roh-File): von 1001 Fits werden ~75 markiert (v. a. tiefe Frequenzen < 3,5 GHz
ohne Resonanz im Fenster); die guten Fits behalten alpha ≈ 1e-3 … 1e-2.

## Gespeicherte Größen

Pro Frequenz: `B_res` (H_res), `µ0ΔH`, Vorfaktor `A`, Phase `φ`, Offsets (Re/Im),
Slopes (Re/Im), `R²`, Temperatur sowie alle Unsicherheiten. Global: `µ0Meff`, g-Faktor/γ,
α, `µ0Hinh` (Kittel/LLG) mit Unsicherheiten. Plots **und** zugrundeliegende Daten werden
ausgegeben (extern reproduzierbar).

## Tests

```bash
QT_QPA_PLATFORM=offscreen MPLBACKEND=Agg pytest -q
```

Abgedeckt: Physik (χ-Resonanzlage, Kittel/LLG-Rückgewinnung), Fit (synthetische
Wahrheit mit/ohne Rauschen), IO (beide TDMS-Formate, Schreiben), End-to-End-Pipeline
inkl. Export. Die Integrationstests verwenden die Beispieldateien in `TDMS files/`
(werden übersprungen, falls nicht vorhanden).

## Validierung an den Beispieldaten

Sortiertes und unsortiertes File liefern konsistent **µ0Meff ≈ 2.382 T, g ≈ 2.08,
α ≈ 2·10⁻³** (oop, −5 K) – die Kittel-Dispersion ist über 5–50 GHz exakt linear.

## Offene Punkte (mit J. Weber abzustimmen)

1. Bedeutung der Fehlercodes „15" / „15/1/2".
2. Sortierkriterium Rohfile → sorted (Resonanzband-Auswahl).
3. Genaue LabVIEW-Solver-Variante.
4. g-Faktor/γ fest vorgeben oder mitfitten.
5. Umfang Messrechner-Zugriff (nur Lesen vs. Steuerung).
6. Umfang funktionaler Erweiterungen über die Portierung hinaus.
7. A-Startwert-Strategie bestätigen.

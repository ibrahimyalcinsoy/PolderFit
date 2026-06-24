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
   neu gefittet („rumfitten"). Das Fit-Panel zoomt dafür automatisch auf das
   Resonanzband (Schalter **„Vollbereich"** zeigt wieder den ganzen Feldsweep); die
   Grenzlinien sind deutlich hervorgehoben (weißer Halo, schattiertes Band, Greifpunkte
   am oberen Rand, Hover-Highlight + Resize-Cursor). `Zurück` / `Weiter` /
   `Nochmal fitten` / `Nächster Problemfit` steuern den iterativen Korrekturlauf.
4. **Kittel/LLG-Auswertung** – Resonanz vs. Frequenz (+ Kittel-Fit, oop/ip wählbar),
   Linienbreite vs. Frequenz (LLG → α, Hinh) und Resonanz vs. Temperatur.
5. **Export** – zugeschnittene Rohdaten + Fitkurven als TDMS, Parameter + Kennzahlen
   als Excel/CSV.

Lang laufende Schritte (Laden großer Dateien, Auto-Fit über alle Frequenzen) laufen in
einem Hintergrund-Thread, sodass die Oberfläche bedienbar bleibt. Ein andockbares,
abtrennbares **Aktivitäts-Panel** zeigt einen Fortschrittsbalken und ein farbiges
Live-Protokoll (jeder Fit mit B_res/α, Problemfits markiert) – die App wirkt nie
„eingefroren", auch wenn sie länger rechnet.

## Dokumentation

Eine ausführliche Dokumentation des Aufbaus, der physikalischen Modelle, der
einstellbaren Parameter (Tuning) sowie zur Fehlersuche befindet sich im Verzeichnis
`docs/` (Format nach Art von ReadTheDocs). Die HTML-Fassung lässt sich mit
[MkDocs](https://www.mkdocs.org/) erzeugen:

```bash
pip install mkdocs
mkdocs serve      # lokale Vorschau unter http://127.0.0.1:8000
mkdocs build      # statisches HTML nach site/
```

Einstieg: `docs/index.md`. Das Kapitel `docs/autowindow.md` beschreibt die
automatische Resonanzbestimmung, `docs/tuning.md` sämtliche Stellschrauben,
`docs/troubleshooting.md` typische Fehlerbilder.

## Architektur

```
ananas/
  io/          Einlesen/Schreiben TDMS, interne Datenstruktur (Linescan, Messdatensatz)
  physik/      Konstanten, Polder-Suszeptibilität, Linescan-Fitmodell, Kittel/LLG
  fit/         AutoWindows, Einzelfit (lmfit), Stapel + Korrekturlauf
  persistenz/  Excel/CSV-Export, Sitzungszustand (JSON)
  auswertung/  Resonanz vs. f/T, Kittel-/LLG-Fit, Publikationsplots
  gui/         PySide6-Oberfläche mit eingebettetem Matplotlib (Hintergrund-Worker,
               Aktivitäts-Panel, helles Stylesheet, App-Icon)
  app.py       Einstiegspunkt
```

### Datenfluss

TDMS → `Messdatensatz` (Liste von `Linescan`: ein Feldsweep je Frequenz) → GUI-Band-
auswahl → `fitte_linescan` (Polder-Fit) → `StapelErgebnis` → Export + übergreifende
Auswertung.

## Funktionsweise im Detail – Physik, Formeln und Implementierung

Dieser Abschnitt erklärt zusammenhängend, *was* gefittet wird, *welche* Formeln
dahinterstehen und *wie* sie im Code umgesetzt sind. Wer die Physik der FMR kennt,
soll danach den Code lesen und nachvollziehen können.

Die Implementierung ist keine freie Neuformulierung, sondern eine zeichengenaue
Portierung dreier verbindlicher Quellen, die alle in `Dokumente/` liegen. Die
geschlossenen Ausdrücke der Polder-Suszeptibilität χ′ und χ″ (out-of-plane und
in-plane) stammen aus dem Mathematica-Notebook
`Chi_Fit_Functions_and_Inductances_2020-04-06.nb` (exportierte `InputForm`,
Z. 1306–1530) und stehen in `ananas/physik/suszeptibilitaet.py`. Das Protokoll
`Protokoll_FMR_Python_2026-05-08.docx` legt die Anforderungen, das TDMS-Format und
mit der inversen Suszeptibilität (Weiler, Gl. 2.7) die *Herkunft* dieser
Fitfunktionen fest. Die übergreifenden Modelle – Kittel-Dispersion Gl. (2.24)/(2.26),
Linienbreite Gl. (2.27)/(2.28) und die zugrunde liegende
Landau-Lifshitz-Gilbert-Gleichung (LLG) – kommen aus Kapitel 2 der Dissertation von
M. Müller (`Mueller_Kap2_text.txt`, vollständig
`Mueller_Manuel_Doktorarbeit_2023.pdf`) und sind in `ananas/physik/kittel_llg.py`
umgesetzt. Den physikalischen Hintergrund des Suszeptibilitätstensors χ̂ₚ liefert die
Originalarbeit von D. Polder, *Phil. Mag.* 40 (1949)
(`1-s2.0-0031891449900518-main.pdf`).

Verbindlich für alle Module ist eine einheitliche Einheiten-Konvention: Magnetfelder
werden durchgehend als **µ₀H in Tesla** geführt (`mu0H0` für das äußere Feld,
`mu0Meff` für die effektive Magnetisierung, `B_res` für das Resonanzfeld), das
gyromagnetische Verhältnis `gamma` in **rad·s⁻¹·T⁻¹**, Frequenzen in Hz und
ω = 2πf in rad·s⁻¹. H (in A/m) wird nie mit µ₀H (in T) gemischt – laut Protokoll die
wahrscheinlichste Fehlerquelle; die TDMS-Felder (`IPS X-Field` bzw. `Field-before`)
liegen ohnehin bereits in Tesla vor. γ und g-Faktor hängen über γ = g·µ_B/ℏ zusammen
(`ananas/physik/konstanten.py`), für g = 2 ist γ ≈ 1.7588·10¹¹ rad·s⁻¹·T⁻¹.

### Die gemessene Größe: komplexes S21 pro Frequenz

Die bbFMR-Messung liefert für jede feste Mikrowellenfrequenz f einen Feldsweep, also
den komplexen Transmissionsparameter S21(B) = Re + i·Im über das äußere Feld
B = µ₀H. Ein solcher Sweep heißt im Code **Linescan** (`ananas/io/datensatz.py`),
der gesamte Messsatz – im Beispiel 725 Frequenzen × 1001 Feldpunkte – ist ein
`Messdatensatz`. Das unsortierte Rohformat wird beim Einlesen per Reshape 725×1001
zerlegt; dass das korrekt ist, bestätigt Protokoll §3.1, und jeder Feldwert ist
bit-identisch zum bereits sortierten File.

### Die Polder-Suszeptibilität als Linienformmodell

Die Magnetisierungsdynamik wird durch die LLG-Gleichung beschrieben; ihre
Linearisierung um die Gleichgewichtslage liefert den Polder-Suszeptibilitätstensor
χ̂ₚ (Polder 1949). Dessen relevante Komponente ist eine komplexe, vom Feld abhängige
Resonanzfunktion mit dispersivem Realteil χ′ und absorptivem Imaginärteil χ″. Für die
out-of-plane-Geometrie (oop) lauten die Ausdrücke mit dem gemeinsamen Nenner N und
dem Feldabstand d = µ₀H₀ − µ₀M_eff (`chi_oop_komponenten` in
`ananas/physik/suszeptibilitaet.py`):

```
N    = γ⁴·d⁴ + 2·(α²−1)·γ²·d²·ω² + (1+α²)²·ω⁴
χ′  =  γ²·µ₀·d · ( γ²·d² + (α²−1)·ω² ) / N
χ″ = −α·γ·µ₀·ω · ( γ²·d² + (1+α²)·ω² ) / N
```

Diese Zeilen sind 1:1 aus dem Mathematica-Notebook übernommen (Form χ/M_s), und die
Variablennamen im Code spiegeln die Notebook-Konvention wider. Physikalisch ist χ″
eine durch α leicht verzerrte Lorentz-Kurve und χ′ deren dispersive Ableitungsform –
genau das Peak/Dip-Paar, das man in Real- und Imaginärteil einer FMR-Linie sieht. Die
Resonanz liegt bei d = ω/γ, also µ₀H₀ − µ₀M_eff = ω/γ. Zur Absicherung wurde das
Modell numerisch gegen die Inversion der inversen Suszeptibilität (Weiler Gl. 2.7 aus
dem Protokoll) geprüft: χ_oop ist bis auf ~10⁻¹² identisch mit der χ_yy-Komponente von
(χ̂⁻¹)⁻¹, wobei der Vorfaktor 1/(µ₀·γ) korrekt erhalten bleibt.

Die in-plane-Variante (`chi_ip_komponenten`, Konfiguration „H ∥ y, senkrecht zum CPW,
ohne `ratio`") ist ebenfalls implementiert, aber noch nicht in den Linescan-Fit
verdrahtet: Der Einzelfit nutzt derzeit immer `chi_oop`, und das oop/ip-Umschalten
greift nur in der übergreifenden Kittel/LLG-Auswertung auf bereits extrahierte B_res.
Der Grund ist physikalisch – die ip-Resonanz liegt nicht einfach bei d = ω/γ, sondern
an der ip-Kittel-Bedingung, und bräuchte daher einen eigenen, über B_res
parametrisierten Wrapper. Die Beispielmessung ist ohnehin oop.

Im Fit ist nicht M_eff die handliche Größe, sondern das ablesbare Resonanzfeld B_res,
das im Feldfenster liegt. Deshalb setzt `chi_oop` intern µ₀M_eff = B_res − ω/γ,
sodass die Resonanz exakt bei µ₀H = B_res zu liegen kommt. Das entkoppelt den
Linescan-Fit sauber vom erst später angefitteten Kittel-Zusammenhang und erlaubt die
harte Schranke, dass B_res innerhalb des ausgeschnittenen Feldfensters liegen muss.

### Das vollständige Linescan-Fitmodell

Die rohe Suszeptibilität ist nicht direkt S21 – Messkette und Hintergrund kommen
hinzu. Das tatsächlich gefittete komplexe Modell (`s21_modell` in
`ananas/physik/fitmodell.py`) lautet pro Frequenz (ω = 2πf fest):

```
S21(B) = A·e^{iφ} · χ_oop(B; B_res, α, ω, γ)
         + (off_re + i·off_im)                      ← konstanter Offset
         + (slope_re + i·slope_im)·(B − B̄)          ← linearer Hintergrund
```

Es hat acht freie Parameter. Der komplexe Vorfaktor A·e^{iφ} trägt einerseits den
großen absoluten Maßstab von χ (inklusive µ₀ und M_s), andererseits die
frequenzabhängige Drehung zwischen χ und der gemessenen S21-Ebene; gerade die Phase φ
beschreibt das Umkippen zwischen „Peak" und „Dip" über die Frequenz. `off_re/off_im`
bilden den konstanten komplexen Offset der Messkette ab, `slope_re/slope_im` einen
linearen, feldabhängigen Hintergrund (Drift über das breite Fenster), der auf die
Bandmitte B̄ (`B_ref`) referenziert wird, damit Offset und Steigung entkoppeln. Die
physikalisch interessanten Größen, die Gilbert-Dämpfung α und das Resonanzfeld B_res,
stecken in χ_oop. Real- und Imaginärteil werden simultan gefittet: Das Residuum
(`fitmodell.residuum`) stapelt sie zu einem reellen Vektor `[Δ.real, Δ.imag]`, sodass
ein einziger Least-Squares beide Kanäle gemeinsam minimiert – sie teilen dieselben
physikalischen Parameter und dürfen nicht getrennt gefittet werden. Als Solver dient
`lmfit` mit Levenberg-Marquardt (`method="leastsq"`, `ananas/fit/linescan_fit.py`).

### Startwerte und AutoWindows

Ein Acht-Parameter-Fit mit Peak/Dip-Mehrdeutigkeit landet ohne gute Startwerte leicht
in lokalen Minima, deshalb leitet `schaetze_startwerte` (`fitmodell.py`) sie
datengetrieben ab. Zunächst wird der Hintergrund linear aus je rund 15 % der Punkte an
den Bandrändern geschätzt (`np.linalg.lstsq`) und ergibt `off_*` und `slope_*`; davon
wird das Signal bereinigt. Das Resonanzfeld B_res ist dann das Feld des größten
Betragsausschlags dieses bereinigten Signals (Peak oder Dip). Die Phase φ wird je
Frequenz aus dem komplexen Winkel des bereinigten Signals am Resonanzpunkt bestimmt,
φ ≈ arg(Signal) + π/2, weil χ″ dort näherungsweise −i ist – das ist der entscheidende
Kniff gegen die Peak/Dip-Verwechslung, denn φ wird gerade *nicht* global festgenagelt.
Die Dämpfung α folgt aus der Halbwertsbreite (FWHM) der bereinigten Magnitude (siehe
unten), und die Amplitude A wird auf die tatsächliche χ-Skala umgerechnet, damit
A·|χ| ungefähr der gemessenen Amplitude entspricht (χ trägt große Vorfaktoren in
sich).

Welcher Feldausschnitt überhaupt in den Fit eingeht, bestimmt **AutoWindows**
(`ananas/fit/autowindows.py`): Es sucht je Frequenz die Resonanz und legt ein
symmetrisches Feldfenster der Breite `breite_faktor`·µ₀ΔH (standardmäßig das Achtfache
der Linienbreite) um B_res, begrenzt auf den gemessenen Bereich. Dieses Fenster
schneidet `schneide_band` aus, und nur die Punkte im Band gehen in den Fit ein. In der
GUI sind die zwei Grenzlinien je Frequenz manuell verschiebbar, und jede Verschiebung
löst sofort einen neuen Fit aus.

Eine subtile, aber wichtige numerische Besonderheit (zugleich ein behobener Fehler)
steckt im α-Startwert: Gleichung (2.27) definiert die Linienbreite µ₀ΔH als FWHM der
Absorption χ″, nicht der Magnitude |χ|. Für die oop-Lorentzform gilt χ″ ∝ 1/(1+x²)
und fällt damit bei x = ±1 auf die Hälfte, während |χ| ∝ 1/√(1+x²) erst bei x = ±√3
auf die Hälfte fällt. Die im Code aus der Magnitude gemessene FWHM ist daher um den
Faktor √3 zu breit. Mit µ₀ΔH = 2·ω·α/γ ergibt sich der korrekte Startwert zu

```
α = γ · FWHM_Magnitude / (2 · √3 · ω)
```

Das betrifft nur Startwert und Fensterbreite; die auskonvergierten Werte bleiben davon
unberührt (abgesichert durch `test_startwert_alpha_aus_magnituden_fwhm`). Zusätzlich
wird α auf den plausiblen Bereich [10⁻⁵, 0.1] begrenzt.

### Übergreifende Auswertung: Kittel und LLG

Aus den pro Frequenz extrahierten B_res(f) und µ₀ΔH(f) werden schließlich die
Materialgrößen gewonnen (`ananas/physik/kittel_llg.py`, mit
`scipy.optimize.curve_fit`); alle Formeln stammen aus Müller Kap. 2. Die
out-of-plane-Kittel-Dispersion, Gl. (2.24), ist eine Gerade in f,
B_res(f) = µ₀M_eff + 2πf/γ, deren Fit µ₀M_eff sowie – optional festgehalten – γ bzw.
den g-Faktor liefert. In-plane gilt nach Gl. (2.25/2.26)
B_res(f) = √[(2πf/γ)² + (µ₀M_eff/2)²] − µ₀M_eff/2 − µ₀H_u. Die inhomogen verbreiterte
Linienbreite nach Gl. (2.28), µ₀ΔH(f) = µ₀H_inh + 2·(2πf)·α/γ, ist wieder eine Gerade:
ihre Steigung ergibt die Gilbert-Dämpfung α, ihr Achsenabschnitt die inhomogene
Verbreiterung µ₀H_inh; der homogene Spezialfall H_inh = 0 ist Gl. (2.27). γ wird hier
in der Regel aus dem Kittel-Fit übernommen. Zur Validierung: An beiden Beispieldateien
(sortiert und unsortiert, oop) ergeben sich konsistent µ₀M_eff ≈ 2.382 T, g ≈ 2.08 und
α ≈ 2·10⁻³ bei exakt linearer Kittel-Dispersion über 5–50 GHz (R² ≈ 0.99999).

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

# bbFMR – Auswertung breitbandiger FMR-Messungen

bbFMR dient der quantitativen Auswertung breitbandiger ferromagnetischer
Resonanzmessungen (bbFMR). Die vorliegende Dokumentation beschreibt den Aufbau des
Programms, die zugrunde liegenden physikalischen Modelle, die Bedeutung der
einstellbaren Parameter sowie das Vorgehen zur Fehlersuche. Sie richtet sich an
Anwenderinnen und Anwender, die den Auswerteweg nachvollziehen, das Programm an
eigene Messreihen anpassen oder Auffälligkeiten diagnostizieren möchten.

## Gegenstand der Auswertung

Bei einer FMR-Messung wird eine magnetische Probe einem äußeren Magnetfeld
ausgesetzt und mit Mikrowellen variabler Frequenz durchstrahlt. Bei einer
materialspezifischen Kombination aus Anregungsfrequenz und Magnetfeld absorbiert die
Probe resonant Energie. Aus der Lage des Resonanzfeldes als Funktion der Frequenz,
`B_res(f)`, sowie aus der frequenzabhängigen Linienbreite lassen sich die effektive
Magnetisierung `μ0Meff`, der Landé-Faktor `g` und die Gilbert-Dämpfung `α`
bestimmen.

Die Eingangsdaten liegen als TDMS-Dateien des Messprogramms vor; bbFMR überführt
sie in physikalische Kenngrößen, Diagramme und tabellarische Exporte.

!!! note "Begriffe"
    - **Linescan**: ein Feld-Sweep bei fester Anregungsfrequenz. Das komplexe
      Transmissionssignal `S21` wird als Funktion des Magnetfeldes erfasst.
    - **`S21`**: komplexer Streuparameter (Real- und Imaginärteil) des Durchgangs.
    - **Resonanzfeld `B_res`**: Magnetfeld, bei dem die Resonanzbedingung erfüllt ist.
    - **Fenster (window)**: der Feldausschnitt um die Resonanz, der in den Fit eingeht.
    - **Fit**: nichtlineare Anpassung der Modellfunktion an die Messpunkte.

## Aufbau der Auswertekette

Die Auswertung erfolgt in einer festen Abfolge von Verarbeitungsschritten. Jeder
Schritt ist einem Modul zugeordnet:

```
   TDMS-Datei
       │   bbfmr/io/tdms_laden.py
       ▼
  [1] Laden und Formaterkennung
       │   Ergebnis: Liste von Linescans (ein Feld-Sweep je Frequenz)
       ▼
  [2] AutoWindow                  bbfmr/fit/autowindows.py
       │   Bestimmung des Resonanzfeldes und des Fitfensters je Frequenz
       ▼
  [3] Beschneiden
       │   Reduktion des Linescans auf das Fenster
       ▼
  [4] Einzel-Fit                  bbfmr/fit/linescan_fit.py
       │   Anpassung der Suszeptibilitäts-Modellfunktion → B_res, α, …
       ▼
  [5] Bewertung                   bbfmr/fit/kriterien.py
       │   Einstufung des Fits als vertrauenswürdig oder problematisch
       ▼
  [6] Kittel- / LLG-Auswertung    bbfmr/physik/kittel_llg.py
       │   aus B_res(f) und Linienbreite(f): μ0Meff, g, α
       ▼
   Ergebnisse, Diagramme, Excel-Export
```

Die Schritte 2 bis 5 werden je Linescan, also je Frequenz, ausgeführt; die Schritte
1 und 6 operieren auf dem gesamten Datensatz. Schritt 2 (AutoWindow) ist für die
Zuverlässigkeit der Auswertung am kritischsten und wird in einem
[eigenen Kapitel](autowindow.md) ausführlich behandelt.

## Modulübersicht

| Aufgabe | Modul |
|---|---|
| Laden der TDMS-Daten, Formaterkennung | `bbfmr/io/tdms_laden.py` |
| interne Datenstruktur | `bbfmr/io/datensatz.py` |
| Bestimmung der Resonanzfenster (AutoWindow) | `bbfmr/fit/autowindows.py` |
| Einzel-Fit eines Linescans | `bbfmr/fit/linescan_fit.py` |
| Bewertungskriterien und Schwellwerte | `bbfmr/fit/kriterien.py` |
| Stapelverarbeitung aller Linescans | `bbfmr/fit/batch.py` |
| Suszeptibilität und S21-Modell | `bbfmr/physik/suszeptibilitaet.py`, `bbfmr/physik/fitmodell.py` |
| Kittel- und Linienbreiten-Auswertung | `bbfmr/physik/kittel_llg.py` |
| physikalische Konstanten | `bbfmr/physik/konstanten.py` |
| grafische Oberfläche | `bbfmr/gui/` |
| Export (Excel, Projektdateien) | `bbfmr/persistenz/` |
| Robustheitsprüfung über reale Daten | `tests/autowindow_runner.py` |

## Leitfaden

Für einen Einstieg empfiehlt sich die Reihenfolge [Installation und
Start](installation.md), [Messdaten](datenformate.md) und [Ablauf der
Auswertung](pipeline.md). Das Kapitel [AutoWindow im Detail](autowindow.md)
erläutert die Resonanzbestimmung; die physikalischen Modelle sind unter [Physik und
Fit](physik-und-fit.md) zusammengefasst. Sämtliche einstellbaren Parameter sind im
Kapitel [Tuning](tuning.md) gebündelt, typische Fehlerbilder im Kapitel
[Troubleshooting](troubleshooting.md).

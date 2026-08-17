# Ablauf der Auswertung

Dieses Kapitel beschreibt den Datenfluss von der geladenen Messung bis zum
bewerteten Fitergebnis. Die zentrale Steuerung übernimmt die Funktion `fitte_alle`
in `polderfit/fit/batch.py`.

## Stapelverarbeitung: `fitte_alle`

```python
def fitte_alle(datensatz, gamma=GAMMA_STANDARD, breite_faktor=8.0,
               r2_schwelle=0.9, fortschritt=None, zentren=None,
               auswahl=None, alpha_erwartet=0.01,
               alpha_max=ALPHA_MAX, nachfenster_faktor=2.5) -> StapelErgebnis:
```

Der Ablauf gliedert sich in zwei Phasen (plus einen optionalen Nachfit):

1. **Globale Fensterbestimmung.** Für den gesamten Datensatz werden die
   Resonanzfenster ermittelt. Standardmäßig geschieht dies durch `auto_fenster_alle`
   (siehe [AutoWindow im Detail](autowindow.md)). Werden über das Argument `zentren`
   vorgegebene Fenstermitten `B_res(f)` übergeben, so wird stattdessen
   `fenster_aus_trasse` verwendet und die automatische Detektion übersprungen.

2. **Einzel-Fit je Frequenz.** Für jeden Linescan wird das Signal auf das zugehörige
   Fenster beschnitten (`schneide_band`) und anschließend angepasst
   (`fitte_linescan`). Jedes Ergebnis wird unmittelbar nach dem Fit bewertet.

```python
fenster = auto_fenster_alle(datensatz, gamma, breite_faktor)   # Phase 1
for i, ls in enumerate(datensatz.linescans):                   # Phase 2
    ergebnis, beschnitten, verwendet = fitte_mit_nachfenster(
        ls, fenster[i], gamma, alpha_max=alpha_max,
        nachfenster_faktor=nachfenster_faktor)
    # verwendet = ggf. auf B_res ± faktor*dH verengtes Fenster (2. Durchgang)
```

**Zweiter Durchgang (`nachfenster_faktor`, Standard 2.5):** Nach dem Fit auf dem
breiten Detektionsfenster wird einmal auf `B_res ± faktor·µ₀ΔH` (aus dem ersten
Ergebnis) nachgefittet; das Ergebnis wird nur übernommen, wenn der Nachfit
erfolgreich und nicht problematisch ist. Das Fenster wird dabei nie erweitert und
enthält mindestens 12 Messpunkte. Hintergrund: Auf sehr breiten Fenstern passt der
lineare Untergrund bei strukturiertem Hintergrund nicht mehr, und µ₀ΔH fällt
systematisch zu klein aus (Benchmark gegen das LabVIEW-FTF, `benchmark_ftf/`).
`nachfenster_faktor=0` schaltet den Durchgang ab. `alpha_max` ist die harte
obere α-Schranke der Einzelfits (Standard 0.1).

Das Resultat ist ein `StapelErgebnis` mit den Listen `fenster` (Bandgrenzen),
`zugeschnitten` (beschnittene Linescans) und `ergebnisse` (Fitergebnisse je
Frequenz).

## Die einzelnen Schritte

### Beschneiden des Bandes

`schneide_band(linescan, feld_unten, feld_oben)` liefert einen neuen Linescan, der
auf das Intervall `[feld_unten, feld_oben]` reduziert ist. Enthält das Fenster
weniger als vier Messpunkte, wird der ungekürzte Linescan beibehalten, um einen
nicht bestimmbaren Fit zu vermeiden.

### Einzel-Fit

`fitte_linescan` passt die Suszeptibilitäts-Modellfunktion simultan an Real- und
Imaginärteil von `S21` an. Verfahren und Modell sind unter [Physik und
Fit](physik-und-fit.md) beschrieben. Die Startwerte werden datengetrieben geschätzt
(`schaetze_startwerte`), sofern sie nicht explizit vorgegeben werden. Es gilt die
verbindliche Randbedingung, dass das Resonanzfeld `B_res` innerhalb des
ausgeschnittenen Fensters liegen muss.

### Bewertung

Jedes Fitergebnis wird durch `bewerte_fit` (`polderfit/fit/kriterien.py`) als
unauffällig oder problematisch eingestuft. Die zugrunde liegenden Kriterien und
Schwellwerte sind im Kapitel [Bewertung der Fits](bewertung.md) dargestellt.

## Nachträgliches Anpassen einzelner Frequenzen

Erweist sich ein einzelner Fit als unbefriedigend, lässt er sich mit veränderten
Bandgrenzen, expliziten Startwerten oder vorgegebenem Resonanzfeld erneut
durchführen, ohne den übrigen Datensatz neu zu berechnen:

```python
from polderfit.fit.batch import fitte_neu

neues = fitte_neu(stapel, index=42,
                  feld_unten=2.55, feld_oben=2.75,   # engeres Fenster
                  B_res_vorgabe=2.64)                # Resonanzfeld vorgeben
```

Das Ergebnis ist als nachbearbeitet markiert (`nachbearbeitet=True`) und ersetzt den
betreffenden Eintrag im `StapelErgebnis`.

## Auswahl problematischer Frequenzen

`StapelErgebnis` stellt Hilfsfunktionen zur Übersicht bereit:

```python
stapel.index_problematisch()   # Indizes aller als problematisch eingestuften Fits
stapel.problem_statistik()     # Häufigkeit der einzelnen Problemgründe
```

Die Einstufung stützt sich auf die Mehrkriterien-Bewertung aus
`polderfit/fit/kriterien.py` und nicht auf das Bestimmtheitsmaß `R²`, das in diesem
Anwendungsfall als Gütemaß ungeeignet ist (siehe [Bewertung der Fits](bewertung.md)).

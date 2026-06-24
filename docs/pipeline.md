# Ablauf der Auswertung

Dieses Kapitel beschreibt den Datenfluss von der geladenen Messung bis zum
bewerteten Fitergebnis. Die zentrale Steuerung übernimmt die Funktion `fitte_alle`
in `ananas/fit/batch.py`.

## Stapelverarbeitung: `fitte_alle`

```python
def fitte_alle(datensatz, gamma=GAMMA_STANDARD, breite_faktor=8.0,
               r2_schwelle=0.9, fortschritt=None, zentren=None) -> StapelErgebnis:
```

Der Ablauf gliedert sich in zwei Phasen:

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
    unten, oben = fenster[i]
    beschnitten = schneide_band(ls, unten, oben)
    ergebnis = fitte_linescan(beschnitten, gamma)
    # Ergebnis und beschnittener Linescan werden im StapelErgebnis abgelegt
```

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

Jedes Fitergebnis wird durch `bewerte_fit` (`ananas/fit/kriterien.py`) als
unauffällig oder problematisch eingestuft. Die zugrunde liegenden Kriterien und
Schwellwerte sind im Kapitel [Bewertung der Fits](bewertung.md) dargestellt.

## Nachträgliches Anpassen einzelner Frequenzen

Erweist sich ein einzelner Fit als unbefriedigend, lässt er sich mit veränderten
Bandgrenzen, expliziten Startwerten oder vorgegebenem Resonanzfeld erneut
durchführen, ohne den übrigen Datensatz neu zu berechnen:

```python
from ananas.fit.batch import fitte_neu

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
`ananas/fit/kriterien.py` und nicht auf das Bestimmtheitsmaß `R²`, das in diesem
Anwendungsfall als Gütemaß ungeeignet ist (siehe [Bewertung der Fits](bewertung.md)).

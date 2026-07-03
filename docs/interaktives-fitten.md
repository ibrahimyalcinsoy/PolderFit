# Interaktives Fitten im Farbplot

Dieses Kapitel bündelt die Werkzeuge, mit denen man Fits **direkt in der
2D-Übersicht** korrigiert. Es wächst mit den interaktiven Funktionen des
Programms; Grundlage ist das Modul `bbfmr/fit/fenster_steuerung.py`.

## Bereich neu fitten (Rechteck)

**Wofür?** Mehrdeutigkeiten auflösen: Liegen zwei ähnlich starke Signale im
Feldsweep — die echte Mode auf der Kittel-Geraden und eine physikalisch
uninteressante Zweitmode oder Störung daneben — kann sich der Auto-Fit am
falschen Signal festhalten. Man sieht das im Resonanz-Overlay als Punkte, die
neben der Geraden liegen.

**Bedienung:**

1. Toolbar → **„Bereich neu fitten"** (erst nach einem Auto-Fit sinnvoll —
   der Bereichs-Fit überschreibt gezielt bestehende Fits).
2. Im Farbplot ein **Rechteck um die Mode aufziehen** (der Mauszeiger wird
   zum Fadenkreuz; `Esc` bricht ab). Das Rechteck zoomt in diesem Modus
   nicht, es definiert den Fit-Bereich.
3. Für alle Frequenzen im Rechteck laufen Fenstersuche **und** Fit erneut —
   beschränkt auf den markierten Feldbereich. `B_res` kann das Rechteck
   nicht verlassen (Fit-Schranken = Fenster ⊆ Rechteck).

**Garantien:**

* Ergebnisse **außerhalb** des Rechtecks bleiben unangetastet.
* Neu gefittete Ergebnisse sind als `nachbearbeitet` markiert.
* Frequenzen mit weniger als 4 Messpunkten im Rechteck werden übersprungen
  (Protokoll zeigt „… ohne Daten im Rechteck").
* Der Vorgang ist beliebig **iterierbar**: anderes Rechteck, anderer
  Teilbereich, bis alle Punkte auf der Mode liegen.

**Skript-Nutzung:**

```python
from bbfmr.fit import fitte_alle, fitte_bereich

stapel = fitte_alle(datensatz)
neu, uebersprungen = fitte_bereich(
    stapel,
    feld_min=0.55, feld_max=1.30,       # Tesla
    frequenz_min=8e9, frequenz_max=18e9,  # Hz
)
```

## Grenzen im Linescan ziehen (Bestandsfunktion)

Unabhängig vom Rechteck lassen sich im rechten Fit-Panel die **grünen
Bandgrenzen** einzelner Linescans mit der Maus verschieben — der Fit läuft
sofort mit den neuen Grenzen. Zusammen mit *Zurück/Weiter/Nächster
Problemfit* ist das der Korrekturlauf für Einzelfälle; das Rechteck ist das
Werkzeug für ganze Bereiche.

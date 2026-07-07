# Interaktives Fitten im Farbplot

Dieses Kapitel bündelt die Werkzeuge, mit denen man Fits **direkt in der
2D-Übersicht** korrigiert. Es wächst mit den interaktiven Funktionen des
Programms; Grundlage ist das Modul `polderfit/fit/fenster_steuerung.py`.

## Bereich neu fitten (Rechteck)

Zweck: Mehrdeutigkeiten auflösen. Liegen zwei ähnlich starke Signale im Feldsweep
(die echte Mode auf der Kittel-Geraden und eine physikalisch uninteressante
Zweitmode oder Störung daneben), kann der Auto-Fit auf das falsche Signal treffen.
Im Resonanz-Overlay erscheint das als Punkte abseits der Geraden.

Bedienung:

1. Menü *Fit → Bereich neu fitten* (auch in der Werkzeugleiste; erst nach einem
   Auto-Fit sinnvoll, da der Bereichsfit bestehende Fits gezielt überschreibt).
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
from polderfit.fit import fitte_alle, fitte_bereich

stapel = fitte_alle(datensatz)
neu, uebersprungen = fitte_bereich(
    stapel,
    feld_min=0.55, feld_max=1.30,       # Tesla
    frequenz_min=8e9, frequenz_max=18e9,  # Hz
)
```

## Ziehbare Fenstergrenzen im Farbplot (mitwandernd)

Panel „Fenster & Grenzen" (Menü *Ansicht → Panel: Fenster & Grenzen*) → Häkchen
„Grenzen im Farbplot anzeigen & ziehen": Über dem Farbplot erscheinen zwei
Polylinien, die linke (orange) und rechte (blaue) Fenstergrenze, je Frequenz durch
die aktuellen Fit-Fenster gelegt. Nur der Bereich dazwischen geht in den Fit ein.

* Ziehen: Grenze mit der Maus anfassen (Cursor wird zum Horizontal-Pfeil) und
  seitlich verschieben; der betroffene Linescan wird neu gefittet, Overlay und
  Fit-Panel aktualisieren sich unmittelbar.
* Mitwandern statt feste Lage: Grenzen werden intern nicht als feste Feldwerte oder
  Punktindizes geführt, sondern als Offsets relativ zur Dispersions-Trasse, einer
  robusten Ausgleichsgeraden B(f) durch die guten Fits (`dispersions_zentren`). Bei
  der Übernahme auf andere Frequenzen folgt das Fenster damit der Resonanz-Geraden.
* **Propagation:** „Grenzen des aktuellen Linescans auf folgende übernehmen"
  wendet die Offsets der gerade gesetzten Grenzen auf alle folgenden
  Linescans an (Klick) — oder automatisch nach jedem Ziehen (Häkchen
  „automatisch übernehmen").

## Überschreiben oder Ergänzen (Modus)

Der **Modus** im Panel gilt für Propagation, Fensterbreite-Anwenden und den
Bereichs-Fit:

* **überschreiben** — alle betroffenen Fits werden ersetzt.
* **ergänzen** — nur die als *problematisch* markierten Fits werden neu
  gefittet; bereits gute Ergebnisse anderer Bereiche bleiben unangetastet.

Der Bereichsfit überschreibt nur den gewählten Ausschnitt: Bereich vorgeben, neu
fitten, prüfen, nächsten Bereich wählen. Bereits gute Fits außerhalb bleiben erhalten.

## Fensterbreite explizit in Punkten

„Fensterbreite explizit setzen": z. B. von 15 auf **25 Punkte** stellen und
„Auf alle anwenden" — jedes Fenster wird zu *Trassen-Zentrum ± Breite/2 in
Feldpunkten des jeweiligen Linescans* gesetzt und neu gefittet. Das ist der
direkte Hebel gegen die Fehlerbilder „Grenzen zu eng gesetzt" und
„Resonanzfenster generell zu eng"; die Automatik ändert diese Vorgabe nicht
selbsttätig. Das Panel zeigt zur Kontrolle die tatsächliche Breite des aktuellen
Fensters in Punkten an.

## Ausschlusszonen (Bereich aus der Auswertung nehmen)

„Zone im Farbplot einzeichnen" → Rechteck um die störenden Punkte aufziehen
(z. B. den zur Feldachse parallelen Abschnitt unten im Plot). Die Punkte in
der Zone werden aus **allen** (Nach-)Fits ausgenommen; betroffene Linescans
fitten sofort neu. Zonen werden schraffiert angezeigt, sind in der Liste des
Panels einsehbar und einzeln entfernbar (die betroffenen Linescans fitten dann
wieder mit allen Punkten). Ein neuer Auto-Fit beginnt mit leerer Zonenliste.

## Multi-Monitor-Betrieb

Das Linescan-Fit-Panel und alle weiteren Panels (Fenster & Grenzen, Verarbeitung,
Aktivität, Navigator) sind abdockbar: Titelleiste des Panels ziehen und auf den
zweiten Monitor legen. Der Farbplot bleibt das zentrale Fenster. Über das Menü
*Ansicht* lässt sich jedes Panel ein- und ausblenden.

## Typische Korrektur-Workflows (bekannte Fehlerbilder)

| Fehlerbild | Werkzeug |
|---|---|
| Grenzen zu eng (R²-Kriterium schneidet den halben Dip weg) | Fensterbreite in Punkten erhöhen → „Auf alle anwenden" |
| Doppel-Dip, Grenzen nur halb gesetzt | Grenzen im Farbplot beidseitig ziehen, dann propagieren |
| Resonanzfenster generell zu eng | Fensterbreite-Hebel oder Grenzen ziehen + „automatisch übernehmen" |
| „Problemfit" (Fit ok gemeldet, physikalisch falsch) | Rechteck-Bereichs-Fit im Modus *überschreiben*, Störbereiche als Ausschlusszone |

## Grenzen im Linescan ziehen (Bestandsfunktion)

Unabhängig davon lassen sich im Linescan-Fit-Panel die **grünen
Bandgrenzen** des einzelnen Linescans mit der Maus verschieben — der Fit
läuft sofort mit den neuen Grenzen. Zusammen mit *Zurück/Weiter/Nächster
Problemfit* ist das der Korrekturlauf für Einzelfälle; Rechteck, Grenzlinien
und Propagation sind die Werkzeuge für ganze Bereiche.

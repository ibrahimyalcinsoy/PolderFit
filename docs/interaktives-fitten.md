# Interaktives Fitten im Farbplot

Dieses Kapitel bündelt die Werkzeuge, mit denen man Fits **direkt in der
2D-Übersicht** korrigiert. Grundlage ist das Modul
`polderfit/fit/fenster_steuerung.py`.

## Interaktionsmodi: exklusiv, sichtbar, jederzeit abbrechbar

Alle interaktiven Modi des Farbplots — *Resonanz vorgeben*, *Bereich neu
fitten*, *Ausschlusszone einzeichnen*, *Ausreißer markieren* — laufen über
einen zentralen Modus-Manager:

* Es ist immer **höchstens ein Modus aktiv**; das Starten eines Modus beendet
  den vorherigen automatisch.
* Der aktive Modus ist **eindeutig sichtbar**: der zugehörige Umschalter ist
  farblich markiert (Menü/„Funktionen"-Dropdown), und rechts in der
  Statusleiste erscheint eine Modus-Anzeige mit Abbruch-Hinweis.
* **`Esc` bricht jeden Modus ab** — unabhängig davon, welches Bedienelement
  gerade den Tastaturfokus hat.
* Ein neuer Datensatz oder ein startender Hintergrund-Job beendet aktive
  Modi ebenfalls.

## Fenstersuche mit Stationär-Abzug (warum der Bereichs-Fit die Mode trifft)

Die Fenstersuche aller Nachfit-Werkzeuge (Rechteck und Grenzgeraden) nutzt
denselben Mechanismus wie der Auto-Fit: Die Residuen werden auf den **vollen**
Linescans gebildet und um den **feld-stationären Untergrund** bereinigt
(Median über die Frequenzachse je Feldpunkt). Senkrechte Störstreifen im
Farbplot — stehende Wellen bei festen Feldwerten, die nicht mit der Frequenz
wandern — fallen dabei heraus; übrig bleibt die wandernde Resonanz. Erst
danach wird der Kandidat **innerhalb** des erlaubten Feldbereichs gesucht,
gestützt durch eine glatte lokale Dispersions-Trasse über die betroffenen
Frequenzen. (Früher suchte der Bereichs-Fit je Linescan isoliert im
Ausschnitt — dort dominierte der Störstreifen, und die Fenster schnappten
auf den Streifen statt auf die Mode.)

## Nachfitten: drei Wege

Zum Neu-Fitten von Teilbereichen gibt es **drei** Werkzeuge:

### 1. Bereich neu fitten (Rechteck, `Strg+B`)

Zweck: Mehrdeutigkeiten auflösen. Liegen zwei ähnlich starke Signale im Feldsweep
(die echte Mode auf der Kittel-Geraden und eine physikalisch uninteressante
Zweitmode oder Störung daneben), kann der Auto-Fit auf das falsche Signal treffen.
Im Resonanz-Overlay erscheint das als Punkte abseits der Geraden.

Bedienung:

1. Menü *Fit → Bereich neu fitten* (`Strg+B`; erst nach einem Auto-Fit
   sinnvoll, da der Bereichsfit bestehende Fits gezielt überschreibt).
2. Im Farbplot ein **Rechteck um die Mode aufziehen** (Fadenkreuz-Cursor;
   `Esc` bricht ab). Das Rechteck zoomt in diesem Modus nicht, es definiert
   den Fit-Bereich.
3. Im anschließenden **Optionen-Dialog** wählen:
   * **Modus** — *überschreiben* (alle Fits im Rechteck ersetzen) oder
     *ergänzen* (nur die als problematisch markierten; gute Fits bleiben).
   * **Fensterbreite fest** (optional) — erzwingt eine feste Breite in
     Feldpunkten um das gefundene Fensterzentrum. Das ist der direkte Hebel
     gegen die Fehlerbilder „Grenzen zu eng gesetzt" und „Resonanzfenster
     generell zu eng"; die Automatik ändert diese Vorgabe nicht selbsttätig.
4. Für alle Frequenzen im Rechteck laufen Fenstersuche **und** Fit erneut —
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
    feld_min=0.55, feld_max=1.30,        # Tesla
    frequenz_min=8e9, frequenz_max=18e9,  # Hz
    modus="ueberschreiben",
    breite_punkte=25,                     # optional: feste Fensterbreite
)
```

### 2. Grenzgeraden (freier Bereich, wie eine Linie in Word)

Panel *Zonen & Grenzgeraden* → **„Gerade einzeichnen (2 Klicks)"**:

1. Zwei Punkte im Farbplot klicken → die (unendliche) Gerade erscheint mit
   zwei **Handgriffen** an den geklickten Punkten. Handgriff ziehen =
   verschieben/rotieren, wie eine eingefügte Linie in einem Textprogramm.
2. Die Seiten sind farblich markiert: **grüner Saum = wird neu gefittet**,
   **roter Saum = wird ignoriert**. **Doppelklick auf die Linie** (oder der
   Panel-Knopf „Seite wechseln") tauscht die Seiten.
3. Mit **zwei Geraden** entsteht ein Band (Schnitt der grünen Seiten) — z. B.
   zwei parallele Geraden entlang der Mode, um nur diesen Schlauch neu zu
   fitten und alles daneben zu ignorieren.
4. **„Grünen Bereich neu fitten …"** öffnet denselben Optionen-Dialog wie der
   Rechteck-Fit (Modus, feste Fensterbreite) und fittet je Frequenz nur im
   erlaubten Feldintervall neu; Frequenzen ganz auf der roten Seite bleiben
   unangetastet.

Skript-Nutzung:

```python
from polderfit.fit import Grenzgerade, fitte_geraden_bereich

geraden = [
    Grenzgerade(b1=2.76, f1=40.5e9, b2=2.85, f2=43.8e9, gruen_positiv=True),
    Grenzgerade(b1=2.84, f1=40.5e9, b2=2.93, f2=43.8e9, gruen_positiv=False),
]
neu, uebersprungen = fitte_geraden_bereich(stapel, geraden)
```

### 3. Grenzen im Linescan ziehen (Einzelfrequenz)

Im Linescan-Fit-Panel lassen sich die **grünen Bandgrenzen** des einzelnen
Linescans mit der Maus verschieben — der Fit läuft sofort mit den neuen
Grenzen. Zusammen mit *Zurück/Weiter/Nochmal fitten/Nächster Problemfit* ist
das der Korrekturlauf für Einzelfälle; das Rechteck ist das Werkzeug für
ganze Bereiche.

> Frühere Einzelwerkzeuge (ziehbare Grenz-Polylinien im Farbplot, separate
> Propagation, „Breite auf alle anwenden") sind bewusst entfallen bzw. als
> Optionen im Bereichs-Fit-Dialog aufgegangen — weniger redundante Wege,
> keine konkurrierenden Modi. Die Kernfunktionen
> (`propagiere_grenzen`, `setze_fensterbreite_punkte`) stehen im Skriptbetrieb
> weiterhin zur Verfügung.

## Ausschlusszonen (Bereich aus der Auswertung nehmen)

Panel *Zonen & Grenzgeraden* (Menü *Ansicht → Panel: Zonen & Grenzgeraden*):
„Zone im Farbplot einzeichnen" (Umschalt-Knopf, zeigt den aktiven Modus) →
Rechteck um die störenden Punkte aufziehen (z. B. den zur Feldachse parallelen
Abschnitt unten im Plot). Die Punkte in der Zone werden aus **allen**
(Nach-)Fits ausgenommen; betroffene Linescans fitten sofort neu. Zonen werden
schraffiert angezeigt, sind in der Liste des Panels einsehbar und einzeln
entfernbar (die betroffenen Linescans fitten dann wieder mit allen Punkten).
Ein neuer Auto-Fit beginnt mit leerer Zonenliste.

## Multi-Monitor-Betrieb

Das Linescan-Fit-Panel und alle weiteren Panels (Ausschlusszonen, Verarbeitung,
Aktivität, Navigator) sind abdockbar: Titelleiste des Panels ziehen und auf den
zweiten Monitor legen. Der Farbplot bleibt das zentrale Fenster und startet in
voller Breite (alle Panels erscheinen erst bei Bedarf). Über das Menü
*Ansicht* bzw. das „Funktionen"-Dropdown lässt sich jedes Panel ein- und
ausblenden.

## Typische Korrektur-Workflows (bekannte Fehlerbilder)

| Fehlerbild | Werkzeug |
|---|---|
| Grenzen zu eng (R²-Kriterium schneidet den halben Dip weg) | Bereichs-Fit mit Option „Fensterbreite fest" (z. B. 25 Punkte) |
| Doppel-Dip, Fenster sitzt auf dem falschen Signal | Rechteck eng um die echte Mode aufziehen |
| Resonanzfenster generell zu eng | Rechteck über den ganzen Frequenzbereich + „Fensterbreite fest" |
| „Problemfit" (Fit ok gemeldet, physikalisch falsch) | Bereichs-Fit im Modus *überschreiben*, Störbereiche als Ausschlusszone |
| Einzelner Fit daneben | Grüne Grenzen im Linescan-Panel ziehen |

# AutoWindow im Detail

Das AutoWindow bestimmt für jeden Linescan automatisch das Feldfenster, das in den
Fit eingeht. Es ist der für die Robustheit der Auswertung kritischste Schritt: Sitzt
das Fenster falsch, liefert der Fit physikalisch unbrauchbare Werte, ohne dass das
Programm zwingend einen Fehler meldet. Die Implementierung befindet sich in
`bbfmr/fit/autowindows.py`.

## Problemstellung

Die Resonanz ist häufig nur eine schmale, schwache Struktur auf einem starken, über
den breiten Feld-Sweep gekrümmten Untergrund. Erschwerend kommen drei Effekte hinzu,
die in realen Messreihen regelmäßig auftreten:

- **Resonanz nur bei starken Feldern.** Bei tiefen Frequenzen liegt das Resonanzfeld
  unter Umständen außerhalb des gemessenen Feldbereichs; in diesen Linescans ist
  keine Resonanz vorhanden.
- **Feldstationäre Störfeatures.** Periodische Untergrund-Ripples (etwa bei
  Gitter-Proben) sowie apparative Artefakte erscheinen bei festen Feldwerten über
  nahezu alle Frequenzen hinweg.
- **Messrauschen.** Wie bei jeder physikalischen Messung sind die Messwerte mit
  kleinen Störungen behaftet.

Eine naive Suche nach dem stärksten Signal je Linescan verirrt sich an diesen
Störungen. Das AutoWindow nutzt daher mehrere ineinandergreifende Schritte.

## Physikalische Grundlage: glatte, wandernde Dispersion

Die echte Resonanz **wandert** mit der Frequenz gemäß der Kittel-Dispersion (siehe
[Physik und Fit](physik-und-fit.md)). Das Resonanzfeld `B_res(f)` ist eine glatte,
monoton steigende Funktion der Frequenz. Feldstationäre Störfeatures hingegen sitzen
bei **festen** Feldwerten. Diese Unterscheidung – wandernd gegenüber stationär – ist
das zentrale Kriterium, mit dem das AutoWindow die echte Resonanz von Störungen
trennt.

## Verfahren

Die Bestimmung erfolgt in der Funktion `auto_fenster_alle` in fünf Schritten.

### Schritt 1 – Untergrundabzug je Linescan

Für jeden Linescan wird ein glattes Polynom an Real- und Imaginärteil von `S21`
angepasst und abgezogen (`_detrend_residuum`). Der Polynomgrad ist an die Feldbreite
gekoppelt (etwa ein Grad je 0,5 T, begrenzt auf 2 bis 6). Übrig bleibt das Residuum
`|S21 − Untergrund|`, in dem die Resonanz als lokale Abweichung hervortritt. Ein rein
linearer Untergrundabzug genügt nicht, da das größte Residuum dann an der stärksten
Krümmung des Untergrunds läge, nicht an der Resonanz.

### Schritt 2 – Abzug des feldstationären Untergrunds

Liegt ein gemeinsames Feldgitter vor – dies ist bei unsortierten Daten der Fall, da
jeder Linescan dieselbe Feldachse besitzt –, wird zusätzlich der feldstationäre
Anteil entfernt (`_stationaeren_untergrund_abziehen`):

```
stationaer[B] = Median über alle Frequenzen des Residuums bei Feld B
bereinigt[f, B] = max(0,  Residuum[f, B] − stationaer[B])
```

Da die Resonanz mit der Frequenz wandert, trägt sie bei einem festen Feldwert `B`
nur für wenige Frequenzen bei; der Median über die Frequenzachse schätzt somit den
stationären Untergrund. Nach dessen Abzug verbleibt im Wesentlichen die wandernde
Resonanz. Auf einem repräsentativen Gitter-Datensatz steigt der Anteil korrekt
detektierter Einzelresonanzen durch diesen Schritt von etwa 87 % auf 95 %.

### Schritt 3 – Lokaler Resonanzkandidat

Aus dem bereinigten Residuum wird je Linescan der Ort des Maximums als
Resonanzkandidat `B_res` bestimmt, zusammen mit einer robusten Prominenz in
Einheiten der medianabsoluten Abweichung (`_kandidat`). Die Prominenz quantifiziert,
wie deutlich sich der Kandidat vom lokalen Untergrund abhebt; sie dient als Maß für
die Verlässlichkeit der Einzeldetektion.

### Schritt 4 – Glatte lokale Trasse

Über die **prominenten** Kandidaten wird eine glatte Trasse `B_res(f)` gelegt
(`_glatte_lokale_trasse`). Verwendet wird eine **gleitende robuste Gerade**: in einem
um jede Frequenz zentrierten Fenster wird eine Gerade an die prominenten Kandidaten
angepasst (mit einer Ausreißerverwerfung über die medianabsolute Abweichung) und der
Wert an der betreffenden Frequenz vorhergesagt.

Die gleitende Gerade folgt der lokalen Steigung der Dispersion und damit auch einer
rasch mit der Frequenz wandernden Resonanz; zugleich unterdrückt sie einzelne
Ausreißer-Kandidaten, die in einem Linescan auf ein Störfeature gesprungen sind.

!!! note "Warum keine globale Polynomanpassung"
    Ein einzelnes Polynom niedrigen Grades über den gesamten Frequenzbereich ist
    anfällig gegen Hebelpunkte: Fehldetektionen bei tiefen Frequenzen ohne Resonanz
    (Feldstationäre Artefakte am Feldrand) verbiegen die Anpassung global und
    verschieben die Fenstermitte auch dort, wo die Einzeldetektion korrekt war. Die
    gleitende Gerade ist gegen diesen Effekt unempfindlich. Eine globale Trasse wird
    nur noch als Rückfallebene verwendet, falls zu wenige prominente Kandidaten für
    eine lokale Anpassung vorliegen.

### Schritt 5 – Fenstermitte und Fensterbreite

Je Linescan wird die Fenstermitte wie folgt festgelegt:

- Ist der lokale Kandidat **prominent und mit der glatten Trasse konsistent** (sein
  Abstand zur Trasse unterschreitet eine Toleranz), so wird ihm vertraut. Die
  Einzeldetektion ist nach dem Stationärabzug genauer als jede Glättung.
- Andernfalls (Ausreißer-Kandidat oder schwacher Linescan) wird die Fenstermitte an
  der glatten Trasse ausgerichtet und auf einen nahegelegenen Residuum-Peak
  verfeinert (`_verfeinere_zentrum`). Der begrenzte Suchradius verhindert ein
  Abspringen auf weiter entfernte Störfeatures.

Die Fensterbreite ist an die lokale Halbwertsbreite des Residuum-Peaks gekoppelt
(`_fenster_um`), nach unten durch den Punktabstand und nach oben durch `_HALB_MAX`
(0,4 T) begrenzt. Letzteres schützt gegen Ausreißer der Linienbreiten-Schätzung bei
schwachen oder verrauschten Resonanzen.

## Vorgabe der Dispersion durch die Anwendung

Bleibt die Automatik an einem festen Störfeature hängen, kann die Resonanz-Dispersion
manuell vorgegeben werden (`fenster_aus_trasse`). In der grafischen Oberfläche
geschieht dies über zwei Klicks in der Übersicht, aus denen eine Kittel-Gerade
abgeleitet wird; die Fenster folgen dann dieser Vorgabe mit eng an die erwartete
Linienbreite gekoppelter Breite.

## Einzel-Linescan-Variante

Für die Bestimmung eines Fensters aus einem einzelnen Linescan ohne globale Trasse
steht `auto_fenster` bereit. Für ganze Datensätze ist `auto_fenster_alle` vorzuziehen,
da nur dort die globale Information über die Dispersion und der Stationärabzug
genutzt werden.

## Grenzen des Verfahrens

In bestimmten Datenklassen ist in den Rohdaten keine Resonanz zuverlässig
lokalisierbar; das Verfahren kann dann kein korrektes Fenster liefern. Dies betrifft
insbesondere:

- Messungen nahe der In-plane-Geometrie mit sehr schwachem Signal,
- antiferromagnetische Proben (z. B. CrSBr), deren Resonanz nicht der Kittel-Form
  folgt,
- Datensätze mit dominanten, stationären Hochfeld-Artefakten.

Solche Fälle werden in der Robustheitsprüfung offen ausgewiesen (siehe
[Robustheits-Harness](test-harness.md)). Eine Diskussion der einstellbaren Parameter
des AutoWindow findet sich im Kapitel [Tuning](tuning.md).

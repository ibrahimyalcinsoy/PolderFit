# Troubleshooting

Dieses Kapitel ordnet typischen Fehlerbildern ihre Ursache und ein Vorgehen zu. Die
beschriebenen Fälle stammen aus der Robustheitsprüfung über den realen Datenbestand
(siehe [Robustheits-Harness](test-harness.md)).

## Laden schlägt fehl: „Punktzahl … nicht durch Feldanzahl … teilbar"

**Ursache.** Die Datei wurde mitten in der Messung auf die Platte geschrieben
(Dateiname mit `_flush`); der letzte Feld-Sweep ist unvollständig.

**Vorgehen.** Aktuelle Programmstände behandeln diesen Fall automatisch: Die
Sweep-Länge wird aus der Frequenzachse abgeleitet, auf die vollständigen Sweeps
gekürzt und regulär ausgewertet (`ananas/io/tdms_laden.py`). Tritt der Fehler
dennoch auf, lässt sich die Sweep-Periode nicht bestimmen; in diesem Fall ist die
Datei vermutlich beschädigt.

## Laden schlägt fehl: „Unbekanntes TDMS-Format" {#nicht_fmr}

**Ursache.** Die Datei enthält weder die Gruppe `Read.PNAX` noch `ZVB`. Häufig
handelt es sich um ein anderes Messverfahren – etwa Winkel-Sweeps bei festem Feld
(Gruppe `Read.ZNA`) – oder um abgebrochene Dateien, die nur Konfigurationsdaten und
keine Messdaten enthalten.

**Vorgehen.** Solche Dateien sind keine Feld-FMR-Linescans und werden bewusst
zurückgewiesen. Es ist zu prüfen, ob die richtige Datei vorliegt. Winkel-Sweeps sind
mit dieser Auswertung nicht zu bearbeiten.

## Auswertung bricht nicht ab, dauert aber sehr lange {#timeout}

**Ursache.** Sehr hochauflösende Feld-Sweeps (mehrere tausend Feldpunkte je
Linescan) führen zu langen Fit-Rechenzeiten. Das AutoWindow selbst ist davon kaum
betroffen; die Rechenzeit entsteht im Fit über alle Frequenzen.

**Vorgehen.** Die Robustheitsprüfung bricht solche Dateien nach einer harten
Zeitgrenze (90 s je Datei) kontrolliert ab und protokolliert sie als Timeout. Für die
reguläre Auswertung einzelner Dateien ist mehr Zeit einzuplanen; gegebenenfalls
empfiehlt sich eine Reduktion der Punktzahl bereits bei der Messung.

## Der Fit ist gut, aber das Fenster sitzt sichtbar falsch

**Ursache.** Das AutoWindow ist an einem feldstationären Störfeature oder, bei sehr
schwachem Signal, an Rauschen hängengeblieben. Der Fit erreicht dann auf dem falschen
Ausschnitt ein kleines Residuum, ohne die eigentliche Resonanz zu erfassen.

**Vorgehen.**
1. Die Dispersion manuell vorgeben: in der grafischen Oberfläche durch zwei Klicks in
   der Übersicht, programmatisch über das Argument `zentren` von `fitte_alle`
   beziehungsweise `fenster_aus_trasse`.
2. Einzelne Frequenzen mit engeren Bandgrenzen über `fitte_neu` nachfitten.
3. Bei verrauschten Daten `_PROMINENZ_MIN` erhöhen (siehe [Tuning](tuning.md)).

## Sehr viele Linescans werden als problematisch gemeldet

**Mögliche Ursachen.**

- **In-plane-Messung mit Out-of-plane-Modell.** Der Einzel-Fit verwendet `χ_oop`. Bei
  In-plane-Geometrie passt das Modell nicht, die Dämpfung läuft an die obere Schranke
  (`alpha unphysikalisch`, `alpha an Grenze`). Die Meldungen sind in diesem Fall
  sachgerecht.
- **Keine Resonanz im Feldbereich.** Bei tiefen Frequenzen liegt das Resonanzfeld
  unter Umständen außerhalb des gemessenen Bereichs; ein Fit ist dann nicht sinnvoll
  und wird zu Recht als problematisch eingestuft.

**Vorgehen.** Die Problemgründe je Linescan prüfen (`erg.problem_text`,
`stapel.problem_statistik()`). Treten überwiegend physikalisch erwartbare Gründe auf,
liegt kein Programmfehler vor.

## Die Resonanz wird nur bei hohen Feldern erwartet, das Fenster sucht zu tief

**Ursache.** Bei tiefen Frequenzen ohne Resonanz erzeugen feldstationäre Artefakte am
unteren Feldrand mitunter scheinbare Kandidaten.

**Vorgehen.** Der feldstationäre Untergrundabzug und die gleitende Trasse mindern
diesen Effekt bereits (siehe [AutoWindow im Detail](autowindow.md)). Verbleibt das
Problem, ist die Dispersion manuell vorzugeben; die Trasse folgt dann der erwarteten,
mit der Frequenz steigenden Resonanzlage.

## Grundsätzliche Diagnose

Zur systematischen Untersuchung über viele Dateien hinweg dient das
[Robustheits-Harness](test-harness.md). Es erzeugt zu auffälligen Linescans
Diagnose-Diagramme (Signal, gewähltes Fenster und – sofern vorhanden – das
Referenzband der sortierten Variante), anhand derer sich Fehlplatzierungen visuell
prüfen lassen.

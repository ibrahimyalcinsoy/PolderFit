# Ausreißer-Management und Projektdateien

## Zweck

Einzelne physikalisch sinnlose Fit-Punkte (in der Minderheit, etwa ein Fit auf einem
Störsignal) verfälschen den linearen Kittel-Fit erheblich, bis hin zu negativer
Steigung. Solche Punkte müssen sich schnell und reversibel aus der Auswertung nehmen
lassen.

## Bedienung

1. Menü *Fit → Ausreißer markieren* (`Strg+M`, Umschalter, auch im
   „Funktionen"-Dropdown; erst nach einem Auto-Fit). Das Ausreißer-Panel
   (rechts) erscheint automatisch. Der aktive Modus ist farblich markiert und
   wird rechts in der Statusleiste angezeigt.
2. Im Farbplot: Punkt anklicken (nächstgelegener sichtbarer Fit-Punkt) oder Kasten
   aufziehen (alle Punkte darin). Markierte Punkte werden aus der Darstellung und aus
   allen übergreifenden Rechnungen entfernt: Kittel-/LLG-Fit, Publikationsplots und
   Globalparameter des Excel-Exports; im Excel-/CSV-Export sind sie in der
   Spalte `ausreisser` gekennzeichnet. Der Modus bleibt aktiv, bis er erneut
   ausgelöst oder mit `Esc` beendet wird; der Kasten-Zoom ist währenddessen
   ausgesetzt. Das Starten eines anderen Modus (z. B. Bereichs-Fit) beendet
   den Ausreißer-Modus automatisch.
3. Alternativ direkt im **Kittel/LLG-Auswertungsfenster** (`Strg+K`): dort
   Punkte im Dispersions- oder Linienbreiten-Plot anklicken bzw. einrahmen —
   gleiche Ausreißer-Liste, der Kittel-/LLG-Fit rechnet sofort neu.
4. **Ausreißer-Panel**: Liste aller ausgeschlossenen Punkte (Index, Frequenz,
   B_res) — einsehbar und editierbar:
   * *Wieder aufnehmen* (Auswahl) / *Alle wieder aufnehmen*
   * *Rückgängig* — macht den jeweils letzten Schritt rückgängig
     (Markieren wie Wiederaufnehmen, bis zu 50 Schritte).

Die Einzelfits selbst bleiben unangetastet — ein Ausreißer-Ausschluss ist
eine reine Auswertungsentscheidung und jederzeit reversibel.

## Projekt speichern / laden

Menü *Datei → Projekt speichern* sichert den kompletten Auswertungszustand als JSON
(Format-Version 2, `polderfit/persistenz/projekt.py`):

* TDMS-Quelle, **Kanal-Zuordnung** und Mapping-Profilname,
* Auswertungsauswahl (Jumper/Bereiche),
* γ, R²-Schwelle, **Fenstergrenzen je Frequenz**,
* **Ausschlusszonen** und **Ausreißer-Markierungen**,
* alle Fitparameter (zur Kontrolle/Archivierung).

*Datei → Projekt laden* stellt die Sitzung wieder her: Die TDMS-Datei wird über
die gespeicherte Zuordnung neu gelesen (Rohdaten werden nie dupliziert),
gegebenenfalls identisch reduziert, und alle Fits werden mit den
gespeicherten Fenstern **deterministisch neu gerechnet** — anschließend sind
Fenster, Zonen, Ausreißer und Bearbeitungsstand wieder exakt da, wo die
Sitzung endete. Ist die Quelle nicht am gespeicherten Pfad (anderer Rechner),
fragt das Programm nach dem Speicherort.

```python
from polderfit.persistenz import speichere_sitzung, lade_sitzung, stelle_stapel_wieder_her
from polderfit.io import lade_tdms

speichere_sitzung(stapel, "sitzung.json")

daten = lade_sitzung("sitzung.json")
zuordnung = {rolle: tuple(paar) for rolle, paar in daten["zuordnung"].items()}
ds = lade_tdms(daten["quelle"], zuordnung=zuordnung, layout=daten["format_typ"])
stapel = stelle_stapel_wieder_her(daten, ds)
stapel.ausreisser            # [4, 17, ...]
stapel.ergebnisse_aktiv()    # Eingabe fuer Kittel/LLG ohne Ausreisser
```

Projektdateien der Version 1 (vor dem Kanal-Mapping) werden weiterhin
gelesen; die Zuordnung wird dann automatisch erkannt.

# Auswertungsauswahl: Jumper & Bereiche

Vor **jeder** Stapelauswertung (Auto-Fit sowie Auto-Fit mit vorgegebener
Resonanz) fragt bbFMR den Auswertungsbereich ab — Dialog
„Auswertungsbereich & Jumper" (`bbfmr/gui/auswahl_dialog.py`, Kernlogik in
`bbfmr/fit/auswahl.py`). Die zuletzt benutzte Auswahl ist vorbelegt; mit den
Standardwerten wird schlicht **alles** ausgewertet.

## Nur jeden n-ten Messpunkt („Jumper")

Getrennt einstellbar für beide Achsen:

| Einstellung | Wirkung |
|---|---|
| **Frequenzachse — jeder n-te Linescan** | Es wird nur jeder n-te Frequenz-Linescan gefittet (z. B. n = 10, 20, 30). Beschleunigt die Auswertung großer Maps entsprechend. |
| **Feldachse — jeder n-te Punkt** | Innerhalb jedes Linescans geht nur jeder n-te Feldpunkt in Fenstersuche und Fit. |

## Auszuwertender Bereich

* **Frequenz von/bis** und **Feld von/bis** grenzen die Auswertung ein
  (volle Spanne = keine Einschränkung).
* **Frequenz-Ausschlüsse**: Bänder, die *nicht* ausgewertet werden — als
  Text `3-5; 10.2-11` (GHz, mehrere mit `;`). Typischer Fall: der zur
  Feldachse parallele Abschnitt bei 3–5 GHz in Out-of-plane-Dünnschicht-
  Messungen.

Reihenfolge der Anwendung (bewusst): **erst** Bereichsfenster und
Ausschlüsse, **dann** jeder n-te der verbleibenden Linescans — so bleibt die
Schrittweite auch neben einem Ausschlussband konstant.

Die Live-Zusammenfassung im Dialog zeigt sofort, wie viele Linescans und
Feldpunkte übrig bleiben; bei leerer Auswahl, weniger als 4 Feldpunkten oder
unlesbaren Ausschluss-Angaben ist „Auswertung starten" gesperrt.

## Was intern passiert

Die Auswahl erzeugt einen **reduzierten** `Messdatensatz`; AutoWindows, Fits,
Kittel/LLG und Export arbeiten unverändert darauf. Nachvollziehbarkeit über
`meta`:

```python
from bbfmr.fit import Auswertungsauswahl, fitte_alle

auswahl = Auswertungsauswahl(
    n_frequenz=10, n_feld=2,
    frequenz_ausschluss=[(3e9, 5e9)],       # Hz
    feld_min_t=2.0, feld_max_t=4.5,
)
stapel = fitte_alle(datensatz, auswahl=auswahl)
stapel.datensatz.meta["quell_indizes"]        # welche Original-Linescans
stapel.datensatz.meta["auswertungsauswahl"]   # die Auswahl (JSON-faehig)
```

Ein Dispersions-Seed (`zentren`) wird deckungsgleich mitreduziert.

Der **Farbplot zeigt weiterhin die volle Messung**; die Zuordnung zwischen
Übersicht und (eventuell reduziertem) Fit-Stapel läuft wertbasiert über die
Frequenz — ein Klick springt zum wertmäßig nächstgelegenen Fit. Ein erneuter
Auto-Fit startet immer wieder vom vollen Datensatz, die Auswahl ist also
jederzeit revidierbar.

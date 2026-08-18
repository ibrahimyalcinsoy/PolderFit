# Interaktives Fitten

Ein Modus zurzeit (Modus-Manager), aktiver Modus farblich + Statusleiste, `Esc` bricht ab. Zoom (Mausrad/Kästchen) ist standardmäßig **aus**: *Ansicht → Zoom (Mausrad / Kästchen)*; Doppelklick setzt zurück, Tasten `+`/`-`/`0` wirken immer. Alles rückgängig: `Strg+Z` / `Strg+Umschalt+Z` (50 Schritte).

| Werkzeug | Aufruf | Wirkung |
|---|---|---|
| Bereich neu fitten (Rechteck) | `Strg+B` | Fenstersuche + Fit nur im Rechteck; Modus *überschreiben*/*ergänzen*; optional feste Fensterbreite (Punkte); `B_res` bleibt im Rechteck |
| Grenzgeraden | Panel *Zonen & Grenzgeraden*, 2 Klicks | grüne Seite neu fitten, rote ignorieren; zwei Geraden = Band; Doppelklick tauscht Seiten |
| Grenzen im Linescan ziehen | Fit-Panel | Einzelfrequenz, Fit sofort |
| Ausschlusszone | Panel, Rechteck | Punkte aus allen (Nach-)Fits; schraffiert; einzeln entfernbar |
| Resonanz vorgeben | 2 Klicks in Übersicht | Kittel-Gerade als Dispersions-Seed → Fenster folgen (`fenster_aus_trasse`) |

Fenstersuche aller Nachfit-Werkzeuge = wie Auto-Fit (Residuen auf vollen Linescans, Stationärabzug, lokale Trasse), nur auf das Feldintervall beschränkt.

| Fehlerbild | Werkzeug |
|---|---|
| Grenzen zu eng | Rechteck + „Fensterbreite fest“ |
| Doppel-Dip, falsches Signal | Rechteck eng um die Mode |
| Fit ok gemeldet, physikalisch falsch | Rechteck *überschreiben* + Ausschlusszone |
| Einzelner Fit daneben | Grenzen im Linescan-Panel ziehen |

```python
neu, uebersprungen = fitte_bereich(stapel, feld_min=0.55, feld_max=1.30, frequenz_min=8e9, frequenz_max=18e9, modus="ueberschreiben", breite_punkte=25)
neu, uebersprungen = fitte_geraden_bereich(stapel, [Grenzgerade(b1=2.76, f1=40.5e9, b2=2.85, f2=43.8e9, gruen_positiv=True)])
```

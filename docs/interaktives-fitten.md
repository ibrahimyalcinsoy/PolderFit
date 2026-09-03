# Interaktives Fitten

Ein Modus zurzeit (Modus-Manager), aktiver Modus blau markiert + Statusleiste, `Esc` bricht ab. Zoom (Mausrad/Kästchen) ist standardmäßig **aus**: *Ansicht → Zoom*; Doppelklick setzt zurück, Tasten `+`/`-`/`0` wirken immer. Alles rückgängig: `Strg+Z` / `Strg+Umschalt+Z` (50 Schritte). **Alle Werkzeuge funktionieren direkt nach dem Laden – ein Auto-Fit ist keine Voraussetzung** (`leerer_stapel`: nicht gefittete Frequenzen bleiben unsichtbar und außerhalb aller Auswertungen).

| Werkzeug | Aufruf | Wirkung |
|---|---|---|
| Auto-Fit (alle) | `F5` | Dialog: Frequenz/Feld von … bis … (Standard: alles), Jumper; Fenstersuche + Fit je Frequenz für Mode 1, danach alle Korridore M2…Mn |
| Korridore | `Strg+L` oder Panel *Korridore & Zonen*, 2 Klicks entlang der Resonanz | Korridor ± Breite für die nächste Mode; Anker setzen (Klick) oder ziehen führt ihn nach (linear interpoliert); „Korridor fitten …“ = Einzelfit je Frequenz NUR auf den Punkten im Korridor (harte Grenze, kein Summenfit); Dialog: Frequenzbereich, Modus, Jumper. „Resonanzen im Korridor“ = n: je Frequenz harte Trennung zwischen den n Dips, Standard Summenfit (B_res je Dip hart auf sein Segment beschränkt), alternativ harte Trennung (jeder Dip einzeln, Nachbar-Dip abgezogen); eigene Mode je Dip |
| Bereich neu fitten (Rechteck) | `Strg+B` | derselbe Dialog (Bereich editierbar); `B_res` bleibt im Bereich |
| Grenzen im Linescan ziehen | Fit-Panel (erscheint mit erstem Fit oder Klick in die Karte) | Einzelfrequenz, Fit sofort; Zahl der Resonanzen wählbar |
| Ausschlusszone | Panel, Rechteck | Punkte aus allen (Nach-)Fits; schraffiert; einzeln entfernbar |
| Bewertung | `Strg+1/2/3`, `Strg+I`, Panel-Knöpfe | gut bestätigen / problematisch / automatisch / ignorieren ([Bewertung](bewertung.md)) |

Auch Nachfits (Grenzen ziehen, „Neu fitten“) bewerten die **Kriterien**; „gut, bestätigt“ wird explizit über die Bewertung gesetzt (automatisches Bestätigen: Strg+P). Im Linescan-Panel zeigt „M1/M2 …“ die gewählte Mode; Grenzen ziehen setzt bei dieser Frequenz einen Anker des Korridors.

Während eines Fits: Wartecursor, Statusleiste mit Phase (Fenstersuche → Einzelfits), Stand, verstrichener und geschätzter Restzeit, Banner im Farbplot, Live-Einzeichnen der fertigen Punkte; `Abbrechen` beendet nach dem laufenden Fit, der Rest bleibt „nicht gefittet“ (`fitte_alle(abbruch=…)`).

Fenstersuche des Bereichs-Fits = wie Auto-Fit (Residuen auf vollen Linescans, Stationärabzug, lokale Trasse), auf das Feldintervall beschränkt. Korridor-Fits suchen kein Fenster: der Korridor ist das Fenster; Startwert aus dem lokalen Dip, sonst vom Nachbarn.

| Fehlerbild | Werkzeug |
|---|---|
| Grenzen zu eng | Rechteck + „Fensterbreite fest“ |
| mehrere Moden (z. B. nanostrukturiertes CoFe, 2–3 Zweige) | Resonanzen = 2/3 (Panel, Strg+P oder Auto-Fit-Dialog); Bänder nacheinander je Mode → fitten; Kittel/LLG je Mode (`Strg+K` → Resonanz); alle Moden im Export |
| falsches Signal neben der Mode | Rechteck eng um die Mode oder Korridor |
| Fit ok gemeldet, physikalisch falsch | `Strg+2` (problematisch) oder Rechteck *überschreiben* + Ausschlusszone |
| Fit gelb, aber sichtbar richtig („alpha unphysikalisch“ bei breiten Linien) | `Strg+1` (gut bestätigen) oder α-Plausibilitätsgrenze anheben (`Strg+P`) |
| Einzelner Fit daneben | Grenzen im Linescan-Panel ziehen |

```python
st = leerer_stapel(ds)                                   # ohne Auto-Fit
k = Korridor(mode=2, anker=[Anker(40.5e9, 2.70, 2.80), Anker(43.8e9, 2.80, 2.90)])
neu, uebersprungen = fitte_korridor(st, k, schritt=1)
neu, uebersprungen = fitte_bereich(stapel, feld_min=0.55, feld_max=1.30, frequenz_min=8e9, frequenz_max=18e9, modus="ueberschreiben", breite_punkte=25)
stapel.bewerte(i, "bestaetigt")                          # "auto" | "bestaetigt" | "verworfen"
```

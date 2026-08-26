# Interaktives Fitten

Ein Modus zurzeit (Modus-Manager), aktiver Modus blau markiert + Statusleiste, `Esc` bricht ab. Zoom (Mausrad/Kästchen) ist standardmäßig **aus**: *Ansicht → Zoom*; Doppelklick setzt zurück, Tasten `+`/`-`/`0` wirken immer. Alles rückgängig: `Strg+Z` / `Strg+Umschalt+Z` (50 Schritte). **Alle Werkzeuge funktionieren direkt nach dem Laden – ein Auto-Fit ist keine Voraussetzung** (`leerer_stapel`: nicht gefittete Frequenzen bleiben unsichtbar und außerhalb aller Auswertungen).

| Werkzeug | Aufruf | Wirkung |
|---|---|---|
| Auto-Fit (alle) | `F5` | Dialog: Frequenz/Feld von … bis …, Jumper; Fenstersuche + Fit je Frequenz |
| Grenzgeraden | `Strg+L` oder Panel *Zonen & Grenzgeraden*, 2 Klicks | grüne Seite fitten, rote ignorieren; zwei Geraden = Band; Doppelklick tauscht Seiten; „Grünen Bereich fitten …“ fragt **Frequenz/Feld von … bis …** (zuletzt benutzter Bereich vorbelegt; Punkt oder Komma), Modus, Fensterbreite, Resonanzen ab; bei mehreren Resonanzen (Panel: „Resonanzen je Linescan“) **nacheinander** je Mode ein Band („Band einzeichnen“, 2 Klicks entlang der Mode ± Breite, oder zwei Geraden) → fitten → nächstes Band → fitten: die Mode-Nummer wird automatisch vergeben (erstes Band = Mode 1, zweites = Mode 2 …), jeder Fit rechnet alle bisher eingezeichneten Moden **gleichzeitig** (Überlagerung berücksichtigt), Mode k wird nur in Band k gesucht; Vorprüfung meldet, wenn sich die grünen Seiten nirgends schneiden |
| Bereich neu fitten (Rechteck) | `Strg+B` | derselbe Dialog (Bereich editierbar); `B_res` bleibt im Bereich |
| Grenzen im Linescan ziehen | Fit-Panel (erscheint mit erstem Fit oder Klick in die Karte) | Einzelfrequenz, Fit sofort; Zahl der Resonanzen wählbar |
| Ausschlusszone | Panel, Rechteck | Punkte aus allen (Nach-)Fits; schraffiert; einzeln entfernbar |
| Bewertung | `Strg+1/2/3`, `Strg+I`, Panel-Knöpfe | gut bestätigen / problematisch / automatisch / ignorieren ([Bewertung](bewertung.md)) |

Ein gezielter Eingriff an **einer** Frequenz (Grenzen ziehen, „Nochmal fitten“) gilt als **vom Nutzer bestätigt** (grün mit blauem Rand, geht in Kittel/LLG ein) – abschaltbar unter `Strg+P`; Bereichs- und Grenzgeraden-Fits über viele Frequenzen bewerten die Kriterien (`auto`). Das Kriterienergebnis bleibt stets als `problematisch_auto` erhalten. Punkt im Farbplot überfahren → Tooltip mit f, B_res, µ0ΔH (mT), α, R², Status. Angezeigt werden nur Werte (keine Residuen-/Unsicherheitskennzahlen; diese stehen im Export).

Während eines Fits: Wartecursor, Statusleiste mit Phase (Fenstersuche → Einzelfits), Stand, verstrichener und geschätzter Restzeit, Banner im Farbplot, Live-Einzeichnen der fertigen Punkte; `Abbrechen` beendet nach dem laufenden Fit, der Rest bleibt „nicht gefittet“ (`fitte_alle(abbruch=…)`).

Fenstersuche aller Nachfit-Werkzeuge = wie Auto-Fit (Residuen auf vollen Linescans, Stationärabzug, lokale Trasse), nur auf das Feldintervall beschränkt. Mehrere Resonanzen je Linescan: `n_moden` ([Physik und Fit](physik-und-fit.md)).

| Fehlerbild | Werkzeug |
|---|---|
| Grenzen zu eng | Rechteck + „Fensterbreite fest“ |
| mehrere Moden (z. B. nanostrukturiertes CoFe, 2–3 Zweige) | Resonanzen = 2/3 (Panel, Strg+P oder Auto-Fit-Dialog); Bänder nacheinander je Mode → fitten; Kittel/LLG je Mode (`Strg+K` → Resonanz); alle Moden im Export |
| falsches Signal neben der Mode | Rechteck eng um die Mode oder Grenzgeraden |
| Fit ok gemeldet, physikalisch falsch | `Strg+2` (problematisch) oder Rechteck *überschreiben* + Ausschlusszone |
| Fit gelb, aber sichtbar richtig („alpha unphysikalisch“ bei breiten Linien) | `Strg+1` (gut bestätigen) oder α-Plausibilitätsgrenze anheben (`Strg+P`) |
| Einzelner Fit daneben | Grenzen im Linescan-Panel ziehen |

```python
st = leerer_stapel(ds)                                   # ohne Auto-Fit
neu, uebersprungen = fitte_geraden_bereich(st, [Grenzgerade(b1=2.76, f1=40.5e9, b2=2.85, f2=43.8e9)],
                                           frequenz_min=8e9, frequenz_max=18e9)
neu, uebersprungen = fitte_bereich(stapel, feld_min=0.55, feld_max=1.30, frequenz_min=8e9, frequenz_max=18e9, modus="ueberschreiben", breite_punkte=25)
stapel.bewerte(i, "bestaetigt")                          # "auto" | "bestaetigt" | "verworfen"
```

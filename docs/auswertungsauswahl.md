# Auswertungsauswahl (Bereiche, Jumper)

Vor jedem Auto-Fit: Dialog „Auswertungsbereich & Jumper“ (`fit/auswahl.py`).

| Einstellung | Wirkung |
|---|---|
| jeder n-te Linescan / jeder n-te Feldpunkt | Unterabtastung (Tempo) |
| Frequenz von/bis, Feld von/bis | Bereich (ROI) – vorbelegt aus dem gezoomten Farbplot; „ROI im Farbplot aufziehen …“ schließt den Dialog, Rechteck aufziehen, Dialog öffnet mit dem Rechteck wieder; „Zoom-Ausschnitt übernehmen“, „Ganzer Bereich“ |
| Frequenz-Ausschlüsse `3-5; 10.2-11` (GHz) | Bänder auslassen (z. B. feldparalleler Abschnitt bei oop-Dünnschichten) |

Ein enger Feldbereich und „jeder n-te Feldpunkt“ beschleunigen den Auto-Fit deutlich (weniger Punkte je Linescan) – bei 2–3 Resonanzen je Linescan besonders. Reihenfolge: Bereich/Ausschlüsse → dann jeder n-te. Ergebnis: reduzierter `Messdatensatz` (`meta["quell_indizes"]`, `meta["auswertungsauswahl"]`); Farbplot zeigt weiter die volle Messung.

```python
stapel = fitte_alle(ds, auswahl=Auswertungsauswahl(n_frequenz=10, frequenz_ausschluss=[(3e9,5e9)], feld_min_t=2.0))
```

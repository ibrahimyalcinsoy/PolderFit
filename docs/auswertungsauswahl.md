# Auswertungsauswahl (Bereiche, Jumper)

Vor jedem Auto-Fit: Dialog „Auswertungsbereich & Jumper“ (`fit/auswahl.py`).

| Einstellung | Wirkung |
|---|---|
| jeder n-te Linescan / jeder n-te Feldpunkt | Unterabtastung (Tempo). Frequenz-Jumper **absolut** auf dem vollen Gitter (Index i mit i mod n = 0); Korridor-Fits übernehmen ihn |
| Frequenz von/bis, Feld von/bis | Bereich – Standard: ganzer Datensatz; „Zoom-Ausschnitt übernehmen“ setzt den sichtbaren Farbplot-Ausschnitt |
| Frequenz-Ausschlüsse `3-5; 10.2-11` (GHz) | Bänder auslassen (z. B. feldparalleler Abschnitt bei oop-Dünnschichten) |

Ein enger Feldbereich und „jeder n-te Feldpunkt“ beschleunigen den Auto-Fit deutlich (weniger Punkte je Linescan). Der Stapel behält **alle** Frequenzen; nicht gewählte bleiben „nicht gefittet“ (`meta["auswertungsauswahl"]`). Feld-Jumper/-Bereich reduzieren die Punkte je Linescan.

```python
stapel = fitte_alle(ds, auswahl=Auswertungsauswahl(n_frequenz=10, frequenz_ausschluss=[(3e9,5e9)], feld_min_t=2.0))
```

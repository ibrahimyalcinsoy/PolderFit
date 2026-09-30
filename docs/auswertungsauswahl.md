# Evaluation selection (ranges, jumpers)

Before every Auto-Fit: dialog “Auto-Fit: range & jumper” (`fit/auswahl.py`).

| Setting | Effect |
|---|---|
| every n-th linescan / every n-th field point | subsampling (speed). Frequency jumper **absolute** on the full grid (index i with i mod n = 0); corridor fits use it too |
| frequency from/to, field from/to | range – default: whole dataset; “Use zoom region” takes the visible color plot region |
| frequency exclusions `3-5; 10.2-11` (GHz) | skip bands (e.g. field-parallel part of oop thin films) |

Narrow field range and field jumper speed up the Auto-Fit. The stack keeps **all** frequencies; unselected ones stay “not fitted” (`meta["auswertungsauswahl"]`).

```python
stapel = fitte_alle(ds, auswahl=Auswertungsauswahl(n_frequenz=10, frequenz_ausschluss=[(3e9,5e9)], feld_min_t=2.0))
```

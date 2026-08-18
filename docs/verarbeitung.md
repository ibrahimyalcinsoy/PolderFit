# Verarbeitung des Farbplots (nur Darstellung)

Portiert aus *pybbfmr*, Grundlage Maier-Flaig et al., RSI 89, 076101 (2018). **Kein Einfluss auf Fits** – der Linescan-Fit läuft immer auf dem rohen S21.

| Schritt | Formel / Wirkung | Parameter |
|---|---|---|
| divide slice | `Z / Z[:, i_ref]` – entfernt `V_BG(ω)·e^{iφ}` | Index/Wert, Achse Feld/Frequenz |
| derivative divide | `[S(H+ΔH) − S(H−ΔH)] / [S(H)·ΔH] ≈ −iωA′ ∂χ/∂ω` (Gl. 4) | `Δn` (Standard 4), `mitteln`, Achse |
| relation amplitude | `Z[i] / Z[i+Δn]` | `Δn` |

Standard nach dem Laden: derivative divide, Δn = 4, Farbskala 2–98 %-Perzentile. Ränder → NaN (pybbfmr: 0).

```python
feld, freq, Z = ds.komplexe_matrix()
feld, freq, G = derivative_divide(feld, freq, Z, delta_n=4, mitteln=True)
```

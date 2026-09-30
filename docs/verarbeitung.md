# Color plot processing (display only)

Ported from *pybbfmr*, based on Maier-Flaig et al., RSI 89, 076101 (2018). **No effect on fits** – the linescan fit always uses raw S21.

| Step | Formula / effect | Parameters |
|---|---|---|
| divide slice | `Z / Z[:, i_ref]` – removes `V_BG(ω)·e^{iφ}` | index/value, axis field/frequency |
| derivative divide | `[S(H+ΔH) − S(H−ΔH)] / [S(H)·ΔH] ≈ −iωA′ ∂χ/∂ω` (eq. 4) | `Δn` (default 4), `mitteln`, axis |
| relation amplitude (hidden in GUI) | `Z[i] / Z[i+Δn]` | `Δn` |

Default after loading: derivative divide, Δn = 4, color scale 2–98 % percentiles. Edges → NaN (pybbfmr: 0).

Panel *Processing*: **one** operation active (“All off” = raw data); color scales Viridis, Gray, Cividis, Magma, Red-Blue (also *View → Color scale*). Export: *Color plot as image* (PNG/PDF/SVG with overlays), *Color plot matrix as CSV*. Chain and color scale are stored in [settings](ausreisser.md) and the project file.

```python
feld, freq, Z = ds.komplexe_matrix()
feld, freq, G = derivative_divide(feld, freq, Z, delta_n=4, mitteln=True)
```

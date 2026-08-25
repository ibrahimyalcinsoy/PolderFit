# Verarbeitung des Farbplots (nur Darstellung)

Portiert aus *pybbfmr*, Grundlage Maier-Flaig et al., RSI 89, 076101 (2018). **Kein Einfluss auf Fits** – der Linescan-Fit läuft immer auf dem rohen S21.

| Schritt | Formel / Wirkung | Parameter |
|---|---|---|
| divide slice | `Z / Z[:, i_ref]` – entfernt `V_BG(ω)·e^{iφ}` | Index/Wert, Achse Feld/Frequenz |
| derivative divide | `[S(H+ΔH) − S(H−ΔH)] / [S(H)·ΔH] ≈ −iωA′ ∂χ/∂ω` (Gl. 4) | `Δn` (Standard 4), `mitteln`, Achse |
| relation amplitude | `Z[i] / Z[i+Δn]` | `Δn` |

Standard nach dem Laden: derivative divide, Δn = 4, Farbskala 2–98 %-Perzentile. Ränder → NaN (pybbfmr: 0).

Bedienung (Panel *Verarbeitung*): **genau eine** Operation aktiv (Einschalten schaltet die andere ab; „Alles aus“ = Rohdaten), jede Option mit Hover-Erklärung, Farbskala wählbar (Viridis, Grau, Cividis, Magma, Rot-Blau; auch *Ansicht → Farbskala*). Mausrad wirkt in Eingabefeldern nur mit Fokus; Änderungen sind entprellt (150 ms). Das Figur-Layout wird vor jedem Neuzeichnen zurückgesetzt – der frühere Fehler „Farbplot wird bei Δn-Mausrad immer schmaler“ ist damit behoben. Export: *Farbplot als Bild* (PNG/PDF/SVG mit Overlays) und *Farbplot-Matrix als CSV* (verarbeitete Matrix). Kette und Farbskala sind Teil der [Voreinstellungen](ausreisser.md) und der Projektdatei.

```python
feld, freq, Z = ds.komplexe_matrix()
feld, freq, G = derivative_divide(feld, freq, Z, delta_n=4, mitteln=True)
```

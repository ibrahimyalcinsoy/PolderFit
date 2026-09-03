# Schnellreferenz

| Symbol | Bedeutung | Einheit | Export |
|---|---|---|---|
| α | Gilbert-Dämpfung (Einzelfit je f; global: LLG-Steigung) | – | `alpha`, `llg_alpha` |
| γ = g·µ_B/ħ | gyromagn. Verhältnis | rad s⁻¹ T⁻¹ | `kittel_gamma` |
| g | Landé-Faktor | – | `kittel_g_faktor` |
| µ0H, B_res | Feld / Resonanzfeld | T (auch mT) | `B_res_T`, `B_res_mT` |
| µ0ΔH = 2ωα/γ | Linienbreite (FWHM χ″) | T (auch mT) | `mu0_dH_T`, `mu0_dH_mT`, `mu0_dH_err_mT` |
| A·e^{iφ} | komplexe Amplitude | – | `A`, `phi_rad`, `A_komplex_re/im` |
| Mode k ≥ 2 | Korridor-Fit der Mode k | eigenes Blatt `Einzelfits_M<k>` | gleiche Spalten wie Mode 1, Spalte `mode` |
| Bewertung | auto / bestaetigt / verworfen | | `bewertung`, `problematisch`, `problematisch_auto` |
| µ0M_eff | eff. Magnetisierung | T | `kittel_mu0Meff` |
| µ0H_u | Anisotropiefeld (ip) | T | `kittel_mu0Hu` |
| µ0ΔH_0 | inhomogene Verbreiterung | T | `llg_mu0Hinh` |
| `*_err` | 1σ (GUM Typ A, Kovarianz) | | |

| Formel | Quelle | Code |
|---|---|---|
| B_res = µ0M_eff + 2πf/γ | Müller (2.24) | `kittel_oop` |
| B_res = √[(2πf/γ)² + (µ0M_eff/2)²] − µ0M_eff/2 − µ0H_u | Müller (2.26) | `kittel_ip` |
| µ0ΔH = 2ωα/γ | Müller (2.27) | `FitErgebnis.dH` |
| µ0ΔH(f) = µ0ΔH_0 + (4π/γ)αf | Müller (2.28) | `fit_linienbreite` |
| χ_oop | Notebook / Müller (2.20) | `suszeptibilitaet.py` |
| S21 = A e^{iφ}χ + B + C(B−B_ref) | Maier-Flaig (8) | `s21_modell` |
| S21 = Σ_k A_k e^{iφ_k}χ_k + B + C(B−B_ref) | Mehr-Moden-Erweiterung | `s21_modell_multi` |
| d_D S21 = [S(H+ΔH)−S(H−ΔH)]/[S(H)ΔH] | Maier-Flaig (4) | `derivative_divide` |
| Σ = ŝ²(JᵀJ)⁻¹, ŝ² = χ²/(N−p) | lmfit `scale_covar` | `fitte_linescan` |
| u(α)/α = √[(u(m)/m)² + (u(γ)/γ)²] | GUM/ABW | `fit_linienbreite` |

Quellen: Müller 2023 (Diss., Kap. 2); Notebook `Chi_Fit_Functions_and_Inductances_2020-04-06.nb`; Maier-Flaig 2018 [doi:10.1063/1.5045135](https://doi.org/10.1063/1.5045135); Kittel 1948 [doi:10.1103/PhysRev.73.155](https://doi.org/10.1103/PhysRev.73.155); Protokoll FMR-Python 2026-05-08; ABW (TUM-Praktikum).

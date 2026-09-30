# Quick reference

| Symbol | Meaning | Unit | Export |
|---|---|---|---|
| α | Gilbert damping (single fit per f; global: LLG slope) | – | `alpha`, `llg_alpha` |
| γ = g·µ_B/ħ | gyromagnetic ratio | rad s⁻¹ T⁻¹ | `kittel_gamma` |
| g | Landé factor | – | `kittel_g_faktor` |
| µ0H, B_res | field / resonance field | T (also mT) | `B_res_T`, `B_res_mT` |
| µ0ΔH = 2ωα/γ | linewidth (FWHM χ″) | T (also mT) | `mu0_dH_T`, `mu0_dH_mT`, `mu0_dH_err_mT` |
| A·e^{iφ} | complex amplitude | – | `A`, `phi_rad`, `A_komplex_re/im` |
| Mode k ≥ 2 | corridor fit of mode k | sheet `Einzelfits_M<k>` | same columns as mode 1, column `mode` |
| Rating | auto / bestaetigt / verworfen | | `bewertung`, `problematisch`, `problematisch_auto` |
| µ0M_eff | effective magnetization | T | `kittel_mu0Meff` |
| µ0H_u | anisotropy field (ip) | T | `kittel_mu0Hu` |
| µ0ΔH_0 | inhomogeneous broadening | T | `llg_mu0Hinh` |
| `*_err` | 1σ (GUM type A, covariance) | | |

| Formula | Source | Code |
|---|---|---|
| B_res = µ0M_eff + 2πf/γ | Müller (2.24) | `kittel_oop` |
| B_res = √[(2πf/γ)² + (µ0M_eff/2)²] − µ0M_eff/2 − µ0H_u | Müller (2.26) | `kittel_ip` |
| µ0ΔH = 2ωα/γ | Müller (2.27) | `FitErgebnis.dH` |
| µ0ΔH(f) = µ0ΔH_0 + (4π/γ)αf | Müller (2.28) | `fit_linienbreite` |
| χ_oop | Notebook / Müller (2.20) | `suszeptibilitaet.py` |
| S21 = A e^{iφ}χ + B + C(B−B_ref) | Maier-Flaig (8) | `s21_modell` |
| S21 = Σ_k A_k e^{iφ_k}χ_k + B + C(B−B_ref) | multi-mode extension | `s21_modell_multi` |
| d_D S21 = [S(H+ΔH)−S(H−ΔH)]/[S(H)ΔH] | Maier-Flaig (4) | `derivative_divide` |
| Σ = ŝ²(JᵀJ)⁻¹, ŝ² = χ²/(N−p) | lmfit `scale_covar` | `fitte_linescan` |
| u(α)/α = √[(u(m)/m)² + (u(γ)/γ)²] | GUM/ABW | `fit_linienbreite` |

Sources: Müller 2023 (PhD thesis, ch. 2); notebook `Chi_Fit_Functions_and_Inductances_2020-04-06.nb`; Maier-Flaig 2018 [doi:10.1063/1.5045135](https://doi.org/10.1063/1.5045135); Kittel 1948 [doi:10.1103/PhysRev.73.155](https://doi.org/10.1103/PhysRev.73.155); FMR-Python protocol 2026-05-08; ABW (TUM lab course).

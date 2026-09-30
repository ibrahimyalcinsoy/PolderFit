# Parameters and tuning

| `fitte_alle(...)` | Default | Effect |
|---|---|---|
| `gamma` | g = 2 | start value/window only; `B_res`, `µ0ΔH` independent |
| `breite_faktor` | 8.0 | detection window = factor × FWHM |
| `alpha_max` | 0.1 | hard α bound (broad lines: raise) |
| `nachfenster_faktor` | 2.5 | 2nd pass `B_res ± k·ΔH`; 0 = off |
| `alpha_plausibel` | None (= α_max/2) | “alpha unphysical” limit |
| `nachfit_bestaetigen` | True | manual refits count as good |
| `zentren` | None | given window centres (script API) |
| `alpha_erwartet` | 0.01 | window width for a given track (script API) |

| Constant (`autowindows.py`) | Default | Adjust |
|---|---|---|
| `_HALB_MAX` | 0.4 T | narrow lines ↓, broad ↑ |
| `_PROMINENZ_MIN` | 4.0 | noisy ↑, weak ↓ |
| `fenster_punkte` (track) | 31 | larger = smoother/slower |

Rating thresholds: `RMSE_NORM_SCHWELLE` 0.35, `ALPHA_PLAUSIBEL_MAX` 0.05, `B_RES_REL_UNSICHERHEIT_MAX` 0.02 ([Rating](bewertung.md)).

| Sample type | Recommendation |
|---|---|
| narrow (YIG) | `_HALB_MAX` ↓; “alpha at bound” (lower) expected |
| weak/noisy (near ip) | `_PROMINENZ_MIN` ↑ or corridor around the mode |
| grid/periodic background | stationary removal (unsorted); else corridor/region |
| very broad (FeCr₂S₄, α ≈ 0.2–0.8) | `alpha_max` ↑, `alpha_plausibel` ↑ + manual windows |
| close modes (double dip, avoided crossing) | one corridor with “Resonances in corridor” = n (sum fit, B_res per dip in segment; or hard split), separators, optional BIC; separate modes: one corridor each |

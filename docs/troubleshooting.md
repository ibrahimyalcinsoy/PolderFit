# Troubleshooting

| Symptom | Cause | Action |
|---|---|---|
| “point count … not divisible by field count” | `_flush` file, last sweep incomplete | cut automatically; else file broken |
| “no mapping profile matches” | foreign layout or non-FMR (`Read.ZNA`, angle sweep) | mapping dialog; angle sweeps not supported |
| very long runtime | thousands of field points per linescan | jumpers (evaluation selection), smaller range |
| fit good, window visibly wrong | spurious feature/noise | corridor (`Ctrl+L`), rectangle refit, `_PROMINENZ_MIN` ↑ |
| color plot misplaced | – | *View → Reset window layout* (`Ctrl+Shift+R`) |
| “alpha unphysical” on visibly good broad lines | plausibility limit α_max/2 | `Ctrl+P` raise limit or `Ctrl+1` confirm |
| “alpha at bound” on narrow lines (α ≲ α_max/100) | within 1 % of [α_min, α_max] | `Ctrl+P` lower α upper bound (down to 0.00001) |
| work lost (crash) | – | *File → Restore auto-backup* |
| program seems frozen | long Auto-Fit/loading | status bar shows phase, progress, remaining time; **Cancel** stops cleanly, fits so far are kept |
| very many problematic fits | no resonance in field range (low f); ip with oop model at bound | check `problem_statistik()` – usually correct |
| fit looks good, “no uncertainties” | φ side minimum, singular Jacobian | automatic φ restart, exception for `rmse_norm ≤ 0.10`; else check window/start values |
| window too low | stationary artefacts at field edge | stationary removal/track; else corridor |
| `.tdms_index` mismatch | file copied/renamed | read without index automatically; delete index |

Many files at once: [Robustness harness](test-harness.md) (`diag/` plots).

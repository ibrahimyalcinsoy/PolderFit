# Parameter und Feineinstellung

| `fitte_alle(...)` | Standard | Wirkung |
|---|---|---|
| `gamma` | g = 2 | nur Startwert/Fenster; `B_res`, `µ0ΔH` unabhängig davon |
| `breite_faktor` | 8.0 | Detektionsfenster = Faktor × FWHM |
| `alpha_max` | 0.1 | harte α-Schranke (breite Linien: anheben) |
| `nachfenster_faktor` | 2.5 | 2. Durchgang `B_res ± k·ΔH`; 0 = aus |
| `zentren` | None | vorgegebene Fenstermitten |
| `alpha_erwartet` | 0.01 | Fensterbreite bei vorgegebener Dispersion |

| Konstante (`autowindows.py`) | Standard | Anpassung |
|---|---|---|
| `_HALB_MAX` | 0.4 T | schmale Linien ↓, breite ↑ |
| `_PROMINENZ_MIN` | 4.0 | verrauscht ↑, schwach ↓ |
| `fenster_punkte` (Trasse) | 31 | größer = glatter/träger |

Bewertungsschwellen: `RMSE_NORM_SCHWELLE` 0.35, `ALPHA_PLAUSIBEL_MAX` 0.05, `B_RES_REL_UNSICHERHEIT_MAX` 0.02 ([Bewertung](bewertung.md)).

| Probentyp | Empfehlung |
|---|---|
| schmal (YIG) | `_HALB_MAX` ↓; „alpha an Grenze“ unten erwartbar |
| schwach/verrauscht (nahe ip) | `_PROMINENZ_MIN` ↑ oder Dispersion vorgeben |
| Gitter/periodischer Untergrund | Stationärabzug greift (unsortiert); sonst Dispersion vorgeben |
| sehr breit (FeCr₂S₄, α ≈ 0,2–0,8) | `alpha_max` ↑ + manuelle Fenster (Automatik nicht ausgelegt) |

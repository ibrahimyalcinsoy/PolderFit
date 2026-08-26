# Parameter und Feineinstellung

| `fitte_alle(...)` | Standard | Wirkung |
|---|---|---|
| `gamma` | g = 2 | nur Startwert/Fenster; `B_res`, `µ0ΔH` unabhängig davon |
| `breite_faktor` | 8.0 | Detektionsfenster = Faktor × FWHM |
| `alpha_max` | 0.1 | harte α-Schranke (breite Linien: anheben) |
| `nachfenster_faktor` | 2.5 | 2. Durchgang `B_res ± k·ΔH`; 0 = aus |
| `alpha_plausibel` | None (= α_max/2) | Grenze „alpha unphysikalisch“ |
| `n_moden` | 1 | Resonanzen je Linescan (Dropdown im Auto-Fit-Dialog) |
| `auto_fit_zweistufig` | aus | Erweitert: erst klassischer Ein-Moden-Auto-Fit, dann weitere Resonanzen je Linescan ergänzen (Phantom-Filter, bei Misserfolg bleibt das klassische Ergebnis) |
| `nachfit_bestaetigen` | True | manuelle Nachfits gelten als gut |
| `zentren` | None | vorgegebene Fenstermitten (Skript-API) |
| `alpha_erwartet` | 0.01 | Fensterbreite bei vorgegebener Trasse (Skript-API) |

| Konstante (`autowindows.py`) | Standard | Anpassung |
|---|---|---|
| `_HALB_MAX` | 0.4 T | schmale Linien ↓, breite ↑ |
| `_PROMINENZ_MIN` | 4.0 | verrauscht ↑, schwach ↓ |
| `fenster_punkte` (Trasse) | 31 | größer = glatter/träger |

Bewertungsschwellen: `RMSE_NORM_SCHWELLE` 0.35, `ALPHA_PLAUSIBEL_MAX` 0.05, `B_RES_REL_UNSICHERHEIT_MAX` 0.02 ([Bewertung](bewertung.md)).

| Probentyp | Empfehlung |
|---|---|
| schmal (YIG) | `_HALB_MAX` ↓; „alpha an Grenze“ unten erwartbar |
| schwach/verrauscht (nahe ip) | `_PROMINENZ_MIN` ↑ oder Grenzgeraden um die Mode |
| Gitter/periodischer Untergrund | Stationärabzug greift (unsortiert); sonst Grenzgeraden/Bereich |
| sehr breit (FeCr₂S₄, α ≈ 0,2–0,8) | `alpha_max` ↑, `alpha_plausibel` ↑ + manuelle Fenster (Automatik nicht ausgelegt) |
| Doppel-Dip (nanostrukturiertes CoFe) | `n_moden = 2`; Hauptmode = stärkste Linie, im Panel wechselbar |

# FTF-Benchmark (nur Auto-Fit) — 2026-09-03

Lauf: `run_benchmark.py --suffix _auto_2026-09-03 cofe_wm_ip_290K_1 cofe_wm_ip_290K_2 cofe_wm_ip_5K_1 cofe_wm_ip_5K_2`
(cofe_gratings_ip_5K, yig_konstanz_ip_50K aus Zeitgründen nicht mehr gelaufen)
Ergebnis: `benchmark_ftf/ergebnisse/zusammenfassung_auto_2026-09-03.json` (+ Einzel-JSON/CSV je Satz)

## Einzelfits (Kittel/LLG, ungewichtet, kombiniertes σ = √(σ_PF²+σ_FTF²))

| Datensatz | Größe | PolderFit ± σ | FTF | z | Bewertung |
|---|---|---|---|---|---|
| cofe_wm_ip_290K_1 | g | 2.1054 ± 0.0025 | 2.1053 ± 0.0026 | 0.03 | OK (≤1σ) |
| | µ0M_eff [T] | 2.2496 ± 0.0096 | 2.2492 ± 0.0098 | 0.03 | OK |
| | α | 0.007338 ± 0.000187 | 0.007378 ± 0.000199 | −0.15 | OK |
| | µ0H_u [T] | 0.003053 ± 0.000474 | 0.003140 ± 0.000430 | −0.14 | OK |
| | µ0ΔH0 [T] | −0.000921 ± 0.000574 | −0.001005 ± 0.000613 | 0.10 | OK |
| cofe_wm_ip_5K_1 | g | 2.1065 ± 0.0026 | 2.1048 ± 0.0026 | 0.46 | OK |
| | µ0M_eff [T] | 2.3049 ± 0.0103 | 2.3104 ± 0.0097 | −0.39 | OK |
| | α | 0.007818 ± 0.000192 | 0.007857 ± 0.000192 | −0.14 | OK |
| | µ0H_u [T] | 0.004758 ± 0.000481 | 0.004624 ± 0.000401 | 0.21 | OK |
| | µ0ΔH0 [T] | −0.0000617 ± 0.000589 | −0.000134 ± 0.000591 | 0.09 | OK |
| cofe_wm_ip_290K_2 | g | 1.938 ± 0.017 | 4.000 ± 2.1e8 (Grenze) | ~0 | FTF-Kittel unbrauchbar (bekannt) |
| | µ0M_eff [T] | 2.749 ± 0.051 | 0.508 ± 0.0096 | 43.2 | kein Vergleich möglich (FTF-Artefakt) |
| | α | 0.00521 ± 0.0003 | 0.01057 ± 0.00057 | −8.3 | kein Vergleich möglich (FTF-Artefakt) |
| cofe_wm_ip_5K_2 | g | 2.257 ± 0.341 | 4.000 ± 9.0e7 (Grenze) | ~0 | FTF-Kittel unbrauchbar (bekannt) |
| | µ0M_eff [T] | 2.008 ± 0.679 | 0.455 ± 0.011 | 2.29 | kein Vergleich möglich (FTF-Artefakt), PF-Fehler groß (nur 13 Punkte) |
| | α | 0.00550 ± 0.00114 | 0.00826 ± 0.00085 | −1.94 | grenzwertig, aber FTF-Referenz selbst unbrauchbar |

Einzelfit-Niveau (Frequenzscans, ΔH-Vergleich):

| Datensatz | n | PF problematisch | Median ΔH_PF/ΔH_FTF−1 | Anteil \|z_ΔH\|≤2 | BERICHT.md (Referenz) |
|---|---|---|---|---|---|
| cofe_wm_ip_290K_1 | 70 | 0 | +0.05 % | 100 % | +0.1 % / 100 % — deckungsgleich |
| cofe_wm_ip_290K_2 | 21 | 0 | +0.08 % | 95.2 % | +0.1 % / 95 % — deckungsgleich |
| cofe_wm_ip_5K_1 | 71 | 0 | −0.24 % | 100 % | −0.2 % / 100 % — deckungsgleich |
| cofe_wm_ip_5K_2 | 13 | 0 | −0.70 % | 100 % | −0.7 % / 100 % — deckungsgleich |

## Fazit Aufgabe 1

1. **Numerische Genauigkeit:** Für `cofe_wm_ip_290K_1` und `cofe_wm_ip_5K_1` (die einzigen Sätze mit brauchbarer FTF-Kittel-Referenz) liegen g, µ0M_eff, α, µ0H_u, µ0ΔH0 alle bei |z| ≤ 0.5 — deutlich innerhalb 1σ, Abnahmekriterium erfüllt und deckt sich exakt mit BERICHT.md. `cofe_wm_ip_290K_2`/`_5K_2` liefern erwartungsgemäß große z-Werte, weil dort das FTF-Kittel selbst an der Fitgrenze hängt (g=4,000 mit σ~10⁸) — das ist der in BERICHT.md §4.6 dokumentierte FTF-Defekt, kein PolderFit-Problem; ein Kittel-Vergleich ist für diese beiden Sätze nicht aussagekräftig.
2. **Physikalische Plausibilität:** µ0M_eff > 0 in allen vier Auto-Fits (CoFe ip, Vorzeichenkonvention korrekt), g liegt bei den beiden validen Sätzen bei 2.105/2.107 (typisch CoFe, nahe 2.1, plausibel); bei den beiden „Grenze"-Sätzen weicht PolderFits eigener g (1.94/2.26) vom FTF-Artefaktwert (4.000) ab, was konsistent mit „FTF unbrauchbar" ist. α liegt bei 5–8·10⁻³, Größenordnung passt zu CoFe.
3. **Reproduzierbarkeit BERICHT.md:** Einzelfit-Kennzahlen (Median ΔH-Abweichung, Anteil |z_ΔH|≤2) reproduzieren die in BERICHT.md Abschnitt 3.1 dokumentierten Werte auf ≤0.05 Prozentpunkte — keine Regression seit dem letzten Bericht (Stand vor den GUI-Änderungen der letzten Commits e3b1ea7 u.a.). Kein Fund, der eine Abweichung > 1σ zum damaligen Stand zeigt.

## Aufgabe 2 — Robustheit Auto-Fit auf Linescan-Sätzen

`lade_tdms` + `fitte_alle`, je Datei timeout 240s (keine Ausnahmen aufgetreten).

| Datei | Linescans | problematisch | Top-Problemgründe | Laufzeit |
|---|---|---|---|---|
| 2025-NOV-11-…-5K_1.1deg-for-FTF.tdms | 629 | 30 (4.8 %) | alpha unphysikalisch: 24, alpha an Grenze: 8, Linie nicht aufgelöst: 6 | 3.4 s |
| 2025-NOV-12-…-5K_19.5-22.5GHz.tdms | (nicht separat ermittelt) | 0 | — | 12.5 s |
| 2025-NOV-12-…-5K_28.5-31.5GHz.tdms | (nicht separat ermittelt) | 2 | keine Unsicherheiten: 2 | 12.6 s |
| 2025-NOV-13-…-295K_19-22GHz.tdms | (nicht separat ermittelt) | 0 | — | 15.4 s |

Befund: Alle 4 echten Linescan-Sätze laufen ohne Absturz/Traceback durch. Datei 1 (5K, 1.1°) hat mit 4.8 % problematischen Fits (Hauptgrund: α unphysikalisch/an Grenze — vermutlich sehr breite oder schwache Linien in diesem Winkel-Datensatz) die auffälligste Problemquote; die drei GHz-Fenster-Sätze sind praktisch sauber (0–2 Ausreißer). Keine Reparaturen vorgenommen (wie angewiesen), nur Befund.


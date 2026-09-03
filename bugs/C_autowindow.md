# Bereich C – AutoWindow (HEAD e3b1ea7 vs. 7c893e8)

Erhoben vom Hauptagenten (der Subagent für C wurde gestoppt); Zahlen aus eigenem
Skript `c_autowindow.py` (Scratchpad) sowie aus den Berichten B und H.

## Ergebnis: kein Bug im AutoWindow-Algorithmus

* `polderfit/fit/autowindows.py`: Diff zu 7c893e8 besteht ausschließlich aus dem
  optionalen Fortschritts-Callback `fortschritt(k, n)` in `auto_fenster_alle`
  (Zeilen 230–266). Fensterbestimmung (`_detrend_residuum`, `_kandidat`,
  `_fwhm_um`, `_robuste_trasse`, `_glatte_lokale_trasse`, `_verfeinere_zentrum`,
  `_fenster_um`, Deckel, Perzentile, Mindestpunkte) ist byteidentisch.
* Defaults unverändert: `breite_faktor` 8.0, Nachfenster 2,5·ΔH, α-Obergrenze 0,1,
  r²-Schwelle 0,9, `n_moden` 1 (`fit/parameter.py`).
* Messung (Standardparameter, `auto_fenster_alle` + `fitte_alle`):

| Datensatz | n | Fenster HEAD/REF | Fenstersuche | Einzelfits | unproblematisch |
|---|---|---|---|---|---|
| 5K_1.1deg-for-FTF | 629 | max Δ = 0 T (bitgleich) | 0,12 s / 0,12 s | 3,4 s / 3,4 s | 605 / 605 |
| 5K_28.5-31.5GHz | 1001 | max Δ = 0 T (bitgleich) | 0,55 s / 0,55 s | 10,7 s / 10,6 s | 999 / 999 |

* Bericht B bestätigt: B_res/ΔH über alle 629 Frequenzen < 1e-9 identisch, Fenster
  wandert entlang der Mode (2,60 T @ 6 GHz → 4,11 T @ 49,7 GHz).
* Bericht H bestätigt: voller Auto-Fit-Pfad (AutoWindows + `fitte_alle` + Kittel/LLG)
  auf CoFe und FeCr₂S₄ elementweise identisch.

## Woher der Eindruck „langsamer, schlechtere Fenster" kommt (Belege in B, E)

1. **n_moden > 1 (zweistufiger Moden-Fit, Commit 798b794):** `batch.py:400–404`
   weitet das Fenster der 2. Stufe per `min/max` auf das breite AutoWindow
   (37 → ~103 Punkte), das validierte Nachfenster ±2,5·ΔH ist damit wirkungslos
   (B3/E3). Laufzeit 3,6 s → 38,1 s (Faktor 10,6) durch bis zu 4 Startwert-
   Kandidaten und ×4,2 LM-Iterationen wegen Entartung des Summenfits (E5).
2. **Wege ohne Auto-Fit (Commit 45871fa):** `leerer_stapel` (`batch.py:505–508`)
   setzt das Fenster auf den ganzen Feldsweep; „Neu fitten"/Grenzen ziehen im
   Panel fitten dann ~197 statt ~35 Punkte, ΔH bis +34 % zu groß (B1).

## Fixvorschlag
* AutoWindow: **Behalten aus HEAD** (identisch zur Referenz, Callback ist harmlos).
* Ursachen 1/2 werden unter B1/B3/E3/E5 behandelt (Nachfenster nicht aufweiten,
  leeren Stapel mit AutoWindow-Fenster füllen bzw. Panel-Fit nur im grünen Fenster).

Risiko: keines für den Algorithmus selbst.

# Benchmark PolderFit gegen das LabVIEW-Tool „FTF" (Stand 2026-08-17)

**Begriffe in diesem Bericht und in den Dateinamen**

| Begriff / Kürzel | Bedeutung |
|---|---|
| FTF | LabVIEW-Auswerteprogramm „fiddling together FMR“ (Referenz) |
| `gratings` | Probe mit Gitterstruktur (nanostrukturiertes CoFe, 138 nm Streifen) |
| `_einpass` (Dateiname) | Lauf mit nur **einem** Fit-Durchgang (ohne zweiten Durchgang auf ±2,5 Linienbreiten, „Nachfenster“ = 0) |
| `alpha_max` / α-Obergrenze | größte im Fit erlaubte Gilbert-Dämpfung α (Standard 0,1; FeCr₂S₄ 1,0) |
| ip / oop | Magnetfeld in der Schichtebene (in-plane) / senkrecht zur Schicht (out-of-plane) |
| Nachfenster | zweiter Fit-Durchgang auf dem verengten Fenster B_res ± 2,5·ΔH |
| z-Score | Differenz geteilt durch die kombinierte Unsicherheit (nur in diesem ausführlichen Bericht; der einfache Vergleich kommt ohne aus) |
| Linescan / Colormap | Feldsweep bei fester Frequenz / Frequenzsweep bei festem Feld (umsortiert) |

Abbildungen (`ergebnisse/*.png`): Feld auf der x-Achse, Frequenz auf der y-Achse.

> **Einfacher Vergleich ohne Statistik** (PolderFit minus FTF je Frequenz, nur Werte und Differenzen, schöne Plots): eigener Ordner `einfacher_vergleich_2026-08-25/` (Bericht `VERGLEICH_EINFACH.md`, Abbildungen, CSV, PDF) – erzeugt mit `python benchmark_ftf/einfacher_vergleich.py`; unabhängig von den älteren Ergebnissen unter `ergebnisse/`.

**Ziel:** Bereits mit dem FTF („fiddling together FMR", P. Louis / M. Weiler,
LabVIEW) ausgewertete bbFMR-Datensätze vom Gruppenlaufwerk
(`smb://badwwmi-119-cha.wmi.badw.de/users`) mit PolderFit neu auswerten und die
Ergebnisse (Resonanzfeld, Linienbreite je Frequenz; g, µ₀M_eff, µ₀H_u, α, µ₀ΔH₀
aus Kittel/LLG) kritisch vergleichen. Stichprobenartig, Schwerpunkt CoFe
(Standardfall, schmale Linien), dazu YIG (sehr schmal) und FeCr₂S₄ (extrem breit).

**Kurzfassung:**

* **Die Fitmodelle sind äquivalent.** Auf *demselben Feldfenster* liefern
  PolderFit und FTF identische Einzelfit-Ergebnisse (B_res auf 10⁻⁵ T,
  ΔH auf 0,1 %; FeCr₂S₄ mit angehobenem α-Limit sogar auf 0,0 %). PolderFits
  Kittel-/LLG-Fitter reproduziert auf den FTF-Einzelfitwerten die FTF-Kittel-Werte
  (g, M_eff, α, ΔH₀) innerhalb ≤ 1σ.
* **Gefundene Ursache für Abweichungen (CoFe):** allein das *Fitfenster*. PolderFits
  Auto-Fenster (Faktor 8 auf die Magnituden-FWHM ≈ ±7 ΔH) war auf strukturiertem
  Untergrund zu breit → ΔH systematisch 3–14 % zu klein, α im LLG-Fit 13–15 %
  zu klein. Bis ≈ ±3 ΔH ist ΔH fensterunabhängig (Plateau) – dort liegen die
  von Hand gewählten FTF-Fenster.
  **Behoben:** zweiter Fit-Durchgang auf B_res ± 2,5·ΔH (neuer Parameter
  „Nachfenster", Standard 2,5). Danach: ΔH-Abweichung Median +0,1 % / −0,2 %,
  |z| ≤ 2 für 95–100 % der Punkte; g, M_eff, H_u, α, ΔH₀ stimmen mit dem FTF
  innerhalb 1σ überein (CoFe 290 K und 5 K, ungewichteter Kittel/LLG-Fit).
* **PolderFit-Defekte, die der Benchmark aufgedeckt hat (behoben):**
  1. Kittel-ip-Fit ist unter (M_eff, H_u) → (−M_eff, H_u+M_eff) exakt entartet;
     PolderFit landete je nach Startwert auf dem unphysikalischen Ast
     (YIG: M_eff = −0,13 T, H_u = +125 mT statt +0,13 T / −4 mT wie FTF).
     Jetzt Schranke µ₀M_eff ≥ 0 (und interne g-Parametrisierung, damit die
     Kovarianz mit Schranken korrekt bleibt).
  2. Harte α-Obergrenze 0,1 im Einzelfit – FeCr₂S₄ (α ≈ 0,2–0,8) war damit
     unfittbar. Jetzt Parameter „α-Obergrenze" (Standard 0,1; im Dialog bis 2).
* **Nicht behoben (dokumentierte Grenze):** Die *Fenster-Automatik* ist für
  Resonanzen mit ΔH ≳ 0,3–2 T (FeCr₂S₄) nicht ausgelegt (Deckel ±0,4 T,
  Untergrund-Polynom verschluckt die Linie). Mit α-Limit 1,0 liefert der Auto-Fit
  bei 100 K immerhin g = 1,74 vs. FTF 1,76 und α = 0,21 vs. 0,22, aber ~50 %
  der Einzelfits bleiben problematisch. Auf manuell gesetzten (FTF-)Fenstern
  ist das Ergebnis identisch.
* **Auch das FTF hat Schwächen:** mehrere FTF-Kittel-Ergebnisse auf dem Laufwerk
  sind erkennbar unbrauchbar (g = 4,000 an der Fitgrenze mit Fehler 10⁸;
  FeCr₂S₄ 2 K: α = 0,79, ΔH₀ = −0,85 T). Ein FTF-Ordner enthält 6 identische
  Parameterdateien (Kopierfehler). Und: FTFs oop-„M eff" hat das *umgekehrte
  Vorzeichen* zu µ₀M_eff in PolderFit (FTF: B_res = ω/γ − M).
* **Gewichtung:** Der (zwischenzeitliche) GUI-Standard „Kittel/LLG gewichtet
  (1/u²)" wich bei CoFe teils um mehrere σ vom FTF (ungewichtet) ab und lag
  einmal 5 % daneben (g = 2,03 vs. 2,16), weil wenige Punkte mit winzigen
  formalen Fehlern dominieren; ungewichtet trifft das FTF überall.
  **Entschieden:** Standard ist „ungewichtet" (wie vorher/FTF), Gewichtung
  bleibt als Option wählbar.

---

## 1. Datenauswahl

!!! warning "Einordnung (Hinweis des Betreuers, 2026-08-17)"
    Gefittet werden sollen vorrangig **Linescan-Messungen** (Feldsweep bei
    fester Frequenz, „Linescan-2D-map…"). Alle hier benutzten FTF-Referenzen
    sind dagegen **umsortierte Colormaps** (Frequenzsweeps bei festem Feld,
    per `Sort-linescan-by-frequency-and-set-range.py` in Feldschnitte
    umsortiert; Dateinamen „…colormap…-sorted"). Echte Linescan-Messungen mit
    FTF-Auswertung wurden auf dem Laufwerk (Weber, Grammer, Mayer, bis Tiefe 3)
    nicht gefunden. Die Aussage „Modelle äquivalent auf gleichem Fenster" gilt
    unabhängig vom Messmodus (gleiche Rohpunkte, gleicher Fit); die
    Fenster-/Untergrund-Befunde sollten aber auf einer echten Linescan-Messung
    nachgeprüft werden, sobald dafür eine FTF-Auswertung vorliegt.

Auf dem Laufwerk existieren 821 Ordner „…(FTF)". Vollständig ausgewertet
(Suszeptibilitätsfit **und** Kittel/LLG) und mit der zugehörigen TDMS-Rohdatei
daneben – ausgewählt wurden 9 Datensätze:

| Kürzel | Probe / Messung | Quelle (Laufwerk) | Geometrie | Linescans | Bemerkung |
|---|---|---|---|---|---|
| `cofe_wm_ip_290K_1` | CoFe, ip, 290 K, 20–66 GHz | Wendelin Mayer/67GHz-Dipstick…/2024-JUN-28-CoFe-ip-colormap-290K_0dBm-sorted-1st-part | ip | 70 | Standardfall CoFe |
| `cofe_wm_ip_290K_2` | CoFe, ip, 290 K, 6–19 GHz | …-2nd-part | ip | 21 | FTF-Kittel unbrauchbar (g = 4 an Grenze) |
| `cofe_wm_ip_5K_1` | CoFe, ip, 5 K, 20–66 GHz | 2024-JUN-30-…-5K…-1st-part | ip | 71 | Standardfall CoFe |
| `cofe_wm_ip_5K_2` | CoFe, ip, 5 K, 6–19 GHz | …-2nd-part | ip | 21 (13 im FTF) | FTF-Kittel unbrauchbar |
| `cofe_gratings_ip_5K` | CoFe-Gitter 138 nm, ip, 5 K, 24–50 GHz | Johannes Weber/CoFe-Si-Gratings 138nm/ip-138nm/ip-parallel-colormap-5K-sorted-2 | ip | 1061 | grob abgetastet (85 Punkte, 2,3 mT Schritt, ΔH ≈ 40–60 mT) |
| `yig_konstanz_ip_50K` | YIG 180 nm, ip, 50 K, 5–50 GHz | Matthias Grammer/YIG_Konstanz_180nm/…-Kit-pos-j10_dH0.1 | ip | 367 | sehr schmale Linien, nur 22–24 Punkte je Linescan |
| `fecr2s4_50K` | FeCr₂S₄, 50 K, 10–69 GHz | Johannes Weber/FeCr2S4/01-04-2026/2026-APR-14-…50K…-sorted | oop | 85 | ΔH ≈ 0,24–1,9 T, α ≈ 0,4 |
| `fecr2s4_100K` | FeCr₂S₄, 100 K, 2–69 GHz | …2026-APR-15-…100K…-sorted | oop | 97 | ΔH ≈ 0,15–1,3 T, α ≈ 0,2 |
| `fecr2s4_2K` | FeCr₂S₄, 2 K, 20–50 GHz, nur 5,5–6 T | …2026-APR-09-…2K…-sorted | oop | 429 | Feldbereich < Linienbreite; FTF-Kittel unbrauchbar |

Ein weiterer CoFe-Ordner (`CoFe-Silicon-Konstanz/2024-OCT-21-bbFMR-5K-sorted(FTF)`)
wurde verworfen: er enthält nur 6 Parameterdateien mit identischen Werten
(FTF-Kopierfehler), keine belastbare Referenz.

Was das FTF ablegt und wie es gelesen wurde:

* `1. FMR-Susceptibility Fit/Resonance Fit.dat` – Tabelle je Frequenz: `Hres1`,
  `dH1` (± Fehler), Offsets/Steigungen, R². **`dH` ist laut „FTF Formula
  Document" die FWHM** (ΔH/2 = αω/(µ₀γ)) in Tesla → direkt vergleichbar mit
  PolderFits `mu0_dH_T = 2ωα/γ`.
* `1. FMR-Susceptibility Fit/Resonance Fit/<f>.dat` – **das tatsächlich gefittete
  Feldfenster**, Messwerte, Fitkurve, Residuen je Frequenz. Damit lässt sich der
  Fenster-Effekt vom Modell-Effekt trennen (Abschnitt 4).
* `2. FMR-Kittel+LLG Fit/Resonance 1_Kittel+LLG Fit.dat` – g, M_eff, [H_aniso
  (nur ip)], α, ΔH₀ mit Fehlern.

## 2. Vorgehen

Skript `benchmark_ftf/run_benchmark.py` (Aufruf aus dem Repo-Wurzelverzeichnis):

```
python benchmark_ftf/run_benchmark.py                       # alle Datensätze, GUI-Standardparameter
python benchmark_ftf/run_benchmark.py --nachfenster 0 --suffix _einpass   # ohne 2. Durchgang (alter Stand)
python benchmark_ftf/run_benchmark.py --alpha-max 1.0 --suffix _alphamax1 fecr2s4_50K fecr2s4_100K fecr2s4_2K
python benchmark_ftf/tabellen.py [_suffix]                  # Markdown-Tabellen aus den JSON-Ergebnissen
```

Je Datensatz: TDMS mit `lade_tdms` laden → `fitte_alle` (Standard: γ für g = 2,
Fensterfaktor 8, α erwartet 0,01) → Zuordnung zu den FTF-Zeilen über die Frequenz
(Toleranz 2 MHz) → je Frequenz Differenz von B_res und ΔH, kombinierte 1σ
(σ = √(σ_PF² + σ_FTF²)) und z-Score → Kittel/LLG mit `auswertung_kittel_llg`
(Geometrie wie im FTF-Kopf: „H aniso" vorhanden ⇒ ip), gewichtet und ungewichtet
→ Isolationstest: PolderFits Kittel/LLG-Fitter auf den **FTF-Punkten** (trennt
Einzelfit-Unterschiede von Kittel-Fit-Unterschieden). Ausgabe:
`benchmark_ftf/ergebnisse/<name>.{png,_z.png,csv,json}` und
`zusammenfassung*.json`.

## 3. Ergebnisse (Endstand, mit den Korrekturen aus Abschnitt 5)

### 3.1 Einzelfits je Frequenz

Nur Frequenzen, bei denen beide Programme einen gültigen Fit haben
(PolderFit nicht „problematisch", FTF Hres ≠ 0). z = (PF − FTF)/σ_komb.

| Datensatz | n (zugeordnet) | PF problematisch | ΔB_res = B(PF)−B(FTF), Median (p16..p84) [mT] | \|z_B\| ≤ 2 | ΔH(PF)/ΔH(FTF)−1, Median (p16..p84) | \|z_ΔH\| ≤ 2 |
|---|---|---|---|---|---|---|
| cofe_gratings_ip_5K | 1061 | 0 | +0.75 (−1.95 .. +3.01) | 60 % | −10.6 % (−19.5 .. −2.9) | 47 % |
| cofe_wm_ip_290K_1 | 70 | 0 | −0.04 (−0.17 .. +0.07) | 93 % | +0.1 % (−0.9 .. +0.7) | 100 % |
| cofe_wm_ip_290K_2 | 21 | 0 | −0.03 (−0.04 .. −0.01) | 86 % | +0.1 % (−0.5 .. +0.5) | 95 % |
| cofe_wm_ip_5K_1 | 71 | 0 | −0.03 (−0.15 .. +0.01) | 100 % | −0.2 % (−0.6 .. +0.2) | 100 % |
| cofe_wm_ip_5K_2 | 13 | 0 | +0.25 (−0.11 .. +0.30) | 46 % | −0.7 % (−1.6 .. +1.8) | 100 % |
| yig_konstanz_ip_50K | 367 | 0 | −0.18 (−0.47 .. +0.13) | 100 % | +1.0 % (−1.2 .. +3.8) | 100 % |
| fecr2s4_100K | 90 | 84 | −567 | 0 % | −99 % | 0 % |
| fecr2s4_50K | 85 | 83 | +599 | 0 % | −99 % | 0 % |
| fecr2s4_2K | 245 | 242 | −46 | 33 % | −96 % | 0 % |

Zum Vergleich der **alte Stand** (ein Fit-Durchgang auf dem Detektionsfenster,
`--nachfenster 0`; vollständige Tabelle in `ergebnisse/tabellen_einpass.md`):

| Datensatz | ΔB_res Median [mT] | \|z_B\| ≤ 2 | ΔH rel. Median (p16..p84) | \|z_ΔH\| ≤ 2 |
|---|---|---|---|---|
| cofe_gratings_ip_5K | +0.72 | 62 % | −14.2 % (−20.6 .. −4.5) | 32 % |
| cofe_wm_ip_290K_1 | +0.11 | 49 % | −5.9 % (−9.0 .. −0.9) | 27 % |
| cofe_wm_ip_290K_2 | −0.11 | 29 % | −2.6 % (−4.0 .. −2.0) | 10 % |
| cofe_wm_ip_5K_1 | +0.04 | 86 % | −6.8 % (−10.2 .. −1.6) | 39 % |
| cofe_wm_ip_5K_2 | +0.09 | 92 % | −1.2 % (−2.2 .. +0.5) | 100 % |
| yig_konstanz_ip_50K | −0.18 | 100 % | +0.9 % (−2.1 .. +3.9) | 100 % |

### 3.2 Kittel/LLG (globale Parameter)

Vollständige Tabellen: `ergebnisse/tabellen_final.md`. Auszug (α in 10⁻³, H_u und
ΔH₀ in mT):

**cofe_wm_ip_290K_1** (ip)

| Quelle | g | µ₀M_eff [T] | µ₀H_u [mT] | α [10⁻³] | µ₀ΔH₀ [mT] |
|---|---|---|---|---|---|
| FTF (LabVIEW) | 2.1053 ± 0.0026 | 2.2492 ± 0.0098 | 3.14 ± 0.43 | 7.378 ± 0.199 | −1.01 ± 0.61 |
| PolderFit, ungewichtet | 2.1054 ± 0.0025 | 2.2496 ± 0.0096 | 3.05 ± 0.47 | 7.338 ± 0.187 | −0.92 ± 0.57 |
| PolderFit, gewichtet (Option) | 2.1008 ± 0.0039 | 2.2623 ± 0.0124 | 3.01 ± 0.31 | 5.971 ± 0.289 | 1.40 ± 0.54 |
| PF-Fitter auf FTF-Punkten | 2.1044 ± 0.0028 | 2.2529 ± 0.0107 | 2.96 ± 0.53 | 7.375 ± 0.200 | −1.01 ± 0.61 |
| *alter Stand, ungewichtet* | 2.1025 ± 0.0020 | 2.2550 ± 0.0078 | 3.36 ± 0.39 | 6.417 ± 0.14 | 0.53 ± 0.42 |

**cofe_wm_ip_5K_1** (ip)

| Quelle | g | µ₀M_eff [T] | µ₀H_u [mT] | α [10⁻³] | µ₀ΔH₀ [mT] |
|---|---|---|---|---|---|
| FTF (LabVIEW) | 2.1048 ± 0.0026 | 2.3104 ± 0.0097 | 4.62 ± 0.40 | 7.857 ± 0.192 | −0.13 ± 0.59 |
| PolderFit, ungewichtet | 2.1065 ± 0.0026 | 2.3049 ± 0.0103 | 4.76 ± 0.48 | 7.818 ± 0.192 | −0.06 ± 0.59 |
| PolderFit, gewichtet (Option) | 2.1142 ± 0.0036 | 2.2756 ± 0.0128 | 6.02 ± 0.48 | 8.119 ± 0.270 | −1.18 ± 0.64 |
| PF-Fitter auf FTF-Punkten | 2.1041 ± 0.0027 | 2.3131 ± 0.0104 | 4.50 ± 0.48 | 7.854 ± 0.192 | −0.13 ± 0.59 |
| *alter Stand, ungewichtet* | 2.1016 ± 0.0023 | 2.3175 ± 0.0090 | 4.91 ± 0.42 | 6.676 ± 0.13 | 1.65 ± 0.41 |

**cofe_gratings_ip_5K** (ip; grob abgetastet, FTF-Fenster ≈ ±1 ΔH)

| Quelle | g | µ₀M_eff [T] | µ₀H_u [mT] | α [10⁻³] | µ₀ΔH₀ [mT] |
|---|---|---|---|---|---|
| FTF (LabVIEW) | 2.1585 ± 0.0080 | 1.7422 ± 0.0251 | 184.96 ± 1.51 | 11.532 ± 0.365 | 20.73 ± 0.91 |
| PolderFit, ungewichtet | 2.1111 ± 0.0123 | 1.8861 ± 0.0408 | 177.40 ± 2.24 | 9.717 ± 0.19 | 18.89 ± 0.47 |
| PolderFit, gewichtet (Option) | 2.0295 ± 0.0109 | 2.1695 ± 0.0391 | 164.46 ± 1.63 | 9.258 ± 0.18 | 18.69 ± 0.42 |
| PF-Fitter auf FTF-Punkten | 2.1692 ± 0.0083 | 1.7094 ± 0.0260 | 186.84 ± 1.66 | 11.589 ± 0.37 | 20.73 ± 0.91 |

**yig_konstanz_ip_50K** (ip)

| Quelle | g | µ₀M_eff [T] | µ₀H_u [mT] | α [10⁻³] | µ₀ΔH₀ [mT] |
|---|---|---|---|---|---|
| FTF (LabVIEW) | 2.0006 ± 0.0003 | 0.1319 ± 0.0018 | −4.48 ± 0.71 | 1.584 ± 0.046 | 16.52 ± 0.10 |
| PolderFit, ungewichtet | 2.0010 ± 0.0003 | 0.1303 ± 0.0021 | −3.75 ± 0.83 | 1.784 ± 0.048 | 16.36 ± 0.10 |
| PolderFit, gewichtet | 2.0011 ± 0.0003 | 0.1291 ± 0.0021 | −3.28 ± 0.84 | 1.788 ± 0.050 | 16.40 ± 0.10 |
| PF-Fitter auf FTF-Punkten | 2.0006 ± 0.0003 | 0.1320 ± 0.0019 | −4.51 ± 0.73 | 1.584 ± 0.046 | 16.52 ± 0.10 |
| *alter Stand (vor Fix Kittel-ip)* | 2.0009 | **−0.1314** | **+127.2** | 1.894 | 16.07 |

**fecr2s4_100K** (oop; PolderFit mit `--alpha-max 1.0`, sonst keine gültigen Fits)

| Quelle | n | g | µ₀M_eff [T] | α | µ₀ΔH₀ [mT] |
|---|---|---|---|---|---|
| FTF (LabVIEW) | 90 | 1.7595 ± 0.0065 | −0.2040 ± 0.0063 (FTF-Vorzeichen) | 0.218 ± 0.004 | −37 ± 12 |
| PolderFit ungewichtet, α_max = 1 | 46 | 1.740 ± 0.010 | 0.168 ± 0.010 | 0.209 ± 0.006 | +15 ± 20 |
| PF-Fitter auf FTF-Punkten | 90 | 1.7616 ± 0.0065 | +0.2059 ± 0.0063 | 0.219 ± 0.004 | −37 ± 12 |

FeCr₂S₄ 50 K analog (FTF g = 1,80, α = 0,43; PolderFit α_max = 1: nur 11 gültige
Fits, g = 1,77 ± 0,09, α = 0,20 ± 0,08 – nicht belastbar). FeCr₂S₄ 2 K: Feldbereich
5,5–6 T ist kleiner als die Linienbreite; **beide** Kittel-Fits sind unbrauchbar
(FTF: g = 4,000 an der Grenze, α = 0,79, ΔH₀ = −0,85 T; PolderFit: g = 4,7–5,8).

## 4. Ursachenanalyse

### 4.1 Gleiches Fenster ⇒ gleiches Ergebnis (Modell-Äquivalenz)

Die FTF-Kurvendateien enthalten das tatsächlich gefittete Fenster. PolderFit auf
genau diesen Punkten (`fitte_linescan(schneide_band(ls, lo, hi))`), CoFe 290 K:

| f [GHz] | FTF-Fenster [T] (n) | PF-Auto-Fenster [T] (n) | ΔH FTF | ΔH PF (Auto, alt) | ΔH PF (FTF-Fenster) | B_res FTF / PF(FTF-Fenster) |
|---|---|---|---|---|---|---|
| 20.11 | 0.170–0.205 (40) | 0.123–0.253 (146) | 10.48 | 10.34 | **10.47** | 0.18802 / 0.18802 |
| 43.55 | 0.682–0.771 (101) | 0.589–0.865 (310) | 23.06 | 21.00 | **23.06** | 0.72914 / 0.72914 |
| 57.62 | 1.079–1.176 (108) | 0.951–1.280 (367) | 29.36 | 25.79 | **29.40** | 1.12796 / 1.12793 |
| 62.31 | 1.216–1.320 (116) | 1.100–1.390 (323) | 31.31 | 28.54 | **31.27** | 1.26747 / 1.26749 |

Die Residuenquadratsumme von PolderFit auf dem FTF-Fenster ist dabei durchweg
gleich oder minimal kleiner als die des FTF (z. B. 4,64e-8 vs. 4,75e-8) – der
Optimierer ist nicht das Problem. Für FeCr₂S₄ gilt dasselbe, sobald das α-Limit
nicht greift: Median ΔB = 0,0 mT, ΔH-Abweichung 0,0 % auf den FTF-Fenstern.

### 4.2 Fensterabhängigkeit der Linienbreite (CoFe 290 K, Fenster = B_res ± k·ΔH_FTF)

| f [GHz] | ΔH FTF | k = 1 | 1.5 | 2 | 3 | 4 | 6 | 8 | 12 |
|---|---|---|---|---|---|---|---|---|---|
| 20.11 | 10.48 | 10.54 | 10.49 | 10.45 | 10.47 | 10.48 | 10.36 | 10.22 | 9.28 |
| 43.55 | 23.06 | 23.13 | 23.24 | 22.95 | 23.01 | 21.96 | 20.99 | 20.62 | 20.39 |
| 57.62 | 29.36 | 28.95 | 29.23 | 28.96 | 27.46 | 26.34 | 25.79 | 25.27 | 25.19 |
| 62.31 | 31.31 | 31.90 | 31.76 | 30.81 | 29.36 | 28.74 | 28.58 | 28.22 | 28.05 |

Plateau bis k ≈ 2–3, danach monotone Drift nach unten. Ursache in den Daten
(siehe `ergebnisse/_diag_cofe290K_fenster.png`): im ±7-ΔH-Fenster liegen
Untergrundstrukturen (Nachbarsignal bei 0,29 T, langsame Ripple, Krümmung), der
lineare Untergrund des Modells passt dort nicht mehr und die Linienbreite
kompensiert. Ein quadratischer Untergrund behebt das nur teilweise. Auf ±2–2,5 ΔH
sind die Residuen strukturlos. PolderFits altes Auto-Fenster
(`halb = 8·FWHM_Magnitude/2 = 4·√3·ΔH ≈ 7 ΔH`) lag im Drift-Bereich; die
FTF-Nutzer wählten von Hand ≈ ±1,7–2 ΔH.

Test des zweiten Durchgangs (Refit auf B_res ± k·ΔH_fit) für k = 2 / 2,5 / 3 / 4:
ΔH-Median-Abweichung zum FTF −0,1 / +0,1 / −0,1 / −2,0 % (290 K) bzw. −0,1 / −0,2 /
−0,7 / −4,6 % (5 K). Gewählt: **k = 2,5** (voll auf dem Plateau, aber mit mehr
Untergrundpunkten als k = 2).

### 4.3 CoFe-Gitter: fensterinstabil auf beiden Seiten

85 Punkte je Linescan bei 2,3 mT Schritt und ΔH ≈ 40–60 mT: das FTF-Fenster
(≈ 44 Punkte ≈ ±1 ΔH) ist *schmaler als die Linie*, PolderFit fittet den ganzen
Linescan (±2 ΔH). Auf gleichem Fenster stimmen beide überein, aber ΔH schwankt je
nach Fenster um ±15 % (z. B. 26,46 GHz: 37,6 → 30,0 mT für k = 1,5 → 3). Keines der
Ergebnisse ist hier „richtig"; g/M_eff/H_u weichen 1–2σ ab, α um 15 %. Datenlimit,
kein Programmfehler.

### 4.4 YIG: Einzelfits identisch, α trotzdem 12 % verschieden

ΔH-Differenz frequenzabhängig 0 % (5–10 GHz) bis +2,8 % (35–40 GHz), d. h.
0,3–0,6 mT bei 20 mT. Weil ΔH(f) bei YIG fast flach ist (2αω/γ ≈ 6 mT bei
50 GHz gegen ΔH₀ = 16,5 mT), schlägt das im LLG-Fit voll auf α durch (1,78 vs.
1,58 · 10⁻³, 4σ). g/M_eff/H_u stimmen. Linescans haben nur 22–24 Punkte;
FTF-Fenster unbekannt. Nicht entscheidbar, wer näher an der Wahrheit liegt.

### 4.5 FeCr₂S₄: α-Deckel und Fenster-Automatik

Ohne Änderung: 83–84 von 85–90 Einzelfits problematisch („alpha an Grenze",
„alpha unphysikalisch"), da `ALPHA_MAX = 0,1` hart in den Fitschranken lag und
das Auto-Fenster (Deckel `_HALB_MAX = 0,4 T`, Untergrund-Polynom Grad ≤ 6 auf
2–4 T Spannweite) Linien mit ΔH = 0,3–2 T nicht erfasst. Mit `--alpha-max 1.0`
(neuer Parameter): 100 K → 44/90 gültig, g = 1,74 vs. 1,76, α = 0,21 vs. 0,22;
50 K → 11/85 gültig. Auf den FTF-Fenstern exakt gleich (4.1). Die
Fenster-Automatik für solche Linien zu erweitern ist ein eigenes Vorhaben
(Deckel und Untergrund-Grad an die Linienbreite koppeln).

### 4.6 Befunde zum FTF selbst

* Kittel-ip-Fits mit g = 4,000 ± 10⁸ (`cofe_wm_ip_290K_2`, `_5K_2`,
  `fecr2s4_2K`): der LabVIEW-Fit hängt an einer Parametergrenze; M_eff = 0,5 T
  und H_aniso = 5–19 mT sind dann Artefakte. Die Einzelfits (Hres, dH) dieser
  Ordner sind dagegen in Ordnung – PolderFit reproduziert sie (ΔH-Median +0,1 %).
* oop-„M eff" im FTF ist −µ₀M_eff (PolderFit-Konvention B_res = µ₀M_eff + ω/γ,
  FTF offenbar B_res = ω/γ − M): FeCr₂S₄ 100 K FTF −0,204 T, PolderFit-Fitter auf
  denselben Punkten +0,206 T bei gleichem g. Beim Vergleich Vorzeichen beachten.
* `CoFe-Silicon-Konstanz/2024-OCT-21-bbFMR-5K-sorted(FTF)`: 6 Parameterdateien
  mit identischem Inhalt (Kopie einer Frequenz).

## 5. Änderungen in PolderFit (dieser Benchmark)

| Änderung | Datei(en) | Wirkung |
|---|---|---|
| Zweiter Fit-Durchgang auf B_res ± `nachfenster_faktor`·ΔH (Standard 2,5; 0 = aus); nur übernommen, wenn der Nachfit unproblematisch ist; nie erweitern, ≥ 12 Punkte | `fit/batch.py` (`nachfenster`, `fitte_mit_nachfenster`, `fitte_alle`), `fit/fenster_steuerung.py` (Bereichs-/Geraden-Fit) | ΔH fensterunabhängig; CoFe-α stimmt mit FTF überein |
| α-Obergrenze als Parameter (`alpha_max`, Standard 0,1) durch Startwerte, Fitschranken, Bewertung (Plausibilitätsgrenze = halbe Schranke), Stapel, `fitte_neu`, Persistenz | `physik/fitmodell.py`, `fit/linescan_fit.py`, `fit/kriterien.py`, `fit/batch.py`, `persistenz/projekt.py` | breite Resonanzen (FeCr₂S₄) fitbar |
| Kittel-ip: Schranke µ₀M_eff ≥ 0, interne g-Parametrisierung (korrekte Kovarianz mit Schranken) | `physik/kittel_llg.py` | eindeutiger, physikalischer Ast wie FTF |
| GUI: Dialog „Physikalische Parameter" mit „α-Obergrenze" und „Nachfenster (± ΔH-Vielfache)"; Hauptfenster reicht beides in Auto-Fit/Nachfits durch | `gui/parameter_dialog.py`, `gui/hauptfenster.py` | einstellbar, Standard = Benchmark-Empfehlung |
| Tests | `tests/test_benchmark_ftf_fixes.py` (13 Tests) | Regression |

Sitzungsdateien speichern `alpha_max`/`nachfenster_faktor` (ältere Sitzungen ⇒
Standardwerte).

## 5a. Regressionsprüfung: AutoWindow-Harness (286 reale Dateien, 12 GB)

`tests/autowindow_runner.py --no-plots` nach den Änderungen (Ergebnis in
`tests/autowindow_results.json`, Vorher-Stand aus dem Repo):

| | vorher | nachher (Nachfenster 2,5) |
|---|---|---|
| bewertbare Resonanzen (213 gemeinsame OK-Dateien) | 122 332 | 122 332 |
| OK | 100 725 (82,3 %) | **102 086 (83,4 %)** |
| WINDOW_FLAGGED (Problem gemeldet) | 21 093 | 19 684 |
| WINDOW_FAIL (still) | 514 (0,42 %) | 562 (0,46 %) |
| OK + FLAGGED | 99,58 % | 99,54 % |

Die 48 zusätzlichen stillen FAILs sind ausnahmslos Klasse `FENSTER_LEER` der
unabhängigen Prüfung – ein Artefakt: auf dem verengten Fenster (±2,5 ΔH)
verschluckt das Prüf-Polynom des Harness einen Teil der Linie und meldet
„keine Resonanz im Fenster", obwohl B_res und ΔH korrekt sind. Insgesamt
verschiebt der zweite Durchgang ~1 400 Fits von „gemeldet problematisch" nach
„OK". Die 30 früheren `NICHT_FMR`-Dateien erschienen zunächst als `CRASH`, weil
der Harness nur die alte Fehlermeldung des Laders abfing (seit dem Kanal-Mapping
`MappingErforderlich`) – Harness angepasst. TIMEOUTs (90 s je Datei; 26 vorher,
36 nachher) hängen von der Maschinenlast ab: die betroffenen Dateien brauchen
schon einzeln 40–50 s (1001 Linescans, viele problematische Fits) und kippen
mit 8 parallelen Workern über die Schwelle. Der zweite Durchgang selbst kostet
gemessen ~2 % Fitzeit (51,3 → 52,2 s bzw. 37,2 → 38,5 s), weil problematische
Fits nicht nachgefittet werden.

## 6. Empfehlungen / offene Punkte

1. **Kittel/LLG-Gewichtung:** „gewichtet (1/u²)" liefert bei CoFe Werte, die
   mehrere σ vom ungewichteten Fit (= FTF) abweichen (290 K: α 5,97 vs.
   7,34 · 10⁻³; Gitter: g 2,03 vs. 2,11/2,16). Die formalen Einzelfehler sind
   viel kleiner als die Punktstreuung, wenige Punkte dominieren. Standard ist
   daher „ungewichtet" (Gewichtung optional); wer gewichtet, sollte die Gewichte
   deckeln (z. B. σ_i ≥ Median σ / 3).
2. **Sehr breite Linien (ΔH ≳ 0,3 T):** Fenster-Automatik erweitern
   (`_HALB_MAX` und Untergrund-Grad an die geschätzte Linienbreite koppeln);
   bis dahin: „α-Obergrenze" anheben + Bereichs-Fit mit manuellem Fenster.
3. **Weitere Stichproben:** Py/CoFeB-Ordner (Vincent, Manuel: 370+139 FTF-Ordner,
   meist ohne Kittel-Datei) und Grammers YIG-Serien wären mit demselben Skript
   in Minuten prüfbar (`benchmark_ftf/data/<name>/` anlegen: TDMS + `ftf/`).

## 7. Reproduktion

Daten liegen lokal unter `benchmark_ftf/data/<name>/` (TDMS + FTF-Tabellen +
FTF-Kurven; Quelle in `quelle.txt`; nicht versioniert – Kopien vom Gruppenlaufwerk).
Ergebnisse: `benchmark_ftf/ergebnisse/` (PNG je Datensatz + `_z.png`
z-Score-Histogramme, CSV je Frequenz, JSON, Logs `lauf*.log`, Tabellen
`tabellen_*.md`).

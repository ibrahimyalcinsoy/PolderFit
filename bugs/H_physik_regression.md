# Bereich H – Physik-Regression HEAD (V0.1.66, e3b1ea7) vs. Referenz 7c893e8

Stand 2026-09-03. Alle Zahlen aus eigenen Laeufen, Skripte und JSONs liegen in
diesem Ordner.

## Kurzergebnis

**Kein Bug gefunden.** Auf identischem Feldfenster liefern HEAD und 7c893e8
**bitgleiche** Einzelfits und Kittel/LLG-Werte, sobald beide Staende mit
DERSELBEN numpy/scipy-Version laufen. Die einzige beobachtete Abweichung
(1 von 90 Frequenzen bei FeCr2S4) stammt nachweislich aus den unterschiedlich
bestueckten venvs (HEAD: numpy 2.4.6 / scipy 1.17.1, Referenz-Worktree:
numpy 2.5.2 / scipy 1.18.1), nicht aus dem Code. Der volle Auto-Fit-Pfad
(AutoWindows + `fitte_alle` + Kittel/LLG) ist auf beiden Datensaetzen
elementweise identisch und reproduziert die in `benchmark_ftf/BERICHT.md`
dokumentierten Referenzwerte exakt. Auch die Achsenpruefung (Feld auf x,
Frequenz auf y) ergab keinen Verstoss.

## 1. Skript und erzwungenes Feldfenster

`regression_vergleich.py` (dieser Ordner; pathlib, `encoding="utf-8"`, keine
neuen Abhaengigkeiten, API-Zugriffe ueber `_hole()` mit klarer Fehlermeldung,
welche Funktion fehlt – daher unveraendert ins Repo uebernehmbar).

Lauf-Modus (mit dem Interpreter des jeweiligen Standes, importiert das dort
installierte `polderfit`):

```
python regression_vergleich.py --label head --datensatz cofe_wm_ip_290K_1 \
    --daten /home/ibrahim/Dokumente/Ananas/benchmark_ftf/data \
    --alpha-max 0.1 --aus head_cofe_wm_ip_290K_1.json
```

Vergleichs-Modus:

```
python regression_vergleich.py --vergleich a.json b.json --md bericht.md
```

**Wie das Fenster erzwungen wird:** nicht aus den Daten geschaetzt
(AutoWindows), sondern deterministisch aus der FTF-Referenztabelle
`benchmark_ftf/data/<satz>/ftf/Resonance Fit.dat`:

```
Fenster(f) = [ Hres_FTF(f) - k*dH_FTF(f) ,  Hres_FTF(f) + k*dH_FTF(f) ],  k = --fensterfaktor (4.0)
```

Fensterbreite also 8*FWHM, wie der GUI-Standard `breite_faktor=8`. Das Fenster
haengt nur von einer Datei und einem Kommandozeilenwert ab und ist deshalb in
beiden Staenden bitgleich; es wird ueber `schneide_band(linescan, unten, oben)`
angewandt und in jeder JSON-Zeile als `fenster_unten`/`fenster_oben`/`n_punkte`
mitgeschrieben (Kontrolle: identische Werte in beiden JSONs, gleiche
Punktzahlen, z. B. 198 Punkte bei 8.4088 GHz).

Je Frequenz werden zwei Varianten gerechnet:

* `fenster` – ein Durchgang: `fitte_linescan(beschnitten, GAMMA_STANDARD, alpha_max=...)`
* `nachfenster` – `fitte_mit_nachfenster(..., nachfenster_faktor=2.5)` mit demselben Startfenster

Kittel/LLG: `auswertung_kittel_llg(..., gewichtet=False)`, Geometrie aus dem
FTF-Kopf ("H aniso" vorhanden ⇒ ip). Ausgabe je Frequenz: B_res, u(B_res), ΔH,
u(ΔH), α, φ, rmse_norm, R², Status/Gruende; global g, µ0M_eff, µ0H_u, α, µ0ΔH0
mit σ. Der Vergleichsmodus schreibt Δ und z = Δ/σ (σ = √(σ_A²+σ_B²)) und
markiert |z| > 1 mit **JA**.

## 2. Ergebnisse

Datensaetze: `cofe_wm_ip_290K_1` (ip, α_max 0.1) und `fecr2s4_100K`
(oop, α_max 1.0).

### 2a. cofe_wm_ip_290K_1 – HEAD vs. REF (je eigenes venv)

70 gemeinsame Frequenzen, `vergleich_cofe_wm_ip_290K_1.md`:

* max |ΔB_res| = 0.103 µT, max |ΔΔH| = 0.039 µT (relativ ~1e-7)
* Frequenzen mit |z| > 1: **0/70**; unterschiedliche Problem-Einstufung: **0**
* Kittel/LLG (1 Durchgang): Δg = 3.1e-08, ΔM_eff = 1.4e-07 T, ΔH_u = 6.6e-09 T,
  Δα = 3.3e-10, ΔΔH0 = 1.0e-11 T → alle z = 0.000
* Mit Nachfenster 2.5 dieselbe Uebereinstimmung (Δg = 3.1e-09).

### 2b. fecr2s4_100K – HEAD vs. REF (je eigenes venv)

90 gemeinsame Frequenzen, `vergleich_fecr2s4_100K.md`:

* 89 von 90 Frequenzen bitgleich; **eine** Frequenz weicht ab: 8.4088 GHz
* Folge: n_punkte im Kittel-Fit 90 (HEAD) vs. 89 (REF); g 1.82645±0.0222 vs.
  1.80047±0.0153 (z = +0.96), M_eff 0.2753±0.0201 vs. 0.2475±0.0144 (z = +1.13),
  α 0.22823 vs. 0.22578 (z = +0.40), ΔH0 −43.9 vs. −47.1 mT (z = +0.18).

Die Frequenz 8.4088 GHz ist ein pathologischer Fit im selben Fenster
[−130.4 mT, 1179.4 mT], 198 Punkte:

| Stand | B_res | u(B_res) | ΔH | α | rmse_norm | Status |
|---|---|---|---|---|---|---|
| HEAD-venv | 1145.74 mT | 20.14 mT | 166.9 mT | 0.2778 | 0.1110 | OK |
| REF-venv | 837.35 mT | 40.53 mT | 458.4 mT | 0.7630 | 0.0703 | problematisch (alpha unphysikalisch, B_res-Unsicherheit zu gross) |

(FTF-Referenz dort: B_res 524.5 mT, ΔH 163.7 mT – beide Loesungen sind falsch;
das erzwungene FTF-Fenster ist bei diesem sehr breiten Signal 1.3 T weit.)

### 2c. Kreuztest: Ursache ist die Bibliotheksversion, nicht der Code

Der Referenz-Quelltext laesst sich per `PYTHONPATH` im HEAD-venv importieren
(geprueft: `polderfit.__file__` zeigt auf `polderfit-ref`, Version 0.1.0):

```
PYTHONPATH=/home/ibrahim/Dokumente/polderfit-ref \
  /home/ibrahim/Dokumente/Ananas/.venv/bin/python regression_vergleich.py \
  --label refcode_headenv --datensatz fecr2s4_100K --alpha-max 1.0 ...
```

* **REF-Code im HEAD-venv** ⇒ exakt die HEAD-Zahlen
  (g = 1.8264464753182394, identisch bis zur letzten Stelle; Vergleich
  `vergleich_fecr2s4_code.md`: max |ΔB_res| = 0.000 µT, 0/90 mit |z| > 1,
  0 abweichende Einstufungen).
* **HEAD-Code im REF-venv** ⇒ exakt die REF-Zahlen (g = 1.8004678607987972,
  n_punkte 89).

Damit ist die Abweichung eindeutig dem MINPACK/LM-Verhalten von
scipy 1.17.1 vs. 1.18.1 (bzw. numpy 2.4.6 vs. 2.5.2) zuzuordnen. Der
PolderFit-Code ist auf dem Ein-Moden-Pfad funktional unveraendert.

### 2d. Voller Auto-Fit-Pfad (AutoWindows + fitte_alle + Kittel/LLG)

`autofit_vergleich.py`, beide Codes im HEAD-venv (Bibliotheks-Confounder
eliminiert), GUI-Standardparameter (Fensterfaktor 8, α erwartet 0.01,
Nachfenster 2.5, ungewichtet):

| Datensatz | Fenster | B_res je Frequenz | ΔH | Problemflags | Kittel | LLG |
|---|---|---|---|---|---|---|
| cofe_wm_ip_290K_1 (ip, α_max 0.1) | identisch | identisch | identisch | identisch | identisch | identisch |
| fecr2s4_100K (oop, α_max 1.0) | identisch | identisch | identisch | identisch | identisch | identisch |

Absolutwerte HEAD (= REF-Code): CoFe g = 2.10543 ± 0.00249,
µ0M_eff = 2.24961 ± 0.00963 T, µ0H_u = 3.053 ± 0.474 mT, 70/70 Fits gut.
FeCr2S4: 97 Fits, 50 problematisch, 46 Punkte im Kittel-Fit,
g = 1.73996 ± 0.00956, µ0M_eff = 0.16803 ± 0.00974 T, α = 0.20893 ± 0.00573,
µ0ΔH0 = +15.05 ± 19.93 mT.

Das deckt sich **exakt** mit `benchmark_ftf/BERICHT.md` (Zeile 218:
„PolderFit ungewichtet, α_max = 1 | 46 | 1.740 ± 0.010 | 0.168 ± 0.010 |
0.209 ± 0.006 | +15 ± 20"). Der HEAD-Stand reproduziert die dokumentierten
Benchmark-Zahlen also unveraendert.

### 2e. Vergleich gegen die FTF-Referenz (BERICHT.md)

Wichtig: Abweichungen zum FTF bestehen, sind aber in HEAD und REF **gleich
gross** – also keine Regression:

* CoFe, Variante mit Nachfenster 2.5: g z = +0.04, M_eff z = +0.03,
  H_u z = −0.14, α z = −0.17, ΔH0 z = +0.12 – alles innerhalb 1σ (HEAD wie REF).
* CoFe, Variante ohne Nachfenster (nur ein Durchgang auf dem FTF-Fenster):
  α z = −3.36, g z = −1.63 – bestaetigt die im Handbuch/BERICHT dokumentierte
  Aussage, dass erst der Nachfenster-Durchgang (2.5·ΔH) die Linienbreite
  fensterunabhaengig macht. Identisch in beiden Staenden.
* FeCr2S4: g z ≈ +2.5 (HEAD) bzw. +2.9 (REF, andere Punktmenge), M_eff mit
  umgekehrtem Vorzeichen zum FTF (in BERICHT.md Zeile 217 ausdruecklich als
  „FTF-Vorzeichen" gekennzeichnet, Betrag 0.204 T vs. 0.206 T beim
  Isolationstest). Kein Regressionsbefund, sondern die bekannte
  Vorzeichenkonvention des LabVIEW-Tools bei oop.

## 3. Code-Abgleich zum Diff (warum keine Regression zu erwarten war)

`git diff 7c893e8 -- polderfit/physik polderfit/fit`: 1267+/80− Zeilen.

* `polderfit/physik/fitmodell.py` (+274): reine Erweiterung. Der
  Ein-Moden-Pfad wurde nur refaktoriert – `schaetze_startwerte` ruft jetzt
  `_untergrund_und_rein()` (fitmodell.py:113–138) auf, das den zuvor inline
  stehenden Block (Sortierung, Randregression je 1/7 der Punkte, B_ref,
  Untergrundabzug) unveraendert enthaelt. Alles Neue (`s21_modell_multi`,
  `residuum_multi`, `schaetze_startwerte_multi`, `startwerte_in_bereichen`,
  `_fwhm_lokal`) wird nur bei `n_moden > 1` bzw. aus den Grenzgeraden-Werkzeugen
  betreten. Numerisch bestaetigt durch 2a/2c (Bitgleichheit).
* `polderfit/fit/linescan_fit.py` (+379): Ein-Moden-Fit unveraendert
  (`fitte_linescan` linescan_fit.py:341–476, gleiche Parameter, Schranken,
  φ-Nebenminimum-Ausweg, `dH = 2ωα/γ`, `dH_err = 2ω·u(α)/γ` aus
  `stderr` des Optimierers, Zeilen 459–460). Neu nur: `_abschliessen()`
  (Zeile 331, ruft dieselbe `bewerte_fit` und merkt sich das Kriterienergebnis
  in `problematisch_auto`), `moden`-Liste, `setze_bewertung`,
  `FitErgebnis.platzhalter`, `fitte_linescan_multi`.
* `polderfit/fit/kriterien.py`: Schwellen unveraendert (ALPHA_MAX 0.1,
  ALPHA_PLAUSIBEL_MAX 0.05, RMSE_NORM_SCHWELLE 0.35,
  B_RES_REL_UNSICHERHEIT_MAX 0.02). `bewerte_fit` bekam den optionalen
  Parameter `alpha_plausibel` (None ⇒ `alpha_plausibel_max(alpha_max)` wie
  bisher) und prueft b–d zusaetzlich fuer Nebenmoden – bei einer Mode
  identische Logik.
* `polderfit/fit/parameter.py` (neu): Defaults exakt wie die validierten
  Werte – `gewichtet = False` (ungewichtet Standard), `alpha_max = ALPHA_MAX`
  (0.1), `nachfenster_faktor = NACHFENSTER_FAKTOR_STANDARD` (2.5, in
  batch.py:36 unveraendert), `breite_faktor = 8.0`, `r2_min = 0.9`,
  `alpha_plausibel = 0.0` (= Automatik), `n_moden = 1`.
* `polderfit/fit/autowindows.py`: nur ein `fortschritt`-Callback in
  `auto_fenster_alle`; Rechenweg unveraendert.
* `polderfit/fit/batch.py` (+269): `fitte_alle` reicht die neuen Optionen
  durch (bei Standardwerten identischer Ablauf), plus `abbruch`,
  `ergaenze_moden` (nur zweistufig), `leerer_stapel`. Numerisch bestaetigt
  durch 2d.
* `polderfit/physik/kittel_llg.py`, `physik/konstanten.py`,
  `physik/suszeptibilitaet.py`, `io/tdms_laden.py`: **byteidentisch** zu
  7c893e8 (`diff` ohne Ausgabe). Damit unveraendert: γ in rad·s⁻¹·T⁻¹
  (`gamma_aus_g`, GAMMA_STANDARD = 1.758820e+11, in beiden Laeufen gleich
  ausgegeben), Felder als µ0H in Tesla, Kittel-ip-Konvention µ0M_eff ≥ 0
  (kittel_llg.py:120), Kittel oop/ip Gl. 2.24/2.26, LLG Gl. 2.28.
* `polderfit/auswertung/uebersicht.py`: nur Extraktion von `ist_guter_fit()`
  aus `_gute_ergebnisse` – identisches Punktkriterium; `gewichtet=False`
  bleibt Standard.
* `polderfit/persistenz/ergebnis_export.py` (+212): ΔH wird weiterhin in
  **Tesla** exportiert (`mu0_dH_T`, `mu0_dH_err_T`); die neuen mT-Spalten
  (`mu0_dH_mT` = `dH*1e3`, linescan_fit.py:122–129) sind additiv. Gleiches
  gilt fuer `B_res_T`/`B_res_mT` und die Kittel/LLG-Werte.

Tests im HEAD: `tests/test_physik.py tests/test_fit.py
tests/test_benchmark_ftf_fixes.py` → 27 passed.

## Befund 1 (kein Code-Bug): Ergebnis haengt von der scipy-Version ab

* **Symptom:** Bei `fecr2s4_100K`, 8.4088 GHz, erzwungenes FTF-Fenster,
  α_max = 1.0 liefert derselbe Code je nach venv zwei verschiedene lokale
  Minima (B_res 1145.7 mT / α 0.278 gegenueber 837.3 mT / α 0.763). Dadurch
  aendert sich die Punktmenge des Kittel-Fits (90 vs. 89) und g um 0.026
  (z = 0.96, knapp unter 1σ).
* **Reproduktion:**
  `python regression_vergleich.py --label X --datensatz fecr2s4_100K
  --alpha-max 1.0 --aus X.json` je Interpreter, dann `--vergleich`.
* **Datei:Zeile:** keine – `polderfit/fit/linescan_fit.py:400` ff.
  (`minimize(..., method="leastsq")`) ist in beiden Staenden identisch;
  unterschiedlich sind nur scipy 1.17.1 vs. 1.18.1 / numpy 2.4.6 vs. 2.5.2.
* **Root Cause:** MINPACK-Levenberg-Marquardt auf einem sehr flachen,
  mehrminimigen Residuum (Fenster 1.31 T breit, ΔH_FTF 164 mT, α_max auf 1.0
  angehoben ⇒ Plausibilitaetsgrenze 0.5, die Kriterien filtern kaum noch).
* **Diff-Ausschnitt zu 7c893e8:** entfaellt (Ein-Moden-Pfad unveraendert;
  siehe Abschnitt 3).
* **Fixvorschlag:** kein Code-Fix. Fuer belastbare Vergleiche die
  Bibliotheksversionen der beiden Worktrees angleichen (z. B. den
  Referenz-Worktree mit `PYTHONPATH` im HEAD-venv fahren, wie in 2c) und in
  `pyproject.toml` fuer Benchmark-Laeufe eine scipy-Untergrenze dokumentieren.
  Falls gewuenscht, unabhaengig davon die Robustheit erhoehen: bei
  `alpha_max > ALPHA_MAX` `alpha_plausibel` bewusst setzen, statt die
  Automatik `alpha_max/2` zu nutzen.
* **Risiko:** niedrig; betrifft nur Datensaetze, bei denen die Linienbreite in
  der Groessenordnung des Fensters liegt (FeCr2S4). Auf dem Auto-Fit-Pfad mit
  Standardparametern trat der Fall in keinem der beiden Datensaetze auf.

## 4. Achsenpruefung (Feld auf x, Frequenz auf y)

Alle Plotstellen in `polderfit/gui`, `polderfit/auswertung`,
`polderfit/persistenz`, `benchmark_ftf`, `docs/abb`. **Kein Verstoss.**

| Datei:Zeile | Plot | x-Achse | y-Achse | Bewertung |
|---|---|---|---|---|
| polderfit/gui/matrix_ansicht.py:405/409 (+411–413) | Farbplot `imshow`, `extent` = (feld_min, feld_max, f_min, f_max) (Zeile 123/278) | Feld µ0H (T) | Frequenz (GHz) | OK |
| polderfit/gui/matrix_ansicht.py:572–591 | Resonanzpunkte/Nebenmoden `plot(B_res, f_GHz)` | Feld | Frequenz | OK |
| polderfit/gui/matrix_ansicht.py:617 | Markierung des aktiven Linescans `axhline(f_ghz)` | – | Frequenz | OK (waagerecht = konstante Frequenz) |
| polderfit/gui/matrix_ansicht.py:878/890/1020 | Grenzgeraden + Griffe in Datenkoordinaten (x = Feld, y = Frequenz) | Feld | Frequenz | OK |
| polderfit/gui/navigator_ansicht.py:50 | Uebersichtsbild, dasselbe `extent` | Feld | Frequenz | OK |
| polderfit/gui/fit_ansicht.py:107–151, 168–170 | Einzel-Linescan Re/Im + Fitkurve, `axvline(B_res)`, Grenzen | Feld µ0H (T) | Re/Im S21 | OK (Einzelscan, keine Frequenzachse) |
| polderfit/gui/auswertung_fenster.py:297/310, 318–319 | Kittel-Dispersion (Punkte + Fitkurve `plot(bb, ff/1e9)`) | Resonanzfeld (T) | Frequenz (GHz) | OK |
| polderfit/gui/auswertung_fenster.py:299/313, 322–323 | Linienbreite + LLG-Gerade | Resonanzfeld (T) | µ0ΔH (mT) | OK (Feld auf x) |
| polderfit/auswertung/uebersicht.py:130–140 | `plot_kittel` | Resonanzfeld (T) | Frequenz (GHz) | OK |
| polderfit/auswertung/uebersicht.py:165–178 | `plot_linienbreite` | Resonanzfeld (T) | µ0ΔH (mT) | OK |
| polderfit/auswertung/uebersicht.py:194–200 | `plot_resonanz_vs_temperatur` | Temperatur (K) | Resonanzfeld (T) | OK (bewusst Temperaturplot) |
| polderfit/auswertung/moden.py | keine Plotfunktion (nur Zweig-/Ausreisserlogik) | – | – | – |
| polderfit/persistenz/ergebnis_export.py | keine Plotfunktion (nur Tabellen/Excel) | – | – | – |
| benchmark_ftf/run_benchmark.py:293–297 | Resonanzfeld FTF vs. PF | µ0H_res (T) | f (GHz) | OK |
| benchmark_ftf/run_benchmark.py:302–307 | Linienbreite | µ0H_res (T) | µ0ΔH (mT) | OK |
| benchmark_ftf/run_benchmark.py:311–315 / 319–323 | Differenzplots | µ0H_res (T, FTF) | ΔB_res (mT) / rel. ΔΔH (%) | OK |
| benchmark_ftf/run_benchmark.py:332–336 | z-Histogramme | z-Wert | Anzahl | OK (Histogramm) |
| benchmark_ftf/einfacher_vergleich.py:236–238 | obere Zusatzachse `secondary_xaxis("top")` mit Frequenz zum Feld | Feld (unten) / Frequenz (oben) | – | OK (Zusatzskala zur Feldachse, nur bei monotonem B_res(f)) |
| benchmark_ftf/einfacher_vergleich.py:255–262 | Resonanzfeld | µ0H_res (T) | Frequenz (GHz) | OK |
| benchmark_ftf/einfacher_vergleich.py:270–276 / 288–294 / 305–310 / 336–348 | Linienbreite und Differenzen | µ0H_res (T) | ΔH bzw. Differenzen | OK |
| benchmark_ftf/folien.py:78 / 315 | Bild-Einbettung bzw. Balkendiagramm | Kategorie | Anteil (%) | OK (kein Feld/Frequenz-Plot) |
| docs/abb/erzeugen.py:87–89 / 129–132 / 186–187 / 219 / 408 / 475 | Suszeptibilitaet, Fit, Residuen, Linescans | Feld µ0H (T) | χ, S21, Residuum | OK |
| docs/abb/erzeugen.py:234 / 259 / 299 / 349 / 511 | Farbplot + Kittel-Dispersionen | Feld bzw. µ0H_res (T) | Frequenz (GHz) | OK |
| docs/abb/erzeugen.py:169–170 | Fensterbreiten-Studie ΔH(k) | halbe Fensterbreite k | rel. ΔH-Abweichung | OK (Methodikplot) |
| docs/abb/erzeugen.py:265 / 276 / 282 / 307 / 313 / 320 / 333 / 357 / 385 / 429 | Residuen-/Differenz-Histogramme und LLG-Gerade | Differenz bzw. µ0ΔH (mT) | Anzahl / Frequenz | OK (Histogramme) |
| docs/abb/erzeugen.py:380 / 415 / 515 | ΔH bzw. rel. ΔH-Abweichung ueber der Frequenz | µ0ΔH (mT) / rel. Abw. (%) | Frequenz (GHz) | OK, aber Konvention weicht von der GUI ab (dort µ0ΔH auf y ueber dem Feld) – rein kosmetisch |

Einziger Hinweis (kein Bug): die ΔH-Darstellung ist nicht einheitlich – GUI und
`benchmark_ftf` tragen µ0ΔH auf y ueber dem Resonanzfeld auf, drei
Handbuch-Abbildungen (`docs/abb/erzeugen.py:380, 415, 515`) tragen µ0ΔH auf x
ueber der Frequenz auf. Beide Varianten halten die Regel „Frequenz auf y" ein.

## 5. Dateien in diesem Ordner

* `regression_vergleich.py` – Regressionsskript (repo-tauglich)
* `autofit_vergleich.py` – voller Auto-Fit-Pfad als JSON
* `head_cofe_wm_ip_290K_1.json`, `ref_cofe_wm_ip_290K_1.json`
* `head_fecr2s4_100K.json`, `ref_fecr2s4_100K.json`,
  `refcode_headenv_fecr2s4_100K.json`, `headcode_refenv_fecr2s4_100K.json`
* `auto_head_cofe.json`, `auto_refcode_cofe.json`, `auto_head_fecr.json`,
  `auto_refcode_fecr.json`
* `vergleich_cofe_wm_ip_290K_1.md`, `vergleich_fecr2s4_100K.md`,
  `vergleich_fecr2s4_code.md`, `vergleich_fecr2s4_ref_zuerst.md`

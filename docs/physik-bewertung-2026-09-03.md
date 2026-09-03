# Physikalische Gegenprüfung PolderFit gegen Müller (Diss. 2023, WMI) und Müller et al., J. Appl. Phys. 132, 233905 (2022)

Stand: 2026-09-03. Read-only-Prüfung, keine Codeänderung.
Quellenangaben: `Diss. S. xx` = Seitenzahl aus der Kopf-/Fußzeile des Textextrakts, `Z. n` = Zeilennummer in
`scratchpad/physik/mueller.txt`; `Paper` = `scratchpad/physik/paper_233905.txt`.
Codeangaben: Pfad relativ zu `/home/ibrahim/Dokumente/Ananas`.

## 0. Konventionsabgleich (Basis für alles Weitere)

| Größe | Diss. | PolderFit | Urteil |
|---|---|---|---|
| Kittel oop | `H_res − M_eff = 2πf/(γµ0)` — Gl. (2.24), Diss. S. 15, Z. 1064 | `B_res = µ0M_eff + 2πf/γ`, `physik/kittel_llg.py:17-20` | identisch |
| Kittel ip | `H_res = −H_u^oop − M_eff/2 + √[(2πf/γµ0)² + (M_eff/2)²]` — Gl. (2.26), S. 16, Z. 1082 | `√(w²+(M_eff/2)²) − M_eff/2 − µ0H_u`, `kittel_llg.py:23-30` | identisch |
| Linienbreite | `ΔH = 2·2πf·α/(γµ0)`, **ausdrücklich FWHM** — Gl. (2.27), S. 16, Z. 1099 („given as the full-width at half-maximum") | `µ0ΔH = 2·ω·α/γ`, `fit/linescan_fit.py:418`; Modell `kittel_llg.py:33-39` | identisch, FWHM |
| Inhomogenität | `ΔH = H_inh + 2·2πfα/(µ0γ)` — Gl. (2.28), S. 17, Z. 1115 | `linienbreite()`, `kittel_llg.py:33-39` | identisch |
| γ | `γ = gµ_B/ħ`, Felder als µ0H in T | `konstanten.py:31-37`, `GAMMA_STANDARD` für g=2 | identisch |

**Numerische Verifikation** (eigener Lauf gegen `physik/suszeptibilitaet.py`): Die FWHM von `−Im χ_oop`
über dem Feld beträgt bei f = 15 GHz, α = 3·10⁻³ genau `2ωα/γ` (Verhältnis 0.99995) — die im Code
verwendete Umrechnung α → µ0ΔH ist also exakt Gl. (2.27) und ist **FWHM, nicht HWHM**. Dasselbe gilt
für `chi_ip_komponenten` (Verhältnis 0.99964), und die dortige Resonanz liegt exakt auf `kittel_ip`.
Damit ist Müllers Aussage „Eq. (2.27) holds irrespective of sample shape and anisotropy as well as
measurement geometry" (S. 16, Z. 1102) im Code konsistent umgesetzt.

**Randbemerkung (kein Fehler, nur Startwert):** Der √3-Faktor in `fitmodell.py:194-200`
(Magnituden-FWHM → Absorptions-FWHM) gilt für eine reine Lorentz-Absorption. Für die tatsächlich
gefittete komplexe Größe `|A·χ_oop|` beträgt das Verhältnis numerisch 1.56 statt 1.73, weil χ′ mit
in den Betrag eingeht. Konsequenz: der α-**Startwert** liegt ca. 10 % zu tief. Für einen
Levenberg-Marquardt-Startwert irrelevant, aber der Kommentar im Code ist insofern ungenau.

---

## 1. Maghemit γ-Fe₂O₃: Welche Modelle nutzt Müller — und reicht PolderFits lineare LLG-Gerade?

### 1.1 Befund aus Diss./Paper

**Geometrie und B_res(f).** Müller misst γ-Fe₂O₃ ausschließlich **oop**, und zwar gezielt:
„The external static magnetic field is applied along the oop direction **to suppress two-magnon
scattering**" (Paper S. 233905-4; Diss. Z. 3059-3061, S. 54). Die Dispersion ist **nicht** die reine
Kittel-Gerade, sondern (Diss. Gl. (2.37), S. 23, Z. 1429; Paper Gl. (1)):

```
µ0 H_res = µ0 M_eff + (hf/gµ_B)·[1 + Im(α_slow(f))]
```

mit `M_eff = M_s − H_k` (Paper, unter Gl. (2)). Es gibt **keinen** zusätzlichen kubischen oder
in-plane-Anisotropieterm im Fit: die Anisotropie steckt vollständig in `M_eff`, unter der
ausdrücklichen Annahme „a uniform uniaxial out-of-plane anisotropy field H_u parallel to the applied
static magnetic field" (Diss. Z. 1425-1427). `H_eff = H_ext + H_d + H_u` ist Gl. (2.11) (Z. 800), also
genau das, was in oop-Geometrie zu `M_eff = M_s − H_u` kollabiert.

**ΔH(f).** Gl. (2.38) (Diss. S. 23, Z. 1432; Paper Gl. (2)):

```
µ0 ΔH = µ0 H_inh + 2·(hf/gµ_B)·[α + Re(α_slow(f))]
```

mit dem Slow-Relaxor-Term (Gl. (2.39), Z. 1440; Paper Gl. (3)), `C` nach Gl. (2.40)/(4) und
`F(T) = sech²(E_slow/k_BT)` nach Gl. (2.41)/(5). Die Auswertung ist ein **globaler, simultaner Fit von
H_res(f) und ΔH(f) mit gemeinsamen Parametern** und festgehaltenem g = 2.022 (Diss. Z. 3204-3212,
S. 56; Paper S. 233905-5). Ergebnis bei RT: µ0M_eff = (−12.4 ± 2.1) mT, α = (2.2 ± 1.5)·10⁻³,
CF(T) = (2.9 ± 0.6) GHz, τ = (6.3 ± 2.5) ps.

Die nichtlineare ΔH(f)-Kurve zeigt eine ausgeprägte **Cusp-Struktur bei 10–20 GHz** (Diss. Z. 3070-3072;
Paper S. 233905-4). Weitere Beiträge werden diskutiert und *ausgeschlossen*: Zwei-Magnonen-Streuung
(„not a strong temperature dependence … expected to be suppressed in oop-geometry", Paper S. 233905-6),
Anisotropie-Dispersion nach Krysztofik (falsche Krümmung), Kasuya-LeCraw/KLC (≈ linear in f).
Als *zusätzlicher* Kanal oberhalb 150 K wird der Valenzaustausch-/Charge-Transfer-Mechanismus
angeführt (Diss. Z. 1477-1494, S. 23), der dieselbe Peakform `ΔH_ct ∝ ωτ_ct/[1+(ωτ_ct)²]` mit
anderer Zeitkonstante erzeugt.

### 1.2 Abgleich mit dem Code

PolderFit besitzt für die ΔH(f)-Auswertung **nur** die Gerade nach Gl. (2.28)
(`kittel_llg.py:33-39`, `fit_linienbreite` :156-190) und für die Dispersion nur die Kittel-Gerade.
Eine Repo-weite Suche findet **keinen** Slow-Relaxor-, Valenzaustausch- oder
Zwei-Magnonen-Term und keinen globalen H_res/ΔH-Kopplungsfit. Temperatur wird zwar je Linescan
geladen (`io/tdms_laden.py:256`, `io/datensatz.py:41`) und als Plot „Resonanz vs. Temperatur"
angeboten (`auswertung/uebersicht.py:186-201`), aber **nie gefittet**.

### 1.3 Quantitative Konsequenz (eigene Rechnung mit Müllers eigenen RT-Parametern)

Ich habe µ0ΔH(f) nach Gl. (2.38) mit g = 2.022, α = 2.2·10⁻³, CF = 2.9 GHz, τ = 6.3 ps über
5–43.5 GHz (Müllers Messbereich) erzeugt und darauf PolderFits Geradenmodell (Gl. 2.28) angepasst:

| Größe | wahr (Müller) | aus PolderFits Geradenfit | Fehler |
|---|---|---|---|
| α | 2.2·10⁻³ | **4.25·10⁻³** | Faktor 1.93 zu groß |
| µ0H_inh | (beliebig) | wahrer Wert **+ 10.7 mT** | massiv überhöht |
| R² der Geraden | – | 0.75 | fällt auf |

Analog für die Dispersion (Gl. 2.37, Debye-Form, s. u.): g = 2.022 → scheinbar **2.040** (+0.9 %),
µ0M_eff −12.4 mT → −11.9 mT, R² = 0.99999.

**Das ist der Kern der Antwort:** Die Kittel-Auswertung bleibt für solche Proben praktisch
brauchbar (Müller selbst: „could be (mis-)interpreted in terms of a modified g-factor", Paper
S. 233905-5) — die **LLG-Gerade dagegen liefert für γ-Fe₂O₃ ein grob falsches α (hier Faktor ≈ 2)
und ein sinnloses H_inh.** Genau die Sorge des Nutzers aus `Dokumente/Prompts.txt` („sodass eben kein
Müll für alpha Gilbert-Dämpfung aus der Kittel Auswertung rauskommt") ist für diese Probenklasse
berechtigt und quantifizierbar.

**Bewertung: nicht gedeckt** (für γ-Fe₂O₃ und allgemein für Proben mit nichtlinearem ΔH(f));
gedeckt nur für Proben mit rein Gilbert-artiger Dämpfung (CoFe, YIG — siehe Abschnitt 6).

### 1.4 Was ließe sich aus PolderFits vorhandener Ausgabe zusätzlich gewinnen?

PolderFit liefert je Linescan bereits genau die Eingangsdaten, die Müller braucht: `f`, `B_res`,
`µ0ΔH` mit 1σ-Unsicherheiten (`fit/linescan_fit.py:416-421`) plus mittlere Temperatur.
Fehlend ist ausschließlich die **zweite Fitstufe**:

| Zielgröße | benötigte Gleichung | Datenbasis in PolderFit | fehlt |
|---|---|---|---|
| α (echt, entkoppelt), H_inh, CF(T), τ | Gl. (2.37)+(2.38)+(2.39) global | vorhanden (f, B_res, ΔH je f) | globaler 2-Kurven-Fit |
| ΔH_max und f_max des Cusps | Maximum von Re(α_slow) bei 2πfτ = 1 | vorhanden | – |
| M_eff(T), g(T), α(T), H_inh(T) | Kittel/LLG je Temperaturgruppe | Temperatur je Linescan vorhanden | Gruppierung nach T + Serienplot |
| E_slow, C·T | Gl. (2.40)·(2.41), Fit an CF(T) | erst nach CF(T) | 3. Stufe |
| E_A, τ₀ | `τ = τ₀·tanh(E_A/2k_BT)` (Paper Gl. (6)) | erst nach τ(T) | 3. Stufe |

**Achtung, Fallstrick bei einer späteren Implementierung:** Gl. (2.39) / Paper Gl. (3) ist in *beiden*
Quellen im Imaginärteil dimensional inkonsistent gesetzt — der Realteil `CF·τ/(1+(2πfτ)²)` ist
dimensionslos (GHz·ps ✓), der Imaginärteil `CF·(2πfτ)²/(1+(2πfτ)²)` hätte die Einheit GHz. Die
physikalisch konsistente Debye-Form ist `α_slow = CFτ·[1 − i·2πfτ]/(1+(2πfτ)²)`. Vor einer
Implementierung ist das mit dem Betreuer zu klären; blindes Abtippen der gedruckten Formel wäre falsch.

### 1.5 Praktischer Nutzen für den Nutzer

Für die Fe₂O₃-Linescans am WMI: Solange nur die Gerade angeboten wird, sollte PolderFit den
Nutzer **warnen**, statt ein falsches α zu exportieren. Konkrete, aufwandsarme Empfehlungen:

1. **Krümmungswarnung im LLG-Fenster.** `fit_linienbreite` liefert bereits R² (`kittel_llg.py:189`).
   Ein Hinweis „ΔH(f) nichtlinear (R² < ~0.95 bzw. systematisches Vorzeichenmuster der Residuen) —
   α ist eine obere Schranke, kein Gilbert-α" hätte im obigen Testfall (R² = 0.75) sofort gegriffen.
   Aufwand: klein.
2. **Residuenplot ΔH − Gerade über f** anzeigen. Das ist exakt Müllers Fig. 4.5(f) und macht den
   Cusp ohne jedes neue Modell sichtbar. Aufwand: klein.
3. Slow-Relaxor-Fit als **optionales** zweites ΔH(f)-Modell (Abschnitt 6).

---

## 2. Einzelfit-Modell: Deckt `s21_modell` die Auswertung nach Kap. 3.3.1 ab?

### 2.1 Befund

Diss. Gl. (3.9), S. 41 (Z. 2417 ff.):

```
S21(f,H_ext) = S21⁰(f) − i·A·e^{iφ}·[χ_bb(1−δ_bH) + χ_cc(1−δ_cH)]
```

mit dem Untergrund `S21⁰ = A + B·H_ext`, ausdrücklich „modeled as a **complex linear function** of the
form S21⁰ = A + B·H_ext, where A and B are complex constants, to account for the magnetic-field
dependence of these losses" (Diss. S. 40, Z. 2352-2356). Für oop reduziert sich das auf Gl. (3.12):
`S21 = S21⁰ − i·A·e^{iφ}·χ_xx = S21⁰ + A·e^{iφ}·χ_yx·e` (S. 42, Z. 2453 ff.).

PolderFit (`physik/fitmodell.py:2-19, 59-79`):

```
S21(B) = A·e^{iφ}·χ_oop(B; B_res, α, ω, γ) + (off_re + i·off_im) + (slope_re + i·slope_im)·(B − B_ref)
```

Das ist **strukturidentisch** mit Gl. (3.9)/(3.12): der Faktor `−i` und alle Setup-Vorfaktoren werden
von der freien Phase φ bzw. der freien Amplitude A aufgenommen; der komplexe lineare Untergrund
entspricht `A + B·H_ext` eins zu eins (die Umparametrisierung auf die Bandmitte `B_ref`
entkoppelt nur Offset und Steigung numerisch). Re und Im werden simultan gefittet
(`fitmodell.py:109-110`), 8 freie Parameter, Levenberg-Marquardt (`fit/linescan_fit.py:353-364`).

**Bewertung: gedeckt.**

### 2.2 „derivative divide" — wichtige Klarstellung

Weder Diss. noch Paper werten diese Daten mit *derivative divide* aus. Der Begriff kommt im
Diss.-Text nicht vor (nur Maier-Flaig als Zitat [140],[150],[203], Z. 10244/10282/10502).
Verwendet wird stattdessen die **feldgesweepte Messung bei fester Frequenz** mit
`ΔS21 = (S21 − S21⁰)/S21` (Gl. (3.7), S. 40, Z. 2362) und anschließendem Polder-Fit
(Diss. Z. 3063-3068: „The complex ΔS21 data is fitted to the Polder susceptibility χ̂p via
Eq. (2.30) to extract the resonance field H_ext and the linewidth ΔH as a function of f").
Derivative divide (Maier-Flaig 2018) ist demgegenüber die **frequenzgesweepte**
Ableitungsmethode. PolderFits Linescan-Ansatz ist also genau Müllers Verfahren — und deckt
sich mit der Betreuervorgabe „gefittet werden sollen vorrangig Linescan-Messungen
(Feldsweep bei fester Frequenz)" (`benchmark_ftf/BERICHT.md`, Hinweis vom 2026-08-17).

Ein Unterschied bleibt: Müller normiert **multiplikativ** (`/S21`), PolderFit modelliert den
Untergrund **additiv** im rohen S21. Das ist bei kleinem ΔS21 (hier ≲ 0.2, vgl. Diss. Fig. 4.5)
in erster Ordnung äquivalent und wird ohnehin von A, φ, off, slope absorbiert. Kein Handlungsbedarf.
**Bewertung: gedeckt.**

### 2.3 χ_oop für ip-Messungen

Diss. Gl. (2.31), S. 17 (Z. 1143): die Elliptizität `e = M_rf,x/M_rf,y`; für oop im Dünnfilmlimes ist
`e ≈ 1` (**zirkulare** Präzession, Z. 2456-2459), für ip ist `e ≠ 1` und in der Konfiguration
`H_ext ∥ b` sogar `e ≫ 1` mit stark reduziertem Signal (Z. 2440-2454). In ip-Geometrie `H_ext ∥ a`
tragen **beide** Treibfeldkomponenten bei: `S21 = S21⁰ + A·e^{iφ}·χ_yx·(e + 1/e)` (Gl. (3.10), S. 41).

Der Code weiß das und dokumentiert es explizit: `physik/suszeptibilitaet.py:102-110` — `chi_ip_*`
existiert, ist aber **nicht** im Linescan-Fit verdrahtet; `s21_modell` benutzt ausschließlich
`chi_oop` (`fitmodell.py:40, 74`). Das oop/ip-Umschalten greift erst in der übergreifenden
Kittel/LLG-Auswertung auf bereits extrahierte B_res (`auswertung/uebersicht.py:90-98`).

Was das praktisch bedeutet, habe ich numerisch geprüft: Die Feld-FWHM von `−Im χ_ip` ist ebenfalls
exakt `2ωα/γ`. Die α↔ΔH-Umrechnung ist also auch für ip korrekt (Gl. (2.27) ist
geometrieunabhängig, Diss. Z. 1102). Der Unterschied liegt allein in der **Linienform**: der
`e+1/e`- bzw. `1/e`-Vorfaktor mischt χ′ und χ″ anders. Da φ frei ist, wird eine *konstante*
Re/Im-Mischung vollständig absorbiert; unmodelliert bleibt nur die schwache **Feldabhängigkeit von
e(H_ext)** über die Linie hinweg (Gl. (2.31)), die eine leichte Linienasymmetrie erzeugt.

**Bewertung: teilweise gedeckt.** χ_oop ist für ip eine sehr gute Linienform-Näherung, keine exakte
Beschreibung. Der empirische Beleg, dass die Näherung trägt, liegt vor: der gesamte
FTF-Benchmark CoFe 290 K/5 K ist **ip**-Geometrie, und alle Kittel/LLG-Größen stimmen mit
|z| ≤ 0.5σ mit dem LabVIEW-FTF überein (`benchmark_ftf/FTF_AUTOFIT_2026-09-03.md`).

**Konsequenz für die Auswertung:** Für die Fe₂O₃-Linescans ist der Punkt ohnehin gegenstandslos —
Müller misst diese Probe oop, und zwar aus physikalischem Grund (Zwei-Magnonen-Unterdrückung).
Empfehlung: bei ip-Datensätzen im Bericht vermerken, dass die Linienform genähert ist; wer es exakt
will, braucht den in `suszeptibilitaet.py:102-110` bereits beschriebenen `B_res`-parametrisierten
ip-Wrapper plus Geometrie-Parameter durch Startwertschätzung/Modell/Fit. Aufwand: mittel.

### 2.4 Vorzeichen und Einheiten

Alle geprüften Punkte stimmen: γ in rad·s⁻¹·T⁻¹ (`konstanten.py:31-37`), Felder durchgehend µ0H in
Tesla (`konstanten.py:4-11`, TDMS liefert bereits Tesla), ω = 2πf (`linescan_fit.py:332`),
ΔH als **FWHM** entsprechend Gl. (2.27) (numerisch verifiziert, Abschnitt 0). Das im
`konstanten.py`-Docstring als „wahrscheinlichste Fehlerquelle" markierte Mischen von H (A/m) und
µ0H (T) tritt nirgends auf. `chi_oop` setzt intern `µ0M_eff = B_res − ω/γ` (`suszeptibilitaet.py:84`),
d. h. die Resonanz liegt per Konstruktion bei `B_res` — das ist Gl. (2.24) nach M_eff aufgelöst und
sauber. **Bewertung: gedeckt.**

---

## 3. Kittel-Auswertung

| Fall | Müller | PolderFit | Urteil |
|---|---|---|---|
| allgemein | Gl. (2.22), S. 15 (Z. 1028): volle Formel mit N_xx,N_yy,N_zz, H_u und Richtung **u** | nicht implementiert | nicht gedeckt (aber s. u.) |
| Kugel | Gl. (2.23), Z. 1049 | nicht implementiert | irrelevant (Dünnfilme) |
| Dünnfilm oop | Gl. (2.24), Z. 1064 | `kittel_oop`, `kittel_llg.py:17-20` | **identisch** |
| Dünnfilm ip | Gl. (2.25)/(2.26), Z. 1075/1082 | `kittel_ip`, `kittel_llg.py:23-30` | **identisch zu (2.26)** |

Müller selbst benutzt in der ganzen Arbeit ausschließlich die Spezialfälle (2.24) und (2.26) —
(2.26) explizit „we use a modified version of Eq. (2.25) in Ch. 5" (Z. 1079-1082); für γ-Fe₂O₃
(Kap. 4) und CoFe/Al₂O₃ (Appendix G1, Z. 9307-9309) wird (2.24) gefittet. Die in
`Dokumente/Prompts.txt` offene Frage, ob `H_eff = H_ext + H_d + H_u + h_rf` in voller
mathematischer Modellierung nötig ist, lässt sich damit beantworten: **Nein, nicht für Dünnfilme in
den beiden Standardgeometrien** — Gl. (2.11) (Z. 800) ist genau das, was zu (2.24)/(2.26)
zusammenfällt; die bereitgestellten Fitfunktionen decken es ab. Das gilt, solange die uniaxiale
Anisotropie **parallel zum Feld** liegt (Müllers ausdrückliche Annahme, Z. 1425-1427) und die
Demagnetisierungsfaktoren die Dünnfilmwerte annehmen.

**Zusätzlicher Befund (Codequalität):** Die in `kittel_llg.py:120-125` beschriebene exakte
Entartung von Gl. (2.26) unter `(M_eff, H_u) → (−M_eff, H_u + M_eff)` habe ich algebraisch
nachgerechnet — sie besteht tatsächlich, und die Schranke `µ0M_eff ≥ 0` (`kittel_llg.py:139`) ist
die richtige Auflösung. Diese Falle steht so nicht in der Diss.; der Fix ist eine echte
Verbesserung gegenüber einer naiven Umsetzung von (2.26).

**Wo es für welche Probe relevant wird:**

| Probe | Situation | Urteil |
|---|---|---|
| γ-Fe₂O₃ / MgO (Dehnung, PMA) | oop gemessen, Anisotropie steckt vollständig in M_eff; kubische Spinellanisotropie spielt in oop keine Rolle | **gedeckt** — nur `kittel_oop` nötig; M_eff wird klein und **negativ** (−12 mT bei RT, Vorzeichenwechsel bei T_cross ≈ 200 K, Diss. Z. 3230-3236). Wichtig: PolderFits `fit_kittel_oop` hat **keine** Vorzeichenschranke (`kittel_llg.py:87, 98`) — negatives M_eff kommt korrekt heraus. Bei `fit_kittel_ip` dagegen erzwingt die Schranke M_eff ≥ 0: **auf eine ip-gemessene Fe₂O₃-Probe mit PMA dürfte man `fit_kittel_ip` nicht anwenden** ohne diese Schranke zu prüfen. |
| CoFe (auch nanostrukturiert) | große M_eff ≈ 2.3 T, Standardfall | gedeckt |
| YIG | kleine M_eff, kubische Anisotropie in ip-Geometrie winkelabhängig | teilweise — Winkelabhängigkeit (kubisch) ist in (2.22) nur über N und uniaxiales H_u parametrisierbar; Müller macht dazu keine Aussage. Kein Handlungsbedarf ohne Winkelserien. |

**Empfehlung:** Warnhinweis in der GUI, wenn im ip-Fit `µ0M_eff` an der unteren Schranke 0 landet —
das ist das Signal für „Probe hat PMA / falsche Geometrie gewählt". Aufwand: klein.

---

## 4. Mehr-Moden-Auswertung

**Vorbemerkung:** In der Dissertation gibt es dazu **nichts** — Müller wertet durchweg die
uniforme Kittel-Mode einer homogenen Schicht aus. Die einzige Situation mit mehreren
Resonanzen ist die Magnon-Phonon-Hybridisierung in Kap. 7, und die wird gerade *nicht*
Mode-für-Mode mit unabhängigen Lorentzlinien behandelt, sondern über ein Modell **gekoppelter
harmonischer Oszillatoren** (Gl. (2.51)-(2.56), S. 27-28). Der Vergleich ist also
notwendigerweise indirekt.

**Was PolderFit tut:** je Mode ein eigener Korridor (`fit/korridor.py:2-13`), pro Linescan ein
Summenmodell aus n Polder-Linien mit je eigenem `B_res_k, α_k, A_k, φ_k` über **gemeinsamem**
Untergrund (`fitmodell.py:26-46`, `residuum_multi` :58-75), danach Kittel/LLG je Mode
(`auswertung/moden.py:60-100`).

**Bewertung: gedeckt für phänomenologisch entkoppelte Moden, nicht gedeckt für gekoppelte.**
Ein Summenmodell aus unabhängigen Polder-Linien ist die korrekte Beschreibung, solange die Moden
nur *räumlich* verschieden sind (z. B. PSSW- oder Randmoden eines perforierten Films) und
**nicht miteinander wechselwirken**. Das entspricht der Vorgabe „phänomenologisch, aber in der
Datenauswertung exakt" (`Dokumente/Prompts.txt`).

**Physikalische Fallen, die so nicht erfasst sind:**

1. **Modenkopplung / vermiedene Kreuzung.** Bei endlicher Kopplung g_eff sind die beiden
   Resonanzen keine Summe zweier Lorentzlinien mehr; Gl. (2.53) (Diss. S. 27, Z. 1697) zeigt einen
   **gemeinsamen Nenner** mit einem `−g_eff²/(…)`-Term. Ein Summenfit erzeugt dort systematisch
   falsche B_res (die Aufspaltung wird als zwei unabhängige Kittel-Zweige interpretiert) und
   falsche α. **Diagnose-Signatur: die Kittel-Fits zweier Moden ergeben kreuzende Geraden, die sich
   in den Daten aber nicht kreuzen.** PolderFit erkennt das nicht.
2. **Gemeinsame Linienbreiten / Linienbreiten-Transfer.** In Resonanz wird die magnetische
   Relaxationsrate *erhöht*: `κ̃_s = κ_s + g_eff²/(4η_a)` (Gl. (2.55), Z. 1721). Wer daraus per
   LLG-Gerade ein „α" der Mode zieht, mischt intrinsische Dämpfung und Kopplung. Der Code hat
   je Mode ein völlig freies α (`fitmodell.py:52-55`), also keine Kopplung der Linienbreiten.
3. **Amplituden-/Phasenentartung.** Bei Modenabstand ≲ ΔH ist das Summenmodell numerisch
   schlecht konditioniert (zwei Linien können A/φ tauschen). Der Code mildert das über die
   nutzergesetzten Korridore und die φ±π-Neustartlogik (`linescan_fit.py:385-395`), löst es aber
   nicht prinzipiell.
4. **Zuordnung über Linescans hinweg.** Die Modenzuordnung erfolgt über die Korridore, also über
   menschliche Vorgabe — physikalisch das Richtige, aber bei Modenkreuzung (Punkt 1) führt genau
   diese Zuordnung in die Irre.

**Empfehlungen (keine Codeänderung, nur Nutzung):**
- Nach einem Mehr-Moden-Lauf prüfen, ob die α_k benachbarter Moden dort lokal *anschwellen*, wo die
  Moden sich nähern. Das ist die Signatur von Punkt 2 und bedeutet: Summenmodell ungeeignet.
- Modenabstand ≥ 2–3 ΔH als Faustregel; darunter das Ergebnis nicht als „zwei unabhängige Moden"
  berichten.
- Ein echter Kopplungsfit nach Gl. (2.53) wäre Aufwand groß und ist ohne konkreten Anwendungsfall
  nicht zu empfehlen (siehe Abschnitt 6).

---

## 5. Kap. 7.1.2, 7.2 und Appendix G

### 5.1 Auswertestandard bei Müller

**Datendarstellung (Fig. 7.2, Diss. S. 134):** `|S21|` als **Colorplot über (µ0H_ext, f − f₀)** —
Feld auf x, Frequenz auf y, in einem Fenster von ±20 mT × ±10 MHz um `µ0H_res(f₀) ≈ 3.005 T` bei
f₀ = 18 GHz, T = 5 K. Dazu: (b) **vertikaler Schnitt** `|S21(f)|` bei einem *verstimmten* Feld
(3.011 T) → zwei Lorentzlinien → elastische Zerfallsraten `η_a1,2/(2π) = (0.23 ± 0.02)` und
`(0.16 ± 0.01)` MHz; (c) **horizontale Schnitte** `|S21(H_ext)|` = normale Linescans, resonant und
verstimmt → `κ_s/(2π) = (69.0 ± 0.1)` MHz aus der **HWHM**; (d) `ΔH(f)` mit den MEC-Peaks
`ΔH_MEC1,2` über der Geraden `ΔH₀` (Z. 7269-7302).

**Extrahierte Größen:** freier Spektralbereich `f_FSR ≈ 6.04 MHz` (Gl. (2.50)), Kopplungsrate über
**Gl. (2.56)** (S. 28, Z. 1725-1728):

```
g_eff = 2·√[η_a·(κ̃_s(f=f_n) − κ_s)] = √{2·η_a·γ·[µ0(ΔH(f=f_n) − ΔH₀)]}
```

→ `g_eff1,2/(2π) = (4.02 ± 0.62)` und `(4.55 ± 0.47)` MHz, Kooperativitäten
`C = g_eff²/(2κ_s η_a) = 0.63 ± 0.09` und `0.76 ± 0.10`.

**Kap. 7.2 (Temperaturabhängigkeit):** `κ_s(f)` linear gefittet als `κ_s/(2π) = κ_s0/(2π) + 2αf`
→ `κ_s0/(2π) = (48.0 ± 2.4)` MHz, `α = (2.9 ± 0.1)·10⁻³` (Z. 7815-7820) — das ist **exakt Gl. (2.28)
in Frequenzeinheiten**. `η_a(f) = η_a0 + 4π²ξf²` (Gl. (7.2)) und `η_a(T) = η_a0 + β_a T⁴`
(Landau-Rumer, Gl. (7.3), Z. 7935-7940). Temperaturserien von g, M_eff, α, H_inh in Fig. G2
(Z. 9325-9335).

**Appendix G1 (S. 181-182, Z. 9278-9324):** Für CoFe/Al₂O₃ bei T = 5 K, oop, wird ganz konventionell
`H_res(f)` mit **Gl. (2.24)** und `ΔH(f)` mit **Gl. (2.28)** gefittet:

| Größe | Müller, Appendix G1 |
|---|---|
| g | 2.079 ± 0.001 |
| µ0M_eff | (2.381 ± 0.004) T |
| µ0H_inh | (1.6 ± 0.2) mT |
| α | (2.8 ± 0.1)·10⁻³ |

### 5.2 Was PolderFit heute kann — und was nicht

| Auswerteschritt | PolderFit | Bewertung |
|---|---|---|
| Colorplot Feld x / Frequenz y | ja (Standarddarstellung, laut Memo „Plots stets x=Feld/y=Frequenz") | **gedeckt** |
| Horizontale Schnitte `|S21(H)|`, Polder-Fit → B_res, ΔH | ja, Kernfunktion (`fit/linescan_fit.py`) | **gedeckt** |
| Kittel oop (2.24) → g, M_eff | ja (`kittel_llg.py:64-110`) | **gedeckt** |
| LLG (2.28) → α, H_inh | ja (`kittel_llg.py:156-190`) | **gedeckt** |
| Gütekriterien / Ausreißer | ja (`fit/kriterien.py`, Nachfenster 2.5·ΔH `fit/batch.py:37`) | über Müllers Standard hinaus |
| **Vertikaler Schnitt `|S21(f)|` bei festem Feld + Lorentzfit → η_a** | **nein** — es gibt keinen Frequenzschnitt-Fit | **nicht gedeckt** |
| **f_FSR / Periodizität der Phononenmoden** | nein | nicht gedeckt |
| **ΔH-Peaks bei Phononenresonanz auswerten (ΔH_MEC)** | indirekt: ΔH(f) wird berechnet, aber nur gegen die Gerade gefittet; Peaks gelten als Ausreißer | **teilweise** |
| **g_eff, C nach Gl. (2.56)** | nein | nicht gedeckt |
| **Fit der vermiedenen Kreuzung (Gl. 2.52/2.53)** | nein | nicht gedeckt |
| **Temperaturserien (M_eff(T), α(T), η_a(T), Gl. (7.3))** | nein — T wird geladen und geplottet, nie gefittet | nicht gedeckt |
| Frequenzauflösung im MHz-Bereich um f₀ | prinzipiell ja, wenn die TDMS so aufgenommen sind | offen (datenabhängig) |

Wichtig für die Erwartungshaltung: Kap. 7 braucht eine **Frequenzauflösung im MHz-Bereich bei
festem Feld** (±10 MHz um 18 GHz, Fig. 7.2). PolderFits Linescan-Paradigma (Feldsweep bei fester
Frequenz) liefert die horizontalen Schnitte — die Colorplot-Achse `f` mit MHz-Schrittweite kommt
aus vielen dicht benachbarten Linescans. Das ist möglich, aber ein anderes Messregime als die
Fe₂O₃-Serien.

### 5.3 Lässt sich Appendix G mit PolderFit kreuzprüfen?

**Ja, und zwar direkt und ohne jede Erweiterung** — Appendix G1 ist der ideale Kreuzprüfungsfall,
weil dort genau PolderFits vier Ausgabegrößen stehen. Vergleichbar wären:

| Größe | Müller CoFe/Al₂O₃, 5 K, oop (App. G1) | PolderFit liefert | Anmerkung |
|---|---|---|---|
| g | 2.079 ± 0.001 | `kittel["g_faktor"]` | direkt vergleichbar |
| µ0M_eff | (2.381 ± 0.004) T | `kittel["mu0Meff"]` | direkt vergleichbar |
| α | (2.8 ± 0.1)·10⁻³ | `llg["alpha"]` | direkt vergleichbar |
| µ0H_inh | (1.6 ± 0.2) mT | `llg["mu0Hinh"]` | direkt vergleichbar |
| κ_s/(2π) | 69.0 MHz (HWHM in f) | aus `µ0ΔH`: κ_s/(2π) = γ·µ0ΔH/(4π) | Umrechnung nötig, kein neuer Fit |
| g_eff, C, η_a, f_FSR | Gl. (2.56), (2.50) | **nicht** ableitbar | η_a fehlt (Frequenzschnitt) |

**Bemerkenswerte Konsistenz:** Der bereits vorhandene FTF-Benchmark (`benchmark_ftf/BERICHT.md`)
prüft CoFe bei 290 K und 5 K und liefert α = 7.34·10⁻³ (290 K) bzw. 7.82·10⁻³ (5 K) — deutlich
größer als Müllers 2.8·10⁻³. Das ist **kein Widerspruch**, sondern eine andere Probe/Geometrie
(ip, andere Schichtfolge, ohne Müllers Pt/Cu-Seedlayer, der laut Z. 7185-7187 „required to generate
optimal magnetization damping properties of CoFe" ist). Ein sauberer Kreuztest gegen Appendix G1
bräuchte einen **oop**-Datensatz der CoFe/Al₂O₃-Probe. Falls ein solcher TDMS auf dem Share liegt,
wäre er die wertvollste noch offene Validierung — vier unabhängige Literaturwerte mit
Fehlerbalken, direkt gegen PolderFits Standardausgabe.

**Konkrete Empfehlung:** Die MEC-Peaks in `ΔH(f)` nicht als Ausreißer wegwerfen. Ein
Zusatzausgabefeld „µ0(ΔH − ΔH_Gerade) je f" (das ist bereits berechenbar, `kittel_llg.py:189` hat
alle Zutaten) macht Fig. 7.2(d) reproduzierbar; mit einem extern bestimmten η_a folgt g_eff
direkt aus Gl. (2.56) per Taschenrechner. Aufwand: klein.

---

## 6. Gesamturteil und priorisierte Erweiterungen

### 6.1 Numerische Genauigkeit

Sehr gut belegt. Gegen das LabVIEW-FTF (`benchmark_ftf/BERICHT.md`, `FTF_AUTOFIT_2026-09-03.md`):

- CoFe 290 K (ip): g 2.1054 vs. 2.1053; µ0M_eff 2.2496 vs. 2.2492 T; α 7.338 vs. 7.378·10⁻³;
  µ0H_u 3.05 vs. 3.14 mT; µ0ΔH₀ −0.92 vs. −1.01 mT. **Alle |z| ≤ 0.15σ.**
- CoFe 5 K (ip): g 2.1065 vs. 2.1048; µ0M_eff 2.3049 vs. 2.3104 T; α 7.818 vs. 7.857·10⁻³.
  **Alle |z| ≤ 0.46σ.**
- Einzelfit-Ebene: Median-Abweichung in ΔH zwischen −0.70 % und +0.08 %, 95–100 % der Punkte
  innerhalb 2σ, 0 problematische Fits.
- Auf identischem Fenster sind die Modelle äquivalent: B_res auf 10⁻⁵ T, ΔH auf 0.1 %.

Der Nachfenster-Faktor 2.5·ΔH (`fit/batch.py:37`) ist empirisch aus einer k-Studie begründet
(k = 2/2.5/3/4 → Median-Abweichung −0.1/+0.1/−0.1/−2.0 %) und behebt eine reale systematische
ΔH-Unterschätzung. **Urteil: numerisch einwandfrei, in ΔH sogar besser kontrolliert als das FTF.**

Einziger offener numerischer Punkt: YIG 50 K, α 1.784 vs. 1.584·10⁻³ (≈ 4σ Differenz). Angesichts
der ansonsten perfekten Übereinstimmung wäre hier zu prüfen, welcher der beiden Werte richtig ist —
bei YIG mit kleinem α ist die Linienbreite nahe an `DH_MIN_FELDSCHRITTE = 1.5` (`kriterien.py:65`),
also am Auflösungslimit. Aufwand: klein (Diagnose, keine Implementierung).

### 6.2 Physikalische Sinnhaftigkeit

| Bereich | Urteil |
|---|---|
| Einheiten/Vorzeichen/FWHM-Konvention | **gedeckt**, numerisch verifiziert |
| S21-Modell (Gl. 3.9/3.12) | **gedeckt** |
| Kittel oop (2.24) und ip (2.26) | **gedeckt**, inkl. korrekter Auflösung der (2.26)-Entartung |
| LLG-Gerade (2.28) für Gilbert-dominierte Proben (CoFe, YIG) | **gedeckt** |
| χ_oop als Linienform für ip-Daten | **teilweise** (Elliptizität e(H) unmodelliert; empirisch unkritisch) |
| ΔH(f) für γ-Fe₂O₃ und andere Proben mit nichtlinearem ΔH(f) | **nicht gedeckt** — α systematisch ≈ Faktor 2 zu groß |
| Temperaturabhängige Relaxationsprozesse (Sec. 2.3.3) | **nicht gedeckt** |
| Magnon-Phonon-Kopplung (Kap. 7) | **nicht gedeckt** |
| Mehr-Moden mit Kopplung | **nicht gedeckt** |

Zusammenfassend: **PolderFit ist eine korrekte und präzise Umsetzung von Müllers Standardauswertung
(Kap. 2/3, Appendix G1) — sie deckt genau den linearen, Gilbert-dominierten Fall ab.** Die
Kapitel 4 und 7 der Dissertation gehen darüber hinaus, und für die Fe₂O₃-Probe des Nutzers ist
dieser Überhang nicht kosmetisch, sondern entscheidet über die Richtigkeit von α.

### 6.3 Priorisierte Erweiterungen

| # | Erweiterung | Gleichung | Aufwand | Nutzen |
|---|---|---|---|---|
| 1 | **Nichtlinearitäts-Warnung + Residuenplot ΔH(f) − Gerade** | Vergleich gegen Gl. (2.28) | **klein** | verhindert stillschweigend falsches α — direkt die Sorge aus `Prompts.txt`. Höchste Priorität. |
| 2 | **Warnung, wenn ip-Fit an der Schranke µ0M_eff = 0 landet** | Gl. (2.26) | **klein** | erkennt PMA-Proben in falscher Geometrie (Fe₂O₃!) |
| 3 | **Export „µ0(ΔH − ΔH_Gerade)(f)"** (MEC-/Cusp-Residuum) | Gl. (2.38) bzw. (2.56) | **klein** | reproduziert Fig. 4.5(f) und Fig. 7.2(d) ohne neues Modell |
| 4 | **Temperaturserien-Auswertung**: Linescans nach T gruppieren, Kittel/LLG je T, Plots M_eff(T), g(T), α(T), H_inh(T) | (2.24)+(2.28) je T | **mittel** | genau Diss. Fig. 4.6 und Fig. G2; T ist bereits geladen |
| 5 | **Slow-Relaxor-ΔH(f)-Modell** als optionale Alternative zur Geraden | **Gl. (2.38)** mit **Gl. (2.39)** (Debye-Form, s. 1.4) | **mittel** | liefert echtes α, H_inh, CF(T), τ für Fe₂O₃ |
| 6 | **Globaler Fit H_res(f) + ΔH(f) mit gemeinsamen Parametern**, g optional fest | **Gl. (2.37) + (2.38)** simultan | **mittel** | Müllers eigenes Verfahren; entkoppelt g von Im(α_slow) |
| 7 | **CF(T)- und τ(T)-Fit** (3. Stufe) | **Gl. (2.40)·(2.41)** und `τ = τ₀ tanh(E_A/2k_BT)` (Paper Gl. 6) | **mittel** | E_slow, C·T, E_A, τ₀ — Diss. Fig. 4.6(c),(d) |
| 8 | **Echter ip-Linienform-Fit** (χ_ip mit B_res-Parametrisierung + Geometrieparameter) | Gl. (2.30)+(3.10)/(3.11) | **mittel** | beseitigt die letzte Näherung bei ip-Daten; Bauplan steht bereits in `suszeptibilitaet.py:102-110` |
| 9 | **Frequenzschnitt-Fit `|S21(f)|` bei festem Feld → η_a, f_FSR** | Lorentz + Gl. (2.50) | **groß** | Voraussetzung für alles aus Kap. 7 |
| 10 | **g_eff / Kooperativität aus ΔH-Peaks** | **Gl. (2.56)**, `C = g_eff²/(2κ_s η_a)` | **groß** (braucht #9) | Kap. 7.1.2 vollständig |
| 11 | **Fit der vermiedenen Kreuzung / gekoppelte Oszillatoren** | **Gl. (2.52)/(2.53)** | **groß** | nur bei konkretem MEC-Projekt sinnvoll |

**Empfehlung an den Nutzer:** #1–#3 sofort (kleiner Aufwand, verhindern falsche Ergebnisse); #4–#7
als Paket, sobald die Fe₂O₃-Temperaturserien ausgewertet werden sollen — das ist der eigentliche
physikalische Mehrwert gegenüber dem LabVIEW-FTF, das diese Modelle ebenfalls nicht hat.
#9–#11 nur bei einem konkreten Magnon-Phonon-Projekt.

---

## Anhang: Fundstellenverzeichnis

| Gleichung / Aussage | Diss. Seite | Zeile im Extrakt |
|---|---|---|
| H_eff = H_ext + H_d + H_u, Gl. (2.11) | S. 12 | 800 |
| Polder-Suszeptibilität χ̂_P, Gl. (2.20)/(2.21) | S. 13 | 958 / 968 |
| Kittel allgemein, Gl. (2.22) | S. 15 | 1028 |
| Kittel oop, Gl. (2.24) | S. 15 | 1064 |
| Kittel ip mit H_u, Gl. (2.26) | S. 16 | 1082 |
| ΔH = 2·2πfα/(γµ0), FWHM, Gl. (2.27) | S. 16 | 1099-1102 |
| ΔH = H_inh + …, Gl. (2.28) | S. 17 | 1115 |
| Elliptizität e, Gl. (2.31) | S. 17 | 1143 |
| Slow-Relaxor: Gl. (2.37)-(2.41) | S. 23 | 1429-1470 |
| Valenzaustausch-Mechanismus | S. 23-24 | 1477-1494 |
| g_eff aus ΔH-Peak, Gl. (2.56) | S. 28 | 1725-1728 |
| ΔS21 = (S21−S21⁰)/S21, Gl. (3.7); Untergrund A+B·H | S. 40 | 2352-2362 |
| S21-Gesamtmodell, Gl. (3.9) | S. 41 | 2417 ff. |
| oop: S21 = S21⁰ − iAe^{iφ}χ_xx, e ≈ 1, Gl. (3.12) | S. 42 | 2453-2459 |
| γ-Fe₂O₃ oop-Messung zur 2-Magnonen-Unterdrückung | S. 54 | 3059-3061 |
| Cusp in ΔH(f), 10-20 GHz | S. 54 | 3070-3072 |
| globaler Fit, g = 2.022 fest, RT-Parameter | S. 56 | 3204-3218 |
| M_eff(T)-Vorzeichenwechsel bei T_cross ≈ 200 K | S. 57 | 3230-3236 |
| Fig. 7.2, η_a, κ_s, ΔH_MEC, g_eff, C | S. 133-135 | 7269-7310 |
| κ_s(f) = κ_s0 + 2αf, α = 2.9·10⁻³ | S. 145 | 7815-7820 |
| η_a(f) = η_a0 + 4π²ξf², Gl. (7.2) | S. 146 | 7925 |
| η_a(T) = η_a0 + β_a T⁴, Gl. (7.3) | S. 146 | 7935-7940 |
| Appendix G1: g, M_eff, H_inh, α für CoFe/Al₂O₃ 5 K | S. 181-182 | 9307-9324 |
| Appendix G1.1: g(T), M_eff(T), α(T), H_inh(T) | S. 182 | 9325-9335 |

| Paper-Fundstelle | Seite |
|---|---|
| oop-Geometrie zur 2-Magnonen-Unterdrückung; Gl. (1)-(4) | 233905-4 |
| F(T) = sech², globaler Fit, g = 2.022, RT-Parameter; Gl. (5), (6) | 233905-5 |
| Ausschluss Zwei-Magnonen / Anisotropiedispersion / KLC; Valenzaustausch | 233905-6 |

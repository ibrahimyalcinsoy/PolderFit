# Bereich E – Multi-Moden-Erkennung und Performance

HEAD: `/home/ibrahim/Dokumente/Ananas` (V0.1.66, e3b1ea7) · Referenz: `/home/ibrahim/Dokumente/polderfit-ref` (7c893e8)

**Vorbemerkung zur Referenz.** 7c893e8 enthält *keinerlei* Multi-Moden-Code
(`grep -c multi` in `physik/fitmodell.py`, `fit/batch.py`, `fit/linescan_fit.py`
liefert dort jeweils `0`; `polderfit/auswertung/moden.py` existiert nicht).
Ein Diff „Zeile gegen Zeile" gibt es für diesen Bereich also nicht – der gesamte
Bereich E ist Neucode. „Zurück auf Referenz" bedeutet hier immer: Feature entfernen.

**Positivbefund vorab:** Der Ein-Moden-Pfad in HEAD ist gegenüber 7c893e8
bitgleich. Auf 30 Linescans (`…oop-5K_1.1deg-for-FTF.tdms`, jede 21. Frequenz)
liefern beide Stände identische `B_res`/`dH` (z. B. 6.03 GHz: 2603.16 mT /
43.08 mT; 8.97 GHz: 2705.95 mT / 20.23 mT) bei 5.2 bzw. 5.1 ms je Linescan.
Alle unten beschriebenen Fehler stecken ausschließlich im Multi-Moden-Zweig.

---

## Reproduktion (gilt für alle Bugs)

Datensatz `testdata-n-lorentz/2025-NOV-11-Linescan-2D-map-oop-5K_1.1deg-for-FTF.tdms`
(629 Linescans, 197 Feldpunkte je Linescan, Feldschritt **2.54 mT**).
Skripte im Scratchpad:

| Skript | Zweck |
|---|---|
| `lade_cache.py` | TDMS laden, Teilmenge (jede 21. Frequenz = 30 Linescans) als `sub30.pkl`, voller Satz als `voll.pkl` |
| `lauf.py --moden {1,2} [--zweistufig] [--profile]` | Laufzeit + cProfile + Ergebnisliste |
| `zaehle.py` | Zählt `fitte_linescan`-Aufrufe, Modellauswertungen, Fenstergrößen (Monkey-Patch) |
| `analyse_ls.py <i>` | Feldprofil, `find_peaks`-Kandidaten, Startwerte der 2. Mode, Ergebnis von `ergaenze_moden` |
| `maske_stat.py` | Sperrzone vs. echter 2. Dip über alle 30 Linescans |
| `entartung.py` | 40 Startwerte über das Fenster geschoben → Anzahl verschiedener Minima; Korridor-Einzelfits |
| `korridor.py` / `korridor2.py` | Korridor-Maskierung vs. Summenfit |
| `expr_kosten.py`, `fenstergroesse.py` | Mikro-Benchmarks (asteval-`expr`, Fensterbreite) |
| `voll.py` | Ganzer Datensatz (629 Linescans) |

---

## Aufgabe 1 – Profiling

### Laufzeiten (30 Linescans, `zaehle.py`)

| Variante | ms / Linescan | `fitte_linescan`-Aufrufe / LS | Modellauswertungen / LS | Fenster (Median) |
|---|---|---|---|---|
| 7c893e8, 1 Mode | 5.2 | 1.93 | 127 | 40 Punkte |
| HEAD, 1 Mode | 5.7 | 1.93 | 127 | 40 Punkte |
| HEAD, `n_moden=2` direkt | **29.3** | 1.97 | 441 | 33 Punkte |
| HEAD, `n_moden=2` zweistufig | **57.0** | **5.17** | **1092** | Stufe 2: **106 Punkte** |

Ganzer Datensatz (629 Linescans, `voll.py`): **3.6 s** (1 Mode) vs. **38.1 s**
(2 Moden zweistufig) → Faktor **10.6**.

### cProfile, `n_moden=2` zweistufig, Top nach cumtime (3.40 s, 30 Linescans)

```
   ncalls  tottime  cumtime  Funktion
        1    0.001    3.404  fit/batch.py:277(fitte_alle)
      155    0.004    3.211  fit/linescan_fit.py:341(fitte_linescan)
       30    0.002    3.115  fit/batch.py:372(ergaenze_moden)          <-- 92 % der Zeit
      155    0.002    3.034  lmfit/minimizer.py:1609(leastsq)
       69    0.003    2.809  fit/linescan_fit.py:482(fitte_linescan_multi)
      155    0.070    2.744  scipy.optimize._minpack._lmdif
    32762    0.226    2.703  lmfit/minimizer.py:493(__residual)
    27380    0.083    1.363  physik/fitmodell.py:257(residuum_multi)
    27617    0.169    0.785  physik/fitmodell.py:225(s21_modell_multi)
   449291    0.067    0.745  lmfit/parameter.py:995(_getval)           <-- expr-Auswertung
    60904    0.121    0.675  physik/suszeptibilitaet.py:71(chi_oop)
    58762    0.032    0.632  asteval/asteval.py:346(eval)              <-- 18.6 % (!)
    60904    0.539    0.552  physik/suszeptibilitaet.py:36(chi_oop_komponenten)
    27449    0.073    0.469  physik/fitmodell.py:248(moden_aus_params)
```

### Wo geht die Zeit hin?

1. **Anzahl der Optimierer-Starts.** Stufe 2 ruft je Linescan **median 3, bis zu 4**
   `fitte_linescan` auf (`batch.py:433-447` baut bis zu drei Startwert-Kandidaten,
   `batch.py:455` kommt ggf. ein Ein-Moden-Vergleichsfit dazu, `batch.py:461-471`
   fittet jeden Kandidaten voll durch). Zusammen mit Stufe 1 (1.93 Fits) sind das
   **5.17 statt 1.93 Fits je Linescan** = Faktor 2.7.
2. **Kosten je Multi-Fit (der Hauptposten).** Ein 2-Moden-Fit braucht **397
   Modellauswertungen**, ein 1-Moden-Fit **66**. Mit 12 statt 8 freien Parametern
   erklärt der Jacobi-Aufwand nur 13/9 = 1.44× davon; die restlichen **4.2×** sind
   *mehr LM-Iterationen*, d. h. der Optimierer kriecht durch eine fast entartete
   Fehlerfläche (siehe Aufgabe 3). Pro Auswertung kosten beide Modelle etwa gleich
   viel (35–45 µs) – es ist **nicht** die Arraygröße, sondern der Python-Overhead
   je Auswertung × Iterationszahl.
3. **`expr`-Kette / asteval.** `linescan_fit.py:556-558` parametrisiert
   `B_res_k = B_res_(k-1) + dB_k` über einen lmfit-`expr`-String. lmfit wertet den
   bei *jedem* Parameterzugriff per asteval neu aus: 58 762 asteval-Läufe,
   **0.63 s von 3.40 s = 18.6 %**. Gegenmessung (`expr_kosten.py`, identische
   Startwerte, 30 Linescans): 12.28 ms/Fit mit `expr` vs. **9.97 ms/Fit** mit
   unabhängigen `min`/`max`-Grenzen (`bereiche`-Pfad) → **19 % reiner Overhead**.
4. **Bandbreite/Fenster.** Stufe 2 fittet auf **106 statt 40 Punkten**
   (`batch.py:403`, siehe Bug E3). Kostenanteil gemessen (`fenstergroesse.py`):
   14.54 ms (106 Punkte) vs. 12.93 ms (40 Punkte) = **11 %**. Für die *Richtigkeit*
   ist das aber gravierend (Bug E3).
5. **Untergrundpolynom / Startwertsuche** sind irrelevant: `_untergrund_und_rein`
   (lstsq auf 2 Spalten) und `find_peaks` tauchen in den Top-20 nicht auf.
6. **`chi_oop_komponenten`** (0.55 s tottime) ist vektorisiert, rechnet aber `d**2`
   dreimal und `d**4` einmal statt `d2 = d*d; d4 = d2*d2` – ein kleiner,
   risikoloser Gewinn (~5 % des Modells).

---

## BUG E1 (Hauptbefund) – Die Kandidatensuche der 2. Mode sperrt genau die Nachbarschaft aus

**Symptom.** Die zweite Mode landet weit vom tiefsten Dip entfernt, obwohl der
zweite Dip nur wenige Feldpunkte daneben liegt (Nutzerbeobachtung b).

**Datei:Zeile.** `polderfit/fit/batch.py:422-436`

```python
fwhm = float(np.sqrt(3.0) * klassisch.dH) ...          # 422
toleranz = max(fwhm, 2.0 * schritt)                    # 424
maske = np.abs(B - klassisch.B_res) > toleranz         # 425
...
versuche += [(B[maske], s21[maske]), (B[maske], rest[maske])]   # 435
versuche.append((B, rest))                                       # 436
```

**Root Cause.** Zwei Drittel aller Startwert-Kandidaten (a und b) suchen die
zweite Mode ausschließlich **außerhalb** von `|B - B_res| <= FWHM`. Die FWHM
stammt aber aus dem *Ein-Moden-Fit*, der die unaufgelöste Nachbarmode bereits in
eine zu breite Linie hineingezogen hat. Je näher die zweite Mode, desto breiter
`dH`, desto größer die Sperrzone – ein Teufelskreis: **Nähe zur Hauptmode ist
genau das Kriterium, mit dem die Nachbarmode ausgeschlossen wird.**

**Zahlen (`maske_stat.py`, 30 Linescans).**

* Der echte zweite Dip (`find_peaks` auf dem untergrundbereinigten Betrag,
  Prominenz ≥ 15 %) liegt **in 28 von 30 Linescans innerhalb der Sperrzone**.
* Der Startwert aus Kandidat (a) liegt **in 25 von 30 Linescans** mehr als zwei
  Feldschritte vom echten zweiten Dip entfernt – typisch **+30 … +40 mT**, also
  jenseits davon im Rauschen bzw. am Fensterrand.

Konkret Linescan 2 (**8.969 GHz**, `analyse_ls.py 2`):

```
Ein-Moden-Fit:  B_res = 2705.95 mT, dH = 20.23 mT  -> FWHM = 35.04 mT = toleranz
Stufe-2-Fenster [2604.9, 2856.9] mT, 100 Punkte, Schritt 2.540 mT
-> 28 Punkte um die Hauptmode (2671.2 .. 2740.5 mT) fuer die Kandidatensuche GESPERRT

Feldprofil |rein| (Ausschnitt):
  2707.0 mT  0.0029038   <== B_res (1 Mode)
  2717.7 mT  0.0021531
  2730.9 mT  0.0030421   <== ZWEITER, sogar staerkerer Dip, +24.95 mT

find_peaks auf dem ganzen Fenster findet ihn (Prominenz 0.00303, groesste im Fenster).

Startwert Mode 2:
  a) Rohdaten ausserhalb der Sperrzone : 2743.05 mT  (+37.10 mT)  <-- daneben
  b) Residuum ausserhalb der Sperrzone : 2743.05 mT  (+37.10 mT)  <-- daneben
  c) Residuum, ganzes Fenster          : 2730.90 mT  (+24.95 mT)  <-- richtig
```

Nur Kandidat (c) trifft. Dass am Ende oft trotzdem etwas Brauchbares herauskommt,
liegt allein daran, dass (c) existiert und `batch.py:470` das kleinste Residuum
gewinnen lässt – (a) und (b) sind in 25/30 Fällen verbrannte Rechenzeit (siehe
Performance) *und* ein Risiko, wenn (c) einmal nicht konvergiert.

Fälle, in denen die Fehlplatzierung durchschlägt (`maske_stat.py`, Spalten
„2.Dip" vs. „Fit M2", Abstand zur Hauptmode):

| Linescan | f/GHz | echter 2. Dip | gefundene Mode 2 | dH der Mode 2 |
|---|---|---|---|---|
| 8  | 17.79 | +8.5 mT  | **+20.6 mT** | 2.93 mT |
| 18 | 32.49 | +6.3 mT  | **+19.4 mT** | 4.47 mT |
| 19 | 33.96 | +5.8 mT  | **+20.2 mT** | 5.20 mT |
| 22 | 38.36 | +4.8 mT  | **+19.9 mT** | 6.00 mT |
| 23 | 39.83 | +3.1 mT  | **+17.6 mT** | 5.96 mT |
| 24 | 41.30 | +6.7 mT  | **+20.8 mT** | 4.95 mT |
| 26 | 44.24 | +5.2 mT  | *keine 2. Mode akzeptiert* | – |

**Dieselbe Sperrlogik ein zweites Mal** in
`polderfit/physik/fitmodell.py:335-349`: dort wird nach jedem gefundenen Peak
`±1.5·FWHM` maskiert, bevor der nächste gesucht wird. Bei ≥ 3 Moden verbietet das
denselben Nähefall noch einmal.

**Fixvorschlag (Fix im aktuellen Code).**
1. Kandidat (c) (`(B, rest)`, ganzes Fenster ohne Sperrzone) **zuerst** probieren
   und die Kandidatenliste dort abbrechen, wenn (c) einen Peak mit ausreichender
   Prominenz liefert – spart in 25/30 Fällen zwei volle Multi-Fits und behebt
   gleichzeitig das Nähe-Problem.
2. Die Sperrzone `toleranz` **entkoppeln** von `klassisch.dH`: statt der
   Ein-Moden-FWHM eine harte, sampling-basierte Untergrenze verwenden
   (`max(2·schritt, min(fwhm, ...))` bzw. gleich nur `2·schritt`) – zwei Dips
   dürfen 2 Feldpunkte auseinanderliegen, das ist die Auflösungsgrenze, nicht
   die Linienbreite.
3. In `fitmodell.py:337/349` die Maskierungsbreite `1.5·FWHM` auf
   `max(2·schritt, 0.5·FWHM)` reduzieren.

**Risiko.** Mittel. Punkt 1 ist rein additiv (Reihenfolge/Abbruch) und wird durch
den vorhandenen Phantomfilter (`PHANTOM_FAKTOR`) abgesichert. Punkte 2/3 erhöhen
die Chance, dass zwei Moden auf denselben Dip fallen; das muss dann Bug E2
(dH-Untergrenze) abfangen.

---

## BUG E2 – Unterabgetastete „Nadel-Linien" werden zur Hauptmode gekürt

**Symptom.** Bei `n_moden=2` springt `B_res` der Hauptmode gegenüber dem
Ein-Moden-Fit um bis zu 26.8 mT; die gemeldete Linienbreite fällt auf **unter
einen Feldschritt**.

**Datei:Zeile.** `polderfit/fit/linescan_fit.py:611` und `:621-624`

```python
hoehe = float(abs(A) * abs(chi_oop(np.array([b_res]), b_res, alpha, omega, gamma))[0])   # 611
...
haupt = int(np.argmax([m["hoehe"] for m in moden]))     # 621
```

und ergänzend `polderfit/fit/kriterien.py` (`bewerte_fit`, Zeilen 130-151): dort
werden je Mode nur `alpha an Grenze`, `phi an Grenze`, `B_res am Fensterrand`,
`B_res ausserhalb Fenster` und `alpha unphysikalisch` (obere Schranke) geprüft –
**es gibt kein Kriterium „Linie schmaler als die Feldabtastung"**. `ALPHA_MIN`
liegt bei 1e-5, also viele Größenordnungen unter der Auflösungsgrenze.

**Root Cause.** Die Hauptmode wird über die reine Signalhöhe entschieden, ohne
zu prüfen, ob die Linie überhaupt aufgelöst ist. Eine über 1–2 Messpunkte
angepasste Nadel kann dieselbe Höhe erreichen wie die echte, breite Resonanz –
und gewinnt dann.

**Zahlen.** Feldschritt 2.540 mT.

* Linescan 2 (8.969 GHz), `ergaenze_moden`-Ergebnis:
  `Mode 0: B_res=2730.49 mT, dH=2.617 mT, hoehe=0.002492`
  `Mode 1: B_res=2707.36 mT, dH=16.950 mT, hoehe=0.002437`
  Die Höhen liegen **2.3 % auseinander**; die Nadel (dH = 1.03 Feldschritte)
  gewinnt. Ergebnis: `B_res` der Hauptmode = 2730.49 statt 2705.95 mT
  (**+24.5 mT**), `dH` = 2.62 statt 20.23 mT.
* Gleiches Bild bei 7.50 GHz (2679.19/2.43 mT statt 2654.16/27.53 mT) und
  10.44 GHz (2780.88/2.37 mT statt 2756.99/17.06 mT).
* Ganzer Datensatz (`voll.py`, 629 Linescans, zweistufig):
  * 603 Ergebnisse mit 2 Moden; **60 davon enthalten mindestens eine Mode mit
    `dH < Feldschritt`**.
  * `B_res(Hauptmode, 2 Moden) − B_res(1 Mode)`: Median **+1.64 mT**, aber
    **43/603 mit |Diff| > 10 mT**, Maximum **26.8 mT**.
  * Kein einziges dieser Ergebnisse ist als `problematisch` markiert.
* Ohne `zweistufig` (reiner `n_moden=2`-Autofit) ist es schlimmer: die ersten vier
  Frequenzen liefern `dH` = 2.49/2.06/2.69/2.58 mT und `B_res`-Fehler von
  +25/+13/+24/+24 mT, und das Nachfenster verengt anschließend auf **30 mT
  Fensterbreite** um die Nadel herum – der Fehler wird zementiert.

**Diff zu 7c893e8.** Kein Gegenstück; `hoehe`, `moden` und die Modenschleife in
`bewerte_fit` sind komplett neu (`git diff 7c893e8 -- polderfit/fit/kriterien.py`
zeigt den Umbau von Einzelparameter- auf Modenschleifen-Prüfung, ohne dass ein
Auflösungskriterium hinzugekommen wäre).

**Fixvorschlag (Fix im aktuellen Code) – drei kleine, unabhängige Eingriffe.**
1. **Harte Untergrenze im Fit:** `alpha_min` je Linescan aus dem Feldschritt
   ableiten (`alpha >= gamma * 2*schritt / (2*omega)`, entspricht `dH >= 2` Feldschritte)
   statt des globalen `ALPHA_MIN = 1e-5`. Das verhindert die Nadel schon im Optimierer.
2. **Kriterium:** in `bewerte_fit` je Mode `dH < 2 * Feldschritt` als Grund
   „Linie nicht aufgelöst" melden (`FitErgebnis` trägt `feld`, der Schritt ist
   dort verfügbar).
3. **Hauptmode-Auswahl:** `haupt = argmax(hoehe)` nur über Moden mit
   aufgelöster Linienbreite laufen lassen; sind die Höhen näher als z. B. 20 %
   beieinander, die breitere Mode bevorzugen (sie trägt die Fläche).

**Risiko.** Niedrig für (2) (nur Kennzeichnung). Mittel für (1)/(3): ändert
bestehende 2-Moden-Ergebnisse – aber genau die 60 bzw. 43 offensichtlich falschen.

---

## BUG E3 – Stufe 2 verwirft das validierte Nachfenster

**Symptom.** Der zweistufige Autofit rechnet auf einem 2.6-mal breiteren Fenster
als der validierte Ein-Moden-Pfad.

**Datei:Zeile.** `polderfit/fit/batch.py:402-403`

```python
unten, oben = fenster if fenster is not None else (st_unten, st_oben)
unten, oben = min(float(unten), float(st_unten)), max(float(oben), float(st_oben))
```

`fitte_alle` übergibt dabei `fenster=fenster_auto[i]` (`batch.py:361`) – also das
**breite Detektionsfenster vor** dem zweiten Durchgang. Durch `min`/`max` gewinnt
immer das breitere; das in `NACHFENSTER_FAKTOR_STANDARD = 2.5` dokumentierte und
gegen das LabVIEW-FTF benchmarkte enge Fenster (`batch.py:24-38`) ist in Stufe 2
wirkungslos.

**Zahlen.** Linescan 2: Stufe-1-Fenster `[2647.4, 2767.3]` mT (120 mT, 47 Punkte)
→ Stufe-2-Fenster `[2604.9, 2856.9]` mT (252 mT, **100 Punkte**). Über 30
Linescans: Median 40 → **106 Punkte**. Genau die Situation, gegen die der
Kommentar in `batch.py:27-35` warnt („auf so breiten Fenstern passt der lineare
Untergrund … nicht mehr, und die Linienbreite kommt systematisch 5-15 % zu klein
heraus"). Laufzeitanteil: 11 % (`fenstergroesse.py`).

**Fixvorschlag (Fix im aktuellen Code).** Das breitere Fenster nur so weit
zulassen, wie es für die Nachbarmoden nötig ist, z. B. Stufe-1-Fenster plus
`faktor·dH` je Seite statt des vollen Auto-Fensters; oder nach dem Mehr-Moden-Fit
ein Nachfenster um die *Menge* aller Moden legen und erneut fitten.
Alternativ (kleinster Eingriff): `batch.py:403` durch `unten, oben = fenster or (st_unten, st_oben)`
ersetzen und in `fitte_alle:361` das Stufe-1-Fenster übergeben.

**Risiko.** Niedrig. Betrifft nur den zweistufigen Pfad; die Prüfung
`ergebnis.rmse_norm <= PHANTOM_FAKTOR * basis_rmse` bleibt intakt, weil die Basis
im selben Fenster gefittet wird (`batch.py:452-457`).

---

## BUG E4 (der inhärente Auswertungsfehler) – Der freie Summenfit über den ganzen Sweep ist entartet

**Symptom.** Das Ergebnis des 2-Moden-Fits hängt vom Startwert ab, nicht von den
Daten; eine der beiden Polder-Linien bildet den Untergrund/die Flanke nach.

**Nachweis (`entartung.py`, Linescan 2, 8.969 GHz, Fenster [2604.9, 2856.9] mT).**
Mode 1 wird auf dem klassischen Ergebnis festgehalten, der **Startwert von Mode 2
wird in 40 Schritten über das ganze Fenster geschoben**, sonst identische
Einstellungen. Ergebnis:

```
3 verschiedene Endzustaende aus 40 Startwerten:
  n=25  B_res=(2707.4, 2730.5) mT  dH=(16.95,  2.62) mT  rmse_norm=0.03945
  n=15  B_res=(2699.7, 2704.8) mT  dH=(51.04,  9.69) mT  rmse_norm=0.05907
```

Das zweite Minimum (**15 von 40 Startwerten**, nämlich alle Startfelder links von
≈ 2697 mT, d. h. die gesamte linke Fensterhälfte) hat **beide Moden auf demselben
Dip** (2699.7 / 2704.8 mT, Abstand 5.1 mT = 2 Feldschritte = exakt `min_abstand`
aus `linescan_fit.py:515`) und eine **51 mT breite Linie** – das ist bei einem
Fenster von 252 mT keine Resonanz mehr, sondern ein **Untergrund-Surrogat**. Es
ist ein echtes lokales Minimum, kein Abbruch: `erfolg=True`, Kovarianz vorhanden.

Und es wäre **akzeptiert worden**: `rmse_norm = 0.0591 < PHANTOM_FAKTOR · 0.0975 = 0.0926`
(`batch.py:468`) und `|2704.8 − 2705.95| = 1.15 mT <= toleranz = 35.04 mT`
(`batch.py:466`). Dass in diesem Linescan das bessere Minimum gewinnt, ist reine
Kandidatenlotterie (`batch.py:470`).

**Warum das strukturell so ist (Codebeleg).**
`physik/fitmodell.py:225-245` (`s21_modell_multi`) summiert n Polder-Linien über
**einem gemeinsamen** linearen Untergrund `(off_re + i·off_im) + (slope_re + i·slope_im)·(B − B_ref)`.
Die einzigen Schranken sind (`linescan_fit.py:552-565`):
`B_res` im Fenster, `alpha ∈ [1e-5, alpha_max]`, `phi ∈ [PHI_MIN, PHI_MAX]`,
`dB_k >= min_abstand = 2·Feldschritt`. **`A` ist völlig unbeschränkt** und
`alpha` darf bis `alpha_max = 0.1` laufen, was bei 9 GHz einer Linienbreite von
`2·ω·α/γ ≈ 51 mT` entspricht – dem Wert, der oben im Fehlminimum auftaucht.
Damit ist `A·exp(iφ)·χ(B; B_res, α_groß)` über ein 252-mT-Fenster hinweg eine
**glatte, nahezu lineare Funktion** und konkurriert direkt mit
`slope_re/slope_im`. Der Fit hat also (2 Untergrundsteigungen + 2 Offsets) gegen
(A, φ, α einer breiten Linie) – vier Parameter zuviel. Das ist der inhärente
Fehler: **nicht die Startwerte sind schuld, das Modell ist auf dem vollen Sweep
nicht identifizierbar.**

Der Preis dafür steht auch in den Profildaten: 397 Modellauswertungen je
Multi-Fit gegen 66 beim Ein-Moden-Fit; nach Abzug des Jacobi-Effekts (12 statt 8
Parameter, Faktor 1.44) bleiben **4.2× mehr LM-Iterationen** – der Optimierer
kriecht durch das flache Tal. **Langsamkeit und Fehlplatzierung haben dieselbe
Ursache.**

**Was eine Korridor-Maskierung ändert – Experiment (`korridor2.py`, 26 Linescans).**
Getestet: statt eines Summenfits je Mode ein **Einzelfit mit einer Polder-Linie**
auf einem Feldkorridor (Mode 1: `[B₁ − 12 mT … Mitte]`, Mode 2: `[Mitte … B₂ + 12 mT]`,
Mitte = `(B₁+B₂)/2`).

```
Abstand M2-M1 (mT): Summenfit   Median 19.25  MAD 1.05   Spanne 15.4..24.2
Abstand M2-M1 (mT): Korridorfit Median 21.16  MAD 4.16   Spanne 10.9..29.0
dH Mode 1  (mT):    Summenfit   Median 17.18  MAD 0.71   Spanne 15.1..19.7
dH Mode 1  (mT):    Korridorfit Median 21.90  MAD 10.72  Spanne  6.1..74.6
```

**Ehrliches Zwischenergebnis: die naive Korridor-Maskierung ist nicht pauschal besser.**
Differenziert:

* **Die schmale Nebenmode profitiert klar.** Ihre Position stimmt im Korridorfit
  auf **< 1 mT** mit dem Summenfit überein (z. B. 8.97 GHz: 2729.97 vs. 2730.49 mT;
  13.38 GHz: 2882.22 vs. 2882.44 mT), ihre Breite ebenfalls (2.6 / 3.1 / 4.5 / 5.5 mT).
  Sie ist also **auch ohne Summenfit** sauber bestimmbar – der teure, entartete
  Summenfit bringt für sie keinen Mehrwert.
* **Die breite Hauptmode leidet**, weil der Korridor an der Mitte abgeschnitten
  wird und damit **die halbe Flanke fehlt**: `dH` streut 6.1 … 74.6 mT
  (36.89 GHz: 74.65 mT, 45.71 GHz: 52.46 mT). Ein einseitig beschnittenes
  Lorentz-Profil ist unterbestimmt.
* Bei symmetrischem Korridor (`entartung.py`, ±12 mT um jeden Dip) sind **beide**
  Moden stabil: 8.97 GHz → 2709.87 mT / 8.48 mT und 2729.97 mT / 2.60 mT,
  `rmse_norm` 0.056 bzw. 0.051, beide `problematisch=False`.

**Fixvorschlag (Fix im aktuellen Code) – Korridor ja, aber richtig geschnitten.**
Die brauchbare Form ist nicht „Fenster halbieren", sondern **Korridor + Abzug der
Nachbarmoden** (klassische *peak stripping*-Iteration):
1. Summenfit einmal als **Startwertgeber** laufen lassen (oder direkt aus den
   Grenzgeraden-Bändern, die es in `fit/fenster_steuerung.py` /
   `fitmodell.py:384 startwerte_in_bereichen` bereits gibt).
2. Je Mode k: Modellbeitrag **aller anderen** Moden vom Messsignal abziehen und
   auf einem **symmetrischen** Korridor `B_res_k ± 2.5·dH_k` (dem bereits
   validierten Nachfenster-Faktor) einen **Ein-Moden-Fit** rechnen –
   `fitte_linescan(..., n_moden=1)`, also exakt der Referenzpfad aus 7c893e8.
3. 2–3 Iterationen. Jede Einzelmode hat dann 8 statt 12 Parameter auf ~25 statt
   106 Punkten; die Entartung „breite Linie ↔ Untergrundsteigung" ist weg, weil
   der Korridor gar nicht breit genug ist, um sie zuzulassen.

Das ist zugleich der Performance-Fix: statt 3–4 Multi-Fits à 397 Auswertungen
zwei bis drei Ein-Moden-Fits à ~66 Auswertungen.

**Alternative „Zurück auf Referenz".** 7c893e8 kennt nur den Ein-Moden-Fit im
Fenster. Der ist auf diesen Daten nachweislich stabil (identische Werte in HEAD,
Benchmark gegen FTF dokumentiert). Falls die Multi-Moden-Auswertung nicht
zwingend gebraucht wird, ist das Entfernen der risikoärmste Weg.

**Risiko des Korridor-Umbaus.** Hoch (Architekturänderung in `ergaenze_moden`),
aber der Ein-Moden-Fit, auf den er sich stützt, ist der validierte Referenzpfad.

---

## BUG E5 – Performance: 10.6× langsamer, davon ist ein großer Teil vermeidbar

**Symptom.** Nutzerbeobachtung (a): die Mehr-Moden-Suche dauert sehr lange.
629 Linescans: **3.6 s → 38.1 s**.

**Aufschlüsselung (alles oben gemessen):**

| Ursache | Datei:Zeile | Anteil / Faktor |
|---|---|---|
| bis zu 4 volle Fits je Linescan statt 2 | `batch.py:433-471` | ×2.7 |
| 4.2× mehr LM-Iterationen wegen Entartung | `fitmodell.py:225-245`, `linescan_fit.py:552-565` | ×4.2 (der Hauptposten) |
| 12 statt 8 freie Parameter (Jacobi) | `linescan_fit.py:541-571` | ×1.44 |
| asteval-`expr` `B_res_k = B_res_(k-1)+dB_k` | `linescan_fit.py:558` | +19 % (0.63 s / 3.40 s) |
| Fenster 106 statt 40 Punkte | `batch.py:403` | +11 % |
| `d**2`/`d**4` mehrfach | `suszeptibilitaet.py:51-65` | ~5 % des Modells |

**Fixvorschlag, nach Aufwand/Nutzen sortiert (alles „Fix im aktuellen Code"):**
1. **`expr` ersetzen** – statt `B_res_k = B_res_(k-1) + dB_k` je Mode direkt
   `params.add(f"B_res_{k}", value=…, min=…, max=…)` mit aus den Startwerten
   abgeleiteten, nicht überlappenden Intervallen (der `bereiche`-Pfad in
   `linescan_fit.py:546-552` macht genau das schon und ist gemessen 19 % schneller).
   Nebeneffekt: keine asteval-Abhängigkeit im heißen Pfad. Risiko niedrig.
2. **Kandidat (c) zuerst + früher Abbruch** (siehe Bug E1) – spart in 25/30
   Fällen zwei Multi-Fits. Risiko niedrig.
3. **Stufe-2-Fenster nicht aufweiten** (Bug E3) – 11 %. Risiko niedrig.
4. **Korridor statt Summenfit** (Bug E4) – der große Hebel, weil er die
   Iterationszahl senkt. Risiko hoch.
5. `chi_oop_komponenten`: `d2 = d*d; d4 = d2*d2` statt `d**2`/`d**4`. Risiko null.

---

## BUG E6 (klein) – Mindestabstand ist an die Abtastung, nicht an die Linienbreite gekoppelt

**Datei:Zeile.** `polderfit/fit/linescan_fit.py:514-515`

```python
schritt = float(np.ptp(B)) / max(B.size - 1, 1)
min_abstand = max(2.0 * schritt, 1e-6)
```

`min_abstand` = 2 Feldschritte = 5.08 mT im Testdatensatz. Das **verbietet keine
nahen Moden** (die Nutzerbeobachtung b kommt nicht daher – der Beweis ist Bug E1),
schafft aber die Attraktorlage aus Bug E4: im entarteten Minimum sitzen beide
Moden **genau** auf `min_abstand` (2699.7 / 2704.8 mT). Ein Fit, der auf der
`dB`-Untergrenze endet, ist per Definition entartet und sollte als
`problematisch` gelten – `bewerte_fit` prüft `dB_k`/`B_res`-Abstände nicht.

**Fixvorschlag.** In `bewerte_fit` zusätzlich prüfen: paarweiser Abstand zweier
Moden `<= 1.2 · min_abstand` → Grund „Moden nicht getrennt". Risiko null
(reine Kennzeichnung).

---

## Zusammenfassung / Empfehlung

| Bug | Kern | Empfehlung | Risiko |
|---|---|---|---|
| E1 | Kandidatensuche sperrt ±FWHM um die Hauptmode → 2. Mode landet in 25/30 Fällen daneben | Kandidat (c) zuerst; Sperrzone an die Abtastung koppeln | mittel |
| E2 | Nadel-Linien (`dH` < Feldschritt) werden Hauptmode; 60/603 bzw. 43/603 betroffen, keins als problematisch markiert | `alpha`-Untergrenze aus dem Feldschritt + Kriterium + robustere Hauptmodenwahl | mittel |
| E3 | Stufe 2 wirft das validierte ±2.5·dH-Nachfenster weg (40 → 106 Punkte) | Fenster nicht aufweiten | niedrig |
| E4 | **Inhärent:** freier Summenfit über den vollen Sweep ist nicht identifizierbar (15/40 Startwerte → Fehlminimum mit 51-mT-„Untergrundlinie", das die Annahmekriterien passiert) | Korridor + Nachbarabzug + Ein-Moden-Fit je Mode; alternativ Feature entfernen (Referenz 7c893e8) | hoch |
| E5 | 10.6× langsamer; Entartung ist der Hauptposten, `expr`/Kandidaten/Fenster zusammen ~35 % | 1.–3. sofort, 4. mit E4 | niedrig–hoch |
| E6 | Entartetes Minimum sitzt auf `min_abstand` und wird nicht erkannt | Kriterium „Moden nicht getrennt" | null |

**Der Ein-Moden-Pfad (= Referenz 7c893e8) ist in HEAD unverändert korrekt.**
Wenn die Zwei-Moden-Auswertung produktiv gebraucht wird, ist E4 der eigentliche
Umbau; E1–E3 und E6 sind lokale, gut abgesicherte Korrekturen, die die
sichtbarsten Fehler (Mode weit weg, `dH` unter der Abtastgrenze, zu breites
Fenster) beheben und die Laufzeit um grob ein Drittel senken.

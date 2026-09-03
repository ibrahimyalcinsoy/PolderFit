# Bereich B – Linescan-Fit, Fensterlogik (HEAD e3b1ea7 vs. Referenz 7c893e8)

Interpreter HEAD `/home/ibrahim/Dokumente/Ananas/.venv/bin/python`,
Referenz `/home/ibrahim/Dokumente/polderfit-ref/.venv/bin/python`.
Testdatei: `testdata-n-lorentz/2025-NOV-11-Linescan-2D-map-oop-5K_1.1deg-for-FTF.tdms`
(629 Frequenzen, 196–198 Feldpunkte je Linescan).
Skripte: `../vergleich_fenster.py`, `../leerer_stapel_test.py`, `../gui_repro.py`,
`../gui_repro_ref.py`, `../nachfit_bestaetigen.py`, `../zweistufig_fenster.py`,
`../problemfit_nav.py`.

---

## 0. Vorabbefund: Der AUTO-FIT ist NICHT kaputt

`fitte_alle` → `auto_fenster_alle` → `fitte_mit_nachfenster` ist in HEAD und
Referenz funktional identisch (`git diff 7c893e8 -- polderfit/fit/autowindows.py`
enthält nur einen `fortschritt`-Callback). Gemessen über alle 629 Frequenzen:

| i | f/GHz | HEAD Fenster [T] | n | B_res | µ₀ΔH | REF Fenster [T] | n | B_res | µ₀ΔH |
|---|-------|------------------|---|-------|------|-----------------|---|-------|------|
| 52  | 9.67  | [2.6758, 2.7852] | 43 | 2.7294 | 16.79 | [2.6758, 2.7852] | 43 | 2.7294 | 16.79 |
| 208 | 20.59 | [3.0689, 3.1538] | 34 | 3.1107 | 15.59 | identisch | 34 | 3.1107 | 15.59 |
| 416 | 35.14 | [3.5506, 3.6650] | 45 | 3.6064 | 21.97 | identisch | 45 | 3.6064 | 21.97 |
| 624 | 49.70 | [4.0551, 4.1605] | 43 | 4.1073 | 20.74 | identisch | 43 | 4.1073 | 20.74 |

Maximale Abweichung über alle 629 Zeilen: **< 1e-9 relativ** (LM-Iterationsrauschen,
verschiedene venv-Builds). Das Fenster wandert in HEAD sauber mit der Mode mit
(2.60 T bei 6 GHz → 4.11 T bei 49.7 GHz), Breite 33–47 von ~197 Punkten.

**Die Nutzerbeobachtung „der Fit sucht im gesamten Feldsweep" trifft also NICHT
den Auto-Fit, sondern die neu hinzugekommenen Wege OHNE Auto-Fit (Bug B1).**

---

## Bug B1 (Hauptbefund) – „Fits ohne Auto-Fit": Fenster = ganzer Feldsweep

### Symptom
Nach dem Laden einer TDMS-Datei steht im Linescan-Panel als grünes Band der
**ganze Feldsweep**. „Neu fitten" und das Ziehen der grünen Grenzen fitten dann
über alle ~197 Feldpunkte statt über die ~35 Punkte des mitwandernden
Mode-Fensters. Die Fensterführung entlang der Mode existiert in diesem Zustand
überhaupt nicht: jede Frequenz startet wieder beim vollen Sweep.

### Reproduktion (headless GUI, `../gui_repro.py`)
```
QT_QPA_PLATFORM=offscreen timeout 300 .venv/bin/python gui_repro.py
```
Klickfolge: TDMS laden → Frequenz im Farbplot anklicken (Panel öffnet auch ohne
Fit, `hauptfenster.py:3110 _frequenz_gewaehlt`) → „Neu fitten".

```
Stapel nach Laden: StapelErgebnis n=629 gefittet: 0
Gruene Grenzen im Panel: [3.1129, 3.6099] T = 196 von 196 Punkten
Nach 'Neu fitten': Fenster [3.1129,3.6099] B_res=3.3600 dH=18.39 mT
                   bewertung=bestaetigt problematisch=False
Statuszeile: [313/629] f=27.866 GHz │ … │ µ₀ΔH=18.39 mT │ Fenster 196 Pkt │
             vom Nutzer als gut bestätigt
```

Referenz an derselben Stelle (`../gui_repro_ref.py`):
```
REF nach Laden: ergebnisse = 0  fenster = 0
REF 'Nochmal fitten' ohne Auto-Fit -> ergebnisse: 0 (kein Fit moeglich)
```

### Quantitativer Schaden (`../leerer_stapel_test.py`)
Gleicher Linescan, gleiche Verarbeitung, gleiche Parameter – nur das Fenster
unterscheidet sich:

| i | f/GHz | Auto-Fenster | n | µ₀ΔH/mT | Sweep-Fenster | n | µ₀ΔH/mT | Δ |
|---|-------|--------------|---|---------|---------------|---|---------|---|
| 52  | 9.67  | [2.6758,2.7852] | 43 | 16.79 | [2.4867,2.9856] | 197 | 22.56 | **+34 %** |
| 104 | 13.31 | [2.8101,2.9063] | 38 | 16.33 | [2.6128,3.1101] | 197 | 19.74 | +21 % |
| 208 | 20.59 | [3.0689,3.1538] | 34 | 15.59 | [2.8617,3.3584] | 196 | 17.29 | +11 % |
| 312 | 27.87 | [3.3147,3.4053] | 35 | 17.44 | [3.1129,3.6099] | 196 | 18.39 | +5 % |
| 520 | 42.42 | [3.8132,3.8968] | 33 | 14.37 | [3.6130,4.1077] | 197 | 18.56 | **+29 %** |
| 624 | 49.70 | [4.0551,4.1605] | 43 | 20.74 | [3.8617,4.3594] | 198 | 21.65 | +4 % |

`B_res` bleibt praktisch gleich (≤ 1.6 mT), **µ₀ΔH wird systematisch zu groß**
(bis +34 %) – genau der Effekt, gegen den `NACHFENSTER_FAKTOR_STANDARD = 2.5`
im FTF-Benchmark eingeführt wurde (`batch.py:24-38`). Die Fits melden sich dabei
NICHT als problematisch (R² = 0.999 auf dem breiten Fenster).

### Datei:Zeile / Root Cause
* `polderfit/fit/batch.py:480-511` `leerer_stapel(...)`, konkret
  `batch.py:505-508`:
  ```python
  for ls in datensatz.linescans:
      if ls.feld.size:
          stapel.fenster.append((float(ls.feld.min()), float(ls.feld.max())))
  ```
  Das Fenster jeder Frequenz ist der komplette Feldsweep.
* `polderfit/gui/hauptfenster.py:1823` `self.stapel = self._leerer_stapel(datensatz)`
  (in `_datensatz_uebernehmen`), `hauptfenster.py:1838-1844`.
* Verbraucher, die dieses Fenster ungeprüft übernehmen:
  `hauptfenster.py:2344-2350` `_neu_fitten` (`unten, oben = self.stapel.fenster[i]`),
  `hauptfenster.py:2168-2176` `_zeige_aktuellen` (zeichnet die grünen Grenzen),
  `hauptfenster.py:2321-2330` `_grenzen_geaendert`.
* Panel wird ohne Fit geöffnet: `hauptfenster.py:3110-3127` `_frequenz_gewaehlt`.

Eingeführt mit **45871fa** (2026-08-25, „GUI/HMI-Umbau … Fits ohne Auto-Fit …"):
`git log -S "def leerer_stapel" -- polderfit/fit/batch.py`.

### Diff zu 7c893e8
Referenz `polderfit/gui/hauptfenster.py:1156`:
```python
self.stapel = StapelErgebnis(datensatz=datensatz)   # ergebnisse=[], fenster=[]
```
`_zeige_aktuellen`/`_neu_fitten` steigen dort sofort aus
(`if not self.stapel or not self.stapel.ergebnisse: return`); das Linescan-Panel
erscheint erst über `_nach_autofit` (`ref:1228-1238`). Damit war in 7c893e8
**jedes** Fenster im Panel ein AutoWindow- bzw. Nachfenster-Fenster.
`leerer_stapel` existiert in 7c893e8 nicht.

### Fixvorschlag (Fix im aktuellen Code, Referenz nicht zurückholen –
`leerer_stapel` ist ein gewolltes Feature)
1. **Bevorzugt:** in `leerer_stapel` kein Vollsweep-Fenster setzen, sondern für
   jeden Linescan das AutoWindow rechnen – `auto_fenster_alle(datensatz, gamma,
   breite_faktor)` einmalig (dauert auf dem Testsatz ~Sekunden, ist derselbe
   Vorlauf wie Phase 1 des Auto-Fits) oder lazy je Index über
   `auto_fenster_intervalle(..., {i: (feld_min, feld_max)}, ...)` beim ersten
   Anzeigen/Fitten dieser Frequenz. Dann stehen die grünen Grenzen von Anfang an
   auf der Mode.
2. **Minimal:** `_neu_fitten` und `_grenzen_geaendert` durch
   `fenster_steuerung._fitte_neu_mit_nachfenster(stapel, i, unten, oben)`
   statt `fitte_neu` führen – dann greift wenigstens der zweite Durchgang
   `B_res ± 2.5·µ₀ΔH` und die Linienbreite landet wieder auf dem Plateau.
   (Betrifft auch den Fall MIT Auto-Fit, siehe Bug B4.)
3. **Zusätzlich:** wenn `stapel.fenster[i]` mehr als z. B. 60 % der Feldpunkte
   umfasst, in der Statuszeile/Panel warnen („Fenster = ganzer Feldsweep –
   Linienbreite wird überschätzt").

### Risiko
Variante 1: mittel – `leerer_stapel` wird beim Laden aufgerufen, das
AutoWindow-Vorrechnen kostet Zeit (auf dem 87-MB-Satz relevant); daher lazy
rechnen oder im Hintergrundjob. Variante 2: gering, rein lokal.

---

## Bug B2 – „Neu fitten" markiert das Ergebnis ungeprüft als „gut"

### Symptom
„Neu fitten" (Knopf `btn_neu`, Beschriftung „Neu fitten", Tooltip/Hilfe nennen
ihn „Nochmal fitten") rechnet mit **unverändertem** Fenster und **unveränderten**
Startwerten – liefert also exakt dasselbe Ergebnis – stuft es aber danach als
„vom Nutzer als gut bestätigt" ein. Ein schlechter Fit verschwindet damit aus
der Problemliste, ohne dass sich irgendetwas verbessert hat.

### Reproduktion (`../nachfit_bestaetigen.py`)
```
Problemfits nach Auto-Fit: 24 -> [0, 1, 3, 9, 10, 11, ...]
vorher  i=0 f=6.03 GHz  problematisch=True
        gruende=['alpha an Grenze', 'alpha unphysikalisch'] bewertung=auto
nachher i=0            problematisch=False  auto=True
        gruende=['alpha an Grenze', 'alpha unphysikalisch'] bewertung=bestaetigt
Problemfits danach: 23
B_res 2.603159 -> 2.603159 | dH 43.077 -> 43.077 mT | rmse_norm 0.1175 -> 0.1175
```
Klickfolge: Auto-Fit → „Problemfit ▶" → „Neu fitten" → der Fit ist grün.

### Datei:Zeile / Root Cause
* `polderfit/fit/batch.py:559-562`
  ```python
  if bestaetigen is None:
      bestaetigen = bool(stapel.nachfit_bestaetigen)
  if bestaetigen:
      ergebnis = setze_bewertung(ergebnis, "bestaetigt")
  ```
* `polderfit/fit/batch.py:122` `nachfit_bestaetigen: bool = True` (Stapel-Default),
  `polderfit/fit/parameter.py:70` `nachfit_bestaetigen: bool = True`.
* `polderfit/fit/linescan_fit.py:242-260` `setze_bewertung` setzt
  `problematisch = False` unabhängig von `problematisch_auto`.
* Aufrufer ohne eigene Prüfung: `hauptfenster.py:2344-2350` `_neu_fitten`,
  `hauptfenster.py:2321-2330` `_grenzen_geaendert`.

Eingeführt mit **45871fa**.

### Diff zu 7c893e8
`fitte_neu` in 7c893e8 (`ref batch.py:282-314`) kennt weder `bestaetigen` noch
`bewertung`; `ergebnis.problematisch` bleibt das reine Kriterienergebnis:
```python
    ergebnis.nachbearbeitet = True
    stapel.zugeschnitten[index] = beschnitten
    stapel.ergebnisse[index] = ergebnis
    return ergebnis
```

### Fixvorschlag
„Bestätigen" nur, wenn der Nutzer wirklich etwas geändert hat, und nur bei
Verbesserung:
* `_neu_fitten` (identisches Fenster, keine neuen Startwerte) mit
  `bestaetigen=False` aufrufen – ein Klick auf „Neu fitten" ist keine Bewertung.
* Beim Grenzen-Ziehen nur bestätigen, wenn `not ergebnis.problematisch_auto`
  (also die Kriterien den Fit ohnehin durchlassen); sonst „auto" lassen und die
  Bewertung dem expliziten Strg+1 überlassen.
* Alternativ Default `nachfit_bestaetigen=False` (Parameterdialog behält den
  Schalter).
Beschriftung vereinheitlichen („Nochmal fitten" in Tooltip/Hilfe vs. „Neu fitten"
auf dem Knopf, `hauptfenster.py:277, 2197, 3192`).

### Risiko
Gering. Nutzer, die sich auf das Auto-Bestätigen verlassen, müssen wieder
Strg+1 drücken – das ist die dokumentierte Bewertungsgeste.

---

## Bug B3 – Zweistufiger Auto-Fit weitet das Nachfenster wieder auf

### Symptom
Bei `n_moden > 1` mit „zweistufig" wird das im 1. Durchgang gefundene
Nachfenster (`B_res ± 2.5·µ₀ΔH`) verworfen und durch das breite AutoWindow
ersetzt – das Fitfenster wächst um Faktor ~2.8.

### Reproduktion (`../zweistufig_fenster.py`, 60 Linescans, i = 100…159)
```
  i   f/GHz |        1 Mode: Fenster    n  dH/mT |     2 Moden zweistufig    n  dH/mT #M
  0   13.03 | [2.8028,2.8936]   36  14.53 | [2.7182,2.9754]  102  15.90   2
  4   13.31 | [2.8101,2.9063]   38  16.33 | [2.7258,2.9879]  104  16.23   2
 11   13.80 | [2.8285,2.9214]   37  15.52 | [2.7425,3.0056]  104  16.13   2
Fenster geaendert bei 60/60 Linescans
Mehr-Moden uebernommen: 60
```
Auf einem Satz, der einmodig ausgewertet wird, wird an **allen** 60 Linescans
eine zweite Mode akzeptiert und das Fenster verdreifacht.

### Datei:Zeile / Root Cause
`polderfit/fit/batch.py:339` `fenster_auto = list(fenster)` (die BREITEN
AutoWindows vor der Nachfenster-Verengung), `batch.py:356-363` Aufruf, und
`batch.py:400-404` in `ergaenze_moden`:
```python
st_unten, st_oben = stapel.fenster[index]                     # verengtes Nachfenster
unten, oben = fenster if fenster is not None else (st_unten, st_oben)
unten, oben = min(float(unten), float(st_unten)), max(float(oben), float(st_oben))
```
`max`/`min` nehmen immer das breitere von beiden; `batch.py:474`
`stapel.fenster[index] = (unten, oben)` schreibt es fest.
Der Phantomfilter `PHANTOM_FAKTOR = 0.95` (`batch.py:369, 468`) verlangt nur
5 % kleineres Residuum – auf dem breiten Fenster mit strukturiertem Untergrund
ist das leicht durch eine zweite Lorentzkurve zu erreichen.

Eingeführt mit **798b794** (2026-08-26).

### Diff zu 7c893e8
`ergaenze_moden`/`zweistufig` gibt es in 7c893e8 nicht; dort endet `fitte_alle`
nach `stapel.fenster[i] = verwendet` (dem Nachfenster).

### Fixvorschlag
Nach erfolgreicher Moden-Ergänzung einen Nachfenster-Durchgang über die Hülle
**aller** gefundenen Moden fahren (`min_k B_res_k − 2.5·µ₀ΔH_k`,
`max_k B_res_k + 2.5·µ₀ΔH_k`) statt das AutoWindow stehen zu lassen; und
`PHANTOM_FAKTOR` verschärfen (z. B. 0.85) bzw. eine Mindest-Signalhöhe der
Nebenmode relativ zur Hauptmode verlangen. Der zweistufige Modus ist nicht
Default (`parameter.py:66 auto_fit_zweistufig = False`), daher kein Rollback nötig.

### Risiko
Mittel – ändert die Ergebnisse des Moden-Modus. Vorher gegen die 10/12 als gut
befundenen Sätze (Memory „Multi-Moden-Check 2026-08-26") gegenprüfen.

---

## Bug B4 – „Neu fitten"/„Grenzen ziehen" fahren keinen Nachfenster-Durchgang

### Symptom
Der Bereichs-/Grenzgeraden-Fit ruft `_fitte_neu_mit_nachfenster`
(`fenster_steuerung.py:311-333`) und bekommt damit den zweiten, verengten
Durchgang. Die beiden Einzelfrequenz-Wege im Linescan-Panel rufen `fitte_neu`
direkt und bekommen ihn NICHT. Ein von Hand gezogenes, etwas zu breites Band
liefert deshalb eine zu große Linienbreite, während derselbe Bereich über den
Bereichs-Fit korrekt verengt würde.

### Datei:Zeile
`hauptfenster.py:2321-2330` `_grenzen_geaendert`, `hauptfenster.py:2344-2350`
`_neu_fitten` – beide `fitte_neu(...)` ohne `nachfenster`.

### Diff zu 7c893e8
Identisch – in 7c893e8 (`ref hauptfenster.py:1454-1481`) ebenfalls ohne
Nachfenster. **Keine Regression**, aber in Kombination mit B1 (Fenster = ganzer
Sweep) der Grund, warum der Fehler dort ungebremst durchschlägt.

### Fixvorschlag / Risiko
`_fitte_neu_mit_nachfenster` statt `fitte_neu` verwenden (deckt B1 Variante 2 mit
ab). Risiko gering; ändert bestehende Handfits leicht (dH sinkt Richtung Plateau).

---

## 3. Checkbox „ganzer Feldsweep" – reine Anzeige, kein Fit-Einfluss

* Definition: `hauptfenster.py:298-300` (`self.chk_vollbereich`, Panel) und
  `hauptfenster.py:556-564` (Menüaktion `akt_vollbereich`, Ansicht-Menü,
  beide Richtungen gespiegelt).
* Wirkung: `hauptfenster.py:3088-3091` `_vollbereich_umschalten` →
  `fit_ansicht.py:221-224` `setze_vollbereich` → nur `_berechne_xlim`
  (`fit_ansicht.py:196-219`), also die **x-Achsengrenzen** des Linescan-Panels.
  Kein Einfluss auf `stapel.fenster`, `schneide_band` oder die Fitschranken.
* Default: **aus** (`fit_ansicht.py:60 self._vollbereich = False`,
  `persistenz/einstellungen.py:53 "vollbereich": False`); in HEAD wird der Wert
  über die Einstellungen persistiert (`hauptfenster.py:2998, 3013`).
* Referenz 7c893e8: identische Semantik (`ref fit_ansicht.py:52, 170`,
  `ref hauptfenster.py:208-210, 348-351, 1797`), nur ohne Persistenz.
* **Kein Bug.** Aber ein Wahrnehmungsproblem: durch B1 zeigt das Panel nach dem
  Laden ohnehin den ganzen Sweep (das Band IST der Sweep), sodass der
  „Zoom aufs Band" wirkungslos wirkt.

---

## 4. „Neu fitten" – Zusammenfassung

* Was: `hauptfenster.py:2344-2350` – dieselbe Frequenz, **Fenster =
  `stapel.fenster[i]` unverändert**, Startwerte = Neuschätzung aus den Daten
  (kein `startwerte=`, kein `B_res_vorgabe=`), Modenzahl = `spin_moden`
  (Panel-Auswahl, nicht zwingend die des Auto-Fits).
* Funktioniert es? Technisch ja (Ergebnis wird gesetzt, Undo-Eintrag erzeugt,
  Overlay/Kittel-Fenster aktualisiert). **Praktisch aber:**
  – ohne Auto-Fit ist das Fenster der ganze Sweep (**B1**),
  – das Ergebnis ist bei unveränderten Eingaben bitgleich, wird aber als „gut"
    bestätigt (**B2**),
  – kein Nachfenster-Durchgang (**B4**),
  – `n_moden` kommt aus dem Panel-Spin: steht dort „Res.: 2", wird auch eine
    einmodige Frequenz zweimodig gefittet (`hauptfenster.py:2349`).
* Referenz: `ref hauptfenster.py:1475-1488` – identisch bis auf `n_moden` und
  die Bestätigung.

---

## 5. „Problemfit"-Navigation

* Kriterium: `batch.py:185-192`
  ```python
  return [i for i, e in enumerate(self.ergebnisse) if e.problematisch and e.gefittet]
  ```
  `problematisch` ist der **wirksame** Zustand, d. h. Nutzerbewertung schlägt die
  Kriterien (`linescan_fit.py:242-260`). Kriterien selbst: `kriterien.py:91-160`
  (a Residuum, b Parameter an Schranke, c B_res außerhalb Fenster,
  d alpha unphysikalisch, e Kovarianz, f relative Unsicherheit) – in HEAD für
  **jede Mode** geprüft.
* Funktion: `hauptfenster.py:2215-2226` `_naechster_problemfit`, Knopf
  `hauptfenster.py:274, 304` („Problemfit ▶").

### B5.1 – Es gibt nur „vorwärts", kein „zurück"
`../problemfit_nav.py`:
```
btn_… vorhanden: ['btn_abbrechen', 'btn_abbrechen_dock', 'btn_hauptmode',
 'btn_laden', 'btn_logo', 'btn_naechstes_problem', 'btn_neu', 'btn_weiter',
 'btn_zurueck']
```
`btn_zurueck`/`btn_weiter` sind reine Frequenznavigation (`_navigiere(±1)`).
Ein „Problemfit ◀" existiert weder in HEAD noch in 7c893e8
(`ref hauptfenster.py:199`) – **kein Regressionsbug, aber ein fehlendes Feature**.
Fix: Gegenstück mit `frueher = [i for i in probleme if i < self.aktueller_index]`,
`ziel = frueher[-1] if frueher else (probleme[-1] if probleme else None)`,
Knopf „◀ Problemfit" plus Tastenkürzel. Risiko: sehr gering.

### B5.2 – Ignorierte Ausreißer bleiben Problemfits
```
i=0 als Ausreisser markiert -> in index_problematisch()? True (Statusfarbe: ignoriert)
```
`_ausreisser_gewaehlt` (`hauptfenster.py:2758-2777`) trägt den Index nur in
`stapel.ausreisser` ein; `problematisch` bleibt `True`, also springt
„Problemfit ▶" immer wieder auf Punkte, die der Nutzer bereits als
„ignoriert" (grau) abgehakt hat. In der Anzeige heißt der Status „ignoriert"
(`farben.py:135-152 status_von`), in der Navigation „Problem" – widersprüchlich.
Gleiches Verhalten in 7c893e8 → keine Regression.
Fix: in `_naechster_problemfit` (oder in `index_problematisch`) die Menge
`stapel.ausreisser` ausnehmen. Risiko: gering; `index_problematisch` wird auch
für die Log-Zählung benutzt – dort ggf. weiter alle zählen und nur die
Navigation filtern.

### B5.3 – Umlauf ohne Rückmeldung
```
Von letztem Problemfit 29 -> Sprung nach 0 (Umlauf ohne Hinweis)
```
`hauptfenster.py:2219-2220`: `ziel = spaeter[0] if spaeter else probleme[0]`.
Ist der aktuelle Index der EINZIGE Problemfit, springt die Funktion auf sich
selbst – der Knopf scheint nicht zu reagieren. Gleiches Verhalten in 7c893e8.
Fix: beim Umlauf `self._log("Umlauf: zurück zum ersten Problemfit.", "info")`
bzw. bei `ziel == self.aktueller_index` eine Meldung. Risiko: keins.

### B5.4 – Wechselwirkung mit B2 (die eigentliche Falle)
Der übliche Korrekturlauf „Problemfit ▶ → Neu fitten → Problemfit ▶" arbeitet
die Liste ab, **ohne dass sich ein einziger Fit verbessert** (siehe B2:
identische Zahlen, Bewertung „bestätigt"). Der Nutzer endet mit
„Keine problematischen Fits mehr", obwohl alle Kriterien weiterhin verletzt
sind (`problematisch_auto=True`). Das ist die gravierendste Verhaltensänderung
gegenüber 7c893e8 im Korrekturlauf.

---

## Priorisierung

| Bug | Regression ggü. 7c893e8 | Physikalischer Einfluss | Empfehlung |
|-----|-------------------------|--------------------------|------------|
| B1 Fenster = ganzer Sweep ohne Auto-Fit | **ja** (45871fa) | µ₀ΔH bis +34 % | AutoWindow in `leerer_stapel`, sonst Nachfenster erzwingen |
| B2 „Neu fitten" bestätigt ungeprüft | **ja** (45871fa) | verdeckt schlechte Fits | `bestaetigen=False` bei unverändertem Fenster |
| B3 zweistufig weitet Fenster | **ja** (798b794) | µ₀ΔH ±10 %, Phantommoden | Nachfenster über Modenhülle, Phantomfilter schärfen |
| B4 kein Nachfenster im Panel | nein | verstärkt B1 | `_fitte_neu_mit_nachfenster` verwenden |
| B5.1 kein „Problemfit ◀" | nein | – | Feature ergänzen |
| B5.2 Ausreißer bleiben Problemfits | nein | – | in der Navigation filtern |
| B5.3 stiller Umlauf | nein | – | Meldung ergänzen |

Ein Rollback auf 7c893e8 ist für keinen der Punkte nötig: der Auto-Fit-Kern
(AutoWindows, Nachfenster, Einzelfit) ist nachweislich unverändert und
numerisch identisch.

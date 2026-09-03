# Bereich G – Ausreißer / ROI / Kriterien

HEAD: `/home/ibrahim/Dokumente/Ananas` (V0.1.66, e3b1ea7) · Referenz: `/home/ibrahim/Dokumente/polderfit-ref` (7c893e8)
Alle Repro-Skripte: `…/scratchpad/bugs/repro_*.py` (offscreen, mit `.venv/bin/python`).
Es wurde **keine Datei im Repo geändert**.

Testlage: `tests/test_ausreisser.py`, `test_ausreisser_gui.py`, `test_kriterien.py`, `test_auswahl*.py`,
`test_modus_manager.py` laufen in **beiden** Versionen grün (41 passed). Gesamtsuite HEAD: 233 passed, 4 skipped.

---

## 1. „Ausreißer markieren" – Kette und Bruchstellen

### 1.1 Ablauf in 7c893e8 (Referenz)

* Farbplot: `matrix_ansicht.setze_ausreisser_modus(True, gewaehlt=…)` → Modus-Manager `"ausreisser"`.
  Klick → `_ausreisser_klick` (Toleranz 0.03 der Achsenspanne), Kasten → `_ausreisser_kasten`.
  Kandidaten (`_sichtbare_resonanzpunkte`, ref `matrix_ansicht.py:747`):
  `sichtbar = ~ausgeschlossen`, zusätzlich `& ~problem`, wenn Problemfits ausgeblendet.
* Kittel-Fenster: `auswertung_fenster._on_release` (ref `:254 ff.`) → `self._cb_markieren(indizes)`
  mit **Stapel-Indizes** direkt.
* Hauptfenster: `_ausreisser_gewaehlt` → `StapelErgebnis.ausreisser_umschalten` → `_aktualisiere_overlay`
  → Kittel/LLG rechnet über `ergebnisse_aktiv()` ohne diese Punkte. Undo über `_merke_ausreisser_aenderung`.
  Projekt: Schlüssel `ausreisser`.

### 1.2 Ablauf in HEAD

Identisch, plus:
* `_sichtbare_resonanzpunkte` (`polderfit/gui/matrix_ansicht.py:947-956`) arbeitet jetzt über die
  Statusklassen (`farben.status_von`) statt über `~ausgeschlossen`.
* Zweite Ausschluss-Art `StapelErgebnis.ausreisser_moden` (`fit/batch.py:136`), Paare `(index, mode)`,
  nur für die Kittel/LLG-Auswertung *einer* Mode; Umschalter `ausreisser_mode_umschalten`.
* `auswertung_fenster._punkte_entfernen` (`:449-465`) verteilt Treffer auf `_cb_markieren`
  (Hauptmode-Ansicht) bzw. `_cb_markieren_mode` (Mode-Ansicht).
* Panel listet beides (`gui/ausreisser_panel.py:74-110`), Projekt speichert `ausreisser_moden`
  (`persistenz/projekt.py:79, 169`).

### 1.3 Reproduktion – die Kette ist **intakt**

`repro_ausreisser.py` (synthetisch) und `repro_real.py` (629 Linescans, echtes TDMS, echter Auto-Fit):

```
modus: ausreisser  checked: True   modus_cb: Hauptfenster._ausreisser_gewaehlt
sichtbare Punkte: 629 von 629
Klick auf Index 314 -> stapel.ausreisser = [314]
Kasten -> stapel.ausreisser = [2, 3, 4, 6]          (synthetisch)
Kittel-Fenster: Klick auf Plotpunkt -> ausreisser 1 -> 2, Punkt verschwindet aus dem Fit
```

`repro_moden.py` (n_moden=2, alle vier Ansichten Hauptmode / Mode 1 / Mode 2 / Alle Moden):
jeder Klick entfernt genau einen Punkt, `ausreisser` bzw. `ausreisser_moden` wachsen korrekt.

**Ergebnis: Es gibt keinen generellen Bruch.** Ausreißer-Markierung funktioniert per Klick und
per Kasten, im Farbplot wie im Kittel-Fenster, ein- und mehrmodig. Was der Nutzer erlebt, muss
einer der folgenden *stillen Sonderfälle* sein (alle reproduziert, `repro_grau.py`).

---

### BUG G-1 (neu in HEAD): Klick auf einen grau angezeigten Punkt tut nichts und meldet nichts

**Symptom** Ansicht → „Ignorierte Punkte (Ausreißer) grau anzeigen" ist an. Der Nutzer sieht die
grauen Punkte, klickt sie im Ausreißer-Modus an, um sie wieder aufzunehmen – nichts passiert,
keine Statusmeldung, kein Protokolleintrag. Genau das Bild „Funktion ohne Wirkung".

**Reproduktion** `repro_grau.py`:
```
1. markiert: [6]
sichtbare Kandidaten (grau an): [0 1 2 3 4 5 6 7 8 9]     <- Punkt 6 IST Klickziel
2. Klick auf grauen Punkt 6 -> ausreisser: [6]            <- unverändert, keine Meldung
```

**Datei:Zeile**
* `polderfit/gui/matrix_ansicht.py:947-956` (`_sichtbare_resonanzpunkte`) – nimmt „ignoriert" in die
  Kandidatenliste auf, sobald `_ausreisser_anzeigen` gesetzt ist (`_status_sichtbar`, `:549-555`).
* `polderfit/gui/hauptfenster.py:2758-2764` (`_ausreisser_gewaehlt`):
  `neu = [i for i in indizes if not self.stapel.ist_ausreisser(i)]` → `if not neu: return` (stumm).

**Root Cause** In HEAD können bereits ignorierte Punkte Klickziel sein (neue Anzeigeoption
„grau anzeigen"), der Empfänger-Slot ist aber weiterhin rein „hinzufügend" und bricht ohne
Rückmeldung ab. In 7c893e8 konnte der Fall nicht auftreten: dort galt hart
`sichtbar = ~ausgeschlossen`, ignorierte Punkte wurden weder gezeichnet noch getroffen.

**Diff zu 7c893e8** (`git diff 7c893e8 -- polderfit/gui/matrix_ansicht.py`)
```
-        ausgeschlossen = (self._res_ausgeschlossen … )
-        sichtbar = ~ausgeschlossen
-        if self._problemfits_ausblenden:
-            sichtbar &= ~self._res_problem
+        status = self._status_array()
+        sichtbar = np.isfinite(self._res_bres)
+        for klasse in ("gut", "bestaetigt", "problem", "fehler", "ignoriert"):
+            if not self._status_sichtbar(klasse):
+                sichtbar &= status != klasse
```

**Fixvorschlag** (Fix im aktuellen Code, klein) – `_ausreisser_gewaehlt` zu einem Umschalter machen:
bereits ignorierte Indizes an `_ausreisser_wieder_aufnehmen` weiterreichen statt zu verwerfen.
Minimalvariante: im leeren Fall `self._log("… bereits ignoriert – Wieder aufnehmen im Panel", "info")`.
**Risiko** gering; Kasten-Markierung würde beim Umschalter-Verhalten allerdings gemischte Auswahlen
kippen – dort weiterhin nur hinzufügen, nur der Einzelklick schaltet um.

---

### BUG G-2 (schon in 7c893e8, aber verschärft): ausgeblendete Problemfits sind nicht markierbar

**Symptom** „Ansicht → Problemfits ausblenden" ist an. Genau die auffälligen (gelben/roten) Punkte,
die der Nutzer als Ausreißer entfernen will, sind weder sichtbar noch klickbar; ein Klick auf ihre
Position markiert entweder gar nichts oder – bei dichten Datensätzen – den *benachbarten guten* Punkt.

**Reproduktion** `repro_grau.py`:
```
Kandidaten (Problemfits aus): [0 1 2 5 7 8 9]     (3 und 4 = problematisch, fehlen)
3. Klick auf ausgeblendeten Problemfit 3 -> ausreisser: [6]   (unverändert)
```
Bei 629 Punkten liegt der nächste sichtbare Nachbar innerhalb der Toleranz `_PUNKT_TOLERANZ = 0.03`
→ dann wird der **falsche** Punkt ignoriert.

**Datei:Zeile** `matrix_ansicht.py:549-556` (`_status_sichtbar`), `:958-971` (`_naechster_punkt`).

**Root Cause** Sichtbarkeit und Treffbarkeit sind gekoppelt; die Toleranz ist absolut (3 % der
Achsenspanne) statt „nächster Punkt, aber nur wenn deutlich näher als der zweitnächste".

**Fixvorschlag** Fix im aktuellen Code: ausgeblendete Klassen als Klickziel *zulassen* (sie sind ja
gemeint) oder wenigstens Statusleisten-Hinweis „Punkt ausgeblendet – Problemfits einblenden".
**Risiko** gering.

---

### Nebenbefunde (kein Bug, aber Bedienfallen)

* `gui/hauptfenster.py:2234-2236` – in der Bewertungsliste bewirkt „ignorieren (Ausreißer)" bei einem
  bereits ignorierten Punkt **nichts** (`return  # schon ignoriert`), während `Strg+I`
  (`_bewerte_aktuellen`, `:2249-2257`) umschaltet. Zwei Wege, zwei Verhalten.
* `gui/hauptfenster.py:2262-2264` – jede andere Bewertung („gut bestätigen", „automatisch (Kriterien)")
  hebt den Ausreißer-Status *stillschweigend* auf.
* `_ausreisser_modus` (`:1324-1336`) verlangt `_modus_start_erlaubt(braucht_fits=True)`. Ohne Fits
  springt der Menüpunkt sofort wieder auf „aus" – Meldung nur im Protokoll/Statusleiste.

---

## 2. ROI – was es ist, wo es wirkt

**Definition** ROI = Rechteck **Feld × Frequenz** `(feld_min, feld_max, f_min_GHz, f_max_GHz)`.
Es ist ausschließlich eine **Vorbelegung der Eingabefelder des Auto-Fit-Dialogs**, kein eigener
Zustand des Programms.

**Alle Verwendungsstellen**

| Stelle | Datei:Zeile | Wirkung |
|---|---|---|
| Knopf „ROI im Farbplot aufziehen …" | `gui/auswahl_dialog.py:135-141, 238-244` | schließt Dialog mit `ROI_AUFZIEHEN = 2`, Eingaben als `zwischenstand()` |
| Rückgabetyp | `gui/auswahl_dialog.py:32-38` (`RoiAnfrage`) | trägt Auswahl + n_moden + zweistufig über den Umweg |
| Rechteck-Modus | `gui/hauptfenster.py:1890-1908` (`_roi_im_farbplot`) | startet `matrix.starte_bereichs_fit(...)`, Modus `"bereich"` |
| Abbruch (Esc) | `gui/hauptfenster.py:986-989`, `1910-1916` | `QTimer.singleShot(0, _roi_abbruch_pruefen)` → Dialog ohne ROI erneut |
| Wiederaufnahme | `gui/hauptfenster.py:1996-2011` (`_auto_fit_fortsetzen`) | öffnet Dialog mit `roi_bereich=(b0,b1,f0,f1)` |
| Übernahme in den Fit | `gui/auswahl_dialog.py:222-228, 258-280` | `setze_bereich` → `auswahl()` → `Auswertungsauswahl(feld_min_t, …)` → `fitte_alle(auswahl=…)` |
| Zoom-Variante | `gui/matrix_ansicht.py:675-683` (`sichtbarer_bereich`) → `hauptfenster.py:1868` | einzige weitere Nutzung von `sichtbarer_bereich()` |

**Persistenz** Keine eigene. Das Ergebnis landet in `self._letzte_auswahl` (`hauptfenster.py:1876`) und
darüber im Projekt (`persistenz/projekt.py:65`, Schlüssel `auswertungsauswahl`). **Es gibt keine
ROI-Darstellung im Farbplot** und keine Wirkung auf Batch, Nachfits, Grenzgeraden oder Ausschlusszonen.

**Wechselwirkung mit Fenster/Grenzgeraden** Keine direkte. Die ROI schneidet nur die Auswahl der zu
fittenden Linescans/Feldpunkte (`fit/auswahl.py`), Fenstersuche und Grenzgeraden bleiben unberührt.

---

### BUG ROI-1: hängender ROI-Rückruf – der Auto-Fit-Dialog springt nach einer ganz anderen Aktion auf

**Symptom** Nutzer klickt im Auto-Fit-Dialog „ROI im Farbplot aufziehen …", überlegt es sich anders und
startet stattdessen „Ausschlusszone" (oder Grenzgerade/Band). Er zeichnet die Zone – und **danach
öffnet sich unvermittelt wieder der modale Auto-Fit-Dialog**.

**Reproduktion** `repro_roi.py`:
```
ROI aktiv: modus = bereich | _roi_rueckruf gesetzt: True
akt_bereich checked (irrefuehrend): True | Statusleisten-Modus: Modus: Bereich neu fitten
nach Zonen-Start: modus = zone | _roi_rueckruf noch gesetzt: True
nach Zone zeichnen: gerufen = ['abgebrochen']      <- ruft _auto_fit_fortsetzen(...)
Ausschlusszonen: 1
```

**Datei:Zeile**
* `gui/hauptfenster.py:1896` – `self._roi_rueckruf = (fertig, abgebrochen)` wird gesetzt.
* `gui/matrix_ansicht.py:200-212` (`starte_modus`) – ein Moduswechsel ruft `_modus_aufraeumen()`
  **ohne** Meldung und meldet danach nur den *neuen* Modus.
* `gui/hauptfenster.py:984-989` (`_auf_modus_geaendert`) – `_roi_abbruch_pruefen` wird nur bei
  `modus is None` geplant; beim Wechsel `bereich → zone` bleibt `_roi_rueckruf` stehen und feuert erst,
  wenn irgendwann *irgendein* Modus endet.

**Root Cause** Der ROI-Rückruf hängt an „Modus endet", nicht am konkreten Modus. Ein Moduswechsel
(statt Modusende) wird nicht als ROI-Abbruch erkannt.

**Diff zu 7c893e8** Der gesamte ROI-Umweg (`RoiAnfrage`, `_roi_im_farbplot`, `_roi_rueckruf`,
`_roi_abbruch_pruefen`) ist **neu in HEAD**; in 7c893e8 gab es weder ROI-Knopf noch Zoom-Übernahme
(`git diff 7c893e8 -- polderfit/gui/auswahl_dialog.py`, +146 Zeilen).

**Fixvorschlag** Fix im aktuellen Code: `_roi_rueckruf` an den Modus binden –
in `_auf_modus_geaendert` auch bei `modus not in (None, "bereich")` abbrechen, oder in
`_roi_im_farbplot` den Rückruf zusätzlich über `matrix.modus == "bereich"` absichern und in
`_roi_abbruch_pruefen` prüfen, ob überhaupt noch dieselbe Aktion läuft.
**Risiko** gering, gut testbar (`tests/test_grenzgeraden_gui.py:415-461` deckt den Normalweg ab).

### BUG ROI-2 (kosmetisch, aber irreführend): ROI läuft als Modus „Bereich neu fitten"

`_roi_im_farbplot` benutzt `starte_bereichs_fit` → `_MODUS_TEXTE["bereich"]`
(`hauptfenster.py:118`) zeigt „Modus: Bereich neu fitten", und `akt_bereich` wird angehakt
(`_auf_modus_geaendert`, `:970-980`). Der Nutzer, der eine ROI aufzieht, liest „Bereich neu fitten".
**Fix**: eigenen Modusnamen `"roi"` in `MODI`/`_MODUS_CURSOR`/`_MODUS_TEXTE` aufnehmen (Verhalten
identisch zum Rechteck-Modus). Risiko gering.

### BUG ROI-3 (Bedienfalle): eine einmal benutzte ROI wirkt still beim nächsten Auto-Fit weiter

`_frage_auswahl` speichert die akzeptierte Auswahl in `self._letzte_auswahl` (`:1876`) und belegt den
Dialog beim nächsten Auto-Fit damit vor (`:1866`). Der erklärende Text `bereich_hinweis` wird dabei
**nicht** gesetzt (`auswahl_dialog.py:157-163`, nur bei `roi_bereich`/`zoom_bereich`). Wer einmal mit
enger ROI gefittet hat, fittet beim nächsten Mal unbemerkt wieder nur diesen Ausschnitt.
**Fix**: Hinweistext auch für „aus letzter Auswahl übernommen" setzen, oder den Bereich beim Öffnen
ohne ROI/Zoom auf den vollen Datenbereich zurücksetzen. Risiko gering.

**Folgen des Entfernens von ROI** Betroffen wären genau: `AuswahlDialog.__init__(roi_moeglich,
roi_bereich)`, `btn_roi`/`_roi_geklickt`/`zwischenstand`/`ROI_AUFZIEHEN`, `RoiAnfrage`,
`Hauptfenster._roi_im_farbplot`/`_roi_abbruch_pruefen`/`_roi_rueckruf` samt Zweig in
`_auto_fit_fortsetzen` und `_auf_modus_geaendert`, sowie `tests/test_grenzgeraden_gui.py:387-461`.
Der Feld-/Frequenzbereich selbst (`Auswertungsauswahl`) bleibt und ist über Zahlenfelder plus
„Zoom-Ausschnitt übernehmen" weiterhin voll bedienbar – **Entfernen ist gefahrlos möglich**
und beseitigt ROI-1 bis ROI-3 auf einen Schlag.

---

## 3. „Einzelgrenzen pro Mode"

**Was es ist** Der Begriff steht nicht im Code. Gemeint ist die Zuordnung **einzelner Grenzgeraden zu
einer Mode** – im Unterschied zu „Band einzeichnen", das zwei Geraden auf einmal erzeugt.

* **Datenstruktur** `fit/fenster_steuerung.py:350-354`: `Grenzgerade.mode: int = 1` (neu in HEAD).
  Zwei Geraden derselben Mode = ihr Band. Projekt: `persistenz/projekt.py:184`.
* **UI** `gui/zonen_panel.py`
  * „Gerade einzeichnen (2 Klicks)" (`:113-119`) – die *Einzelgrenze*.
  * „Mode ändern" (`btn_gerade_mode`, `:130-135`, nur sichtbar bei n_moden > 1) – schaltet die
    gewählte Gerade zyklisch 1 → 2 → … → 1; Slot `hauptfenster.py:1148-1158` (`_gerade_mode`).
  * Automatische Vergabe `mode_neu()` (`zonen_panel.py:286-299`): erst wenn eine Mode **zwei** Geraden
    hat, beginnt die nächste. Statuszeile `band_status` zeigt `M1 ✓ (2) · M2 – (1)`.
* **Wirkung**
  * Fit: `fenster_steuerung.fitte_geraden_bereich` → `_fitte_moden_baender` (`:462-500`) – je Mode ein
    Feldband, Startwerte `startwerte_in_bereichen`, `B_res_k` im Fit auf das Band beschränkt.
  * Auswertung: `auswertung/moden.zuordnung_moden` (`:105-145`) benutzt dieselben Bänder als
    **Zweig-Zuordnung** (Regel `"band"`), sonst Feldordnung.
* **Abhängigkeiten** `moden_baender_bei`, `zuordnung_moden`, `ausreisser_moden` (Mode-Nummern!),
  Export `Parameter_M<k>`/`Punkte_M<k>` (`gui/auswertung_fenster.py:507`), Blatt *Global*
  (`hauptfenster.py:2459-2478`), Farben `farben.MODE_FARBEN`.

**Schwachstelle** Eine Mode mit nur **einer** Geraden liefert in `moden_baender_bei` eine offene
Halbebene; überlappt sie mit dem Band einer anderen Mode, ist `kandidaten` nicht eindeutig
(`moden.py:135-139`) und die Zuordnung fällt still auf die Feldordnung zurück. Das ist die einzige
Stelle, an der „Einzelgrenzen pro Mode" praktisch anders wirken als ein Band.
→ **Vorschlag**: `zonen_panel` warnt bereits per `M2 – (1)`; zusätzlich beim Fit-Start eine
Protokollzeile „Mode k hat nur eine Grenzgerade – Band offen, Zuordnung über Feldordnung".

**Folgen des Entfernens** Ohne `Grenzgerade.mode` fällt der gesamte Mehrmoden-Grenzgeraden-Fit
(`_fitte_moden_baender`, `bereiche=` in `fitte_neu`), die Band-Regel in `zuordnung_moden` und damit
die reproduzierbare Mode-Nummerierung weg – `ausreisser_moden`, Kittel/LLG je Mode und die
`M<k>`-Exportblätter verlieren ihre Grundlage. **Nicht entfernbar**, solange n_moden > 1 unterstützt wird.

---

## 4. Kriterien-Dropdown „automatisch (Kriterien)"

### 4.1 Vollständige Kriterienliste (`polderfit/fit/kriterien.py`)

| Grund-Text | Bedingung | Schwellwert / Konstante | Zeile |
|---|---|---|---|
| `nicht gefittet` | `erg.gefittet == False` | – (sofortiger Abbruch, `problematisch=True`) | `:113-114` (`GRUND_NICHT_GEFITTET`, `:86`) |
| `keine Konvergenz` | `not erg.erfolg` | – | `:122-123` |
| `keine Unsicherheiten` | `not erg.kovarianz_ok` **und** nicht exzellent | `RMSE_NORM_EXZELLENT = 0.10` | `:57, 124-128` |
| `alpha an Grenze` | `an_grenze(alpha, ALPHA_MIN, alpha_max)` | `ALPHA_MIN=1e-5`, `ALPHA_MAX=0.1`, `GRENZ_NAEHE_REL=0.01` | `:22-23, 36, 136` |
| `phi an Grenze` | `an_grenze(phi, PHI_MIN, PHI_MAX)` | `±2π`, 1 % Randnähe | `:29-30, 138` |
| `B_res am Fensterrand` | `an_grenze(B_res, B_fenster_min, B_fenster_max)` | 1 % der Fensterbreite | `:140-142` |
| `B_res ausserhalb Fenster` | `B_res < min` oder `> max` | – | `:144-147` |
| `alpha unphysikalisch` | `alpha > plausibel` | `ALPHA_PLAUSIBEL_MAX = 0.05`, skaliert mit `alpha_max` (`alpha_plausibel_max`), überschreibbar über Physik-Parameter | `:26, 70-82, 148-149` |
| `Residuum zu gross` | `rmse_norm` nicht endlich oder `> Schwelle` | `RMSE_NORM_SCHWELLE = 0.35` | `:38, 152-153` |
| `Chi2 extrem` | `chi2_red > Notbremse` (nur wenn Residuum ok) | `CHI2_RED_NOTBREMSE = 1e6` | `:47, 154-155` |
| `B_res-Unsicherheit zu gross` | `B_res_err/|B_res| > Grenze` | `B_RES_REL_UNSICHERHEIT_MAX = 0.02` | `:50, 158-161` |

`problematisch = len(gruende) > 0`. Reines Kriterienergebnis: `FitErgebnis.problematisch_auto`
(`fit/linescan_fit.py:102, 333-337`).

### 4.2 Wie „gut/schlecht/problematisch" entsteht und wo es steht

* Bewertung `"auto"` → `problematisch = problematisch_auto`; `"bestaetigt"` → nie problematisch;
  `"verworfen"` → immer problematisch (`fit/linescan_fit.py:242-260`).
* Statusklasse: `gui/farben.py:135-152` (`status_von`) – Reihenfolge
  `ignoriert > nicht gefittet/fehlgeschlagen > bestaetigt > problem > gut`.
* **Dropdown** „automatisch (Kriterien)" = `hauptfenster.py:326-329`, Wert `"auto"`, `Strg+3`
  (`:536`) → `_bewerte_aktuellen` (`:2239-2278`) → `StapelErgebnis.bewerte`.
* **Darstellung**
  * Farbplot: Marker + Farbe je Klasse (`farben.STATUS_FARBEN/STATUS_MARKER`, gelbes Dreieck =
    problematisch), gezeichnet in `matrix_ansicht._zeichne_resonanz` (`:557-593`).
  * Hover-Tooltip im Farbplot: `hauptfenster._tooltip_text` (`:2126-2141`), enthält
    `"Gründe: " + ", ".join(e.problem_gruende)`.
  * Status-Chip im Linescan-Panel: `status_label` + `STATUS_KURZ`/`STATUS_TEXTE` (`:2176-2183`).
  * Infozeile unter dem Linescan: `hauptfenster.py:2204` (`e.problem_text`).
  * Aktivitätsprotokoll während des Fits: `_fortschritt_text` (`:1300-1305`), `⚠ <problem_text>`.
  * Export: Spalten `problematisch`, `problematisch_auto`, `problem_gruende`
    (`persistenz/ergebnis_export.py:38`, `linescan_fit.py:215-220`).
  * `batch.py:208` sammelt die Gründe für die Zusammenfassung.
* Es gibt **keine** Liste/Tabelle aller Kriterien in der GUI – nur Freitext.

### 4.3 Diff zu 7c893e8 und die daraus folgende Regression

```diff
-def bewerte_fit(erg, alpha_max: float = ALPHA_MAX) -> tuple[bool, list[str]]:
+def bewerte_fit(erg, alpha_max: float = ALPHA_MAX,
+                alpha_plausibel: float | None = None) -> tuple[bool, list[str]]:
+    if not getattr(erg, "gefittet", True):
+        return True, [GRUND_NICHT_GEFITTET]
…
-    # (b) Parameter an Schranke   (nur Hauptmode)
-    if an_grenze(erg.alpha, ALPHA_MIN, alpha_max): …
+    moden = getattr(erg, "moden", None) or []
+    kandidaten = [(erg.alpha, erg.phi, erg.B_res)] + [
+        (m.get("alpha"), m.get("phi"), m.get("B_res")) for m in moden[1:]]
+    for alpha, phi, b_res in kandidaten:
+        …  # b, c, d fuer JEDE Mode
```
Neu sind außerdem `GRUND_NICHT_GEFITTET` und der einstellbare `alpha_plausibel`.
Schwellwerte selbst sind **unverändert**.

### BUG KRIT-1: eine schlechte Nebenmode verwirft den guten Hauptmoden-Punkt

**Symptom** Mit `n_moden = 2` verschwinden Punkte aus Farbplot und Kittel-Fit, deren *Hauptmode*
tadellos ist – die zweite, schwache Resonanz sitzt am Fensterrand oder ihr `alpha` steht an der
Schranke.

**Reproduktion** `repro_kriterien.py` / `repro_kriterien2.py`, echtes TDMS (629 Linescans):
```
n_moden=1: problematisch 24 von 629   (alpha unphysikalisch 24, alpha an Grenze 8)
n_moden=2: problematisch 29 von 629   (alpha an Grenze 23, phi an Grenze 7,
                                       B_res am Fensterrand 2, B_res ausserhalb Fenster 2)
davon NUR wegen einer Nebenmode: 22 von 29  (76 %)
```
Diese 22 Linescans fallen über `ist_guter_fit` (`auswertung/uebersicht.py:30-39`,
`not e.problematisch`) aus **jeder** Kittel/LLG-Auswertung – auch aus der der Hauptmode und
aus der von Mode 1, obwohl deren Fit gut ist.

**Datei:Zeile** `polderfit/fit/kriterien.py:131-149` (Schleife über `kandidaten`),
Wirkung in `polderfit/auswertung/uebersicht.py:34-39` und `auswertung/moden.py:212`.

**Root Cause** Die Einstufung ist pro **Linescan** (ein Flag), die Kriterien b–d aber jetzt pro
**Mode**. Es fehlt eine Zuordnung „welche Mode ist schuld"; `auswertung_je_mode` kann deshalb
nicht selektiv filtern.

**Fixvorschlag** (Fix im aktuellen Code, empfohlen)
1. `bewerte_fit` gibt die Gründe mit Mode-Präfix zurück (`"M2: alpha an Grenze"`), oder besser:
   zusätzlich `problematisch_moden: list[int]`.
2. `auswertung_je_mode`/`ergebnisse_fuer_mode` filtert Mode k nur, wenn Mode k selbst betroffen ist;
   `status_von` bleibt „problem", solange irgendeine Mode auffällt, aber der Punkt fällt nicht mehr
   aus der Auswertung der gesunden Moden.
Alternative (klein, konservativ): Kriterien b–d wieder nur auf die Hauptmode anwenden
(= Rückkehr zu 7c893e8) und die Nebenmoden nur als Text/Tooltip vermerken.
**Risiko** mittel – ändert die Punktmenge der Kittel/LLG-Fits; `tests/test_kriterien.py`,
`test_moden_auswertung.py`, `test_benchmark_ftf_fixes.py` sind nachzuziehen.

### Welche Kriterien erzeugen nur Text?

Keines – **alle elf Gründe** setzen `problematisch = True` und wirken damit hart auf Farbe,
Problemfit-Ausblenden und Kittel/LLG-Punktmenge. Ausdrücklich *nicht* hart wirkt nur das reduzierte
Chi-Quadrat unterhalb der Notbremse (`CHI2_RED_NOTBREMSE = 1e6`, Kommentar `kriterien.py:41-47`) –
es wird exportiert, aber nicht bewertet.

### 4.4 Vorschlag: kompakte Darstellung statt langer Listen

1. **Vier Gruppen statt elf Texte** – im Code als Mapping `GRUND_GRUPPE` neben den Gründen:
   * **A Anpassung** – `Residuum zu gross`, `Chi2 extrem`, `keine Konvergenz`
   * **P Parameter** – `alpha an Grenze`, `phi an Grenze`, `alpha unphysikalisch`
   * **F Fenster** – `B_res am Fensterrand`, `B_res ausserhalb Fenster`
   * **U Unsicherheit** – `keine Unsicherheiten`, `B_res-Unsicherheit zu gross`
2. **Chip statt Satz**: der Status-Chip zeigt `▲ problematisch · P F`; die Buchstaben sind die
   verletzten Gruppen. Vollständiger Klartext (inkl. Zahlenwert und Schwelle, z. B.
   `alpha = 0.071 > 0.05`) nur im **Tooltip** – das ist bereits die Infrastruktur von
   `_tooltip_text` (`hauptfenster.py:2126-2141`).
3. **Mode-Präfix** sobald `n_moden > 1`: `▲ M2: P` – macht KRIT-1 für den Nutzer sofort sichtbar.
4. **Ein Legenden-Dialog** (Hilfe → „Bewertungskriterien"), der die Tabelle aus 4.1 einmalig mit den
   aktuell gültigen Schwellwerten zeigt; damit entfällt jede lange Liste in der laufenden Oberfläche.
5. Dropdown-Text präzisieren: „automatisch (Kriterien)" → „automatisch – Kriterien entscheiden"
   mit Tooltip „Hebt eine manuelle Bewertung auf; ein ignorierter Punkt wird dabei wieder aufgenommen."
   (deckt den Nebenbefund aus 1.3 ab).

---

## 5. Zusammenfassung / Priorität

| # | Bug | Schwere | Empfehlung |
|---|---|---|---|
| KRIT-1 | Nebenmode verwirft guten Hauptmoden-Punkt (22/29 Fälle im Realdatensatz) | **hoch** | Fix im aktuellen Code (Mode-Zuordnung der Gründe) |
| ROI-1 | hängender ROI-Rückruf → Auto-Fit-Dialog springt nach fremder Aktion auf | mittel | Fix im aktuellen Code oder ROI entfernen |
| G-1 | Klick auf grauen (ignorierten) Punkt ohne Wirkung und ohne Meldung | mittel | Fix im aktuellen Code (Umschalter) |
| G-2 | ausgeblendete Problemfits nicht markierbar / Nachbar wird getroffen | mittel | Fix im aktuellen Code |
| ROI-3 | ROI wirkt still beim nächsten Auto-Fit weiter | mittel | Hinweistext bzw. Rücksetzen |
| ROI-2 | ROI-Modus heißt „Bereich neu fitten" | niedrig | eigener Modusname `"roi"` |
| – | Einzelgrenze (nur eine Gerade je Mode) → stiller Rückfall auf Feldordnung | niedrig | Protokollhinweis |

**Nicht bestätigt:** ein genereller Ausfall von „Ausreißer markieren". Die Kette Farbplot → Modus-Manager
→ `_ausreisser_gewaehlt` → `ausreisser_umschalten` → Overlay/Kittel ist in HEAD vollständig und wurde
mit synthetischen und echten Daten (1 und 2 Moden, Klick und Kasten, Farbplot und Kittel-Fenster)
reproduzierbar als **funktionierend** nachgewiesen. Die vom Nutzer erlebte Wirkungslosigkeit lässt sich
durch G-1 und G-2 erklären – beides stille Fehlschläge ohne jede Rückmeldung.

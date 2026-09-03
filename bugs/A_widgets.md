# Bereich A – Widgets ohne Wirkung (Signal/Slot-Audit der gesamten GUI)

HEAD: V0.1.66 / e3b1ea7 (`/home/ibrahim/Dokumente/Ananas`)
Referenz: 7c893e8 (`/home/ibrahim/Dokumente/polderfit-ref`)
Testdaten: `testdata-n-lorentz/2025-NOV-11-Linescan-2D-map-oop-5K_1.1deg-for-FTF.tdms` (629 Linescans)
Hilfsskripte (Scratchpad): `qss_test.py`, `scan.py`, `harness.py`, `harness2.py`, `harness3.py`, `harness4.py`, `harness5.py`

---

## Zusammenfassung

Es gibt **kein** systemisches, alle Panels betreffendes Signal/Slot-Problem. Zwei
verbreitete Verdachtsmomente wurden gezielt widerlegt (siehe „Geprüft und **kein**
Bug"). Gefunden wurden **sieben** konkrete Fehler, davon vier Regressionen gegenüber
7c893e8. Der subjektive Eindruck „überall ohne Wirkung" erklärt sich aus **A1/A2**:
die Modenzahl ist an drei Stellen bedienbar, die Synchronisation läuft aber nur in
eine Richtung – Eingaben werden angenommen, sind aber unwirksam oder werden beim
nächsten beliebigen Schritt stillschweigend überschrieben.

| Nr. | Priorität | Kurzbeschreibung | Regression seit 7c893e8 |
|-----|-----------|------------------|--------------------------|
| A1 | **hoch** | `spin_moden` („Res.: n ×", Linescan-Panel) ändert keinen Programmzustand und wird still zurückgesetzt | ja (45871fa/0807c7c) |
| A2 | **hoch** | „Resonanzen je Linescan" aus Strg+P / Einstellungen erreicht das Zonen-Panel nicht → Band-Werkzeug bleibt unsichtbar, Grenzgeraden-Fit fittet 1 Mode | ja (0807c7c/e41a560) |
| A3 | **mittel** | Ausreißer-Panel „Wieder aufnehmen": bei gemischter Auswahl werden die Mode-Einträge stillschweigend verworfen | ja (e41a560) |
| A4 | mittel | „Ganzer Bereich"/Vorbelegung im Auto-Fit-Dialog: Rundung auf 3 Dezimalen (GHz) kann Randlinescans ausschließen | nein |
| A5 | mittel | `bewertung_combo`: „ignorieren (Ausreißer)" erneut wählen nimmt den Punkt NICHT wieder auf (anders als Strg+I) | ja (45871fa) |
| A6 | niedrig | „Gewaehlte Zone entfernen" ohne Listenauswahl wirkungslos (Geraden wurden 03a4939 repariert, Zonen nicht) | nein (vorbestehend) |
| A7 | niedrig | Live-Vorschau (`_live`, `_live_timer`, `_live_zeichnen`, `live=`-Parameter, `_hinweis_zuletzt`) ist toter Code | ja (7b91ab6) |
| A8 | niedrig | Kittel-Fenster: `geo_combo` wirkt nur auf die Anzeige, Export nimmt `_physik.geometrie` | nein (vorbestehend) |
| A9 | niedrig | `SpaltenDialog`: alle Spaltengruppen abwählen exportiert ALLE Spalten (invertierte Wirkung) | ja (45871fa, neue Datei) |

---

## A1 – `spin_moden` („Res.: n ×") ist wirkungslos und wird still überschrieben — **hoch**

**Symptom.** Im Linescan-Fit-Panel steht eine Spin-Box „Res.: n ×". Ändert der
Nutzer sie, passiert sichtbar nichts: das Zonen-Panel („Resonanzen je Linescan"),
der Auto-Fit-Dialog und die Parameter (Strg+P) bleiben auf dem alten Wert. Beim
nächsten beliebigen Schritt (Zonen-Panel bedienen, Bereichs-Fit, Strg+P,
Einstellungen laden) springt die Spin-Box ohne Meldung zurück.

**Reproduktion** (`harness.py`, T1/T2):

```
--- T1: spin_moden von 1 auf 3 ---
vorher : {'physik': 1, 'stapel': 1, 'spin': 1, 'zonen_combo': 1, 'zonen_intern': 1}
nachher: {'physik': 1, 'stapel': 1, 'spin': 3, 'zonen_combo': 1, 'zonen_intern': 1}
--- T2: Zonen-Combo auf 2, danach spin auf 4 ---
nach combo=2: {'physik': 2, 'stapel': 2, 'spin': 2, ...}
nach spin=4 : {'physik': 2, 'stapel': 2, 'spin': 4, ...}   # Spin allein, Rest bleibt 2
```

Jeder spätere Aufruf von `_setze_n_moden`/`_physik_uebernehmen` setzt `spin_moden`
per `blockSignals` auf den alten Wert zurück (Zeilen 1931-1933 und 1964-1966).

**Datei:Zeile.**
* `polderfit/gui/hauptfenster.py:280-287` – `self.spin_moden = RuhigeSpinBox()`;
  **kein einziges `connect`** (bestätigt durch `scan.py`: `connect=0 read=2 set=3`).
* Gelesen nur an `hauptfenster.py:2328` (`_grenzen_geaendert`) und `:2351` (`_neu_fitten`).
* Überschrieben an `hauptfenster.py:1931-1933`, `:1964-1966`.
* Widerspruch zur dokumentierten Absicht: `polderfit/gui/zonen_panel.py:64-66`
  („Resonanzen je Linescan - EINE sichtbare Stelle; synchron mit dem Auto-Fit-Dialog
  und ‚Res.' im Linescan-Panel").

**Root Cause.** `spin_moden.valueChanged` ist an nichts gebunden. Die Synchronisation
ist einseitig: `_setze_n_moden` → `spin_moden`, aber nie `spin_moden` → `_setze_n_moden`.
Deshalb wirkt der Wert ausschließlich als lokales Argument der beiden `fitte_neu`-
Aufrufe und ist für alles andere (Stapel, Physik, Auto-Fit-Dialog, Zonen-Panel,
Auswertung, Autosicherung) unsichtbar.

**Diff zu 7c893e8.** In der Referenz existiert `spin_moden` nicht; das Linescan-Panel
kannte nur `chk_vollbereich` (`ref/hauptfenster.py:208`). Die Spin-Box kam mit
45871fa/0807c7c hinzu, ohne Anbindung.

**Fixvorschlag** (Fix im aktuellen Code, klein):

```python
self.spin_moden.valueChanged.connect(self._setze_n_moden)
```

`_setze_n_moden` ist bereits reentranzsicher (es setzt `spin_moden` mit `blockSignals`
und vergleicht gegen `self._physik.n_moden`). Alternativ – wenn der Wert bewusst nur
für den Einzelfit gelten soll – die Spin-Box entfernen und die Modenzahl allein über
das Zonen-Panel/Strg+P führen; das entspräche der eigenen Doku „EINE sichtbare Stelle".

**Risiko.** Gering. `_setze_n_moden` schreibt `stapel.n_moden`, protokolliert und
ruft `_auswertung_nachziehen()` – bei jedem Tastendruck in der Spin-Box also ein
Neurechnen der Kittel-Auswertung. Ggf. `editingFinished` statt `valueChanged`
verwenden, oder in `_setze_n_moden` früh zurückkehren, wenn sich nichts ändert.

---

## A2 – Modenzahl aus Strg+P / Einstellungen erreicht das Zonen-Panel nicht — **hoch**

**Symptom.** Der Nutzer stellt in „Physikalische Parameter" (Strg+P) „Resonanzen je
Linescan = 5" ein. Im Panel „Zonen & Grenzgeraden" steht weiter „1 – eine Mode",
das Band-Werkzeug („Bandbreite ±", „Band einzeichnen") und der Knopf „Mode ändern"
bleiben **unsichtbar**, und „Grünen Bereich fitten" fittet nur eine Mode. Derselbe
Effekt beim Laden von Einstellungen / „Standardwerte wiederherstellen".

**Reproduktion** (`harness.py` T3, `harness2.py` T4):

```
--- T3: _physik_uebernehmen(n_moden=5) ---
vorher : {'physik': 1, 'stapel': 1, 'spin': 1, 'zonen_combo': 1, 'zonen_intern': 1}
nachher: {'physik': 5, 'stapel': 5, 'spin': 5, 'zonen_combo': 1, 'zonen_intern': 1}
         n_moden_effektiv = 1
--- T4: _einstellungen_anwenden(physik n_moden=6) ---
nachher: (physik=6, stapel=6, spin=6, zonen_combo=1, zonen_intern=1)
```

**Datei:Zeile.**
* `polderfit/gui/hauptfenster.py:1927-1954` `_physik_uebernehmen` – setzt `spin_moden`,
  `self._physik`, `stapel.n_moden`, ruft aber **nicht** `self.zonenpanel.setze_n_moden(...)`.
* `polderfit/gui/hauptfenster.py:3005-3021` `_einstellungen_anwenden` – ebenfalls nicht.
* Zum Vergleich: `hauptfenster.py:1955-1969` `_setze_n_moden` macht es richtig (Zeile 1967).
* Folgen: `zonen_panel.py:252-256` `_moden_ansicht_aktualisieren` (`band_box`/`btn_gerade_mode`
  bleiben `setVisible(False)`), `zonen_panel.py:247-250` `n_moden_effektiv()` liefert 1,
  `hauptfenster.py:1213-1215` `_geraden_fit` rechnet dann mit `n_eff = 1`.

**Root Cause.** Zwei parallele Einstiegspunkte für dieselbe Größe; nur einer
(`_setze_n_moden`) ist vollständig. `_physik_uebernehmen` – der Weg des Parameter-
Dialogs und der Einstellungen – dupliziert einen Teil davon und lässt das Panel aus.

**Diff zu 7c893e8.** In 7c893e8 gab es weder ein Moden-Dropdown im Zonen-Panel noch
ein Band-Werkzeug; die Kopplung entstand mit 798b794/0807c7c/e41a560 und wurde nur an
`_setze_n_moden` gehängt.

**Fixvorschlag** (Fix im aktuellen Code): in `_physik_uebernehmen` nach dem Setzen von
`spin_moden` ergänzen

```python
self.zonenpanel.setze_n_moden(max(1, int(parameter.n_moden)))
```

(`setze_n_moden` im Panel ruft keinen Callback zurück – `blockSignals` an
`zonen_panel.py:218-221` – also keine Schleife.) Sauberer: `_physik_uebernehmen`
delegiert die Modenzahl an `_setze_n_moden` statt sie selbst zu setzen.

**Risiko.** Gering; `ZonenPanel.setze_n_moden` ist rückruffrei und idempotent.

---

## A3 – Ausreißer-Panel „Wieder aufnehmen" verwirft Mode-Einträge — **mittel**

**Symptom.** Sind in der Ausreißer-Liste gleichzeitig ein Linescan-Eintrag
(`#0: f = …`) und ein Mode-Eintrag (`#1 · Mode 2: …`) markiert, nimmt „Wieder
aufnehmen" nur den Linescan zurück. Der Mode-Ausschluss bleibt bestehen, ohne
Meldung. Der Knopf wirkt also „halb tot", je nach Auswahl.

**Reproduktion** (`harness2.py`, T6):

```
Liste: ['#0:  f =   6.029 GHz,  B_r', '#1 · Mode 2:  f =   6.099 ']
gewaehlt linescan: [0]  mode: [(1, 2)]
vorher  ausreisser: [0]  ausreisser_moden: [(1, 2)]
nachher ausreisser: []   ausreisser_moden: [(1, 2)]    <-- Mode-Eintrag NICHT zurueckgenommen
```

**Datei:Zeile.** `polderfit/gui/ausreisser_panel.py:116-122`

```python
def _wieder_geklickt(self) -> None:
    indizes = self.gewaehlte_indizes()
    if indizes and self._cb_wieder is not None:
        self._cb_wieder(indizes)          # <-- leert die Liste
    paare = self.gewaehlte_moden_paare()  # <-- erst DANACH gelesen -> []
    if paare and self._cb_wieder_moden is not None:
        self._cb_wieder_moden(paare)
```

**Root Cause.** `self._cb_wieder` ist `Hauptfenster._ausreisser_wieder_aufnehmen`
(`hauptfenster.py:2779`) → `_aktualisiere_overlay()` (`:2144`) → `:2166`
`self.ausreisserpanel.zeige_ausreisser(st)` → `ausreisser_panel.py:75` `self.liste.clear()`.
Damit ist die Auswahl weg, bevor `gewaehlte_moden_paare()` sie liest. Klassischer
„Zustand während des Callbacks entzogen"-Fehler.

**Diff zu 7c893e8.** Neu mit e41a560; in der Referenz gab es nur
`_cb_wieder(self.gewaehlte_indizes())`, ohne zweiten Lesezugriff nach dem Callback.

**Fixvorschlag** (Fix im aktuellen Code): beide Auswahlen **vor** dem ersten Callback
einlesen.

```python
def _wieder_geklickt(self) -> None:
    indizes = self.gewaehlte_indizes()
    paare = self.gewaehlte_moden_paare()   # vor dem Callback lesen
    if indizes and self._cb_wieder is not None:
        self._cb_wieder(indizes)
    if paare and self._cb_wieder_moden is not None:
        self._cb_wieder_moden(paare)
```

`_alle_geklickt` (`:124-129`) ist nicht betroffen: es liest `self._eintraege`, das
`zeige_ausreisser` neu aufbaut und in dem die Mode-Einträge erhalten bleiben.

**Risiko.** Keines. Zwei Undo-Schritte statt einem – wie schon heute bei
funktionierender Reihenfolge.

---

## A4 – „Ganzer Bereich"/Vorbelegung im Auto-Fit-Dialog: Rundung schneidet Ränder ab — **mittel**

**Symptom.** Der Auto-Fit-Dialog meldet nach „Ganzer Bereich" nicht „keine
Einschränkung", sondern eine gerundete Frequenzgrenze. Je nach Datensatz fällt der
äußerste Linescan stillschweigend aus der Auswertung; der Knopf tut also nicht, was
er verspricht.

**Reproduktion** (`harness5.py`):

```
Datensatz: Frequenz 6.02914 .. 49.98286 GHz
nach 'Ganzer Bereich':
  feld_min_t = None  feld_max_t = None          (Feld: 4 Dezimalen -> exakt getroffen)
  frequenz_min_hz = 6029000000.0                (statt None)
  frequenz_max_hz = 49983000000.0               (statt None)
  ist_neutral = False
```

Hier rettet der Zufall die Daten (beide Rundungen weiten den Bereich). Bei einer
Obergrenze wie 49.9834 GHz rundet `setDecimals(3)` auf 49.983 GHz **nach unten** –
der oberste Linescan ist dann ohne Hinweis draußen.

**Datei:Zeile.**
* `polderfit/gui/auswahl_dialog.py:104-112` `_spin(...)` mit `box.setDecimals(dezimalen)`,
  Aufrufe `:112-122` mit `3` (GHz) bzw. `4` (T).
* `polderfit/gui/auswahl_dialog.py:262-266` `_oder_none`: `None if abs(wert - standard) < 1e-12 else wert`.
* `polderfit/gui/auswahl_dialog.py:230-232` `_ganzer_bereich` → `setze_bereich(*self._voller_bereich)`.

**Root Cause.** Der Vergleich auf „unverändert" hat eine Toleranz von 1e-12, die
Eingabefelder haben aber eine Auflösung von 1e-3 GHz bzw. 1e-4 T. Der Sollwert kann
gar nicht exakt zurückgeschrieben werden.

**Diff zu 7c893e8.** `_oder_none` und die Dezimalstellen sind unverändert; neu sind
nur die Knöpfe „Ganzer Bereich"/„Zoom übernehmen"/„ROI" (798b794/e3b1ea7), die den
Effekt jetzt bedienbar machen. Kein Regressions-, sondern ein Auslegungsfehler.

**Fixvorschlag** (Fix im aktuellen Code): Toleranz an die Anzeigeauflösung koppeln,
z. B. `< 0.51 * 10**-dez` je Achse, oder `_ganzer_bereich()` einen expliziten Merker
setzen lassen (`self._voll = True`), den `auswahl()` in `None` übersetzt.

**Risiko.** Gering; betrifft nur die Umrechnung „Spin-Wert → Einschränkung".

---

## A5 – `bewertung_combo`: „ignorieren" erneut wählen bleibt wirkungslos — **mittel**

**Symptom.** Ist der aktuelle Fit bereits ignoriert, steht in der Auswahlliste
„ignorieren (Ausreißer)". Wählt der Nutzer diesen Eintrag erneut (um ihn wieder
aufzunehmen, wie es der Tooltip mit „ignorieren/wieder aufnehmen (Strg+I)"
verspricht), passiert nichts. Nur Strg+I schaltet um.

**Reproduktion** (`harness3.py`):

```
ist_ausreisser(0): True | Combo: ignorieren
nach erneutem Waehlen 'ignorieren': True -> TOT (kein Wiederaufnehmen)
```

**Datei:Zeile.** `polderfit/gui/hauptfenster.py:2229-2237`

```python
if art == "ignorieren" and st is not None and st.ist_ausreisser(self.aktueller_index):
    return  # schon ignoriert
```

Tooltip mit dem Toggle-Versprechen: `hauptfenster.py:330-332`.
`_bewerte_aktuellen` selbst (`:2249-2258`) implementiert den Toggle korrekt.

**Root Cause.** Die Wächterzeile sollte verhindern, dass das programmatische Setzen
der Liste in `_zeige_aktuellen` den Punkt versehentlich wieder aufnimmt – dafür gibt
es aber bereits zwei Mechanismen: `activated` feuert nur bei Nutzerinteraktion, und
`_bewertung_blockiert` (`:2189-2193`) deckt den Rest ab. Die Zeile ist also
überflüssig und blockiert genau den gewollten Nutzerfall.

**Diff zu 7c893e8.** `bewertung_combo` existiert erst seit 45871fa; in 7c893e8 gab es
nur die Menüaktionen.

**Fixvorschlag** (Fix im aktuellen Code): die beiden Zeilen entfernen, damit der
Listeneintrag denselben Toggle auslöst wie Strg+I. Alternativ (weniger schön) den
Eintrag umbenennen in „ignorieren / wieder aufnehmen" und trotzdem durchreichen.

**Risiko.** Gering. `_bewerte_aktuellen("ignorieren")` ist bereits ein sauberer
Toggle mit Undo-Eintrag.

---

## A6 – „Gewaehlte Zone entfernen" ohne Listenauswahl wirkungslos — **niedrig**

**Symptom.** Nach dem Einzeichnen einer Ausschlusszone steht sie in der Liste, ist
aber nicht markiert. Ein Klick auf „Gewaehlte Zone entfernen" tut nichts – ohne
Meldung. Erst ein Klick in die Listenzeile macht den Knopf wirksam.

**Reproduktion** (`harness4.py`, mit laufender Ereignisschleife):

```
Zonen: 1 | Listeneintraege: 1 | currentRow: -1
nach Klick 'Gewaehlte Zone entfernen': 1 Zonen -> TOT
mit Listenauswahl:                      0 Zonen
```

**Datei:Zeile.**
* `polderfit/gui/zonen_panel.py:330-333` `_zone_entfernen_geklickt` → `zonen_liste.currentRow()`,
  `if zeile >= 0`.
* `polderfit/gui/zonen_panel.py:181-187` `setze_zonen` – `clear()` + `addItem`, **ohne**
  `setCurrentRow`.

**Root Cause.** Für die Grenzgeraden wurde genau dieses Problem mit 03a4939 behoben
(`_gerade_zeile()`, `zonen_panel.py:297-302`, fällt ohne Auswahl auf die zuletzt
gesetzte Gerade zurück, plus Vorwahl in `setze_geraden`, `:207-210`). Die Zonenliste
hat die Behandlung nicht bekommen.

**Diff zu 7c893e8.** Identisches Verhalten in der Referenz (`ref/zonen_panel.py:160`) –
vorbestehend, keine Regression.

**Fixvorschlag** (Fix im aktuellen Code): analog zu `_gerade_zeile()` eine
`_zone_zeile()` einführen und in `setze_zonen` die zuletzt hinzugefügte Zone
vorwählen.

**Risiko.** Gering, aber Verhaltensänderung: „Entfernen" ohne Auswahl löscht dann
die zuletzt gezeichnete Zone. Genau so verhalten sich die Geraden seit 03a4939.

---

## A7 – Live-Vorschau ist toter Code — **niedrig**

**Symptom.** Kein Nutzersymptom (Ergebnisse werden am Jobende korrekt gezeichnet),
aber ein ganzer Codepfad inkl. eines öffentlichen Parameters führt ins Leere und
suggeriert eine Funktion, die es nicht mehr gibt.

**Datei:Zeile.** `polderfit/gui/hauptfenster.py`
* `:1517-1520` `_live_timer` angelegt und mit `_live_zeichnen` verbunden – **`start()`
  wird nirgends aufgerufen** (nur `stop()` an `:1682`).
* `:1652-1664` `_auf_zwischenstand` füllt `self._live`, startet aber den Timer nicht mehr.
* `:1666-1668` `_live_zeichnen` kehrt bei `self._job_laeuft` sofort zurück; `:1682-1684`
  `_job_anzeige_beenden` leert `self._live` und setzt `_live_aktiv = False` – und wird
  in `_auf_fertig` (`:1693-1695`) **vor** `bei_fertig` ausgeführt. Damit ist die
  Methode unerreichbar.
* `:1513` `self._hinweis_zuletzt` wird nur noch initialisiert, nie gelesen.
* `:1522-1528` Docstring von `_starte_job` beschreibt `live="neu"/"ergaenzen"` weiter
  als „Live-Vorschau der Fit-Punkte im Farbplot".

**Root Cause.** 7b91ab6 hat die Live-Zeichnung bewusst entfernt (GIL-Konkurrenz),
aber Timer, Puffer, Slot und Parameterdoku stehen gelassen. `live="neu"` hat noch
eine Restwirkung (`:1568` leert das Overlay zu Jobbeginn), `live="ergaenzen"` füllt
nur noch einen Puffer, der danach verworfen wird.

**Fixvorschlag** (Entfernen): `_live`, `_live_timer`, `_live_zeichnen`,
`_hinweis_zuletzt` und den `"ergaenzen"`-Zweig streichen; `live` durch ein
sprechendes `overlay_leeren: bool` ersetzen und den Docstring anpassen. Wer die
Vorschau zurückwill, muss sie ohnehin anders bauen (Zeichnen nach Jobende).

**Risiko.** Keines für das Verhalten; `tests/test_neue_funktionen.py:648-652` prüft
bereits explizit, dass während des Jobs nicht gezeichnet wird.

---

## A8 – Kittel-Fenster: `geo_combo` wirkt nicht auf den Export — **niedrig**

**Symptom.** Die Umschaltung „Kittel-Geometrie: oop/ip" im Auswertungsfenster ändert
Plot und Parametertabelle im Fenster, aber Excel-/CSV-Export und die Moden-Auswertung
des Hauptfensters rechnen weiter mit der Geometrie aus Strg+P. Beim Schließen des
Fensters ist die Wahl verloren (`_auswertungsfenster_zu` setzt die Referenz auf `None`).

**Datei:Zeile.**
* `polderfit/gui/auswertung_fenster.py:114-117` (`geo_combo`, `currentTextChanged` →
  `aktualisiere()`), gelesen `:274`.
* `polderfit/gui/hauptfenster.py:2436` `_global_parameter` und `:2472`
  `_global_parameter_moden` verwenden `p.geometrie` aus `self._physik`.
* `polderfit/gui/hauptfenster.py:2392-2393` `_auswertungsfenster_zu`.

**Root Cause.** Zwei Quellen für dieselbe Größe ohne Rückschreibung.

**Diff zu 7c893e8.** Identisch in der Referenz (`ref/auswertung_fenster.py:73-77`,
`ref/hauptfenster.py:1537`) – vorbestehend.

**Fixvorschlag** (Fix im aktuellen Code): `AuswertungsFenster` einen Callback
`geometrie_geaendert(name)` geben, der im Hauptfenster
`self._physik = replace(self._physik, geometrie=name)` setzt (und die Voreinstellung
mitschreibt). Alternativ die Combo im Auswertungsfenster entfernen und die Geometrie
nur in Strg+P führen.

**Risiko.** Gering; ändert aber eine globale Einstellung aus einem Nebenfenster
heraus – im Log vermerken.

---

## A9 – `SpaltenDialog`: alle Gruppen abwählen exportiert alles — **niedrig**

**Symptom.** Werden im Dialog „Export-Spalten" **alle** Spaltengruppen abgewählt,
enthält der Export trotzdem sämtliche Spalten. Die Checkboxen wirken dann invertiert.

**Datei:Zeile.**
* `polderfit/gui/export_dialog.py:168-173` `einstellungen()`:
  `"spalten": spalten if len(spalten) < len(SPALTEN_GRUPPEN) else []` – die leere
  Liste kodiert „alle", wird aber auch bei null Auswahl erzeugt.
* Auswertung: `hauptfenster.py:2531` / `:2551` `spalten=opt.get("spalten") or None`
  → `None` = alle.
* Im Gegensatz zu `AlleSpeichernDialog._pruefen` (`export_dialog.py:102-109`) gibt es
  hier keine Mindestauswahl-Prüfung.

**Root Cause.** Sentinel-Wert `[]` mit zwei Bedeutungen („alle gewählt" und „keine
gewählt").

**Diff zu 7c893e8.** `export_dialog.py` existiert in der Referenz nicht (neu mit 45871fa).

**Fixvorschlag** (Fix im aktuellen Code): eine `_pruefen`-Analogie ergänzen (mindestens
eine Gruppe verlangen) oder `None` statt `[]` als „alle"-Sentinel benutzen und die
leere Auswahl als „nur Pflichtspalten" durchreichen.

**Risiko.** Gering.

---

## Geprüft und **kein** Bug (Verdacht widerlegt)

**QSS/`stil.py` beschädigt keine Bedienelemente.** `stil.py:134-141` stylt
`QSpinBox/QDoubleSpinBox/QComboBox` mit Rahmen, ohne `::up-button`/`::down-button`/
`::drop-down` zu definieren – der bekannte Qt-Fallstrick. Die Referenz 7c893e8 hat
diese Regeln gar nicht (`grep QSpinBox ref/stil.py` → leer), es wäre also ein
plausibler Regressionskandidat gewesen. Messung (`qss_test.py`, Sub-Control-Rects und
synthetischer Klick):

```
QSS AUS: QSpinBox.up 366,0 14x13 | GroupBox.checkbox 1,2 14x14 | Klick Up: 5 -> 6 | GroupBox-Indicator: False -> True
QSS AN : QSpinBox.up 366,0 14x12 | GroupBox.checkbox 12,1 14x14 | Klick Up: 5 -> 6 | GroupBox-Indicator: False -> True
```

Pfeil-Flächen, Checkbox- und GroupBox-Indikatoren behalten Größe und Trefferfläche.

**`widgets.py` (`RuhigeSpinBox`/`RuhigeDoubleSpinBox`/`RuhigeComboBox`) ist korrekt.**
`setFocusPolicy(StrongFocus)` + `wheelEvent`-Ignorieren ohne Fokus ist der gewollte
Schrumpf-Bug-Fix; Tastatur, Pfeiltasten, Klick auf die Pfeile und `setValue` sind
unberührt (Nachweis oben). `_dezimal_normiert` greift nur in `validate`/`valueFromText`.

**Verarbeitungs-Panel arbeitet vollständig** (`harness2.py`, T5): Gruppen-Checkboxen
(exklusiv), `dd_delta`, `dd_mitteln`, `divide_index` (inkl. Wert-Label), `divide_achse`,
`anzeige_combo`, `farbskala_combo` und „Alles aus" schlagen alle bis in
`Hauptfenster._einstellungen.verarbeitung` bzw. `matrix.setze_verarbeitung` durch.
Die im Statik-Scan als „kein connect" markierten Widgets sind über die Schleifen
`verarbeitung_panel.py:186-193` verbunden.

**Ansicht-Menü und Panel-Umschalter arbeiten** (`harness3.py`/`harness4.py`):
`akt_zoom`, `akt_problemfits`, `akt_ausreisser_anzeigen`, `akt_nebenmoden`,
`akt_vollbereich` (inkl. Spiegelung auf `chk_vollbereich`) und alle sechs
Panel-Aktionen schalten den Zielzustand um.

**Bereichs-Fit-Dialog:** `moden_spin` wirkt trotz fehlendem Signal – `_bereich_gewaehlt`
(`hauptfenster.py:2088`) ruft `_setze_n_moden(dialog.n_moden())` **vor** dem Job, und
`fitte_bereich` → `_fitte_mit_intervallen(n_moden=None)` → `fitte_neu` greift auf
`stapel.n_moden` zurück (`polderfit/fit/batch.py:552`). Anfangs als Bug verdächtigt,
ist aber korrekt.

**Alle `PhysikParameter`-Felder des Parameter-Dialogs werden konsumiert**
(`g_faktor`, `gamma_fest`, `geometrie`, `breite_faktor`, `r2_schwelle`, `r2_min`,
`alpha_max`, `alpha_plausibel`, `nachfenster_faktor`, `n_moden`, `gewichtet`,
`nachfit_bestaetigen`) – keine tote Dialogzeile.

**`farbskala_gruppe` / `btn_laden`** waren Fehlalarme des Statik-Scans:
`QActionGroup` hält nur die Exklusivität, `btn_laden` nutzt `setDefaultAction`.

**Anmerkung (kein Fehler, aber fragil).** `VerarbeitungPanel.setze_farbskala`
(`verarbeitung_panel.py:255-261`) setzt `self._blockiert` im `finally`
**bedingungslos** auf `False`. Ein Aufruf aus einem bereits blockierten Kontext würde
die Sperre vorzeitig aufheben. Heute tritt das nicht auf (`_einstellungen_anwenden`
ruft `_farbskala_setzen` vor `setze_kette`). Empfehlung: alten Wert sichern und
wiederherstellen.

---

## Tabelle aller geprüften Widgets

Status: **ok** = Slot ändert nachweislich Zielzustand · **tot** = keine oder falsche
Wirkung · **ok\*** = wirkt, aber mit dokumentiertem Mangel (siehe Bug-Nummer).

| Panel / Datei:Zeile | Widget | Signal | Slot | wirkt auf | Status |
|---|---|---|---|---|---|
| **Hauptfenster (Linescan-Panel)** |
| hauptfenster.py:272 | `btn_zurueck` | clicked | `lambda: _navigiere(-1)` | `aktueller_index` | ok |
| hauptfenster.py:273 | `btn_weiter` | clicked | `lambda: _navigiere(+1)` | `aktueller_index` | ok |
| hauptfenster.py:274 | `btn_naechstes_problem` | clicked | `_naechster_problemfit` | `aktueller_index` | ok |
| hauptfenster.py:276 | `btn_neu` | clicked | `_neu_fitten` | `stapel.ergebnisse[i]` | ok |
| **hauptfenster.py:280** | **`spin_moden`** | **– (kein connect)** | **–** | **nur Argument in `fitte_neu`; kein Zustand** | **tot (A1)** |
| hauptfenster.py:288 | `btn_hauptmode` | clicked | `_hauptmode_wechseln` | `stapel.ergebnisse[i]` | ok |
| hauptfenster.py:298 | `chk_vollbereich` | toggled | `akt_vollbereich.setChecked` | `fitansicht._vollbereich` | ok |
| hauptfenster.py:324 | `bewertung_combo` | activated | `_bewertung_gewaehlt` | `ergebnis.bewertung` / `stapel.ausreisser` | ok\* (A5) |
| **Hauptfenster (Menü / Aktionen)** |
| hauptfenster.py:484 | `akt_bereich` | toggled | `_bereich_umschalten` | `matrix.modus` | ok |
| hauptfenster.py:493 | `akt_gerade` | toggled | `_gerade_modus` | `matrix.modus` | ok |
| hauptfenster.py:501 | `akt_zone` | toggled | `_zone_modus` | `matrix.modus` | ok |
| hauptfenster.py:506 | `akt_ausreisser` | toggled | `_ausreisser_modus` | `matrix.modus` | ok |
| hauptfenster.py:545 | `akt_vollbild` | toggled | `_vollbild_umschalten` | Fensterzustand | ok |
| hauptfenster.py:556 | `akt_vollbereich` | toggled | `_vollbereich_umschalten` | `fitansicht._vollbereich` | ok |
| hauptfenster.py:565 | `akt_zoom` | toggled | `matrix.setze_zoom_aktiv` | `matrix._zoom_aktiv` | ok |
| hauptfenster.py:572 | `akt_problemfits` | toggled | `_problemfits_umschalten` | `matrix._problemfits_ausblenden` | ok |
| hauptfenster.py:577 | `akt_ausreisser_anzeigen` | toggled | `matrix.setze_ausreisser_anzeigen` | `matrix._ausreisser_anzeigen` | ok |
| hauptfenster.py:580 | `akt_nebenmoden` | toggled | `matrix.setze_nebenmoden_anzeigen` | `matrix._nebenmoden_anzeigen` | ok |
| hauptfenster.py:586-594 | `akt_farbskalen[*]` | triggered | `_farbskala_setzen` | `matrix.farbskala()` | ok |
| hauptfenster.py:599/604/608/615/618/620 | Panel-Umschalter | toggled | `dock.setVisible` | Dock-Sichtbarkeit | ok |
| hauptfenster.py:1494 / :770 | `btn_abbrechen`, `btn_abbrechen_dock` | clicked | `_job_abbrechen` | `_arbeiter.abbrechen()` | ok |
| hauptfenster.py:639 | `btn_logo` | clicked | `_zeige_hilfe` | Hilfedialog | ok |
| hauptfenster.py:725 | `btn_laden` | (defaultAction) | `akt_laden` | Laden | ok |
| **Verarbeitungs-Panel** |
| verarbeitung_panel.py:103/124/146 | `grp_divide`, `grp_dd`, `grp_rel` | toggled (Schleife :186-187) | `_exklusiv` → `_melde` | `matrix.setze_verarbeitung` | ok |
| verarbeitung_panel.py:108/138/156 | `divide_achse`, `dd_achse`, `rel_achse` | currentIndexChanged (:191-192) | `_melde` | Kette | ok |
| verarbeitung_panel.py:113 | `divide_index` | valueChanged (:189-190) | `_melde` (+ Wert-Label) | Kette | ok |
| verarbeitung_panel.py:129 | `dd_delta` | valueChanged | `_melde` | Kette | ok |
| verarbeitung_panel.py:134 | `dd_mitteln` | toggled (:188) | `_melde` | Kette | ok |
| verarbeitung_panel.py:151 | `rel_delta` | valueChanged | `_melde` | Kette | ok |
| verarbeitung_panel.py:166 | `anzeige_combo` | currentIndexChanged | `_melde` | Anzeigemodus | ok |
| verarbeitung_panel.py:171 | `farbskala_combo` | currentIndexChanged | `_farbskala_gewaehlt` | `matrix.farbskala()` | ok |
| verarbeitung_panel.py:178 | `btn_roh` | clicked | `_alles_aus` | Kette + Anzeige | ok |
| **Zonen-Panel** |
| zonen_panel.py:69 | `n_moden_combo` | currentIndexChanged | `_n_moden_gewaehlt` → `_setze_n_moden` | `_physik`, `stapel`, `spin_moden` | ok |
| zonen_panel.py:91 | `breite_spin` | – (bei Bedarf gelesen) | `bandbreite_T()` | Bandbreite beim Zeichnen (geprüft: 37 mT → 0.074 T Abstand) | ok |
| zonen_panel.py:100 | `btn_band` | toggled | `_band_umgeschaltet` | `matrix.modus` | ok |
| zonen_panel.py:113 | `btn_gerade` | toggled | `_gerade_umgeschaltet` | `matrix.modus` | ok |
| zonen_panel.py:126 | `btn_gerade_seite` | clicked | `_gerade_seite_geklickt` | `Grenzgerade.gruen_positiv` | ok |
| zonen_panel.py:132 | `btn_gerade_mode` | clicked | `_gerade_mode_geklickt` | `Grenzgerade.mode` | ok\* (unsichtbar bei A2) |
| zonen_panel.py:137 | `btn_gerade_entfernen` | clicked | `_gerade_entfernen_geklickt` | `_grenzgeraden` | ok |
| zonen_panel.py:142 | `btn_geraden_fit` | clicked | `_geraden_fit` | Nachfit-Job | ok |
| zonen_panel.py:162 | `btn_zone` | toggled | `_zone_umgeschaltet` | `matrix.modus` | ok |
| **zonen_panel.py:174** | **`btn_zone_entfernen`** | clicked | `_zone_entfernen_geklickt` | **nur mit Listenauswahl** | **tot ohne Auswahl (A6)** |
| zonen_panel.py:121/170 | `geraden_liste`, `zonen_liste` | – | `currentRow()` bei Bedarf | Auswahlindex | ok |
| **Ausreißer-Panel** |
| ausreisser_panel.py:53 | `liste` | – | `selectedIndexes()` bei Bedarf | Auswahl | ok |
| **ausreisser_panel.py:58** | **`btn_wieder`** | clicked | `_wieder_geklickt` | `stapel.ausreisser` (+ `ausreisser_moden`) | **teilweise tot (A3)** |
| ausreisser_panel.py:62 | `btn_alle` | clicked | `_alle_geklickt` | `ausreisser` + `ausreisser_moden` | ok |
| ausreisser_panel.py:67 | `btn_rueckgaengig` | clicked | `_cb_rueckgaengig` | Undo-Stapel | ok |
| **Trace-Panel** |
| trace_panel.py:100 | `chk_aktiv` | toggled | `_umschalten` | `FunktionsTracer` (geprüft: False→True) | ok |
| trace_panel.py:108 | `leeren` | clicked | `ansicht.clear` | Textfeld | ok |
| **Auto-Fit-Dialog (`auswahl_dialog.py`)** |
| :87 / :92 | `n_frequenz`, `n_feld` | valueChanged (:211) | `_aktualisiere_zusammenfassung`; gelesen in `auswahl()` | `Auswertungsauswahl` | ok |
| :112-122 | `f_min/f_max/b_min/b_max` | valueChanged (:213) | `_aktualisiere_zusammenfassung`; gelesen in `auswahl()` | `Auswertungsauswahl` | ok\* (A4) |
| :135 | `btn_roi` | clicked | `_roi_geklickt` | `done(ROI_AUFZIEHEN)` | ok |
| :142 | `btn_zoom` | clicked | `_zoom_uebernehmen` | Bereichsfelder | ok |
| **:147** | **`btn_alles`** | clicked | `_ganzer_bereich` | Bereichsfelder | **ok\* (A4: liefert nicht „neutral")** |
| :164 | `ausschluss` | textChanged (:214) | `_aktualisiere_zusammenfassung`; gelesen in `auswahl()` | `frequenz_ausschluss` | ok |
| :175 | `moden_combo` | currentIndexChanged | `_moden_geaendert`; gelesen via `n_moden()` | `_setze_n_moden` | ok |
| :186 | `chk_zweistufig` | – | gelesen via `zweistufig()` | `_physik.auto_fit_zweistufig` | ok |
| **Bereichs-Fit-Dialog (`bereichsfit_dialog.py`)** |
| :50 | `modus_combo` | – | `modus()` | `fitte_bereich(modus=…)` | ok |
| :76-83 | `f_von/f_bis/b_von/b_bis` | – | `frequenz_bereich()`/`feld_bereich()` | Fit-Grenzen | ok |
| :89 | `moden_spin` | – | `n_moden()` → `_setze_n_moden` | `stapel.n_moden` → `fitte_neu` | ok |
| :103 | `chk_breite` | toggled | `breite_spin.setEnabled`; gelesen in `breite_punkte()` | feste Fensterbreite | ok |
| :108 | `breite_spin` | – | `breite_punkte()` | `breite_punkte` | ok |
| **Parameter-Dialog (`parameter_dialog.py`)** |
| :43 | `g_spin` | valueChanged | `_zeige_gamma`; gelesen in `parameter()` | `PhysikParameter.g_faktor` | ok |
| :59/:66/:75/:85/:95/:105/:117/:130/:157/:169 | `chk_gamma_fest`, `geo_combo`, `breite_spin`, `r2_spin`, `r2min_spin`, `alpha_max_spin`, `alpha_plausibel_spin`, `nachfenster_spin`, `gewicht_combo`, `chk_bestaetigen` | – | `parameter()` bei OK | jeweiliges `PhysikParameter`-Feld (alle konsumiert) | ok |
| **:146** | **`moden_spin`** | – | `parameter()` → `_physik_uebernehmen` | `_physik`, `stapel`, `spin_moden` – **nicht** Zonen-Panel | **teilweise tot (A2)** |
| :190 | „Standardwerte" | clicked | `_standardwerte` | alle Felder | ok |
| **Export-Dialoge (`export_dialog.py`)** |
| :67 | `AlleSpeichernDialog._boxen[*]` | – | `auswahl()` | Export-Teile | ok |
| :77/:84 | `ordner`, `basis` | – | `auswahl()` | Pfad/Basisname | ok |
| :81 | Ordner-Knopf | clicked | `_ordner_waehlen` | `ordner` | ok |
| **:137** | **`SpaltenDialog._boxen[*]`** | – | `einstellungen()` | Export-Spalten | **ok\* (A9: alle abwählen = alle)** |
| :145/:148/:152 | `chk_nur_gefittete`, `chk_csv_deutsch`, `chk_zusatz` | – | `einstellungen()` | Exportoptionen | ok |
| :161 | „Alle" | clicked | Lambda setzt `_boxen` | Spaltengruppen | ok |
| **Auswertungsfenster (`auswertung_fenster.py`)** |
| **:114** | **`geo_combo`** | currentTextChanged | `aktualisiere()` | nur Fensteranzeige | **ok\* (A8)** |
| :121 | `mode_combo` | currentIndexChanged | `aktualisiere()` | Moden-Ansicht/Fit | ok |
| :155 | `btn_rueckgaengig` | clicked | `_rueckgaengig` | Undo | ok |
| :159 | `btn_export` | clicked | `_exportieren` | Dateien | ok |
| **Mapping-Dialog (`mapping_dialog.py`, unverändert gg. 7c893e8)** |
| :73 | `profil_combo` | currentIndexChanged | Profilwechsel | Kanalzuordnung | ok |
| :120 | `layout_combo` | currentIndexChanged | Layoutwechsel | Kanalzuordnung | ok |

---

## Empfohlene Reihenfolge der Behebung

1. **A2** (eine Zeile in `_physik_uebernehmen`) – stellt das Band-Werkzeug wieder her.
2. **A1** (eine Zeile `spin_moden.valueChanged.connect(self._setze_n_moden)` **oder**
   Widget entfernen) – beseitigt die auffälligste „Eingabe ohne Wirkung".
3. **A3** (zwei Zeilen tauschen) – Datenverlust bei Mode-Ausreißern.
4. **A5**, **A4**, **A6**, **A9**, **A8**, **A7** nach Bedarf.

Alle Fixes sind lokal; kein Rollback auf 7c893e8 nötig – die Referenz kennt die
betroffenen Widgets zum größten Teil gar nicht.

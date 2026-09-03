# Bereich D – Panel „Zonen & Grenzgeraden“ (HEAD e3b1ea7 / V0.1.66 gegen Referenz 7c893e8)

Repro-Skripte: `repro_D.py`, `repro_D2.py`, `repro_D3.py`, `repro_D4.py`, `repro_D5.py`
(alle in diesem Verzeichnis, Aufruf: `QT_QPA_PLATFORM=offscreen /home/ibrahim/Dokumente/Ananas/.venv/bin/python <skript>`).
Bestehende Tests `tests/test_grenzgeraden_gui.py` + `tests/test_modus_manager.py`: **31 passed** in HEAD.
Die Zwei-Klick-Mechanik, Esc-Abbruch, Modus-Exklusivität, Doppelklick-Seitenwechsel und Endpunkt-Drag
funktionieren in HEAD nachweislich (repro_D3.py). Die vom Nutzer gemeldeten Ausfälle sind **keine
Ausfälle des Klick-Handlings**, sondern (a) eine nicht synchronisierte Modenzahl, die das Band-Werkzeug
unsichtbar und den Fit unbrauchbar macht, (b) drei bis vier gleichnamige „Resonanzen“-Bedienelemente,
von denen eines wirkungslos ist, und (c) Bezeichnungs-Kollisionen („Band“, „Res.“, „Mode“, „Zone“).

---

## 1. Vollständige Funktionsliste des Panels

### 1.1 Referenz 7c893e8 – `polderfit/gui/zonen_panel.py` (176 Zeilen)

| Widget | Zeile | Slot | Wirkung auf den State |
|---|---|---|---|
| Label „Gerade per zwei Klicks einfügen …“ | 53–59 | – | statisch |
| `btn_gerade` „Gerade einzeichnen (2 Klicks)“ (checkable) | 61–67 | `_gerade_umgeschaltet` → `Hauptfenster._gerade_modus` (hauptfenster.py:726) | startet/beendet Matrix-Modus `"gerade"`; Vorbedingung `_modus_start_erlaubt(braucht_fits=True)` – **ohne Auto-Fit gesperrt** |
| `geraden_liste` (QListWidget) | 69–71 | – | reine Auswahl; `setze_geraden` (127) füllt neu, Auswahl bleibt nur, wenn Index noch gültig |
| `btn_gerade_seite` „Seite wechseln“ | 74–79 | `_gerade_seite_geklickt` (168) → `Hauptfenster._gerade_seite` (781) | **nur bei `currentRow() >= 0`**; ruft `Grenzgerade.seite_wechseln()` |
| `btn_gerade_entfernen` „Entfernen“ | 80–82 | `_gerade_entfernen_geklickt` (173) → `_gerade_entfernen` (790) | nur bei Auswahl; `del self._grenzgeraden[i]` |
| `btn_geraden_fit` „Grünen Bereich neu fitten …“ | 85–88 | Lambda → `_geraden_fit` (799) | Dialog (nur Modus + Fensterbreite), dann `fitte_geraden_bereich` |
| `btn_zone` „Zone im Farbplot einzeichnen“ (checkable) | 100–106 | `_zone_umgeschaltet` → `_zone_modus` (713) | Matrix-Modus `"zone"`, ebenfalls `braucht_fits=True` |
| `zonen_liste` | 108–110 | – | |
| `btn_zone_entfernen` | 112–114 | `_zone_entfernen_geklickt` (159) | |
| `setze_modus_aktiv` / `setze_gerade_modus_aktiv` | 139–152 | vom Modus-Manager | Knopf-Sync ohne Rückruf |

**Keine** Modenzahl, kein Band-Werkzeug, kein „Mode ändern“, kein Mode-Attribut.
Die Grenzgeraden wurden in 7c893e8 **nicht** im Projekt gespeichert (Projektversion 2).

### 1.2 HEAD – `polderfit/gui/zonen_panel.py` (347 Zeilen)

| Widget | Zeile | Slot | Wirkung auf den State |
|---|---|---|---|
| `n_moden_combo` „Resonanzen je Linescan:“ (1…6) | 68–79 | `_n_moden_gewaehlt` (224) → `Hauptfenster._setze_n_moden` (hauptfenster.py:1955) | setzt `self._n_moden`, `_physik.n_moden`, `stapel.n_moden`, `spin_moden`, ruft `setze_geraden` neu; **einzige Stelle, die `band_box`/`btn_gerade_mode` sichtbar macht** |
| `hinweis_g` (dynamisch) | 81–83 | – | Text aus `_moden_ansicht_aktualisieren` (252) |
| `band_box` (Container, nur sichtbar bei `_n_moden > 1`) | 86–111, 255 | – | |
| `breite_spin` „Bandbreite ± … mT“ | 91–97 | – | gelesen von `bandbreite_T()` (231) |
| `btn_band` „Band einzeichnen (2 Klicks entlang der Mode)“ | 100–107 | `_band_umgeschaltet` (239) → `_band_modus` (hauptfenster.py:1071) | Matrix-Modus `"band"`; nach 2 Klicks `band_geraden(...)` → **zwei** Geraden ±Breite, Seiten automatisch nach innen, `mode = mode_neu()` |
| `band_status` „Bänder: M1 ✓ (2) · M2 – (0) → nächste Gerade/Band: Mode k“ | 108–110, 268–273 | – | Statusanzeige |
| `btn_gerade` „Gerade einzeichnen (2 Klicks)“ | 113–119 | `_gerade_umgeschaltet` (335) → `_gerade_modus` (1040) | wie Referenz, aber **ohne** `braucht_fits`, dafür **mit** `_mapping_vorhanden()` |
| `geraden_liste` | 121–123 | – | `setze_geraden` (189) wählt neue Geraden automatisch vor |
| `btn_gerade_seite` „Seite wechseln“ | 126–131 | `_gerade_seite_geklickt` (339) → `_gerade_seite` (1138) | `_gerade_zeile()` (297): **ohne Listenauswahl die zuletzt gesetzte Gerade** |
| `btn_gerade_mode` „Mode ändern“ (nur `_n_moden > 1`) | 132–136, 256 | `_gerade_mode_geklickt` (304) → `_gerade_mode` (1148) | `mode = aktuell % _n_moden + 1`, zyklisch |
| `btn_gerade_entfernen` „Entfernen“ | 137–139 | `_gerade_entfernen_geklickt` (344) | wie oben, Fallback letzte Gerade |
| `btn_geraden_fit`, Text wechselt zu „Mode 1 fitten …“ / „Moden 1–n fitten …“ | 142–149, 259 | `_geraden_fit` (1199) | Vorprüfung `zaehle_abgedeckt`, dann `BereichsFitDialog` (Modus, Frequenz/Feld von…bis, **Resonanzen je Linescan**, Fensterbreite) |
| Ausschlusszonen-Block | 154–176 | wie Referenz | `_zone_modus` jetzt **ohne** `braucht_fits` |
| `setze_n_moden` (213) / `n_moden_effektiv` (247) / `mode_neu` (283) | | | Automatische Mode-Vergabe: 2 Geraden = 1 Band = 1 Mode |

Zusätzlich neu in HEAD (nicht im Panel, aber gleiche Funktion):
`akt_gerade` „Grenzgerade einzeichnen“ **Strg+L** (hauptfenster.py:493) und `akt_zone`
„Ausschlusszone einzeichnen“ (501) im Funktionen-Menü. Das Band-Werkzeug hat **keine** Menü-Aktion.

### 1.3 Der „Jumper“ – Befundlage

Im Code heißt „Jumper“ **ausschließlich** die Unterabtastung „nur jeden n-ten Messpunkt“ im
Auto-Fit-Dialog (`polderfit/fit/auswahl.py:4`, `polderfit/gui/auswahl_dialog.py`).
**Dieser Jumper existiert in HEAD unverändert weiter**, nur der Fenstertitel wurde geändert:

* 7c893e8: `auswahl_dialog.py:26` `setWindowTitle("Auswertungsbereich & Jumper")`, Gruppe
  „Nur jeden n-ten Messpunkt auswerten“ (Zeile 45–58).
* HEAD: `auswahl_dialog.py:61` `setWindowTitle("Auto-Fit: Bereich, Jumper & Resonanzen")`,
  identische Gruppe (Zeile 85–98), zusätzlich ROI-Knöpfe und ein Resonanzen-Dropdown.

Was aus dem Farbplot **tatsächlich verschwunden ist**, ist das zweite Zwei-Klick-Werkzeug direkt
neben „Grenzgerade“: **„Resonanz vorgeben“ (Dispersions-Seed), Strg+D**.

* Referenz: `matrix_ansicht.py:52` `MODI = ("seed", "bereich", "zone", "ausreisser", "gerade")`,
  `_ZWEI_PUNKT_MODI = ("seed", "gerade")` (64), `starte_dispersion_seed` (197),
  `_seed_klick` (795); Hauptfenster `akt_seed` (308–318), `_seed_umschalten` (687),
  `_seed_fertig` (1290–1342): zwei Klicks legen eine Kittel-Gerade `B_res(f)`, daraus
  `zentren` → `fitte_alle(..., zentren=zentren)` (Auto-Fit mit vorgegebener Dispersion).
* HEAD: `MODI = ("bereich", "zone", "ausreisser", "gerade", "band")` (matrix_ansicht.py:68),
  `_ZWEI_PUNKT_MODI = ("gerade", "band")` (80). Kein `seed` mehr.
* **Entfernt in Commit 45871fa** („… ‚Resonanz vorgeben‘ (Seed) aus der GUI entfernt“).
* Die Kernfunktion lebt weiter: `polderfit/fit/batch.py:283/305/322-326` akzeptiert weiterhin
  `zentren=`. Eine Wiederherstellung wäre also reine GUI-Arbeit (Aktion + Modus + Callback).

> **Empfehlung:** Beim Nutzer rückfragen, ob mit „Jumper“ (a) die n-te-Punkt-Unterabtastung
> gemeint ist (dann: existiert, nur der Dialogtitel heißt anders und der Dialog hat viel mehr
> Inhalt bekommen) oder (b) „Resonanz vorgeben“ / Strg+D (dann: in 45871fa bewusst entfernt,
> `zentren=` im Backend noch vorhanden).

---

## Bug D-1 – „Resonanzen je Linescan“ im Panel wird beim Projektladen und beim Parameter-Dialog nicht gesetzt → Band-Werkzeug unsichtbar, Grenzgeraden-Fit bricht ab

**Symptom.** Nach `Projekt laden` (oder nach Strg+P „Physikalische Parameter“ → Resonanzen je
Linescan = 2, oder mit gespeicherten Voreinstellungen n_moden = 2) steht im Panel weiterhin
„1 – eine Mode (klassisch)“. „Bandbreite ±“, „Band einzeichnen“ und „Mode ändern“ sind **unsichtbar**.
Im Farbplot sind die geladenen Mode-2-Geraden mit „M2“ beschriftet, in der Panel-Liste fehlt das
`M…`-Präfix. „Grünen Bereich fitten …“ bricht vor dem Dialog ab mit
„kein Linescan im grünen Bereich … ‚Resonanzen je Linescan‘ steht auf 1“.

**Reproduktion** (`repro_D2.py`, Abschnitte BUG 1 + BUG 2):
```
nach _physik_uebernehmen(n_moden=2):
  physik.n_moden = 2 | stapel.n_moden = 2 | spin_moden = 2 | zonenpanel._n_moden = 1
  band_box sichtbar: False | 'Mode ändern' sichtbar: False
Moden der Geraden: [1, 1, 2, 2]
  panel._n_moden: 1 -> n_moden_effektiv(): 1
  Listentext: (2.550 T, 10.00 GHz) – (2.750 T, 40.00 GHz)  · grün: +      <- kein "M1 ·"
  zaehle_abgedeckt(n=n_eff=1): 0        <- _geraden_fit() bricht ab
  zaehle_abgedeckt(n=2, korrekt): 10
```
Persistenz selbst ist in Ordnung (`repro_D5.py`): Projektversion 3 speichert
`grenzgeraden` inkl. `mode` und lädt sie korrekt zurück.

**Datei:Zeile.**
* `polderfit/gui/hauptfenster.py:1927-1953` `_physik_uebernehmen` – setzt `self._physik`,
  `self.spin_moden`, `stapel.n_moden`, **aber nie `self.zonenpanel.setze_n_moden(...)`**.
* Aufrufer: `hauptfenster.py:2945` (Projekt laden), `:1925` (Parameter-Dialog),
  `:3009` `_einstellungen_anwenden` (Voreinstellungen laden / Standard).
* Startpfad: `hauptfenster.py:159` `self._physik = self._einstellungen.physik_parameter()`
  vor dem Bau des Panels (`:184`), das mit `_n_moden = 1` (`zonen_panel.py:54`) startet.
* Folge im Panel: `zonen_panel.py:243-250` `_mode_von` **klemmt** jede Mode auf `self._n_moden`,
  `n_moden_effektiv()` liefert deshalb 1; `zonen_panel.py:252-256` blendet `band_box` und
  `btn_gerade_mode` aus; `:204` unterdrückt das `M…`-Präfix.
* Folge im Fit: `hauptfenster.py:1252` `n_eff = self.zonenpanel.n_moden_effektiv()` →
  `zaehle_abgedeckt(..., n_moden=1)` (`fenster_steuerung.py:416`) → `moden_modus = False` →
  Schnitt **aller vier** grünen Halbebenen → leer.

**Root Cause.** Die Modenzahl hat vier Speicherorte (`_physik.n_moden`, `stapel.n_moden`,
`spin_moden`, `ZonenPanel._n_moden`), aber nur **ein** Setter (`_setze_n_moden`, hauptfenster.py:1955)
synchronisiert alle vier. `_physik_uebernehmen` synchronisiert drei von vier.

**Diff zu 7c893e8.** In 7c893e8 gibt es weder `n_moden` noch das Panel-Feld – der Fehler ist
vollständig in `45871fa`/`798b794`/`0807c7c` neu entstanden.

**Fixvorschlag** (Fix im aktuellen Code, klein und lokal):
```python
# hauptfenster.py, Ende von _physik_uebernehmen (nach self.spin_moden.blockSignals(False))
self.zonenpanel.setze_n_moden(max(1, int(parameter.n_moden)))
```
`ZonenPanel.setze_n_moden` blockiert die Combo-Signale selbst, es entsteht keine Rekursion.
Zusätzlich beim Projektladen nach `self._grenzgeraden = grenzgeraden_aus_sitzung(daten)`
(hauptfenster.py:2966) die Modenzahl an den geladenen Geraden nach oben ziehen:
`self._setze_n_moden(max([g.mode for g in self._grenzgeraden] + [self._physik.n_moden]))`.

**Risiko.** Gering. Betrifft nur GUI-Sync; `setze_n_moden` ist idempotent und ruft
`setze_geraden` mit der bestehenden Liste auf.

---

## Bug D-2 – „Res.: n ×“ im Linescan-Panel ist ein toter Zwilling des Panel-Dropdowns

**Symptom.** Der Nutzer stellt „Res.: 2 ×“ ein und erwartet, damit den Mehr-Moden-Modus
eingeschaltet zu haben. Das Band-Werkzeug bleibt unsichtbar, der Grenzgeraden-Fit bleibt
einmodig, das Panel-Dropdown bleibt auf 1. Umgekehrt springt „Res.“ mit, wenn man das
Panel-Dropdown ändert – die Kopplung ist also **einseitig** und wirkt genau falschherum.

**Reproduktion** (`repro_D.py`, Abschnitte A und B):
```
--- A: 'Res.' Spin im Linescan-Panel auf 2 stellen ---
nach spin=2 -> panel._n_moden: 1 | physik.n_moden: 1 | stapel.n_moden: 1 | combo: 1 | band_box: False
--- B: Panel-Combo auf 2 stellen ---
nach combo=2 -> panel._n_moden: 2 | physik: 2 | stapel: 2 | spin: 2 | band_box: True
```

**Datei:Zeile.** `polderfit/gui/hauptfenster.py:280-285` erzeugt `self.spin_moden`;
es gibt **keine** `valueChanged`-Verbindung (alle Vorkommen: 280–285, 306, 314, 1931–1933,
1964–1966, 2328, 2351). Gelesen wird der Wert nur in `_grenzen_geaendert` (2327) und
`_neu_fitten` (2350), also für Einzelfrequenz-Nachfits.

**Root Cause.** Widget ohne Signalanschluss; der Kommentar in `zonen_panel.py:65-66`
(„EINE sichtbare Stelle; synchron mit dem Auto-Fit-Dialog und ‚Res.‘ im Linescan-Panel“)
beschreibt einen Zustand, der so nur in einer Richtung existiert.

**Diff zu 7c893e8.** `spin_moden` existiert in 7c893e8 nicht (dort `fitte_neu(stapel, i,
feld_unten=..., feld_oben=...)` ohne `n_moden`, hauptfenster.py:1458/1479). Neu in 45871fa.

**Fixvorschlag.** Entweder
(a) **Fix**: `self.spin_moden.valueChanged.connect(self._setze_n_moden)` – macht „Res.“ zum
gleichwertigen Bedienelement (Blockierungen in `_setze_n_moden`/`_physik_uebernehmen` sind
bereits vorhanden, keine Signalschleife); oder
(b) **Entfernen**: `spin_moden` streichen und in `_neu_fitten`/`_grenzen_geaendert`
`self._physik.n_moden` verwenden – dann bleibt genau **eine** sichtbare Stelle, wie im
Panel-Kommentar behauptet. (b) ist die konsistentere Lösung.

**Risiko.** (a) minimal. (b) mittel: `tests/test_gui.py`/`test_inplot_gui.py` auf `spin_moden`
prüfen (`grep -rn spin_moden tests/`).

---

## Bug D-3 – „Mode ändern“ auf EINER Geraden schaltet stillschweigend den ganzen Fit-Algorithmus um

**Symptom.** Der Knopf sieht aus wie ein Etikettenwechsel („Gewählte Gerade der nächsten Mode
zuordnen“). Tatsächlich wechselt der Grenzgeraden-Fit dadurch von der Ein-Moden-Fenstersuche
(`_fitte_mit_intervallen`, mit Stationär-Abzug und `breite_punkte`) auf den band-beschränkten
Mehr-Moden-Pfad (`_fitte_moden_baender`, **ohne** Fenstersuche, `breite_punkte` wirkungslos).

**Reproduktion** (`repro_D2.py`, Abschnitt BUG 3):
```
2 Geraden, Moden: [1, 1] n_eff: 1 -> Fit-Knopf: Mode 1 fitten …
nach 'Mode ändern' auf Gerade 2 -> Moden: [1, 2] n_eff: 2 -> Fit-Knopf: Moden 1–2 fitten …
```
Jetzt hat Mode 1 nur noch **eine** Gerade (Halbebene statt Band) und Mode 2 ebenfalls eine;
`_moden_baender` akzeptiert das (Mode ohne Geraden = „frei“), das Fit-Fenster wird die Hülle
±50 % – ein völlig anderer Fit als vorher, ohne Warnung.

**Datei:Zeile.**
* `polderfit/gui/zonen_panel.py:304-308` `_gerade_mode_geklickt`
* `polderfit/gui/hauptfenster.py:1148-1157` `_gerade_mode`
* Umschaltpunkt: `hauptfenster.py:1252-1253` `n_eff = …; moden_modus = n_eff > 1`
* `polderfit/fit/fenster_steuerung.py:541` `moden_modus = n_moden > 1 and any(mode > 1 …)`
  → `:576` `_fitte_moden_baender` statt `:581` `_fitte_mit_intervallen`

**Root Cause.** Der Moden-Pfad wird allein aus „existiert irgendeine Gerade mit `mode > 1`“
abgeleitet, nicht aus „für jede Mode 1…n existiert ein vollständiges Band (≥ 2 Geraden)“.
`zonen_panel.mode_neu()` (283–295) verlangt für die automatische Vergabe ≥ 2 Geraden je Mode –
`n_moden_effektiv()` (247–250) tut das nicht.

**Diff zu 7c893e8.** Existiert dort nicht (kein `mode`-Attribut, ein einziger Fit-Pfad).

**Fixvorschlag** (Fix im aktuellen Code):
1. `n_moden_effektiv()` nur Moden zählen, deren Band vollständig ist (≥ 2 Geraden), sonst
   auf die höchste vollständige Mode zurückfallen – dann bleibt eine halbe Zuordnung folgenlos.
2. Im Fit-Dialog (`_geraden_fit`, hauptfenster.py:1264-1274) explizit protokollieren/anzeigen:
   „Mode k hat nur 1 Gerade – kein Band, die Mode wird frei gefittet.“
3. Knopf umbenennen von „Mode ändern“ auf **„Zu Mode 2 verschieben“** (Text dynamisch aus
   `mode_neu`-Logik), damit klar ist, dass hier die Bandzugehörigkeit geändert wird.

**Risiko.** Punkt 1 ändert das Fit-Verhalten für halbfertige Bänder (heute: Mehr-Moden-Fit,
danach: Ein-Moden-Fit). Das ist die gewollte Richtung, sollte aber mit dem Nutzer abgestimmt
und in `tests/test_neue_funktionen.py::test_grenzgeraden_band_*` abgesichert werden.

---

## Bug D-4 (Bezeichnung, kein Absturz) – „Zwei Geraden ergeben ein Band“ stimmt mit den Standard-Seiten nicht

**Symptom.** Der Hinweistext (`zonen_panel.py:276-281`, identisch in 7c893e8:53-57) verspricht
„Zwei Geraden ergeben ein Band“. Frisch gezeichnete Geraden haben aber beide
`gruen_positiv=True` – der Schnitt ist eine **Halbebene**, kein Band. Der Nutzer muss auf eine
der beiden Linien doppelklicken. Nichts im UI sagt das an dieser Stelle.

**Reproduktion** (`repro_D4.py`):
```
f= 10.0 GHz  Standard-Seiten (beide +): erlaubtes Intervall = (2.7, 3.5)   <- Halbebene
f= 40.0 GHz  Standard-Seiten (beide +): erlaubtes Intervall = (2.9, 3.5)
-- nach Doppelklick auf Gerade 2 --
f= 10.0 GHz  -> (2.6, 2.7)                                                 <- jetzt Band
f= 40.0 GHz  -> (2.8, 2.9)
```

**Datei:Zeile.** `polderfit/fit/fenster_steuerung.py:352` `gruen_positiv: bool = True`
(Default), `hauptfenster.py:1058-1062` `_gerade_gezeichnet` legt die Gerade ohne Seitenwahl an.

**Diff zu 7c893e8.** Identisch – **keine Regression**, aber die Ursache dafür, dass „zwei
Geraden = Band“ im Alltag nicht funktioniert; genau dafür wurde „Band einzeichnen“ gebaut.

**Fixvorschlag.** In `_gerade_gezeichnet`: wenn bereits eine Gerade derselben Mode existiert,
die zweite automatisch so orientieren, dass ihre grüne Seite zur ersten zeigt (dieselbe Logik
wie `band_geraden`, fenster_steuerung.py:385-403). Alternativ nur Textänderung:
„Zwei Geraden ergeben ein Band – bei der zweiten Geraden mit Doppelklick die Seite umdrehen.“

**Risiko.** Automatische Orientierung ändert bestehendes Verhalten; Textfix ist risikofrei.

---

## Bug D-5 (Text) – Ausschlusszonen-Hinweis spricht von „Band“

`polderfit/gui/zonen_panel.py:158`:
`"bereits gefittete Linescans im Band rechnen sofort neu."` –
im Ausschlusszonen-Kontext gibt es kein Band; gemeint ist der Frequenzbereich der Zone
(intern `_fitte_zonen_band`, fenster_steuerung.py:188). 7c893e8:96 hatte den korrekten Text
`"betroffene Linescans fitten sofort neu."`
**Fix:** Text auf die Referenzformulierung zurücksetzen. Risiko: keins.

---

## 2. „Gerade einzeichnen (2 Klicks)“ – Ablauf in beiden Versionen

**Referenz 7c893e8**
1. `btn_gerade.toggled` → `ZonenPanel._gerade_umgeschaltet` (164) → `Hauptfenster._gerade_modus` (726).
2. Vorbedingung `_modus_start_erlaubt(braucht_fits=True)` (672) – **ohne Auto-Fit gesperrt**.
3. `MatrixAnsicht.starte_gerade_zeichnen` (209) → `starte_modus("gerade", cb)` (148): beendet den
   laufenden Modus, `_seed_punkte = []`, Cross-Cursor, `setFocus()`, `modus_geaendert("gerade")`.
4. `_on_press` (810): `if self._modus in _ZWEI_PUNKT_MODI: self._seed_klick(event); return`.
   `_seed_klick` (795) sammelt `(B, f_GHz)`, setzt einen orangen `"P"`-Marker; beim zweiten Punkt
   `beende_modus()` **vor** dem Callback, dann `fertig(punkte)`.
5. `Hauptfenster._gerade_gezeichnet` (740) → `Grenzgerade(...)` → `_zeige_geraden` (750) → Undo.

**HEAD** – strukturell identisch, umbenannt und erweitert:
1. `btn_gerade`/`akt_gerade` (Strg+L) → `_gerade_modus` (1040).
2. Vorbedingung `_modus_start_erlaubt()` **ohne** `braucht_fits` (funktioniert jetzt direkt nach
   dem Laden), **zusätzlich** `_mapping_vorhanden()` (1845) – ohne Kanal-Zuordnung erscheint eine
   modale Box und der Knopf springt zurück (bestätigt in `repro_D3.py`, letzter Abschnitt).
   Die Ausschlusszone hat diese Prüfung **nicht** (1025-1038) – inkonsistent, aber harmlos.
3. `starte_modus` (190) → `_punkt_liste = []` (`_ZWEI_PUNKT_MODI = ("gerade", "band")`).
4. `_on_press` (1032) → `_zwei_punkt_klick` (1015, umbenannt aus `_seed_klick`), Marker jetzt
   `F.SIGNAL_BLAU`. Rest identisch.
5. `_gerade_gezeichnet` (1056) setzt zusätzlich `mode=self.zonenpanel.mode_neu()` und ruft über
   `_merke_geraden_aenderung` (1119) neu auch `_auswertung_nachziehen()`.

**Sonderfälle – alle in HEAD verifiziert (`repro_D3.py`), kein Bruch:**

| Fall | Ergebnis HEAD |
|---|---|
| Esc nach dem 1. Klick | Modus `None`, Punktliste geleert, Marker entfernt, `btn_gerade` entprellt, keine Gerade |
| Job läuft (`_job_laeuft=True`) | Modus startet nicht, `btn_gerade` und `akt_gerade` springen zurück, Log-Warnung |
| Zoom aktiv | Zwei-Punkt-Zweig läuft **vor** dem Box-/Zoom-Zweig (`_on_press`:1036) – Gerade entsteht |
| Modus-Wechsel Gerade→Band→Zone | exklusiv, alle drei Knöpfe und `akt_zone`/`akt_gerade` korrekt synchronisiert |
| Doppelklick auf die Linie | `_finde_gerade_linie` → `_gerade_seite` → Seiten getauscht |
| ohne Kanal-Zuordnung | modale Box, Modus startet nicht (Zone dagegen schon) |

**Fazit zu Frage 2: In HEAD bricht das Zwei-Klick-Zeichnen an keiner Stelle.** Die Nutzer-
wahrnehmung „kaputt“ erklärt sich über D-1 (Band-Werkzeug unsichtbar), D-3/D-4 (der Fit
danach findet nichts) und über die modale Mapping-Box in Schritt 2.

---

## 3. „Seite wechseln“, „Mode ändern“, „Band“ – Wirkung auf Datenstruktur und Fit

Datenstruktur `polderfit/fit/fenster_steuerung.py:336-381`:
```python
@dataclass
class Grenzgerade:
    b1: float; f1: float   # Hz     – Handgriff 1
    b2: float; f2: float   # Hz     – Handgriff 2
    gruen_positiv: bool = True      # welche Halbebene gefittet wird
    mode: int = 1                   # NEU in HEAD: Bandzugehörigkeit
```
Es gibt **kein** „links/rechts“-Attribut; die Seite ist rein über das Vorzeichen des
Kreuzprodukts `(P-P1)×(P2-P1)` definiert (`erlaubtes_intervall`, :361-381 – unverändert gegenüber
7c893e8). Die Gerade ist unendlich; `b1/f1/b2/f2` sind nur Griffe.

* **„Seite wechseln“** → `seite_wechseln()` (:358) kippt `gruen_positiv`. Wirkung: **Fenster-
  begrenzung**, keine Maskierung. Je Frequenz liefert `erlaubtes_intervall` das Feldintervall der
  grünen Halbebene; ist der Schnitt aller Geraden leer, wird der Linescan **übersprungen**
  (bleibt unverändert), er wird nicht „ausgeschlossen“. Identisch in beiden Versionen.
  Unterschied HEAD: wirkt ohne Listenauswahl auf die **zuletzt gesetzte** Gerade
  (`_gerade_zeile`, zonen_panel.py:297; Commit 03a4939). Funktioniert (repro_D.py, Abschnitt D).
* **„Mode ändern“** → `mode = aktuell % _n_moden + 1`. Reine Zahl am Objekt; alle Wirkung
  entsteht indirekt über `n_moden_effektiv()` → siehe **Bug D-3**. Im Farbplot bekommt nur
  `mode > 1` eine farbige Linie plus „M2“-Text (matrix_ansicht.py:877-890) – Mode-1-Geraden
  bleiben unbeschriftet, was die Zuordnung beim Zurückschalten unsichtbar macht.
* **„Band einzeichnen“** → `band_geraden` (fenster_steuerung.py:384-404): erzeugt aus einer
  geklickten Linie **zwei** parallele Geraden bei `b ± halbbreite`, orientiert die grünen Seiten
  automatisch nach innen und setzt beide auf `mode`. Verifiziert (`repro_D.py`, Abschnitt G):
  `[(2.99, 3.29, mode 2, True), (3.01, 3.31, mode 2, False)]`.
  Grenzfall: `f1 == f2` wirft `ValueError` → nur Log-Warnung „Band: …“ (hauptfenster.py:1095),
  ein Band bei konstanter Frequenz ist also nicht möglich (fachlich sinnvoll, aber nicht erklärt).
* **Ausschlusszonen** sind der einzige echte **Maskierungs**-Mechanismus (Punkte fallen aus allen
  Fits). Grenzgeraden maskieren nichts.

### Bezeichnungs-Kollisionen (gesammelt)

„**Band**“ bedeutet an drei Stellen etwas anderes:
1. Moden-Band aus zwei Grenzgeraden – `btn_band`, „Bandbreite ±“, „Bänder: M1 ✓“, `band_geraden`.
2. Fit-Fenster / Resonanzband im Linescan-Panel – „Zoom aufs Band“, „grüne Linien ziehen, um das
   Band zu ändern“, `_grenzen_geaendert` „neue Bandgrenzen“, „ganzer Feldsweep statt Zoom aufs Band“.
3. Frequenzbereich einer Ausschlusszone – `_fitte_zonen_band`, Panel-Text „Linescans im Band“
   (**Bug D-5**), sowie „Frequenz-Ausschlussbänder“ im Auto-Fit-Dialog.

„**Resonanzen je Linescan**“ / „**Res.**“ / „**Mode**“ existiert an **vier** Bedienstellen:
| Ort | Beschriftung | Datei:Zeile | wirkt auf |
|---|---|---|---|
| Zonen-Panel | „Resonanzen je Linescan:“ (Dropdown) | zonen_panel.py:68-79 | alles (einziger vollständiger Setter) |
| Linescan-Panel | „Res.: n ×“ (Spin) | hauptfenster.py:280-285 | **nur** Einzelfit; nirgends verbunden (**Bug D-2**) |
| Auto-Fit-Dialog | „Resonanzen je Linescan / Anzahl:“ | auswahl_dialog.py:172-185 | `_setze_n_moden` beim OK |
| Grenzgeraden-/Bereichsfit-Dialog | „Resonanzen je Linescan:“ | bereichsfit_dialog.py (n_moden-Spin) | nur **anhebend** (hauptfenster.py:1259-1260) |
| Parameter-Dialog Strg+P | „Resonanzen je Linescan:“ | parameter_dialog.py:146-155 | Physik + Stapel, **nicht** das Panel (**Bug D-1**) |

„**Zone**“ = Ausschlussrechteck; „**ROI**“ = Auto-Fit-Rechteck; „**Bereich**“ = sowohl Rechteck-Fit
als auch „Frequenz von … bis“ im Dialog als auch „Grünen Bereich fitten“. Drei Rechtecke, drei Namen.

---

## 4. Verwendung der Geraden im Fit (beide Versionen)

**7c893e8** – `fitte_geraden_bereich` (fenster_steuerung.py:357-391), ein Pfad:
```
je Linescan i:  erlaubt = (feld.min, feld.max)
                für jede Gerade:  erlaubt = g.erlaubtes_intervall(ls.frequenz, *erlaubt)
                erlaubt is None -> uebersprungen ; sonst intervalle[i] = erlaubt
→ auto_fenster_intervalle(datensatz, intervalle, ...)   # Fenstersuche NUR im Intervall
→ _fitte_neu_mit_nachfenster(stapel, i, *fenster[i])
```
Ja: **pro Frequenz wird der Schnittpunkt der Geraden mit der Horizontalen `f = const` als
Fenstergrenze benutzt** – nicht als Maske. `fitte_geraden_bereich` kennt weder Frequenz-/Feld-
Bereich noch Abbruch noch Moden.

**HEAD** – `fitte_geraden_bereich` (:504-583), zwei Pfade:
* Zusätzliche Vorfilter `frequenz_min/max` (Hz) und `feld_min/max` (T) aus dem Dialog (:556-570).
* `moden_modus = n_moden > 1 and any(g.mode > 1)` (:541).
  * **False** → wie Referenz, plus `abbruch=` und `n_moden=` an `_fitte_mit_intervallen`.
  * **True** → `_moden_baender` (:441-466) baut je Mode k das Band (Schnitt der grünen Seiten
    ihrer Geraden); Moden ohne Geraden = „frei“; ist **irgendein** definiertes Band bei dieser
    Frequenz leer → Linescan übersprungen. Fit-Fenster = Hülle aller Bänder + 50 % Rand.
    Dann `_fitte_moden_baender` (:469-501): **keine** Fenstersuche, Startwerte je Band über
    `startwerte_in_bereichen`, `B_res_k` im Fit auf sein Band beschränkt (`bereiche=baender`).
    **`breite_punkte` ist in diesem Pfad wirkungslos**, obwohl der Dialog es weiter anbietet.
* Aufrufer `hauptfenster._geraden_fit` (:1199-1300): Vorprüfung `zaehle_abgedeckt(:405-431)`
  vor dem Dialog (ohne die Bereichsgrenzen des Dialogs, also optimistisch), Modenzahl des Fits
  = `zonenpanel.n_moden_effektiv()`, im Dialog nach oben korrigierbar.
* Nebenwirkung des Pfadwechsels: beim sukzessiven Arbeiten („Band Mode 1 → fitten → Band Mode 2
  → fitten“) wird Mode 1 im zweiten Durchgang mit einem **anderen Algorithmus** neu berechnet
  (Bandfit statt Fenstersuche), weil `modus="ueberschreiben"` der Standard ist. Das ist im
  Hinweistext (`zonen_panel.py:262-266`) nicht erkennbar.

---

## 5. Persistenz der Grenzgeraden

| | 7c893e8 | HEAD |
|---|---|---|
| Projektversion | 2 | 3 (`persistenz/projekt.py:35`) |
| Grenzgeraden gespeichert | **nein** | ja, `"grenzgeraden": [asdict(g) …]` inkl. `mode` |
| Laden | – | `grenzgeraden_aus_sitzung` (projekt.py:174 ff.), `mode = max(1, int(g.get("mode", 1)))` |
| GUI-Anbindung | – | speichern hauptfenster.py:2859/2879, laden :2966 → `_zeige_geraden()` |

Verifiziert (`repro_D5.py`): Roundtrip erhält `b1/f1/b2/f2`, `gruen_positiv` und `mode`;
ein Projekt ohne den Schlüssel (Version 2) liefert `[]` – **alt→neu ist kompatibel**.
Neu→alt: die Referenzversion ignoriert unbekannte Schlüssel, verliert die Geraden also still.
**Einschränkung:** Die zugehörige Modenzahl des Panels wird beim Laden nicht mitgesetzt →
die geladenen Bänder sind bis zur manuellen Umstellung des Dropdowns unbrauchbar (**Bug D-1**).

---

## 6. Priorisierte Empfehlung

| # | Bug | Aufwand | Empfehlung |
|---|---|---|---|
| D-1 | Panel-Modenzahl nicht synchronisiert | 2 Zeilen | **sofort fixen** – erklärt „Band-Funktion kaputt“ am direktesten |
| D-2 | „Res.: n ×“ ohne Signal | 1 Zeile bzw. Entfernen | fixen oder entfernen (entfernen bevorzugt) |
| D-5 | Zonen-Text „im Band“ | 1 Zeile | Text auf 7c893e8-Formulierung zurück |
| D-3 | „Mode ändern“ schaltet Fit-Pfad | mittel | `n_moden_effektiv` auf vollständige Bänder stützen + Knopf umbenennen |
| D-4 | „Zwei Geraden = Band“ | klein–mittel | zweite Gerade automatisch nach innen orientieren, sonst Text präzisieren |
| Jumper | Begriff klären | – | Rückfrage: Unterabtastung (existiert) vs. „Resonanz vorgeben“/Strg+D (in 45871fa entfernt, `zentren=` im Backend intakt) |

# PolderFit – konsolidierte Bugliste und Rückbauplan (Stand 2026-09-03)

Basis: HEAD `e3b1ea7` (V0.1.66) gegen Referenz `7c893e8` (18.08.2026, FTF-validiert).
Einzelberichte mit Reproduktionen: `bugs/A_widgets.md` … `bugs/H_physik_regression.md`.
Branch: `fix/rueckbau-7c893e8`. Referenz-Worktree: `../polderfit-ref`.

## 0. Gesamtbild in fünf Sätzen

1. **Physik und Ein-Moden-Fit sind nicht regrediert.** AutoWindow, Einzelfit und
   Kittel/LLG sind auf identischem Fenster bitgleich zur Referenz; FTF-Werte aus
   `benchmark_ftf/BERICHT.md` werden exakt reproduziert (H, C, B §0).
2. **Alle P0-Befunde stammen aus den seit 18.08. neuen Wegen:** Fits ohne Auto-Fit
   (Fenster = ganzer Sweep, ΔH bis +34 % zu groß) und der Mehr-Moden-Summenfit
   (entartet, zweite Mode landet neben dem falschen Dip, gute Hauptmoden-Punkte
   werden verworfen).
3. **Der Moden-State hat sechs Schreib- und fünf Lesestellen**; „Res.: n ×" ist
   unverbunden, „Hauptmode ↻" überlebt kein Speichern. Beides ist ohne fachlichen
   Grund (F §4) und entfällt mit dem Korridor-Konzept.
4. **Ausreißer-Markieren funktioniert grundsätzlich** (G §1.3); es scheitert nur
   stumm bei grau angezeigten ignorierten Punkten und ausgeblendeten Problemfits.
5. **Der „Jumper" (n-ter Punkt) existiert unverändert.** Verschwunden ist das
   Zwei-Klick-Werkzeug „Resonanz vorgeben" (Dispersions-Seed, Strg+D, Commit 45871fa);
   siehe offene Frage 1.

## 1. Bugliste, dedupliziert und priorisiert

P0 = physikalisch falsch oder Regression gegen 7c893e8 · P1 = Funktion tot/unbenutzbar · P2 = UI/Übersicht.
Spalte „Lösung": R = zurück auf Referenzverhalten, F = Fix im aktuellen Code, E = Entfernen, K = durch Korridor-Konzept gelöst.

### P0

| Nr | Quelle | Befund | Datei:Zeile | Lösung |
|---|---|---|---|---|
| P0-1 | B1, B4, C | Fits ohne Auto-Fit („Neu fitten", Grenzen ziehen, Panel ohne Fit): `leerer_stapel` setzt Fenster = ganzer Feldsweep, kein Nachfenster-Durchgang → µ₀ΔH bis +34 % zu groß, R² = 0,999, unmarkiert. In 7c893e8 unmöglich (Stapel bis Auto-Fit leer). | `fit/batch.py:505-508`, `gui/hauptfenster.py:1823, 2321, 2344, 3110` | R+F: grünes Fenster aus AutoWindow (lazy je Frequenz) statt Vollsweep; Panel-Fits über `_fitte_neu_mit_nachfenster`; Warnung, wenn Fenster > 60 % des Sweeps |
| P0-2 | E1, E4, E5, B3/E3, KRIT-1, E2, E6, D-3 | Summenfit mehrerer Moden: nicht identifizierbar (15/40 Startwerte → breite 51-mT-Linie als Untergrund-Surrogat), Kandidatensperre `|B−B_res| ≤ FWHM` schließt den echten 2. Dip in 28/30 Linescans aus, Stufe 2 weitet Nachfenster auf (37 → 103 Punkte), Faktor 10,6 langsamer; `bewerte_fit` verwirft 22 von 29 Linescans nur wegen einer Nebenmode; Nadel-Linien mit ΔH < Feldschritt werden Hauptmode (60/603) | `fit/batch.py:400-425`, `fit/linescan_fit.py` (Multi-Lorentz), `fit/kriterien.py:131-149`, `physik/fitmodell.py` (Summenmodell) | E+K: Summenfit, zweistufigen Pfad und Einzelbeitrags-Kurven entfernen; Fit je Mode = Einzelfit im Korridor; Kriterien wieder je gefitteter Linie (wie 7c893e8) plus neu „Linie nicht aufgelöst" |
| P0-3 | F-4 | Projekt-Restore ignoriert Bänder (`fitte_neu` ohne `startwerte`/`bereiche`): 14/20 Linescans weichen nach Speichern/Laden bis 12 mT ab | `persistenz/projekt.py:166` | K: Restore fittet je Mode im gespeicherten Korridor |

### P1

| Nr | Quelle | Befund | Datei:Zeile | Lösung |
|---|---|---|---|---|
| P1-1 | A1, D-2, F-2 | „Res.: n ×" ohne `valueChanged`-Verbindung, dritte Wahrheit, wird still überschrieben | `gui/hauptfenster.py:280-287` | E (Konzept: n aus Zahl der Korridore) |
| P1-2 | A2, D-1, F-1 | `_physik_uebernehmen`/`_einstellungen_anwenden`/Projekt laden setzen `zonenpanel.setze_n_moden()` nicht → Band-Werkzeug unsichtbar, „Grünen Bereich fitten" bricht ab | `gui/hauptfenster.py:1927-1953, 3005, 2945` | E+K (ein State, keine Synchronisation nötig) |
| P1-3 | F-3 | „Hauptmode ↻" nicht persistiert; Projektdatei und Zustand widersprechen sich | `gui/hauptfenster.py:288-295, 2301-2321` | E (Korridor-Nummer ist die Mode) |
| P1-4 | B2, B5.4 | „Neu fitten" bestätigt den Nachfit ungeprüft als „gut – vom Nutzer bestätigt" → Problemfit-Liste schrumpft ohne Verbesserung | `fit/batch.py:559-562`, `fit/parameter.py:70` | F: `bestaetigen=False`, wenn Fenster unverändert; Bewertung nur per Kriterien oder explizit |
| P1-5 | G-1 | Ignorierte Punkte grau sichtbar, aber Klick darauf wird stumm verworfen | `gui/matrix_ansicht.py:947-956`, `gui/hauptfenster.py:2762` | F: Klick auf grauen Punkt = wieder aufnehmen (Toggle) |
| P1-6 | G-2 | „Problemfits ausblenden": auffällige Punkte nicht markierbar, Toleranz 0,03 trifft Nachbarpunkt | `gui/matrix_ansicht.py` (`_PUNKT_TOLERANZ`) | F: Pick auf sichtbare Punkte beschränken und Toleranz an Punktabstand koppeln; Hinweis in Statuszeile |
| P1-7 | ROI-1 | Hängender ROI-Rückruf: Auto-Fit-Dialog springt nach Ausschlusszone auf | `gui/hauptfenster.py` (`_roi_rueckruf`) | E (ROI entfällt) |
| P1-8 | A3 | Ausreißer-Panel „Wieder aufnehmen" liest Mode-Paare nach dem Callback, der die Liste leert | `gui/ausreisser_panel.py:116` | F (Zeilentausch) |
| P1-9 | F-5, F-6 | Drei Mode-Nummerierungen (Listenposition / Zweig / Band); Ausreißer-Panel nutzt Regel „feld" statt „band" | `gui/ausreisser_panel.py:87`, `auswertung/moden.py:105-145` | K: eine Nummer = Korridor-Index |
| P1-10 | F-7 | Rechteck-Fit senkt globale Modenzahl, Grenzgeraden-Fit hebt nur an → Bänder still entwertet | `gui/hauptfenster.py:2092, 1258` | E (`moden_spin` im Bereichsfit-Dialog) |
| P1-11 | A5 | Bewertungs-Dropdown „ignorieren" auf ignoriertem Punkt toggelt nicht (nur Strg+I) | `gui/hauptfenster.py:2231` | F |
| P1-12 | F-8 | v2-Projekte (7c893e8) hinterlassen physik ≠ stapel | `persistenz/projekt.py` | K (n_moden abgeleitet) |

### P2

| Nr | Quelle | Befund | Lösung |
|---|---|---|---|
| P2-1 | D §3, G §4, F §1 | Bezeichnungs-Kollisionen: „Band" (Moden-Band / Fit-Fenster / Frequenzbereich), „Res." / „Resonanzen je Linescan" / „Mode" an fünf Stellen | K: „Korridor Mk", „Fenster", „Ausschlusszone" |
| P2-2 | G §4.4 | Kriterien als lange Textliste im Sichtbereich | F: Buchstaben-Chip (A/P/F/U), Details im Tooltip, Legende als Dialog |
| P2-3 | A4 | Auto-Fit-Dialog „Ganzer Bereich": 1e-12-Vergleich gegen gerundete Felder → Randlinescan fällt raus | F |
| P2-4 | A6 | „Gewählte Zone entfernen" ohne Listenauswahl wirkungslos | F (wie Geraden in 03a4939) |
| P2-5 | A7 | Live-Vorschau toter Code seit 7b91ab6 | E |
| P2-6 | A8 | Kittel-Fenster `geo_combo` wirkt nicht auf Export | F |
| P2-7 | A9 | Spalten-Dialog: alle Gruppen abwählen exportiert alles | F |
| P2-8 | B5.1-B5.3 | Problemfit nur vorwärts, Umlauf ohne Rückmeldung, ignorierte Ausreißer bleiben Problemfits | F: ◀/▶, Statuszeile, Ignorierte überspringen |
| P2-9 | D-4, D-5 | Neue Geraden beide `gruen_positiv` (Halbebene statt Band); Ausschlusszonen-Text nennt „Band" | K (Korridor hat immer links+rechts) / F Text |
| P2-10 | ROI-2, ROI-3 | ROI-Modus heißt „Bereich neu fitten"; benutzte ROI wirkt still weiter | E |
| P2-11 | F-9, F-10 | `mode_neu()`-Deckel; Excel verliert Band-Nr. | K |
| P2-12 | H §4 | Handbuch-Abbildungen 380/415/515 tragen ΔH auf x über Frequenz (GUI: ΔH auf y über Feld) – regelkonform, nur uneinheitlich | F (kosmetisch, optional) |
| P2-13 | UI-Regeln | Fließtext in Panels (zonen_panel, auswahl_dialog, Kriterien) | F: Tooltips, Zusatzpanel bei Bedarf |

### Kein Bug (geprüft)
* AutoWindow-Algorithmus, Ein-Moden-Fit, Kittel/LLG, Einheiten, Unsicherheiten, ΔH-Export in Tesla (H, C).
* Zwei-Klick-Zeichnen, Esc, Job-Sperre, Zoom (D §2). Checkbox „ganzer Feldsweep" = reine Anzeige (B §3).
* Signal/Slot-System, QSS, Ruhige-Widgets (A). Achsen: Feld x / Frequenz y überall (H §4).
* FeCr₂S₄-Abweichung bei 8,41 GHz zwischen den venvs ist eine numpy/scipy-Versionsfrage, kein Code (H 2c).

## 2. Modultabelle

| Modul | Entscheidung | Begründung |
|---|---|---|
| `physik/kittel_llg.py`, `konstanten.py`, `suszeptibilitaet.py` | Behalten aus HEAD | byteidentisch zu 7c893e8 |
| `physik/fitmodell.py` | Behalten aus HEAD | Ein-Moden-Pfad identisch; Summenmodell wird ungenutzt (Entfernen nur nach Rückfrage, Frage 2) |
| `fit/autowindows.py` | Behalten aus HEAD | identisch bis auf harmlosen Fortschritts-Callback |
| `fit/linescan_fit.py` | Zurück auf 7c893e8-Verhalten | Multi-Lorentz/Summenfit entfernen, Ein-Moden-Fit mit Maske (Korridor) ergänzen |
| `fit/batch.py` | Behalten aus HEAD, teils Entfernen | Fortschritt/Abbruch/`leerer_stapel` behalten; `zweistufig`/`ergaenze_moden`/`n_moden` entfernen; P0-1, P1-4 fixen |
| `fit/fenster_steuerung.py` | Neu (auf HEAD-Basis) | `_fitte_moden_baender` → Korridor-Einzelfit je Mode mit Maskierung |
| `fit/kriterien.py` | Zurück auf 7c893e8 + Neu | Bewertung je gefitteter Linie; neu „Linie nicht aufgelöst", „zu wenige Punkte im Korridor" |
| `fit/auswahl.py`, `gui/auswahl_dialog.py` | Behalten aus HEAD, ROI Entfernen | Jumper/Bereich bleiben; ROI-Knöpfe, Resonanzen-Dropdown raus; P2-3 |
| `fit/parameter.py` | Behalten aus HEAD | `n_moden`/`zweistufig` entfernen (abgeleitet aus Korridoren) |
| `auswertung/moden.py` | Neu (vereinfacht) | Zuordnung = Korridor-Index; Ausreißer je Mode behalten |
| `gui/hauptfenster.py` | Behalten aus HEAD (Grundstruktur) | Entfernen: `spin_moden`, „Hauptmode ↻", ROI, Einzelbeitrags-Kurven; Neu: Korridor-Slots |
| `gui/zonen_panel.py` | Neu | Korridorliste M1..Mn mit Ankerpunkten, Seite, Drag; Ausschlusszonen behalten; kein Fließtext |
| `gui/matrix_ansicht.py` | Behalten aus HEAD + Neu | Modus „band" → „korridor" (Anker setzen/löschen, Grenzen per Drag); Farbplot-Neuzeichnen-Sperre bleibt |
| `gui/fit_ansicht.py` | Behalten aus HEAD | nur Messung + Fit der gewählten Mode; Einzelbeiträge entfernen |
| `gui/auswertung_fenster.py` | Behalten aus HEAD | Kittel/LLG je Mode (eigener Plot je Mode, Feld x / Frequenz y); Hauptmode-Wechsel entfernen; P2-6 |
| `gui/bereichsfit_dialog.py` | Behalten aus HEAD | `moden_spin` entfernen (P1-10) |
| `gui/ausreisser_panel.py` | Behalten aus HEAD | P1-8, P1-9 |
| `gui/arbeiter.py` | Behalten aus HEAD | Drosselung/kein Neuzeichnen bleibt; Live-Vorschau-Totcode entfernen (P2-5) |
| `gui/export_dialog.py`, `persistenz/ergebnis_export.py` | Behalten aus HEAD | Blatt je Mode bleibt; P2-7, P2-11 |
| `persistenz/projekt.py`, `einstellungen.py` | Behalten aus HEAD | Restore mit Korridoren (P0-3); v2-Kompatibilität (P1-12) |
| `gui/farben.py`, `stil.py`, `widgets.py`, `navigator_ansicht.py`, `trace_panel.py`, `verarbeitung_panel.py` | Behalten aus HEAD | geprüft, kein Befund |
| `io/*` | Behalten aus HEAD | byteidentisch |
| Fenstergröße, Dock-Layout, Panels seitlich frei | Behalten aus HEAD | Vorgabe |

## 3. Umsetzungsplan (ein Bug/eine Funktion je Commit)

**Block P0**
1. P0-1: leerer Stapel mit AutoWindow-Fenster (lazy je Frequenz), Panel-Fits mit Nachfenster, Warnung bei Vollsweep. → Regressionsskript.
2. P0-2 Teil 1: Summenfit, zweistufigen Pfad, Kandidatensuche und Einzelbeitrags-Kurven entfernen; Kriterien je gefitteter Linie. → Regressionsskript. (Löst B3/E1–E6/KRIT-1/D-3 auf einen Schlag; Mehr-Moden bis Block K nur über Korridor-Einzelfit in Schritt 7.)
3. P0-2 Teil 2: Kriterium „Linie nicht aufgelöst" (ΔH < 1,5·Feldschritt) und „zu wenige Punkte" (n < Parameter + Marge). → Regressionsskript.

**Block P1**
4. P1-4 „Neu fitten" bestätigt nicht mehr automatisch.
5. P1-5/P1-6 Ausreißer: grauer Punkt toggelt, Pick nur auf sichtbare Punkte, Toleranz aus Punktabstand.
6. P1-8, P1-11 Kleinfixe Ausreißer-Panel / Bewertungs-Dropdown.

**Block K – Moden-Konzept**
7. Datenmodell: `Korridor` (Mode k, Ankerpunkte je Seite, lineare Interpolation über f), einzige Quelle in Hauptfenster; `n_moden` abgeleitet; Projekt v4 mit Migration von Grenzgeraden-Paaren (`mode`) zu Korridoren.
8. Fit je Mode = Einzelfit auf maskierten Punkten im Korridor ∩ grünes Fenster; Startwert aus lokalem Dip im Korridor, sonst Nachbarfrequenz; kein Autofit ohne Korridor (Ausnahme siehe Frage 3). → Regressionsskript.
9. Entfernen: „Res.: n ×", „Hauptmode ↻", ROI, `moden_spin`, Resonanzen-Dropdown, Band-Modus; damit P1-1/2/3/7/10/12, P2-9/10/11.
10. Korridor-Werkzeuge im Farbplot: Anker setzen (2 Klicks je Seite an wenigen Frequenzen), Anker löschen, Grenzen per Drag, Seite wechseln, Korridor entlang der Resonanz kopieren („Jumper", Frage 1).
11. Zonen-Panel neu: Liste M1..Mn, Status (Anker/Punkte), eine sichtbare Funktion, Details im Zusatzpanel, Tooltips statt Text.
12. Restore aus Projekt fittet je Mode im Korridor (P0-3); Ausreißer je Mode auf Korridor-Index (P1-9).
13. Kittel/LLG je Mode: Plot je Mode (Feld x, Frequenz y), Tabellenblatt je Mode, Unsicherheiten wie bisher; Hauptmode-Wechsel raus.
14. Linescan-Panel: nur gewählte Mode als Kurve; andere Moden nur als Korridor-Andeutung im Farbplot.

**Block P2**
15. Bezeichnungen vereinheitlichen (Korridor/Fenster/Ausschlusszone), Kriterien-Chip mit Tooltip, Legenden-Dialog.
16. P2-3, P2-4, P2-5, P2-6, P2-7, P2-8 als Einzelcommits.
17. Abschluss: Regressionsskript → `benchmark_ftf/REGRESSION_<datum>.md`, Kurzbericht, Handbuch-Abbildungen (P2-12 optional).

Regressionsskript: `benchmark_ftf/regression_vergleich.py` (aus H, noch unversioniert); Abnahme = CoFe 290 K und FeCr₂S₄ 100 K innerhalb 1σ zu `BERICHT.md`, HEAD-vs-Referenz elementweise.

## 4. Offene Fragen (vor Umsetzung zu klären)

1. **„Jumper":** Meinst du (a) die Unterabtastung „nur jeden n-ten Punkt" (existiert, Dialogtitel geändert) oder (b) das Zwei-Klick-Werkzeug „Resonanz vorgeben" (Strg+D, Kittel-Gerade als Vorgabe für die Fenstermitten; in 45871fa entfernt, Backend `zentren=` intakt)? Für (b) schlage ich vor, es als „Korridor entlang der Resonanz anlegen" in Block K wiederzubeleben.
2. **`physik/fitmodell.py`:** Das Summenmodell (Multi-Lorentz) wird nach Schritt 2 ungenutzt. Entfernen (Änderung in physik/) oder ungenutzt belassen?
3. **Ein-Moden-Fall ohne Korridor:** Konzept-Punkt 6 sagt „ohne Korridor kein Autofit". Vorschlag: Ohne Korridor gilt M1 = grünes AutoWindow-Fenster (exakt 7c893e8-Verhalten, FTF-Regression bleibt erfüllt); Korridore nur nötig, sobald mehr als eine Mode gewünscht ist. Einverstanden?
4. **P0-1, Variante:** AutoWindow beim Laden lazy je Frequenz berechnen (grüne Grenzen sofort auf der Mode, Kosten Sekunden beim ersten Anzeigen) oder nur Nachfenster-Durchgang bei Panel-Fits (minimal, aber erste Anzeige weiter Vollsweep)? Empfehlung: lazy je Frequenz.
5. **Ausgeblendete Problemfits (P1-6):** Sollen ausgeblendete Punkte gar nicht markierbar sein (dann Hinweis) oder beim Klick temporär eingeblendet werden?
6. **Kriterien-Chip:** Vorschlag vier Gruppen A (Amplitude/Signal), P (Parameter/α), F (Fenster/Punkte), U (Unsicherheit) als Buchstaben mit Farbe, Zahlen im Tooltip. Einverstanden oder andere Gruppierung?
7. **Regressions-venv:** Die Referenz-venv hat numpy 2.5.2/scipy 1.18.1, HEAD numpy 2.4.6/scipy 1.17.1. Für den 1σ-Vergleich beide auf denselben Stand bringen (Referenz auf HEAD-Stand)?

## 5. Stand der Umsetzung (2026-09-03, Sitzung wegen Token-Limit vorzeitig beendet)

Branch `fix/rueckbau-7c893e8`, nicht auf main gemergt.

| Schritt | Status |
|---|---|
| P0-1 Fits ohne Auto-Fit im AutoWindow-Fenster, Nachfenster, Vollsweep-Warnung | **fertig** (Commit 57867f5, Regression bitgleich) |
| P0-2 Summenfit/zweistufiger Pfad/Multi-Lorentz entfernt; Kriterien je Linie + „zu wenige Punkte“/„Linie nicht aufgelöst“ | **fertig** (dieser Commit) |
| Block K Kern: `fit/korridor.py` (Anker, lineare Interpolation), `fitte_mode`/`fitte_korridor` (Einzelfit je Mode nur im Korridor, Nachbar-Startwert als Rückfall, Nachfenster im Korridor, Jumper), `StapelErgebnis.nebenmoden`, Projekt v4 mit Migration v3-Grenzgeraden → Korridore, Restore je Mode im Korridor (P0-3), Excel-Blatt je Mode | **fertig** |
| Block K GUI: Korridorliste als einzige Moden-Quelle (P1-1/2/3/10/12 damit hinfällig), Werkzeuge „Korridor anlegen“ (2 Klicks ± Breite), „Anker setzen“ (Klick), Anker-Drag im Farbplot, Anker-Details einklappbar, „Korridor fitten …“ (Dialog: Frequenzbereich, Modus, Jumper), Linescan-Panel zeigt gewählte Mode (Grenzen ziehen = Anker setzen), Kittel/LLG je Mode (Mode 1..n / alle), ROI/„Res.: n ×“/„Hauptmode ↻“/Band-Werkzeug entfernt (P1-7, P2-10/11) | **fertig, GUI nur headless/offscreen geprüft** |
| P1-8 Ausreißer-Panel Zeilentausch | fertig (in diesem Commit) |
| P2-4 Zone entfernen ohne Auswahl | fertig (in diesem Commit) |
| Tests: veraltete Module nach `tests/veraltet/` (Grenzgeraden, Summenfit, ROI); neue `tests/test_korridor.py`; Suite 176 grün | fertig |

**Offen (nach Token-Reset, Reihenfolge wie Plan §3):**
1. P1-4 „Neu fitten“ bestätigt nicht mehr automatisch (`bestaetigen=None` → Kriterien, wenn Fenster unverändert).
2. P1-5/P1-6 Ausreißer: Klick auf grauen Punkt nimmt wieder auf; ausgeblendete Problemfits nicht markierbar → Hinweis in Statuszeile.
3. P1-11 Bewertungs-Dropdown „ignorieren“ toggelt.
4. P2-1/P2-13 Bezeichnungen und Texte: Reste „Grenzgeraden/Band/Zonen & Grenzgeraden“ in Tooltips, Menü (`akt_zonen_panel`), Hilfe-Dialog, Docstrings von hauptfenster.py/matrix_ansicht.py; Fließtext in `auswahl_dialog`, Kittel-Fenster weiter kürzen.
5. P2-2 Kriterien-Chip (A/P/F/U) mit Tooltip statt Textliste.
6. P2-3, P2-5, P2-6, P2-7, P2-8, P2-12.
7. Korridor-GUI am Bildschirm prüfen (Drag-Handhabung, Farben, Dock-Breite), neue GUI-Tests für Korridor-Werkzeuge (Ersatz für `tests/veraltet/`).
8. Handbuch/Doku (docs/, handbuch/) auf Korridor-Konzept aktualisieren.
9. Phase 4: `benchmark_ftf/REGRESSION_<datum>.md`, Kurzbericht, Freigabe vor Merge.

## 6. Nutzer-Feedback nach Test von V0.1.68 (2026-09-03, Datensätze testdata-n-lorentz 19.5–22.5 GHz und 28.5–31.5 GHz)

Positiv: Korridor-Fit ist schnell und nahezu eindeutig, auch bei schwierigen Daten (vermiedene Kreuzung zweier Moden); Panel ist übersichtlich. Abzuarbeiten nach dem Token-Reset, vor den P2-Punkten aus §5:

| Nr | Befund | Soll |
|---|---|---|
| F-1 | „Korridor fitten …“ für M2: scheinbar passiert nichts; erst nach erneutem Auswählen der Zeile erscheinen die Punkte – und dann **grau und eckig** (Raute wie „ignoriert“) | Nach dem Korridor-Fit sofort Overlay/Liste/Linescan aktualisieren und M2 auswählen; Nebenmoden-Punkte rund in der Mode-Farbe (M2 violett …), Status-Farben wie bei M1; „ignoriert“ bleibt grau |
| F-2 | Auto-Fit-Dialog vorbelegt mit falschem Frequenzbereich (25,5–25,5 GHz → 0 Linescans; stammt aus vorherigem Datensatz/Zoom) | Standard = ganzer Bereich, keine Begrenzung; letzte Auswahl nur übernehmen, wenn sie im Datenbereich liegt (P2-3 mit einschließen) |
| F-3 | Spinbox „± 10 mT“ (Korridorbreite): Klick auf Pfeile hoch/runter wirkt nicht zuverlässig | Muss funktionieren (RuhigeSpinBox-Pfeile prüfen; ggf. auch andere Spinboxen) |
| F-4 | Nahe Dips (Zeichnung): **Hard Crop** durch den Nutzer – eine Lorentz links, eine rechts der Grenze, jede über alle Punkte ihrer Seite gefittet, Grenze strikt. V1.66 konnte das im Fit, aber die Grenzgeraden-Grenzen wurden im Linescan-Fenster ignoriert | Korridorgrenzen = harte Grenzen in jedem Fit (Auto-Fit, Korridor-Fit, Nachfit) und im Linescan-Fenster sichtbar/ziehbar; Grenze im Linescan-Fenster ziehen → Anker → schräge Korridorgrenze im Farbplot (bereits so gebaut, am Bildschirm verifizieren) |
| F-5 | Vorgabe an den Auto-Fit: „hier sind zwei (drei) Resonanzen“ als harte Randbedingung; nur danach suchen; dritte weiter entfernt ebenfalls per Hard Crop | Auto-Fit bei vorhandenen Korridoren: alle Korridore nacheinander fitten (M1..Mn), keine freie Suche außerhalb; Korridor-Anlage einfach halten (Tutor: eine globale Grenze je Mode, innerhalb jede gewünschte Mode fitten) |
| F-6 | Jumper aktiv: Pfeiltasten im Farbplot springen auch auf nicht gefittete Frequenzen (Linescan-Panel zeigt ungefittete Punkte) | Option „ungefittete überspringen“ (Standard an, wenn Jumper > 1) |
| F-7 (Beobachtung) | Auto-Fit ohne Korridor an der vermiedenen Kreuzung (28,5–31,5 GHz): AutoWindow springt zwischen den Ästen, Fenster 247 Punkte, viele Problemfits | Hinweis/Empfehlung im Protokoll: bei mehreren Moden Korridore anlegen; Fensterbreite gegenüber Sweep deckeln |

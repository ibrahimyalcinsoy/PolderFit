# Bereich F – Moden-State (HEAD e3b1ea7 / V0.1.66) gegen Referenz 7c893e8

Alle Pfade relativ zu `/home/ibrahim/Dokumente/Ananas`. Referenz-Worktree:
`/home/ibrahim/Dokumente/polderfit-ref` (7c893e8).
Reproduktionsskripte: `…/scratchpad/bugs/t1.py … t5.py` (headless, `QT_QPA_PLATFORM=offscreen`).

## 0. Ausgangslage: 7c893e8 kannte keinen Moden-State

In 7c893e8 gibt es **kein** Moden-Konzept – weder `n_moden`, noch `moden`,
noch `Grenzgerade.mode`, noch `polderfit/auswertung/moden.py`, noch eine
Moden-Auswahl in der GUI:

```
$ cd ../polderfit-ref && grep -rn "n_moden\|hauptmode" --include=*.py polderfit/
(keine Treffer)
$ ls polderfit/auswertung/       # __init__.py  uebersicht.py   – kein moden.py
$ sed -n '324,329p' polderfit/fit/fenster_steuerung.py
    b1: float
    f1: float          # Hz
    b2: float
    f2: float
    gruen_positiv: bool = True      # <- kein 'mode'-Feld
```

Ein Linescan → ein `FitErgebnis` → ein Kittel/LLG-Fit. Es gab genau **eine**
Wahrheit. Der gesamte in diesem Bericht analysierte Zustand ist zwischen
7c893e8 und HEAD in vier Commits neu entstanden
(`798b794`, `13ca321`, `0807c7c`, `e41a560`; +3576/−764 Zeilen in den
betroffenen Dateien). „Diff zu 7c893e8" heißt bei jedem Befund unten deshalb:
*die Größe existiert in der Referenz nicht* – ein „Zurück auf Referenz" ist
nur als Feature-Rücknahme möglich, nicht als Zeilen-Revert.

---

## 1. Tabelle aller Moden-State-Orte

| # | Größe / Datenstruktur | Definition | Besitzer | Schreiber (W) | Leser (R) |
|---|---|---|---|---|---|
| S1 | `PhysikParameter.n_moden: int` | `fit/parameter.py:63` | `Hauptfenster._physik` + Einstellungsdatei | `hauptfenster.py:1959` (`_setze_n_moden`), `:1929` (`_physik_uebernehmen`) | `:284`, `:1259`, `:1842` (`_leerer_stapel`), `:1864` (Auto-Fit-Dialog-Vorbelegung), `:2044` |
| S2 | `StapelErgebnis.n_moden: int` | `fit/batch.py:119` | Stapel (Fit-Ergebnis) | `hauptfenster.py:1945`, `:1963`; `batch.py:334` (`fitte_alle`), `:501` (`leerer_stapel`); `projekt.py:135` (Restore) | `batch.py:555` (Default von `fitte_neu`), `fenster_steuerung.py:415,470,540`, `hauptfenster.py:1066,1217,1247,2083`, `auswertung_fenster.py:262`, `ausreisser_panel.py:87`, `projekt.py:70` |
| S3 | `Hauptfenster.spin_moden` („Res.: n ×") | `hauptfenster.py:280-287` | nur das Widget | `:284`, `:1932`, `:1965` | `:2328` (`_grenzen_geaendert`), `:2351` (`_neu_fitten`) — **kein `valueChanged`-Connect** |
| S4 | `ZonenPanel._n_moden: int` | `zonen_panel.py:54` | Panel | `zonen_panel.py:216` (`setze_n_moden`) | `:205,245,254,262,268,291,295,308` |
| S5 | `ZonenPanel.n_moden_combo` („Resonanzen je Linescan") | `zonen_panel.py:69-78` | Panel-Widget | `:220` | `:225` → Callback `Hauptfenster._setze_n_moden` |
| S6 | `Grenzgerade.mode: int` (Band-Nr.) | `fit/fenster_steuerung.py:353` | `Hauptfenster._grenzgeraden` | `hauptfenster.py:1062` (neue Gerade), `:1094` (Band), `:1153` (`_gerade_mode`); `projekt.py:186` (Restore) | `fenster_steuerung.py:416,444,541`, `auswertung/moden.py:56`, `zonen_panel.py:204,245,307`, `hauptfenster.py:1262` |
| S7 | `FitErgebnis.n_moden`, `.moden[]`, `.fitkurven_moden[]` | `fit/linescan_fit.py:113-118` | Fit-Ergebnis (Position, **nicht** Zweig!) | `linescan_fit.py:478`, `:634`, `:650` (`hauptmode_wechseln`) | `fit_ansicht.py:119-128,163`, `hauptfenster.py:2139,2155-2165,2186,2307`, `auswertung/moden.py`, `kriterien.py:130` |
| S8 | `StapelErgebnis.ausreisser_moden: list[(index, Zweig)]` | `fit/batch.py:136` | Stapel | `hauptfenster.py:2799,2820,2837`; `projekt.py:180` | `moden.py:157`, `auswertung_fenster.py:279`, `ausreisser_panel.py:85`, `hauptfenster.py:2471,2476,2500` |
| S9 | `ModenZuordnung` (Zweig je Resonanz) | `auswertung/moden.py:69-104` | **transient**, bei jedem Aufruf neu | – | erzeugt an `hauptfenster.py:2456` (mit Geraden), `auswertung_fenster.py:262` (mit Geraden), `ausreisser_panel.py:87` (**ohne** Geraden), `moden.py:159,190` (Default ohne Geraden) |
| S10 | `AuswertungsFenster.mode_combo` / `_moden_aktiv` / `_zuordnung` / `_reihen` | `auswertung_fenster.py:121,99,98,97` | Fenster (Ansichtszustand) | `_combo_befuellen:191-220`, `aktualisiere:262-280` | `mode_gewaehlt:178`, `exportiere:523` |
| S11 | `AuswahlDialog.moden_combo` + `chk_zweistufig` | `auswahl_dialog.py:175,186` | Dialog | – | zurück über `hauptfenster.py:1877` (`_setze_n_moden`) |
| S12 | `BereichsFitDialog.moden_spin` | `bereichsfit_dialog.py:89` | Dialog | – | zurück über `hauptfenster.py:1258-1260` (**nur anheben**) bzw. `:2092` (**anheben und absenken**) |
| S13 | `StapelErgebnis.zweistufig` / `PhysikParameter.auto_fit_zweistufig` | `batch.py:120`, `parameter.py:64` | Stapel / Einstellungen | `batch.py:338ff`, `hauptfenster.py:1878-1880` | `hauptfenster.py:2056` |
| S14 | `MatrixAnsicht._res_nebenmoden` | `matrix_ansicht.py:139` | Farbplot-Overlay | `hauptfenster.py:2155-2165` (**nach Position in `moden`**) | `matrix_ansicht.py:584-588` |

### Drei konkurrierende Moden-Nummerierungen

1. **Position in `FitErgebnis.moden`** (S7) – Reihenfolge = Signalhöhe/Startwert,
   kann je Linescan den Zweig wechseln (so auch dokumentiert in
   `auswertung/moden.py:6-8`). Genutzt von: Farbplot-Nebenmoden (S14),
   `fit_ansicht.py:119-128` („Mode 1 (Hauptmode)", „Mode 2"), Tooltip
   (`hauptfenster.py:2139`), Excel-Spalten `*_2`, `*_3` (`linescan_fit.py:224`).
2. **Zweig-Nummer aus `ModenZuordnung`** (S9) – Band bzw. Feldordnung. Genutzt
   von: Auswertungsfenster, `ausreisser_moden` (S8), Blatt *Global*,
   Blätter `Parameter_M<k>`.
3. **Band-Nummer `Grenzgerade.mode`** (S6) – bestimmt, wo der Fit die Mode
   suchen darf.

Für denselben Linescan können 1 und 2 auf verschiedene Resonanzen zeigen
(nachgewiesen in t4.py, i=11: `moden = [3.3449, 3.339]`, d. h. Position 1 liegt
**unter** Position 0, während bei i=10 `[3.339, 3.3502]` gilt – die Nebenmoden-
Kurve im Farbplot springt dort den Zweig, die Kurve „Mode 2" im Kittel-Fenster
nicht).

---

## 2. Datenfluss (Text-Diagramm)

```
                       Einstellungsdatei (physik.n_moden)
                                    │
                                    ▼
  AuswahlDialog.moden_combo ──►  _setze_n_moden(n)  ◄── BereichsFitDialog.moden_spin
  (Auto-Fit, hf:1877)            (hf:1955-1969)         (Rechteck-Fit hf:2092  –  anheben UND absenken)
  ZonenPanel.n_moden_combo ──►        │                 (Grenzgeraden-Fit hf:1258-1260 – NUR anheben)
  (zp:227 → hf:1955)                  │
                                      ├──► self._physik.n_moden      (S1)
                                      ├──► self.stapel.n_moden       (S2)
                                      ├──► self.spin_moden.setValue  (S3)  ← überschreibt Nutzereingabe
                                      ├──► zonenpanel.setze_n_moden  (S4/S5)
                                      └──► _auswertung_nachziehen()

  ParameterDialog (Strg+P) ──► _physik_uebernehmen (hf:1927-1953)
  Projekt laden (hf:2958)   ──►      ├──► self._physik.n_moden   (S1)
                                     ├──► self.spin_moden        (S3)
                                     ├──► self.stapel.n_moden    (S2)
                                     └──► ✗ ZonenPanel NICHT     ← BUG F-1

  spin_moden („Res.: n ×")  ──► ✗ kein Signal ──► nur gelesen in
                                _neu_fitten/_grenzen_geaendert   ← BUG F-2

  Fit-Pfad Modenzahl:
    Auto-Fit          : physik.n_moden           (hf:2044)
    Neu fitten/Grenzen: spin_moden.value()       (hf:2328/2351)
    Rechteck-Fit      : stapel.n_moden           (fitte_bereich → fitte_neu Default)
    Grenzgeraden-Fit  : zonenpanel.n_moden_effektiv()  (hf:1213) = max(clamp(g.mode, 1, panel._n_moden))
    Projekt-Restore   : zeile["n_moden"] je Fit  (projekt.py:167)

  Auswertungs-Pfad (Zweige):
    Auswertungsfenster : zuordnung_moden(erg, self._hole_geraden(), stapel.n_moden, feld_bereich)
    Blatt Global/Export: zuordnung_moden(erg, self._grenzgeraden,  stapel.n_moden, feld_bereich)
    Ausreißer-Panel    : zuordnung_moden(erg, KEINE Geraden,       stapel.n_moden)   ← BUG F-5
    Farbplot-Nebenmoden: gar keine Zuordnung, Position in erg.moden                 ← BUG F-6
```

**Sechs Stellen schreiben die Modenzahl, fünf Fit-Pfade lesen fünf verschiedene
Quellen davon.** Das ist der Kern des Problems, nicht ein einzelner Bug.

---

## 3. Befunde

### F-1 (schwer) Projekt laden / Strg+P lässt das Grenzgeraden-Panel auf altem Stand → Grenzgeraden-Fit verweigert die Arbeit

**Symptom.** Nach „Projekt laden" (oder nach Auto-Sicherung wiederherstellen,
oder nach einem Strg+P-Dialog) steht im Panel *Zonen/Grenzgeraden* weiter
„Resonanzen je Linescan: 1", obwohl Projekt und Linescan-Panel 2 zeigen. Das
Band-Werkzeug und der Knopf „Mode ändern" sind unsichtbar, die Geradenliste
zeigt keine `M1 ·`/`M2 ·`-Präfixe, und „Grünen Bereich fitten …" bricht mit
*„Grenzgeraden-Fit: kein Linescan im grünen Bereich. Die grünen Seiten der
Geraden schneiden sich in keinem Linescan …"* ab, obwohl die Bänder korrekt
geladen sind.

**Reproduktion.** `t2.py` (Projekt-Rundlauf mit 2 Bändern, 629 Linescans):

```
gespeichert n_moden: 2  physik.n_moden: 2  geraden modes: [1, 1, 2, 2]
NACH LADEN: stapel.n_moden = 2 | physik.n_moden = 2 | spin = 2
            | panel._n_moden = 1 | panel-combo = 1
n_moden_effektiv() = 1  (erwartet 2)
zaehle_abgedeckt(n_eff) = 0        <-- GUI bricht hier ab
zaehle_abgedeckt(2)     = 208      <-- korrekt wären 208 Linescans
Band-Werkzeug sichtbar: False
Liste: ['(3.294', '(3.334', '(3.364', '(3.404']   (ohne M1/M2-Präfix)
```

Klickfolge in der GUI: Projekt mit 2 Bändern laden → Panel „Zonen
Grenzgeraden" öffnen → „Grünen Bereich fitten …".

**Datei:Zeile / Root Cause.**
`polderfit/gui/hauptfenster.py:1927-1953` (`_physik_uebernehmen`) setzt S1, S3
und S2, ruft aber **nicht** `self.zonenpanel.setze_n_moden(...)`:

```python
1931        self.spin_moden.blockSignals(True)
1932        self.spin_moden.setValue(max(1, int(parameter.n_moden)))
1933        self.spin_moden.blockSignals(False)
…
1945            st.n_moden = max(1, int(parameter.n_moden))
              # <- hier fehlt: self.zonenpanel.setze_n_moden(...)
```

`_projekt_laden.bei_fertig` (`:2958`) ruft ausschließlich
`_physik_uebernehmen`, nie `_setze_n_moden` (das als einziges auch das Panel
synchronisiert, `:1967`). Die Folge kaskadiert über `ZonenPanel._mode_von`
(`zonen_panel.py:245`), das jede Geraden-Mode auf `self._n_moden` = 1 klemmt →
`n_moden_effektiv()` = 1 (`:250`) → `hauptfenster.py:1213` fittet einmodig →
`zaehle_abgedeckt(..., n_moden=1)` (`fenster_steuerung.py:417`) prüft den
Schnitt **aller** Geraden statt der Bänder und findet 0.

Zusätzlich ist der Abbruchtext falsch: der Zweig
`hauptfenster.py:1217 if stapel.n_moden == 1 and len(geraden) >= 3` greift
nicht (S2 = 2), also erscheint der irreführende Ratschlag „Seite per
Doppelklick tauschen".

**Diff zu 7c893e8.** Existiert dort nicht (kein Panel-Modenzustand, kein
`Grenzgerade.mode`, `zaehle_abgedeckt` ohne `n_moden`).

**Fixvorschlag (Fix im aktuellen Code).** Eine einzige Setter-Route erzwingen:
`_physik_uebernehmen` ruft am Ende `self._setze_n_moden(parameter.n_moden)`
(bzw. `self.zonenpanel.setze_n_moden(...)`), und `_projekt_laden.bei_fertig`
ruft nach `self.stapel = stapel` explizit `self._setze_n_moden(stapel.n_moden)`.
Strukturell besser: `ZonenPanel._n_moden` ersatzlos streichen und die Modenzahl
aus der Bänderliste ableiten (siehe §5).

**Risiko.** Gering (reines Sync-Problem). Achtung auf die Reihenfolge:
`_physik_uebernehmen` läuft in `bei_fertig` **vor** `self.stapel = stapel`
(`:2958` vs. `:2962`) und schreibt `st.n_moden` daher noch auf den **alten**
Stapel.

---

### F-2 (schwer) „Res.: n ×" ist eine dritte, unverbundene Wahrheit

**Symptom.** Der Spin „Res.: n ×" im Linescan-Panel wirkt **nur** auf
„Neu fitten" und auf das Ziehen der grünen Grenzen. Er ändert weder die
Einstellung, noch den Stapel, noch das Panel – und wird beim nächsten Dialog
kommentarlos zurückgesetzt. Umgekehrt fittet der Nutzer damit einzelne
Linescans mit einer anderen Modenzahl als der Rest des Datensatzes, ohne dass
das irgendwo sichtbar oder speicherbar wäre.

**Reproduktion.** `t1.py`:

```
start:                 physik 1  spin 1  panel 1
nach spin=3:           physik 1  panel 1  combo 1   band_box sichtbar False
nach panel-combo=2:    physik 2  spin 2  panel 2   <-- Spin-Eingabe 3 verworfen
nach _physik_uebernehmen(4): physik 4 spin 4 panel 2
```

Klickfolge: „Res.: n ×" auf 3 stellen → „Neu fitten" (fittet 3 Moden) →
Panel-Auswahl anfassen oder Strg+P → Spin steht wieder auf dem globalen Wert,
der 3-Moden-Fit bleibt als Einzelfall im Stapel stehen.

**Datei:Zeile / Root Cause.** `hauptfenster.py:280-287` legt den Spin an;
es gibt **kein** `self.spin_moden.valueChanged.connect(...)` (verifiziert:
`grep -n spin_moden hauptfenster.py` → nur `setValue`/`value()`). Gelesen wird
er an `:2328` und `:2351`; geschrieben an `:1932` und `:1965`.

**Diff zu 7c893e8.** In der Referenz gibt es weder Spin noch Modenzahl; die
Steuerleiste des Linescan-Panels hatte nur Zurück/Weiter/Problemfit/Neu fitten.

**Fixvorschlag (Entfernen).** Der Spin dupliziert „Resonanzen je Linescan"
ohne Synchronisation und ohne eigenen fachlichen Auftrag. Ersatzlos streichen;
`_neu_fitten`/`_grenzen_geaendert` sollen `self.stapel.n_moden` verwenden
(= `fitte_neu`-Default, also einfach `n_moden` nicht übergeben). Falls ein
Einzel-Override erwünscht bleibt, müsste er mindestens per
`valueChanged → _setze_n_moden` an die eine Wahrheit gehängt werden – dann ist
er aber nur noch eine zweite Anzeige derselben Zahl.

**Risiko.** Sehr gering; nur das Verhalten „diesen einen Linescan mit anderer
Modenzahl fitten" entfällt (nicht speicherbar, also ohnehin flüchtig).

---

### F-3 (schwer) „Hauptmode ↻" überlebt Speichern/Laden nicht – die Projektdatei ist danach in sich widersprüchlich

**Symptom.** Nach `Hauptmode ↻` zeigt alles (Farbplot, Tooltip, Excel, Kittel
in der Hauptmode-Ansicht) die getauschte Resonanz. Projekt speichern → laden →
der Tausch ist weg, ohne Meldung. Die gespeicherte JSON-Zeile enthält den
getauschten `B_res_T`; der Restore rechnet aber neu und liefert den anderen
Wert – Datei und wiederhergestellter Zustand widersprechen sich.

**Reproduktion.** `t3.py`:

```
Fit 0: n_moden 2  B_res(haupt) 3.33121  moden [3.33121, 3.35073]
nach Hauptmode-Wechsel: B_res 3.35073   moden [3.35073, 3.33121]
gespeicherte Zeile 0 B_res_T: 3.3507269089509926
   | Zusatzspalten fuer Mode 2 vorhanden: False
nach Laden: B_res 3.33121  moden [3.33121, 3.35073]
Hauptmode-Wechsel erhalten? False
```

**Datei:Zeile / Root Cause.** `persistenz/projekt.py:79-82` speichert
`e.als_zeile(hauptmode_nur=True)` – die Moden-Zusatzspalten werden bewusst
weggelassen. `stelle_stapel_wieder_her` (`projekt.py:166-168`) rechnet jeden
Fit über `fitte_neu(..., n_moden=zeile["n_moden"])` neu; `fitte_linescan_multi`
sortiert die Moden dabei wieder nach Signalhöhe
(`linescan_fit.py:620-622: haupt = argmax(hoehe)`). Der Tausch existiert nur in
der Objekt-Reihenfolge und wird nicht mitgeschrieben.

**Fixvorschlag.** Entweder die Mode-Reihenfolge persistieren (z. B.
`"moden_reihenfolge": [...]` je Fit und nach dem Restore `hauptmode_wechseln`
anwenden) – oder, deutlich besser, **die Funktion entfernen** (§4).

**Risiko des Entfernens.** Gering, weil die Funktion heute ohnehin nicht
haltbar ist: sie überlebt weder Speichern noch irgendein erneutes Fitten
desselben Linescans.

---

### F-4 (schwer) Band-Fits sind nicht reproduzierbar: der Restore ignoriert die Bänder

**Symptom.** Ein mit Bändern gefitteter Datensatz sieht nach Projekt
speichern → laden anders aus; Resonanzfelder verschieben sich um mehrere mT,
teilweise wechselt die Mode-Reihenfolge.

**Reproduktion.** `t4.py` (20 Linescans, 2 Bänder, `fitte_geraden_bereich`,
dann Rundlauf):

```
Band-Fit: 20 gefittet, 0 uebersprungen
abweichende Linescans nach Restore: 14 von 20
  i=0   vorher (3.323,  [3.323, 3.343])    nachher (3.31994, [3.31994, 3.33658])
  i=10  vorher (3.339,  [3.339, 3.35019])  nachher (3.34411, [3.34411, 3.36123])
  i=11  vorher (3.3449, [3.3449, 3.339])   nachher (3.34642, [3.34642, 3.36363])
```

**Datei:Zeile / Root Cause.** Der Band-Fit übergibt Startwerte je Band **und**
harte Schranken je Mode:

```python
# fit/fenster_steuerung.py:488-495
starts = startwerte_in_bereichen(beschnitten.feld, beschnitten.s21, …, baender, …)
ergebnis = fitte_neu(stapel, i, feld_unten=fenster[0], feld_oben=fenster[1],
                     startwerte=starts, n_moden=n, bereiche=baender,
                     bestaetigen=False)
```

Der Restore kennt weder `startwerte` noch `bereiche`:

```python
# persistenz/projekt.py:166-168
ergebnis = fitte_neu(stapel, i, bestaetigen=False,
                     n_moden=(int(n_moden) if n_moden else None))
```

Das gespeicherte Fenster ist die **Hülle der Bänder plus 50 % Rand**
(`fenster_steuerung.py:438-459`), also deutlich weiter als die Bänder – der
freie Mehrmodenfit darin konvergiert anderswo. Die Grenzgeraden liegen in der
Projektdatei (`projekt.py:77`), werden aber nur an die GUI zurückgegeben
(`hauptfenster.py:2966`), nie an `stelle_stapel_wieder_her`.

**Fixvorschlag (Fix im aktuellen Code).** `stelle_stapel_wieder_her` einen
Parameter `grenzgeraden` geben und je Index über
`_moden_baender(geraden, n, ls.frequenz, lo, hi)` + `startwerte_in_bereichen`
denselben Fit wie `_fitte_moden_baender` rechnen; alternativ die
Mehrmoden-Parameter direkt speichern (`als_zeile(hauptmode_nur=False)`) und den
Fit gar nicht neu rechnen.

**Risiko.** Mittel – berührt den zentralen Restore-Pfad; Version-2/3-Dateien
ohne Bänder müssen unverändert weiterlaufen.

---

### F-5 (mittel) Ausreißer-Panel verwendet eine andere Zuordnungsregel als Auswertungsfenster und Export

**Symptom.** Ein im Kittel-Fenster für „Mode 2" ausgeschlossener Punkt wird im
Ausreißer-Panel mit dem `B_res` der *anderen* Resonanz beschriftet, sobald die
Band-Reihenfolge nicht der Feldordnung entspricht (Nutzer zeichnet das Band um
die starke, obenliegende Mode zuerst → M1 liegt über M2).

**Reproduktion.** `t5.py`:

```
Regel Auswertungsfenster/Export: band  labels [1, 2] -> position(Mode 1) = 0
Regel Ausreisser-Panel        : feld  labels [2, 1] -> position(Mode 1) = 1
gleiche Position? False
```

**Datei:Zeile / Root Cause.** `gui/ausreisser_panel.py:87`

```python
zuordnung = zuordnung_moden(stapel.ergebnisse, n_moden=getattr(stapel, "n_moden", 1))
```

– ohne `geraden` und ohne `feld_bereich`, während `hauptfenster.py:2456`
(`_moden_zuordnung`) und `auswertung_fenster.py:262` beides übergeben.
`zuordnung_moden` schaltet ohne Geraden auf `regel="feld"`
(`auswertung/moden.py:116-118`).

**Fixvorschlag.** `AusreisserPanel` eine `hole_zuordnung`-Callback bzw. die
fertige `ModenZuordnung` vom Hauptfenster (`_moden_zuordnung()`) übergeben –
die Zuordnung darf nur an EINER Stelle berechnet werden.

**Risiko.** Sehr gering (reine Anzeige; `ausreisser_moden` selbst bleibt korrekt).

---

### F-6 (mittel) Farbplot-Nebenmoden und Linescan-Panel nummerieren nach Listenposition, das Kittel-Fenster nach Zweig

**Symptom.** Die zusätzliche Resonanzkurve im Farbplot („Weitere Resonanzen
(Nebenmoden) anzeigen") und die Legende im Linescan-Panel („Mode 2") springen
zwischen den Dispersionszweigen, während „Mode 2" im Kittel-Fenster ein
sauberer Zweig ist. Dieselbe Beschriftung meint zwei verschiedene Dinge.

**Datei:Zeile / Root Cause.**
`hauptfenster.py:2155-2165` baut die Nebenmoden strikt aus `e.moden[k]`:

```python
2160                nebenmoden.append(np.array([
2161                    e.moden[k]["B_res"] if (e.gefittet and len(e.moden) > k) else np.nan
2162                    for e in st.ergebnisse], dtype=float))
```

Ebenso `gui/fit_ansicht.py:119-128` (`label=f"Mode {k+1}"`) und der Tooltip
`hauptfenster.py:2139-2141`. Dass die Position kein Zweig ist, steht wörtlich
im Modulkopf von `auswertung/moden.py:6-8`. Nachweis für den Zweigwechsel:
`t4.py`, i=10 `[3.339, 3.3502]` vs. i=11 `[3.3449, 3.339]`.

**Fixvorschlag.** Overlay, Fit-Ansicht, Tooltip und die Excel-Spalten `*_k`
über `_moden_zuordnung()` umsortieren (bzw. `ergebnisse_fuer_mode` nutzen),
sodass „Mode k" überall derselbe Zweig ist.

**Risiko.** Gering–mittel (Anzeige und Spaltenbelegung im Export ändern sich;
letzteres ist eine Formatänderung).

---

### F-7 (mittel) Der Rechteck-Fit senkt die globale Modenzahl und entwertet damit stillschweigend alle Bänder

**Symptom.** Ein Rechteck-Nachfit („Bereich neu fitten") mit „Resonanzen je
Linescan: 1" im Dialog setzt die globale Einstellung auf 1. Alle vorhandenen
Bänder M2, M3 … gelten danach als Mode 1; der nächste Grenzgeraden-Fit ist
einmodig und findet in der Regel gar keinen grünen Bereich mehr. Die
`Grenzgerade.mode`-Werte bleiben erhalten, sodass ein Zurückstellen der Zahl
alles wiederherstellt – der Zustand ist also unsichtbar, nicht zerstört.

**Reproduktion.** `t5.py`, Teil (a):

```
n_moden=2  -> n_moden_effektiv 2  mode_neu 2
n_moden=1  -> n_moden_effektiv 1  mode_neu 1 | Geraden-Modes unveraendert: [1,1,2,2]
zurueck auf 2 -> n_moden_effektiv 2
```

**Datei:Zeile / Root Cause.** `hauptfenster.py:2092`

```python
        self._setze_n_moden(dialog.n_moden())        # Rechteck-Fit: hebt UND senkt
```

gegenüber dem bewusst asymmetrischen Grenzgeraden-Fit `:1258-1260`

```python
        n_fit = max(1, int(dialog.n_moden()))
        if n_fit > self._physik.n_moden:
            self._setze_n_moden(n_fit)   # nur anheben - die Einstellung ist die Obergrenze
```

Zwei Dialoge mit derselben Beschriftung, zwei verschiedene Semantiken. Wirksam
wird die Absenkung über die Klemmung `ZonenPanel._mode_von`
(`zonen_panel.py:243-245`).

**Fixvorschlag.** Entweder beide Dialoge auf „nur anheben" vereinheitlichen,
oder – konsequenter – die Modenzahl nicht mehr aus lokalen Nachfit-Dialogen
schreiben lassen (§5).

**Risiko.** Gering.

---

### F-8 (mittel) Projektdateien der Version 2 (Stand 7c893e8) hinterlassen einen inkonsistenten Moden-Zustand

**Symptom.** Ein mit 7c893e8 (oder HEAD vor `798b794`) gespeichertes Projekt
enthält keinen `physik`-Block. Beim Laden bleibt `self._physik.n_moden` auf dem
Wert aus der Einstellungsdatei (z. B. 3) und der Spin zeigt 3, während
`stapel.n_moden` = 1 ist.

**Datei:Zeile / Root Cause.** `hauptfenster.py:2958`

```python
            if isinstance(daten.get("physik"), dict):
                self._physik_uebernehmen(PhysikParameter.aus_dict(daten["physik"]), leise=True)
```

Ohne `physik`-Block passiert nichts; `projekt.py:135`
`n_moden=max(1, int(daten.get("n_moden", 1)))` setzt den Stapel dagegen auf 1.

**Kompatibilität in die andere Richtung** (geprüft an
`../polderfit-ref/polderfit/persistenz/projekt.py:75-121`): Version-3-Dateien
lassen sich mit 7c893e8 öffnen – alle unbekannten Schlüssel (`n_moden`,
`ausreisser_moden`, `grenzgeraden`, `physik`, `verarbeitung`) laufen durch
`.get(...)` ins Leere. Die Moden-Information geht dabei still verloren, und
zusätzlich fittet die Referenz auch die Platzhalter (`gefittet=False`) neu,
weil sie diesen Fall nicht kennt.

**Fixvorschlag.** Beim Laden immer `self._setze_n_moden(stapel.n_moden)` als
letzten Schritt (deckt F-1 und F-8 gemeinsam ab).

**Risiko.** Sehr gering.

---

### F-9 (klein) `mode_neu()` deckelt neue Bänder an der eingestellten Modenzahl

**Datei:Zeile.** `zonen_panel.py:283-295`

```python
        k = self.n_moden_effektiv()
        anzahl = sum(1 for g in self._geraden if self._mode_von(g) == k)
        return min(k + 1, self._n_moden) if anzahl >= 2 else k
```

**Symptom.** Sind M1 und M2 vollständig und steht „Resonanzen je Linescan" auf
2, bekommt das nächste gezeichnete Band wieder Mode 2 und zerstört das
bestehende Band M2 (vier Geraden in einer Mode → das Band schrumpft auf den
Schnitt). Der Nutzer muss erst die Combo erhöhen. Das ist der eigentliche
Grund, warum die Combo überhaupt bedient werden muss – und damit die Ursache
der wahrgenommenen „drei Auswahlstellen".

**Fixvorschlag.** `mode_neu()` = `n_moden_effektiv() + 1`, sobald das oberste
Band voll ist, ohne Deckel; die Modenzahl ergibt sich aus der Bänderzahl (§5).

**Risiko.** Gering.

---

### F-10 (klein) Der Excel-Export verliert die Band-Nummer

**Datei:Zeile.** `hauptfenster.py:2495-2496`

```python
        zonen += [{"Typ": "Grenzgerade", "b1_T": g.b1, "f1_Hz": g.f1, "b2_T": g.b2, "f2_Hz": g.f2,
                   "gruen_positiv": g.gruen_positiv} for g in self._grenzgeraden]
```

`g.mode` fehlt, obwohl das Blatt *Global* die Zuordnungsregel „Moden-Baender
(Grenzgeraden)" ausweist (`:2468`) – die Bänder selbst sind im Export damit
nicht rekonstruierbar. Fix: `"mode": g.mode` ergänzen. Risiko: keins.

---

## 4. „Hauptmode ↻" und „Res.: n ×" – was tun sie, und braucht man sie?

### 4.1 „Hauptmode ↻" (`hauptfenster.py:288-295`, Slot `:2301-2321`)

**Algorithmus.** Der Slot arbeitet **nur auf dem gerade angezeigten Linescan**
(`i = self.aktueller_index`), ist aktiv bei `e.gefittet and e.n_moden > 1`
(`:2186`) und ruft immer `hauptmode_wechseln(e, 1)` – also *Rotation um eine
Position*, kein Auswählen einer bestimmten Mode. `hauptmode_wechseln`
(`fit/linescan_fit.py:640-654`) erzeugt eine Kopie mit rotierter Liste
`moden`/`fitkurven_moden` und kopiert `moden[0]` in die Skalarfelder
`B_res, B_res_err, alpha, alpha_err, dH, dH_err, A, A_err, phi, phi_err`.
Es wird **nicht** neu gefittet.

**Nebenwirkungen.**
* Farbplot-Hauptkurve, Tooltip (`:2139`), Statusfarbe – die Kriterienprüfung
  bewertet die Hauptmode als „die Felder des Ergebnisses selbst"
  (`fit/kriterien.py:130-133`), Rotation kann also den Fit-Status kippen.
* Excel-Hauptspalten `B_res_T`, `mu0_dH_mT`, `alpha`, … und die
  `*_2`/`*_3`-Zusatzspalten (`linescan_fit.py:224-238`) tauschen die Rollen.
* Kittel/LLG in der Ansicht **Hauptmode** ändert sich, in der Ansicht
  **Mode k** nicht (die geht über `ergebnisse_fuer_mode` → eigene Rotation).
* `ausreisser` (Linescan) unberührt; `ausreisser_moden` unberührt, weil sie an
  der Zweig-Nummer hängen, nicht an der Position – die Anzeige des zugehörigen
  `B_res` ändert sich aber (`ausreisser_panel.py:88-92`).
* Undo/Redo ist implementiert (`:2311-2314`); Persistenz **nicht** (F-3).

**Braucht man die Funktion in einem Modell „eine Modenliste M1..Mn mit je einem
Korridor"?** Nein. Ihr einziger fachlicher Zweck ist, eine falsche automatische
Zweig-Zuordnung an einem einzelnen Linescan zu korrigieren; genau das leistet
`zuordnung_moden` (`auswertung/moden.py:106-140`) bereits global,
reproduzierbar und über die Korridore gesteuert – und die Auswahl „Resonanz"
im Auswertungsfenster (`auswertung_fenster.py:121`) macht die Wahl der
auszuwertenden Mode explizit. Sobald `Mode k := Korridor k` gilt, ist
„welche Mode füllt die Skalarfelder" eine reine Darstellungsfrage
(Antwort: M1, bzw. jede Mode bekommt ihre eigene Zeile/ihr eigenes Blatt).
Dazu kommt: die Funktion ist **nicht haltbar** – jeder Neu-Fit desselben
Linescans und jedes Speichern/Laden macht sie rückgängig (F-3). Sie ist damit
eine Falle, kein Werkzeug.

**Empfehlung:** GUI-Knopf und Slot entfernen; `hauptmode_wechseln` als
Bibliotheksfunktion behalten – `ergebnisse_fuer_mode`
(`auswertung/moden.py:143-172`) baut damit die virtuellen Ergebnisse je Zweig.

### 4.2 „Res.: n ×" (`hauptfenster.py:280-287`)

Reines Duplikat von „Resonanzen je Linescan" (S5) ohne Synchronisation
(F-2). Einziges Alleinstellungsmerkmal: einen einzelnen Linescan mit
abweichender Modenzahl nachfitten – ein Zustand, der weder angezeigt noch
gespeichert wird und beim nächsten Dialog verschwindet. In einem Modell, in
dem die Modenzahl = Zahl der Korridore ist, hat er keinen Auftrag mehr.

**Empfehlung:** entfernen.

---

## 5. Vorschlag: eine Wahrheit

Wenn künftig „eine Modenliste M1..Mn mit je einem Korridor (zwei
Grenzgeraden)" die einzige Quelle sein soll, ergibt sich aus der Tabelle in §1
direkt der Zielzustand:

* **Quelle:** `Hauptfenster._grenzgeraden`, gruppiert nach `mode` → Liste der
  Korridore. `n_moden := Zahl der Korridore` (abgeleitet, nirgends gespeichert).
* **Entfallen:** S3 (`spin_moden`), S4/S5 (`ZonenPanel._n_moden` +
  `n_moden_combo`), der Knopf „Hauptmode ↻", `zonen_panel.mode_neu()`-Deckel,
  `BereichsFitDialog.moden_spin` (F-7), `AuswahlDialog.moden_combo`
  (Auto-Fit ohne Korridore = einmodig, mit Korridoren = deren Zahl).
* **Bleiben:** S2 `StapelErgebnis.n_moden` als *Ergebnis*-Feld (was wurde
  gefittet), S6 `Grenzgerade.mode` als Korridor-Nummer, S7 `FitErgebnis.moden`
  – dann aber **in Korridor-Reihenfolge** sortiert, womit F-6 und die drei
  Nummerierungen aus §1 auf eine zusammenfallen und `ModenZuordnung` (S9)
  zur Identität degeneriert (für den korridorlosen Fall bleibt die Feldregel
  als Rückfallebene).
* **Persistenz:** Korridore sind bereits vollständig in der Projektdatei
  (`projekt.py:77`); der Restore muss sie nur benutzen (F-4), dann ist der
  Zustand reproduzierbar und `hauptmode_nur=True` bleibt korrekt.

## 6. Priorisierung

| Prio | Befund | Kurz |
|---|---|---|
| 1 | F-1 | Panel-Desync nach Projekt laden/Strg+P → Grenzgeraden-Fit verweigert |
| 2 | F-4 | Band-Fits nach Projekt-Rundlauf nicht reproduzierbar (14/20 Linescans) |
| 3 | F-3 | „Hauptmode ↻" nicht persistiert, JSON widersprüchlich |
| 4 | F-2 | „Res.: n ×" unverbunden, dritte Wahrheit |
| 5 | F-7 | Rechteck-Fit senkt globale Modenzahl, entwertet Bänder |
| 6 | F-6 | Zwei Bedeutungen von „Mode k" in Plot vs. Auswertung |
| 7 | F-5 | Ausreißer-Panel mit anderer Zuordnungsregel |
| 8 | F-8, F-9, F-10 | v2-Projekte, `mode_neu()`-Deckel, fehlende Band-Nr. im Export |

## 7. Reproduktionsskripte

| Datei | Zeigt |
|---|---|
| `t1.py` | F-2 (Spin ohne Connect), F-1 (Panel nach `_physik_uebernehmen`) |
| `t2.py` | F-1 vollständig (Projekt-Rundlauf, `zaehle_abgedeckt` 0 statt 208) |
| `t3.py` | F-3 (Hauptmode-Wechsel geht verloren) |
| `t4.py` | F-4 (14/20 Linescans weichen ab), Belege für F-6 |
| `t5.py` | F-5 (Regel band vs. feld), F-7 (Absenken entwertet Bänder) |

Alle mit `/home/ibrahim/Dokumente/Ananas/.venv/bin/python` und
`QT_QPA_PLATFORM=offscreen` ausgeführt; Testdaten
`testdata-n-lorentz/2025-NOV-11-Linescan-2D-map-oop-5K_1.1deg-for-FTF.tdms`
(629 Linescans, 2.36–4.37 T, 6.0–50.0 GHz).

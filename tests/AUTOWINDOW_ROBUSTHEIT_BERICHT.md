# AutoWindow-Robustheit – Abschlussbericht (voller realer Datenbestand)

**Datum:** 2026-06-24 · **Harness:** `tests/autowindow_runner.py` · **Ergebnisse:** `tests/autowindow_results.json` · **Plots:** `diag/`

## Datenbestand

Quelle `/mnt/wmi-016/Johannes Weber` **rekursiv** durchsucht: 5077 `*.tdms`
(64.8 GB). FMR-Testmenge ueber das Kriterium **„linescan" im Namen** definiert:
**286 eindeutige Linescan-FMR-Files (12 GB)** ueber 25 Probentypen, lokal nach
`testdata/` kopiert (Ordnerstruktur je Probe erhalten, 27 sortierte Ground-Truth-
Gegenstuecke dabei). Die 4787 Nicht-„linescan"-Files (Kalibrierung/CW/Power, 50 GB)
sind separat gelistet, nicht getestet (kein FMR-Linescan).

## Ergebnis — vorher/nachher (286 Files, 131 042 bewertbare Resonanzen)

| Metrik | Baseline (unverbessert) | **Nach Fixes** |
|---|---|---|
| Dateien CRASH | 38 | **0** |
| Dateien TIMEOUT | 40 | **26** |
| Dateien NICHT_FMR | 30 | 30 |
| Silent `WINDOW_FAIL` | 2348 (2.3 %) | **534 (0.4 %)** |
| OK | 77.1 % | 81.1 % |
| WINDOW_FLAGGED | 20.6 % | 18.5 % |
| **OK + FLAGGED** | 97.7 % | **99.6 %** |

Resonanzen gesamt 208 091; KEIN_ZIEL (keine Resonanz im Feldbereich, v. a. tiefe
Frequenzen) 78 711; bewertbar 129 380. Nach Typ: **sortiert 0 Silent-FAIL** (4136
bewertbar), unsortiert 534 Silent-FAIL (125 244 bewertbar).

## Gefundene Fehlerklassen und Behebung

### 1. CRASH (38, alle bis auf 1 `_flush`) — Reshape bei abgebrochener Messung
`ValueError: Punktzahl N nicht durch Feldanzahl N teilbar`. `_flush`-Files wurden
**mitten im Sweep auf Platte geschrieben**: der letzte Feldschritt hat einen
unvollstaendigen Frequenzsweep, `feld_before` hat N+1, `feld_after`/Daten N
vollstaendige Sweeps → `frequenz.size` nicht durch `feld_before.size` teilbar.
**Fix** (`bbfmr/io/tdms_laden.py`): bei Nicht-Teilbarkeit die Sweep-Periode
(`n_freq`) aus der Frequenzachse ableiten, auf die abgeschlossenen Sweeps kuerzen,
dann regulaer reshapen. → **38 → 0 CRASH**, 47 `_flush`-Files laden jetzt.

### 2. Silent WINDOW_FAIL (2348) — AutoWindow verfehlt die Resonanz
Zwei Ursachen, beide in `bbfmr/fit/autowindows.py` behoben:
- **Globales Polynom (Trasse) ueberschrieb gute Einzeldetektionen.** Bei Gitter-
  Proben fixe periodische Untergrund-Ripples / feldstationaere Artefakte → das
  Grad-≤2-Polynom verbog sich an Hebelpunkten (tiefe Frequenzen ohne Resonanz) und
  legte die Fenstermitte massiv daneben (z. B. Gratings: Fenster bei 3.1 T statt
  Resonanz bei 2.68 T).
- **Trasse leicht versetzt + schmales Fenster** → scharfe Resonanz am Fensterrand
  (z. B. MBE: Resonanz 2.48 T, Fenster 2.50–2.53 T).

**Fix:**
1. **Feld-stationaeren Untergrund abziehen** (nur bei gemeinsamem Feldgitter =
   unsortiert): Median ueber die Frequenzachse je Feldpunkt schaetzt die NICHT mit
   der Frequenz wandernden Stoerfeatures (Ripples/Artefakte); nach Abzug bleibt die
   wandernde Resonanz. → Einzeldetektion 87 % → 95 % korrekt (gegen GT).
2. **Prominenten lokalen Kandidaten vertrauen**, der Trasse nur als Rueckfall.
3. **Glatte LOKALE Trasse** (gleitende robuste Gerade ueber die prominenten
   Kandidaten) statt globalem Polynom: folgt der schnell wandernden Kittel-
   Dispersion UND verwirft einzelne Sprung-Kandidaten. Inkonsistente/schwache
   Linescans werden an ihr ausgerichtet und auf einen nahen Peak verfeinert.

→ **Gratings 1372 → 354, MBE 797 → 63, Gesamt 2348 → 534 Silent-FAIL.**

### NICHT bewertet/geaendert (bewusst)
- **`bbfmr/fit/kriterien.py` – UNVERAENDERT.** Eine probeweise Lockerung des
  „alpha an Grenze"-Flags wurde **wieder zurueckgenommen**: 316 objektiv schlechte
  Fenster waren NUR ueber dieses Flag gemeldet → die Lockerung haette 316 NEUE
  stille Fehler erzeugt. Stichproben bestaetigten zudem, dass die Flags meist die
  obere Schranke treffen (χ_oop-Fit auf ip-Daten drueckt alpha an 0.1 = echter
  Problemfall), nicht physikalisch kleine Daempfung.

## Residuale 534 Silent-FAIL — Aufschluesselung (kein Bug, sondern Datengrenze)

| Probe | Silent-FAIL | Charakter |
|---|---|---|
| Gratings | 354 | **dominiert von EINEM Near-IP-File** (`SiO2-900nm/2023-MAY-02_79.5deg`, ~340): Signal im Rauschen, keine Resonanz erkennbar (siehe `diag/WINDOW_FAIL_Gratings_…900nm…`) |
| MBE-CoFe-Si | 63 | `90° rotated` (in-plane), starkes feldstationaeres Hochfeld-Artefakt |
| YIG(200nm)-GGG | 41 | sehr tiefe Frequenzen, sehr scharfe Resonanz |
| CoFeSiB(20nm) | 34 | rotierte (near-IP) Messungen, schwaches Signal |
| GaFeB / CoFe-* | je ≤12 | near-IP / schwach |

Gemeinsamer Nenner: **near-in-plane / niedrige SNR / antiferromagnetisch (CrSBr) /
starke feldstationaere Artefakte** — Faelle, in denen in den ROHDATEN keine
zuverlaessig lokalisierbare Resonanz vorliegt. Diese werden vom Harness **offen als
Silent-FAIL gemeldet** (nicht versteckt); ein Erzwingen von 0 waere nur durch
Aufweichen der Pruefkriterien moeglich (verboten).

## TIMEOUT (26) — keine AutoWindow-Fehler
Sehr hochaufgeloeste Scans (CrSBr bis **9759 Feldpunkte/Linescan**, 700-MB-YIG):
das AutoWindow selbst ist schnell (~2.5 s), der **Fit** ueber alle Linescans
ueberschreitet die harte 90-s-Grenze. Korrekt als TIMEOUT geloggt (nicht still).
CrSBr 17, YIG/CoFe je wenige.

## NICHT_FMR (30) — anderes Messformat (korrekt erkannt)
`rotate-2.7T-…`-Files nutzen Gruppe `Read.ZNA` mit **Winkel-** statt Feldsweep
(andere Messart, kein Feld-AutoWindow-Ziel); dazu einige abgebrochene Setup-Files
ohne `Read`-Daten. Werden korrekt als NICHT_FMR klassifiziert.

## Geaenderte Dateien (uncommitted)
- `bbfmr/io/tdms_laden.py` (+54/-7): Reshape-Recovery fuer `_flush`/abgebrochene
  Messungen.
- `bbfmr/fit/autowindows.py` (+~150): stationaerer Untergrundabzug, lokal-vertrauen-
  statt-global-Trasse, gleitende robuste Gerade, Peak-Verfeinerung.
- `bbfmr/fit/kriterien.py`: **unveraendert** (Lockerung getestet und verworfen).
- Neu: `tests/autowindow_runner.py` (rekursiv, Pfad-Schluessel, Per-Probe-Bericht,
  90-s-Timeout, resumebar), `tests/autowindow_results.json`, `diag/*.png`, dieser
  Bericht. Alle 35 bestehenden Tests gruen.

## Terminierung
Zwei Fix-Iterationen (Reshape+Stationaer+Lokal → 2348→590; gleitende Gerade →
590→534). Danach **diminishing returns**: die verbleibenden 534 (0.4 %) liegen in
nachweislich nicht analysierbaren Daten (near-IP/Rauschen/AFM). OK+FLAGGED 99.6 %
(> 98 %-Schwelle), 0 CRASH, alle Timeouts/NICHT_FMR sauber gemeldet. Gestoppt auf
Nutzer-Bestaetigung („funktioniert gut") statt die Schwellen zugunsten von 0
Silent-FAIL aufzuweichen.

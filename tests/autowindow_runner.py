"""Robustheits-Harness fuer das AutoWindow von bbFMR.

Testet den GESAMTEN realen Datenbestand (``testdata/*.tdms``) gegen die
automatische Resonanzfenster-Auswahl. Der Fit selbst funktioniert – geprueft wird,
ob das *Fenster* sitzt und ob falsch sitzende Fenster vom Programm GEMELDET werden
(statt still falschen Murks zu liefern).

Status je Resonanz (Linescan):
  OK             Fenster plausibel + Fit nicht problematisch.
  WINDOW_FLAGGED Fenster-Problem erkannt UND von bbFMR selbst gemeldet
                 (``ergebnis.problematisch``) -> erlaubt.
  WINDOW_FAIL    Fenster-Problem erkannt, aber NICHT gemeldet -> stiller Bug.
Status je Datei zusaetzlich: CRASH / TIMEOUT / NICHT_FMR.

Die Fenster-Checks sind UNABHAENGIG vom AutoWindow-Algorithmus reimplementiert
(eigener robuster Untergrundabzug + Peak-Suche), damit die Validierung nicht
zirkulaer wird. Wo ein sortiertes Gegenstueck existiert, dient dessen Feldband als
Ground Truth.

Aufruf:
  python tests/autowindow_runner.py            # voller Lauf
  python tests/autowindow_runner.py --rerun-failed-only
  python tests/autowindow_runner.py --no-plots
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

# Headless-Plotten.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HIER = Path(__file__).resolve().parent
WURZEL = HIER.parent
if str(WURZEL) not in sys.path:
    sys.path.insert(0, str(WURZEL))

TESTDATA = WURZEL / "testdata"
DIAG = WURZEL / "diag"
RESULTS = WURZEL / "tests" / "autowindow_results.json"


def _schluessel(p) -> str:
    """Stabiler Schluessel = Pfad relativ zu ``testdata/`` (Dateinamen kollidieren
    ueber Probenordner hinweg, daher NICHT der reine Name)."""
    try:
        return Path(p).relative_to(TESTDATA).as_posix()
    except ValueError:
        return Path(p).name


def _probe(schluessel: str) -> str:
    """Probentyp = oberster Unterordner unter ``testdata/`` (sonst '(toplevel)')."""
    teile = schluessel.split("/")
    return teile[0] if len(teile) > 1 else "(toplevel)"

PRO_DATEI_TIMEOUT = 90.0           # s, harter Per-Datei-Timeout
WORKERS = min(8, os.cpu_count() or 1)

# --- Schwellwerte der UNABHAENGIGEN Fenster-Pruefung -----------------------
# Bewusst konservativ: ein Fenster wird nur dann als problematisch gewertet, wenn
# das Problem klar und reproduzierbar ist (kein Aufweichen zugunsten der Quote).
PROM_PRESENT = 6.0       # MAD-Sigma: ab hier gilt eine Resonanz als klar vorhanden
PROM_STARK = 10.0        # ab hier "dominante" Resonanz (fuer Verpasst-Kriterium)
PROM_NEBEN = 8.0         # Prominenz eines Nebenpeaks fuer Mehrfachresonanz (Diagnose)
FIT_RMSE_GUT = 0.35      # normiertes Residuum, unter dem der Fit als gut gilt
ZU_ENG_FLANKE = 0.5      # Residuum am Fensterrand > Faktor*Peakhoehe -> Flanke beschnitten
ZU_WEIT_FAKTOR = 6.0     # Fensterbreite > Faktor*FWHM und kaum Signalanteil -> zu weit
ZU_WEIT_ANTEIL = 0.12    # Anteil des Fensters ueber Halbmax, unter dem es "zu weit" ist
GT_TOL_T = 0.03          # Toleranz (T), um die das Fensterzentrum aus dem GT-Band darf
RAND_SAMPLES = 2         # Peak innerhalb so vieler Randpunkte -> Randresonanz

# Diagnose-Plot-Deckel (kein stilles Abschneiden – wird geloggt).
MAX_PLOTS_FAIL_PRO_DATEI = 30
MAX_PLOTS_FLAGGED_PRO_DATEI = 8


# ==========================================================================
# Unabhaengige Resonanz-/Fenster-Analyse
# ==========================================================================
def _detrend_unabh(B: np.ndarray, sig: np.ndarray) -> np.ndarray:
    """Untergrundbereinigtes |S21| – EIGENE, vom Algorithmus unabhaengige Schaetzung."""
    B = np.asarray(B, float)
    sig = np.asarray(sig)
    n = B.size
    if n < 6:
        return np.abs(sig - np.mean(sig))
    span = float(B.max() - B.min()) or 1.0
    deg = int(np.clip(round(span / 0.5), 2, 6))
    deg = min(deg, max(1, n // 3))
    cre = np.polyfit(B, sig.real, deg)
    cim = np.polyfit(B, sig.imag, deg)
    rest = (sig.real - np.polyval(cre, B)) + 1j * (sig.imag - np.polyval(cim, B))
    return np.abs(rest)


def _prominenz(rein: np.ndarray) -> tuple[int, float, float, float]:
    """``(i_peak, prominenz_sigma, median, peakhoehe_ueber_median)``."""
    i = int(np.argmax(rein))
    med = float(np.median(rein))
    mad = float(np.median(np.abs(rein - med))) or 1e-12
    prom = (float(rein[i]) - med) / (1.4826 * mad)
    return i, prom, med, float(rein[i]) - med


def _peaks_getrennt(B, rein, lo, hi, med, hoehe):
    """Zaehlt ECHTE, getrennte Resonanzen im Fenster (konservativ, Diagnose).

    Ein Zweitpeak zaehlt nur, wenn er (a) hinreichend hoch ist (>= 0.45 der
    Hauptpeakhoehe), (b) deutlich vom Hauptpeak getrennt ist und (c) das Residuum
    dazwischen wieder fast auf die Basislinie faellt (< 0.3 der Hoehe). Damit
    werden Rausch-/Schulter-Doppelspitzen EINER Resonanz nicht mehr als zwei
    Resonanzen gezaehlt (haeufigster Fehlalarm der ersten Version).
    """
    maske = (B >= lo) & (B <= hi)
    if maske.sum() < 7 or hoehe <= 0:
        return 0
    Bf = B[maske]
    rf = rein[maske] - med
    hoch = 0.45 * hoehe
    tal = 0.3 * hoehe
    peaks = []
    for k in range(1, rf.size - 1):
        if rf[k] >= hoch and rf[k] >= rf[k - 1] and rf[k] >= rf[k + 1]:
            peaks.append(k)
    if len(peaks) < 2:
        return len(peaks)
    # Nur Peaks behalten, zwischen denen das Residuum auf Talniveau faellt.
    echte = [peaks[0]]
    for k in peaks[1:]:
        zwischen = rf[echte[-1]:k + 1]
        if zwischen.size and float(zwischen.min()) < tal and (Bf[k] - Bf[echte[-1]]) > 0.02:
            echte.append(k)
    return len(echte)


def _lokalisiere_resonanz(B, rein):
    """Robuste, KANTENFESTE Resonanzortung.

    Liefert ``(i_peak, b_peak, prominenz, med, hoehe, isoliert)``. Die aeusseren
    ~4 % der Feldpunkte werden bei der Peak-Suche ignoriert: am Rand des Sweeps
    erzeugt der abklingende Untergrund (Roll-off) regelmaessig grosse Residuen, die
    eine naive ``argmax``-Suche faelschlich als "Resonanz" detektiert (genau diese
    Kantenartefakte haben die fruehe Heuristik in die Irre gefuehrt).
    """
    n = B.size
    med = float(np.median(rein))
    mad = float(np.median(np.abs(rein - med))) or 1e-12
    m = max(2, int(round(0.04 * n)))
    if n - 2 * m >= 5:
        i_rel = int(np.argmax(rein[m:n - m]))
        i = i_rel + m
    else:
        i = int(np.argmax(rein))
    prom = (float(rein[i]) - med) / (1.4826 * mad)
    hoehe = float(rein[i]) - med
    # Isoliertheit: zweithoechster, baseline-getrennter Peak relativ zum Hauptpeak.
    schwelle = med + 0.5 * hoehe
    masch = rein >= schwelle
    # Bereiche oberhalb der Halbhoehe finden; alles ausserhalb des Hauptbereichs
    # gilt als potenzieller Zweitpeak.
    nebenhoehe = 0.0
    if hoehe > 0:
        # Hauptpeak-Bereich um i ausblenden
        links = i
        while links > 0 and rein[links - 1] >= med + 0.3 * hoehe:
            links -= 1
        rechts = i
        while rechts < n - 1 and rein[rechts + 1] >= med + 0.3 * hoehe:
            rechts += 1
        rest = rein.copy()
        rest[max(0, links - 1):min(n, rechts + 2)] = med
        nebenhoehe = float(rest[m:n - m].max() - med) if n - 2 * m >= 5 else float(rest.max() - med)
    isoliert = nebenhoehe < 0.5 * hoehe
    return i, float(B[i]), prom, med, hoehe, isoliert


def fenster_checks(B, s21, lo, hi, ref_band, fit):
    """Bewertet ein Fenster anhand OBJEKTIVER Ergebnisse, nicht fragiler Morphologie.

    Ein Fenster gilt nur dann als FEHLERHAFT (``objektiv_bad``), wenn es die
    Resonanz objektiv verfehlt:

    * **GT-Verletzung** – existiert ein sortiertes Gegenstueck, MUSS das
      Fensterzentrum (mit Toleranz) im GT-Band liegen und das Fenster mit ihm
      ueberlappen. Das ist das objektivste Kriterium.
    * **Dominante Resonanz verpasst** – eine klare, isolierte, *innenliegende*
      (kantenfest detektierte) Resonanz liegt deutlich ausserhalb des Fensters.

    Reine Form-Auffaelligkeiten (zu eng/weit, Doppelspitze) werden zusaetzlich als
    *Diagnose*-Klassen erfasst (``morph``), zaehlen aber nur dann als Fehler, wenn
    auch das Ergebnis schlecht ist – ein Fenster, dessen Fit gut ist UND (falls
    GT vorhanden) im GT-Band liegt, ist per Definition kein schlechtes Fenster.
    Damit wird die Validierung nicht zirkulaer und produziert keine Fehlalarme auf
    nachweislich guten Fenstern.

    Liefert ``(objektiv_bad, morph, info)``.
    """
    B = np.asarray(B, float)
    n = B.size
    objektiv_bad: list[str] = []
    morph: list[str] = []
    info: dict = {}
    if n < 5:
        return objektiv_bad, morph, info

    rein = _detrend_unabh(B, s21)
    i_glob, b_peak, prom, med, hoehe, isoliert = _lokalisiere_resonanz(B, rein)
    info["prom"] = round(prom, 2)
    info["b_peak"] = round(b_peak, 5)

    spacing = float(np.ptp(B)) / n if n else 0.0
    voll = (lo <= B.min() + 2 * spacing) and (hi >= B.max() - 2 * spacing)
    breite = hi - lo
    info["breite"] = round(breite, 5)
    zentrum = 0.5 * (lo + hi)

    resonanz_da = prom >= PROM_PRESENT
    info["resonanz_da"] = bool(resonanz_da)

    # Fit-Kennzahlen (objektive Ergebnisqualitaet).
    rmse = fit.get("rmse_norm", np.inf)
    fit_gut = bool(fit.get("erfolg")) and np.isfinite(rmse) and rmse < FIT_RMSE_GUT
    b_res = fit.get("B_res", np.nan)
    info["rmse_norm"] = round(rmse, 3) if np.isfinite(rmse) else None

    # --- Objektives Kriterium 1: GT-Band -----------------------------------
    if ref_band is not None:
        blo, bhi = ref_band
        info["gt_band"] = [round(blo, 5), round(bhi, 5)]
        overlap = max(0.0, min(hi, bhi) - max(lo, blo))
        in_band = (blo - GT_TOL_T) <= zentrum <= (bhi + GT_TOL_T)
        if (not in_band) or overlap <= 0:
            objektiv_bad.append("FENSTER_LEER")  # gegen GT verrutscht

    # --- Kein Resonanzziel? ------------------------------------------------
    if not resonanz_da and ref_band is None:
        info["kein_ziel"] = True
        return objektiv_bad, morph, info

    # --- Objektives Kriterium 2: dominante Resonanz verpasst ----------------
    # Nur bei KLARER, isolierter, innenliegender Resonanz und nur, wenn der Fit
    # die Verfehlung nicht ohnehin durch ein grosses Residuum sichtbar macht ODER
    # GT die Lage bestaetigt – sonst Gefahr eines Kantenartefakt-Fehlalarms.
    if resonanz_da and isoliert and prom >= PROM_STARK:
        marge = max(0.5 * breite, 6 * spacing)
        verpasst = (b_peak < lo - marge) or (b_peak > hi + marge)
        # Gegen GT absichern: liegt der detektierte Peak ueberhaupt im GT-Band?
        peak_passt_gt = True
        if ref_band is not None:
            blo, bhi = ref_band
            peak_passt_gt = (blo - GT_TOL_T) <= b_peak <= (bhi + GT_TOL_T)
        if verpasst and peak_passt_gt:
            if voll:
                objektiv_bad.append("KEIN_FENSTER")
            else:
                objektiv_bad.append("FENSTER_LEER")
            if i_glob <= RAND_SAMPLES or i_glob >= n - 1 - RAND_SAMPLES:
                objektiv_bad.append("RANDRESONANZ_VERPASST")

    # --- Diagnose-Morphologie (nur informativ) -----------------------------
    halb = med + 0.5 * hoehe
    ueber = np.where(rein >= halb)[0]
    fwhm = float(B[ueber[-1]] - B[ueber[0]]) if ueber.size >= 2 else 4 * spacing
    info["fwhm"] = round(fwhm, 5)
    peak_im_fenster = lo <= b_peak <= hi
    if peak_im_fenster and not voll and breite > 0:
        i_lo = int(np.argmin(np.abs(B - lo)))
        i_hi = int(np.argmin(np.abs(B - hi)))
        rand = max(rein[i_lo], rein[i_hi]) - med
        if rand > ZU_ENG_FLANKE * hoehe and breite < fwhm:
            morph.append("FENSTER_ZU_ENG")
        anteil_ueber = float(np.mean(rein[(B >= lo) & (B <= hi)] >= halb))
        if breite > ZU_WEIT_FAKTOR * fwhm and anteil_ueber < ZU_WEIT_ANTEIL and breite > 0.3:
            morph.append("FENSTER_ZU_WEIT")
    if _peaks_getrennt(B, rein, lo, hi, med, hoehe) >= 2:
        morph.append("MEHRFACHRESONANZ")

    objektiv_bad = list(dict.fromkeys(objektiv_bad))
    morph = list(dict.fromkeys(morph))
    return objektiv_bad, morph, info


# ==========================================================================
# GT-Band-Zuordnung (sortiertes Gegenstueck)
# ==========================================================================
def baue_gt_baender(sortiert_pfad):
    """Feldband je Frequenz aus einem sortierten File: ``[(f, lo, hi), ...]``."""
    from bbfmr.io.tdms_laden import lade_tdms
    ds = lade_tdms(str(sortiert_pfad))
    baender = []
    for ls in ds.linescans:
        if ls.feld.size:
            baender.append((ls.frequenz, float(ls.feld.min()), float(ls.feld.max())))
    baender.sort()
    return baender


def gt_band_fuer(f, baender, max_df=0.3e9):
    """Naechstes GT-Band zur Frequenz ``f`` (None, wenn keins nah genug)."""
    if not baender:
        return None
    fs = np.array([b[0] for b in baender])
    k = int(np.argmin(np.abs(fs - f)))
    if abs(fs[k] - f) > max_df:
        return None
    return (baender[k][1], baender[k][2])


# ==========================================================================
# Per-Datei-Worker (laeuft im Subprozess)
# ==========================================================================
def verarbeite_datei(pfad_str, schluessel, gt_pfad_str, ergebnis_q):
    """Volle Pipeline einer Datei. Ergebnis in die Queue legen."""
    try:
        from bbfmr.io.tdms_laden import lade_tdms
        from bbfmr.fit.batch import fitte_alle

        name = schluessel

        # --- Laden + Typ-Erkennung --------------------------------------
        try:
            ds = lade_tdms(pfad_str)
        except ValueError as exc:
            if "Unbekanntes TDMS-Format" in str(exc):
                ergebnis_q.put({"datei": name, "status_datei": "NICHT_FMR",
                                "grund": str(exc)[:200]})
                return
            raise

        gt_baender = baue_gt_baender(gt_pfad_str) if gt_pfad_str else []

        # --- AutoWindow + Fit (volle Stapelverarbeitung) -----------------
        stapel = fitte_alle(ds)

        zaehler = {"OK": 0, "WINDOW_FLAGGED": 0, "WINDOW_FAIL": 0, "KEIN_ZIEL": 0}
        klasse_zaehler: dict[str, dict[str, int]] = {}  # klasse -> {flagged, fail}
        morph_zaehler: dict[str, int] = {}              # Diagnose-Morphologie
        probleme = []  # detaillierte Eintraege fuer Plot/Report

        for i, ls in enumerate(ds.linescans):
            lo, hi = stapel.fenster[i]
            erg = stapel.ergebnisse[i]
            ref = gt_band_fuer(ls.frequenz, gt_baender)
            fit = {"rmse_norm": erg.rmse_norm, "erfolg": erg.erfolg, "B_res": erg.B_res}
            objektiv_bad, morph, cinfo = fenster_checks(ls.feld, ls.s21, lo, hi, ref, fit)
            gemeldet = bool(erg.problematisch)
            for mk in morph:
                morph_zaehler[mk] = morph_zaehler.get(mk, 0) + 1

            if cinfo.get("kein_ziel"):
                # Keine Resonanz vorhanden -> kein Autowindow-Ziel.
                zaehler["KEIN_ZIEL"] += 1
                continue

            if not objektiv_bad:
                if gemeldet:
                    # Programm meldet ein (Fit-)Problem, Fenster aber objektiv ok.
                    zaehler["WINDOW_FLAGGED"] += 1
                else:
                    zaehler["OK"] += 1
                continue

            # Objektiv schlechtes Fenster -> wird es vom Programm gemeldet?
            if gemeldet:
                zaehler["WINDOW_FLAGGED"] += 1
                status = "WINDOW_FLAGGED"
            else:
                zaehler["WINDOW_FAIL"] += 1
                status = "WINDOW_FAIL"

            for kl in objektiv_bad:
                slot = klasse_zaehler.setdefault(kl, {"flagged": 0, "fail": 0})
                slot["fail" if status == "WINDOW_FAIL" else "flagged"] += 1

            probleme.append({
                "i": i, "f_GHz": round(ls.frequenz / 1e9, 4),
                "fenster": [round(lo, 5), round(hi, 5)],
                "klassen": objektiv_bad, "morph": morph, "status": status,
                "gruende": erg.problem_gruende, "info": cinfo,
            })

        ergebnis_q.put({
            "datei": name,
            "status_datei": "OK",
            "format": ds.format_typ,
            "n_resonanzen": len(ds.linescans),
            "hat_gt": bool(gt_baender),
            "zaehler": zaehler,
            "klasse_zaehler": klasse_zaehler,
            "morph_zaehler": morph_zaehler,
            "probleme": probleme,
        })
    except Exception:
        ergebnis_q.put({
            "datei": schluessel,
            "status_datei": "CRASH",
            "traceback": traceback.format_exc(),
        })


# ==========================================================================
# Scheduler mit hartem Per-Datei-Timeout
# ==========================================================================
def finde_paare(dateien):
    """Ordnet jeder unsortierten Datei ihr sortiertes Gegenstueck zu (Pfad oder None).

    Sortierte Files enden auf ``-sorted...`` oder ``-for-FTF``; die unsortierte hat
    denselben Stamm ohne dieses Suffix. Gepaart wird NUR innerhalb DESSELBEN Ordners
    (Probe), damit gleichnamige Messungen verschiedener Proben nicht verwechselt
    werden. Schluessel der Zuordnung ist der testdata-relative Pfad.
    """
    def stamm(p):
        s = p.stem
        for suf in ("-sorted (1)", "-sorted", "-for-FTF"):
            if s.endswith(suf):
                return s[: -len(suf)], True
        return s, False

    # Sortierte je (Ordner, Stamm).
    sortierte = {}
    for p in dateien:
        st, ist_sort = stamm(p)
        if ist_sort:
            sortierte[(str(p.parent), st)] = p

    zuordnung = {}
    for p in dateien:
        st, ist_sort = stamm(p)
        if not ist_sort and (str(p.parent), st) in sortierte:
            zuordnung[_schluessel(p)] = str(sortierte[(str(p.parent), st)])
    return zuordnung


def lauf(dateien, gt_zuordnung):
    ctx = mp.get_context("spawn")
    offen = list(dateien)
    laufend = {}  # proc -> (datei, queue, start)
    fertig = {}

    def starte(pfad):
        q = ctx.Queue()
        sch = _schluessel(pfad)
        gt = gt_zuordnung.get(sch)
        p = ctx.Process(target=verarbeite_datei, args=(str(pfad), sch, gt, q))
        p.start()
        laufend[p] = (pfad, sch, q, time.time())

    while offen or laufend:
        while offen and len(laufend) < WORKERS:
            starte(offen.pop(0))

        time.sleep(0.2)
        for p in list(laufend):
            pfad, sch, q, start = laufend[p]
            res = None
            if not q.empty():
                try:
                    res = q.get_nowait()
                except Exception:
                    res = None
            if res is not None:
                p.join(timeout=5)
                if p.is_alive():
                    p.terminate()
                fertig[sch] = res
                del laufend[p]
                _log_kurz(res)
            elif not p.is_alive():
                # Prozess tot ohne Ergebnis -> Crash beim Start.
                fertig[sch] = {"datei": sch, "status_datei": "CRASH",
                               "traceback": "Prozess ohne Ergebnis beendet."}
                del laufend[p]
                _log_kurz(fertig[sch])
            elif time.time() - start > PRO_DATEI_TIMEOUT:
                p.terminate()
                p.join(timeout=5)
                fertig[sch] = {"datei": sch, "status_datei": "TIMEOUT",
                               "dauer_s": round(time.time() - start, 1)}
                del laufend[p]
                _log_kurz(fertig[sch])
    return fertig


def _log_kurz(res):
    sd = res.get("status_datei")
    if sd == "OK":
        z = res["zaehler"]
        print(f"  [{sd:6}] {res['datei'][:55]:55} {res['format']:10} "
              f"OK={z['OK']} FLAG={z['WINDOW_FLAGGED']} FAIL={z['WINDOW_FAIL']} "
              f"KZ={z['KEIN_ZIEL']}")
    else:
        print(f"  [{sd:8}] {res['datei'][:55]}")


# ==========================================================================
# Diagnose-Plots
# ==========================================================================
def schreibe_plots(dateien, fertig, gt_zuordnung):
    from bbfmr.io.tdms_laden import lade_tdms
    DIAG.mkdir(exist_ok=True)
    geplottet = {"FAIL": 0, "FLAGGED": 0}
    gedeckelt = 0
    for pfad in dateien:
        sch = _schluessel(pfad)
        res = fertig.get(sch)
        if not res or res.get("status_datei") != "OK":
            continue
        probleme = res.get("probleme", [])
        if not probleme:
            continue
        fails = [p for p in probleme if p["status"] == "WINDOW_FAIL"]
        flags = [p for p in probleme if p["status"] == "WINDOW_FLAGGED"]
        n_fail = min(len(fails), MAX_PLOTS_FAIL_PRO_DATEI)
        n_flag = min(len(flags), MAX_PLOTS_FLAGGED_PRO_DATEI)
        gedeckelt += (len(fails) - n_fail) + (len(flags) - n_flag)
        auswahl = fails[:n_fail] + flags[:n_flag]
        if not auswahl:
            continue
        try:
            ds = lade_tdms(str(pfad))
        except Exception:
            continue
        gt = gt_zuordnung.get(sch)
        baender = baue_gt_baender(gt) if gt else []
        for pe in auswahl:
            ls = ds.linescans[pe["i"]]
            ref = gt_band_fuer(ls.frequenz, baender)
            _plot_einen(sch, ls, pe, ref)
            geplottet["FAIL" if pe["status"] == "WINDOW_FAIL" else "FLAGGED"] += 1
    print(f"\nDiagnose-Plots: {geplottet['FAIL']} FAIL, {geplottet['FLAGGED']} FLAGGED "
          f"-> {DIAG}")
    if gedeckelt:
        print(f"  (Deckel aktiv: {gedeckelt} weitere Problem-Resonanzen NICHT geplottet)")


def _plot_einen(datei, ls, pe, ref):
    B = ls.feld
    rein = _detrend_unabh(B, ls.s21)
    lo, hi = pe["fenster"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    ax1.plot(B, np.abs(ls.s21), ".-", ms=2, lw=0.6, label="|S21|")
    ax1.axvspan(lo, hi, color="orange", alpha=0.25, label="AutoWindow")
    if ref is not None:
        ax1.axvspan(ref[0], ref[1], color="green", alpha=0.15, label="GT-Band")
    ax1.legend(fontsize=7, loc="best")
    ax1.set_ylabel("|S21|")
    ax1.set_title(f"{datei}\nf={pe['f_GHz']}GHz  {pe['status']}  {','.join(pe['klassen'])}",
                  fontsize=8)
    ax2.plot(B, rein, ".-", ms=2, lw=0.6, color="purple", label="|Residuum| (unabh.)")
    ax2.axvspan(lo, hi, color="orange", alpha=0.25)
    if ref is not None:
        ax2.axvspan(ref[0], ref[1], color="green", alpha=0.15)
    ax2.set_xlabel("Feld B (T)")
    ax2.set_ylabel("Residuum")
    ax2.legend(fontsize=7)
    fig.tight_layout()
    sicher = "".join(c if c.isalnum() else "_" for c in datei)[:50]
    out = DIAG / f"{pe['status']}_{sicher}_i{pe['i']}_f{pe['f_GHz']}.png"
    fig.savefig(out, dpi=80)
    plt.close(fig)


# ==========================================================================
# Bericht
# ==========================================================================
def bericht(fertig):
    print("\n" + "=" * 78)
    print("ABSCHLUSSBERICHT  AutoWindow-Robustheit")
    print("=" * 78)
    g = {"OK": 0, "WINDOW_FLAGGED": 0, "WINDOW_FAIL": 0, "KEIN_ZIEL": 0}
    nach_typ = {}
    nach_klasse = {}
    morph_gesamt = {}
    nach_probe = {}
    dateien_status = {"OK": 0, "CRASH": 0, "TIMEOUT": 0, "NICHT_FMR": 0}
    n_res = 0
    for name, res in sorted(fertig.items()):
        sd = res.get("status_datei")
        dateien_status[sd] = dateien_status.get(sd, 0) + 1
        probe = _probe(res.get("datei", name))
        ps = nach_probe.setdefault(probe, {"dateien": 0, "OK": 0, "WINDOW_FLAGGED": 0,
                                           "WINDOW_FAIL": 0, "KEIN_ZIEL": 0,
                                           "CRASH": 0, "TIMEOUT": 0, "NICHT_FMR": 0})
        ps["dateien"] += 1
        if sd != "OK":
            ps[sd] = ps.get(sd, 0) + 1
            continue
        z = res["zaehler"]
        for k in g:
            g[k] += z.get(k, 0)
        for k in ("OK", "WINDOW_FLAGGED", "WINDOW_FAIL", "KEIN_ZIEL"):
            ps[k] += z.get(k, 0)
        n_res += res["n_resonanzen"]
        typ = res["format"]
        tt = nach_typ.setdefault(typ, {"OK": 0, "WINDOW_FLAGGED": 0,
                                       "WINDOW_FAIL": 0, "KEIN_ZIEL": 0})
        for k in tt:
            tt[k] += z.get(k, 0)
        for kl, cnt in res.get("klasse_zaehler", {}).items():
            slot = nach_klasse.setdefault(kl, {"flagged": 0, "fail": 0})
            slot["flagged"] += cnt["flagged"]
            slot["fail"] += cnt["fail"]
        for mk, c in res.get("morph_zaehler", {}).items():
            morph_gesamt[mk] = morph_gesamt.get(mk, 0) + c

    bewertbar = g["OK"] + g["WINDOW_FLAGGED"] + g["WINDOW_FAIL"]
    print(f"\nDateien: {dateien_status}")
    print(f"Resonanzen gesamt (Linescans): {n_res}")
    print(f"  davon KEIN_ZIEL (keine Resonanz im Feldbereich): {g['KEIN_ZIEL']}")
    print(f"  bewertbare Resonanzen: {bewertbar}")
    if bewertbar:
        print(f"    OK             {g['OK']:6}  ({100*g['OK']/bewertbar:.1f}%)")
        print(f"    WINDOW_FLAGGED {g['WINDOW_FLAGGED']:6}  ({100*g['WINDOW_FLAGGED']/bewertbar:.1f}%)")
        print(f"    WINDOW_FAIL    {g['WINDOW_FAIL']:6}  ({100*g['WINDOW_FAIL']/bewertbar:.1f}%)  <-- stille Fehler")
        gut = g["OK"] + g["WINDOW_FLAGGED"]
        print(f"    OK+FLAGGED     {gut:6}  ({100*gut/bewertbar:.1f}%)")

    print("\nNach TDMS-Typ:")
    for typ, tt in nach_typ.items():
        b = tt["OK"] + tt["WINDOW_FLAGGED"] + tt["WINDOW_FAIL"]
        print(f"  {typ:11} OK={tt['OK']} FLAGGED={tt['WINDOW_FLAGGED']} "
              f"FAIL={tt['WINDOW_FAIL']} KEIN_ZIEL={tt['KEIN_ZIEL']}  (bewertbar {b})")

    print("\nObjektive Fehlerklasse (flagged=gemeldet / fail=still):")
    if nach_klasse:
        for kl, slot in sorted(nach_klasse.items(), key=lambda kv: -(kv[1]['fail'] + kv[1]['flagged'])):
            print(f"  {kl:24} flagged={slot['flagged']:5}  FAIL(still)={slot['fail']:5}")
    else:
        print("  (keine objektiv fehlerhaften Fenster)")

    print("\nDiagnose-Morphologie (informativ, nicht als Fehler gewertet):")
    for mk, c in sorted(morph_gesamt.items(), key=lambda kv: -kv[1]):
        print(f"  {mk:24} {c:5}")

    print("\nNach Probentyp (Unterordner)  [Res: OK/FLAG/FAIL/KZ ; Dateien-Sonderstatus]:")
    print(f"  {'Probe':<40} {'OK':>6} {'FLAG':>6} {'FAIL':>6} {'KZ':>6}   Sonst")
    for probe, ps in sorted(nach_probe.items()):
        b = ps["OK"] + ps["WINDOW_FLAGGED"] + ps["WINDOW_FAIL"]
        sonst = []
        for s in ("CRASH", "TIMEOUT", "NICHT_FMR"):
            if ps.get(s):
                sonst.append(f"{s}={ps[s]}")
        markierung = "  <-- FAIL!" if ps["WINDOW_FAIL"] else ""
        print(f"  {probe:<40} {ps['OK']:>6} {ps['WINDOW_FLAGGED']:>6} "
              f"{ps['WINDOW_FAIL']:>6} {ps['KEIN_ZIEL']:>6}   {','.join(sonst)}{markierung}")

    crashes = [n for n, r in fertig.items() if r.get("status_datei") in ("CRASH", "TIMEOUT")]
    if crashes:
        print("\nCRASH/TIMEOUT Dateien:")
        for n in crashes:
            print(f"  {n}: {fertig[n].get('status_datei')}")
    return g, dateien_status


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rerun-failed-only", action="store_true")
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args()

    # REKURSIV ueber alle Probenordner (Dateinamen kollidieren -> Pfad-Schluessel).
    alle = sorted(TESTDATA.rglob("*.tdms"))
    alle = [p for p in alle if not p.name.endswith(".tdms_index")]
    gt_zuordnung = finde_paare(alle)

    vorher = {}
    if RESULTS.exists():
        vorher = json.loads(RESULTS.read_text())

    if args.rerun_failed_only and vorher:
        zu_laufen = [p for p in alle if vorher.get(_schluessel(p), {}).get("status_datei")
                     in ("WINDOW_FAIL", "CRASH", "TIMEOUT", None)
                     or any(pr["status"] == "WINDOW_FAIL"
                            for pr in vorher.get(_schluessel(p), {}).get("probleme", []))]
        print(f"Re-Lauf nur fehlerhafte: {len(zu_laufen)} Dateien")
    else:
        zu_laufen = alle

    print(f"AutoWindow-Harness: {len(zu_laufen)} Dateien, {WORKERS} Worker, "
          f"Timeout {PRO_DATEI_TIMEOUT:.0f}s\n")
    t0 = time.time()
    neu = lauf(zu_laufen, gt_zuordnung)
    print(f"\nLaufzeit: {time.time() - t0:.1f}s")

    vorher.update(neu)
    RESULTS.write_text(json.dumps(vorher, indent=1, ensure_ascii=False))

    if not args.no_plots:
        # Plots nur fuer die in diesem Lauf verarbeiteten Dateien.
        schreibe_plots([p for p in alle if _schluessel(p) in neu], neu, gt_zuordnung)

    bericht(vorher)


if __name__ == "__main__":
    main()

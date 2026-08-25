# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Einfacher Benchmark: PolderFit minus LabVIEW-FTF je Frequenz - ohne Statistik.

Fuer jeden Datensatz in ``benchmark_ftf/data/<name>/`` (TDMS + FTF-Ergebnis
``ftf/Resonance Fit.dat``) wird PolderFit mit den GUI-Standardparametern
gefittet und je Frequenz direkt verglichen:

* Resonanzfeld   B_res(PF) und B_res(FTF), Differenz in mT
* Linienbreite   µ0ΔH(PF) und µ0ΔH(FTF), Differenz in mT und in %
* globale Kittel/LLG-Parameter (g, µ0M_eff, µ0H_u, α, µ0ΔH_0): PF vs. FTF, Differenz

Keine Fehlerbalken, keine z-Scores, keine Verteilungen - nur Werte, Differenzen
und als einzige Kennzahl je Datensatz der Median der Differenz (die "typische
Abweichung"). Verglichen werden nur Frequenzen, an denen BEIDE Programme ein
Ergebnis liefern (PF nicht problematisch, FTF mit gueltigem Hres/dH); die
uebrigen Punkte sind in den Uebersichtsplots hohl dargestellt.

Darstellung wie in der PolderFit-GUI: **Feld auf der x-Achse, Frequenz auf der
y-Achse** (Dispersion); Differenzen werden ueber dem Resonanzfeld aufgetragen,
die zugehoerige Frequenz steht als obere Zusatzachse daran.

Ausgabe: ein EIGENSTAENDIGER, datierter Ordner ``benchmark_ftf/einfacher_vergleich_<Datum>/``
(unabhaengig von den aelteren, ausfuehrlichen Ergebnissen unter ``ergebnisse/``) mit
je Messung einem PNG (vier Teilbilder) und einer CSV-Tabelle, dazu ``uebersicht.png``
(alle Messungen), ``kittel_llg.png``, ``kennzahlen.json``, dem Bericht
``VERGLEICH_EINFACH.md`` und ``Vergleich_PolderFit_FTF.pdf`` (alle Abbildungen).

Aufruf:  python benchmark_ftf/einfacher_vergleich.py [--ordner PFAD] [name ...]
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

HIER = Path(__file__).resolve().parent
WURZEL = HIER.parent
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(HIER))

from run_benchmark import lies_ftf_kittel, lies_ftf_tabelle  # noqa: E402
from polderfit import PROGRAMMNAME  # noqa: E402
from polderfit.auswertung.uebersicht import auswertung_kittel_llg  # noqa: E402
from polderfit.fit.batch import fitte_alle  # noqa: E402
from polderfit.io.tdms_laden import lade_tdms  # noqa: E402
from polderfit.physik.konstanten import GAMMA_STANDARD  # noqa: E402

DATA = HIER / "data"
#: Eigener, datierter Ergebnisordner (per ``--ordner`` ueberschreibbar).
OUT = HIER / f"einfacher_vergleich_{date.today().isoformat()}"
BERICHT = OUT / "VERGLEICH_EINFACH.md"

# Farben wie in der GUI (DIN EN 60073-Semantik: gruen = PolderFit-Ergebnis,
# neutral dunkelblau = Differenz); FTF in Dunkelorange (Serienfarbe, keine Statusbedeutung).
F_PF = "#2E9E4F"
F_FTF = "#B35C00"
F_DIFF = "#174A96"
F_AUS = "#8C8F94"

#: Datensatzspezifische Fit-Optionen (nur wo die GUI-Standardwerte physikalisch
#: nicht passen: FeCr2S4 hat alpha ~ 0.2-0.8 -> alpha-Obergrenze anheben, siehe BERICHT.md).
OPTIONEN = {
    "fecr2s4_2K": {"alpha_max": 1.0},
    "fecr2s4_50K": {"alpha_max": 1.0},
    "fecr2s4_100K": {"alpha_max": 1.0},
}

#: Verstaendliche Namen der Messungen (Ordnerkuerzel nur intern).
BESCHREIBUNG = {
    "cofe_wm_ip_290K_1": "CoFe-Schicht, 290 K, Feld in der Ebene, 20–66 GHz",
    "cofe_wm_ip_290K_2": "CoFe-Schicht, 290 K, Feld in der Ebene, 6–19 GHz",
    "cofe_wm_ip_5K_1": "CoFe-Schicht, 5 K, Feld in der Ebene, 20–66 GHz",
    "cofe_wm_ip_5K_2": "CoFe-Schicht, 5 K, Feld in der Ebene, 6–19 GHz",
    "cofe_gratings_ip_5K": "CoFe mit Gitterstruktur (138 nm), 5 K, Feld in der Ebene",
    "yig_konstanz_ip_50K": "YIG-Schicht (180 nm), 50 K, Feld in der Ebene",
    "fecr2s4_2K": "FeCr₂S₄-Kristall, 2 K, Feld senkrecht (Dämpfung α bis 1,0 erlaubt)",
    "fecr2s4_50K": "FeCr₂S₄-Kristall, 50 K, Feld senkrecht (Dämpfung α bis 1,0 erlaubt)",
    "fecr2s4_100K": "FeCr₂S₄-Kristall, 100 K, Feld senkrecht (Dämpfung α bis 1,0 erlaubt)",
}
#: Kurzname fuer Achsenbeschriftungen/Uebersicht.
KURZNAME = {
    "cofe_wm_ip_290K_1": "CoFe 290 K (20–66 GHz)",
    "cofe_wm_ip_290K_2": "CoFe 290 K (6–19 GHz)",
    "cofe_wm_ip_5K_1": "CoFe 5 K (20–66 GHz)",
    "cofe_wm_ip_5K_2": "CoFe 5 K (6–19 GHz)",
    "cofe_gratings_ip_5K": "CoFe-Gitter 5 K",
    "yig_konstanz_ip_50K": "YIG 50 K",
    "fecr2s4_2K": "FeCr₂S₄ 2 K",
    "fecr2s4_50K": "FeCr₂S₄ 50 K",
    "fecr2s4_100K": "FeCr₂S₄ 100 K",
}
GEOMETRIE_TEXT = {"ip": "Feld in der Ebene", "oop": "Feld senkrecht zur Schicht"}


def vergleiche_datensatz(ordner: Path) -> dict:
    name = ordner.name
    tdms = sorted(ordner.glob("*.tdms"))[0]
    ftf = lies_ftf_tabelle(ordner / "ftf" / "Resonance Fit.dat")
    kittel_dateien = sorted((ordner / "ftf").glob("*Kittel*"))
    ftf_kit = lies_ftf_kittel(kittel_dateien[0]) if kittel_dateien else None
    geometrie = ftf_kit["geometrie"] if ftf_kit else "oop"
    opt = OPTIONEN.get(name, {})
    print(f"\n=== {name} ({tdms.name}), Geometrie {geometrie}, Optionen {opt}", flush=True)

    t0 = time.time()
    daten = lade_tdms(str(tdms))
    stapel = fitte_alle(daten, gamma=GAMMA_STANDARD, alpha_max=opt.get("alpha_max", 0.1))
    t_fit = time.time() - t0
    print(f"  PolderFit: {len(stapel.ergebnisse)} Fits in {t_fit:.0f} s", flush=True)

    # --- je Frequenz zuordnen (Toleranz 2 MHz) ---------------------------------
    f_ftf = np.asarray(ftf["f (GHz)"], dtype=float)
    zeilen = []
    for e in stapel.ergebnisse:
        f_ghz = e.frequenz / 1e9
        j = int(np.argmin(np.abs(f_ftf - f_ghz)))
        if abs(f_ftf[j] - f_ghz) > 2e-3:
            continue
        b_ftf, dh_ftf = float(ftf["Hres1"][j]), float(ftf["dH1"][j])
        # FTF-Ergebnis gilt als vorhanden, wenn Hres und dH endlich und dH nicht
        # praktisch null ist (dH < 0,01 mT = kein sinnvoller Fit; sonst explodiert die %-Differenz).
        ftf_ok = (np.isfinite(b_ftf) and b_ftf != 0.0 and np.isfinite(dh_ftf) and dh_ftf > 1e-5)
        pf_ok = bool(e.erfolg and not e.problematisch and np.isfinite(e.B_res))
        zeilen.append({
            "f_GHz": f_ghz,
            "B_res_PF_T": e.B_res, "B_res_FTF_T": b_ftf,
            "dH_PF_mT": e.dH * 1e3, "dH_FTF_mT": dh_ftf * 1e3,
            "alpha_PF": e.alpha,
            "PF_ok": pf_ok, "FTF_ok": bool(ftf_ok), "beide_ok": pf_ok and bool(ftf_ok),
            "PF_status": "gut" if pf_ok else e.problem_text,
        })
    for z in zeilen:
        z["dB_res_mT"] = (z["B_res_PF_T"] - z["B_res_FTF_T"]) * 1e3 if z["beide_ok"] else np.nan
        z["ddH_mT"] = (z["dH_PF_mT"] - z["dH_FTF_mT"]) if z["beide_ok"] else np.nan
        z["ddH_prozent"] = (z["ddH_mT"] / z["dH_FTF_mT"] * 100.0
                            if z["beide_ok"] and z["dH_FTF_mT"] else np.nan)

    # CSV je Datensatz
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(zeilen[0].keys()))
        w.writeheader()
        w.writerows(zeilen)

    T = {k: np.array([z[k] for z in zeilen]) for k in zeilen[0]}
    beide = T["beide_ok"].astype(bool)
    n_beide = int(beide.sum())
    kenn = {
        "name": name, "beschreibung": BESCHREIBUNG.get(name, name), "geometrie": geometrie,
        "n_pf": len(stapel.ergebnisse), "n_zugeordnet": len(zeilen), "n_beide_ok": n_beide,
        "n_pf_problematisch": int((~T["PF_ok"].astype(bool)).sum()),
        "n_ftf_ohne_ergebnis": int((~T["FTF_ok"].astype(bool)).sum()),
        "t_fit_s": t_fit,
    }
    if n_beide:
        dB = T["dB_res_mT"][beide]
        ddh = T["ddH_mT"][beide]
        rel = T["ddH_prozent"][beide]
        kenn.update({
            "median_dB_mT": float(np.median(dB)), "max_abs_dB_mT": float(np.max(np.abs(dB))),
            "anteil_dB_unter_1mT": float(np.mean(np.abs(dB) <= 1.0)),
            "median_ddH_mT": float(np.median(ddh)), "median_ddH_prozent": float(np.median(rel)),
            "anteil_ddH_unter_5prozent": float(np.mean(np.abs(rel) <= 5.0)),
            "anteil_ddH_unter_10prozent": float(np.mean(np.abs(rel) <= 10.0)),
        })
        print(f"  {n_beide} Frequenzen in beiden Programmen: B_res-Differenz Median "
              f"{kenn['median_dB_mT']:+.3f} mT, ΔH-Differenz Median {kenn['median_ddH_mT']:+.3f} mT "
              f"({kenn['median_ddH_prozent']:+.1f} %)", flush=True)

    # --- Kittel/LLG global ----------------------------------------------------
    kittel = {}
    try:
        info = auswertung_kittel_llg(stapel.ergebnisse_aktiv(), geometrie=geometrie,
                                     gamma_start=GAMMA_STANDARD, gewichtet=False)
        kit, llg = info["kittel"], info["llg"]
        kittel["PF"] = {"g": kit["g_faktor"], "mu0Meff_T": kit["mu0Meff"],
                        "mu0Hu_mT": kit["mu0Hu"] * 1e3 if "mu0Hu" in kit else np.nan,
                        "alpha": llg["alpha"], "mu0dH0_mT": llg["mu0Hinh"] * 1e3,
                        "n": int(info["frequenz_Hz"].size)}
    except Exception as exc:  # noqa: BLE001
        kittel["PF"] = {"fehler": str(exc)}
    if ftf_kit:
        # FTF definiert oop "M eff" mit umgekehrtem Vorzeichen (B_res = ω/γ − M);
        # fuer den Vergleich in PolderFit-Konvention (B_res = µ0M_eff + ω/γ) umrechnen.
        meff_ftf = -ftf_kit["mu0Meff"] if geometrie == "oop" else ftf_kit["mu0Meff"]
        kittel["FTF"] = {"g": ftf_kit["g"], "mu0Meff_T": meff_ftf,
                         "mu0Hu_mT": ftf_kit["mu0Hu"] * 1e3 if "mu0Hu" in ftf_kit else np.nan,
                         "alpha": ftf_kit["alpha"], "mu0dH0_mT": ftf_kit["mu0Hinh"] * 1e3}
    kenn["kittel"] = kittel

    # --- Abbildung je Datensatz ------------------------------------------------
    fig = zeichne_datensatz(name, kenn, T)
    fig.savefig(OUT / f"{name}.png", dpi=150)
    kenn["fig"] = fig
    return kenn


def _prozent_grenzen(ax, werte, grenze=200.0):
    """y-Achse einer %-Differenz auf die Werte innerhalb +-grenze beschraenken;
    Punkte ausserhalb werden am Rand angedeutet (Anzahl im Titel)."""
    werte = np.asarray(werte, dtype=float)
    werte = werte[np.isfinite(werte)]
    if werte.size == 0:
        return 0
    drin = werte[np.abs(werte) <= grenze]
    aussen = int(werte.size - drin.size)
    if drin.size:
        lim = max(1.0, 1.15 * float(np.max(np.abs(drin))))
        ax.set_ylim(-lim, lim)
    if aussen:
        ax.set_title(ax.get_title() + f"  ({aussen} Punkt(e) außerhalb ±{grenze:.0f} %)", fontsize=9)
    return aussen


def _frequenzachse_oben(ax, b_feld, f_ghz):
    """Obere Zusatzachse mit der Frequenz zum Resonanzfeld (nur wenn B_res(f) monoton)."""
    b_feld = np.asarray(b_feld, dtype=float)
    f_ghz = np.asarray(f_ghz, dtype=float)
    m = np.isfinite(b_feld) & np.isfinite(f_ghz)
    if m.sum() < 3:
        return
    reihe = np.argsort(f_ghz[m])
    f_s, b_s = f_ghz[m][reihe], b_feld[m][reihe]
    if not np.all(np.diff(b_s) > 0):
        return
    sek = ax.secondary_xaxis("top", functions=(lambda b: np.interp(b, b_s, f_s),
                                               lambda f: np.interp(f, f_s, b_s)))
    sek.set_xlabel("Frequenz (GHz)", fontsize=8)
    sek.tick_params(labelsize=8)


def zeichne_datensatz(name: str, kenn: dict, T: dict):
    """Vier Teilbilder, Feld stets auf der x-Achse (wie in der GUI)."""
    f = T["f_GHz"]
    beide = T["beide_ok"].astype(bool)
    pf_ok = T["PF_ok"].astype(bool)
    ftf_ok = T["FTF_ok"].astype(bool)
    b_ftf = T["B_res_FTF_T"]
    b_pf = T["B_res_PF_T"]
    fig, axs = plt.subplots(2, 2, figsize=(13, 9.5))
    fig.suptitle(f"{kenn['beschreibung']}\nPolderFit (grün) und LabVIEW-FTF (orange); "
                 f"unten: PolderFit minus FTF", fontsize=13)

    # Dispersion: Resonanzfeld (x) gegen Frequenz (y).
    ax = axs[0, 0]
    ax.plot(b_ftf[ftf_ok], f[ftf_ok], "s", ms=6, mfc="none", mec=F_FTF, mew=1.3, label="LabVIEW-FTF")
    ax.plot(b_pf[pf_ok], f[pf_ok], "o", ms=4, color=F_PF, label="PolderFit")
    if (~pf_ok).any():
        ax.plot(b_pf[~pf_ok], f[~pf_ok], "^", ms=5, mfc="none", mec=F_AUS,
                label="PolderFit: problematisch (nicht verglichen)")
    ax.set_xlabel("Resonanzfeld µ₀H_res (T)")
    ax.set_ylabel("Frequenz (GHz)")
    ax.set_title("Resonanzfeld je Frequenz")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # Linienbreite ueber dem Resonanzfeld.
    ax = axs[0, 1]
    ax.plot(b_ftf[ftf_ok], T["dH_FTF_mT"][ftf_ok], "s", ms=6, mfc="none", mec=F_FTF, mew=1.3,
            label="LabVIEW-FTF")
    ax.plot(b_pf[pf_ok], T["dH_PF_mT"][pf_ok], "o", ms=4, color=F_PF, label="PolderFit")
    if (~pf_ok).any():
        ax.plot(b_pf[~pf_ok], T["dH_PF_mT"][~pf_ok], "^", ms=5, mfc="none", mec=F_AUS,
                label="PolderFit: problematisch")
    ax.set_xlabel("Resonanzfeld µ₀H_res (T)")
    ax.set_ylabel("Linienbreite µ₀ΔH (mT)")
    ax.set_title("Linienbreite über dem Resonanzfeld")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    _frequenzachse_oben(ax, b_ftf[ftf_ok], f[ftf_ok])

    # Differenzen ueber dem Feld (Frequenz oben).
    ax = axs[1, 0]
    ax.axhline(0, color="k", lw=1)
    ax.plot(b_ftf[beide], T["dB_res_mT"][beide], "o", ms=4, color=F_DIFF)
    if beide.any():
        med = kenn["median_dB_mT"]
        ax.axhline(med, color=F_DIFF, lw=1, ls="--")
        ax.text(0.02, 0.95, f"typisch (Median): {med:+.3f} mT\n"
                f"|Differenz| ≤ 1 mT bei {kenn['anteil_dB_unter_1mT']*100:.0f} % der Frequenzen",
                transform=ax.transAxes, va="top", fontsize=9,
                bbox=dict(facecolor="white", edgecolor=F_DIFF, alpha=0.9))
    ax.set_xlabel("Resonanzfeld µ₀H_res (T, FTF)")
    ax.set_ylabel("B_res(PolderFit) − B_res(FTF)  (mT)")
    ax.set_title("Differenz Resonanzfeld")
    ax.grid(alpha=0.3)
    _frequenzachse_oben(ax, b_ftf[beide], f[beide])

    ax = axs[1, 1]
    ax.axhline(0, color="k", lw=1)
    ax.plot(b_ftf[beide], T["ddH_prozent"][beide], "o", ms=4, color=F_DIFF)
    if beide.any():
        med = kenn["median_ddH_prozent"]
        ax.axhline(med, color=F_DIFF, lw=1, ls="--")
        ax.text(0.02, 0.95, f"typisch (Median): {kenn['median_ddH_mT']:+.3f} mT = {med:+.1f} %\n"
                f"|Differenz| ≤ 5 % bei {kenn['anteil_ddH_unter_5prozent']*100:.0f} % der Frequenzen",
                transform=ax.transAxes, va="top", fontsize=9,
                bbox=dict(facecolor="white", edgecolor=F_DIFF, alpha=0.9))
    ax.set_xlabel("Resonanzfeld µ₀H_res (T, FTF)")
    ax.set_ylabel("ΔH(PolderFit) / ΔH(FTF) − 1  (%)")
    ax.set_title("Differenz Linienbreite (relativ)")
    _prozent_grenzen(ax, T["ddH_prozent"][beide])
    ax.grid(alpha=0.3)
    _frequenzachse_oben(ax, b_ftf[beide], f[beide])

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


def zeichne_uebersicht(alle: list[dict]):
    """Kleine Vielfache: Differenzen aller Datensaetze auf einen Blick."""
    gueltig = [k for k in alle if "T" in k and k.get("n_beide_ok")]
    n = len(gueltig)
    if n == 0:
        return None
    fig, axs = plt.subplots(n, 2, figsize=(12, 2.6 * n), squeeze=False)
    fig.suptitle("PolderFit minus LabVIEW-FTF über dem Resonanzfeld – alle Messungen", fontsize=13)
    for zeile, k in enumerate(gueltig):
        T = k["T"]
        beide = T["beide_ok"].astype(bool)
        b = T["B_res_FTF_T"][beide]
        kurz = KURZNAME.get(k["name"], k["name"])
        ax = axs[zeile, 0]
        ax.axhline(0, color="k", lw=0.8)
        ax.plot(b, T["dB_res_mT"][beide], "o", ms=3, color=F_DIFF)
        ax.set_ylabel("ΔB_res (mT)")
        ax.set_title(f"{kurz} – Resonanzfeld, typisch {k['median_dB_mT']:+.2f} mT", fontsize=9)
        ax.grid(alpha=0.3)
        ax = axs[zeile, 1]
        ax.axhline(0, color="k", lw=0.8)
        ax.plot(b, T["ddH_prozent"][beide], "o", ms=3, color=F_DIFF)
        ax.set_ylabel("ΔΔH (%)")
        ax.set_title(f"{kurz} – Linienbreite, typisch {k['median_ddH_prozent']:+.1f} %", fontsize=9)
        _prozent_grenzen(ax, T["ddH_prozent"][beide])
        ax.grid(alpha=0.3)
        if zeile == n - 1:
            axs[zeile, 0].set_xlabel("Resonanzfeld µ₀H_res (T)")
            axs[zeile, 1].set_xlabel("Resonanzfeld µ₀H_res (T)")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    return fig


def zeichne_kittel(alle: list[dict]):
    """Globale Parameter PF vs. FTF je Datensatz (Punktpaare)."""
    gueltig = [k for k in alle if "kittel" in k and "FTF" in k["kittel"] and "fehler" not in k["kittel"]["PF"]]
    if not gueltig:
        return None
    groessen = [("g", "g-Faktor", 1.0), ("mu0Meff_T", "effektive Magnetisierung µ₀M_eff (T)", 1.0),
                ("alpha", "Dämpfung α", 1.0), ("mu0dH0_mT", "Linienbreite bei f = 0, µ₀ΔH₀ (mT)", 1.0)]
    fig, axs = plt.subplots(1, 4, figsize=(15, 4.6))
    fig.suptitle("Kittel/LLG-Parameter: PolderFit (grün) und LabVIEW-FTF (orange) je Messung", fontsize=12)
    x = np.arange(len(gueltig))
    for ax, (key, titel, _s) in zip(axs, groessen):
        pf = np.array([k["kittel"]["PF"].get(key, np.nan) for k in gueltig], dtype=float)
        ft = np.array([k["kittel"]["FTF"].get(key, np.nan) for k in gueltig], dtype=float)
        ax.plot(x, ft, "s", ms=8, mfc="none", mec=F_FTF, mew=1.5, label="FTF")
        ax.plot(x, pf, "o", ms=6, color=F_PF, label="PolderFit")
        for xi, a, b in zip(x, pf, ft):
            if np.isfinite(a) and np.isfinite(b):
                ax.plot([xi, xi], [a, b], "-", color=F_AUS, lw=1, zorder=0)
        ax.set_xticks(x)
        ax.set_xticklabels([KURZNAME.get(k["name"], k["name"]) for k in gueltig],
                           rotation=60, ha="right", fontsize=8)
        ax.set_title(titel)
        ax.grid(alpha=0.3)
    axs[0].legend(fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


def schreibe_bericht(alle: list[dict]) -> None:
    z = []
    z.append(f"# Einfacher Vergleich {PROGRAMMNAME} – LabVIEW-FTF (Stand {date.today().isoformat()})\n")
    z.append("Je Frequenz werden die Einzelfit-Werte beider Programme direkt verglichen: "
             "**PolderFit minus FTF** für Resonanzfeld und Linienbreite, dazu die globalen "
             "Kittel/LLG-Parameter. Keine Fehlerbalken, keine Verteilungen – nur Werte und "
             "Differenzen; die einzige Kennzahl ist der Median der Differenz („typische Abweichung“) "
             "und der Anteil der Frequenzen innerhalb ±1 mT (Feld) bzw. ±5 % (Linienbreite). "
             "Verglichen werden Frequenzen, an denen beide Programme ein Ergebnis liefern.\n")
    z.append("PolderFit lief mit den Standardwerten der Oberfläche (Auto-Fit; zweiter Fit-Durchgang "
             "auf ±2,5 Linienbreiten; Dämpfung α im Fit bis 0,1 erlaubt, bei FeCr₂S₄ bis 1,0). "
             "Alle Abbildungen wie in der Oberfläche: **Feld auf der x-Achse, Frequenz auf der "
             "y-Achse** bzw. als obere Zusatzachse. Hinweis: Die FTF-Referenzen stammen aus "
             "umsortierten Frequenz-Sweeps (siehe `BERICHT.md`, Abschnitt 1).\n")
    z.append("Dieser Ordner ist eigenständig (unabhängig von den älteren, ausführlichen Ergebnissen "
             "unter `../ergebnisse/`): `<Kürzel>.png` (je Messung), `uebersicht.png`, `kittel_llg.png`, "
             "alles zusammen in `Vergleich_PolderFit_FTF.pdf`; Werte je Frequenz in `<Kürzel>.csv`, "
             "Kennzahlen in `kennzahlen.json`. Erzeugt mit `python benchmark_ftf/einfacher_vergleich.py`. "
             "Kürzel ↔ Messung: Tabelle am Ende.\n")
    z.append("## Begriffe\n")
    z.append("| Begriff | Bedeutung |\n|---|---|\n"
             "| Resonanzfeld B_res | Feld µ₀H (Tesla), bei dem die Resonanz liegt – je Frequenz ein Wert |\n"
             "| Linienbreite µ₀ΔH | volle Breite der Resonanz (mT) |\n"
             "| Dämpfung α | Gilbert-Dämpfung (dimensionslos); Steigung der Linienbreite über der Frequenz |\n"
             "| µ₀M_eff, µ₀H_u, µ₀ΔH₀ | effektive Magnetisierung, Anisotropiefeld, Linienbreite bei f = 0 (Kittel/LLG) |\n"
             "| Feld in der Ebene / senkrecht | Messgeometrie: Magnetfeld parallel zur Schicht (ip) bzw. senkrecht dazu (oop) |\n"
             "| typische Differenz | Median aller Differenzen PolderFit − FTF (Ausreißer verzerren ihn nicht) |\n"
             "| FTF | LabVIEW-Auswerteprogramm „fiddling together FMR“ (Referenz) |\n")
    z.append("## Einzelfits je Frequenz\n")
    z.append("| Messung | Frequenzen verglichen | B_res: typische Differenz | B_res innerhalb ±1 mT | "
             "ΔH: typische Differenz | ΔH innerhalb ±5 % | ΔH innerhalb ±10 % |")
    z.append("|---|---|---|---|---|---|---|")
    for k in alle:
        if "fehler" in k:
            z.append(f"| {k['name']} | Fehler: {k['fehler']} | | | | | |")
            continue
        if not k.get("n_beide_ok"):
            z.append(f"| {k['beschreibung']} | 0 von {k['n_zugeordnet']} | – | – | – | – | – |")
            continue
        z.append(f"| {k['beschreibung']} | {k['n_beide_ok']} von {k['n_zugeordnet']} "
                 f"(PF problematisch {k['n_pf_problematisch']}, FTF ohne Ergebnis {k['n_ftf_ohne_ergebnis']}) "
                 f"| {k['median_dB_mT']:+.3f} mT | {k['anteil_dB_unter_1mT']*100:.0f} % "
                 f"| {k['median_ddH_mT']:+.3f} mT ({k['median_ddH_prozent']:+.1f} %) "
                 f"| {k['anteil_ddH_unter_5prozent']*100:.0f} % | {k['anteil_ddH_unter_10prozent']*100:.0f} % |")
    z.append("\n![Übersicht](uebersicht.png)\n")
    z.append("## Kittel/LLG-Parameter\n")
    z.append("PolderFit ungewichtet (Standard). FTF-„M eff“ bei senkrechtem Feld ist in die "
             "PolderFit-Konvention umgerechnet (Vorzeichen; FTF: B_res = ω/γ − M). FeCr₂S₄: die "
             "automatische Fenstersuche ist für Linienbreiten ≳ 0,3 T nicht ausgelegt, viele "
             "PolderFit-Einzelfits sind dort problematisch (siehe `BERICHT.md`); die Werte sind "
             "entsprechend zu lesen.\n")
    z.append("| Messung | g PF / FTF (Diff.) | µ₀M_eff PF / FTF (T) | µ₀H_u PF / FTF (mT) | α PF / FTF (Diff.) | µ₀ΔH₀ PF / FTF (mT) |")
    z.append("|---|---|---|---|---|---|")

    def paar(a, b, fmt, rel=False):
        if a is None or b is None or not (np.isfinite(a) and np.isfinite(b)):
            return "–"
        d = f" ({(a - b) / abs(b) * 100:+.1f} %)" if rel and b else f" ({a - b:+{fmt}})"
        return f"{a:{fmt}} / {b:{fmt}}{d}"

    for k in alle:
        kit = k.get("kittel", {})
        if "fehler" in k or "FTF" not in kit or "fehler" in kit.get("PF", {}):
            continue
        pf, ft = kit["PF"], kit["FTF"]
        hinweis = " ⚠ FTF-Kittel-Fit an seiner Grenze (g = 4,000) – FTF-Werte unbrauchbar" \
            if abs(ft["g"] - 4.0) < 1e-6 else ""
        z.append(f"| {k['beschreibung']}{hinweis} | {paar(pf['g'], ft['g'], '.4f')} "
                 f"| {paar(pf['mu0Meff_T'], ft['mu0Meff_T'], '.4f')} "
                 f"| {paar(pf['mu0Hu_mT'], ft['mu0Hu_mT'], '.2f')} "
                 f"| {paar(pf['alpha'], ft['alpha'], '.2e', rel=True)} "
                 f"| {paar(pf['mu0dH0_mT'], ft['mu0dH0_mT'], '.2f')} |")
    z.append("\n![Kittel/LLG](kittel_llg.png)\n")
    z.append("## Abbildungen je Messung\n")
    for k in alle:
        if "fehler" in k:
            continue
        z.append(f"### {k['beschreibung']}\n")
        z.append(f"![{k['name']}]({k['name']}.png)\n")
    z.append("## Kürzel der Ordner und Dateien\n")
    z.append("| Kürzel (Ordner/Datei) | Messung |\n|---|---|")
    for k in alle:
        z.append(f"| `{k['name']}` | {k.get('beschreibung', k['name'])} |")
    BERICHT.write_text("\n".join(z) + "\n", encoding="utf-8")


def main(argv):
    global OUT, BERICHT
    rest = []
    it = iter(argv[1:])
    for a in it:
        if a == "--ordner":
            OUT = Path(next(it)).resolve()
            BERICHT = OUT / "VERGLEICH_EINFACH.md"
        else:
            rest.append(a)
    OUT.mkdir(parents=True, exist_ok=True)
    namen = rest or sorted(p.name for p in DATA.iterdir() if p.is_dir())
    alle = []
    for n in namen:
        try:
            k = vergleiche_datensatz(DATA / n)
            # Rohtabelle fuer die Uebersicht mitnehmen.
            with open(OUT / f"{n}.csv", encoding="utf-8") as fh:
                zeilen = list(csv.DictReader(fh))
            k["T"] = {
                "f_GHz": np.array([float(r["f_GHz"]) for r in zeilen]),
                "B_res_FTF_T": np.array([float(r["B_res_FTF_T"]) for r in zeilen]),
                "beide_ok": np.array([r["beide_ok"] == "True" for r in zeilen]),
                "dB_res_mT": np.array([float(r["dB_res_mT"]) for r in zeilen]),
                "ddH_prozent": np.array([float(r["ddH_prozent"]) for r in zeilen]),
            }
            alle.append(k)
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            alle.append({"name": n, "fehler": repr(exc)})
    fig_u = zeichne_uebersicht(alle)
    fig_k = zeichne_kittel(alle)
    with PdfPages(OUT / "Vergleich_PolderFit_FTF.pdf") as pdf:
        if fig_u is not None:
            fig_u.savefig(OUT / "uebersicht.png", dpi=150)
            pdf.savefig(fig_u)
        if fig_k is not None:
            fig_k.savefig(OUT / "kittel_llg.png", dpi=150)
            pdf.savefig(fig_k)
        for k in alle:
            if "fig" in k:
                pdf.savefig(k["fig"])
                plt.close(k["fig"])
    for k in alle:
        k.pop("fig", None)
        k.pop("T", None)
    with open(OUT / "kennzahlen.json", "w", encoding="utf-8") as fh:
        json.dump(alle, fh, indent=1, ensure_ascii=False,
                  default=lambda o: o.item() if hasattr(o, "item") else str(o))
    schreibe_bericht(alle)
    print(f"\nBericht: {BERICHT}\nAbbildungen/PDF: {OUT}")


if __name__ == "__main__":
    main(sys.argv)

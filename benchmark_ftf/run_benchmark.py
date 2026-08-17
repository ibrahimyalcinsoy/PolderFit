# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Benchmark PolderFit gegen bereits mit dem LabVIEW-Tool "FTF" ausgewertete Daten.

Je Datensatz (Ordner ``benchmark_ftf/data/<name>/``):
  * ``*.tdms``                       – dieselbe Rohdatei, die auch das FTF eingelesen hat
  * ``ftf/Resonance Fit.dat``        – FTF-Suszeptibilitaetsfit je Frequenz (Hres, dH, ...)
  * ``ftf/Resonance 1_Kittel+LLG Fit.dat`` – FTF-Kittel/LLG-Ergebnis (g, Meff, [Haniso], alpha, dH0)

Ablauf:
  1. PolderFit-Auto-Fit (``fitte_alle``, GUI-Standardparameter).
  2. Zuordnung der Einzelfits ueber die Frequenz; Vergleich von B_res und mu0*dH
     (Differenz, kombinierte 1σ-Unsicherheit, z-Score, relative Abweichung).
  3. Kittel-/LLG-Auswertung von PolderFit (gewichtet + ungewichtet) vs. FTF.
  4. Isolationstest: PolderFits Kittel/LLG-Fit auf die FTF-Einzelfitwerte
     (trennt Linienform-Fit-Unterschiede von Kittel-Fit-Unterschieden).
  5. Plots + CSV + JSON je Datensatz, Gesamtbericht als Markdown.

Konventionen: FTF ``dH`` ist laut "FTF Formula Document" die FWHM
(``dH/2 = alpha*omega/(mu0*gamma)``) in Tesla – identisch mit PolderFits ``dH``.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HIER = Path(__file__).resolve().parent
WURZEL = HIER.parent
sys.path.insert(0, str(WURZEL))

from polderfit.io.tdms_laden import lade_tdms  # noqa: E402
from polderfit.fit.batch import fitte_alle  # noqa: E402
from polderfit.auswertung.uebersicht import auswertung_kittel_llg  # noqa: E402
from polderfit.physik.kittel_llg import fit_kittel_ip, fit_kittel_oop, fit_linienbreite  # noqa: E402
from polderfit.physik.konstanten import GAMMA_STANDARD, gamma_aus_g  # noqa: E402

DATA = HIER / "data"
OUT = HIER / "ergebnisse"
OUT.mkdir(exist_ok=True)

#: Laufoptionen (per Kommandozeile setzbar, siehe ``main``).
OPTIONEN = {"alpha_max": 0.1, "nachfenster_faktor": 2.5, "suffix": ""}


# ---------------------------------------------------------------------------
# FTF-Dateien lesen
# ---------------------------------------------------------------------------
def lies_ftf_tabelle(pfad: Path) -> dict[str, np.ndarray]:
    with open(pfad, encoding="latin-1") as fh:
        kopf = fh.readline().rstrip("\n").split("\t")
        zeilen = [z.rstrip("\n").split("\t") for z in fh if z.strip()]
    werte = np.array([[float(x) if x.strip() else np.nan for x in z] for z in zeilen], dtype=float)
    return {k: werte[:, i] for i, k in enumerate(kopf)}


def lies_ftf_kittel(pfad: Path) -> dict[str, float]:
    t = lies_ftf_tabelle(pfad)
    d = {k: float(v[0]) for k, v in t.items()}
    out = {
        "g": d["g-factor"], "g_err": d["g-factor_error"],
        "mu0Meff": d["M eff (T)"], "mu0Meff_err": d["M eff (T)_error"],
        "alpha": d["gilbert-alpha"], "alpha_err": d["gilbert-alpha_error"],
        "mu0Hinh": d["deltaH0 (T)"], "mu0Hinh_err": d["deltaH0 (T)_error"],
        "g_llg": d["g-factor (used for LLG-Fit)"],
    }
    if "H aniso (T)" in d:
        out["mu0Hu"] = d["H aniso (T)"]
        out["mu0Hu_err"] = d["H aniso (T)_error"]
        out["geometrie"] = "ip"
    else:
        out["geometrie"] = "oop"
    return out


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------
def _z(a, ea, b, eb):
    s = np.sqrt(np.nan_to_num(ea, nan=0.0) ** 2 + np.nan_to_num(eb, nan=0.0) ** 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(s > 0, (a - b) / s, np.nan)


def _pf_kittel_auf(f, b, dh, geometrie, gamma_start, b_err=None, dh_err=None):
    """PolderFits Kittel-/LLG-Fitter auf beliebige (f, B_res, dH)-Punkte."""
    if geometrie == "ip":
        kit = fit_kittel_ip(f, b, gamma_start=gamma_start, B_res_err=b_err)
    else:
        kit = fit_kittel_oop(f, b, gamma_start=gamma_start, B_res_err=b_err)
    llg = fit_linienbreite(f, dh, gamma=kit["gamma"], gamma_err=kit["gamma_err"], mu0dH_err=dh_err)
    return {"kittel": kit, "llg": llg}


def _kittel_zeile(quelle, kit, llg):
    z = {
        "quelle": quelle,
        "g": kit["g_faktor"], "g_err": kit["g_faktor_err"],
        "mu0Meff": kit["mu0Meff"], "mu0Meff_err": kit["mu0Meff_err"],
        "alpha": llg["alpha"], "alpha_err": llg["alpha_err"],
        "mu0Hinh": llg["mu0Hinh"], "mu0Hinh_err": llg["mu0Hinh_err"],
        "n_punkte": None,
    }
    if "mu0Hu" in kit:
        z["mu0Hu"] = kit["mu0Hu"]
        z["mu0Hu_err"] = kit["mu0Hu_err"]
    return z


def _vergleich_kittel(pf: dict, ftf: dict) -> dict:
    """z-Scores und relative Abweichung fuer die globalen Parameter."""
    out = {}
    for k in ("g", "mu0Meff", "mu0Hu", "alpha", "mu0Hinh"):
        if k in pf and k in ftf and np.isfinite(pf[k]) and np.isfinite(ftf[k]):
            z = float(_z(pf[k], pf.get(k + "_err", np.nan), ftf[k], ftf.get(k + "_err", np.nan)))
            rel = (pf[k] - ftf[k]) / abs(ftf[k]) if ftf[k] != 0 else np.nan
            out[k] = {"pf": pf[k], "pf_err": pf.get(k + "_err"), "ftf": ftf[k],
                      "ftf_err": ftf.get(k + "_err"), "z": z, "rel": float(rel)}
    return out


# ---------------------------------------------------------------------------
# Ein Datensatz
# ---------------------------------------------------------------------------
def benchmark_datensatz(ordner: Path) -> dict:
    name = ordner.name + OPTIONEN["suffix"]
    tdms = sorted(ordner.glob("*.tdms"))[0]
    ftf_tab = lies_ftf_tabelle(ordner / "ftf" / "Resonance Fit.dat")
    kittel_dateien = sorted((ordner / "ftf").glob("*Kittel*"))
    ftf_kit = lies_ftf_kittel(kittel_dateien[0]) if kittel_dateien else None
    geometrie = ftf_kit["geometrie"] if ftf_kit else "oop"

    print(f"\n=== {name}  ({tdms.name})  Geometrie(FTF)={geometrie}", flush=True)
    t0 = time.time()
    daten = lade_tdms(str(tdms))
    stapel = fitte_alle(daten, gamma=GAMMA_STANDARD, breite_faktor=8.0, alpha_erwartet=0.01,
                        alpha_max=OPTIONEN["alpha_max"],
                        nachfenster_faktor=OPTIONEN["nachfenster_faktor"])
    t_fit = time.time() - t0
    erg = stapel.ergebnisse
    print(f"  PolderFit: {len(erg)} Fits in {t_fit:.1f}s, "
          f"{len(stapel.index_problematisch())} problematisch", flush=True)

    # --- Zuordnung ueber die Frequenz ---------------------------------------
    f_pf = np.array([e.frequenz for e in erg]) / 1e9
    f_ftf = ftf_tab["f (GHz)"]
    zeilen = []
    for i, e in enumerate(erg):
        j = int(np.argmin(np.abs(f_ftf - f_pf[i])))
        if abs(f_ftf[j] - f_pf[i]) > 2e-3:  # > 2 MHz -> keine Entsprechung
            continue
        h_ftf, h_ftf_e = ftf_tab["Hres1"][j], ftf_tab["Hres err1"][j]
        dh_ftf, dh_ftf_e = ftf_tab["dH1"][j], ftf_tab["dH err1"][j]
        ftf_ok = np.isfinite(h_ftf) and h_ftf != 0.0 and np.isfinite(dh_ftf) and dh_ftf > 0
        zeilen.append({
            "f_GHz": f_pf[i],
            "B_pf": e.B_res, "B_pf_err": e.B_res_err,
            "B_ftf": h_ftf, "B_ftf_err": h_ftf_e,
            "dH_pf": e.dH, "dH_pf_err": e.dH_err,
            "dH_ftf": dh_ftf, "dH_ftf_err": dh_ftf_e,
            "pf_problem": bool(e.problematisch), "pf_gruende": e.problem_text,
            "pf_rmse_norm": e.rmse_norm, "ftf_R2": ftf_tab["R-Square"][j],
            "ftf_ok": bool(ftf_ok),
            "B_fenster_min": e.B_fenster_min, "B_fenster_max": e.B_fenster_max,
        })
    if not zeilen:
        print("  !! keine Frequenz-Entsprechung", flush=True)
        return {"name": name, "fehler": "keine Zuordnung"}
    T = {k: np.array([z[k] for z in zeilen]) for k in zeilen[0]}
    T["dB"] = T["B_pf"] - T["B_ftf"]
    T["z_B"] = _z(T["B_pf"], T["B_pf_err"], T["B_ftf"], T["B_ftf_err"])
    T["ddH"] = T["dH_pf"] - T["dH_ftf"]
    T["z_dH"] = _z(T["dH_pf"], T["dH_pf_err"], T["dH_ftf"], T["dH_ftf_err"])
    with np.errstate(divide="ignore", invalid="ignore"):
        T["rel_dH"] = T["ddH"] / T["dH_ftf"]
        T["dB_in_dH"] = T["dB"] / T["dH_ftf"]  # Verschiebung in Einheiten der Linienbreite

    beide_ok = (~T["pf_problem"]) & T["ftf_ok"]
    n_gesamt = len(zeilen)
    n_pf_prob = int(T["pf_problem"].sum())
    n_ftf_fail = int((~T["ftf_ok"]).sum())

    def _stat(x, m):
        x = x[m]
        x = x[np.isfinite(x)]
        if x.size == 0:
            return {}
        return {"n": int(x.size), "median": float(np.median(x)),
                "mean": float(np.mean(x)), "std": float(np.std(x)),
                "p16": float(np.percentile(x, 16)), "p84": float(np.percentile(x, 84)),
                "max_abs": float(np.max(np.abs(x))),
                "anteil_abs_le_1": float(np.mean(np.abs(x) <= 1)),
                "anteil_abs_le_2": float(np.mean(np.abs(x) <= 2)),
                "anteil_abs_le_3": float(np.mean(np.abs(x) <= 3))}

    stat = {
        "n_zugeordnet": n_gesamt, "n_pf_problematisch": n_pf_prob, "n_ftf_fehlgeschlagen": n_ftf_fail,
        "n_beide_ok": int(beide_ok.sum()),
        "dB_T": _stat(T["dB"], beide_ok), "z_B": _stat(T["z_B"], beide_ok),
        "dB_in_dH": _stat(T["dB_in_dH"], beide_ok),
        "ddH_T": _stat(T["ddH"], beide_ok), "rel_dH": _stat(T["rel_dH"], beide_ok),
        "z_dH": _stat(T["z_dH"], beide_ok),
        "problem_statistik_pf": stapel.problem_statistik(),
    }
    print(f"  Zuordnung: {n_gesamt} Frequenzen, beide ok: {int(beide_ok.sum())}, "
          f"PF problematisch: {n_pf_prob}, FTF fehlgeschlagen: {n_ftf_fail}")
    if stat["dB_T"]:
        print(f"  B_res: median dB = {stat['dB_T']['median']*1e3:+.3f} mT "
              f"(p16..p84 {stat['dB_T']['p16']*1e3:+.3f}..{stat['dB_T']['p84']*1e3:+.3f}), "
              f"|z|<=2: {stat['z_B']['anteil_abs_le_2']*100:.0f}%, "
              f"dB/dH median {stat['dB_in_dH']['median']:+.3f}")
        print(f"  dH   : median rel = {stat['rel_dH']['median']*100:+.1f}% "
              f"(p16..p84 {stat['rel_dH']['p16']*100:+.1f}..{stat['rel_dH']['p84']*100:+.1f}), "
              f"|z|<=2: {stat['z_dH']['anteil_abs_le_2']*100:.0f}%")

    # --- Kittel / LLG ------------------------------------------------------
    kittel = {}
    gamma_start = GAMMA_STANDARD
    try:
        info_w = auswertung_kittel_llg(erg, geometrie=geometrie, gamma_start=gamma_start, gewichtet=True)
        z = _kittel_zeile("PolderFit (gewichtet)", info_w["kittel"], info_w["llg"])
        z["n_punkte"] = int(info_w["frequenz_Hz"].size)
        kittel["pf_gewichtet"] = z
    except Exception as ex:  # noqa: BLE001
        kittel["pf_gewichtet"] = {"fehler": repr(ex)}
    try:
        info_u = auswertung_kittel_llg(erg, geometrie=geometrie, gamma_start=gamma_start, gewichtet=False)
        z = _kittel_zeile("PolderFit (ungewichtet)", info_u["kittel"], info_u["llg"])
        z["n_punkte"] = int(info_u["frequenz_Hz"].size)
        kittel["pf_ungewichtet"] = z
    except Exception as ex:  # noqa: BLE001
        kittel["pf_ungewichtet"] = {"fehler": repr(ex)}
    # Isolationstest: PF-Fitter auf FTF-Punkte (alle gueltigen FTF-Einzelfits)
    m = T["ftf_ok"]
    try:
        r = _pf_kittel_auf(T["f_GHz"][m] * 1e9, T["B_ftf"][m], T["dH_ftf"][m], geometrie, gamma_start)
        z = _kittel_zeile("PF-Fitter auf FTF-Punkte (ungewichtet)", r["kittel"], r["llg"])
        z["n_punkte"] = int(m.sum())
        kittel["pf_fitter_auf_ftf"] = z
    except Exception as ex:  # noqa: BLE001
        kittel["pf_fitter_auf_ftf"] = {"fehler": repr(ex)}
    # und PF-Fitter auf FTF-Punkte, aber nur die, die PF auch fuer gut haelt (gleiche Punktmenge)
    try:
        r = _pf_kittel_auf(T["f_GHz"][beide_ok] * 1e9, T["B_ftf"][beide_ok], T["dH_ftf"][beide_ok],
                           geometrie, gamma_start)
        z = _kittel_zeile("PF-Fitter auf FTF-Punkte (Schnittmenge, ungew.)", r["kittel"], r["llg"])
        z["n_punkte"] = int(beide_ok.sum())
        kittel["pf_fitter_auf_ftf_schnitt"] = z
    except Exception as ex:  # noqa: BLE001
        kittel["pf_fitter_auf_ftf_schnitt"] = {"fehler": repr(ex)}
    # PF-Punkte (Schnittmenge) mit PF-Fitter, ungewichtet -> exakt gleiche Punktmenge wie oben
    try:
        r = _pf_kittel_auf(T["f_GHz"][beide_ok] * 1e9, T["B_pf"][beide_ok], T["dH_pf"][beide_ok],
                           geometrie, gamma_start)
        z = _kittel_zeile("PF-Punkte (Schnittmenge, ungew.)", r["kittel"], r["llg"])
        z["n_punkte"] = int(beide_ok.sum())
        kittel["pf_schnitt"] = z
    except Exception as ex:  # noqa: BLE001
        kittel["pf_schnitt"] = {"fehler": repr(ex)}

    vergleiche = {}
    if ftf_kit:
        kittel["ftf"] = dict(ftf_kit, quelle="FTF")
        for k, v in kittel.items():
            if k != "ftf" and "fehler" not in v:
                vergleiche[k] = _vergleich_kittel(v, ftf_kit)
        for k in ("pf_gewichtet", "pf_ungewichtet", "pf_fitter_auf_ftf", "pf_schnitt"):
            v = kittel.get(k, {})
            if "fehler" in v:
                print(f"  {k}: FEHLER {v['fehler'][:120]}")
                continue
            hu = f", Hu={v['mu0Hu']*1e3:+.2f}±{v['mu0Hu_err']*1e3:.2f} mT" if "mu0Hu" in v else ""
            print(f"  {k:26s}: g={v['g']:.4f}±{v['g_err']:.4f}, Meff={v['mu0Meff']:.4f}±{v['mu0Meff_err']:.4f} T{hu}, "
                  f"alpha={v['alpha']:.3e}±{v['alpha_err']:.1e}, dH0={v['mu0Hinh']*1e3:+.2f}±{v['mu0Hinh_err']*1e3:.2f} mT  (n={v['n_punkte']})")
        hu = f", Hu={ftf_kit['mu0Hu']*1e3:+.2f}±{ftf_kit['mu0Hu_err']*1e3:.2f} mT" if "mu0Hu" in ftf_kit else ""
        print(f"  {'FTF':26s}: g={ftf_kit['g']:.4f}±{ftf_kit['g_err']:.4f}, Meff={ftf_kit['mu0Meff']:.4f}±{ftf_kit['mu0Meff_err']:.4f} T{hu}, "
              f"alpha={ftf_kit['alpha']:.3e}±{ftf_kit['alpha_err']:.1e}, dH0={ftf_kit['mu0Hinh']*1e3:+.2f}±{ftf_kit['mu0Hinh_err']*1e3:.2f} mT")

    # --- Plots ---------------------------------------------------------------
    fig, axs = plt.subplots(2, 2, figsize=(13, 9))
    ax = axs[0, 0]
    ok_ftf = T["ftf_ok"]
    ok_pf = ~T["pf_problem"]
    ax.errorbar(T["f_GHz"][ok_ftf], T["B_ftf"][ok_ftf], yerr=T["B_ftf_err"][ok_ftf], fmt="s", ms=4, mfc="none",
                color="C1", label="FTF (LabVIEW)")
    ax.errorbar(T["f_GHz"][ok_pf], T["B_pf"][ok_pf], yerr=T["B_pf_err"][ok_pf], fmt=".", ms=5,
                color="C0", label="PolderFit (gut)")
    if (~ok_pf).any():
        ax.plot(T["f_GHz"][~ok_pf], T["B_pf"][~ok_pf], "x", color="C3", ms=5, label="PolderFit (problematisch)")
    ax.set_xlabel("f (GHz)"); ax.set_ylabel(r"$\mu_0 H_{res}$ (T)"); ax.set_title(f"{name}: Resonanzfeld")
    ax.legend(fontsize=8)

    ax = axs[0, 1]
    ax.errorbar(T["f_GHz"][ok_ftf], T["dH_ftf"][ok_ftf] * 1e3, yerr=T["dH_ftf_err"][ok_ftf] * 1e3, fmt="s", ms=4,
                mfc="none", color="C1", label="FTF")
    ax.errorbar(T["f_GHz"][ok_pf], T["dH_pf"][ok_pf] * 1e3, yerr=T["dH_pf_err"][ok_pf] * 1e3, fmt=".", ms=5,
                color="C0", label="PolderFit (gut)")
    if (~ok_pf).any():
        ax.plot(T["f_GHz"][~ok_pf], T["dH_pf"][~ok_pf] * 1e3, "x", color="C3", ms=5, label="PolderFit (problematisch)")
    ax.set_xlabel("f (GHz)"); ax.set_ylabel(r"$\mu_0 \Delta H$ (mT)"); ax.set_title("Linienbreite (FWHM)")
    ax.legend(fontsize=8)

    ax = axs[1, 0]
    ax.axhline(0, color="k", lw=0.8)
    ax.errorbar(T["f_GHz"][beide_ok], T["dB"][beide_ok] * 1e3,
                yerr=np.hypot(np.nan_to_num(T["B_pf_err"][beide_ok]), np.nan_to_num(T["B_ftf_err"][beide_ok])) * 1e3,
                fmt=".", ms=4, color="C2")
    ax.set_xlabel("f (GHz)"); ax.set_ylabel(r"$B_{res}$(PF) − $B_{res}$(FTF) (mT)")
    ax.set_title("Differenz Resonanzfeld (Fehlerbalken = kombinierte 1σ)")

    ax = axs[1, 1]
    ax.axhline(0, color="k", lw=0.8)
    ax.errorbar(T["f_GHz"][beide_ok], T["rel_dH"][beide_ok] * 100,
                yerr=np.hypot(np.nan_to_num(T["dH_pf_err"][beide_ok]), np.nan_to_num(T["dH_ftf_err"][beide_ok]))
                / T["dH_ftf"][beide_ok] * 100, fmt=".", ms=4, color="C2")
    ax.set_xlabel("f (GHz)"); ax.set_ylabel(r"$\Delta H$(PF)/$\Delta H$(FTF) − 1 (%)")
    ax.set_title("Relative Differenz Linienbreite")
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", dpi=130)
    plt.close(fig)

    # z-Score-Histogramme
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
    for ax, key, titel in ((axs[0], "z_B", "z(B_res)"), (axs[1], "z_dH", "z(ΔH)")):
        x = T[key][beide_ok]
        x = x[np.isfinite(x)]
        if x.size:
            ax.hist(np.clip(x, -10, 10), bins=41, range=(-10, 10), color="C2")
        ax.set_xlabel(f"{titel} = (PF − FTF)/σ_komb (geclippt ±10)")
        ax.set_title(f"{name}: {titel}")
    fig.tight_layout()
    fig.savefig(OUT / f"{name}_z.png", dpi=130)
    plt.close(fig)

    # CSV
    keys = list(T.keys())
    with open(OUT / f"{name}.csv", "w") as fh:
        fh.write(",".join(keys) + "\n")
        for i in range(n_gesamt):
            fh.write(",".join(str(T[k][i]) for k in keys) + "\n")

    ergebnis = {"name": name, "tdms": tdms.name, "geometrie_ftf": geometrie,
                "n_linescans": len(erg), "t_fit_s": t_fit,
                "statistik": stat, "kittel": kittel, "kittel_vergleich_zu_ftf": vergleiche}
    with open(OUT / f"{name}.json", "w") as fh:
        json.dump(ergebnis, fh, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    return ergebnis


def main(argv):
    rest = []
    it = iter(argv[1:])
    for a in it:
        if a == "--alpha-max":
            OPTIONEN["alpha_max"] = float(next(it))
        elif a == "--nachfenster":
            OPTIONEN["nachfenster_faktor"] = float(next(it))
        elif a == "--suffix":
            OPTIONEN["suffix"] = next(it)
        else:
            rest.append(a)
    print(f"Optionen: {OPTIONEN}")
    namen = rest or sorted(p.name for p in DATA.iterdir() if p.is_dir())
    alle = []
    for n in namen:
        try:
            alle.append(benchmark_datensatz(DATA / n))
        except Exception as ex:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            alle.append({"name": n, "fehler": repr(ex)})
    with open(OUT / f"zusammenfassung{OPTIONEN['suffix']}.json", "w") as fh:
        json.dump(alle, fh, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))


if __name__ == "__main__":
    main(sys.argv)

# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Physik-Regression: zwei PolderFit-Staende auf IDENTISCHEM Feldfenster vergleichen.

Aufruf je Stand (mit dem jeweiligen Interpreter, importiert das dort
installierte ``polderfit``)::

    python regression_vergleich.py --label head --datensatz cofe_wm_ip_290K_1 \
        --daten /pfad/benchmark_ftf/data --aus /pfad/head_cofe.json

Vergleich zweier Laeufe::

    python regression_vergleich.py --vergleich head.json ref.json [--md bericht.md]

Erzwungenes Feldfenster
-----------------------
Das Fenster wird NICHT aus den Daten geschaetzt (AutoWindows), sondern
deterministisch aus der FTF-Referenztabelle ``ftf/Resonance Fit.dat``
berechnet::

    Fenster(f) = [Hres_FTF(f) - k*dH_FTF(f),  Hres_FTF(f) + k*dH_FTF(f)]

mit ``k = --fensterfaktor`` (Standard 4.0; Fensterbreite = 8*FWHM, wie der
GUI-Standard ``breite_faktor=8``). Da die FTF-Tabelle eine Datei ist und der
Faktor per Kommandozeile fest steht, ist das Fenster in BEIDEN Staenden
bitgleich; Unterschiede in den Ergebnissen koennen daher nur aus dem
Fitmodell / Optimierer / den Kriterien kommen. Zusaetzlich wird die Variante
"nachfenster" gerechnet (zweiter Durchgang, Fenster = B_res +- 2.5*dH), die
denselben Startpunkt hat.

Alle Felder in Tesla (mu0*H), gamma in rad/(s*T), dH ist die FWHM.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

FEHLENDE_API: list[str] = []


def _hole(modul: str, name: str):
    """Importiert ``name`` aus ``modul``; fehlt er, wird das gemerkt (klare Meldung)."""
    try:
        mod = __import__(modul, fromlist=[name])
    except Exception as exc:  # pragma: no cover - Umgebungsfehler
        FEHLENDE_API.append(f"{modul} nicht importierbar: {exc!r}")
        return None
    if not hasattr(mod, name):
        FEHLENDE_API.append(f"{modul}.{name} fehlt in dieser Version")
        return None
    return getattr(mod, name)


# ---------------------------------------------------------------------------
# FTF-Referenzdateien
# ---------------------------------------------------------------------------
def lies_ftf_tabelle(pfad: Path) -> dict:
    with open(pfad, encoding="latin-1") as fh:
        kopf = fh.readline().rstrip("\n").split("\t")
        zeilen = [z.rstrip("\n").split("\t") for z in fh if z.strip()]
    werte = np.array([[float(x) if x.strip() else np.nan for x in z] for z in zeilen], dtype=float)
    return {k: werte[:, i] for i, k in enumerate(kopf)}


def lies_ftf_kittel(pfad: Path) -> dict:
    t = lies_ftf_tabelle(pfad)
    d = {k: float(v[0]) for k, v in t.items()}
    out = {
        "g": d["g-factor"], "g_err": d["g-factor_error"],
        "mu0Meff": d["M eff (T)"], "mu0Meff_err": d["M eff (T)_error"],
        "alpha": d["gilbert-alpha"], "alpha_err": d["gilbert-alpha_error"],
        "mu0Hinh": d["deltaH0 (T)"], "mu0Hinh_err": d["deltaH0 (T)_error"],
    }
    if "H aniso (T)" in d:
        out["mu0Hu"] = d["H aniso (T)"]
        out["mu0Hu_err"] = d["H aniso (T)_error"]
        out["geometrie"] = "ip"
    else:
        out["geometrie"] = "oop"
    return out


# ---------------------------------------------------------------------------
# Ein Lauf
# ---------------------------------------------------------------------------
def lauf(label: str, ordner: Path, alpha_max: float, fensterfaktor: float,
         nachfenster_faktor: float) -> dict:
    lade_tdms = _hole("polderfit.io.tdms_laden", "lade_tdms")
    schneide_band = _hole("polderfit.fit.autowindows", "schneide_band")
    fitte_linescan = _hole("polderfit.fit.linescan_fit", "fitte_linescan")
    fitte_mit_nachfenster = _hole("polderfit.fit.batch", "fitte_mit_nachfenster")
    auswertung_kittel_llg = _hole("polderfit.auswertung.uebersicht", "auswertung_kittel_llg")
    GAMMA_STANDARD = _hole("polderfit.physik.konstanten", "GAMMA_STANDARD")
    if FEHLENDE_API:
        raise SystemExit("Fehlende API in dieser polderfit-Version:\n  " + "\n  ".join(FEHLENDE_API))

    tdms = sorted(ordner.glob("*.tdms"))[0]
    ftf_tab = lies_ftf_tabelle(ordner / "ftf" / "Resonance Fit.dat")
    kittel_dateien = sorted((ordner / "ftf").glob("*Kittel*"))
    ftf_kit = lies_ftf_kittel(kittel_dateien[0]) if kittel_dateien else None
    geometrie = ftf_kit["geometrie"] if ftf_kit else "oop"

    daten = lade_tdms(str(tdms))
    f_ftf = ftf_tab["f (GHz)"]

    zeilen = []
    erg_fenster = []
    erg_nach = []
    for ls in daten.linescans:
        f_ghz = float(ls.frequenz) / 1e9
        j = int(np.argmin(np.abs(f_ftf - f_ghz)))
        if abs(f_ftf[j] - f_ghz) > 2e-3:
            continue
        h, dh = float(ftf_tab["Hres1"][j]), float(ftf_tab["dH1"][j])
        if not (np.isfinite(h) and h != 0.0 and np.isfinite(dh) and dh > 0):
            continue
        unten, oben = h - fensterfaktor * dh, h + fensterfaktor * dh
        beschnitten = schneide_band(ls, unten, oben)
        e1 = fitte_linescan(beschnitten, GAMMA_STANDARD, alpha_max=alpha_max)
        e2, _besch2, verwendet = fitte_mit_nachfenster(
            ls, (unten, oben), GAMMA_STANDARD, alpha_max=alpha_max,
            nachfenster_faktor=nachfenster_faktor)
        erg_fenster.append(e1)
        erg_nach.append(e2)
        zeilen.append({
            "f_GHz": f_ghz,
            "fenster_unten": unten, "fenster_oben": oben,
            "n_punkte": int(np.size(beschnitten.feld)),
            "B_res": float(e1.B_res), "B_res_err": float(e1.B_res_err),
            "dH": float(e1.dH), "dH_err": float(e1.dH_err),
            "alpha": float(e1.alpha), "phi": float(e1.phi),
            "rmse_norm": float(e1.rmse_norm), "R2": float(e1.R2),
            "erfolg": bool(e1.erfolg), "problematisch": bool(e1.problematisch),
            "gruende": list(e1.problem_gruende),
            "nf_B_res": float(e2.B_res), "nf_B_res_err": float(e2.B_res_err),
            "nf_dH": float(e2.dH), "nf_dH_err": float(e2.dH_err),
            "nf_problematisch": bool(e2.problematisch),
            "nf_fenster_unten": float(verwendet[0]), "nf_fenster_oben": float(verwendet[1]),
            "ftf_B_res": h, "ftf_B_res_err": float(ftf_tab["Hres err1"][j]),
            "ftf_dH": dh, "ftf_dH_err": float(ftf_tab["dH err1"][j]),
        })

    def _kittel(ergebnisse):
        try:
            info = auswertung_kittel_llg(ergebnisse, geometrie=geometrie,
                                         gamma_start=GAMMA_STANDARD, gewichtet=False)
        except Exception as exc:  # noqa: BLE001
            return {"fehler": repr(exc)}
        kit, llg = info["kittel"], info["llg"]
        z = {
            "g": kit["g_faktor"], "g_err": kit["g_faktor_err"],
            "mu0Meff": kit["mu0Meff"], "mu0Meff_err": kit["mu0Meff_err"],
            "alpha": llg["alpha"], "alpha_err": llg["alpha_err"],
            "mu0Hinh": llg["mu0Hinh"], "mu0Hinh_err": llg["mu0Hinh_err"],
            "gamma": kit["gamma"], "gamma_err": kit["gamma_err"],
            "n_punkte": int(np.size(info["frequenz_Hz"])),
        }
        if "mu0Hu" in kit:
            z["mu0Hu"] = kit["mu0Hu"]
            z["mu0Hu_err"] = kit["mu0Hu_err"]
        return {k: (float(v) if not isinstance(v, int) else v) for k, v in z.items()}

    return {
        "label": label,
        "datensatz": ordner.name,
        "tdms": tdms.name,
        "geometrie": geometrie,
        "alpha_max": alpha_max,
        "fensterfaktor": fensterfaktor,
        "nachfenster_faktor": nachfenster_faktor,
        "gamma_standard": float(GAMMA_STANDARD),
        "polderfit_version": _version(),
        "zeilen": zeilen,
        "kittel_fenster": _kittel(erg_fenster),
        "kittel_nachfenster": _kittel(erg_nach),
        "ftf_kittel": ftf_kit,
    }


def _version() -> str:
    try:
        import polderfit
        return str(getattr(polderfit, "__version__", "?"))
    except Exception:  # noqa: BLE001
        return "?"


# ---------------------------------------------------------------------------
# Vergleich
# ---------------------------------------------------------------------------
def _lies(pfad: str) -> dict:
    return json.loads(Path(pfad).read_text(encoding="utf-8"))


def _z(a, ea, b, eb):
    s = float(np.hypot(np.nan_to_num(ea), np.nan_to_num(eb)))
    return (a - b) / s if s > 0 else float("nan")


def vergleich(a_pfad: str, b_pfad: str) -> str:
    A, B = _lies(a_pfad), _lies(b_pfad)
    zeilen = ["# Regression " + f"{A['label']} vs. {B['label']} – {A['datensatz']}", "",
              f"* polderfit-Version: {A['label']}={A['polderfit_version']}, "
              f"{B['label']}={B['polderfit_version']}",
              f"* alpha_max={A['alpha_max']}, Fensterfaktor={A['fensterfaktor']} "
              f"(Fenster = Hres_FTF ± {A['fensterfaktor']}·ΔH_FTF), "
              f"Nachfenster={A['nachfenster_faktor']}",
              f"* gamma_standard: {A['label']}={A['gamma_standard']:.6e}, "
              f"{B['label']}={B['gamma_standard']:.6e}", ""]

    za = {round(z["f_GHz"], 6): z for z in A["zeilen"]}
    zb = {round(z["f_GHz"], 6): z for z in B["zeilen"]}
    gemeinsam = sorted(set(za) & set(zb))
    zeilen += [f"* Frequenzen: {A['label']}={len(za)}, {B['label']}={len(zb)}, "
               f"gemeinsam={len(gemeinsam)}", ""]

    # Einzelfits
    zeilen += ["## Einzelfits (erzwungenes Fenster, 1 Durchgang)", "",
               "| f (GHz) | B_res A (mT) | B_res B (mT) | Δ (µT) | z=Δ/σ | ΔH A (mT) | "
               "ΔH B (mT) | Δ (µT) | z=Δ/σ | >1σ |", "|" + "---|" * 10]
    n_ueber = 0
    dmax_b = dmax_dh = 0.0
    for f in gemeinsam:
        x, y = za[f], zb[f]
        db = x["B_res"] - y["B_res"]
        ddh = x["dH"] - y["dH"]
        zb_ = _z(x["B_res"], x["B_res_err"], y["B_res"], y["B_res_err"])
        zdh = _z(x["dH"], x["dH_err"], y["dH"], y["dH_err"])
        ueber = (abs(zb_) > 1) or (abs(zdh) > 1)
        n_ueber += int(bool(ueber))
        dmax_b = max(dmax_b, abs(db))
        dmax_dh = max(dmax_dh, abs(ddh))
        zeilen.append(f"| {f:.4f} | {x['B_res']*1e3:.4f} | {y['B_res']*1e3:.4f} | "
                      f"{db*1e6:+.3f} | {zb_:+.3f} | {x['dH']*1e3:.4f} | {y['dH']*1e3:.4f} | "
                      f"{ddh*1e6:+.3f} | {zdh:+.3f} | {'**JA**' if ueber else ''} |")
    zeilen += ["", f"**Maximale Differenz:** B_res {dmax_b*1e6:.3f} µT, ΔH {dmax_dh*1e6:.3f} µT; "
               f"Frequenzen mit |z|>1: {n_ueber}/{len(gemeinsam)}", ""]

    # Statusvergleich
    unterschied = [f for f in gemeinsam
                   if za[f]["problematisch"] != zb[f]["problematisch"]]
    zeilen += [f"* Unterschiedliche Problem-Einstufung: {len(unterschied)} "
               f"({', '.join(f'{f:.3f}' for f in unterschied[:10])})", ""]

    # Kittel/LLG
    for schluessel, titel in (("kittel_fenster", "Kittel/LLG (erzwungenes Fenster)"),
                              ("kittel_nachfenster", "Kittel/LLG (mit Nachfenster)")):
        zeilen += [f"## {titel}", ""]
        ka, kb = A[schluessel], B[schluessel]
        if "fehler" in ka or "fehler" in kb:
            zeilen += [f"FEHLER: {A['label']}={ka.get('fehler')}, {B['label']}={kb.get('fehler')}", ""]
            continue
        ftf = A.get("ftf_kittel") or {}
        zeilen += [f"| Groesse | {A['label']} | {B['label']} | Δ(A−B) | z=Δ/σ | FTF | "
                   f"z(A−FTF) | >1σ |", "|" + "---|" * 8]
        for name, faktor, einheit in (("g", 1.0, ""), ("mu0Meff", 1.0, " T"),
                                      ("mu0Hu", 1e3, " mT"), ("alpha", 1.0, ""),
                                      ("mu0Hinh", 1e3, " mT")):
            if name not in ka or name not in kb:
                continue
            a, ea = ka[name], ka.get(name + "_err", float("nan"))
            b, eb = kb[name], kb.get(name + "_err", float("nan"))
            zab = _z(a, ea, b, eb)
            if name in ftf:
                zaf = _z(a, ea, ftf[name], ftf.get(name + "_err", float("nan")))
                ftf_txt = f"{ftf[name]*faktor:.5g}±{ftf.get(name+'_err', float('nan'))*faktor:.2g}"
            else:
                zaf, ftf_txt = float("nan"), "—"
            ueber = abs(zab) > 1 or (np.isfinite(zaf) and abs(zaf) > 1)
            zeilen.append(f"| {name}{einheit} | {a*faktor:.6g}±{ea*faktor:.3g} | "
                          f"{b*faktor:.6g}±{eb*faktor:.3g} | {(a-b)*faktor:+.4g} | {zab:+.3f} | "
                          f"{ftf_txt} | {zaf:+.3f} | {'**JA**' if ueber else ''} |")
        zeilen += ["", f"n_punkte: {A['label']}={ka['n_punkte']}, {B['label']}={kb['n_punkte']}", ""]
    return "\n".join(zeilen)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--label", default=None, help="head | ref (Name des Standes)")
    p.add_argument("--datensatz", default="cofe_wm_ip_290K_1")
    p.add_argument("--daten", default=None, help="Pfad zu benchmark_ftf/data")
    p.add_argument("--alpha-max", type=float, default=0.1)
    p.add_argument("--fensterfaktor", type=float, default=4.0)
    p.add_argument("--nachfenster", type=float, default=2.5)
    p.add_argument("--aus", default=None, help="Ziel-JSON")
    p.add_argument("--vergleich", nargs=2, metavar=("A.json", "B.json"))
    p.add_argument("--md", default=None, help="Ziel-Markdown des Vergleichs")
    a = p.parse_args(argv)

    if a.vergleich:
        text = vergleich(*a.vergleich)
        if a.md:
            Path(a.md).write_text(text, encoding="utf-8")
        print(text)
        return 0

    if not a.label:
        p.error("--label oder --vergleich noetig")
    wurzel = Path(a.daten) if a.daten else Path(__file__).resolve().parents[1] / "benchmark_ftf" / "data"
    ordner = wurzel / a.datensatz
    if not ordner.is_dir():
        p.error(f"Datensatz {ordner} nicht gefunden")
    erg = lauf(a.label, ordner, a.alpha_max, a.fensterfaktor, a.nachfenster)
    ziel = Path(a.aus) if a.aus else Path(f"{a.label}_{a.datensatz}.json")
    ziel.write_text(json.dumps(erg, indent=1, default=float), encoding="utf-8")
    print(f"{a.label}: {len(erg['zeilen'])} Frequenzen -> {ziel}")
    print(f"  Kittel (Fenster):     {erg['kittel_fenster']}")
    print(f"  Kittel (Nachfenster): {erg['kittel_nachfenster']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

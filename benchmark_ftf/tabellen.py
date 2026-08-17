"""Erzeugt die Markdown-Tabellen des Berichts aus ergebnisse/zusammenfassung*.json."""
import json, sys
from pathlib import Path
HIER = Path(__file__).resolve().parent
suffix = sys.argv[1] if len(sys.argv) > 1 else ""
alle = json.load(open(HIER / "ergebnisse" / f"zusammenfassung{suffix}.json"))
print("| Datensatz | n (zugeordnet) | PF problematisch | ΔB_res = B(PF)−B(FTF), Median (p16..p84) [mT] | \\|z_B\\| ≤ 2 | ΔH(PF)/ΔH(FTF)−1, Median (p16..p84) | \\|z_ΔH\\| ≤ 2 |")
print("|---|---|---|---|---|---|---|")
for d in alle:
    if "fehler" in d:
        print(f"| {d['name']} | Fehler: {d['fehler']} | | | | | |"); continue
    s = d["statistik"]
    if not s["dB_T"]:
        print(f"| {d['name']} | {s['n_zugeordnet']} | {s['n_pf_problematisch']} | – | – | – | – |"); continue
    print(f"| {d['name']} | {s['n_zugeordnet']} | {s['n_pf_problematisch']} | {s['dB_T']['median']*1e3:+.2f} ({s['dB_T']['p16']*1e3:+.2f} .. {s['dB_T']['p84']*1e3:+.2f}) | {s['z_B']['anteil_abs_le_2']*100:.0f} % | {s['rel_dH']['median']*100:+.1f} % ({s['rel_dH']['p16']*100:+.1f} .. {s['rel_dH']['p84']*100:+.1f}) | {s['z_dH']['anteil_abs_le_2']*100:.0f} % |")
def fmt(v, k, scale=1, prec=4, unit=""):
    if k not in v or v[k] is None: return "–"
    return f"{v[k]*scale:.{prec}f} ± {v[k+'_err']*scale:.{prec}f}{unit}"
for d in alle:
    if "fehler" in d or "ftf" not in d.get("kittel", {}): continue
    k = d["kittel"]
    print(f"\n**{d['name']}** (Kittel-Geometrie laut FTF: {d['geometrie_ftf']})\n")
    print("| Quelle | n Punkte | g | µ₀M_eff [T] | µ₀H_u [mT] | α [10⁻³] | µ₀ΔH₀ [mT] |"); print("|---|---|---|---|---|---|---|")
    for key, lab in (("ftf", "FTF (LabVIEW)"), ("pf_ungewichtet", "PolderFit, ungewichtet"), ("pf_gewichtet", "PolderFit, gewichtet (GUI-Standard)"), ("pf_fitter_auf_ftf", "PolderFit-Kittel/LLG-Fitter auf den FTF-Punkten")):
        v = k.get(key, {})
        if "fehler" in v:
            print(f"| {lab} | – | Fehler ({v['fehler'][:60]}) | | | | |"); continue
        n = v.get("n_punkte", d["statistik"]["n_zugeordnet"] if key == "ftf" else "")
        print(f"| {lab} | {n if n is not None else ''} | {fmt(v,'g')} | {fmt(v,'mu0Meff')} | {fmt(v,'mu0Hu',1e3,2)} | {fmt(v,'alpha',1e3,3)} | {fmt(v,'mu0Hinh',1e3,2)} |")

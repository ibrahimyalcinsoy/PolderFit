# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Abbildungen fuer Dokumentation und Handbuch (docs/abb/*.png).

Konvention aller Plots: x-Achse = Feld (T bzw. mT), y-Achse = Frequenz (GHz),
sofern beide Groessen vorkommen. Aufruf aus dem Repo-Wurzelverzeichnis:

    python docs/abb/erzeugen.py

Datenquellen (lokal, nicht versioniert): benchmark_ftf/data/<name>/ (TDMS +
FTF-Tabellen), benchmark_ftf/ergebnisse/*.csv, testdata/ (unsortierte Linescans).
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

HIER = Path(__file__).resolve().parent          # docs/abb
WURZEL = HIER.parent.parent
sys.path.insert(0, str(WURZEL))
ABB = HIER
ABB.mkdir(exist_ok=True)

from polderfit.io.tdms_laden import lade_tdms  # noqa: E402
from polderfit.physik.konstanten import GAMMA_STANDARD, gamma_aus_g  # noqa: E402
from polderfit.physik.suszeptibilitaet import chi_oop  # noqa: E402
from polderfit.physik.kittel_llg import kittel_ip, kittel_oop, linienbreite, fit_kittel_ip, fit_linienbreite  # noqa: E402
from polderfit.fit.autowindows import (schneide_band, _detrend_residuum,  # noqa: E402
                                        _stationaeren_untergrund_abziehen, _kandidat,
                                        _glatte_lokale_trasse, _PROMINENZ_MIN, auto_fenster_alle)
from polderfit.fit.linescan_fit import fitte_linescan  # noqa: E402
from polderfit.fit.batch import fitte_alle  # noqa: E402

plt.rcParams.update({"font.size": 9, "axes.titlesize": 10, "figure.dpi": 100,
                     "savefig.dpi": 200, "axes.grid": True, "grid.alpha": 0.25})
C_PF, C_FTF, C_ALT, C_G, C_R = "#1f497d", "#e07b00", "#888888", "#3fa34d", "#a02828"

COFE = sorted(glob.glob(str(WURZEL / "benchmark_ftf/data/cofe_wm_ip_290K_1/*.tdms")))[0]
COFE_FTF = WURZEL / "benchmark_ftf/data/cofe_wm_ip_290K_1/ftf/Resonance Fit"
UNSORT = WURZEL / "testdata/CoFe-Si/CoFe(40nm)-Si(675um-Si-Mat.)/2023-JAN-18-Linescan-2D-map-ip--5K_53.164deg.tdms"
GRAT = sorted(glob.glob(str(WURZEL / "benchmark_ftf/data/cofe_gratings_ip_5K/*.tdms")))
ERG = WURZEL / "benchmark_ftf/ergebnisse"


def speichere(fig, name, layout=True):
    if layout:
        fig.tight_layout()
    fig.savefig(ABB / name)
    plt.close(fig)
    print("  ->", name)


# ---------------------------------------------------------------------------
# 1. Polder-Suszeptibilitaet: chi', chi'', |chi| und der Faktor sqrt(3)
# ---------------------------------------------------------------------------
def abb_chi():
    f = 30e9
    omega = 2 * np.pi * f
    gamma = GAMMA_STANDARD
    B_res = 1.0
    B = np.linspace(0.85, 1.15, 3000)
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.4))
    for ax, alpha in zip(axs, (0.01, 0.03)):
        chi = chi_oop(B, B_res, alpha, omega, gamma)
        s = np.max(np.abs(chi))
        ax.plot(B, chi.real / s, color=C_PF, label=r"$\chi'$ (Dispersion)")
        ax.plot(B, chi.imag / s, color=C_R, label=r"$\chi''$ (Absorption)")
        ax.plot(B, np.abs(chi) / s, color=C_G, ls="--", label=r"$|\chi|$")
        dH = 2 * omega * alpha / gamma
        # FWHM-Marker
        ax.axvspan(B_res - dH / 2, B_res + dH / 2, color=C_R, alpha=0.08)
        ax.annotate("", xy=(B_res - dH / 2, -0.5), xytext=(B_res + dH / 2, -0.5),
                    arrowprops=dict(arrowstyle="<->", color=C_R))
        ax.text(B_res, -0.56, r"$\mu_0\Delta H$ (FWHM $\chi''$) = %.1f mT" % (dH * 1e3),
                ha="center", va="top", color=C_R, fontsize=8)
        ax.annotate("", xy=(B_res - np.sqrt(3) * dH / 2, 0.5), xytext=(B_res + np.sqrt(3) * dH / 2, 0.5),
                    arrowprops=dict(arrowstyle="<->", color=C_G))
        ax.text(B_res, 0.53, r"FWHM $|\chi|$ = $\sqrt{3}\,\mu_0\Delta H$", ha="center", va="bottom", color=C_G, fontsize=8)
        ax.axvline(B_res, color="k", lw=0.6, ls=":")
        ax.set_title(fr"$f$ = 30 GHz, $\alpha$ = {alpha}, $g$ = 2")
        ax.set_xlabel(r"Feld $\mu_0 H$ (T)")
        ax.set_ylim(-1.1, 1.1)
    axs[0].set_ylabel(r"$\chi/\max|\chi|$")
    axs[0].legend(loc="upper right", fontsize=8)
    speichere(fig, "abb_chi.png")


# ---------------------------------------------------------------------------
# 2. Ein realer Linescan-Fit: Modell, Untergrund, Residuen (CoFe 43.55 GHz)
# ---------------------------------------------------------------------------
def _cofe():
    return lade_tdms(COFE)


def abb_linescan_fit(ds):
    i = int(np.argmin(np.abs(ds.frequenzen - 43.5535e9)))
    ls = ds.linescans[i]
    fen = auto_fenster_alle(ds)[i]
    lsb = schneide_band(ls, *fen)
    e1 = fitte_linescan(lsb)
    lo, hi = e1.B_res - 2.5 * e1.dH, e1.B_res + 2.5 * e1.dH
    ls2 = schneide_band(ls, lo, hi)
    e2 = fitte_linescan(ls2)
    B = ls2.feld
    B_ref = float(np.mean(B))
    bg_re = e2.off_re + e2.slope_re * (B - B_ref)
    bg_im = e2.off_im + e2.slope_im * (B - B_ref)
    fig, axs = plt.subplots(2, 2, figsize=(9, 5.4), sharex=True,
                            gridspec_kw=dict(height_ratios=[3, 1.3]))
    for k, (teil, mess, kurve, bg, name) in enumerate([
            ("Re", ls2.re, e2.fitkurve.real, bg_re, "Realteil"),
            ("Im", ls2.im, e2.fitkurve.imag, bg_im, "Imaginärteil")]):
        ax = axs[0, k]
        ax.plot(B, mess, ".", ms=3, color="k", label="Messung $S_{21}$")
        ax.plot(B, kurve, "-", color=C_PF, lw=1.5, label="Fit (Modell)")
        ax.plot(B, bg, "--", color=C_ALT, lw=1, label="Untergrund (Offset + Steigung)")
        ax.axvline(e2.B_res, color=C_R, lw=0.8, ls=":")
        ax.axvspan(e2.B_res - e2.dH / 2, e2.B_res + e2.dH / 2, color=C_R, alpha=0.08)
        ax.set_title(f"{name}, f = {ls.frequenz/1e9:.2f} GHz")
        axr = axs[1, k]
        axr.plot(B, mess - kurve, ".", ms=3, color=C_PF)
        axr.axhline(0, color="k", lw=0.6)
        axr.set_xlabel(r"Feld $\mu_0 H$ (T)")
        axr.set_ylabel("Residuum")
    axs[0, 0].legend(fontsize=8, loc="lower left")
    axs[0, 0].set_ylabel("$S_{21}$ (lin. Einheiten)")
    txt = (fr"$B_\mathrm{{res}}$ = {e2.B_res:.5f} ± {e2.B_res_err:.5f} T" "\n"
           fr"$\mu_0\Delta H$ = {e2.dH*1e3:.2f} ± {e2.dH_err*1e3:.2f} mT" "\n"
           fr"$\alpha$ = {e2.alpha:.4f} ± {e2.alpha_err:.4f} (bei g=2)" "\n"
           f"rmse_norm = {e2.rmse_norm:.3f},  " r"$\chi^2_\mathrm{red}$" f" = {e2.chi2_red:.2f}" "\n"
           f"Fenster = B_res ± 2,5 ΔH ({B.size} Punkte)")
    axs[0, 1].text(0.02, 0.04, txt, transform=axs[0, 1].transAxes, fontsize=7.5, va="bottom",
                   bbox=dict(boxstyle="round", fc="white", ec=C_ALT, alpha=0.9))
    speichere(fig, "abb_linescan_fit.png")
    return i, e1, e2, fen


# ---------------------------------------------------------------------------
# 3. Fensterabhaengigkeit von dH: Sweep in k, plus zwei Fenster im Linescan
# ---------------------------------------------------------------------------
def abb_fenster(ds):
    ks = [1, 1.5, 2, 2.5, 3, 4, 6, 8, 12]
    ziele = [20.107e9, 43.5535e9, 57.62e9, 62.31e9]
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.6), gridspec_kw=dict(width_ratios=[1.1, 1]))
    ax = axs[0]
    for fz, col in zip(ziele, [C_G, C_PF, C_FTF, C_R]):
        i = int(np.argmin(np.abs(ds.frequenzen - fz)))
        ls = ds.linescans[i]
        # FTF-dH aus dem CSV
        csv = pd.read_csv(ERG / "cofe_wm_ip_290K_1.csv")
        row = csv.iloc[int(np.argmin(np.abs(csv.f_GHz - fz / 1e9)))]
        dH_ftf, B_ftf = row.dH_ftf, row.B_ftf
        vals = []
        for k in ks:
            e = fitte_linescan(schneide_band(ls, B_ftf - k * dH_ftf, B_ftf + k * dH_ftf))
            vals.append(e.dH * 1e3)
        ax.plot(ks, np.array(vals) / (dH_ftf * 1e3) - 1, "o-", ms=4, color=col,
                label=f"{ls.frequenz/1e9:.1f} GHz (FTF: {dH_ftf*1e3:.1f} mT)")
    ax.axhline(0, color="k", lw=0.8)
    ax.axvspan(2, 3, color=C_G, alpha=0.12, label="Plateau, Nachfenster k = 2,5")
    ax.axvline(7, color=C_ALT, ls="--", lw=1)
    ax.text(7.1, 0.02, "altes Auto-Fenster\n≈ ±7 ΔH", fontsize=7.5, color=C_ALT)
    ax.set_xlabel(r"halbe Fensterbreite $k$ (Fenster = $B_\mathrm{res} \pm k\,\mu_0\Delta H_\mathrm{FTF}$)")
    ax.set_ylabel(r"$\mu_0\Delta H(k)\,/\,\mu_0\Delta H_\mathrm{FTF} - 1$")
    ax.set_title("Linienbreite gegen Fensterbreite (CoFe 290 K)")
    ax.legend(fontsize=7)
    # rechts: Linescan 43.55 GHz mit Fenstern k=2.5 / k=8, Residuen
    ax = axs[1]
    i = int(np.argmin(np.abs(ds.frequenzen - 43.5535e9)))
    ls = ds.linescans[i]
    csv = pd.read_csv(ERG / "cofe_wm_ip_290K_1.csv")
    row = csv.iloc[int(np.argmin(np.abs(csv.f_GHz - 43.5535)))]
    dH_ftf, B_ftf = row.dH_ftf, row.B_ftf
    for k, col in ((8, C_R), (2.5, C_G)):
        lsk = schneide_band(ls, B_ftf - k * dH_ftf, B_ftf + k * dH_ftf)
        e = fitte_linescan(lsk)
        ax.plot(lsk.feld, (lsk.re - e.fitkurve.real) * 1e4, ".", ms=2.5, color=col,
                label=f"k = {k}: ΔH = {e.dH*1e3:.1f} mT")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel(r"Feld $\mu_0 H$ (T)")
    ax.set_ylabel(r"Residuum Re($S_{21}$) ($\times 10^{-4}$)")
    ax.set_title(f"Residuen bei {ls.frequenz/1e9:.2f} GHz")
    ax.legend(fontsize=8)
    speichere(fig, "abb_fenster.png")


# ---------------------------------------------------------------------------
# 4. AutoWindow auf einer echten unsortierten Linescan-Messung
# ---------------------------------------------------------------------------
def abb_autowindow():
    ds = lade_tdms(str(UNSORT))
    # nur jede 3. Frequenz fuer die Darstellung -> schnellere Fits, klarere Bilder
    linescans = ds.linescans
    f = ds.frequenzen / 1e9
    B = linescans[0].feld
    reins = [_detrend_residuum(ls.feld, ls.s21) for ls in linescans]
    R = np.array(reins)
    Rs = np.array(_stationaeren_untergrund_abziehen(reins))
    kand = np.array([_kandidat(ls.feld, Rs[k]) for k, ls in enumerate(linescans)])
    kb, ks = kand[:, 0], kand[:, 1]
    guide = _glatte_lokale_trasse(ds.frequenzen, kb, ks)
    fenster = auto_fenster_alle(ds)
    roh = np.abs(np.array([ls.s21 for ls in linescans]))
    roh_db = 20 * np.log10(roh / np.median(roh, axis=1, keepdims=True))

    fig, axs = plt.subplots(1, 4, figsize=(12.5, 4.2), sharey=True)
    ext = [B.min(), B.max(), f.min(), f.max()]

    def show(ax, M, titel, cmap="viridis", p=(2, 98)):
        vmin, vmax = np.nanpercentile(M, p)
        ax.imshow(M, origin="lower", aspect="auto", extent=ext, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(titel)
        ax.set_xlabel(r"Feld $\mu_0 H$ (T)")
        ax.grid(False)
    show(axs[0], roh_db, r"(a) $|S_{21}|$ je Frequenz normiert (dB)")
    show(axs[1], R, "(b) nach Polynom-Untergrundabzug", cmap="magma")
    show(axs[2], Rs, "(c) nach Stationärabzug (Median über f)", cmap="magma")
    ax = axs[3]
    show(ax, Rs, "(d) Kandidaten, Trasse, Fenster", cmap="Greys")
    gut = ks >= _PROMINENZ_MIN
    ax.plot(kb[~gut], f[~gut], "x", ms=3, color=C_R, label="Kandidat schwach (s < 4)")
    ax.plot(kb[gut], f[gut], ".", ms=3, color=C_G, label="Kandidat prominent (s ≥ 4)")
    if guide is not None:
        ax.plot(guide, f, "-", color=C_PF, lw=1.2, label="glatte lokale Trasse")
    lo = np.array([w[0] for w in fenster]); hi = np.array([w[1] for w in fenster])
    ax.fill_betweenx(f, lo, hi, color=C_FTF, alpha=0.18, lw=0, label="Auto-Fenster (Detektion)")
    ax.legend(fontsize=7, loc="lower left", framealpha=0.95)
    axs[0].set_ylabel("Frequenz (GHz)")
    fig.suptitle(f"AutoWindow: {UNSORT.name} ({len(linescans)} Linescans, {B.size} Feldpunkte)", fontsize=9)
    speichere(fig, "abb_autowindow.png")
    return ds


# ---------------------------------------------------------------------------
# 5. Kittel-Dispersion und LLG-Gerade (Feld x, Frequenz y) - CoFe 290 K
# ---------------------------------------------------------------------------
def abb_kittel_llg(ds):
    stapel = fitte_alle(ds)
    erg = [e for e in stapel.ergebnisse if e.erfolg and not e.problematisch]
    f = np.array([e.frequenz for e in erg]); b = np.array([e.B_res for e in erg])
    dh = np.array([e.dH for e in erg]); dh_err = np.array([e.dH_err for e in erg])
    b_err = np.array([e.B_res_err for e in erg])
    kit = fit_kittel_ip(f, b)
    llg = fit_linienbreite(f, dh, gamma=kit["gamma"], gamma_err=kit["gamma_err"])
    ff = np.linspace(f.min(), f.max(), 300)
    fig, axs = plt.subplots(1, 4, figsize=(12.5, 3.8), sharey=True,
                            gridspec_kw=dict(width_ratios=[1.3, 0.8, 1.1, 0.8]))
    ax = axs[0]
    ax.errorbar(b, f / 1e9, xerr=b_err, fmt="o", ms=3, color=C_PF, label="Einzelfits $B_\\mathrm{res}$")
    ax.plot(kittel_ip(ff, kit["mu0Meff"], kit["mu0Hu"], kit["gamma"]), ff / 1e9, "-", color=C_R,
            label=(f"Kittel ip: g = {kit['g_faktor']:.4f}±{kit['g_faktor_err']:.4f}\n"
                   f"µ0Meff = {kit['mu0Meff']:.4f} T, µ0Hu = {kit['mu0Hu']*1e3:.2f} mT"))
    ax.set_xlabel(r"Resonanzfeld $\mu_0 H_\mathrm{res}$ (T)"); ax.set_ylabel("Frequenz (GHz)")
    ax.set_title("Kittel-Dispersion (ip)"); ax.legend(fontsize=7, loc="upper left")
    ax = axs[1]
    res = (b - kittel_ip(f, kit["mu0Meff"], kit["mu0Hu"], kit["gamma"])) * 1e3
    ax.errorbar(res, f / 1e9, xerr=b_err * 1e3, fmt="o", ms=3, color=C_PF)
    ax.axvline(0, color="k", lw=0.7)
    ax.set_xlabel(r"$B_\mathrm{res} - $ Kittel (mT)")
    ax.set_title(f"Residuen, R² = {kit['R2']:.6f}\nStreuung ≫ formale Fehler")
    ax = axs[2]
    ax.errorbar(dh * 1e3, f / 1e9, xerr=dh_err * 1e3, fmt="o", ms=3, color=C_PF, label="Einzelfits $\\mu_0\\Delta H$")
    ax.plot(linienbreite(ff, llg["mu0Hinh"], llg["alpha"], kit["gamma"]) * 1e3, ff / 1e9, "-", color=C_R,
            label=(f"LLG: α = ({llg['alpha']*1e3:.3f}±{llg['alpha_err']*1e3:.3f})·10⁻³\n"
                   f"µ0ΔH0 = {llg['mu0Hinh']*1e3:.2f}±{llg['mu0Hinh_err']*1e3:.2f} mT"))
    # 1-sigma-Band der Geraden (Steigung/Achsenabschnitt unkorreliert genaehert)
    band = np.sqrt(llg["mu0Hinh_err"] ** 2 + (2 * (2 * np.pi * ff) * llg["alpha_err"] / kit["gamma"]) ** 2) * 1e3
    mitte = linienbreite(ff, llg["mu0Hinh"], llg["alpha"], kit["gamma"]) * 1e3
    ax.fill_betweenx(ff / 1e9, mitte - band, mitte + band, color=C_R, alpha=0.15, label="±1σ (Fortpflanzung)")
    ax.set_xlabel(r"Linienbreite $\mu_0\Delta H$ (mT)"); ax.set_title("LLG-Gerade")
    ax.legend(fontsize=7, loc="upper left")
    ax = axs[3]
    res = (dh - linienbreite(f, llg["mu0Hinh"], llg["alpha"], kit["gamma"])) * 1e3
    ax.errorbar(res, f / 1e9, xerr=dh_err * 1e3, fmt="o", ms=3, color=C_PF)
    ax.axvline(0, color="k", lw=0.7)
    ax.set_xlabel(r"$\mu_0\Delta H - $ LLG (mT)"); ax.set_title(f"Residuen, R² = {llg['R2']:.4f}")
    fig.suptitle("CoFe ip 290 K (Benchmark-Datensatz), ungewichteter Fit", fontsize=9)
    speichere(fig, "abb_kittel_llg.png")
    return stapel


# ---------------------------------------------------------------------------
# 6. Benchmark PF vs FTF: alles mit Frequenz auf y
# ---------------------------------------------------------------------------
def abb_benchmark():
    neu = pd.read_csv(ERG / "cofe_wm_ip_290K_1.csv")
    alt = pd.read_csv(ERG / "cofe_wm_ip_290K_1_einpass.csv")
    fig, axs = plt.subplots(1, 4, figsize=(12.5, 4), sharey=True,
                            gridspec_kw=dict(width_ratios=[1.1, 1, 1, 1]))
    ax = axs[0]
    ax.plot(neu.B_ftf, neu.f_GHz, "s", ms=5, mfc="none", color=C_FTF, label="FTF (LabVIEW)")
    ax.plot(neu.B_pf, neu.f_GHz, ".", ms=4, color=C_PF, label="PolderFit")
    ax.set_xlabel(r"$\mu_0 H_\mathrm{res}$ (T)"); ax.set_ylabel("Frequenz (GHz)"); ax.set_title("Resonanzfeld")
    ax.legend(fontsize=8)
    ax = axs[1]
    ax.errorbar(alt.dB * 1e3, alt.f_GHz, xerr=np.sqrt(alt.B_pf_err**2 + alt.B_ftf_err**2) * 1e3, fmt="o", ms=2.5,
                color=C_ALT, alpha=0.7, label="alter Stand (ein Durchgang)")
    ax.errorbar(neu.dB * 1e3, neu.f_GHz, xerr=np.sqrt(neu.B_pf_err**2 + neu.B_ftf_err**2) * 1e3, fmt="o", ms=3,
                color=C_G, label="mit Nachfenster 2,5 ΔH")
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel(r"$B_\mathrm{res}$(PF) − $B_\mathrm{res}$(FTF) (mT)"); ax.set_title("Differenz Resonanzfeld (±1σ komb.)")
    ax.legend(fontsize=7, loc="upper left")
    ax = axs[2]
    ax.plot(neu.dH_ftf * 1e3, neu.f_GHz, "s", ms=5, mfc="none", color=C_FTF, label="FTF")
    ax.plot(alt.dH_pf * 1e3, alt.f_GHz, ".", ms=4, color=C_ALT, label="PF alt")
    ax.plot(neu.dH_pf * 1e3, neu.f_GHz, ".", ms=4, color=C_PF, label="PF neu")
    ax.set_xlabel(r"$\mu_0\Delta H$ (mT)"); ax.set_title("Linienbreite (FWHM)"); ax.legend(fontsize=8)
    ax = axs[3]
    ax.errorbar(alt.rel_dH * 100, alt.f_GHz, xerr=np.sqrt(alt.dH_pf_err**2 + alt.dH_ftf_err**2) / alt.dH_ftf * 100,
                fmt="o", ms=2.5, color=C_ALT, alpha=0.7, label=f"alt: Median {np.median(alt.rel_dH)*100:+.1f} %")
    ax.errorbar(neu.rel_dH * 100, neu.f_GHz, xerr=np.sqrt(neu.dH_pf_err**2 + neu.dH_ftf_err**2) / neu.dH_ftf * 100,
                fmt="o", ms=3, color=C_G, label=f"neu: Median {np.median(neu.rel_dH)*100:+.1f} %")
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel(r"$\Delta H$(PF)/$\Delta H$(FTF) − 1 (%)"); ax.set_title("Relative Differenz Linienbreite")
    ax.legend(fontsize=7, loc="upper left")
    fig.suptitle("Benchmark cofe_wm_ip_290K_1: PolderFit gegen FTF je Frequenz", fontsize=9)
    speichere(fig, "abb_benchmark.png")

    # z-Score-Histogramme
    fig, axs = plt.subplots(1, 2, figsize=(8, 3))
    for ax, sp, name, d in ((axs[0], "z_B", r"$z_B$ (Resonanzfeld)", neu), (axs[1], "z_dH", r"$z_{\Delta H}$ (Linienbreite)", neu)):
        za = alt[sp].dropna(); zn = d[sp].dropna()
        ax.hist(za, bins=np.linspace(-6, 6, 37), color=C_ALT, alpha=0.5, label=f"alt: |z|≤2: {np.mean(np.abs(za)<=2)*100:.0f} %")
        ax.hist(zn, bins=np.linspace(-6, 6, 37), color=C_G, alpha=0.6, label=f"neu: |z|≤2: {np.mean(np.abs(zn)<=2)*100:.0f} %")
        x = np.linspace(-6, 6, 300)
        ax.plot(x, len(zn) * (12 / 36) * np.exp(-x**2 / 2) / np.sqrt(2 * np.pi), "k-", lw=1, label="N(0,1)")
        ax.set_xlabel(name); ax.set_ylabel("Anzahl"); ax.legend(fontsize=7)
    fig.suptitle("z-Scores CoFe 290 K: (PF − FTF)/√(u²(PF)+u²(FTF))", fontsize=9)
    speichere(fig, "abb_zscore.png")


# ---------------------------------------------------------------------------
# 7. Kittel-ip-Entartung
# ---------------------------------------------------------------------------
def abb_ip_entartung():
    ff = np.linspace(5e9, 50e9, 300)
    gam = gamma_aus_g(2.0)
    M, Hu = 0.13, -0.004
    fig, axs = plt.subplots(1, 2, figsize=(8.5, 3.4), sharey=True, gridspec_kw=dict(width_ratios=[1.3, 1]))
    ax = axs[0]
    ax.plot(kittel_ip(ff, M, Hu, gam), ff / 1e9, "-", color=C_PF, lw=2.5, label=f"µ0Meff = {M:+.3f} T, µ0Hu = {Hu*1e3:+.1f} mT (physikalisch)")
    ax.plot(kittel_ip(ff, -M, Hu + M, gam), ff / 1e9, "--", color=C_R, lw=1.5, label=f"µ0Meff = {-M:+.3f} T, µ0Hu = {(Hu+M)*1e3:+.1f} mT (Spiegelast)")
    ax.set_xlabel(r"$\mu_0 H_\mathrm{res}$ (T)"); ax.set_ylabel("Frequenz (GHz)")
    ax.set_title("Kittel ip: zwei Parametersätze, eine Kurve"); ax.legend(fontsize=7)
    ax = axs[1]
    d = np.abs(kittel_ip(ff, M, Hu, gam) - kittel_ip(ff, -M, Hu + M, gam))
    ax.semilogx(np.maximum(d, 1e-19), ff / 1e9, ".", ms=3, color="k")
    ax.axvline(1e-16, color=C_ALT, ls="--", lw=0.8)
    ax.text(1.2e-16, 45, "Maschinengenauigkeit\n(double ≈ 10⁻¹⁶ · 1 T)", fontsize=7, color=C_ALT)
    ax.set_xlim(1e-19, 1e-12)
    ax.set_xlabel("|Differenz der Kurven| (T)"); ax.set_title("Beide Parametersätze: identische Kurve")
    speichere(fig, "abb_ip_entartung.png")


# ---------------------------------------------------------------------------
# 8. YIG: Hebelwirkung kleiner dH-Unterschiede auf alpha
# ---------------------------------------------------------------------------
def abb_yig_hebel():
    d = pd.read_csv(ERG / "yig_konstanz_ip_50K.csv")
    d = d[d.ftf_ok & ~d.pf_problem]
    f = d.f_GHz.values * 1e9
    gam = gamma_aus_g(2.0006)
    l_pf = fit_linienbreite(f, d.dH_pf.values, gamma=gam)
    l_ftf = fit_linienbreite(f, d.dH_ftf.values, gamma=gam)
    ff = np.linspace(f.min(), f.max(), 200)
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    ax = axs[0]
    ax.plot(d.dH_ftf * 1e3, d.f_GHz, "s", ms=3, mfc="none", color=C_FTF, label="FTF")
    ax.plot(d.dH_pf * 1e3, d.f_GHz, ".", ms=3, color=C_PF, label="PolderFit")
    ax.plot(linienbreite(ff, l_ftf["mu0Hinh"], l_ftf["alpha"], gam) * 1e3, ff / 1e9, "-", color=C_FTF,
            label=f"LLG FTF-Punkte: α = {l_ftf['alpha']*1e3:.2f}·10⁻³")
    ax.plot(linienbreite(ff, l_pf["mu0Hinh"], l_pf["alpha"], gam) * 1e3, ff / 1e9, "-", color=C_PF,
            label=f"LLG PF-Punkte: α = {l_pf['alpha']*1e3:.2f}·10⁻³")
    ax.set_xlabel(r"$\mu_0\Delta H$ (mT)"); ax.set_ylabel("Frequenz (GHz)")
    ax.set_title("YIG 50 K: ΔH(f) fast flach (ΔH₀ ≈ 16,5 mT)"); ax.legend(fontsize=7)
    ax = axs[1]
    ax.plot(d.rel_dH * 100, d.f_GHz, ".", ms=3, color=C_G)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel(r"$\Delta H$(PF)/$\Delta H$(FTF) − 1 (%)")
    ax.set_title("0–3 % in ΔH  ⇒  12 % in α (Steigung ≪ Achsenabschnitt)")
    speichere(fig, "abb_yig_hebel.png")


# ---------------------------------------------------------------------------
# 9. Gitter: Diskretisierung (2,3 mT Schritt bei dH ~ 40-60 mT)
# ---------------------------------------------------------------------------
def abb_gitter():
    if not GRAT:
        return
    ds = lade_tdms(GRAT[0])
    i = int(np.argmin(np.abs(ds.frequenzen - 26.46e9)))
    ls = ds.linescans[i]
    csv = pd.read_csv(ERG / "cofe_gratings_ip_5K.csv")
    row = csv.iloc[int(np.argmin(np.abs(csv.f_GHz - ls.frequenz / 1e9)))]
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.4))
    ax = axs[0]
    ax.plot(ls.feld, ls.re, "o-", ms=3, lw=0.6, color="k", label="Re $S_{21}$ (Messpunkte)")
    for k, col in ((1.5, C_R), (3, C_G)):
        lsk = schneide_band(ls, row.B_ftf - k * row.dH_ftf, row.B_ftf + k * row.dH_ftf)
        e = fitte_linescan(lsk)
        ax.plot(lsk.feld, e.fitkurve.real, "-", color=col, lw=1.5, label=f"Fit k = {k}: ΔH = {e.dH*1e3:.1f} mT")
    ax.set_xlabel(r"Feld $\mu_0 H$ (T)"); ax.set_ylabel("Re $S_{21}$")
    ax.set_title(f"CoFe-Gitter, {ls.frequenz/1e9:.2f} GHz: {ls.feld.size} Punkte, Schritt {np.mean(np.diff(ls.feld))*1e3:.1f} mT")
    ax.legend(fontsize=7)
    ax = axs[1]
    d = csv[csv.ftf_ok & ~csv.pf_problem]
    ax.plot(d.rel_dH * 100, d.f_GHz, ".", ms=2, color=C_G, alpha=0.6)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel(r"$\Delta H$(PF)/$\Delta H$(FTF) − 1 (%)"); ax.set_ylabel("Frequenz (GHz)")
    ax.set_title(f"Gitter: Median {np.median(d.rel_dH)*100:+.1f} %, breite Streuung (Datenlimit)")
    speichere(fig, "abb_gitter.png")


# ---------------------------------------------------------------------------
# 10. Systematik: Feld-vorher/nachher (Sweep-Lag) aus den TDMS-Kanaelen
# ---------------------------------------------------------------------------
def abb_sweeplag(ds):
    d = np.concatenate([(ls.feld_after - ls.feld_before) for ls in ds.linescans
                        if ls.feld_before is not None and ls.feld_after is not None]) * 1e3
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.hist(d, bins=60, color=C_PF, alpha=0.8)
    ax.axvline(np.median(d), color=C_R, label=f"Median {np.median(d):+.2f} mT")
    ax.set_xlabel(r"$B_\mathrm{nach} - B_\mathrm{vor}$ je Messpunkt (mT)"); ax.set_ylabel("Anzahl")
    ax.set_title("Sweep-Lag im Benchmark-Datensatz (CoFe 290 K)"); ax.legend(fontsize=8)
    speichere(fig, "abb_sweeplag.png")
    return float(np.median(d)), float(np.percentile(np.abs(d), 84))


# ---------------------------------------------------------------------------
# 11. Bewertungskriterien: Beispiele problematischer Fits aus der unsortierten Messung
# ---------------------------------------------------------------------------
def abb_kriterien(ds_unsort):
    stapel = fitte_alle(ds_unsort)
    probl = [e for e in stapel.ergebnisse if e.problematisch and e.feld is not None
             and e.fitkurve is not None and e.frequenz > 8e9 and np.isfinite(e.signalhub)]
    probl.sort(key=lambda e: -e.signalhub)
    gut = [e for e in stapel.ergebnisse if not e.problematisch and e.feld is not None and 15e9 < e.frequenz < 30e9]
    # je ein Beispiel fuer moeglichst verschiedene Gruende
    beispiele = []
    gesehen = set()
    for e in probl:
        g = e.problem_gruende[0] if e.problem_gruende else "?"
        if g not in gesehen:
            beispiele.append(e); gesehen.add(g)
        if len(beispiele) == 3:
            break
    if gut:
        beispiele.insert(0, gut[len(gut) // 2])
    n = len(beispiele)
    if n == 0:
        return stapel
    fig, axs = plt.subplots(1, n, figsize=(3.1 * n, 3.2))
    axs = np.atleast_1d(axs)
    for ax, e in zip(axs, beispiele):
        # Messdaten aus dem zugeschnittenen Linescan
        idx = stapel.ergebnisse.index(e)
        ls = stapel.zugeschnitten[idx]
        mre, mim = np.mean(ls.re), np.mean(ls.im)
        ax.plot(ls.feld, ls.re - mre, ".", ms=2.5, color="k")
        ax.plot(ls.feld, ls.im - mim, ".", ms=2.5, color=C_ALT)
        ax.plot(ls.feld, e.fitkurve.real - mre, "-", color=C_PF, lw=1.2)
        ax.plot(ls.feld, e.fitkurve.imag - mim, "-", color=C_FTF, lw=1.2)
        if np.isfinite(e.B_res):
            ax.axvline(e.B_res, color=C_R, ls=":", lw=0.8)
        gr = e.problem_gruende[:2]
        titel = "OK" if not e.problematisch else "\n".join(gr) + (" …" if len(e.problem_gruende) > 2 else "")
        ax.text(0.5, 1.03, f"{e.frequenz/1e9:.2f} GHz: {titel}\nrmse_norm = {e.rmse_norm:.2f}", fontsize=7.5,
                color=(C_G if not e.problematisch else C_R), transform=ax.transAxes, ha="center", va="bottom")
        ax.set_xlabel(r"Feld $\mu_0 H$ (T)")
        ax.tick_params(labelleft=False)
    fig.suptitle("Bewertung: ein unauffälliger und drei als problematisch gemeldete Fits (Re schwarz/blau, Im grau/orange; Mittelwert abgezogen)", fontsize=8.5)
    fig.subplots_adjust(left=0.03, right=0.99, top=0.74, bottom=0.17, wspace=0.08)
    speichere(fig, "abb_kriterien.png", layout=False)
    return stapel


# ---------------------------------------------------------------------------
# 12. Kittel/LLG auf der echten Linescan-Messung (unsortiert, 5 K, ip)
# ---------------------------------------------------------------------------
def abb_kittel_unsort(stapel):
    erg = stapel.ergebnisse_aktiv()
    FMIN, FMAX = 10e9, 35e9   # Auswertungsauswahl wie in der GUI (Frequenzbereich)
    def _drin(e):
        return FMIN <= e.frequenz <= FMAX and e.B_res > 0.05
    erg = [e for e in erg if e.erfolg and not e.problematisch and _drin(e)]
    f = np.array([e.frequenz for e in erg]); b = np.array([e.B_res for e in erg]); dh = np.array([e.dH for e in erg])
    fig, axs = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    ax = axs[0]
    ax.plot([e.B_res for e in stapel.ergebnisse if e.problematisch], [e.frequenz / 1e9 for e in stapel.ergebnisse if e.problematisch],
            "x", ms=3, color=C_R, alpha=0.5, label="problematisch (ausgeschlossen)")
    ax.plot([e.B_res for e in stapel.ergebnisse if not e.problematisch and not _drin(e)],
            [e.frequenz / 1e9 for e in stapel.ergebnisse if not e.problematisch and not _drin(e)],
            ".", ms=3, color=C_ALT, label="gut, aber außerhalb Auswertungsauswahl")
    ax.plot(b, f / 1e9, ".", ms=3, color=C_PF, label="gut, 10–35 GHz (Auswertungsauswahl)")
    try:
        kit = fit_kittel_ip(f, b)
        ff = np.linspace(f.min(), f.max(), 300)
        ax.plot(kittel_ip(ff, kit["mu0Meff"], kit["mu0Hu"], kit["gamma"]), ff / 1e9, "-", color=C_FTF,
                label=f"Kittel ip: g = {kit['g_faktor']:.3f}±{kit['g_faktor_err']:.3f}, µ0Meff = {kit['mu0Meff']:.3f} T")
        llg = fit_linienbreite(f, dh, gamma=kit["gamma"], gamma_err=kit["gamma_err"])
        axs[1].plot(linienbreite(ff, llg["mu0Hinh"], llg["alpha"], kit["gamma"]) * 1e3, ff / 1e9, "-", color=C_FTF,
                    label=f"LLG: α = ({llg['alpha']*1e3:.2f}±{llg['alpha_err']*1e3:.2f})·10⁻³, µ0ΔH0 = {llg['mu0Hinh']*1e3:.1f} mT")
    except Exception as exc:
        print("Kittel unsort:", exc)
    ax.set_xlabel(r"$\mu_0 H_\mathrm{res}$ (T)"); ax.set_ylabel("Frequenz (GHz)"); ax.legend(fontsize=7)
    ax.set_title("Echte Linescan-Messung: Dispersion")
    ax = axs[1]
    ax.plot(dh * 1e3, f / 1e9, ".", ms=3, color=C_PF)
    ax.set_xlabel(r"$\mu_0\Delta H$ (mT)"); ax.set_title("Linienbreite"); ax.legend(fontsize=7)
    fig.suptitle(f"{UNSORT.name}: {len(erg)} verwendete von {len(stapel.ergebnisse)} Fits (Auswertungsauswahl 10–35 GHz)", fontsize=9)
    speichere(fig, "abb_kittel_unsort.png")


if __name__ == "__main__":
    print("Abbildungen ->", ABB)
    if len(sys.argv) > 1 and sys.argv[1] == "unsort":   # nur die langsamen unsortiert-Abbildungen
        ds_u = abb_autowindow()
        st = abb_kriterien(ds_u)
        abb_kittel_unsort(st)
        sys.exit(0)
    abb_chi()
    abb_ip_entartung()
    abb_benchmark()
    abb_yig_hebel()
    ds = _cofe()
    abb_linescan_fit(ds)
    abb_fenster(ds)
    abb_kittel_llg(ds)
    lag = abb_sweeplag(ds)
    print("Sweep-Lag Median/p84:", lag)
    abb_gitter()
    ds_u = abb_autowindow()
    st = abb_kriterien(ds_u)
    abb_kittel_unsort(st)
    print("fertig")

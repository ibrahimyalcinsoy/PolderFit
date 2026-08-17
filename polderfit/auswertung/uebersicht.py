# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Uebergreifende Auswertung nach den Einzelfits.

Verbindlich gefordert (Protokoll Abschnitt 9):
* Resonanz gegen Frequenz (mit Kittel-Fit, oop/ip waehlbar),
* Resonanz gegen Temperatur,
* Linienbreite gegen Frequenz (LLG-Fit -> Daempfung alpha, Inhomogenitaet).

Die Funktionen liefern Matplotlib-Figures (zum Einbetten in die GUI oder zum
Speichern) und geben zusaetzlich die zugrundeliegenden Daten zurueck, damit
Plots extern reproduzierbar sind.
"""

from __future__ import annotations

import numpy as np

from ..fit.linescan_fit import FitErgebnis
from ..physik.konstanten import GAMMA_STANDARD
from ..physik.kittel_llg import (
    fit_kittel_ip,
    fit_kittel_oop,
    fit_linienbreite,
    kittel_ip,
    kittel_oop,
    linienbreite,
)


def _gute_ergebnisse(ergebnisse: list[FitErgebnis], r2_min: float):
    """Liefert (f, B_res, mu0dH, T, B_res_err, mu0dH_err) nur fuer
    nicht-problematische Einzelfits.

    ``r2_min`` bleibt als zusaetzliche, sekundaere Schranke erhalten; primaer
    zaehlt die Mehrkriterien-Einstufung (``not e.problematisch``). Die
    1σ-Unsicherheiten dienen der GUM-konformen Gewichtung der Kittel-/LLG-Fits.
    """
    f, b, dh, t, b_err, dh_err = [], [], [], [], [], []
    for e in ergebnisse:
        gut = (
            e.erfolg
            and not e.problematisch
            and np.isfinite(e.B_res)
            and (not np.isfinite(e.R2) or e.R2 >= r2_min)
        )
        if gut:
            f.append(e.frequenz)
            b.append(e.B_res)
            dh.append(e.dH)
            t.append(e.temperatur if e.temperatur is not None else np.nan)
            b_err.append(e.B_res_err)
            dh_err.append(getattr(e, "dH_err", np.nan))
    return (np.array(f), np.array(b), np.array(dh), np.array(t),
            np.array(b_err), np.array(dh_err))


def auswertung_kittel_llg(
    ergebnisse: list[FitErgebnis],
    geometrie: str = "oop",
    gamma_fest: bool = False,
    gamma_start: float = GAMMA_STANDARD,
    r2_min: float = 0.9,
    gewichtet: bool = False,
) -> dict:
    """Fuehrt Kittel- und LLG-Fit ueber alle (guten) Einzelfits durch.

    ``geometrie`` ist ``"oop"`` oder ``"ip"``. Rueckgabe enthaelt die Kittel-
    und Linienbreiten-Parameter sowie die verwendeten Datenpunkte.
    ``gewichtet=False`` (Standard) rechnet die klassische ungewichtete
    Ausgleichsrechnung (wie das LabVIEW-FTF; Benchmark: trifft dessen Werte
    ueberall innerhalb 1σ). ``True`` gewichtet beide Fits mit den
    1σ-Unsicherheiten der Einzelfits (w = 1/u², GUM/ABW Abschn. 6.3) – optional,
    in der GUI umschaltbar (Physikalische Parameter, Strg+P); die formalen
    Einzelfehler sind oft viel kleiner als die Punktstreuung, dann dominieren
    wenige Punkte. Die
    Unsicherheit des uebernommenen ``gamma`` geht stets in ``alpha_err`` ein.
    """
    f, b, dh, _t, b_err, dh_err = _gute_ergebnisse(ergebnisse, r2_min)
    if f.size < 3:
        raise ValueError("Zu wenige gute Einzelfits fuer die uebergreifende Auswertung.")
    if not gewichtet:
        b_err = dh_err = None

    if geometrie == "ip":
        kittel = fit_kittel_ip(f, b, gamma_start=gamma_start, B_res_err=b_err)
    else:
        kittel = fit_kittel_oop(f, b, gamma_fest=gamma_fest, gamma_start=gamma_start,
                                B_res_err=b_err)

    llg = fit_linienbreite(f, dh, gamma=kittel["gamma"],
                           gamma_err=kittel["gamma_err"], mu0dH_err=dh_err)
    return {
        "geometrie": geometrie,
        "kittel": kittel,
        "llg": llg,
        "frequenz_Hz": f,
        "B_res_T": b,
        "mu0_dH_T": dh,
    }


def plot_resonanz_vs_frequenz(
    ergebnisse: list[FitErgebnis],
    geometrie: str = "oop",
    gamma_fest: bool = False,
    r2_min: float = 0.9,
    ax=None,
    gewichtet: bool = False,
):
    """Kittel-Dispersionsplot: Feld (x) gegen Frequenz (y), wie im Farbplot.

    Liefert (fig, info). Die Kittel-Modelle sind als ``B_res(f)`` formuliert;
    fuer die Feld-x-Darstellung werden schlicht die Plot-Argumente getauscht.
    """
    import matplotlib.pyplot as plt

    info = auswertung_kittel_llg(ergebnisse, geometrie, gamma_fest, r2_min=r2_min,
                                 gewichtet=gewichtet)
    f, b = info["frequenz_Hz"], info["B_res_T"]
    kit = info["kittel"]

    fig = ax.figure if ax is not None else plt.figure(figsize=(6, 4.5))
    ax = ax or fig.add_subplot(111)
    ax.plot(b, f / 1e9, "o", ms=4, label="Messung")
    ff = np.linspace(f.min(), f.max(), 400)
    if geometrie == "ip":
        bb = kittel_ip(ff, kit["mu0Meff"], kit["mu0Hu"], kit["gamma"])
    else:
        bb = kittel_oop(ff, kit["mu0Meff"], kit["gamma"])
    ax.plot(bb, ff / 1e9, "-",
            label=(f"Kittel {geometrie}: $\\mu_0 M_{{eff}}$={kit['mu0Meff']:.3f} T, "
                   f"g={kit['g_faktor']:.3f}"))
    ax.set_xlabel(r"Resonanzfeld $\mu_0 H_{res}$ (T)")
    ax.set_ylabel("Frequenz (GHz)")
    ax.set_title("Dispersion (Kittel)")
    ax.legend()
    fig.tight_layout()
    return fig, info


def plot_linienbreite(
    ergebnisse: list[FitErgebnis],
    gamma: float = GAMMA_STANDARD,
    r2_min: float = 0.9,
    ax=None,
    gewichtet: bool = False,
):
    """Plot Linienbreite mu0*DeltaH ueber dem Resonanzfeld inkl. LLG-Fit.

    Der LLG-Fit selbst laeuft weiterhin ueber der Frequenz (Gl. 2.28 ist in f
    linear); fuer die Darstellung wird jeder Punkt bei seinem Resonanzfeld
    aufgetragen und die Fitgerade durch die (B_res, DeltaH(f))-Paare gelegt.
    Liefert (fig, info).
    """
    import matplotlib.pyplot as plt

    f, b, dh, _t, _b_err, dh_err = _gute_ergebnisse(ergebnisse, r2_min)
    llg = fit_linienbreite(f, dh, gamma=gamma,
                           mu0dH_err=dh_err if gewichtet else None)

    fig = ax.figure if ax is not None else plt.figure(figsize=(6, 4.5))
    ax = ax or fig.add_subplot(111)
    ax.plot(b, dh * 1e3, "o", ms=4, label="Messung")
    # Fitlinie an den Stuetzstellen der Messpunkte, nach Feld sortiert (die
    # Zuordnung f -> B_res kommt aus der Messung selbst, kein Modell noetig).
    reihenfolge = np.argsort(b)
    ax.plot(b[reihenfolge],
            linienbreite(f[reihenfolge], llg["mu0Hinh"], llg["alpha"], gamma) * 1e3, "-",
            label=(f"LLG: $\\alpha$={llg['alpha']:.2e}, "
                   f"$\\mu_0 H_{{inh}}$={llg['mu0Hinh']*1e3:.2f} mT"))
    ax.set_xlabel(r"Resonanzfeld $\mu_0 H_{res}$ (T)")
    ax.set_ylabel(r"Linienbreite $\mu_0\Delta H$ (mT)")
    ax.set_title("Linienbreite (LLG)")
    ax.legend()
    fig.tight_layout()
    return fig, {"llg": llg}


def plot_resonanz_vs_temperatur(ergebnisse: list[FitErgebnis], r2_min: float = 0.9, ax=None):
    """Plot Resonanzfeld vs. Temperatur (sofern Temperaturdaten vorhanden)."""
    import matplotlib.pyplot as plt

    f, b, _dh, t, _b_err, _dh_err = _gute_ergebnisse(ergebnisse, r2_min)
    gueltig = np.isfinite(t)
    fig = ax.figure if ax is not None else plt.figure(figsize=(6, 4.5))
    ax = ax or fig.add_subplot(111)
    if gueltig.sum() == 0:
        ax.text(0.5, 0.5, "Keine Temperaturdaten vorhanden",
                ha="center", va="center", transform=ax.transAxes)
    else:
        sc = ax.scatter(t[gueltig], b[gueltig], c=f[gueltig] / 1e9, cmap="viridis", s=20)
        fig.colorbar(sc, ax=ax, label="Frequenz (GHz)")
    ax.set_xlabel("Temperatur (K)")
    ax.set_ylabel(r"Resonanzfeld $\mu_0 H_{res}$ (T)")
    ax.set_title("Resonanz vs. Temperatur")
    fig.tight_layout()
    return fig, {"temperatur_K": t, "B_res_T": b}

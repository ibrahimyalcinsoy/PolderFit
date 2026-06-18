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
    """Liefert (f, B_res, mu0dH, T) nur fuer nicht-problematische Einzelfits.

    ``r2_min`` bleibt als zusaetzliche, sekundaere Schranke erhalten; primaer
    zaehlt die Mehrkriterien-Einstufung (``not e.problematisch``).
    """
    f, b, dh, t = [], [], [], []
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
    return (np.array(f), np.array(b), np.array(dh), np.array(t))


def auswertung_kittel_llg(
    ergebnisse: list[FitErgebnis],
    geometrie: str = "oop",
    gamma_fest: bool = False,
    gamma_start: float = GAMMA_STANDARD,
    r2_min: float = 0.9,
) -> dict:
    """Fuehrt Kittel- und LLG-Fit ueber alle (guten) Einzelfits durch.

    ``geometrie`` ist ``"oop"`` oder ``"ip"``. Rueckgabe enthaelt die Kittel-
    und Linienbreiten-Parameter sowie die verwendeten Datenpunkte.
    """
    f, b, dh, _t = _gute_ergebnisse(ergebnisse, r2_min)
    if f.size < 3:
        raise ValueError("Zu wenige gute Einzelfits fuer die uebergreifende Auswertung.")

    if geometrie == "ip":
        kittel = fit_kittel_ip(f, b, gamma_start=gamma_start)
    else:
        kittel = fit_kittel_oop(f, b, gamma_fest=gamma_fest, gamma_start=gamma_start)

    llg = fit_linienbreite(f, dh, gamma=kittel["gamma"])
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
):
    """Plot Resonanzfeld vs. Frequenz inkl. Kittel-Fit. Liefert (fig, info)."""
    import matplotlib.pyplot as plt

    info = auswertung_kittel_llg(ergebnisse, geometrie, gamma_fest, r2_min=r2_min)
    f, b = info["frequenz_Hz"], info["B_res_T"]
    kit = info["kittel"]

    fig = ax.figure if ax is not None else plt.figure(figsize=(6, 4.5))
    ax = ax or fig.add_subplot(111)
    ax.plot(f / 1e9, b, "o", ms=4, label="Messung")
    ff = np.linspace(f.min(), f.max(), 400)
    if geometrie == "ip":
        bb = kittel_ip(ff, kit["mu0Meff"], kit["mu0Hu"], kit["gamma"])
    else:
        bb = kittel_oop(ff, kit["mu0Meff"], kit["gamma"])
    ax.plot(ff / 1e9, bb, "-",
            label=(f"Kittel {geometrie}: $\\mu_0 M_{{eff}}$={kit['mu0Meff']:.3f} T, "
                   f"g={kit['g_faktor']:.3f}"))
    ax.set_xlabel("Frequenz (GHz)")
    ax.set_ylabel(r"Resonanzfeld $\mu_0 H_{res}$ (T)")
    ax.set_title("Resonanz vs. Frequenz")
    ax.legend()
    fig.tight_layout()
    return fig, info


def plot_linienbreite(
    ergebnisse: list[FitErgebnis],
    gamma: float = GAMMA_STANDARD,
    r2_min: float = 0.9,
    ax=None,
):
    """Plot Linienbreite mu0*DeltaH vs. Frequenz inkl. LLG-Fit. Liefert (fig, info)."""
    import matplotlib.pyplot as plt

    f, _b, dh, _t = _gute_ergebnisse(ergebnisse, r2_min)
    llg = fit_linienbreite(f, dh, gamma=gamma)

    fig = ax.figure if ax is not None else plt.figure(figsize=(6, 4.5))
    ax = ax or fig.add_subplot(111)
    ax.plot(f / 1e9, dh * 1e3, "o", ms=4, label="Messung")
    ff = np.linspace(f.min(), f.max(), 400)
    ax.plot(ff / 1e9, linienbreite(ff, llg["mu0Hinh"], llg["alpha"], gamma) * 1e3, "-",
            label=(f"LLG: $\\alpha$={llg['alpha']:.2e}, "
                   f"$\\mu_0 H_{{inh}}$={llg['mu0Hinh']*1e3:.2f} mT"))
    ax.set_xlabel("Frequenz (GHz)")
    ax.set_ylabel(r"Linienbreite $\mu_0\Delta H$ (mT)")
    ax.set_title("Linienbreite vs. Frequenz (LLG)")
    ax.legend()
    fig.tight_layout()
    return fig, {"llg": llg}


def plot_resonanz_vs_temperatur(ergebnisse: list[FitErgebnis], r2_min: float = 0.9, ax=None):
    """Plot Resonanzfeld vs. Temperatur (sofern Temperaturdaten vorhanden)."""
    import matplotlib.pyplot as plt

    f, b, _dh, t = _gute_ergebnisse(ergebnisse, r2_min)
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

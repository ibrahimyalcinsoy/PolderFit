"""Uebergreifende Dispersions- und Daempfungsmodelle (Kittel, LLG).

Alle Felder in Tesla (mu0H), Frequenzen in Hz, ``gamma`` in rad/(s*T).
Quellen: Dissertation M. Mueller, Kap. 2 – Gl. (2.24)/(2.26) (Kittel) und
Gl. (2.28) (inhomogen verbreiterte Linienbreite).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import curve_fit

from .konstanten import GAMMA_STANDARD, g_aus_gamma


def kittel_oop(f: np.ndarray, mu0Meff: float, gamma: float) -> np.ndarray:
    """Kittel-Dispersion out-of-plane, Gl. (2.24): ``B_res = mu0Meff + 2*pi*f/gamma``."""
    f = np.asarray(f, dtype=float)
    return mu0Meff + 2.0 * np.pi * f / gamma


def kittel_ip(f: np.ndarray, mu0Meff: float, mu0Hu: float, gamma: float) -> np.ndarray:
    """Kittel-Dispersion in-plane, Gl. (2.25/2.26) in Tesla.

    ``B_res = sqrt((2*pi*f/gamma)^2 + (mu0Meff/2)^2) - mu0Meff/2 - mu0Hu``.
    """
    f = np.asarray(f, dtype=float)
    w = 2.0 * np.pi * f / gamma
    return np.sqrt(w**2 + (mu0Meff / 2.0) ** 2) - mu0Meff / 2.0 - mu0Hu


def linienbreite(f: np.ndarray, mu0Hinh: float, alpha: float, gamma: float) -> np.ndarray:
    """Inhomogen verbreiterte Linienbreite, Gl. (2.28) in Tesla.

    ``mu0*DeltaH = mu0Hinh + 2*(2*pi*f)*alpha/gamma``.
    """
    f = np.asarray(f, dtype=float)
    return mu0Hinh + 2.0 * (2.0 * np.pi * f) * alpha / gamma


def fit_kittel_oop(
    f: np.ndarray, B_res: np.ndarray, gamma_fest: bool = False,
    gamma_start: float = GAMMA_STANDARD,
) -> dict:
    """Fittet die oop-Kittel-Dispersion an (f, B_res).

    Liefert ``mu0Meff``, ``gamma`` (und g-Faktor) samt Unsicherheiten sowie R².
    Bei ``gamma_fest=True`` wird ``gamma`` festgehalten und nur ``mu0Meff`` gefittet.
    """
    f = np.asarray(f, dtype=float)
    B_res = np.asarray(B_res, dtype=float)

    if gamma_fest:
        def modell(ff, mu0Meff):
            return kittel_oop(ff, mu0Meff, gamma_start)

        p0 = [float(np.median(B_res - 2.0 * np.pi * f / gamma_start))]
        popt, pcov = curve_fit(modell, f, B_res, p0=p0)
        mu0Meff = float(popt[0])
        gamma = gamma_start
        err = np.sqrt(np.diag(pcov))
        ergebnis = {"mu0Meff": mu0Meff, "mu0Meff_err": float(err[0]),
                    "gamma": gamma, "gamma_err": 0.0}
    else:
        def modell(ff, mu0Meff, gamma):
            return kittel_oop(ff, mu0Meff, gamma)

        p0 = [float(np.median(B_res - 2.0 * np.pi * f / gamma_start)), gamma_start]
        popt, pcov = curve_fit(modell, f, B_res, p0=p0)
        mu0Meff, gamma = float(popt[0]), float(popt[1])
        err = np.sqrt(np.diag(pcov))
        ergebnis = {"mu0Meff": mu0Meff, "mu0Meff_err": float(err[0]),
                    "gamma": gamma, "gamma_err": float(err[1])}

    ergebnis["g_faktor"] = g_aus_gamma(ergebnis["gamma"])
    ergebnis["R2"] = _r_quadrat(B_res, kittel_oop(f, ergebnis["mu0Meff"], ergebnis["gamma"]))
    return ergebnis


def fit_kittel_ip(
    f: np.ndarray, B_res: np.ndarray, gamma_start: float = GAMMA_STANDARD,
) -> dict:
    """Fittet die in-plane-Kittel-Dispersion an (f, B_res)."""
    f = np.asarray(f, dtype=float)
    B_res = np.asarray(B_res, dtype=float)

    def modell(ff, mu0Meff, mu0Hu, gamma):
        return kittel_ip(ff, mu0Meff, mu0Hu, gamma)

    p0 = [1.0, 0.0, gamma_start]
    popt, pcov = curve_fit(modell, f, B_res, p0=p0, maxfev=10000)
    err = np.sqrt(np.diag(pcov))
    ergebnis = {
        "mu0Meff": float(popt[0]), "mu0Meff_err": float(err[0]),
        "mu0Hu": float(popt[1]), "mu0Hu_err": float(err[1]),
        "gamma": float(popt[2]), "gamma_err": float(err[2]),
    }
    ergebnis["g_faktor"] = g_aus_gamma(ergebnis["gamma"])
    ergebnis["R2"] = _r_quadrat(
        B_res, kittel_ip(f, ergebnis["mu0Meff"], ergebnis["mu0Hu"], ergebnis["gamma"])
    )
    return ergebnis


def fit_linienbreite(
    f: np.ndarray, mu0dH: np.ndarray, gamma: float = GAMMA_STANDARD,
) -> dict:
    """Fittet die LLG-Linienbreite ``mu0*DeltaH(f)`` -> alpha, Hinh.

    ``gamma`` wird hier festgehalten (z. B. aus dem Kittel-Fit uebernommen).
    """
    f = np.asarray(f, dtype=float)
    mu0dH = np.asarray(mu0dH, dtype=float)

    def modell(ff, mu0Hinh, alpha):
        return linienbreite(ff, mu0Hinh, alpha, gamma)

    p0 = [float(np.min(mu0dH)), 1e-3]
    popt, pcov = curve_fit(modell, f, mu0dH, p0=p0)
    err = np.sqrt(np.diag(pcov))
    ergebnis = {
        "mu0Hinh": float(popt[0]), "mu0Hinh_err": float(err[0]),
        "alpha": float(popt[1]), "alpha_err": float(err[1]),
        "gamma": gamma,
    }
    ergebnis["R2"] = _r_quadrat(mu0dH, linienbreite(f, ergebnis["mu0Hinh"], ergebnis["alpha"], gamma))
    return ergebnis


def _r_quadrat(y: np.ndarray, y_fit: np.ndarray) -> float:
    """Bestimmtheitsmass R²."""
    y = np.asarray(y, dtype=float)
    ss_res = float(np.sum((y - y_fit) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

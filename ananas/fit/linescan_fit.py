"""Einzel-Fit eines Linescans an die Polder-Suszeptibilitaet (Re+Im simultan).

Verwendet ``lmfit`` (nichtlineares Least-Squares, Levenberg-Marquardt) mit
datengetriebenen Startwerten und physikalisch sinnvollen Schranken. Liefert alle
Fitparameter samt Unsicherheiten, mehrere Guetemasse (normiertes Residuum,
reduziertes Chi-Quadrat, R²) sowie die automatische Problem-Einstufung.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from lmfit import Parameters, minimize

from ..io.datensatz import Linescan
from ..physik.konstanten import GAMMA_STANDARD
from ..physik.fitmodell import residuum, s21_modell, schaetze_startwerte, Startwerte
from .kriterien import (
    ALPHA_MAX,
    ALPHA_MIN,
    PHI_MAX,
    PHI_MIN,
    bewerte_fit,
)


@dataclass
class FitErgebnis:
    """Ergebnis eines Linescan-Fits (alle Felder SI/Tesla)."""

    frequenz: float
    erfolg: bool
    B_res: float = np.nan
    B_res_err: float = np.nan
    alpha: float = np.nan
    alpha_err: float = np.nan
    dH: float = np.nan          # mu0*DeltaH (Tesla)
    A: float = np.nan
    A_err: float = np.nan
    phi: float = np.nan
    phi_err: float = np.nan
    off_re: float = np.nan
    off_im: float = np.nan
    slope_re: float = np.nan
    slope_im: float = np.nan
    # Guetemasse
    R2: float = np.nan
    rmse_norm: float = np.nan       # primaeres Mass: RMSE/Signalhub (kombiniert)
    rmse_norm_re: float = np.nan
    rmse_norm_im: float = np.nan
    chi2_red: float = np.nan        # reduziertes Chi-Quadrat
    signalhub: float = np.nan       # Signalhub nach Offset-/Gradient-Abzug
    # Fenster und Konvergenz
    B_fenster_min: float = np.nan
    B_fenster_max: float = np.nan
    kovarianz_ok: bool = False
    # Problem-Einstufung
    problematisch: bool = True
    problem_gruende: list = field(default_factory=list)
    nachbearbeitet: bool = False
    meldung: str = ""
    feld: np.ndarray = field(default=None, repr=False)
    fitkurve: np.ndarray = field(default=None, repr=False)
    temperatur: float | None = None

    @property
    def problem_text(self) -> str:
        """Kurzbegruendung fuer die Statuszeile (z. B. 'alpha an Grenze, ...')."""
        return ", ".join(self.problem_gruende) if self.problem_gruende else "OK"

    def als_zeile(self) -> dict:
        """Flache dict-Darstellung fuer den Tabellen-/Excel-Export."""
        return {
            "frequenz_Hz": self.frequenz,
            "B_res_T": self.B_res,
            "B_res_err_T": self.B_res_err,
            "alpha": self.alpha,
            "alpha_err": self.alpha_err,
            "mu0_dH_T": self.dH,
            "A": self.A,
            "A_err": self.A_err,
            "phi_rad": self.phi,
            "phi_err_rad": self.phi_err,
            "offset_re": self.off_re,
            "offset_im": self.off_im,
            "slope_re": self.slope_re,
            "slope_im": self.slope_im,
            "rmse_norm": self.rmse_norm,
            "rmse_norm_re": self.rmse_norm_re,
            "rmse_norm_im": self.rmse_norm_im,
            "chi2_red": self.chi2_red,
            "signalhub": self.signalhub,
            "R2": self.R2,
            "eins_minus_R2": 1.0 - self.R2 if np.isfinite(self.R2) else np.nan,
            "B_fenster_min_T": self.B_fenster_min,
            "B_fenster_max_T": self.B_fenster_max,
            "kovarianz_ok": self.kovarianz_ok,
            "temperatur_K": self.temperatur if self.temperatur is not None else np.nan,
            "nachbearbeitet": self.nachbearbeitet,
            "erfolg": self.erfolg,
            "problematisch": self.problematisch,
            "problem_gruende": self.problem_text,
            "meldung": self.meldung,
        }


def _rausch_sigma(werte: np.ndarray) -> float:
    """Robuste, fit-unabhaengige Rauschschaetzung aus zweiten Differenzen (MAD).

    Zweite Differenzen unterdruecken glatte Anteile (Offset, Gradient, breite
    Resonanz) und lassen vorwiegend das Messrauschen uebrig.
    """
    werte = np.asarray(werte, dtype=float)
    if werte.size < 5:
        return float(np.std(werte)) or 1.0
    d2 = werte[2:] - 2.0 * werte[1:-1] + werte[:-2]
    mad = np.median(np.abs(d2 - np.median(d2)))
    sigma = 1.4826 * mad / np.sqrt(6.0)  # Normierung der zweiten Differenz
    if sigma <= 0:
        sigma = float(np.std(werte)) or 1.0
    return float(sigma)


def _guetemasse(B, s21, kurve, p, B_ref, n_param):
    """Berechnet normiertes Residuum, reduziertes Chi² und R².

    Der Signalhub wird NACH Abzug von Offset und feldabhaengigem Gradienten
    bestimmt, damit die dominante Untergrund-Rampe das Mass nicht verfaelscht.
    """
    bg_re = p["off_re"].value + p["slope_re"].value * (B - B_ref)
    bg_im = p["off_im"].value + p["slope_im"].value * (B - B_ref)

    mess_re = s21.real - bg_re
    mess_im = s21.imag - bg_im
    res_re = kurve.real - s21.real
    res_im = kurve.imag - s21.imag

    def _norm(mess_ohne_bg, res):
        hub = float(np.max(mess_ohne_bg) - np.min(mess_ohne_bg))
        rmse = float(np.sqrt(np.mean(res ** 2)))
        return (rmse / hub) if hub > 0 else np.inf, hub

    rmse_norm_re, hub_re = _norm(mess_re, res_re)
    rmse_norm_im, hub_im = _norm(mess_im, res_im)

    mess_bg = np.concatenate([mess_re, mess_im])
    res = np.concatenate([res_re, res_im])
    signalhub = float(np.max(mess_bg) - np.min(mess_bg))
    rmse = float(np.sqrt(np.mean(res ** 2)))
    rmse_norm = (rmse / signalhub) if signalhub > 0 else np.inf

    # Reduziertes Chi²: Rauschen fit-unabhaengig aus den Rohdaten schaetzen.
    # Re und Im GETRENNT schaetzen und quadratisch mitteln – ein gemeinsamer
    # concatenate-Block wuerde an der Re/Im-Naht zwei kuenstliche zweite
    # Differenzen erzeugen (verschiedene Offsets/Steigungen von Re und Im).
    sigma_re = _rausch_sigma(s21.real)
    sigma_im = _rausch_sigma(s21.imag)
    sigma = float(np.sqrt(0.5 * (sigma_re ** 2 + sigma_im ** 2)))
    dof = max(res.size - n_param, 1)
    chi2_red = float(np.sum(res ** 2) / (sigma ** 2) / dof)

    # R² (sekundaer) ueber Re+Im gemeinsam.
    mess = np.concatenate([s21.real, s21.imag])
    modell = np.concatenate([kurve.real, kurve.imag])
    ss_res = float(np.sum((mess - modell) ** 2))
    ss_tot = float(np.sum((mess - np.mean(mess)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return dict(
        rmse_norm=rmse_norm, rmse_norm_re=rmse_norm_re, rmse_norm_im=rmse_norm_im,
        chi2_red=chi2_red, signalhub=signalhub, R2=r2,
    )


def fitte_linescan(
    linescan: Linescan,
    gamma: float = GAMMA_STANDARD,
    startwerte: Startwerte | None = None,
    B_res_vorgabe: float | None = None,
) -> FitErgebnis:
    """Fittet einen (i. d. R. bereits zugeschnittenen) Linescan.

    ``startwerte`` koennen vorgegeben werden (manuelles Nachfitten); sonst werden
    sie aus den Daten geschaetzt. ``B_res_vorgabe`` setzt nur das Resonanzfeld.
    Schranken sind physikalisch begrenzt (siehe :mod:`ananas.fit.kriterien`);
    insbesondere MUSS ``B_res`` innerhalb des ausgeschnittenen Feldfensters liegen.
    """
    omega = 2.0 * np.pi * linescan.frequenz
    B = linescan.feld
    s21 = linescan.s21
    B_ref = float(np.mean(B))
    B_min, B_max = float(B.min()), float(B.max())

    if startwerte is None:
        startwerte = schaetze_startwerte(B, s21, omega, gamma, B_res_vorgabe)

    sw = startwerte
    temperatur = linescan.temperatur_mittel()

    # Startwerte in die Schranken zwingen (kein Start exakt auf einer Grenze).
    b_res_start = float(np.clip(sw.B_res, B_min, B_max))
    alpha_start = float(np.clip(sw.alpha, ALPHA_MIN * 1.1, ALPHA_MAX * 0.9))
    phi_start = float(np.clip(sw.phi, PHI_MIN + 1e-6, PHI_MAX - 1e-6))

    params = Parameters()
    # B_res MUSS im Feldfenster liegen (Defekt 1).
    params.add("B_res", value=b_res_start, min=B_min, max=B_max)
    params.add("alpha", value=alpha_start, min=ALPHA_MIN, max=ALPHA_MAX)
    params.add("A", value=sw.A)
    params.add("phi", value=phi_start, min=PHI_MIN, max=PHI_MAX)
    params.add("off_re", value=sw.off_re)
    params.add("off_im", value=sw.off_im)
    params.add("slope_re", value=sw.slope_re)
    params.add("slope_im", value=sw.slope_im)

    try:
        ergebnis = minimize(
            residuum, params, method="leastsq",
            args=(B, s21, omega, gamma, B_ref),
        )
    except Exception as exc:  # numerisch fehlgeschlagen
        erg = FitErgebnis(
            frequenz=linescan.frequenz, erfolg=False, meldung=f"Fit-Fehler: {exc}",
            B_fenster_min=B_min, B_fenster_max=B_max, kovarianz_ok=False,
            feld=B, temperatur=temperatur,
        )
        erg.problematisch, erg.problem_gruende = bewerte_fit(erg)
        return erg

    p = ergebnis.params
    kurve = s21_modell(
        B, p["B_res"].value, p["alpha"].value, p["A"].value, p["phi"].value,
        p["off_re"].value, p["off_im"].value, p["slope_re"].value, p["slope_im"].value,
        omega, gamma, B_ref,
    )

    masse = _guetemasse(B, s21, kurve, p, B_ref, n_param=len(params))

    def _err(name):
        par = p[name]
        return float(par.stderr) if par.stderr is not None else np.nan

    # Kovarianz/Unsicherheiten vorhanden? (lmfit setzt errorbars).
    kovarianz_ok = bool(getattr(ergebnis, "errorbars", False)) and p["B_res"].stderr is not None

    erg = FitErgebnis(
        frequenz=linescan.frequenz,
        erfolg=bool(ergebnis.success),
        B_res=float(p["B_res"].value), B_res_err=_err("B_res"),
        alpha=float(p["alpha"].value), alpha_err=_err("alpha"),
        dH=2.0 * omega * float(p["alpha"].value) / gamma,
        A=float(p["A"].value), A_err=_err("A"),
        phi=float(p["phi"].value), phi_err=_err("phi"),
        off_re=float(p["off_re"].value), off_im=float(p["off_im"].value),
        slope_re=float(p["slope_re"].value), slope_im=float(p["slope_im"].value),
        B_fenster_min=B_min, B_fenster_max=B_max,
        kovarianz_ok=kovarianz_ok,
        meldung=ergebnis.message if hasattr(ergebnis, "message") else "",
        feld=B, fitkurve=kurve, temperatur=temperatur,
        **masse,
    )
    erg.problematisch, erg.problem_gruende = bewerte_fit(erg)
    return erg

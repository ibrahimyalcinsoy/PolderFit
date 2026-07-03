# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Tests des Problemfit-Fixes (phi-Nebenminimum / fehlende Kovarianz).

Bekannte Baustelle: Ein numerisch nahezu perfekter Fit konnte in einem
phi-Nebenminimum mit singulaerer Jacobi-Matrix landen. lmfit liefert dann
keine Unsicherheiten, und der Fit wurde allein deswegen hart als
problematisch markiert ("Programm meldet Problemfit, sieht aber gut aus").

Zweiteiliger Fix:
1. kriterien.bewerte_fit: fehlende Kovarianz ist bei exzellentem Residuum
   (rmse_norm <= RMSE_NORM_EXZELLENT) kein hartes Problem mehr.
2. fitte_linescan: liefert der erste Fit keine Unsicherheiten, wird einmal
   mit um pi verschobenem phi-Start neu gestartet und das bessere Ergebnis
   behalten.
"""

import dataclasses

import numpy as np

from polderfit.fit.kriterien import RMSE_NORM_EXZELLENT, bewerte_fit
from polderfit.fit.linescan_fit import FitErgebnis, fitte_linescan
from polderfit.io.datensatz import Linescan
from polderfit.physik.fitmodell import s21_modell, schaetze_startwerte
from polderfit.physik.konstanten import GAMMA_STANDARD

GAMMA = GAMMA_STANDARD


def _ergebnis(**kwargs) -> FitErgebnis:
    """Ansonsten unauffaelliges Fitergebnis (alle anderen Kriterien gruen)."""
    basis = dict(
        frequenz=15e9, erfolg=True, B_res=0.95, B_res_err=1e-4,
        alpha=0.01, phi=0.3, rmse_norm=0.05, chi2_red=1.0,
        B_fenster_min=0.8, B_fenster_max=1.1, kovarianz_ok=True,
    )
    basis.update(kwargs)
    return FitErgebnis(**basis)


# --- Teil 1: Bewertung ---------------------------------------------------------

def test_fehlende_kovarianz_bei_exzellentem_fit_kein_problem():
    erg = _ergebnis(kovarianz_ok=False, B_res_err=np.nan,
                    rmse_norm=0.5 * RMSE_NORM_EXZELLENT)
    problematisch, gruende = bewerte_fit(erg)
    assert "keine Unsicherheiten" not in gruende
    assert not problematisch


def test_fehlende_kovarianz_bei_maessigem_fit_bleibt_problem():
    erg = _ergebnis(kovarianz_ok=False, B_res_err=np.nan,
                    rmse_norm=2.0 * RMSE_NORM_EXZELLENT)
    problematisch, gruende = bewerte_fit(erg)
    assert "keine Unsicherheiten" in gruende and problematisch


def test_keine_konvergenz_bleibt_immer_problem():
    erg = _ergebnis(erfolg=False, kovarianz_ok=False, B_res_err=np.nan,
                    rmse_norm=0.5 * RMSE_NORM_EXZELLENT)
    problematisch, gruende = bewerte_fit(erg)
    assert "keine Konvergenz" in gruende and problematisch
    # Ohne Konvergenz zaehlt auch die fehlende Kovarianz weiter.
    assert "keine Unsicherheiten" in gruende


def test_kovarianz_vorhanden_unveraendert_gruen():
    problematisch, gruende = bewerte_fit(_ergebnis())
    assert not problematisch and gruende == []


# --- Teil 2: phi-Alternativstart im Linescan-Fit -----------------------------------

def _synthetischer_linescan(phi_wahr: float, frequenz=15e9, n=160):
    omega = 2 * np.pi * frequenz
    B = np.linspace(0.7, 1.2, n)
    B_ref = float(np.mean(B))
    b_res_wahr = 0.95
    rng = np.random.default_rng(21)
    s = s21_modell(B, b_res_wahr, 0.012, 5e-3, phi_wahr,
                   0.02, 0.01, 1e-3, -5e-4, omega, GAMMA, B_ref)
    # Rauschen deutlich unter der Signalamplitude (~5e-7 bei A=5e-3) halten,
    # sonst ist B_res prinzipiell nicht auf 5 mT genau bestimmbar.
    s = s + rng.normal(scale=5e-9, size=n) + 1j * rng.normal(scale=5e-9, size=n)
    return Linescan(frequenz=frequenz, feld=B, re=s.real, im=s.imag), b_res_wahr


def test_pi_falscher_phi_start_wird_gerettet():
    """Startwert-phi bewusst um pi daneben: der Alternativstart rettet den Fit."""
    ls, b_res_wahr = _synthetischer_linescan(phi_wahr=0.4)
    omega = 2 * np.pi * ls.frequenz
    sw = schaetze_startwerte(ls.feld, ls.s21, omega, GAMMA)
    sw_falsch = dataclasses.replace(sw, phi=float(np.clip(sw.phi + np.pi,
                                                          -2 * np.pi + 1e-3,
                                                          2 * np.pi - 1e-3)))
    erg = fitte_linescan(ls, GAMMA, startwerte=sw_falsch)
    assert abs(erg.B_res - b_res_wahr) < 5e-3
    assert not erg.problematisch, erg.problem_gruende


def test_normale_fits_unveraendert_gut():
    """Regressionsschutz: der Alternativstart aendert gute Fits nicht."""
    for phi_wahr in (0.0, 0.4, -1.0, 2.5):
        ls, b_res_wahr = _synthetischer_linescan(phi_wahr=phi_wahr)
        erg = fitte_linescan(ls, GAMMA)
        assert abs(erg.B_res - b_res_wahr) < 5e-3, f"phi_wahr={phi_wahr}"
        assert not erg.problematisch, (phi_wahr, erg.problem_gruende)

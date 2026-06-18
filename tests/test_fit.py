"""Tests des Linescan-Fits anhand synthetischer Daten (bekannte Wahrheit)."""

import numpy as np
import pytest

from ananas.io.datensatz import Linescan
from ananas.physik.konstanten import GAMMA_STANDARD
from ananas.physik.fitmodell import s21_modell, schaetze_startwerte
from ananas.fit.linescan_fit import fitte_linescan


def _synthetischer_linescan(frequenz, B_res, alpha, A, phi, rausch=0.0, seed=0):
    gamma = GAMMA_STANDARD
    omega = 2 * np.pi * frequenz
    B = np.linspace(B_res - 0.15, B_res + 0.15, 200)
    B_ref = float(B.mean())
    s = s21_modell(B, B_res, alpha, A, phi, 0.02, -0.01, 0.05, 0.03, omega, gamma, B_ref)
    if rausch > 0:
        # Rauschen relativ zur tatsaechlichen Signalamplitude (chi traegt grosse
        # Vorfaktoren, daher ist der reine Resonanzhub i. d. R. klein).
        chi_teil = s21_modell(B, B_res, alpha, A, phi, 0.0, 0.0, 0.0, 0.0, omega, gamma, B_ref)
        hub = float(np.abs(chi_teil - chi_teil.mean()).max())
        rng = np.random.default_rng(seed)
        s = s + rausch * hub * (rng.standard_normal(B.size) + 1j * rng.standard_normal(B.size))
    return Linescan(frequenz=frequenz, feld=B, re=s.real, im=s.imag)


def test_fit_rueckgewinnung_ohne_rauschen():
    wahr = dict(frequenz=20e9, B_res=3.0, alpha=4e-3, A=0.01, phi=0.7)
    ls = _synthetischer_linescan(**wahr)
    erg = fitte_linescan(ls)
    assert erg.erfolg
    assert np.isclose(erg.B_res, wahr["B_res"], atol=1e-4)
    assert np.isclose(erg.alpha, wahr["alpha"], rtol=0.05)
    assert erg.R2 > 0.999


def test_fit_robust_mit_rauschen():
    wahr = dict(frequenz=30e9, B_res=2.8, alpha=6e-3, A=0.02, phi=-1.2)
    ls = _synthetischer_linescan(**wahr, rausch=0.02, seed=42)  # 2 % des Signalhubs
    erg = fitte_linescan(ls)
    assert erg.erfolg
    assert np.isclose(erg.B_res, wahr["B_res"], atol=2e-3)
    assert erg.R2 > 0.95


@pytest.mark.parametrize("alpha_true", [3e-3, 6e-3, 1e-2])
def test_startwert_alpha_aus_magnituden_fwhm(alpha_true):
    """Der alpha-Startwert muss aus der MAGNITUDEN-FWHM korrekt zurueckgerechnet
    werden: |chi| faellt erst bei x=+-sqrt(3) auf die Haelfte, die Absorption
    (Definition von mu0*DeltaH, Gl. 2.27) schon bei x=+-1. Ohne den sqrt(3)-Faktor
    waere der Startwert um ~73 % zu gross (Faktor 1.732)."""
    gamma = GAMMA_STANDARD
    f = 25e9
    omega = 2 * np.pi * f
    B_res = 3.0
    B = np.linspace(B_res - 0.12, B_res + 0.12, 300)
    B_ref = float(B.mean())
    s = s21_modell(B, B_res, alpha_true, 0.01, 0.6, 0.02, -0.01, 0.05, 0.03,
                   omega, gamma, B_ref)
    sw = schaetze_startwerte(B, s.real + 1j * s.imag, omega, gamma)
    # Mit korrektem sqrt(3): Faktor ~0.9-1.0; ohne ihn waere er ~1.73 (Test faellt).
    assert np.isclose(sw.alpha, alpha_true, rtol=0.25)


def test_auto_fenster_liefert_gueltiges_band():
    """AutoWindows muss ein gueltiges (unten, oben)-Band liefern.

    Trifft ananas.fit.autowindows.auto_fenster (nutzt np.ptp) – haette den
    NumPy-2.0-Regress 'ndarray has no attribute ptp' erwischt.
    """
    from ananas.fit.autowindows import auto_fenster

    ls = _synthetischer_linescan(20e9, B_res=3.0, alpha=5e-3, A=0.01, phi=0.3)
    unten, oben = auto_fenster(ls)
    assert unten < oben
    assert ls.feld.min() <= unten and oben <= ls.feld.max()
    assert unten <= 3.0 <= oben  # Resonanz liegt im vorgeschlagenen Band


def test_dH_konsistenz():
    ls = _synthetischer_linescan(20e9, 3.0, 5e-3, 0.01, 0.0)
    erg = fitte_linescan(ls)
    omega = 2 * np.pi * 20e9
    erwartet = 2 * omega * erg.alpha / GAMMA_STANDARD
    assert np.isclose(erg.dH, erwartet, rtol=1e-9)

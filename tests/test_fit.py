"""Tests des Linescan-Fits anhand synthetischer Daten (bekannte Wahrheit)."""

import numpy as np

from ananas.io.datensatz import Linescan
from ananas.physik.konstanten import GAMMA_STANDARD
from ananas.physik.fitmodell import s21_modell
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


def test_dH_konsistenz():
    ls = _synthetischer_linescan(20e9, 3.0, 5e-3, 0.01, 0.0)
    erg = fitte_linescan(ls)
    omega = 2 * np.pi * 20e9
    erwartet = 2 * omega * erg.alpha / GAMMA_STANDARD
    assert np.isclose(erg.dH, erwartet, rtol=1e-9)

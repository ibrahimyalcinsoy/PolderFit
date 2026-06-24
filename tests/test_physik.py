"""Tests der physikalischen Kernmodelle (Konstanten, Suszeptibilitaet, Kittel/LLG)."""

import numpy as np

from bbfmr.physik.konstanten import gamma_aus_g, g_aus_gamma, GAMMA_STANDARD
from bbfmr.physik.suszeptibilitaet import chi_oop, chi_oop_komponenten
from bbfmr.physik.kittel_llg import kittel_oop, fit_kittel_oop, linienbreite, fit_linienbreite


def test_gamma_g_umkehrung():
    assert np.isclose(g_aus_gamma(gamma_aus_g(2.0)), 2.0)
    # gamma = g*mu_B/hbar; fuer g=2 exakt ~1.7588e11 rad/(s*T).
    assert np.isclose(gamma_aus_g(2.0), 1.7588e11, rtol=1e-3)


def test_chi_resonanz_lage():
    # Resonanz liegt bei mu0H = B_res (Definition ueber B_res-Parametrisierung).
    gamma = GAMMA_STANDARD
    omega = 2 * np.pi * 20e9
    B_res = 3.0
    B = np.linspace(2.5, 3.5, 2001)
    chi = chi_oop(B, B_res, 0.005, omega, gamma)
    i_max = int(np.argmax(np.abs(chi.imag)))
    assert abs(B[i_max] - B_res) < 5e-3


def test_chi_komponenten_form():
    re, im = chi_oop_komponenten(np.array([3.0]), 2.4, 0.01, 2 * np.pi * 20e9, GAMMA_STANDARD)
    assert re.shape == (1,) and im.shape == (1,)
    assert np.isfinite(re).all() and np.isfinite(im).all()


def test_kittel_oop_fit_rueckgewinnung():
    gamma = GAMMA_STANDARD
    f = np.linspace(5e9, 50e9, 40)
    mu0Meff = 2.38
    b = kittel_oop(f, mu0Meff, gamma)
    fit = fit_kittel_oop(f, b)
    assert np.isclose(fit["mu0Meff"], mu0Meff, atol=1e-3)
    assert np.isclose(fit["gamma"], gamma, rtol=1e-3)
    assert fit["R2"] > 0.999


def test_linienbreite_fit_rueckgewinnung():
    gamma = GAMMA_STANDARD
    f = np.linspace(5e9, 50e9, 40)
    alpha, hinh = 2e-3, 3e-3
    dh = linienbreite(f, hinh, alpha, gamma)
    fit = fit_linienbreite(f, dh, gamma=gamma)
    assert np.isclose(fit["alpha"], alpha, rtol=1e-3)
    assert np.isclose(fit["mu0Hinh"], hinh, atol=1e-4)

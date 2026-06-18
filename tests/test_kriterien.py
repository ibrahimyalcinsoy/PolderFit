"""Tests der Fit-Robustheit: Schranken, Guetemasse und Problem-Erkennung."""

import numpy as np

from ananas.io.datensatz import Linescan
from ananas.physik.konstanten import GAMMA_STANDARD
from ananas.physik.fitmodell import s21_modell
from ananas.fit.linescan_fit import fitte_linescan
from ananas.fit.kriterien import (
    ALPHA_MAX,
    ALPHA_MIN,
    an_grenze,
    bewerte_fit,
)


def _guter_linescan(frequenz=20e9, B_res=3.0, alpha=4e-3, A=0.01, phi=0.6):
    gamma = GAMMA_STANDARD
    omega = 2 * np.pi * frequenz
    B = np.linspace(B_res - 0.12, B_res + 0.12, 200)
    s = s21_modell(B, B_res, alpha, A, phi, 0.02, -0.01, 0.05, 0.03, omega, gamma, float(B.mean()))
    return Linescan(frequenz=frequenz, feld=B, re=s.real, im=s.imag)


def test_an_grenze_helfer():
    assert an_grenze(0.0, 0.0, 1.0)          # exakt an unterer Schranke
    assert an_grenze(1.0, 0.0, 1.0)          # exakt an oberer Schranke
    assert an_grenze(0.005, 0.0, 1.0)        # innerhalb 1 %
    assert not an_grenze(0.5, 0.0, 1.0)      # Mitte


def test_guter_fit_nicht_problematisch():
    erg = fitte_linescan(_guter_linescan())
    assert erg.erfolg and not erg.problematisch
    assert erg.rmse_norm < 0.05
    assert ALPHA_MIN < erg.alpha < ALPHA_MAX
    assert erg.kovarianz_ok


def test_alpha_bleibt_in_schranken():
    # Sehr breite "Resonanz" -> Optimierer wuerde ohne Schranke alpha hochtreiben.
    erg = fitte_linescan(_guter_linescan(alpha=8e-3))
    assert ALPHA_MIN <= erg.alpha <= ALPHA_MAX


def test_reines_rauschen_wird_markiert():
    # Kein Resonanzsignal -> muss als problematisch erkannt werden.
    rng = np.random.default_rng(1)
    B = np.linspace(2.3, 4.4, 300)
    s = 0.04 + 0.02 * (B - B.mean()) + 0.001 * (rng.standard_normal(B.size) + 1j * rng.standard_normal(B.size))
    ls = Linescan(frequenz=0.5e9, feld=B, re=s.real, im=s.imag)
    erg = fitte_linescan(ls)
    assert erg.problematisch
    # Trotz fast konstantem/linearem Signal darf R² nicht ueber Guete entscheiden:
    # rmse_norm oder Schranken-/Konvergenzkriterien greifen.
    assert erg.problem_gruende


def test_R2_taeuscht_bei_dominantem_gradient():
    # Starke Untergrund-Rampe + winzige Resonanz: R² ~ 1, aber falscher Fit moeglich.
    erg = fitte_linescan(_guter_linescan(A=1e-5))  # kaum Resonanz ueber dem Gradienten
    # R² ist hier nahe 1 (vom Gradienten dominiert) ...
    assert erg.R2 > 0.99
    # ... aber das normierte Residuum ist das aussagekraeftige Mass.
    assert np.isfinite(erg.rmse_norm)


def test_B_res_innerhalb_fenster_erzwungen():
    # Breiter Linescan mit Resonanz bei 3.0, Fenster schliesst die Resonanz aus.
    gamma = GAMMA_STANDARD
    omega = 2 * np.pi * 20e9
    B = np.linspace(2.7, 3.6, 300)
    s = s21_modell(B, 3.0, 4e-3, 0.01, 0.6, 0.02, -0.01, 0.05, 0.03, omega, gamma, float(B.mean()))
    maske = B > 3.15  # Resonanz bei 3.0 ausgeschlossen, ~150 Punkte verbleiben
    ls = Linescan(frequenz=20e9, feld=B[maske], re=s.real[maske], im=s.imag[maske])
    erg = fitte_linescan(ls)
    # B_res muss im (beschnittenen) Fenster liegen ...
    assert erg.B_fenster_min <= erg.B_res <= erg.B_fenster_max
    # ... und der Fit ist problematisch (Resonanz nicht im Fenster).
    assert erg.problematisch


def test_problemgruende_im_klartext():
    # Kuenstliches Ergebnis mit alpha an der Grenze.
    class Dummy:
        erfolg = True
        kovarianz_ok = True
        alpha = ALPHA_MAX
        phi = 0.0
        B_res = 3.0
        B_res_err = 1e-4
        B_fenster_min = 2.9
        B_fenster_max = 3.1
        rmse_norm = 0.01
        chi2_red = 1.0
    problematisch, gruende = bewerte_fit(Dummy())
    assert problematisch
    assert any("alpha" in g for g in gruende)

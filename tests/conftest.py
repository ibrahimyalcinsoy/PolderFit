# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Gemeinsame Test-Fixtures und Pfade zu den Beispiel-TDMS-Dateien."""

import os

import pytest

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TDMS_DIR = os.path.join(WURZEL, "TDMS files")

PFAD_UNSORTIERT = os.path.join(TDMS_DIR, "2023-APR-14-Linescan-2D-map-oop--5K_1.615deg.tdms")
PFAD_SORTIERT = os.path.join(TDMS_DIR, "2023-APR-14-Linescan-2D-map-oop--5K_1.615deg-sorted (1).tdms")


@pytest.fixture
def pfad_sortiert():
    if not os.path.exists(PFAD_SORTIERT):
        pytest.skip("Beispiel-TDMS (sorted) nicht vorhanden.")
    return PFAD_SORTIERT


@pytest.fixture
def pfad_unsortiert():
    if not os.path.exists(PFAD_UNSORTIERT):
        pytest.skip("Beispiel-TDMS (unsortiert) nicht vorhanden.")
    return PFAD_UNSORTIERT


@pytest.fixture
def synthetischer_datensatz():
    """Kleiner synthetischer oop-Datensatz (eine Polder-Linie je Frequenz, glatter
    Untergrund) fuer Korridor-/Stapel-Tests ohne Messdatei."""
    import numpy as np
    from polderfit.io.datensatz import Linescan, Messdatensatz
    from polderfit.physik.fitmodell import s21_modell
    from polderfit.physik.konstanten import GAMMA_STANDARD

    gamma = GAMMA_STANDARD
    B = np.linspace(1.0, 3.65, 400)
    B_ref = float(B.mean())
    linescans = []
    for f in np.linspace(6e9, 30e9, 12):
        omega = 2 * np.pi * f
        B_res = 1.37 + omega / gamma
        sig = s21_modell(B, B_res, 5e-3, 0.02, 0.5, 0.0, 0.0, 0.0, 0.0, omega, gamma, B_ref)
        d = B - B.mean()
        s = sig + (0.25 - 0.04 * d) + 1j * (0.10 + 0.03 * d)
        linescans.append(Linescan(frequenz=float(f), feld=B.copy(), re=s.real, im=s.imag))
    return Messdatensatz(quelle="synth", format_typ="unsortiert", linescans=linescans)

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

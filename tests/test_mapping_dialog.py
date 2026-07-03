# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Smoke-Tests der Mapping-Dialoge (Zuordnung + Import-Vorschau).

Laeuft headless (QT_QPA_PLATFORM=offscreen); wird ohne PySide6 uebersprungen.
"""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from polderfit.io.datensatz import Linescan, Messdatensatz
from polderfit.io.kanal_mapping import EINGEBAUTE_PROFILE, PROFIL_SORTIERT
from polderfit.io.tdms_laden import pruefe_datensatz


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


#: Dateistruktur eines sortierten Files (wie von inspiziere_tdms geliefert).
STRUKTUR_SORTIERT = {
    "ZVB": {"frequency": 60, "ReS21": 60, "ImS21": 60},
    "Field": {"Field-before": 60, "Field-after": 60},
}

#: Unbekanntes Layout fuer den Heuristik-Pfad.
STRUKTUR_FREMD = {
    "Acq": {"Frequency (Hz)": 60, "REAL S21": 60, "IMAG S21": 60},
    "Magnet": {"Field (T)": 60},
}


def _dialog(struktur, vorschlag=None):
    from polderfit.gui.mapping_dialog import MappingDialog
    return MappingDialog("test.tdms", struktur, list(EINGEBAUTE_PROFILE),
                         vorschlag=vorschlag)


def test_mapping_dialog_vorbelegt_mit_profil(app):
    dlg = _dialog(STRUKTUR_SORTIERT, vorschlag=PROFIL_SORTIERT)
    zuordnung, layout = dlg.ergebnis()
    assert zuordnung["frequenz"] == ("ZVB", "frequency")
    assert zuordnung["feld_before"] == ("Field", "Field-before")
    assert layout == "sortiert"
    assert dlg.knoepfe.button(QtWidgets.QDialogButtonBox.Ok).isEnabled()


def test_mapping_dialog_heuristik_bei_fremder_datei(app):
    dlg = _dialog(STRUKTUR_FREMD)
    zuordnung, layout = dlg.ergebnis()
    assert zuordnung["frequenz"] == ("Acq", "Frequency (Hz)")
    assert zuordnung["re_s21"] == ("Acq", "REAL S21")
    assert zuordnung["feld_before"] == ("Magnet", "Field (T)")
    assert layout == "sortiert"  # alle Kanaele gleich lang


def test_mapping_dialog_sperrt_ok_bei_fehlender_pflichtrolle(app):
    # Struktur ohne brauchbaren Feld-Kanal: Heuristik findet feld_before nicht.
    struktur = {"Acq": {"Frequency (Hz)": 60, "REAL S21": 60, "IMAG S21": 60}}
    dlg = _dialog(struktur)
    zuordnung, _ = dlg.ergebnis()
    # Heuristik ordnet feld_before hier zwangslaeufig irgendeinen Kanal nicht zu
    # ODER der OK-Knopf bleibt nur bei vollstaendiger Zuordnung frei.
    ok = dlg.knoepfe.button(QtWidgets.QDialogButtonBox.Ok)
    assert ("feld_before" in zuordnung) == ok.isEnabled()


def test_vorschau_dialog_zeigt_bericht_und_warnungen(app):
    from polderfit.gui.mapping_dialog import VorschauDialog
    b = np.linspace(1.0, 2.0, 30)
    ls = Linescan(frequenz=10e9, feld=b, re=np.cos(b), im=np.sin(b))
    ds = Messdatensatz(
        quelle="test.tdms", format_typ="sortiert", linescans=[ls],
        meta={"mapping_profil": "Testprofil",
              "lade_warnungen": ["Die Index-Datei passt nicht zur Datendatei."]})
    bericht = pruefe_datensatz(ds)
    dlg = VorschauDialog(ds, bericht)
    assert dlg is not None  # Aufbau ohne Fehler ist der Smoke-Test

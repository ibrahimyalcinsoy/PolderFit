# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Smoke-Tests des Auswertungsauswahl-Dialogs (Jumper/Bereich)."""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from polderfit.fit import Auswertungsauswahl
from polderfit.io.datensatz import Linescan, Messdatensatz


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _datensatz(n_freq=20, n_feld=60):
    freqs = np.linspace(2e9, 40e9, n_freq)
    B = np.linspace(1.0, 3.0, n_feld)
    ls = [Linescan(frequenz=float(f), feld=B, re=np.cos(B), im=np.sin(B)) for f in freqs]
    return Messdatensatz(quelle="t", format_typ="sortiert", linescans=ls)


def test_dialog_default_ist_neutral(app):
    from polderfit.gui.auswahl_dialog import AuswahlDialog
    dlg = AuswahlDialog(_datensatz())
    auswahl = dlg.auswahl()
    assert auswahl.ist_neutral
    assert dlg.knoepfe.button(QtWidgets.QDialogButtonBox.Ok).isEnabled()
    assert "20 von 20" in dlg.zusammenfassung.text()


def test_dialog_jumper_und_ausschluss(app):
    from polderfit.gui.auswahl_dialog import AuswahlDialog
    dlg = AuswahlDialog(_datensatz())
    dlg.n_frequenz.setValue(5)
    dlg.n_feld.setValue(3)
    dlg.ausschluss.setText("3-5")
    auswahl = dlg.auswahl()
    assert auswahl.n_frequenz == 5 and auswahl.n_feld == 3
    assert auswahl.frequenz_ausschluss == [(3e9, 5e9)]
    assert "4 von 20" in dlg.zusammenfassung.text()


def test_dialog_vorbelegung_aus_letzter_auswahl(app):
    from polderfit.gui.auswahl_dialog import AuswahlDialog
    letzte = Auswertungsauswahl(n_frequenz=7, frequenz_ausschluss=[(10e9, 12e9)])
    dlg = AuswahlDialog(_datensatz(), letzte)
    assert dlg.n_frequenz.value() == 7
    assert dlg.ausschluss.text() == "10-12"


def test_dialog_sperrt_bei_unlesbarem_ausschluss(app):
    from polderfit.gui.auswahl_dialog import AuswahlDialog
    dlg = AuswahlDialog(_datensatz())
    dlg.ausschluss.setText("kaputt")
    assert not dlg.knoepfe.button(QtWidgets.QDialogButtonBox.Ok).isEnabled()
    dlg.ausschluss.setText("")
    assert dlg.knoepfe.button(QtWidgets.QDialogButtonBox.Ok).isEnabled()


def test_dialog_sperrt_bei_leerer_auswahl(app):
    from polderfit.gui.auswahl_dialog import AuswahlDialog
    dlg = AuswahlDialog(_datensatz())
    dlg.ausschluss.setText("0-100")  # alles ausgeschlossen -> 0 Linescans
    assert not dlg.knoepfe.button(QtWidgets.QDialogButtonBox.Ok).isEnabled()

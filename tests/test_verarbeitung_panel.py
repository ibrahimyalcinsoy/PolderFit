# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Smoke-Tests des Verarbeitungspanels und der Farbplot-Anbindung."""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from polderfit.io.datensatz import Linescan, Messdatensatz
from polderfit.verarbeitung import Verarbeitungskette


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _mini_datensatz(n_freq=8, n_feld=60):
    B = np.linspace(0.5, 1.5, n_feld)
    freqs = np.linspace(5e9, 20e9, n_freq)
    ls = [Linescan(frequenz=float(f), feld=B, re=np.cos(20 * B) + 2.0, im=np.sin(20 * B))
          for f in freqs]
    return Messdatensatz(quelle="t", format_typ="sortiert", linescans=ls)


def test_panel_standard_und_callback(app):
    from polderfit.gui.verarbeitung_panel import VerarbeitungPanel
    meldungen = []
    panel = VerarbeitungPanel(geaendert=lambda k, m: meldungen.append((k, m)))

    kette = panel.kette()
    aktive = [s.operation for s in kette.aktive_schritte()]
    assert aktive == ["derivative_divide"]           # Standard wie Verarbeitungskette.standard()
    assert kette.schritte[1].parameter["delta_n"] == 4
    assert panel.anzeige_modus() == "betrag"

    panel.grp_divide.setChecked(True)                # Aenderung -> Callback
    assert meldungen and meldungen[-1][0].schritte[0].aktiv is True

    panel.dd_delta.setValue(9)
    assert meldungen[-1][0].schritte[1].parameter["delta_n"] == 9

    panel._alles_aus()
    assert meldungen[-1][0].aktive_schritte() == []


def test_panel_setze_achsen_grenzen(app):
    from polderfit.gui.verarbeitung_panel import VerarbeitungPanel
    panel = VerarbeitungPanel()
    feld = np.linspace(0.5, 1.5, 100)
    freq = np.linspace(5e9, 20e9, 40)
    panel.setze_achsen(feld, freq)
    assert panel.dd_delta.maximum() == 19            # min(100, 40)//2 - 1
    assert panel.divide_index.minimum() == -100
    assert "T" in panel.divide_wert_label.text()     # Wert-Anzeige fuer Feld-Slice


def test_matrix_ansicht_wendet_kette_an(app):
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    ansicht = MatrixAnsicht()
    ds = _mini_datensatz()
    ansicht.zeige(ds)
    roh = np.array(ansicht._matrix)

    ansicht.setze_verarbeitung(Verarbeitungskette.standard(), "real")
    verarbeitet = ansicht._matrix
    assert verarbeitet.shape == roh.shape
    assert not np.allclose(np.nan_to_num(verarbeitet), np.nan_to_num(roh))
    # dd-Raender (Δn=4) sind NaN.
    assert np.all(np.isnan(verarbeitet[:, :4])) and np.all(np.isnan(verarbeitet[:, -4:]))
    assert "derivative_divide" in ansicht.ax.get_title()


def test_matrix_ansicht_haelt_zustand_bei_fehler(app):
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    from polderfit.verarbeitung import KettenSchritt
    ansicht = MatrixAnsicht()
    ansicht.zeige(_mini_datensatz(n_feld=20))
    gut = Verarbeitungskette.standard()
    ansicht.setze_verarbeitung(gut, "betrag")

    # Δn muss das feste Anzeige-Feldgitter (komplexe_matrix: 400 Punkte) uebersteigen,
    # damit derivative_divide ValueError wirft (400 < 2·250+1).
    kaputt = Verarbeitungskette(schritte=[
        KettenSchritt("derivative_divide", aktiv=True, parameter={"delta_n": 250})])
    with pytest.raises(ValueError):
        ansicht.setze_verarbeitung(kaputt, "betrag")
    assert ansicht._kette is gut                     # alter Zustand wiederhergestellt


def test_hauptfenster_mit_verarbeitung_dock(app):
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    assert w.verarbeitung_dock is not None
    assert w.akt_verarbeitung.isCheckable()

"""Offscreen-Smoke-Tests des Bereichs-Fit-Modus in der Matrix-Ansicht."""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtWidgets

from bbfmr.io.datensatz import Linescan, Messdatensatz


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _ev(ax=None, **kw):
    d = dict(inaxes=ax, xdata=None, ydata=None, step=0, key=None, dblclick=False, button=1)
    d.update(kw)
    return SimpleNamespace(**d)


def _mini_datensatz(n=10):
    B = np.linspace(2.5, 3.5, 40)
    freqs = np.linspace(5e9, 50e9, n)
    ls = [Linescan(frequenz=float(f), feld=B, re=np.cos(20 * B), im=np.sin(20 * B))
          for f in freqs]
    return Messdatensatz(quelle="t", format_typ="sortiert", linescans=ls)


def _ziehe_box(ansicht, x0, y0, x1, y1):
    """Simuliert Druecken, Ziehen (ueber der Schwelle) und Loslassen."""
    ansicht._on_press(_ev(ansicht.ax, xdata=x0, ydata=y0))
    ansicht._on_move(_ev(ansicht.ax, xdata=x1, ydata=y1))
    ansicht._on_release(_ev(ansicht.ax, xdata=x1, ydata=y1))


def test_bereichs_fit_meldet_rechteck_statt_zoom(app):
    from bbfmr.gui.matrix_ansicht import MatrixAnsicht
    ansicht = MatrixAnsicht()
    ansicht.zeige(_mini_datensatz())
    xlim_vorher = ansicht.ax.get_xlim()

    empfangen = {}
    ansicht.starte_bereichs_fit(
        lambda b0, b1, f0, f1: empfangen.update(b0=b0, b1=b1, f0=f0, f1=f1))
    _ziehe_box(ansicht, 3.2, 40.0, 2.8, 10.0)  # absichtlich "verdreht" gezogen

    assert empfangen == {"b0": 2.8, "b1": 3.2, "f0": 10.0, "f1": 40.0}
    assert ansicht._bereich_fertig is None                      # Modus beendet
    assert ansicht.ax.get_xlim() == xlim_vorher                 # NICHT gezoomt

    # Danach zoomt ein Rechteck wieder normal.
    _ziehe_box(ansicht, 2.7, 15.0, 3.3, 35.0)
    assert ansicht.ax.get_xlim() != xlim_vorher


def test_escape_bricht_bereichs_fit_ab(app):
    from bbfmr.gui.matrix_ansicht import MatrixAnsicht
    ansicht = MatrixAnsicht()
    ansicht.zeige(_mini_datensatz())
    aufrufe = []
    ansicht.starte_bereichs_fit(lambda *a: aufrufe.append(a))
    ansicht._on_key(_ev(ansicht.ax, key="escape"))
    assert ansicht._bereich_fertig is None
    _ziehe_box(ansicht, 3.2, 40.0, 2.8, 10.0)                   # zoomt jetzt normal
    assert not aufrufe


def test_hauptfenster_bereichsfit_verlangt_fits(app):
    from bbfmr.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    assert w.akt_bereich is not None
    # Ohne Ergebnisse zeigt _bereich_fitten nur einen Hinweis - kein Modus aktiv.
    # (QMessageBox oeffnet modal; im Offscreen-Test genuegt der Zustands-Check
    # ueber einen nicht gestarteten Modus, deshalb hier nur Existenz + Sperre.)
    assert w.stapel is None

# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Smoke-Tests des interaktiven In-Plot-Fittings (GUI-Seite):

ziehbare Fenstergrenzen, Ausschlusszonen-Zeichnen, Fenster-Panel und die
abdockbaren Ansichten (Multi-Monitor).
"""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtWidgets

from polderfit.fit.batch import Ausschlusszone
from polderfit.io.datensatz import Linescan, Messdatensatz


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


def _ansicht_mit_grenzen(callback=None):
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    ansicht = MatrixAnsicht()
    ds = _mini_datensatz()
    ansicht.zeige(ds)
    fenster = [(2.7 + 0.01 * i, 3.3 + 0.01 * i) for i in range(len(ds))]
    ansicht.zeige_fenstergrenzen(ds.frequenzen, fenster, grenze_gezogen=callback)
    return ansicht, ds, fenster


def test_grenzen_werden_gezeichnet_und_versteckt(app):
    ansicht, ds, fenster = _ansicht_mit_grenzen()
    labels = [ln.get_label() for ln in ansicht.ax.lines]
    assert "_grenze_links" in labels and "_grenze_rechts" in labels
    ansicht.verstecke_fenstergrenzen()
    labels = [ln.get_label() for ln in ansicht.ax.lines]
    assert "_grenze_links" not in labels


def test_grenze_ziehen_meldet_index_seite_wert(app):
    gezogen = {}
    ansicht, ds, fenster = _ansicht_mit_grenzen(
        lambda i, seite, wert: gezogen.update(index=i, seite=seite, wert=wert))

    # Nahe der linken Grenze von Linescan 4 anfassen (f in GHz auf der y-Achse).
    f4_ghz = ds.frequenzen[4] / 1e9
    links4 = fenster[4][0]
    ansicht._on_press(_ev(ansicht.ax, xdata=links4 + 0.001, ydata=f4_ghz))
    assert ansicht._drag_grenze == ("links", 4)
    ansicht._on_move(_ev(ansicht.ax, xdata=2.60, ydata=f4_ghz))
    ansicht._on_release(_ev(ansicht.ax, xdata=2.60, ydata=f4_ghz))
    assert gezogen == {"index": 4, "seite": "links", "wert": 2.60}
    assert ansicht._drag_grenze is None


def test_klick_fern_der_grenze_bleibt_frequenzwahl(app):
    gewaehlt = []
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    ansicht = MatrixAnsicht(frequenz_gewaehlt=gewaehlt.append)
    ds = _mini_datensatz()
    ansicht.zeige(ds)
    ansicht.zeige_fenstergrenzen(ds.frequenzen, [(2.7, 3.3)] * len(ds))
    # Klick weit weg von beiden Grenzen -> normale Frequenzauswahl.
    ansicht._on_press(_ev(ansicht.ax, xdata=3.0, ydata=ds.frequenzen[6] / 1e9))
    assert ansicht._drag_grenze is None
    ansicht._on_release(_ev(ansicht.ax, xdata=3.0, ydata=ds.frequenzen[6] / 1e9))
    assert gewaehlt == [6]


def test_ausschluss_zeichnen_meldet_rechteck(app):
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    ansicht = MatrixAnsicht()
    ansicht.zeige(_mini_datensatz())
    empfangen = {}
    ansicht.starte_ausschluss_zeichnen(
        lambda b0, b1, f0, f1: empfangen.update(b0=b0, b1=b1, f0=f0, f1=f1))
    ansicht._on_press(_ev(ansicht.ax, xdata=2.6, ydata=8.0))
    ansicht._on_move(_ev(ansicht.ax, xdata=3.0, ydata=20.0))
    ansicht._on_release(_ev(ansicht.ax, xdata=3.0, ydata=20.0))
    assert empfangen == {"b0": 2.6, "b1": 3.0, "f0": 8.0, "f1": 20.0}
    assert ansicht._ausschluss_fertig is None


def test_zonen_anzeige(app):
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    ansicht = MatrixAnsicht()
    ansicht.zeige(_mini_datensatz())
    zonen = [Ausschlusszone(2.6, 2.8, 10e9, 20e9), Ausschlusszone(3.0, 3.2, 30e9, 40e9)]
    ansicht.zeige_ausschlusszonen(zonen)
    assert len(ansicht._zonen_patches) == 2
    ansicht.zeige_ausschlusszonen([])
    assert ansicht._zonen_patches == []


def test_fenster_panel_callbacks_und_zustand(app):
    from polderfit.gui.fenster_panel import FensterPanel
    aufrufe = []
    panel = FensterPanel(
        grenzen_umschalten=lambda an: aufrufe.append(("grenzen", an)),
        breite_anwenden=lambda p, m: aufrufe.append(("breite", p, m)),
        propagieren=lambda m: aufrufe.append(("prop", m)),
        zone_zeichnen=lambda: aufrufe.append(("zone",)),
        zone_entfernen=lambda i: aufrufe.append(("weg", i)),
    )
    assert panel.modus() == "ueberschreiben"
    panel.modus_combo.setCurrentIndex(1)
    assert panel.modus() == "ergaenzen"

    panel.chk_grenzen.setChecked(True)
    panel.breite_spin.setValue(25)
    panel.btn_breite.click()
    panel.btn_propagieren.click()
    panel.btn_zone.click()
    assert ("grenzen", True) in aufrufe
    assert ("breite", 25, "ergaenzen") in aufrufe
    assert ("prop", "ergaenzen") in aufrufe
    assert ("zone",) in aufrufe

    panel.setze_zonen([Ausschlusszone(2.6, 2.8, 10e9, 20e9)])
    assert panel.zonen_liste.count() == 1
    panel.zonen_liste.setCurrentRow(0)
    panel.btn_zone_entfernen.click()
    assert ("weg", 0) in aufrufe

    panel.setze_breite_info(17, 2.7, 3.1)
    assert "17 Punkte" in panel.breite_info.text()


def test_hauptfenster_docks_fuer_multimonitor(app):
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    # Linescan-Fit-Panel und Fenster-Panel sind abdockbare Fenster.
    for dock in (w.linescan_dock, w.fenster_dock):
        assert bool(dock.features() & QtWidgets.QDockWidget.DockWidgetFloatable)
    # Farbplot ist das zentrale Widget.
    assert w.centralWidget() is w.matrix
    assert w.fensterpanel is not None
    assert w.akt_fenster.isCheckable() and w.akt_linescan.isCheckable()
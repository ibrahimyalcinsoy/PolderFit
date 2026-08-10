# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Smoke-Tests der Ausschlusszonen (GUI-Seite) und der abdockbaren
Ansichten (Multi-Monitor)."""

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
    assert ansicht.modus is None  # Modus nach dem Rechteck beendet


def test_zonen_anzeige(app):
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    ansicht = MatrixAnsicht()
    ansicht.zeige(_mini_datensatz())
    zonen = [Ausschlusszone(2.6, 2.8, 10e9, 20e9), Ausschlusszone(3.0, 3.2, 30e9, 40e9)]
    ansicht.zeige_ausschlusszonen(zonen)
    assert len(ansicht._zonen_patches) == 2
    ansicht.zeige_ausschlusszonen([])
    assert ansicht._zonen_patches == []


def test_zonen_panel_callbacks_und_zustand(app):
    from polderfit.gui.zonen_panel import ZonenPanel
    aufrufe = []
    panel = ZonenPanel(
        zone_umschalten=lambda an: aufrufe.append(("zone", an)),
        zone_entfernen=lambda i: aufrufe.append(("weg", i)),
    )
    # Zeichnen-Knopf ist checkbar (sichtbarer Modus-Zustand).
    assert panel.btn_zone.isCheckable()
    panel.btn_zone.setChecked(True)
    assert ("zone", True) in aufrufe

    # Sync vom Modus-Manager loest KEINEN Rueckruf aus.
    aufrufe.clear()
    panel.setze_modus_aktiv(False)
    assert panel.btn_zone.isChecked() is False
    assert aufrufe == []

    panel.setze_zonen([Ausschlusszone(2.6, 2.8, 10e9, 20e9)])
    assert panel.zonen_liste.count() == 1
    panel.zonen_liste.setCurrentRow(0)
    panel.btn_zone_entfernen.click()
    assert ("weg", 0) in aufrufe


def test_hauptfenster_docks_fuer_multimonitor(app):
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    # Linescan-Fit-Panel und Zonen-Panel sind abdockbare Fenster.
    for dock in (w.linescan_dock, w.zonen_dock):
        assert bool(dock.features() & QtWidgets.QDockWidget.DockWidgetFloatable)
    # Farbplot ist das zentrale Widget.
    assert w.centralWidget() is w.matrix
    assert w.zonenpanel is not None
    assert w.akt_zonen_panel.isCheckable() and w.akt_linescan.isCheckable()
    # Aufgeraeumter Start: Panels erscheinen erst bei Bedarf.
    for dock in (w.linescan_dock, w.zonen_dock, w.verarbeitung_dock,
                 w.aktivitaet_dock, w.ausreisser_dock):
        assert dock.isHidden()

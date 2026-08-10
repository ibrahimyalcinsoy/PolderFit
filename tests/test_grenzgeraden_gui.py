# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Tests des Grenzgeraden-Werkzeugs (GUI-Seite), der Navigator-
Farbskala und des Vollbereich-Umschalters am Linescan-Panel."""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtWidgets

from polderfit.fit.fenster_steuerung import Grenzgerade
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


def _ansicht():
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    m = MatrixAnsicht()
    m.zeige(_mini_datensatz())
    return m


def test_gerade_modus_zwei_klicks(app):
    m = _ansicht()
    got = {}
    m.starte_gerade_zeichnen(lambda p: got.__setitem__("p", p))
    assert m.modus == "gerade"
    m._on_press(_ev(m.ax, xdata=2.7, ydata=10.0))
    assert "p" not in got
    m._on_press(_ev(m.ax, xdata=3.2, ydata=40.0))
    assert got["p"] == [(2.7, 10.0), (3.2, 40.0)]
    assert m.modus is None


def test_geraden_overlay_und_saeume(app):
    m = _ansicht()
    g = Grenzgerade(b1=2.8, f1=10e9, b2=3.2, f2=40e9)
    m.zeige_grenzgeraden([g])
    labels = [a.get_label() for a in m._geraden_artists]
    assert labels.count("_gerade_saum") == 2          # gruener + roter Saum
    assert "_gerade" in labels and "_gerade_griff" in labels
    m.zeige_grenzgeraden([])
    assert m._geraden_artists == []


def test_endpunkt_ziehen_meldet_neue_geometrie(app):
    m = _ansicht()
    g = Grenzgerade(b1=2.8, f1=10e9, b2=3.2, f2=40e9)
    gemeldet = {}
    m.zeige_grenzgeraden(
        [g], endpunkt_geaendert=lambda i, b1, f1, b2, f2:
        gemeldet.update(i=i, b1=b1, f1=f1, b2=b2, f2=f2))
    # Endpunkt p2 anfassen und verschieben.
    m._on_press(_ev(m.ax, xdata=3.2, ydata=40.0))
    assert m._drag_endpunkt == (0, "p2")
    m._on_move(_ev(m.ax, xdata=3.4, ydata=45.0))
    m._on_release(_ev(m.ax, xdata=3.4, ydata=45.0))
    assert m._drag_endpunkt is None
    assert gemeldet["i"] == 0
    assert abs(gemeldet["b2"] - 3.4) < 1e-9 and abs(gemeldet["f2"] - 45.0) < 1e-9
    assert abs(g.b2 - 3.4) < 1e-9 and abs(g.f2 - 45e9) < 1e-3


def test_doppelklick_wechselt_seite(app):
    m = _ansicht()
    g = Grenzgerade(b1=3.0, f1=5e9, b2=3.0, f2=50e9)   # senkrechte Linie bei 3.0 T
    gewechselt = []
    m.zeige_grenzgeraden([g], seite_gewechselt=gewechselt.append)
    # Doppelklick direkt auf der Linie -> Seitenwechsel, KEIN Zoom-Reset noetig.
    m._on_press(_ev(m.ax, xdata=3.0, ydata=27.0, dblclick=True))
    assert gewechselt == [0]
    # Doppelklick fern der Linie -> normaler Zoom-Reset (kein Seitenwechsel).
    m._on_press(_ev(m.ax, xdata=2.55, ydata=27.0, dblclick=True))
    assert gewechselt == [0]


def test_zonen_panel_geraden_steuerung(app):
    from polderfit.gui.zonen_panel import ZonenPanel
    aufrufe = []
    panel = ZonenPanel(
        gerade_umschalten=lambda an: aufrufe.append(("modus", an)),
        gerade_seite=lambda i: aufrufe.append(("seite", i)),
        gerade_entfernen=lambda i: aufrufe.append(("weg", i)),
        geraden_fit=lambda: aufrufe.append(("fit",)),
    )
    assert panel.btn_gerade.isCheckable()
    panel.btn_gerade.setChecked(True)
    assert ("modus", True) in aufrufe

    aufrufe.clear()
    panel.setze_gerade_modus_aktiv(False)     # Sync ohne Rueckruf
    assert panel.btn_gerade.isChecked() is False and aufrufe == []

    panel.setze_geraden([Grenzgerade(b1=2.8, f1=10e9, b2=3.2, f2=40e9)])
    assert panel.geraden_liste.count() == 1
    panel.geraden_liste.setCurrentRow(0)
    panel.btn_gerade_seite.click()
    panel.btn_gerade_entfernen.click()
    panel.btn_geraden_fit.click()
    assert ("seite", 0) in aufrufe and ("weg", 0) in aufrufe and ("fit",) in aufrufe


def test_navigator_robuste_farbskala(app):
    from polderfit.gui.navigator_ansicht import NavigatorAnsicht
    nav = NavigatorAnsicht()
    rng = np.random.default_rng(3)
    matrix = rng.normal(size=(20, 30))    # normale Struktur ...
    matrix[10, 15] = 1e6                  # ... plus einzelner dd-Ausreisser
    nav.zeige(matrix, (2.5, 3.5, 5.0, 50.0))
    bild = nav.ax.images[0]
    vmin, vmax = bild.get_clim()
    assert vmax < 1e6              # Ausreisser dominiert die Skala nicht mehr


def test_vollbereich_checkbox_spiegelt_aktion(app):
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    assert w.chk_vollbereich.isChecked() is False
    w.chk_vollbereich.setChecked(True)
    assert w.akt_vollbereich.isChecked() is True
    w.akt_vollbereich.setChecked(False)
    assert w.chk_vollbereich.isChecked() is False

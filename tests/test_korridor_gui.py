# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Tests der Korridor-Werkzeuge (Farbplot, Panel, Hauptfenster)."""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtWidgets

from polderfit.fit.korridor import Anker, Korridor
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


def test_korridor_modus_zwei_klicks(app):
    m = _ansicht()
    erhalten = []
    m.starte_korridor_zeichnen(lambda p: erhalten.append(p))
    assert m.modus == "korridor"
    m._on_press(_ev(m.ax, xdata=2.7, ydata=10.0))
    assert m.modus == "korridor" and not erhalten
    m._on_press(_ev(m.ax, xdata=3.2, ydata=40.0))
    assert m.modus is None and erhalten == [[(2.7, 10.0), (3.2, 40.0)]]


def test_anker_modus_bleibt_aktiv_bis_esc(app):
    m = _ansicht()
    klicks = []
    m.starte_anker_setzen(lambda p: klicks.append(p))
    m._on_press(_ev(m.ax, xdata=2.8, ydata=12.0))
    m._on_press(_ev(m.ax, xdata=2.9, ydata=20.0))
    assert m.modus == "anker" and len(klicks) == 2
    m._on_key(_ev(m.ax, key="escape"))
    assert m.modus is None


def test_korridor_overlay_und_anker_drag(app):
    m = _ansicht()
    k = Korridor(mode=2, anker=[Anker(10e9, 2.7, 2.8), Anker(40e9, 3.1, 3.2)])
    gemeldet = []
    m.zeige_korridore([k], aktiv=2, anker_geaendert=lambda *a: gemeldet.append(a))
    labels = [str(a.get_label()) for a in m._korridor_artists]
    assert "_korridor" in labels and "_korridor_anker" in labels and "_korridor_mode" in labels
    # Anker rechts bei 10 GHz anfassen und nach 2.85 T ziehen
    m._on_press(_ev(m.ax, xdata=2.8, ydata=10.0))
    assert m._drag_anker == (0, 0, "rechts")
    m._on_move(_ev(m.ax, xdata=2.85, ydata=10.0))
    m._on_release(_ev(m.ax, xdata=2.85, ydata=10.0))
    assert m._drag_anker is None
    assert gemeldet and gemeldet[0][:3] == (2, 0, "rechts") and abs(gemeldet[0][3] - 2.85) < 1e-9
    assert abs(k.anker[0].b_rechts - 2.85) < 1e-9


def test_zonen_panel_korridorliste(app):
    from polderfit.gui.zonen_panel import ZonenPanel
    gewaehlt = []
    p = ZonenPanel(korridor_gewaehlt=lambda mode: gewaehlt.append(mode))
    p.setze_korridore([])
    assert p.korridor_liste.count() == 1 and p.mode_neu() == 1
    assert not p.btn_fit.isEnabled()
    k1 = Korridor(mode=1, anker=[Anker(10e9, 2.7, 2.8)])
    k2 = Korridor(mode=2, anker=[Anker(10e9, 2.9, 3.0), Anker(20e9, 3.0, 3.1)])
    p.setze_korridore([k1, k2], {1: (5, 1), 2: (3, 0)})
    assert p.korridor_liste.count() == 2 and p.mode_neu() == 3
    assert "1 ⚠" in p.korridor_liste.item(0).text()
    p.korridor_liste.setCurrentRow(1)
    assert gewaehlt == [2] and p.mode_aktiv() == 2 and p.korridor_aktiv() is k2
    assert p.btn_fit.isEnabled()


def test_hauptfenster_korridor_anlegen_anker_und_undo(app):
    from polderfit.gui.hauptfenster import Hauptfenster
    from polderfit.fit.batch import leerer_stapel
    w = Hauptfenster()
    d = _mini_datensatz()
    w.datensatz_voll = d
    w.matrix.zeige(d)
    w.stapel = leerer_stapel(d)
    w._korridor_gezeichnet([(2.7, 10.0), (3.2, 40.0)])
    assert len(w._korridore) == 1 and w._korridore[0].mode == 1
    assert w._mode_aktiv == 1 and w.zonenpanel.mode_aktiv() == 1
    w._korridor_gezeichnet([(2.9, 10.0), (3.4, 40.0)])
    assert [k.mode for k in w._korridore] == [1, 2] and w._mode_aktiv == 2
    # Anker setzen: naehere Grenze bei 25 GHz auf das geklickte Feld
    k2 = w._korridore[1]
    lo, hi = k2.grenzen(25e9)
    w._anker_geklickt((hi + 0.002, 25.0))
    assert len(k2.anker) == 3 and abs(k2.grenzen(25e9)[1] - (hi + 0.002)) < 1e-9
    w._rueckgaengig()
    assert len(w._korridore[1].anker) == 2
    w._korridor_entfernen(2)
    assert [k.mode for k in w._korridore] == [1] and w._mode_aktiv == 1

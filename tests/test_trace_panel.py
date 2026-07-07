# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Smoke-Tests des Call-Trace-Panels (Entwickler-Werkzeug)."""

import os
import sys

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_tracer_meldet_polderfit_aufrufe(app):
    from polderfit.gui.trace_panel import FunktionsTracer, aktiver_tracer
    from polderfit.physik import konstanten

    zeilen = []
    tracer = FunktionsTracer()
    tracer.zeile.connect(zeilen.append)  # gleicher Thread -> synchrone Zustellung
    tracer.aktiviere()
    try:
        assert aktiver_tracer() is tracer
        konstanten.gamma_aus_g(2.0)
    finally:
        tracer.deaktiviere()

    assert any("konstanten.gamma_aus_g" in z for z in zeilen)
    assert sys.getprofile() is None        # Profiler sauber entfernt
    assert aktiver_tracer() is None


def test_trace_panel_umschalten(app):
    from polderfit.gui.trace_panel import TracePanel, aktiver_tracer
    panel = TracePanel()
    assert panel.ist_aktiv() is False
    panel.chk_aktiv.setChecked(True)
    assert aktiver_tracer() is panel.tracer
    panel.chk_aktiv.setChecked(False)
    assert aktiver_tracer() is None
    assert sys.getprofile() is None


def test_hauptfenster_hat_trace_dock(app):
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    assert w.trace_dock is not None
    assert w.akt_trace.isCheckable()
    assert w.trace_dock.isHidden()          # standardmaessig ausgeblendet
    assert w.tracepanel.ist_aktiv() is False

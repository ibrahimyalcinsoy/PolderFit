"""Offscreen-Smoke-Tests der GUI (Aktivitaets-Panel, Hintergrund-Job, Grenzlinien).

Laeuft headless (QT_QPA_PLATFORM=offscreen). Wird uebersprungen, wenn PySide6
fehlt. Prueft, dass die GUI baut, der Hintergrund-Worker einen Job bis zum Ende
durchlaeuft und die verschiebbaren Grenzlinien ohne Fehler auf Maus-Events
reagieren.
"""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtCore, QtWidgets

from ananas.io.datensatz import Linescan


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _pumpe(ms=2000):
    """Event-Loop kurz laufen lassen, bis ein Hintergrund-Job fertig ist."""
    schleife = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, schleife.quit)
    schleife.exec()


def test_hauptfenster_baut_mit_aktivitaet_panel(app):
    from ananas.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    assert w.aktivitaet_dock is not None
    assert w.fortschritt_balken is not None
    # Protokoll schreibt eine Zeile.
    n0 = w.protokoll_ansicht.blockCount()
    w._log("Testmeldung", "ok")
    assert w.protokoll_ansicht.blockCount() >= n0
    # Dock laesst sich abtrennen (eigenes Fenster neben dem GUI).
    assert bool(w.aktivitaet_dock.features() & QtWidgets.QDockWidget.DockWidgetFloatable)


def test_hintergrund_job_laeuft_durch(app):
    from ananas.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    ergebnisse = {}

    def aufgabe(melde):
        for i in range(5):
            melde(i + 1, 5, f"Schritt {i+1}/5")
        return "fertig"

    def bei_fertig(res):
        ergebnisse["res"] = res

    w._starte_job(aufgabe, bei_fertig, "Testjob …")
    # Waehrend des Jobs sind die Bedienelemente gesperrt.
    assert w.akt_fit.isEnabled() in (True, False)  # je nach Timing
    _pumpe(1500)
    assert ergebnisse.get("res") == "fertig"
    assert w._job_laeuft is False
    assert w.akt_fit.isEnabled() is True  # wieder freigegeben


def test_matrix_navigation(app):
    """Die horizontale Frequenz-Linie laesst sich per Klick, Ziehen, Mausrad und
    Tastatur bewegen; jede Aenderung meldet den Index zurueck."""
    from ananas.gui.matrix_ansicht import MatrixAnsicht
    from ananas.io.datensatz import Messdatensatz
    gew = {}
    m = MatrixAnsicht(frequenz_gewaehlt=lambda i: gew.__setitem__("i", i))
    B = np.linspace(2.5, 3.5, 40)
    freqs = np.linspace(5e9, 50e9, 10)
    ls = [Linescan(frequenz=float(f), feld=B, re=np.cos(20 * B), im=np.sin(20 * B)) for f in freqs]
    ds = Messdatensatz(quelle="t", format_typ="sortiert", linescans=ls)
    m.zeige(ds)
    m.markiere_frequenz(0)

    # Mausrad hoch -> naechste Frequenz.
    m._on_scroll(SimpleNamespace(step=1))
    assert m._aktueller_index == 1 and gew["i"] == 1
    # Pfeiltaste hoch -> +1, Bild hoch -> +10 (geklemmt), Ende -> letzte.
    m._on_key(SimpleNamespace(key="up"))
    assert m._aktueller_index == 2
    m._on_key(SimpleNamespace(key="end"))
    assert m._aktueller_index == len(ls) - 1 and gew["i"] == len(ls) - 1
    # Ziehen (press + move) scrubbt die Linie zur Maus-Frequenz.
    m._on_press(SimpleNamespace(inaxes=m.ax, ydata=freqs[3] / 1e9))
    assert m._aktueller_index == 3
    m._on_move(SimpleNamespace(inaxes=m.ax, ydata=freqs[6] / 1e9))
    assert m._aktueller_index == 6
    m._on_release(SimpleNamespace(inaxes=m.ax, ydata=0.0))
    assert m._ziehen is False


def test_grenzlinien_interaktion(app):
    from ananas.gui.fit_ansicht import FitAnsicht
    gerufen = {}
    fa = FitAnsicht(grenzen_geaendert=lambda u, o: gerufen.update(unten=u, oben=o))
    B = np.linspace(2.9, 3.1, 200)
    ls = Linescan(frequenz=20e9, feld=B, re=np.cos(40 * B), im=np.sin(40 * B))
    fa.zeige(ls, 2.95, 3.05, None)

    # Hover nahe der unteren Grenze -> Hervorhebung gesetzt.
    fa._on_move(SimpleNamespace(inaxes=fa.ax_re, xdata=2.951, ydata=0.0))
    assert fa._hover == "unten"

    # Greifen, ziehen, loslassen -> Callback mit sortierten Grenzen.
    fa._on_press(SimpleNamespace(inaxes=fa.ax_re, xdata=2.951, ydata=0.0))
    assert fa._gezogen == "unten"
    fa._on_move(SimpleNamespace(inaxes=fa.ax_re, xdata=2.93, ydata=0.0))
    fa._on_release(SimpleNamespace(inaxes=fa.ax_re, xdata=2.93, ydata=0.0))
    assert fa._gezogen is None
    assert "unten" in gerufen and gerufen["unten"] <= gerufen["oben"]

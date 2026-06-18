"""Offscreen-Smoke-Tests der GUI.

Laeuft headless (QT_QPA_PLATFORM=offscreen). Wird uebersprungen, wenn PySide6
fehlt. Prueft Aufbau, Hintergrund-Job, Uebersichts-Navigation/Zoom, Navigator,
Problemfit-Ausblenden, klickbares Logo/Hilfe und die Grenzlinien-Interaktion.
"""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtCore, QtWidgets

from ananas.io.datensatz import Linescan, Messdatensatz


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _pumpe(ms=2000):
    """Event-Loop kurz laufen lassen, bis ein Hintergrund-Job fertig ist."""
    schleife = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, schleife.quit)
    schleife.exec()


def _ev(ax=None, **kw):
    """Synthetisches Matplotlib-Event mit allen abgefragten Attributen."""
    d = dict(inaxes=ax, xdata=None, ydata=None, step=0, key=None, dblclick=False, button=1)
    d.update(kw)
    return SimpleNamespace(**d)


def _mini_datensatz(n=10):
    B = np.linspace(2.5, 3.5, 40)
    freqs = np.linspace(5e9, 50e9, n)
    ls = [Linescan(frequenz=float(f), feld=B, re=np.cos(20 * B), im=np.sin(20 * B)) for f in freqs]
    return Messdatensatz(quelle="t", format_typ="sortiert", linescans=ls)


def test_hauptfenster_baut_mit_panels(app):
    from ananas.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    assert w.aktivitaet_dock is not None and w.fortschritt_balken is not None
    assert w.navigator_dock is not None
    assert w.navigator_dock.isHidden() is True  # Navigator erst beim Zoomen
    n0 = w.protokoll_ansicht.blockCount()
    w._log("Testmeldung", "ok")
    assert w.protokoll_ansicht.blockCount() >= n0
    assert bool(w.aktivitaet_dock.features() & QtWidgets.QDockWidget.DockWidgetFloatable)


def test_hintergrund_job_laeuft_durch(app):
    from ananas.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    ergebnisse = {}

    def aufgabe(melde):
        for i in range(5):
            melde(i + 1, 5, f"Schritt {i+1}/5")
        return "fertig"

    w._starte_job(aufgabe, lambda res: ergebnisse.__setitem__("res", res), "Testjob …")
    _pumpe(1500)
    assert ergebnisse.get("res") == "fertig"
    assert w._job_laeuft is False
    assert w.akt_fit.isEnabled() is True


def test_matrix_frequenz_navigation(app):
    """Frequenzwahl per Klick, Umschalt+Mausrad und Tastatur; meldet den Index."""
    from ananas.gui.matrix_ansicht import MatrixAnsicht
    gew = {}
    m = MatrixAnsicht(frequenz_gewaehlt=lambda i: gew.__setitem__("i", i))
    ds = _mini_datensatz(10)
    m.zeige(ds)
    m.markiere_frequenz(0)
    freqs = ds.frequenzen

    m._on_scroll(_ev(m.ax, step=1, key="shift"))          # Umschalt+Rad -> +1
    assert m._aktueller_index == 1 and gew["i"] == 1
    m._on_key(_ev(m.ax, key="up"))
    assert m._aktueller_index == 2
    m._on_key(_ev(m.ax, key="end"))
    assert m._aktueller_index == len(freqs) - 1
    # Klick (press + release ohne Bewegung) -> Frequenz waehlen.
    m._on_press(_ev(m.ax, xdata=3.0, ydata=freqs[3] / 1e9))
    m._on_release(_ev(m.ax, xdata=3.0, ydata=freqs[3] / 1e9))
    assert m._aktueller_index == 3


def test_matrix_zoom_wheel_box_doppelklick(app):
    """Mausrad-Zoom, Aufzieh-Kästchen und Doppelklick-Reset; Zoom-Callback feuert."""
    from ananas.gui.matrix_ansicht import MatrixAnsicht
    zooms = []
    m = MatrixAnsicht(zoom_geaendert=lambda xl, yl, z: zooms.append(z))
    m.zeige(_mini_datensatz(10))
    x0, x1 = m.ax.get_xlim()

    # Mausrad rein -> sichtbarer Bereich schrumpft, Callback meldet "gezoomt".
    m._on_scroll(_ev(m.ax, step=1, xdata=3.0, ydata=27.0))
    nx0, nx1 = m.ax.get_xlim()
    assert (nx1 - nx0) < (x1 - x0)
    assert zooms[-1] is True

    # Doppelklick -> Reset auf vollen Bereich.
    m._on_press(_ev(m.ax, xdata=3.0, ydata=27.0, dblclick=True))
    assert abs((m.ax.get_xlim()[1] - m.ax.get_xlim()[0]) - (x1 - x0)) < 1e-6
    assert zooms[-1] is False

    # Aufzieh-Kästchen -> Zoom auf den markierten Bereich.
    m._on_press(_ev(m.ax, xdata=2.7, ydata=10.0))
    m._on_move(_ev(m.ax, xdata=3.2, ydata=30.0))
    assert m._box_aktiv is True
    m._on_release(_ev(m.ax, xdata=3.2, ydata=30.0))
    bx = m.ax.get_xlim()
    by = m.ax.get_ylim()
    assert abs(bx[0] - 2.7) < 1e-6 and abs(bx[1] - 3.2) < 1e-6
    assert abs(by[0] - 10.0) < 1e-6 and abs(by[1] - 30.0) < 1e-6


def test_problemfits_ausblenden(app):
    from ananas.gui.matrix_ansicht import MatrixAnsicht
    m = MatrixAnsicht()
    ds = _mini_datensatz(10)
    m.zeige(ds)
    freqs = ds.frequenzen
    bres = np.full(len(freqs), 3.0)
    problem = np.zeros(len(freqs), dtype=bool)
    problem[::2] = True
    m.aktualisiere_resonanz(freqs, bres, problem)
    labels = [ln.get_label() for ln in m.ax.lines]
    assert "_resonanz" in labels and "_resonanz_problem" in labels
    m.setze_problemfits_ausblenden(True)
    labels = [ln.get_label() for ln in m.ax.lines]
    assert "_resonanz" in labels and "_resonanz_problem" not in labels


def test_navigator(app):
    from ananas.gui.navigator_ansicht import NavigatorAnsicht
    gerufen = {}
    nav = NavigatorAnsicht(bereich_gewaehlt=lambda xl, yl: gerufen.update(xl=xl, yl=yl))
    nav.zeige(np.zeros((10, 20)), (2.5, 3.5, 5.0, 50.0))
    nav.setze_ausschnitt((2.7, 3.2), (10.0, 30.0))
    assert nav._rect is not None
    nav._on_press(_ev(nav.ax, xdata=3.0, ydata=27.0))
    assert "xl" in gerufen and len(gerufen["xl"]) == 2


def test_logo_hilfe_und_navigator_sichtbarkeit(app):
    from ananas.gui.hauptfenster import Hauptfenster, REPO_URL
    w = Hauptfenster()
    assert w.btn_logo is not None
    htmltext = w._hilfe_html()
    assert REPO_URL in htmltext and "Walther-Meißner" in htmltext
    # Navigator erscheint beim Zoomen, verschwindet beim Zurücksetzen.
    w._auf_zoom((2.6, 2.8), (10.0, 20.0), True)
    assert w.navigator_dock.isHidden() is False
    w._auf_zoom((2.3, 4.4), (0.0, 50.0), False)
    assert w.navigator_dock.isHidden() is True


def test_matrix_dispersion_seed(app):
    """Dispersions-Seed: zwei Klicks in der Übersicht liefern die zwei Resonanzpunkte."""
    from ananas.gui.matrix_ansicht import MatrixAnsicht
    got = {}
    m = MatrixAnsicht()
    m.zeige(_mini_datensatz(10))
    m.starte_dispersion_seed(lambda p: got.__setitem__("p", p))
    m._on_press(_ev(m.ax, xdata=2.0, ydata=10.0))   # erster Punkt
    assert "p" not in got                            # noch nicht fertig
    m._on_press(_ev(m.ax, xdata=3.0, ydata=40.0))   # zweiter Punkt -> Callback
    assert "p" in got and len(got["p"]) == 2
    assert got["p"][0] == (2.0, 10.0) and got["p"][1] == (3.0, 40.0)
    assert m._seed_fertig is None                    # Seed-Modus wieder aus


def test_grenzlinien_interaktion(app):
    from ananas.gui.fit_ansicht import FitAnsicht
    gerufen = {}
    fa = FitAnsicht(grenzen_geaendert=lambda u, o: gerufen.update(unten=u, oben=o))
    B = np.linspace(2.9, 3.1, 200)
    ls = Linescan(frequenz=20e9, feld=B, re=np.cos(40 * B), im=np.sin(40 * B))
    fa.zeige(ls, 2.95, 3.05, None)

    fa._on_move(_ev(fa.ax_re, xdata=2.951, ydata=0.0))
    assert fa._hover == "unten"
    fa._on_press(_ev(fa.ax_re, xdata=2.951, ydata=0.0))
    assert fa._gezogen == "unten"
    fa._on_move(_ev(fa.ax_re, xdata=2.93, ydata=0.0))
    fa._on_release(_ev(fa.ax_re, xdata=2.93, ydata=0.0))
    assert fa._gezogen is None
    assert "unten" in gerufen and gerufen["unten"] <= gerufen["oben"]

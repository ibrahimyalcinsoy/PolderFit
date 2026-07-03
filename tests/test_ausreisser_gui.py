"""Offscreen-Smoke-Tests des Ausreisser-Managements (GUI-Seite)."""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtWidgets

from bbfmr.fit.batch import StapelErgebnis
from bbfmr.fit.linescan_fit import FitErgebnis
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


def _ansicht_mit_overlay():
    from bbfmr.gui.matrix_ansicht import MatrixAnsicht
    ansicht = MatrixAnsicht()
    ds = _mini_datensatz()
    ansicht.zeige(ds)
    bres = np.linspace(2.7, 3.3, len(ds))
    ansicht.aktualisiere_resonanz(ds.frequenzen, bres,
                                  problematisch=np.zeros(len(ds), dtype=bool))
    return ansicht, ds, bres


def _overlay_punkte(ansicht):
    for ln in ansicht.ax.lines:
        if ln.get_label() == "_resonanz":
            return len(ln.get_xdata())
    return 0


def test_ausgeschlossene_punkte_verschwinden_aus_darstellung(app):
    ansicht, ds, bres = _ansicht_mit_overlay()
    assert _overlay_punkte(ansicht) == len(ds)
    ausgeschlossen = np.zeros(len(ds), dtype=bool)
    ausgeschlossen[[2, 5]] = True
    ansicht.aktualisiere_resonanz(ds.frequenzen, bres,
                                  np.zeros(len(ds), dtype=bool), ausgeschlossen)
    assert _overlay_punkte(ansicht) == len(ds) - 2


def test_ausreisser_klick_trifft_naechsten_punkt(app):
    ansicht, ds, bres = _ansicht_mit_overlay()
    getroffen = []
    ansicht.setze_ausreisser_modus(True, gewaehlt=getroffen.extend)
    # Klick direkt auf Punkt 6.
    ansicht._on_press(_ev(ansicht.ax, xdata=bres[6], ydata=ds.frequenzen[6] / 1e9))
    ansicht._on_release(_ev(ansicht.ax, xdata=bres[6], ydata=ds.frequenzen[6] / 1e9))
    assert getroffen == [6]
    # Klick weit weg von allen Punkten: nichts.
    getroffen.clear()
    ansicht._on_press(_ev(ansicht.ax, xdata=2.51, ydata=48.0))
    ansicht._on_release(_ev(ansicht.ax, xdata=2.51, ydata=48.0))
    assert getroffen == []


def test_ausreisser_kasten_trifft_gruppe_ohne_zoom(app):
    ansicht, ds, bres = _ansicht_mit_overlay()
    getroffen = []
    ansicht.setze_ausreisser_modus(True, gewaehlt=getroffen.extend)
    xlim_vorher = ansicht.ax.get_xlim()
    f_ghz = ds.frequenzen / 1e9
    # Kasten um die Punkte 3..5.
    ansicht._on_press(_ev(ansicht.ax, xdata=bres[3] - 0.02, ydata=f_ghz[3] - 1))
    ansicht._on_move(_ev(ansicht.ax, xdata=bres[5] + 0.02, ydata=f_ghz[5] + 1))
    ansicht._on_release(_ev(ansicht.ax, xdata=bres[5] + 0.02, ydata=f_ghz[5] + 1))
    assert getroffen == [3, 4, 5]
    assert ansicht.ax.get_xlim() == xlim_vorher  # kein Zoom im Ausreisser-Modus

    # Ausgeschlossene Punkte sind nicht mehr treffbar.
    ausgeschlossen = np.zeros(len(ds), dtype=bool)
    ausgeschlossen[4] = True
    ansicht.aktualisiere_resonanz(ds.frequenzen, bres,
                                  np.zeros(len(ds), dtype=bool), ausgeschlossen)
    getroffen.clear()
    ansicht._on_press(_ev(ansicht.ax, xdata=bres[3] - 0.02, ydata=f_ghz[3] - 1))
    ansicht._on_move(_ev(ansicht.ax, xdata=bres[5] + 0.02, ydata=f_ghz[5] + 1))
    ansicht._on_release(_ev(ansicht.ax, xdata=bres[5] + 0.02, ydata=f_ghz[5] + 1))
    assert getroffen == [3, 5]

    # Modus aus -> Kasten zoomt wieder.
    ansicht.setze_ausreisser_modus(False)
    ansicht._on_press(_ev(ansicht.ax, xdata=2.7, ydata=15.0))
    ansicht._on_move(_ev(ansicht.ax, xdata=3.3, ydata=35.0))
    ansicht._on_release(_ev(ansicht.ax, xdata=3.3, ydata=35.0))
    assert ansicht.ax.get_xlim() != xlim_vorher


def test_ausreisser_panel_liste_und_callbacks(app):
    from bbfmr.gui.ausreisser_panel import AusreisserPanel
    ds = _mini_datensatz()
    stapel = StapelErgebnis(datensatz=ds)
    for i, f in enumerate(ds.frequenzen):
        stapel.ergebnisse.append(FitErgebnis(frequenz=float(f), erfolg=True,
                                             B_res=2.7 + 0.06 * i, problematisch=False))
    stapel.ausreisser = [1, 8]

    aufrufe = []
    panel = AusreisserPanel(wieder_aufnehmen=aufrufe.append,
                            rueckgaengig=lambda: aufrufe.append("undo"))
    panel.zeige_ausreisser(stapel)
    assert panel.liste.count() == 2
    assert "2 Punkt(e)" in panel.anzahl_label.text()

    panel.liste.setCurrentRow(1)
    panel.btn_wieder.click()
    assert aufrufe == [[8]]

    panel.btn_alle.click()
    assert aufrufe[-1] == [1, 8]

    panel.btn_rueckgaengig.click()
    assert aufrufe[-1] == "undo"


def test_hauptfenster_ausreisser_aktion_und_dock(app):
    from bbfmr.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    assert w.akt_ausreisser.isCheckable()
    assert w.ausreisser_dock.isHidden()  # erscheint erst mit dem Modus
    assert w.akt_projekt_speichern is not None and w.akt_projekt_laden is not None
    # Ohne Fits: Einschalten wird abgewiesen und wieder ausgecheckt.
    w.akt_ausreisser.setChecked(True)
    assert w.akt_ausreisser.isChecked() is False

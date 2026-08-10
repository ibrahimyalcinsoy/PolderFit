# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Tests des zentralen Rueckgaengig-/Wiederholen-Stapels (Strg+Z/Strg+Umschalt+Z).

Abgedeckt: Grenzgeraden (einfuegen, Seite wechseln, Endpunkt ziehen, entfernen),
Ausreisser, Einzel-Nachfit (Grenzen ziehen) und Ausschlusszonen (Undo stellt die
betroffenen Fits OHNE Neurechnung wieder her). Ein neuer Datensatz leert den Stapel.
"""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets

from polderfit.fit.batch import StapelErgebnis
from polderfit.fit.linescan_fit import FitErgebnis
from polderfit.io.datensatz import Linescan, Messdatensatz


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _pumpe(ms=3000):
    schleife = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, schleife.quit)
    schleife.exec()


def _fenster_mit_stapel(n=10):
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    B = np.linspace(2.5, 3.5, 40)
    freqs = np.linspace(5e9, 50e9, n)
    ds = Messdatensatz(quelle="t", format_typ="sortiert", linescans=[
        Linescan(frequenz=float(f), feld=B,
                 re=np.cos(20 * B) + 0.01 * np.random.default_rng(1).normal(size=40),
                 im=np.sin(20 * B)) for f in freqs])
    ds.meta["zuordnung"] = {"re": ("g", "k")}
    w.matrix.zeige(ds)
    w.datensatz_voll = ds
    stapel = StapelErgebnis(datensatz=ds)
    for i, f in enumerate(freqs):
        stapel.ergebnisse.append(FitErgebnis(frequenz=float(f), erfolg=True,
                                             B_res=2.7 + 0.06 * i, problematisch=False))
        stapel.fenster.append((2.6, 3.4))
        stapel.zugeschnitten.append(ds.linescans[i])
    w.stapel = stapel
    return w, stapel


def test_gerade_einfuegen_undo_redo(app):
    w, _ = _fenster_mit_stapel()
    assert w.akt_rueckgaengig.isEnabled() is False
    w._gerade_gezeichnet([(2.7, 10.0), (3.2, 40.0)])
    assert len(w._grenzgeraden) == 1
    assert w.akt_rueckgaengig.isEnabled() is True
    assert "Grenzgerade" in w.akt_rueckgaengig.text()

    w._rueckgaengig()
    assert w._grenzgeraden == []
    assert w.akt_wiederholen.isEnabled() is True

    w._wiederholen()
    assert len(w._grenzgeraden) == 1
    assert abs(w._grenzgeraden[0].b1 - 2.7) < 1e-9


def test_gerade_seite_und_endpunkt_undo(app):
    w, _ = _fenster_mit_stapel()
    w._gerade_gezeichnet([(2.7, 10.0), (3.2, 40.0)])
    w._gerade_seite(0)
    assert w._grenzgeraden[0].gruen_positiv is False
    w._rueckgaengig()
    assert w._grenzgeraden[0].gruen_positiv is True

    # Endpunkt-Drag: Matrix mutiert das Objekt live, dann kommt der Callback.
    g = w._grenzgeraden[0]
    g.b2, g.f2 = 3.4, 45e9
    w._gerade_geaendert(0, g.b1, g.f1 / 1e9, 3.4, 45.0)
    assert abs(w._grenzgeraden[0].b2 - 3.4) < 1e-9
    w._rueckgaengig()
    assert abs(w._grenzgeraden[0].b2 - 3.2) < 1e-9   # alter Endpunkt zurueck
    w._wiederholen()
    assert abs(w._grenzgeraden[0].b2 - 3.4) < 1e-9


def test_ausreisser_undo_redo(app):
    w, stapel = _fenster_mit_stapel()
    w._aktualisiere_overlay()
    w._ausreisser_gewaehlt([3, 5])
    assert stapel.ausreisser == [3, 5]
    w._rueckgaengig()
    assert stapel.ausreisser == []
    w._wiederholen()
    assert stapel.ausreisser == [3, 5]
    # Wieder aufnehmen ist ebenfalls umkehrbar.
    w._ausreisser_wieder_aufnehmen([3])
    assert stapel.ausreisser == [5]
    w._rueckgaengig()
    assert stapel.ausreisser == [3, 5]


def test_grenzen_ziehen_undo_stellt_fit_wieder_her(app):
    w, stapel = _fenster_mit_stapel()
    w.aktueller_index = 4
    alt_fenster = stapel.fenster[4]
    alt_ergebnis = stapel.ergebnisse[4]
    w._grenzen_geaendert(2.8, 3.2)                 # synchroner Nachfit
    assert stapel.fenster[4] == (2.8, 3.2)
    assert stapel.ergebnisse[4] is not alt_ergebnis
    neu_ergebnis = stapel.ergebnisse[4]

    w._rueckgaengig()
    assert stapel.fenster[4] == alt_fenster
    assert stapel.ergebnisse[4] is alt_ergebnis    # exakt derselbe Zustand
    w._wiederholen()
    assert stapel.ergebnisse[4] is neu_ergebnis


def test_zone_undo_ohne_neurechnung(app):
    w, stapel = _fenster_mit_stapel()
    fits_vorher = list(stapel.ergebnisse)
    w._zone_gezeichnet(2.9, 3.1, 15.0, 35.0)       # Hintergrund-Job
    _pumpe(4000)
    assert len(stapel.ausschlusszonen) == 1
    betroffen = [i for i, f in enumerate(stapel.datensatz.frequenzen)
                 if 15e9 <= f <= 35e9]
    assert any(stapel.ergebnisse[i] is not fits_vorher[i] for i in betroffen)

    w._rueckgaengig()                              # sofort, ohne Job
    assert stapel.ausschlusszonen == []
    for i in betroffen:
        assert stapel.ergebnisse[i] is fits_vorher[i]
    assert w.zonenpanel.zonen_liste.count() == 0

    w._wiederholen()
    assert len(stapel.ausschlusszonen) == 1
    assert w.zonenpanel.zonen_liste.count() == 1


def test_neuer_datensatz_leert_undo(app):
    w, _ = _fenster_mit_stapel()
    w._gerade_gezeichnet([(2.7, 10.0), (3.2, 40.0)])
    assert w.akt_rueckgaengig.isEnabled()
    w._undo_verwerfen()
    assert w.akt_rueckgaengig.isEnabled() is False
    assert w.akt_wiederholen.isEnabled() is False
    assert w.akt_rueckgaengig.text() == "Rückgängig"


def test_undo_aktionen_in_menue_und_dropdown(app):
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    menues = {m.title(): m for m in w.menuBar().findChildren(QtWidgets.QMenu)}
    assert "&Bearbeiten" in menues
    aktionen = set(menues["&Bearbeiten"].actions())
    assert w.akt_rueckgaengig in aktionen and w.akt_wiederholen in aktionen
    assert w.akt_rueckgaengig in set(w.funktionen_menue.actions())
    assert w.akt_rueckgaengig.shortcut().toString() == "Ctrl+Z"

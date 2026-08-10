# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Tests des zentralen Modus-Managers der Matrix-Ansicht.

Prueft die Kernzusagen des GUI-Umbaus: hoechstens EIN Interaktionsmodus aktiv,
das Starten eines Modus beendet den vorherigen, Esc bricht JEDEN Modus ab,
jeder Wechsel wird gemeldet (fuer die sichtbare Markierung in Werkzeugleiste
und Statusleiste), und ein neuer Datensatz setzt alle Modi zurueck.
"""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtWidgets

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


def _ansicht(meldungen=None):
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    m = MatrixAnsicht(modus_geaendert=(meldungen.append if meldungen is not None else None))
    m.zeige(_mini_datensatz())
    return m


def test_modi_schliessen_sich_gegenseitig_aus(app):
    m = _ansicht()
    m.starte_bereichs_fit(lambda *a: None)
    assert m.modus == "bereich"
    m.starte_dispersion_seed(lambda p: None)
    assert m.modus == "seed"           # Bereichs-Fit wurde beendet
    m.setze_ausreisser_modus(True, gewaehlt=lambda i: None)
    assert m.modus == "ausreisser"     # Seed wurde beendet
    m.starte_ausschluss_zeichnen(lambda *a: None)
    assert m.modus == "zone"           # Ausreisser wurde beendet

    # Im Zonen-Modus zeichnet ein Kasten eine Zone - er markiert KEINE
    # Ausreisser mehr (frueherer Bug: Ausreisser-Flag blieb haengen).
    zonen, ausreisser = [], []
    m.starte_ausschluss_zeichnen(lambda *a: zonen.append(a))
    m._on_press(_ev(m.ax, xdata=2.6, ydata=8.0))
    m._on_move(_ev(m.ax, xdata=3.0, ydata=20.0))
    m._on_release(_ev(m.ax, xdata=3.0, ydata=20.0))
    assert len(zonen) == 1 and not ausreisser
    assert m.modus is None


def test_escape_bricht_jeden_modus_ab(app):
    m = _ansicht()
    for starten in (lambda: m.starte_dispersion_seed(lambda p: None),
                    lambda: m.starte_bereichs_fit(lambda *a: None),
                    lambda: m.starte_ausschluss_zeichnen(lambda *a: None),
                    lambda: m.setze_ausreisser_modus(True, gewaehlt=lambda i: None)):
        starten()
        assert m.modus is not None
        m._on_key(_ev(m.ax, key="escape"))
        assert m.modus is None


def test_seed_halb_gestartet_laesst_sich_abbrechen(app):
    """Frueherer Bug: nach EINEM Seed-Klick gab es keinen Ausweg mehr."""
    m = _ansicht()
    punkte = []
    m.starte_dispersion_seed(punkte.append)
    m._on_press(_ev(m.ax, xdata=2.8, ydata=10.0))   # erster von zwei Klicks
    assert m.modus == "seed" and not punkte
    m._on_key(_ev(m.ax, key="escape"))
    assert m.modus is None
    assert m._seed_punkte == [] and m._seed_marker == []
    # Danach ist wieder normale Frequenzwahl aktiv - kein spaeter Seed-Callback.
    m._on_press(_ev(m.ax, xdata=3.0, ydata=30.0))
    m._on_release(_ev(m.ax, xdata=3.0, ydata=30.0))
    assert not punkte


def test_moduswechsel_werden_gemeldet(app):
    meldungen = []
    m = _ansicht(meldungen)
    m.starte_bereichs_fit(lambda *a: None)
    m.starte_dispersion_seed(lambda p: None)
    m.beende_modus()
    assert meldungen == ["bereich", "seed", None]


def test_neuer_datensatz_setzt_modus_zurueck(app):
    meldungen = []
    m = _ansicht(meldungen)
    m.setze_ausreisser_modus(True, gewaehlt=lambda i: None)
    assert m.modus == "ausreisser"
    m.zeige(_mini_datensatz(8))
    assert m.modus is None
    assert meldungen[-1] is None


def test_platzhalter_ohne_daten(app):
    """Ohne Messung: leeres Koordinatensystem, Eingaben laufen ins Leere."""
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    m = MatrixAnsicht()
    assert m._datensatz is None
    assert m.ax.get_xlabel().startswith("Feld")
    assert "Frequenz" in m.ax.get_ylabel()
    # Interaktion ohne Daten wirft nicht.
    m._on_press(_ev(m.ax, xdata=0.5, ydata=0.5))
    m._on_key(_ev(m.ax, key="up"))
    m._on_scroll(_ev(m.ax, step=1))


def test_hauptfenster_synct_umschalter_und_statusleiste(app):
    from polderfit.gui.hauptfenster import Hauptfenster
    from polderfit.fit.batch import StapelErgebnis
    from polderfit.fit.linescan_fit import FitErgebnis
    w = Hauptfenster()
    ds = _mini_datensatz()
    w.matrix.zeige(ds)
    w.datensatz_voll = ds
    stapel = StapelErgebnis(datensatz=ds)
    for i, f in enumerate(ds.frequenzen):
        stapel.ergebnisse.append(FitErgebnis(frequenz=float(f), erfolg=True,
                                             B_res=2.7 + 0.06 * i, problematisch=False))
        stapel.fenster.append((2.5, 3.5))
    stapel.datensatz.meta["zuordnung"] = {"re": ("g", "k")}
    w.stapel = stapel

    # Ausreisser-Modus einschalten: Aktion checked, Modus-Label sichtbar.
    w.akt_ausreisser.setChecked(True)
    assert w.matrix.modus == "ausreisser"
    assert w.modus_label.isVisibleTo(w)
    # Bereichs-Fit starten: Ausreisser-Aktion wird automatisch abgewaehlt.
    w.akt_bereich.setChecked(True)
    assert w.matrix.modus == "bereich"
    assert w.akt_ausreisser.isChecked() is False
    assert w.akt_bereich.isChecked() is True
    # Esc (ueber den Manager) beendet den Modus und waehlt die Aktion ab.
    w.matrix.beende_modus()
    assert w.akt_bereich.isChecked() is False
    assert w.modus_label.isVisibleTo(w) is False


def test_hauptfenster_modus_ohne_fits_abgewiesen(app):
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    # Ohne geladene Daten: Umschalter springen zurueck, kein Modus aktiv.
    w.akt_ausreisser.setChecked(True)
    assert w.akt_ausreisser.isChecked() is False
    w.akt_bereich.setChecked(True)
    assert w.akt_bereich.isChecked() is False
    w.akt_seed.setChecked(True)
    assert w.akt_seed.isChecked() is False
    assert w.matrix.modus is None

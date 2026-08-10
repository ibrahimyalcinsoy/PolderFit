# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Tests der einstellbaren physikalischen Parameter.

Konvention (Mueller 2023, Kap. 2): gamma = g*mu_B/hbar. Der Dialog liefert
eine PhysikParameter-Datenklasse; das Hauptfenster reicht sie in Auto-Fit,
Nachfits und die Kittel/LLG-Auswertung durch.
"""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from polderfit.physik.konstanten import GAMMA_STANDARD, gamma_aus_g


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_parameter_datenklasse_gamma():
    from polderfit.gui.parameter_dialog import PhysikParameter
    p = PhysikParameter()
    assert abs(p.gamma - GAMMA_STANDARD) < 1e-3
    p2 = PhysikParameter(g_faktor=2.1)
    assert abs(p2.gamma - gamma_aus_g(2.1)) < 1e-3
    assert "g=2.1000" in p2.beschreibung()


def test_dialog_roundtrip_und_standardwerte(app):
    from polderfit.gui.parameter_dialog import ParameterDialog, PhysikParameter
    start = PhysikParameter(g_faktor=2.05, gamma_fest=True, geometrie="ip",
                            breite_faktor=12.0, r2_schwelle=0.8,
                            r2_min=0.85, alpha_erwartet=0.02)
    dlg = ParameterDialog(start)
    # Vorbelegung entspricht den uebergebenen Werten, Roundtrip identisch.
    p = dlg.parameter()
    assert p == start
    # Wert aendern -> neue Datenklasse.
    dlg.g_spin.setValue(2.2)
    dlg.geo_combo.setCurrentText("oop")
    p2 = dlg.parameter()
    assert abs(p2.g_faktor - 2.2) < 1e-9 and p2.geometrie == "oop"
    assert p2.gamma_fest is True                    # unveraendert uebernommen
    # gamma-Anzeige folgt dem g-Faktor.
    assert f"{gamma_aus_g(2.2):.4e}" in dlg.gamma_label.text()
    # Standardwerte-Knopf setzt alles zurueck.
    dlg._standardwerte()
    assert dlg.parameter() == PhysikParameter()


def test_hauptfenster_uebernimmt_parameter(app):
    from polderfit.gui.hauptfenster import Hauptfenster
    from polderfit.gui.parameter_dialog import PhysikParameter
    w = Hauptfenster()
    neu = PhysikParameter(g_faktor=2.1, breite_faktor=10.0)
    w._physik_uebernehmen(neu)
    assert w._physik == neu
    assert w.akt_physik.shortcut().toString() == "Ctrl+P"


def test_auswertungsfenster_nutzt_parameter(app):
    """gamma_fest + eigener g-Faktor: der Kittel-Fit haelt genau dieses gamma."""
    from polderfit.gui.auswertung_fenster import AuswertungsFenster
    from polderfit.gui.parameter_dialog import PhysikParameter
    from polderfit.fit.batch import StapelErgebnis
    from polderfit.fit.linescan_fit import FitErgebnis
    from polderfit.io.datensatz import Linescan, Messdatensatz
    from polderfit.physik.kittel_llg import linienbreite

    freqs = np.linspace(8e9, 30e9, 12)
    ds = Messdatensatz(quelle="t", format_typ="sortiert", linescans=[
        Linescan(frequenz=float(f), feld=np.linspace(0.4, 1.6, 30),
                 re=np.zeros(30), im=np.zeros(30)) for f in freqs])
    stapel = StapelErgebnis(datensatz=ds)
    for f in freqs:
        b = 2 * np.pi * f / GAMMA_STANDARD + 0.4
        stapel.ergebnisse.append(FitErgebnis(
            frequenz=float(f), erfolg=True, B_res=float(b),
            dH=float(linienbreite(f, 2e-3, 0.008, GAMMA_STANDARD)),
            problematisch=False))
        stapel.fenster.append((b - 0.1, b + 0.1))
        stapel.zugeschnitten.append(ds.linescans[0])

    p = PhysikParameter(g_faktor=2.1, gamma_fest=True)
    w = AuswertungsFenster(hole_stapel=lambda: stapel, hole_parameter=lambda: p)
    assert w._info is not None
    # gamma wurde festgehalten: exakt der eingestellte Wert, Fehler 0.
    assert abs(w._info["kittel"]["gamma"] - gamma_aus_g(2.1)) < 1e-3
    assert w._info["kittel"]["gamma_err"] == 0.0

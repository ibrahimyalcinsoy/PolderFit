# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Tests des Kittel/LLG-Auswertungsfensters und der Plot-Achsen.

Verbindliche Darstellung: FELD auf der x-Achse (wie im Farbplot) - sowohl im
Auswertungsfenster als auch in den Modul-Plotfunktionen. Punkte lassen sich
direkt im Plot (Klick/Kasten) als Ausreisser entfernen; der Fit rechnet sofort
neu. Der Export enthaelt Parameter samt Fehlern und alle Punkte mit Flags.
"""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtWidgets

from polderfit.fit.batch import StapelErgebnis
from polderfit.fit.linescan_fit import FitErgebnis
from polderfit.io.datensatz import Linescan, Messdatensatz
from polderfit.physik.konstanten import GAMMA_STANDARD
from polderfit.physik.kittel_llg import linienbreite

GAMMA = GAMMA_STANDARD
MU0MEFF = 0.4
ALPHA = 0.008


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _ev(ax=None, **kw):
    d = dict(inaxes=ax, xdata=None, ydata=None, step=0, key=None, dblclick=False, button=1)
    d.update(kw)
    return SimpleNamespace(**d)


def _kittel_stapel(n=12):
    """Stapel mit Ergebnissen exakt auf der oop-Kittel-Geraden."""
    freqs = np.linspace(8e9, 30e9, n)
    ds = Messdatensatz(quelle="t", format_typ="sortiert", linescans=[
        Linescan(frequenz=float(f), feld=np.linspace(0.4, 1.6, 30),
                 re=np.zeros(30), im=np.zeros(30)) for f in freqs])
    stapel = StapelErgebnis(datensatz=ds)
    for i, f in enumerate(freqs):
        omega = 2 * np.pi * f
        b = omega / GAMMA + MU0MEFF
        dh = linienbreite(f, 2e-3, ALPHA, GAMMA)
        stapel.ergebnisse.append(FitErgebnis(
            frequenz=float(f), erfolg=True, B_res=float(b), dH=float(dh),
            B_res_err=1e-4, alpha=ALPHA, alpha_err=1e-4, problematisch=False))
        stapel.fenster.append((b - 0.1, b + 0.1))
        stapel.zugeschnitten.append(ds.linescans[i])
    return stapel


def test_modulplots_haben_feld_auf_x():
    """plot_resonanz_vs_frequenz und plot_linienbreite: Feld (T) auf der x-Achse."""
    import matplotlib
    matplotlib.use("Agg")
    from polderfit.auswertung.uebersicht import plot_linienbreite, plot_resonanz_vs_frequenz
    stapel = _kittel_stapel()

    fig, info = plot_resonanz_vs_frequenz(stapel.ergebnisse, geometrie="oop")
    ax = fig.axes[0]
    assert "Feld" in ax.get_xlabel() or "H_{res}" in ax.get_xlabel()
    assert "Frequenz" in ax.get_ylabel()
    # Messpunkte: x = B_res (T), y = f (GHz).
    linie = ax.lines[0]
    assert np.allclose(sorted(linie.get_xdata()), sorted(info["B_res_T"]))
    assert np.allclose(sorted(linie.get_ydata()), sorted(info["frequenz_Hz"] / 1e9))

    fig2, _info2 = plot_linienbreite(stapel.ergebnisse, gamma=info["kittel"]["gamma"])
    ax2 = fig2.axes[0]
    assert "H_{res}" in ax2.get_xlabel()
    assert "Delta" in ax2.get_ylabel() or "ΔH" in ax2.get_ylabel()


def test_auswertungsfenster_rechnet_und_zeigt_fehler(app):
    from polderfit.gui.auswertung_fenster import AuswertungsFenster
    stapel = _kittel_stapel()
    w = AuswertungsFenster(hole_stapel=lambda: stapel)
    assert w._info is not None
    kit = w._info["kittel"]
    assert abs(kit["mu0Meff"] - MU0MEFF) < 1e-3
    # Parameter samt Fehlern im Textfeld.
    text = w.param_text.toPlainText()
    assert "±" in text and "α" in text
    # Achsen: Feld auf x in beiden Plots.
    assert "H_{res}" in w.ax_disp.get_xlabel()
    assert "H_{res}" in w.ax_lb.get_xlabel()


def test_auswertungsfenster_klick_entfernt_punkt(app):
    from polderfit.gui.auswertung_fenster import AuswertungsFenster
    stapel = _kittel_stapel()
    markiert = []

    def markieren(indizes):
        markiert.extend(indizes)
        for i in indizes:
            if not stapel.ist_ausreisser(i):
                stapel.ausreisser_umschalten(i)

    w = AuswertungsFenster(hole_stapel=lambda: stapel, ausreisser_markieren=markieren)
    n_vorher = w._punkt_indizes.size
    # Klick exakt auf Punkt 5 im Dispersionsplot (x=B_res, y=f_GHz).
    e5 = stapel.ergebnisse[5]
    w._on_press(_ev(w.ax_disp, xdata=e5.B_res, ydata=e5.frequenz / 1e9))
    w._on_release(_ev(w.ax_disp, xdata=e5.B_res, ydata=e5.frequenz / 1e9))
    assert markiert == [5]
    assert stapel.ausreisser == [5]
    assert w._punkt_indizes.size == n_vorher - 1  # sofort neu gerechnet
    assert 5 not in w._punkt_indizes


def test_auswertungsfenster_export_schreibt_plot_und_tabellen(app, tmp_path):
    from polderfit.gui.auswertung_fenster import AuswertungsFenster
    import pandas as pd
    stapel = _kittel_stapel()
    stapel.ausreisser_umschalten(2)
    w = AuswertungsFenster(hole_stapel=lambda: stapel)
    w.aktualisiere()

    ziel = tmp_path / "auswertung.xlsx"
    # Dateidialog umgehen: direkten Exportpfad simulieren.
    from unittest.mock import patch
    with patch.object(QtWidgets.QFileDialog, "getSaveFileName",
                      return_value=(str(ziel), "Excel (*.xlsx)")), \
         patch.object(QtWidgets.QMessageBox, "information"):
        w._exportieren()

    assert ziel.exists()
    assert (tmp_path / "auswertung.png").exists()
    assert (tmp_path / "auswertung.pdf").exists()
    param = pd.read_excel(ziel, sheet_name="Parameter")
    assert "mu0_Meff" in set(param["Groesse"])
    assert "Fehler_1sigma" in param.columns
    punkte = pd.read_excel(ziel, sheet_name="Punkte")
    assert {"B_res_err_T", "mu0_dH_err_T", "ausreisser",
            "im_kittel_fit_verwendet"} <= set(punkte.columns)
    assert bool(punkte.sort_values("frequenz_Hz").iloc[2]["ausreisser"]) is True


def test_export_kennzeichnet_ausreisser():
    from polderfit.persistenz.ergebnis_export import parameter_tabelle
    stapel = _kittel_stapel()
    tab = parameter_tabelle(stapel.ergebnisse, ausreisser=[1, 4])
    assert "ausreisser" in tab.columns
    markiert = tab.sort_values("frequenz_Hz")["ausreisser"].tolist()
    assert markiert[1] is True or markiert[1] == True  # noqa: E712
    assert sum(bool(x) for x in markiert) == 2

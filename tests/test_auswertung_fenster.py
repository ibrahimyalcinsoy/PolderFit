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
    assert "α" in text and "im Export" in text   # nur Werte, keine Statistik in der Anzeige
    # Achsen: Feld auf x in beiden Plots.
    assert "H_{res}" in w.ax_disp.get_xlabel()
    assert "H_{res}" in w.ax_lb.get_xlabel()


def _klick(w, ax, x, y):
    w._on_press(_ev(ax, xdata=x, ydata=y))
    w._on_release(_ev(ax, xdata=x, ydata=y))


def _fenster_mit_callbacks(stapel):
    from polderfit.gui.auswertung_fenster import AuswertungsFenster
    protokoll = {"markiert": [], "wieder": []}

    def markieren(indizes):
        protokoll["markiert"].extend(indizes)
        for i in indizes:
            if not stapel.ist_ausreisser(i):
                stapel.ausreisser_umschalten(i)

    def wieder(indizes):
        protokoll["wieder"].extend(indizes)
        for i in indizes:
            if stapel.ist_ausreisser(i):
                stapel.ausreisser_umschalten(i)

    w = AuswertungsFenster(hole_stapel=lambda: stapel, ausreisser_markieren=markieren,
                           ausreisser_wieder_aufnehmen=wieder)
    return w, protokoll


def test_auswertungsfenster_klick_waehlt_dann_ausblenden(app):
    """Klick waehlt (blauer Ring), erst 'Auswahl ausblenden' schliesst aus."""
    stapel = _kittel_stapel()
    w, protokoll = _fenster_mit_callbacks(stapel)
    n_vorher = w._punkt_indizes.size
    e5 = stapel.ergebnisse[5]
    _klick(w, w.ax_disp, e5.B_res, e5.frequenz / 1e9)
    assert w.auswahl() == [("v", 5, 1)]
    assert protokoll["markiert"] == [] and stapel.ausreisser == []
    assert w.act_ausblenden.isEnabled() and not w.act_einblenden.isEnabled()
    # Ring in beiden Plots (Linienbreitenplot: gleicher Punkt).
    for ax in (w.ax_disp, w.ax_lb):
        assert len(w._markierung[ax].get_xdata()) == 1
    assert "1 Punkt(e) ausgewählt" in w.hinweis.text()
    # Erneuter Klick hebt die Auswahl des Punktes auf.
    _klick(w, w.ax_lb, e5.B_res, e5.dH * 1e3)
    assert w.auswahl() == []
    _klick(w, w.ax_disp, e5.B_res, e5.frequenz / 1e9)
    w.act_ausblenden.trigger()
    assert protokoll["markiert"] == [5]
    assert stapel.ausreisser == [5]
    assert w._punkt_indizes.size == n_vorher - 1  # sofort neu gerechnet
    assert 5 not in w._punkt_indizes
    assert w.auswahl() == [] and not w.act_ausblenden.isEnabled()


def test_auswertungsfenster_kasten_esc_und_navigation(app):
    stapel = _kittel_stapel()
    w, protokoll = _fenster_mit_callbacks(stapel)
    b = [e.B_res for e in stapel.ergebnisse]
    f = [e.frequenz / 1e9 for e in stapel.ergebnisse]
    # Kasten um die Punkte 3..5 fuegt alle drei hinzu.
    w._on_press(_ev(w.ax_disp, xdata=b[3] - 0.01, ydata=f[3] - 0.3))
    w._on_move(_ev(w.ax_disp, xdata=b[5] + 0.01, ydata=f[5] + 0.3))
    w._on_release(_ev(w.ax_disp, xdata=b[5] + 0.01, ydata=f[5] + 0.3))
    assert [k[1] for k in w.auswahl()] == [3, 4, 5]
    w.act_aufheben.trigger()                       # Esc
    assert w.auswahl() == [] and protokoll["markiert"] == []
    # Zoom aktiv -> Klick waehlt nichts; Auswaehlen schaltet Zoom wieder ab.
    w.werkzeuge.zoom()
    assert not w.act_auswahl.isChecked()
    _klick(w, w.ax_disp, b[2], f[2])
    assert w.auswahl() == []
    w.act_auswahl.trigger()
    assert w.act_auswahl.isChecked() and not w._navigation_aktiv()
    _klick(w, w.ax_disp, b[2], f[2])
    assert w.auswahl() == [("v", 2, 1)]


def test_auswertungsfenster_zoom_bleibt_und_ausgeblendete_einblenden(app):
    stapel = _kittel_stapel()
    w, protokoll = _fenster_mit_callbacks(stapel)
    e = stapel.ergebnisse
    # Gezoomte Ansicht bleibt nach dem Ausblenden erhalten.
    w.ax_disp.set_xlim(e[2].B_res - 0.05, e[6].B_res + 0.05)
    zoom = w.ax_disp.get_xlim()
    _klick(w, w.ax_disp, e[4].B_res, e[4].frequenz / 1e9)
    w.act_ausblenden.trigger()
    assert stapel.ausreisser == [4]
    assert np.allclose(w.ax_disp.get_xlim(), zoom)
    w.werkzeuge.home()                             # Gesamtansicht
    assert np.allclose(w.ax_disp.get_xlim(), w._auto_ansicht[0][0])
    # Ausgeblendete grau zeigen, auswaehlen, wieder aufnehmen.
    w.chk_ausgeblendete.setChecked(True)
    assert ("a", 4, 1) in w._kand_keys
    _klick(w, w.ax_disp, e[4].B_res, e[4].frequenz / 1e9)
    assert w.auswahl() == [("a", 4, 1)]
    assert w.act_einblenden.isEnabled() and not w.act_ausblenden.isEnabled()
    w.act_einblenden.trigger()
    assert protokoll["wieder"] == [4]
    assert stapel.ausreisser == []
    assert 4 in w._punkt_indizes


def test_auswertungsfenster_mehrere_moden_blendet_je_mode_aus(app):
    """Bei mehreren Moden: Ausblenden nur fuer die Mode (Paar), Einblenden ebenso."""
    from polderfit.gui.auswertung_fenster import AuswertungsFenster
    stapel = _kittel_stapel()
    liste2 = stapel.ergebnisse_mode(2)
    for i, e in enumerate(stapel.ergebnisse):
        liste2[i] = FitErgebnis(frequenz=e.frequenz, erfolg=True, B_res=e.B_res + 0.2,
                                dH=e.dH, B_res_err=1e-4, alpha=ALPHA, alpha_err=1e-4,
                                problematisch=False, mode=2)
    gemeldet, wieder = [], []

    def mode_markieren(paare):
        gemeldet.extend(paare)
        for i, k in paare:
            stapel.ausreisser_mode_umschalten(i, k)

    def mode_wieder(paare):
        wieder.extend(paare)
        for i, k in paare:
            stapel.ausreisser_mode_umschalten(i, k)

    w = AuswertungsFenster(hole_stapel=lambda: stapel, ausreisser_mode_markieren=mode_markieren,
                           ausreisser_mode_wieder_aufnehmen=mode_wieder)
    w.setze_mode(2)
    e = liste2[7]
    _klick(w, w.ax_disp, e.B_res, e.frequenz / 1e9)
    assert w.auswahl() == [("v", 7, 2)]
    w.act_ausblenden.trigger()
    assert gemeldet == [(7, 2)] and stapel.ausreisser == []
    assert 7 not in w._reihen[2].indizes
    w.chk_ausgeblendete.setChecked(True)
    _klick(w, w.ax_disp, e.B_res, e.frequenz / 1e9)
    w.act_einblenden.trigger()
    assert wieder == [(7, 2)] and stapel.ausreisser_moden == []


def _hauptfenster_mit(stapel):
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    w.matrix.zeige(stapel.datensatz)
    w.datensatz_voll = stapel.datensatz
    w.stapel = stapel
    w._aktualisiere_overlay()
    return w


def test_ausblenden_wird_in_hauptfenster_und_farbplot_uebernommen(app):
    stapel = _kittel_stapel()
    w = _hauptfenster_mit(stapel)
    k = w._auswertungsfenster_holen()
    e5 = stapel.ergebnisse[5]
    _klick(k, k.ax_disp, e5.B_res, e5.frequenz / 1e9)
    k.act_ausblenden.trigger()
    assert stapel.ausreisser == [5]
    assert w.matrix._res_status[5] == "ignoriert"
    # Wieder einblenden ueber das Kittel-Fenster.
    k.chk_ausgeblendete.setChecked(True)
    _klick(k, k.ax_disp, e5.B_res, e5.frequenz / 1e9)
    k.act_einblenden.trigger()
    assert stapel.ausreisser == []
    assert w.matrix._res_status[5] != "ignoriert"


def test_ausblenden_je_mode_graut_farbplot_sofort(app):
    stapel = _kittel_stapel()
    liste2 = stapel.ergebnisse_mode(2)
    for i, e in enumerate(stapel.ergebnisse):
        liste2[i] = FitErgebnis(frequenz=e.frequenz, erfolg=True, B_res=e.B_res + 0.2,
                                dH=e.dH, B_res_err=1e-4, alpha=ALPHA, alpha_err=1e-4,
                                problematisch=False, mode=2)
    w = _hauptfenster_mit(stapel)
    k = w._auswertungsfenster_holen()
    k.setze_mode(1)
    e5 = stapel.ergebnisse[5]
    _klick(k, k.ax_disp, e5.B_res, e5.frequenz / 1e9)
    k.act_ausblenden.trigger()
    assert stapel.ausreisser_moden == [(5, 1)] and stapel.ausreisser == []
    assert w.matrix._res_status[5] == "ignoriert"
    w._rueckgaengig()
    assert stapel.ausreisser_moden == []
    assert w.matrix._res_status[5] != "ignoriert"


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

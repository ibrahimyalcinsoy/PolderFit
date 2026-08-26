# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Kittel/LLG-Auswertung JE MODE (mehrere Resonanzen je Linescan).

Zwei Dispersionszweige exakt auf oop-Kittel-Geraden (mu0Meff 0,40 T und
0,60 T). Die Hauptmode (groesste Signalhoehe) springt absichtlich zwischen den
Zweigen - die alte Hauptmode-Auswertung mischt sie, die Auswertung je Mode
trennt sie (Zuordnung nach Feld oder nach den Moden-Baendern der
Grenzgeraden). Ausreisser je Mode schliessen nur ``(Linescan, Mode)`` aus.
"""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtWidgets

from polderfit.auswertung.moden import (
    ALLE_MODEN,
    HAUPTMODE,
    auswertung_je_mode,
    ergebnisse_fuer_mode,
    max_moden,
    zuordnung_moden,
)
from polderfit.fit.batch import StapelErgebnis
from polderfit.fit.fenster_steuerung import band_geraden
from polderfit.fit.linescan_fit import FitErgebnis
from polderfit.io.datensatz import Linescan, Messdatensatz
from polderfit.physik.konstanten import GAMMA_STANDARD
from polderfit.physik.kittel_llg import linienbreite

GAMMA = GAMMA_STANDARD
MEFF_A, MEFF_B = 0.40, 0.60          # zwei Zweige (oop): B_res = omega/gamma + Meff
ALPHA_A, ALPHA_B = 0.008, 0.012


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _ev(ax=None, **kw):
    d = dict(inaxes=ax, xdata=None, ydata=None, step=0, key=None, dblclick=False, button=1)
    d.update(kw)
    return SimpleNamespace(**d)


def _b_von(f, meff):
    return 2 * np.pi * f / GAMMA + meff


def _mode(f, meff, alpha, hinh, hoehe):
    return {"B_res": float(_b_von(f, meff)), "B_res_err": 1e-4, "alpha": alpha,
            "alpha_err": 1e-4, "dH": float(linienbreite(f, hinh, alpha, GAMMA)),
            "dH_err": 1e-5, "A": 1.0, "A_err": 0.01, "phi": 0.0, "phi_err": 0.01,
            "hoehe": hoehe}


def _zweizweig_stapel(n=12):
    """Zwei Zweige; die Hauptmode (groesste Hoehe) wechselt von Linescan zu Linescan."""
    freqs = np.linspace(8e9, 30e9, n)
    ds = Messdatensatz(quelle="t", format_typ="sortiert", linescans=[
        Linescan(frequenz=float(f), feld=np.linspace(0.4, 2.0, 30),
                 re=np.zeros(30), im=np.zeros(30)) for f in freqs])
    stapel = StapelErgebnis(datensatz=ds, n_moden=2)
    for i, f in enumerate(freqs):
        a = _mode(f, MEFF_A, ALPHA_A, 2e-3, 1.0 if i % 2 == 0 else 0.5)
        b = _mode(f, MEFF_B, ALPHA_B, 3e-3, 0.5 if i % 2 == 0 else 1.0)
        moden = [a, b] if a["hoehe"] >= b["hoehe"] else [b, a]
        h = moden[0]
        stapel.ergebnisse.append(FitErgebnis(
            frequenz=float(f), erfolg=True, B_res=h["B_res"], B_res_err=h["B_res_err"],
            alpha=h["alpha"], alpha_err=h["alpha_err"], dH=h["dH"], dH_err=h["dH_err"],
            A=1.0, phi=0.0, problematisch=False, n_moden=2, moden=moden))
        stapel.fenster.append((a["B_res"] - 0.1, b["B_res"] + 0.1))
        stapel.zugeschnitten.append(ds.linescans[i])
    return stapel


def test_zuordnung_nach_feld_trennt_zweige():
    st = _zweizweig_stapel()
    assert max_moden(st.ergebnisse) == 2
    z = zuordnung_moden(st.ergebnisse, n_moden=2)
    assert z.regel == "feld" and z.n_moden == 2
    for i, e in enumerate(st.ergebnisse):
        pos = z.position(i, 1)
        assert pos is not None
        assert abs(e.moden[pos]["B_res"] - _b_von(e.frequenz, MEFF_A)) < 1e-9
    reihen = auswertung_je_mode(st.ergebnisse, [HAUPTMODE, 1, 2], z)
    assert reihen[1].n == 12 and reihen[2].n == 12
    assert abs(reihen[1].info["kittel"]["mu0Meff"] - MEFF_A) < 1e-3
    assert abs(reihen[2].info["kittel"]["mu0Meff"] - MEFF_B) < 1e-3
    assert abs(reihen[1].info["llg"]["alpha"] - ALPHA_A) < 1e-4
    assert abs(reihen[2].info["llg"]["alpha"] - ALPHA_B) < 1e-4
    # Hauptmode-Auswertung mischt beide Zweige -> Wert dazwischen.
    assert 0.45 < reihen[HAUPTMODE].info["kittel"]["mu0Meff"] < 0.55


def test_zuordnung_nach_baendern_folgt_band_nummer():
    st = _zweizweig_stapel()
    f_lo, f_hi = 8e9, 30e9
    # Band M1 um den HOEHEREN Zweig (0,60 T), Band M2 um 0,40 T -> Mode 1 = 0,60-Zweig.
    geraden = (band_geraden(_b_von(f_lo, MEFF_B), f_lo, _b_von(f_hi, MEFF_B), f_hi, 0.03, mode=1)
               + band_geraden(_b_von(f_lo, MEFF_A), f_lo, _b_von(f_hi, MEFF_A), f_hi, 0.03, mode=2))
    z = zuordnung_moden(st.ergebnisse, geraden, n_moden=2, feld_bereich=(0.0, 3.0))
    assert z.regel == "band" and "Band M1" in z.beschreibung(1)
    reihen = auswertung_je_mode(st.ergebnisse, [1, 2], z)
    assert abs(reihen[1].info["kittel"]["mu0Meff"] - MEFF_B) < 1e-3
    assert abs(reihen[2].info["kittel"]["mu0Meff"] - MEFF_A) < 1e-3
    # Nur ein Band (M1 um 0,40): Rest nach Feld -> Mode 2 = 0,60.
    nur_eins = band_geraden(_b_von(f_lo, MEFF_A), f_lo, _b_von(f_hi, MEFF_A), f_hi, 0.03, mode=1)
    for g in nur_eins:
        g.mode = 2      # Baender-Modus braucht eine Gerade mit mode > 1: M2 um 0,40
    z2 = zuordnung_moden(st.ergebnisse, nur_eins, n_moden=2, feld_bereich=(0.0, 3.0))
    r2 = auswertung_je_mode(st.ergebnisse, [1, 2], z2)
    assert abs(r2[2].info["kittel"]["mu0Meff"] - MEFF_A) < 1e-3
    assert abs(r2[1].info["kittel"]["mu0Meff"] - MEFF_B) < 1e-3


def test_ausreisser_je_mode_und_je_linescan():
    st = _zweizweig_stapel()
    assert st.ausreisser_mode_umschalten(5, 2) is True
    assert st.ist_ausreisser_mode(5, 2) and not st.ist_ausreisser_mode(5, 1)
    st.ausreisser_umschalten(3)
    z = zuordnung_moden(st.ergebnisse, n_moden=2)
    r1 = [i for i, _ in ergebnisse_fuer_mode(st.ergebnisse, 1, z, st.ausreisser, st.ausreisser_moden)]
    r2 = [i for i, _ in ergebnisse_fuer_mode(st.ergebnisse, 2, z, st.ausreisser, st.ausreisser_moden)]
    assert 3 not in r1 and 3 not in r2          # Linescan-Ausreisser: alle Moden
    assert 5 in r1 and 5 not in r2              # nur Mode 2
    assert st.ausreisser_mode_umschalten(5, 2) is False and st.ausreisser_moden == []
    # Ergebnisse ohne moden-Liste (Ein-Moden-Fit alter Art): Hauptmode = Position 0.
    einzel = [FitErgebnis(frequenz=1e10, erfolg=True, B_res=1.0, problematisch=False)]
    assert max_moden(einzel) == 1 and zuordnung_moden(einzel).position(0, 1) == 0
    assert [i for i, _ in ergebnisse_fuer_mode(einzel, 1)] == [0]


def test_fenster_moden_auswahl_klick_und_export(app, tmp_path):
    import pandas as pd
    from polderfit.gui.auswertung_fenster import AuswertungsFenster
    st = _zweizweig_stapel()

    def markieren(indizes):
        for i in indizes:
            st.ausreisser_umschalten(i)

    def markieren_mode(paare):
        for i, k in paare:
            st.ausreisser_mode_umschalten(i, k)

    w = AuswertungsFenster(hole_stapel=lambda: st, ausreisser_markieren=markieren,
                           ausreisser_mode_markieren=markieren_mode)
    assert w._moden_aktiv and not w.mode_combo.isHidden()
    assert [w.mode_combo.itemData(i) for i in range(w.mode_combo.count())] == \
        [HAUPTMODE, 1, 2, ALLE_MODEN]
    assert w.mode_gewaehlt() == 1                                  # Vorwahl: Mode 1
    assert abs(w._info["kittel"]["mu0Meff"] - MEFF_A) < 1e-3
    assert "Mode 1" in w.ax_disp.get_title()
    w.setze_mode(2)
    assert abs(w._info["kittel"]["mu0Meff"] - MEFF_B) < 1e-3
    assert "Mode 2" in w.param_text.toPlainText()

    # Klick auf Punkt 5 in der Mode-2-Ansicht: nur (5, 2) ausgeschlossen.
    e5 = st.ergebnisse[5]
    b5 = e5.moden[w._zuordnung.position(5, 2)]["B_res"]
    n_vorher = w._punkt_indizes.size
    w._on_press(_ev(w.ax_disp, xdata=b5, ydata=e5.frequenz / 1e9))
    w._on_release(_ev(w.ax_disp, xdata=b5, ydata=e5.frequenz / 1e9))
    assert st.ausreisser_moden == [(5, 2)] and st.ausreisser == []
    assert w._punkt_indizes.size == n_vorher - 1 and 5 not in w._punkt_indizes
    w.setze_mode(1)
    assert 5 in w._punkt_indizes                                   # Mode 1 unberuehrt

    # Alle Moden: zwei Kittel-Kurven, beide Bloecke im Text.
    w.setze_mode(ALLE_MODEN)
    kurven = [ln for ln in w.ax_disp.lines if str(ln.get_label()).startswith("Kittel")]
    assert len(kurven) == 2 and set(w._reihen) == {1, 2}
    text = w.param_text.toPlainText()
    assert "Mode 1" in text and "Mode 2" in text and "im Export" in text

    # Hauptmode-Ansicht: Klick entfernt den ganzen Linescan (bisheriges Verhalten).
    w.setze_mode(HAUPTMODE)
    e2 = st.ergebnisse[2]
    w._on_press(_ev(w.ax_disp, xdata=e2.B_res, ydata=e2.frequenz / 1e9))
    w._on_release(_ev(w.ax_disp, xdata=e2.B_res, ydata=e2.frequenz / 1e9))
    assert st.ausreisser == [2]

    # Export: aktuelle Ansicht (Mode 2) + je Mode.
    w.setze_mode(2)
    w.exportiere(str(tmp_path / "kittel"))
    assert (tmp_path / "kittel.xlsx").exists() and (tmp_path / "kittel_punkte.csv").exists()
    assert (tmp_path / "kittel.png").exists() and (tmp_path / "kittel.pdf").exists()
    blaetter = pd.ExcelFile(tmp_path / "kittel.xlsx").sheet_names
    assert blaetter == ["Parameter", "Punkte", "Parameter_M1", "Punkte_M1",
                        "Parameter_M2", "Punkte_M2"]
    param = pd.read_excel(tmp_path / "kittel.xlsx", sheet_name="Parameter")
    assert param.iloc[0]["Groesse"] == "Mode" and int(param.iloc[0]["Wert"]) == 2
    punkte = pd.read_excel(tmp_path / "kittel.xlsx", sheet_name="Punkte_M2")
    assert set(punkte["mode"]) == {2}
    zeile5 = punkte[punkte["stapel_index"] == 5].iloc[0]
    assert bool(zeile5["ausreisser"]) is True and bool(zeile5["im_kittel_fit_verwendet"]) is False
    p1 = pd.read_excel(tmp_path / "kittel.xlsx", sheet_name="Parameter_M1")
    meff = float(p1[p1["Groesse"] == "mu0_Meff"]["Wert"].iloc[0])
    assert abs(meff - MEFF_A) < 1e-3
    n_aus = int(p1[p1["Groesse"] == "N_ausreisser"]["Wert"].iloc[0])
    assert n_aus == 1                                              # Linescan 2
    # Alle Moden exportieren: Parameter beider Moden untereinander.
    w.setze_mode(ALLE_MODEN)
    w.exportiere(str(tmp_path / "alle"))
    param_alle = pd.read_excel(tmp_path / "alle.xlsx", sheet_name="Parameter")
    assert list(param_alle[param_alle["Groesse"] == "Mode"]["Wert"]) == [1, 2]
    w.close()


def test_einmoden_stapel_unveraendert(app, tmp_path):
    import pandas as pd
    from tests.test_auswertung_fenster import _kittel_stapel
    from polderfit.gui.auswertung_fenster import AuswertungsFenster
    st = _kittel_stapel()
    w = AuswertungsFenster(hole_stapel=lambda: st)
    assert not w._moden_aktiv and w.mode_combo.isHidden() and w.mode_gewaehlt() == HAUPTMODE
    assert "Mode" not in w.ax_disp.get_title()
    w.exportiere(str(tmp_path / "k"))
    assert pd.ExcelFile(tmp_path / "k.xlsx").sheet_names == ["Parameter", "Punkte"]
    param = pd.read_excel(tmp_path / "k.xlsx", sheet_name="Parameter")
    assert "Mode" not in set(param["Groesse"])
    w.close()


def test_hauptfenster_ausreisser_je_mode_undo_panel_global(app):
    from tests.test_grenzgeraden_gui import _fenster_mit_stapel
    from polderfit.persistenz.projekt import sitzung_als_dict
    w = _fenster_mit_stapel()
    st = w.stapel
    st.n_moden = 2
    for e in st.ergebnisse:                       # Stapel auf zwei Zweige umbauen
        a = _mode(e.frequenz, MEFF_A, ALPHA_A, 2e-3, 1.0)
        b = _mode(e.frequenz, MEFF_B, ALPHA_B, 3e-3, 0.5)
        e.moden, e.n_moden = [a, b], 2
        e.B_res, e.dH, e.alpha = a["B_res"], a["dH"], a["alpha"]
    w._setze_n_moden(2)
    fenster = w._auswertungsfenster_holen()
    assert fenster._moden_aktiv
    w._ausreisser_mode_gewaehlt([(4, 2)])
    assert st.ausreisser_moden == [(4, 2)] and st.ausreisser == []
    panel = w.ausreisserpanel
    assert any("Mode 2" in panel.liste.item(i).text() for i in range(panel.liste.count()))
    w._rueckgaengig()
    assert st.ausreisser_moden == []
    w._wiederholen()
    assert st.ausreisser_moden == [(4, 2)]
    panel.liste.setCurrentRow(0)
    panel.btn_wieder.click()                       # Panel: wieder aufnehmen
    assert st.ausreisser_moden == []
    w._rueckgaengig()
    assert st.ausreisser_moden == [(4, 2)]
    # Blatt 'Global' der Einzelfit-Excel: Kittel/LLG je Mode.
    g = w._global_parameter()
    assert abs(g["mode1_kittel_mu0Meff"] - MEFF_A) < 1e-3
    assert abs(g["mode2_kittel_mu0Meff"] - MEFF_B) < 1e-3
    assert g["mode2_n_ausreisser_mode"] == 1 and g["mode1_n_punkte"] == 10
    assert "Ausreisser" in w._zusatzblaetter()
    blatt = w._zusatzblaetter()["Ausreisser"]
    assert int(blatt.iloc[0]["mode"]) == 2 and int(blatt.iloc[0]["index"]) == 4
    # Projektdatei enthaelt die Paare.
    assert sitzung_als_dict(st)["ausreisser_moden"] == [[4, 2]]
    fenster.close()
    w.close()

# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Offscreen-Tests des Grenzgeraden-Werkzeugs (GUI-Seite), der Navigator-
Farbskala und des Vollbereich-Umschalters am Linescan-Panel."""

import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtWidgets

from polderfit.fit.fenster_steuerung import Grenzgerade
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


def _ansicht():
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    m = MatrixAnsicht()
    m.zeige(_mini_datensatz())
    return m


def test_gerade_modus_zwei_klicks(app):
    m = _ansicht()
    got = {}
    m.starte_gerade_zeichnen(lambda p: got.__setitem__("p", p))
    assert m.modus == "gerade"
    m._on_press(_ev(m.ax, xdata=2.7, ydata=10.0))
    assert "p" not in got
    m._on_press(_ev(m.ax, xdata=3.2, ydata=40.0))
    assert got["p"] == [(2.7, 10.0), (3.2, 40.0)]
    assert m.modus is None


def test_geraden_overlay_und_saeume(app):
    m = _ansicht()
    g = Grenzgerade(b1=2.8, f1=10e9, b2=3.2, f2=40e9)
    m.zeige_grenzgeraden([g])
    labels = [a.get_label() for a in m._geraden_artists]
    assert labels.count("_gerade_saum") == 2          # gruener + roter Saum
    assert "_gerade" in labels and "_gerade_griff" in labels
    m.zeige_grenzgeraden([])
    assert m._geraden_artists == []


def test_endpunkt_ziehen_meldet_neue_geometrie(app):
    m = _ansicht()
    g = Grenzgerade(b1=2.8, f1=10e9, b2=3.2, f2=40e9)
    gemeldet = {}
    m.zeige_grenzgeraden(
        [g], endpunkt_geaendert=lambda i, b1, f1, b2, f2:
        gemeldet.update(i=i, b1=b1, f1=f1, b2=b2, f2=f2))
    # Endpunkt p2 anfassen und verschieben.
    m._on_press(_ev(m.ax, xdata=3.2, ydata=40.0))
    assert m._drag_endpunkt == (0, "p2")
    m._on_move(_ev(m.ax, xdata=3.4, ydata=45.0))
    m._on_release(_ev(m.ax, xdata=3.4, ydata=45.0))
    assert m._drag_endpunkt is None
    assert gemeldet["i"] == 0
    assert abs(gemeldet["b2"] - 3.4) < 1e-9 and abs(gemeldet["f2"] - 45.0) < 1e-9
    assert abs(g.b2 - 3.4) < 1e-9 and abs(g.f2 - 45e9) < 1e-3


def test_doppelklick_wechselt_seite(app):
    m = _ansicht()
    g = Grenzgerade(b1=3.0, f1=5e9, b2=3.0, f2=50e9)   # senkrechte Linie bei 3.0 T
    gewechselt = []
    m.zeige_grenzgeraden([g], seite_gewechselt=gewechselt.append)
    # Doppelklick direkt auf der Linie -> Seitenwechsel, KEIN Zoom-Reset noetig.
    m._on_press(_ev(m.ax, xdata=3.0, ydata=27.0, dblclick=True))
    assert gewechselt == [0]
    # Doppelklick fern der Linie -> normaler Zoom-Reset (kein Seitenwechsel).
    m._on_press(_ev(m.ax, xdata=2.55, ydata=27.0, dblclick=True))
    assert gewechselt == [0]


def test_zonen_panel_geraden_steuerung(app):
    from polderfit.gui.zonen_panel import ZonenPanel
    aufrufe = []
    panel = ZonenPanel(
        gerade_umschalten=lambda an: aufrufe.append(("modus", an)),
        gerade_seite=lambda i: aufrufe.append(("seite", i)),
        gerade_entfernen=lambda i: aufrufe.append(("weg", i)),
        geraden_fit=lambda: aufrufe.append(("fit",)),
    )
    assert panel.btn_gerade.isCheckable()
    panel.btn_gerade.setChecked(True)
    assert ("modus", True) in aufrufe

    aufrufe.clear()
    panel.setze_gerade_modus_aktiv(False)     # Sync ohne Rueckruf
    assert panel.btn_gerade.isChecked() is False and aufrufe == []

    panel.setze_geraden([Grenzgerade(b1=2.8, f1=10e9, b2=3.2, f2=40e9)])
    assert panel.geraden_liste.count() == 1
    panel.geraden_liste.setCurrentRow(0)
    panel.btn_gerade_seite.click()
    panel.btn_gerade_entfernen.click()
    panel.btn_geraden_fit.click()
    assert ("seite", 0) in aufrufe and ("weg", 0) in aufrufe and ("fit",) in aufrufe


def test_zonen_panel_seite_wechseln_ohne_auswahl_trifft_letzte_gerade(app):
    """Nach dem Einzeichnen ist keine Zeile angeklickt - der Knopf muss trotzdem
    auf die zuletzt gesetzte Gerade wirken (Nutzerbericht: 'funktioniert nicht')."""
    from polderfit.gui.zonen_panel import ZonenPanel
    aufrufe = []
    panel = ZonenPanel(
        gerade_seite=lambda i: aufrufe.append(("seite", i)),
        gerade_entfernen=lambda i: aufrufe.append(("weg", i)),
        gerade_mode=lambda i, m: aufrufe.append(("mode", i, m)),
    )
    # Ohne Geraden: Klick ist wirkungslos (kein Fehler).
    panel.btn_gerade_seite.click()
    assert aufrufe == []

    g1 = Grenzgerade(b1=2.8, f1=10e9, b2=3.2, f2=40e9)
    g2 = Grenzgerade(b1=2.9, f1=10e9, b2=3.3, f2=40e9)
    panel.setze_geraden([g1])
    assert panel.geraden_liste.currentRow() == 0        # neue Gerade vorgewaehlt
    panel.setze_geraden([g1, g2])
    assert panel.geraden_liste.currentRow() == 1        # zuletzt gesetzte
    panel.geraden_liste.clearSelection()
    panel.geraden_liste.setCurrentRow(-1)
    assert panel.geraden_liste.currentRow() == -1
    panel.btn_gerade_seite.click()
    assert aufrufe[-1] == ("seite", 1)                  # letzte Gerade, nicht nichts
    panel.geraden_liste.setCurrentRow(0)                # explizite Auswahl hat Vorrang
    panel.btn_gerade_seite.click()
    assert aufrufe[-1] == ("seite", 0)
    # Aendern ohne Hinzufuegen (z. B. Seite gewechselt) behaelt die Auswahl.
    g1.seite_wechseln()
    panel.setze_geraden([g1, g2])
    assert panel.geraden_liste.currentRow() == 0
    panel.setze_geraden([g1])                            # Entfernen: Auswahl geklemmt
    assert panel.geraden_liste.currentRow() == 0
    panel.setze_n_moden(2)
    panel.btn_gerade_mode.click()
    assert aufrufe[-1] == ("mode", 0, 2)


def test_navigator_robuste_farbskala(app):
    from polderfit.gui.navigator_ansicht import NavigatorAnsicht
    nav = NavigatorAnsicht()
    rng = np.random.default_rng(3)
    matrix = rng.normal(size=(20, 30))    # normale Struktur ...
    matrix[10, 15] = 1e6                  # ... plus einzelner dd-Ausreisser
    nav.zeige(matrix, (2.5, 3.5, 5.0, 50.0))
    bild = nav.ax.images[0]
    vmin, vmax = bild.get_clim()
    assert vmax < 1e6              # Ausreisser dominiert die Skala nicht mehr


def test_vollbereich_checkbox_spiegelt_aktion(app):
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    assert w.chk_vollbereich.isChecked() is False
    w.chk_vollbereich.setChecked(True)
    assert w.akt_vollbereich.isChecked() is True
    w.akt_vollbereich.setChecked(False)
    assert w.chk_vollbereich.isChecked() is False


def _fenster_mit_stapel(n=10):
    """Hauptfenster mit synthetischem Datensatz und gefuelltem Stapel (ohne Auto-Fit)."""
    from polderfit.fit.batch import StapelErgebnis
    from polderfit.fit.linescan_fit import FitErgebnis
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    ds = _mini_datensatz(n)
    ds.meta["zuordnung"] = {"re": ("g", "k")}
    w._datensatz_uebernehmen(ds)
    stapel = StapelErgebnis(datensatz=ds)
    for i, ls in enumerate(ds.linescans):
        stapel.ergebnisse.append(FitErgebnis(frequenz=ls.frequenz, erfolg=True,
                                             B_res=2.7 + 0.06 * i, problematisch=False))
        stapel.fenster.append((2.6, 3.4))
        stapel.zugeschnitten.append(ls)
    w.stapel = stapel
    return w


def test_geraden_fit_merkt_sich_frequenz_und_feldbereich(app, monkeypatch):
    """Bug: der Grenzgeraden-Dialog vergass den zuletzt eingegebenen
    Frequenz-/Feldbereich (sprang auf den ganzen Datenbereich zurueck)."""
    from polderfit.gui import bereichsfit_dialog as bd
    w = _fenster_mit_stapel()
    w._gerade_gezeichnet([(2.7, 10.0), (3.2, 40.0)])
    gestartet = []
    monkeypatch.setattr(w, "_starte_job", lambda *a, **k: gestartet.append(a))
    gesehen = []

    def exec_setzen(dlg):
        gesehen.append((dlg.f_von.value(), dlg.f_bis.value(), dlg.b_von.value(), dlg.b_bis.value()))
        dlg.f_von.setValue(20.0)
        dlg.b_bis.setValue(3.2)
        return True

    monkeypatch.setattr(bd.BereichsFitDialog, "exec", exec_setzen)
    w._geraden_fit()
    assert gesehen[-1] == (5.0, 50.0, 2.5, 3.5)               # erster Aufruf: Datenbereich
    assert w._bereich_frequenz == (20e9, 50e9) and w._bereich_feld == (2.5, 3.2)
    assert len(gestartet) == 1

    def exec_abbrechen(dlg):
        gesehen.append((dlg.f_von.value(), dlg.f_bis.value(), dlg.b_von.value(), dlg.b_bis.value()))
        return False

    monkeypatch.setattr(bd.BereichsFitDialog, "exec", exec_abbrechen)
    w._geraden_fit()
    assert gesehen[-1] == (20.0, 50.0, 2.5, 3.2)              # zweiter Aufruf: gemerkt
    assert len(gestartet) == 1                                # Abbruch startet nichts

    # Neuer Datensatz: Bereich gehoert zum alten -> wieder Datenbereich.
    w._datensatz_uebernehmen(_mini_datensatz())
    assert w._bereich_frequenz is None and w._bereich_feld is None


def test_geraden_bereich_vorgabe_klemmt_an_datenbereich(app):
    w = _fenster_mit_stapel()
    w._bereich_frequenz, w._bereich_feld = (1e9, 30e9), (3.6, 3.9)   # Feld ganz ausserhalb
    (b1, b2, f1, f2), gemerkt = w._geraden_bereich_vorgabe()
    assert gemerkt and (f1, f2) == (5.0, 30.0) and (b1, b2) == (2.5, 3.5)
    w._bereich_frequenz = w._bereich_feld = None
    (b1, b2, f1, f2), gemerkt = w._geraden_bereich_vorgabe()
    assert not gemerkt and (b1, b2, f1, f2) == (2.5, 3.5, 5.0, 50.0)


@pytest.mark.parametrize("locale_name, eingabe, erwartet", [
    ("de_DE", "5,51", 5.51), ("de_DE", "5.51", 5.51), ("de_DE", "12.5", 12.5),
    ("en_US", "5.51", 5.51), ("en_US", "5,51", 5.51), ("en_US", "0,25", 0.25),
])
def test_double_spinbox_punkt_und_komma(app, locale_name, eingabe, erwartet):
    """Bug: unter deutscher Locale wurde „5.51" zu 55 (Punkt = Tausendertrenner).
    Getippte Tausendertrenner werden bewusst nicht unterstuetzt (physikalische
    Groessen wie 1.234 T sind mit Punkt gemeint, nicht 1234 T)."""
    from PySide6 import QtCore
    from PySide6.QtTest import QTest
    from polderfit.gui.widgets import RuhigeDoubleSpinBox
    box = RuhigeDoubleSpinBox()
    box.setLocale(QtCore.QLocale(locale_name))
    box.setRange(0.0, 5000.0)
    box.setDecimals(3)
    box.setValue(0.01)
    box.setSuffix(" GHz")
    box.show()
    box.setFocus()
    box.selectAll()
    QTest.keyClicks(box, eingabe)
    assert box.value() == pytest.approx(erwartet)
    assert box.valueFromText(eingabe) == pytest.approx(erwartet)


def test_auswahl_dialog_resonanzen_dropdown_und_zweistufig(app):
    from polderfit.gui.auswahl_dialog import AuswahlDialog
    dlg = AuswahlDialog(_mini_datensatz(), None, n_moden=2, zweistufig=True)
    assert dlg.n_moden() == 2 and dlg.zweistufig() is True and dlg.chk_zweistufig.isEnabled()
    dlg.moden_combo.setCurrentIndex(dlg.moden_combo.findData(1))
    assert dlg.n_moden() == 1 and dlg.zweistufig() is False
    assert not dlg.chk_zweistufig.isEnabled()          # nur bei > 1 Resonanz sinnvoll
    dlg2 = AuswahlDialog(_mini_datensatz())
    assert dlg2.n_moden() == 1 and dlg2.zweistufig() is False


def test_hauptfenster_uebernimmt_moden_aus_auswahl_dialog(app, monkeypatch):
    from polderfit.gui import auswahl_dialog as ad
    w = _fenster_mit_stapel()

    def exec_setzen(dlg):
        dlg.moden_combo.setCurrentIndex(dlg.moden_combo.findData(2))
        dlg.chk_zweistufig.setChecked(True)
        return True

    monkeypatch.setattr(ad.AuswahlDialog, "exec", exec_setzen)
    assert w._frage_auswahl() is not None
    assert w._physik.n_moden == 2 and w._physik.auto_fit_zweistufig is True
    assert w.stapel.n_moden == 2 and w._einstellungen.physik["auto_fit_zweistufig"] is True


def test_geraden_mode_zuordnung_und_undo(app):
    w = _fenster_mit_stapel()
    assert w.zonenpanel.band_box.isHidden()          # eine Mode: klassische Ansicht
    w._setze_n_moden(2)
    assert not w.zonenpanel.band_box.isHidden()
    w._gerade_gezeichnet([(2.7, 10.0), (3.2, 40.0)])
    assert w._grenzgeraden[0].mode == 1              # erste Gerade: Mode 1
    assert w.zonenpanel.geraden_liste.item(0).text().startswith("M1")
    w.zonenpanel.geraden_liste.setCurrentRow(0)
    w.zonenpanel.btn_gerade_mode.click()            # Experten-Werkzeug: 1 -> 2
    assert w._grenzgeraden[0].mode == 2
    assert w.zonenpanel.geraden_liste.item(0).text().startswith("M2")
    w._rueckgaengig()
    assert w._grenzgeraden[0].mode == 1
    w._setze_n_moden(1)
    assert w.zonenpanel.mode_neu() == 1


def test_sukzessive_moden_nummerierung(app):
    """Nutzerwunsch: Baender NACHEINANDER einzeichnen, Mode-Nummer automatisch -
    zwei Geraden = ein Band = eine Mode, das naechste Band ist die naechste Mode
    (bis zur eingestellten Modenzahl); Fit-Modenzahl = Zahl der Baender."""
    w = _fenster_mit_stapel()
    panel = w.zonenpanel
    w._setze_n_moden(3)
    assert panel.mode_neu() == 1 and panel.n_moden_effektiv() == 1
    w._gerade_gezeichnet([(2.7, 10.0), (3.2, 40.0)])       # Mode 1, Gerade 1
    assert panel.mode_neu() == 1                           # Band 1 noch offen
    w._gerade_gezeichnet([(2.8, 10.0), (3.3, 40.0)])       # Mode 1, Gerade 2 -> Band 1 fertig
    assert [g.mode for g in w._grenzgeraden] == [1, 1]
    assert panel.mode_neu() == 2 and panel.n_moden_effektiv() == 1
    assert "Mode 1 fitten" in panel.btn_geraden_fit.text()
    assert "nächste Gerade/Band: Mode 2" in panel.band_status.text()
    panel.breite_spin.setValue(8)
    w._band_gezeichnet([(2.9, 10.0), (3.4, 40.0)])         # Band-Werkzeug -> Mode 2
    assert [g.mode for g in w._grenzgeraden] == [1, 1, 2, 2]
    assert panel.mode_neu() == 3 and panel.n_moden_effektiv() == 2
    assert "Moden 1–2 fitten" in panel.btn_geraden_fit.text()
    assert "M1 ✓ (2)" in panel.band_status.text() and "M2 ✓ (2)" in panel.band_status.text()
    w._band_gezeichnet([(3.0, 10.0), (3.5, 40.0)])         # Mode 3
    assert panel.n_moden_effektiv() == 3
    w._gerade_gezeichnet([(3.1, 10.0), (3.6, 40.0)])       # ueber der Obergrenze: bleibt Mode 3
    assert w._grenzgeraden[-1].mode == 3 and panel.mode_neu() == 3
    w._rueckgaengig()
    w._rueckgaengig()                                      # Band 3 weg
    assert panel.n_moden_effektiv() == 2 and panel.mode_neu() == 3
    # Klassisch (eine Resonanz): immer Mode 1, Knopftext klassisch.
    w._setze_n_moden(1)
    assert panel.mode_neu() == 1 and "Grünen Bereich" in panel.btn_geraden_fit.text()


def test_band_werkzeug_und_vorpruefung(app, monkeypatch):
    from polderfit.fit.fenster_steuerung import band_geraden
    from polderfit.gui import bereichsfit_dialog as bd
    w = _fenster_mit_stapel()
    panel = w.zonenpanel
    assert panel.band_box.isHidden() and "Grünen Bereich" in panel.btn_geraden_fit.text()
    panel.n_moden_combo.setCurrentIndex(panel.n_moden_combo.findData(2))   # Panel -> Hauptfenster
    assert w._physik.n_moden == 2 and w.stapel.n_moden == 2 and w.spin_moden.value() == 2
    assert not panel.band_box.isHidden() and "Mode 1 fitten" in panel.btn_geraden_fit.text()
    panel.breite_spin.setValue(8)
    w._band_gezeichnet([(2.7, 10.0), (3.2, 40.0)])
    assert len(w._grenzgeraden) == 2 and all(g.mode == 1 for g in w._grenzgeraden)
    assert "M1 ✓" in panel.band_status.text() and "M2 –" in panel.band_status.text()
    w._band_gezeichnet([(2.8, 10.0), (3.3, 40.0)])       # zweites Band -> Mode 2
    assert [g.mode for g in w._grenzgeraden] == [1, 1, 2, 2]
    assert "M2 ✓" in panel.band_status.text()
    w._rueckgaengig()
    w._rueckgaengig()
    assert w._grenzgeraden == []
    # Vorpruefung: Geraden, deren gruene Seiten sich nirgends schneiden -> kein Dialog
    a, b = band_geraden(2.6, 5e9, 3.4, 50e9, 0.02, 1)
    a.seite_wechseln()
    b.seite_wechseln()
    w._geraden_setzen([a, b])
    monkeypatch.setattr(bd.BereichsFitDialog, "exec",
                        lambda dlg: pytest.fail("Dialog trotz leerem Fit-Bereich"))
    w._geraden_fit()
    assert "kein linescan" in w.statusBar().currentMessage().lower()
    w._setze_n_moden(1)
    assert panel.band_box.isHidden() and panel.n_moden_combo.currentData() == 1

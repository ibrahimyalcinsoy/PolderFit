# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Tests der Erweiterungen: Layout-Stabilitaet des Farbplots, Normfarben/Status,
Bewertung, Mehr-Moden-Fit, Fits ohne Auto-Fit (Grenzgeraden), Export-Spalten,
Voreinstellungen, Projekt v3, Vollbild, exklusive Verarbeitung, Mausrad-Schutz."""

import json
import os

import numpy as np
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PySide6 import QtCore, QtWidgets

from polderfit.fit.batch import StapelErgebnis, fitte_alle, fitte_neu, leerer_stapel
from polderfit.fit.fenster_steuerung import Grenzgerade, fitte_geraden_bereich
from polderfit.fit.linescan_fit import FitErgebnis, fitte_linescan, setze_bewertung
from polderfit.fit.parameter import PhysikParameter
from polderfit.io.datensatz import Linescan, Messdatensatz
from polderfit.physik.fitmodell import s21_modell_multi
from polderfit.physik.konstanten import GAMMA_STANDARD
from polderfit.verarbeitung import Verarbeitungskette


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _ev(ax=None, **kw):
    d = dict(inaxes=ax, xdata=None, ydata=None, step=0, key=None, dblclick=False, button=1)
    d.update(kw)
    return SimpleNamespace(**d)


def _pumpe(ms=2000):
    schleife = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, schleife.quit)
    schleife.exec()


def _synth_linescan(f, moden, B=None, rausch=0.01, seed=1):
    """Synthetischer Linescan mit n Polder-Linien (moden = [(B_res, alpha, A, phi)])."""
    omega = 2 * np.pi * f
    B = np.linspace(0.55, 0.95, 400) if B is None else B
    s = s21_modell_multi(B, moden, 0.02, -0.01, 0.05, 0.03, omega, GAMMA_STANDARD,
                         float(B.mean()))
    rng = np.random.default_rng(seed)
    hub = np.ptp(np.abs(s - (0.02 - 0.01j) - (0.05 + 0.03j) * (B - B.mean())))
    s = s + rng.normal(scale=rausch * hub, size=B.size) + 1j * rng.normal(scale=rausch * hub, size=B.size)
    return Linescan(frequenz=float(f), feld=B, re=s.real, im=s.imag)


def _synth_datensatz(n=8, zwei_moden=False):
    """Kittel-artige Dispersion, eine (oder zwei) Resonanzen je Frequenz."""
    linescans = []
    for k, f in enumerate(np.linspace(10e9, 24e9, n)):
        b = 0.62 + 0.02 * k
        moden = [(b, 0.012, 3e-6, 0.4)]
        if zwei_moden:
            moden.append((b + 0.035, 0.010, 2e-6, 0.9))
        linescans.append(_synth_linescan(f, moden, seed=k))
    ds = Messdatensatz(quelle="synth", format_typ="sortiert", linescans=linescans)
    ds.meta["zuordnung"] = {"re": ("g", "k")}
    return ds


def _mini_datensatz(n=10):
    B = np.linspace(2.5, 3.5, 40)
    freqs = np.linspace(5e9, 50e9, n)
    ls = [Linescan(frequenz=float(f), feld=B, re=np.cos(20 * B), im=np.sin(20 * B)) for f in freqs]
    return Messdatensatz(quelle="t", format_typ="sortiert", linescans=ls)


# ---------------------------------------------------------------------------
# Farbplot: Layout schrumpft nicht mehr (Regression Δn-Mausrad-Bug)
# ---------------------------------------------------------------------------
def test_farbplot_schrumpft_nicht_bei_wiederholter_verarbeitung(app):
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    B = np.linspace(0.0, 1.0, 200)
    ds = Messdatensatz(quelle="t", format_typ="sortiert", linescans=[
        Linescan(frequenz=float(f), feld=B, re=np.cos(20 * B), im=np.sin(20 * B))
        for f in np.linspace(5e9, 40e9, 30)])
    m = MatrixAnsicht()
    m.resize(520, 500)
    m.show()
    m.zeige(ds)
    app.processEvents()
    start = m.ax.get_position().width
    for k in range(1, 25):                      # wie 24 Mausrad-Schritte auf Δn
        kette = Verarbeitungskette.standard()
        kette.schritte[1].parameter["delta_n"] = k
        m.setze_verarbeitung(kette, "betrag")
        app.processEvents()
    ende = m.ax.get_position().width
    assert ende >= 0.55                          # frueher: 0.016 (unkenntlich schmal)
    assert abs(ende - start) < 0.05
    m.close()


def test_farbplot_status_marker_und_tooltips(app):
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    m = MatrixAnsicht()
    ds = _mini_datensatz(6)
    m.zeige(ds)
    f = ds.frequenzen
    status = ["gut", "bestaetigt", "problem", "fehler", "gut", "gut"]
    ausgeschlossen = np.array([False, False, False, False, True, False])
    m.aktualisiere_resonanz(f, np.full(6, 3.0), np.array([s == "problem" for s in status]),
                            ausgeschlossen, status=status, info=[f"punkt {i}" for i in range(6)],
                            nebenmoden=[np.array([3.1, np.nan, 3.1, np.nan, np.nan, 3.1])])
    labels = [ln.get_label() for ln in m.ax.lines]
    assert "_resonanz" in labels and "_resonanz_problem" in labels
    assert "_resonanz_fehler" in labels and "_resonanz_nebenmode" in labels
    assert "_resonanz_ignoriert" not in labels           # Ausreisser standardmaessig unsichtbar
    m.setze_ausreisser_anzeigen(True)
    assert "_resonanz_ignoriert" in [ln.get_label() for ln in m.ax.lines]
    m.setze_problemfits_ausblenden(True)
    labels = [ln.get_label() for ln in m.ax.lines]
    assert "_resonanz_problem" not in labels and "_resonanz_fehler" not in labels
    # Hover ueber einem Punkt findet den Index (Tooltip-Text vorhanden).
    m._hover(_ev(m.ax, xdata=3.0, ydata=f[0] / 1e9))
    assert m._hover_index == 0
    m._hover(_ev(m.ax, xdata=2.5, ydata=f[0] / 1e9 + 100))
    assert m._hover_index is None
    # Farbskala wechseln bleibt stabil (unbekannter Name -> Standard).
    m.setze_farbskala("gray")
    assert m.farbskala() == "gray"
    m.setze_farbskala("gibtsnicht")
    assert m.farbskala() == "viridis"
    feld, freq, matrix = m.verarbeitete_matrix()
    assert matrix.shape == (6, feld.size)


def test_farben_status_von():
    from polderfit.gui import farben as F
    gut = FitErgebnis(frequenz=1e9, erfolg=True, B_res=0.5, problematisch=False)
    assert F.status_von(gut) == "gut"
    assert F.status_von(gut, ignoriert=True) == "ignoriert"
    assert F.status_von(setze_bewertung(gut, "verworfen")) == "problem"
    best = FitErgebnis(frequenz=1e9, erfolg=True, B_res=0.5, problematisch=False,
                       problematisch_auto=False, bewertung="bestaetigt")
    assert F.status_von(best) == "bestaetigt"
    assert F.status_von(FitErgebnis(frequenz=1e9, erfolg=False)) == "fehler"
    assert F.status_von(FitErgebnis.platzhalter(1e9)) == "ignoriert"
    # Jede Statusklasse hat Farbe UND eigene Form (zweites Merkmal).
    assert set(F.STATUS_FARBEN) == set(F.STATUS_MARKER)


# ---------------------------------------------------------------------------
# Bewertung: manuelle Nachfits gelten als bestaetigt, Umbewerten ist eine Kopie
# ---------------------------------------------------------------------------
def test_bewertung_setzen_und_platzhalter():
    ls = _synth_linescan(20e9, [(0.735, 0.012, 3e-6, 0.4)])
    erg = fitte_linescan(ls, GAMMA_STANDARD)
    assert erg.bewertung == "auto" and erg.problematisch == erg.problematisch_auto
    v = setze_bewertung(erg, "verworfen")
    assert v.problematisch and v.bewertung == "verworfen" and v is not erg
    assert "vom Nutzer" in v.problem_text
    b = setze_bewertung(v, "bestaetigt")
    assert not b.problematisch and b.bewertung == "bestaetigt"
    a = setze_bewertung(b, "auto")
    assert a.problematisch == erg.problematisch_auto and a.bewertung == "auto"
    with pytest.raises(ValueError):
        setze_bewertung(erg, "egal")
    # Fehlgeschlagener Fit kann nicht "gut" werden.
    kaputt = FitErgebnis(frequenz=1e9, erfolg=False)
    assert setze_bewertung(kaputt, "bestaetigt").bewertung == "auto"
    # Platzhalter: nicht gefittet, kein Problemfit-Ziel, erkennbar in der Zeile.
    ph = FitErgebnis.platzhalter(1e9, np.linspace(0, 1, 10))
    assert not ph.gefittet and ph.problem_gruende == ["nicht gefittet"]
    zeile = ph.als_zeile()
    assert zeile["gefittet"] is False and np.isnan(zeile["B_res_T"])


def test_stapel_nachfit_bestaetigt_und_umschaltbar():
    ds = _synth_datensatz(4)
    st = fitte_alle(ds, nachfenster_faktor=0.0)
    assert all(e.bewertung == "auto" for e in st.ergebnisse)
    e = fitte_neu(st, 1)                            # manueller Eingriff
    assert e.bewertung == "bestaetigt" and not e.problematisch
    st.nachfit_bestaetigen = False
    e2 = fitte_neu(st, 2)
    assert e2.bewertung == "auto"
    st.bewerte(2, "verworfen")
    assert st.ergebnisse[2].problematisch and 2 in st.index_problematisch()
    st.bewerte(2, "auto")
    assert st.ergebnisse[2].problematisch == st.ergebnisse[2].problematisch_auto


# ---------------------------------------------------------------------------
# Mehrere Resonanzen je Linescan
# ---------------------------------------------------------------------------
def test_zwei_lorentz_simultan():
    wahr = [(0.735, 0.012, 3e-6, 0.4), (0.765, 0.010, 2e-6, 0.9)]
    ls = _synth_linescan(20e9, wahr)
    e1 = fitte_linescan(ls, GAMMA_STANDARD, n_moden=1)
    e2 = fitte_linescan(ls, GAMMA_STANDARD, n_moden=2)
    assert e2.n_moden == 2 and len(e2.moden) == 2 and len(e2.fitkurven_moden) == 2
    assert e2.rmse_norm < 0.5 * e1.rmse_norm            # zwei Linien passen deutlich besser
    b_res = sorted(m["B_res"] for m in e2.moden)
    assert abs(b_res[0] - 0.735) < 2e-3 and abs(b_res[1] - 0.765) < 2e-3
    alphas = {round(m["B_res"], 2): m["alpha"] for m in e2.moden}
    assert abs(alphas[0.73] - 0.012) < 0.002 and abs(alphas[0.77] - 0.010) < 0.002
    # Hauptmode = staerkste Linie (A=3e-6 bei 0.735 T) fuellt die Ergebnisfelder.
    assert abs(e2.B_res - 0.735) < 2e-3 and e2.moden[0]["B_res"] == e2.B_res
    assert np.isfinite(e2.dH_mT) and e2.kovarianz_ok
    zeile = e2.als_zeile()
    for spalte in ("B_res_2_T", "alpha_2", "mu0_dH_2_mT", "A_2", "phi_2_rad", "mu0_dH_mT",
                   "B_res_mT", "A_komplex_re", "A_komplex_im", "phi_deg"):
        assert spalte in zeile
    assert abs(zeile["mu0_dH_mT"] - e2.dH * 1e3) < 1e-9
    assert "B_res_2_T" not in e2.als_zeile(hauptmode_nur=True)


def test_hauptmode_wechseln_und_stapel_mit_moden():
    from polderfit.fit.linescan_fit import hauptmode_wechseln
    ds = _synth_datensatz(3, zwei_moden=True)
    st = fitte_alle(ds, nachfenster_faktor=0.0, n_moden=2)
    assert st.n_moden == 2 and all(e.n_moden == 2 for e in st.ergebnisse)
    e = st.ergebnisse[0]
    gewechselt = hauptmode_wechseln(e, 1)
    assert gewechselt.B_res == e.moden[1]["B_res"] and gewechselt.moden[1]["B_res"] == e.B_res
    assert hauptmode_wechseln(e, 0) is e
    # Einzelner Nachfit mit anderer Modenzahl.
    e1 = fitte_neu(st, 0, n_moden=1)
    assert e1.n_moden == 1


# ---------------------------------------------------------------------------
# Fits ohne Auto-Fit: leerer Stapel + Grenzgeraden mit Frequenz von … bis …
# ---------------------------------------------------------------------------
def test_grenzgeraden_fit_ohne_autofit():
    ds = _synth_datensatz(8)
    st = leerer_stapel(ds, nachfenster_faktor=0.0)
    assert len(st.ergebnisse) == 8 and st.index_gefittet() == [] and st.index_problematisch() == []
    # Senkrechte Gerade bei 0.55 T (links); gruen = rechts davon (alles).
    g = Grenzgerade(b1=0.56, f1=5e9, b2=0.56, f2=30e9, gruen_positiv=False)
    iv = g.erlaubtes_intervall(10e9, 0.55, 0.95)
    if iv is None or iv[1] < 0.9:                 # gruen soll RECHTS der Geraden liegen
        g.seite_wechseln()
    assert g.erlaubtes_intervall(10e9, 0.55, 0.95)[1] > 0.9
    neu, uebersprungen = fitte_geraden_bereich(st, [g], frequenz_min=12e9, frequenz_max=20e9)
    f = ds.frequenzen
    erwartet = [int(i) for i in np.flatnonzero((f >= 12e9) & (f <= 20e9))]
    assert neu == erwartet
    assert sorted(uebersprungen) == [i for i in range(8) if i not in erwartet]
    assert st.index_gefittet() == erwartet
    for i in erwartet:
        e = st.ergebnisse[i]
        # Bulk-Fit ueber viele Frequenzen: Kriterien bewerten (keine Nutzer-Freigabe).
        assert e.gefittet and e.bewertung == "auto" and e.nachbearbeitet
        assert abs(e.B_res - (0.62 + 0.02 * i)) < 5e-3
    for i in uebersprungen:
        assert not st.ergebnisse[i].gefittet
    # Nicht gefittete Frequenzen bleiben ausserhalb von Kittel/LLG und Problemfits.
    assert all(e.gefittet for e in st.ergebnisse_aktiv() if e.erfolg)
    assert st.problem_statistik().get("nicht gefittet") == len(uebersprungen)


# ---------------------------------------------------------------------------
# Export: Spaltengruppen, mT, Zusatzblaetter, CSV deutsch
# ---------------------------------------------------------------------------
def test_export_spaltengruppen_und_zusatzblaetter(tmp_path):
    from polderfit.persistenz.ergebnis_export import (
        SPALTEN_GRUPPEN, exportiere_csv, exportiere_excel, kittel_llg_tabelle,
        parameter_tabelle, spalten_fuer)
    import pandas as pd
    ds = _synth_datensatz(5, zwei_moden=True)
    st = fitte_alle(ds, nachfenster_faktor=0.0, n_moden=2)
    st.ergebnisse.append(FitErgebnis.platzhalter(99e9))
    alle = parameter_tabelle(st.ergebnisse, ausreisser=[1], verwendet=[0, 2])
    assert len(alle) == 6
    for spalte in ("mu0_dH_mT", "B_res_mT", "A_komplex_re", "bewertung", "ausreisser",
                   "im_kittel_verwendet", "B_res_2_T", "n_punkte_fenster", "gefittet"):
        assert spalte in alle.columns
    assert bool(alle.loc[alle["frequenz_Hz"] == st.ergebnisse[1].frequenz, "ausreisser"].iloc[0])
    nur = parameter_tabelle(st.ergebnisse, spalten=["kern"], nur_gefittete=True)
    assert len(nur) == 5 and list(nur.columns) == [
        c for c in SPALTEN_GRUPPEN["kern"][1] if c in alle.columns]
    assert "B_res_2_T" in spalten_fuer(["nebenmoden"], list(alle.columns))
    assert "B_res_2_T" not in spalten_fuer(["kern", "status"], list(alle.columns))

    xlsx = tmp_path / "e.xlsx"
    exportiere_excel(st.ergebnisse, str(xlsx), {"kittel_mu0Meff": 1.0}, ausreisser=[1],
                     spalten=["kern", "status"], nur_gefittete=True,
                     zusatzblaetter={"Einstellungen": pd.DataFrame([{"Groesse": "g", "Wert": 2.0}])})
    blaetter = pd.read_excel(xlsx, sheet_name=None)
    assert set(blaetter) == {"Einzelfits", "Global", "Einstellungen"}
    assert "mu0_dH_mT" in blaetter["Einzelfits"].columns and "A" not in blaetter["Einzelfits"].columns
    csv_de = tmp_path / "e.csv"
    exportiere_csv(st.ergebnisse, str(csv_de), spalten=["kern"], deutsch=True, nur_gefittete=True)
    text = csv_de.read_text(encoding="utf-8-sig")
    assert ";" in text.splitlines()[0] and "," in text.splitlines()[1]
    tab = kittel_llg_tabelle({"geometrie": "oop",
                              "kittel": {"mu0Meff": 1.2, "mu0Meff_err": 0.01, "g_faktor": 2.0,
                                         "g_faktor_err": 0.01, "gamma": 1.7e11, "gamma_err": 1e9, "R2": 0.99},
                              "llg": {"alpha": 0.01, "alpha_err": 1e-4, "mu0Hinh": 0.002,
                                      "mu0Hinh_err": 1e-4, "R2": 0.9}})
    assert "mu0_Meff_mT" in set(tab["Groesse"]) and "mu0_Hinh_mT" in set(tab["Groesse"])


# ---------------------------------------------------------------------------
# Voreinstellungen und Projekt v3
# ---------------------------------------------------------------------------
def test_einstellungen_roundtrip_und_konfigpfad(tmp_path, monkeypatch):
    from polderfit.persistenz import einstellungen as E
    monkeypatch.setenv("POLDERFIT_KONFIG", str(tmp_path / "konfig"))
    assert E.konfig_verzeichnis() == tmp_path / "konfig" and (tmp_path / "konfig").is_dir()
    einst = E.Einstellungen()
    einst.physik = PhysikParameter(g_faktor=2.1, n_moden=2, alpha_plausibel=0.2,
                                   nachfit_bestaetigen=False).als_dict()
    einst.anzeige["farbskala"] = "gray"
    einst.export["spalten"] = ["kern", "status"]
    einst.export["csv_deutsch"] = True
    pfad = E.speichere_einstellungen(einst, tmp_path / ("x" + E.DATEI_ENDUNG))
    geladen = E.lade_einstellungen(pfad)
    p = geladen.physik_parameter()
    assert p.g_faktor == 2.1 and p.n_moden == 2 and p.alpha_plausibel == 0.2
    assert p.nachfit_bestaetigen is False and p.alpha_plausibel_wirksam == 0.2
    assert geladen.anzeige["farbskala"] == "gray" and geladen.export["csv_deutsch"] is True
    assert geladen.export["spalten"] == ["kern", "status"]
    # Unbekannte/ungueltige Werte werden abgefangen.
    kaputt = E.Einstellungen.aus_dict({"anzeige": {"farbskala": "nix", "fremd": 1},
                                       "physik": {"geometrie": "xy", "unbekannt": 5}})
    assert kaputt.anzeige["farbskala"] == "viridis" and "fremd" not in kaputt.anzeige
    assert kaputt.physik_parameter().geometrie == "oop"
    # Standarddatei: erst keine, dann geladen.
    assert E.lade_standard()[1] is False
    E.speichere_einstellungen(einst, E.standard_pfad())
    st, ok = E.lade_standard()
    assert ok and st.physik_parameter().g_faktor == 2.1
    assert E.autosicherung_pfad().parent == tmp_path / "konfig"


def test_projekt_v3_bewertung_geraden_platzhalter(tmp_path):
    from polderfit.persistenz.projekt import (
        grenzgeraden_aus_sitzung, lade_sitzung, speichere_sitzung, stelle_stapel_wieder_her)
    ds = _synth_datensatz(6)
    st = leerer_stapel(ds, nachfenster_faktor=0.0)
    g = Grenzgerade(b1=0.56, f1=5e9, b2=0.56, f2=30e9, gruen_positiv=False)
    iv = g.erlaubtes_intervall(10e9, 0.55, 0.95)
    if iv is None or iv[1] < 0.9:                 # gruen soll RECHTS der Geraden liegen
        g.seite_wechseln()
    assert g.erlaubtes_intervall(10e9, 0.55, 0.95)[1] > 0.9
    fitte_geraden_bereich(st, [g], frequenz_min=12e9)
    gefittet = st.index_gefittet()
    assert gefittet and len(gefittet) < 6
    st.bewerte(gefittet[0], "verworfen")
    st.bewerte(gefittet[1], "auto")
    st.bewerte(gefittet[2], "bestaetigt")
    physik = PhysikParameter(g_faktor=2.05).als_dict()
    pfad = tmp_path / "p.json"
    speichere_sitzung(st, str(pfad), physik=physik,
                      verarbeitung=Verarbeitungskette.standard().als_dict(), grenzgeraden=[g])
    daten = lade_sitzung(str(pfad))
    assert daten["polderfit_projekt_version"] == 3
    assert daten["physik"]["g_faktor"] == 2.05 and daten["verarbeitung"]["schritte"]
    assert grenzgeraden_aus_sitzung(daten)[0].b1 == 0.56
    # Keine Anzeige-Zustaende in der Datei.
    assert not any(k in daten for k in ("zoom", "xlim", "layout", "geometrie_fenster"))
    wieder = stelle_stapel_wieder_her(daten, ds)
    assert wieder.index_gefittet() == gefittet
    assert wieder.ergebnisse[gefittet[0]].bewertung == "verworfen"
    assert wieder.ergebnisse[gefittet[0]].problematisch
    assert wieder.ergebnisse[gefittet[1]].bewertung == "auto"
    assert wieder.ergebnisse[gefittet[2]].bewertung == "bestaetigt"
    assert not wieder.ergebnisse[0].gefittet


# ---------------------------------------------------------------------------
# GUI: Vollbild, Layout-Reset, Modi ohne Auto-Fit, Bewertungs-Aktionen, Panels
# ---------------------------------------------------------------------------
def test_hauptfenster_vollbild_layout_und_modi_ohne_autofit(app, monkeypatch, tmp_path):
    monkeypatch.setenv("POLDERFIT_KONFIG", str(tmp_path / "konfig"))
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    w.show()
    # Vollbild ueber die Aktion (F11) und wieder zurueck; Esc verlaesst es.
    w.akt_vollbild.setChecked(True)
    app.processEvents()
    assert w.isFullScreen()
    w._esc_gedrueckt()
    app.processEvents()
    assert not w.isFullScreen() and not w.akt_vollbild.isChecked()

    ds = _synth_datensatz(6)
    w._datensatz_uebernehmen(ds)
    assert w.stapel is not None and w.stapel.index_gefittet() == []
    assert not w.verarbeitung_dock.isHidden()
    # Grenzgerade und Zone sind OHNE Auto-Fit erlaubt, Ausreisser (braucht Punkte) nicht.
    w.akt_gerade.setChecked(True)
    assert w.matrix.modus == "gerade"
    w.akt_zone.setChecked(True)
    assert w.matrix.modus == "zone" and not w.akt_gerade.isChecked()
    w.matrix.beende_modus()
    w.akt_ausreisser.setChecked(True)
    assert w.akt_ausreisser.isChecked() is False and w.matrix.modus is None
    # Klick in die Karte oeffnet das Linescan-Panel (Grenzen ziehen fittet dort).
    w._frequenz_gewaehlt(2)
    assert not w.linescan_dock.isHidden()
    assert "nicht gefittet" in w.label_info.text()
    w._grenzen_geaendert(0.58, 0.80)
    e = w.stapel.ergebnisse[w.aktueller_index]
    assert e.gefittet and e.bewertung == "bestaetigt"
    assert w.status_label.objectName() == "status_bestaetigt"
    # Bewertung ueber die Aktionen inkl. Undo.
    w._bewerte_aktuellen("verworfen")
    assert w.stapel.ergebnisse[w.aktueller_index].problematisch
    assert w.status_label.objectName() == "status_problem"
    w._rueckgaengig()
    assert w.stapel.ergebnisse[w.aktueller_index].bewertung == "bestaetigt"
    w._bewerte_aktuellen("ignorieren")
    assert w.stapel.ist_ausreisser(w.aktueller_index)
    assert w.status_label.objectName() == "status_ignoriert"
    w._bewerte_aktuellen("ignorieren")
    assert not w.stapel.ist_ausreisser(w.aktueller_index)
    # Auswahlliste spiegelt den Zustand und setzt ihn.
    assert w.bewertung_combo.currentData() == "bestaetigt"
    w.bewertung_combo.setCurrentIndex(w.bewertung_combo.findData("verworfen"))
    w._bewertung_gewaehlt(w.bewertung_combo.currentIndex())
    assert w.stapel.ergebnisse[w.aktueller_index].bewertung == "verworfen"
    w.bewertung_combo.setCurrentIndex(w.bewertung_combo.findData("ignorieren"))
    w._bewertung_gewaehlt(w.bewertung_combo.currentIndex())
    assert w.stapel.ist_ausreisser(w.aktueller_index)
    w.bewertung_combo.setCurrentIndex(w.bewertung_combo.findData("auto"))
    w._bewertung_gewaehlt(w.bewertung_combo.currentIndex())
    assert not w.stapel.ist_ausreisser(w.aktueller_index)
    assert w.stapel.ergebnisse[w.aktueller_index].bewertung == "auto"
    # Keine Statistik-Kennzahlen in der Anzeige.
    assert "rmse" not in w.label_info.text() and "1−R²" not in w.label_info.text()
    # Layout-Reset behaelt Daten und Fits.
    w._layout_zuruecksetzen()
    assert w.stapel.index_gefittet() == [w.aktueller_index]
    assert not w.linescan_dock.isHidden() and not w.verarbeitung_dock.isHidden()
    # Auto-Sicherung schreibt eine Projektdatei ins Konfigurationsverzeichnis.
    w._autosicherung_schreiben()
    from polderfit.persistenz.einstellungen import autosicherung_pfad
    assert autosicherung_pfad().exists()
    daten = json.loads(autosicherung_pfad().read_text(encoding="utf-8"))
    assert daten["polderfit_projekt_version"] == 3
    w.close()


def test_hauptfenster_einstellungen_und_export(app, monkeypatch, tmp_path):
    monkeypatch.setenv("POLDERFIT_KONFIG", str(tmp_path / "konfig"))
    from polderfit.gui.hauptfenster import Hauptfenster
    from polderfit.persistenz.einstellungen import Einstellungen, standard_pfad
    w = Hauptfenster()
    ds = _synth_datensatz(5)
    w._datensatz_uebernehmen(ds)
    w.stapel = fitte_alle(ds, nachfenster_faktor=0.0)
    w._nach_autofit(w.stapel)
    assert not w.linescan_dock.isHidden()
    # Physik-Parameter wirken auf Stapel und Spin-Box.
    w._physik_uebernehmen(PhysikParameter(n_moden=2, alpha_plausibel=0.3, nachfit_bestaetigen=False))
    assert w.stapel.n_moden == 2 and w.stapel.alpha_plausibel == 0.3
    assert w.stapel.nachfit_bestaetigen is False and w.spin_moden.value() == 2
    # Farbskala ueber Menue und Panel synchron.
    w._farbskala_setzen("gray")
    assert w.matrix.farbskala() == "gray" and w.verarbeitung.farbskala() == "gray"
    assert w.akt_farbskalen["gray"].isChecked()
    # Einstellungen sammeln / als Standard / zuruecksetzen.
    e = w._einstellungen_sammeln()
    assert e.physik["n_moden"] == 2 and e.anzeige["farbskala"] == "gray"
    w._einstellungen_als_standard()
    assert standard_pfad().exists()
    w._einstellungen_anwenden(Einstellungen(), melden=False)
    assert w._physik.n_moden == 1 and w.matrix.farbskala() == "viridis"
    # Export ohne Dialoge in Dateien.
    xlsx = w._export_excel(str(tmp_path / "a.xlsx"))
    csv = w._export_csv(str(tmp_path / "a.csv"))
    bild = w._export_farbplot_bild(str(tmp_path / "a.png"))
    matrix = w._export_matrix_csv(str(tmp_path / "a_matrix.csv"))
    projekt = w._projekt_speichern(str(tmp_path / "a.json"))
    kittel = w._export_kittel(str(tmp_path / "a_kittel"))
    for pfad in (xlsx, csv, bild, matrix, projekt, *kittel):
        assert pfad and os.path.exists(pfad)
    import pandas as pd
    blaetter = pd.read_excel(xlsx, sheet_name=None)
    assert {"Einzelfits", "Global", "Einstellungen", "Zonen_Geraden", "Ausreisser"} <= set(blaetter)
    assert "mu0_dH_mT" in blaetter["Einzelfits"].columns
    assert any(str(g).startswith("llg_mu0Hinh_mT") for g in blaetter["Global"]["Groesse"])
    w.close()


def test_verarbeitung_panel_exklusiv_kette_setzen_und_ruhige_spinbox(app):
    from polderfit.gui.verarbeitung_panel import VerarbeitungPanel
    from polderfit.gui.widgets import RuhigeSpinBox
    VerarbeitungPanel.VERZOEGERUNG_MS = 0
    meldungen = []
    panel = VerarbeitungPanel(geaendert=lambda k, m: meldungen.append(k),
                              farbskala_geaendert=lambda n: meldungen.append(("cmap", n)))
    panel.grp_rel.setChecked(True)
    aktive = [s.operation for s in meldungen[-1].aktive_schritte()]
    assert aktive == ["relation_amplitude"]
    assert not panel.grp_dd.isChecked() and not panel.grp_divide.isChecked()
    # Kette setzen (z. B. aus Voreinstellungen): mehrere aktive -> nur die erste bleibt.
    kette = Verarbeitungskette.standard()
    kette.schritte[0].aktiv = True
    kette.schritte[1].aktiv = True
    panel.setze_kette(kette, melden=True)
    assert [s.operation for s in meldungen[-1].aktive_schritte()] == ["divide_slice"]
    panel.farbskala_combo.setCurrentIndex(panel.farbskala_combo.findData("gray"))
    assert ("cmap", "gray") in meldungen
    # Alle Optionen tragen Tooltips (Hover-Erklaerung).
    for widget in (panel.grp_divide, panel.grp_dd, panel.grp_rel, panel.dd_delta,
                   panel.rel_delta, panel.divide_index, panel.anzeige_combo,
                   panel.farbskala_combo, panel.dd_mitteln, panel.btn_roh):
        assert widget.toolTip()
    # Mausrad ohne Fokus aendert den Wert nicht.
    assert isinstance(panel.dd_delta, RuhigeSpinBox)
    panel.show()
    panel.dd_delta.clearFocus()
    vorher = panel.dd_delta.value()
    from PySide6 import QtGui
    ereignis = QtGui.QWheelEvent(QtCore.QPointF(5, 5), QtCore.QPointF(5, 5), QtCore.QPoint(0, 0),
                                 QtCore.QPoint(0, 120), QtCore.Qt.NoButton, QtCore.Qt.NoModifier,
                                 QtCore.Qt.NoScrollPhase, False)
    app.sendEvent(panel.dd_delta, ereignis)
    assert panel.dd_delta.value() == vorher
    panel.close()


def test_bereichsfit_dialog_frequenz_und_feld_von_bis(app):
    from polderfit.gui.bereichsfit_dialog import BereichsFitDialog
    dlg = BereichsFitDialog(0.6, 0.8, 12.0, 18.0, daten_bereich=(0.5, 1.0, 10.0, 24.0), n_moden=2)
    assert dlg.frequenz_bereich() == (12e9, 18e9) and dlg.feld_bereich() == (0.6, 0.8)
    assert dlg.n_moden() == 2
    dlg.f_von.setValue(20.0)
    dlg.f_bis.setValue(14.0)
    assert dlg.frequenz_bereich() == (14e9, 20e9)        # sortiert
    dlg.b_bis.setValue(0.9)
    assert dlg.feld_bereich() == (0.6, 0.9)


def test_parameter_dialog_neue_felder(app):
    from polderfit.gui.parameter_dialog import ParameterDialog, PhysikParameter as P
    start = P(n_moden=3, alpha_plausibel=0.25, nachfit_bestaetigen=False)
    dlg = ParameterDialog(start)
    assert dlg.parameter() == start
    assert not hasattr(dlg, "alpha_spin")               # "erwartetes alpha" nicht mehr abgefragt
    dlg.moden_spin.setValue(1)
    dlg.alpha_plausibel_spin.setValue(0.0)
    dlg.chk_bestaetigen.setChecked(True)
    p = dlg.parameter()
    assert p.n_moden == 1 and p.alpha_plausibel == 0.0 and p.alpha_plausibel_wirksam is None
    assert p.nachfit_bestaetigen
    dlg._standardwerte()
    assert dlg.parameter() == P()


def test_export_dialoge(app):
    from polderfit.gui.export_dialog import AllesSpeichernDialog, SpaltenDialog
    from polderfit.persistenz.ergebnis_export import SPALTEN_GRUPPEN
    d = AllesSpeichernDialog("/tmp", "probe", hat_fits=False, hat_daten=True)
    wahl = d.auswahl()
    assert wahl["basis"] == "probe" and "projekt" not in wahl["teile"]   # braucht Fits
    assert "farbplot" in wahl["teile"]
    s = SpaltenDialog({"spalten": ["kern"], "csv_deutsch": True})
    e = s.einstellungen()
    assert e["spalten"] == ["kern"] and e["csv_deutsch"] is True
    for box in s._boxen.values():
        box.setChecked(True)
    assert s.einstellungen()["spalten"] == []           # alle = leere Liste
    assert set(s._boxen) == set(SPALTEN_GRUPPEN)


def test_fit_ansicht_mit_moden_und_status(app):
    from polderfit.gui.fit_ansicht import FitAnsicht
    ls = _synth_linescan(20e9, [(0.735, 0.012, 3e-6, 0.4), (0.765, 0.010, 2e-6, 0.9)])
    e = fitte_linescan(ls, GAMMA_STANDARD, n_moden=2)
    fa = FitAnsicht()
    fa.zeige(ls, 0.6, 0.9, e, status="bestaetigt")
    assert "2 Moden" in fa.ax_re.get_title() and "mT" in fa.ax_re.get_title()
    labels = [ln.get_label() for ln in fa.ax_re.lines]
    assert any(l.startswith("Mode 1") for l in labels) and "Mode 2" in labels
    fa.zeige(ls, 0.6, 0.9, FitErgebnis.platzhalter(20e9, ls.feld))
    assert "nicht gefittet" in fa.ax_re.get_title()


# ---------------------------------------------------------------------------
# Sofortige Rueckmeldung bei Hintergrund-Jobs: Statusleiste, Live-Vorschau, Abbrechen
# ---------------------------------------------------------------------------
def test_fitte_alle_abbruch_und_fensterfortschritt():
    ds = _synth_datensatz(6)
    zaehler = {"fenster": 0, "fits": 0}

    def fortschritt_fenster(k, n):
        zaehler["fenster"] = max(zaehler["fenster"], k)
        assert n == 6

    def abbruch():
        return zaehler["fits"] >= 2

    def fortschritt(i, n, erg):
        zaehler["fits"] += 1

    st = fitte_alle(ds, nachfenster_faktor=0.0, fortschritt=fortschritt,
                    fortschritt_fenster=fortschritt_fenster, abbruch=abbruch)
    assert zaehler["fenster"] == 6                      # Phase 1 meldet jeden Linescan
    assert len(st.ergebnisse) == 6 and st.index_gefittet() == [0, 1]
    assert all(not e.gefittet for e in st.ergebnisse[2:])
    # Grenzgeraden-Fit bricht ebenfalls geordnet ab.
    st2 = leerer_stapel(ds, nachfenster_faktor=0.0)
    g = Grenzgerade(b1=0.56, f1=5e9, b2=0.56, f2=30e9, gruen_positiv=False)
    if (g.erlaubtes_intervall(10e9, 0.55, 0.95) or (0, 0))[1] < 0.9:
        g.seite_wechseln()
    n_fits = {"k": 0}

    def fortschritt2(k, n, erg):
        n_fits["k"] = k

    neu, uebersprungen = fitte_geraden_bereich(st2, [g], fortschritt=fortschritt2,
                                               abbruch=lambda: n_fits["k"] >= 3)
    assert len(neu) == 3 and len(uebersprungen) == 3


def test_hauptfenster_job_rueckmeldung_live_und_abbruch(app, monkeypatch, tmp_path):
    monkeypatch.setenv("POLDERFIT_KONFIG", str(tmp_path / "konfig"))
    from polderfit.gui.hauptfenster import Hauptfenster
    w = Hauptfenster()
    ds = _synth_datensatz(6)
    w._datensatz_uebernehmen(ds)
    gesehen = {}

    def aufgabe(melde):
        melde(0, 0, "", phase="Fenstersuche")
        for k in range(6):
            melde(k + 1, 6, "", phase="Einzelfits",
                  daten=(ds.frequenzen[k], 0.62 + 0.02 * k, "gut"))
            if melde.abgebrochen():
                return f"abgebrochen bei {k + 1}"
            _pumpe(120)
        return "fertig"

    def bei_fertig(res):
        gesehen["res"] = res

    w._starte_job(aufgabe, bei_fertig, "Testfit läuft …", abbrechbar=True, live="neu")
    # Sofort sichtbar: Statusleiste, Banner, Wartecursor, Abbrechen-Knopf.
    assert w.status_job.isVisibleTo(w) and w.status_fortschritt.isVisibleTo(w)
    assert w.btn_abbrechen.isVisibleTo(w) and w.btn_abbrechen.isEnabled()
    assert w.matrix._hinweis_text and "Testfit" in w.matrix._hinweis_text
    assert QtWidgets.QApplication.overrideCursor() is not None
    _pumpe(500)
    # Waehrend des Jobs wird NICHT gezeichnet (GIL-Konkurrenz), nur vorgemerkt.
    assert len(w._live) >= 1 and w.matrix._res_freq.size == 0
    assert "Einzelfits" in w.status_job.text() and "%" in w.status_job.text()
    w._job_abbrechen()
    assert not w.btn_abbrechen.isEnabled()
    _pumpe(2500)
    assert gesehen["res"].startswith("abgebrochen")
    assert w._job_laeuft is False
    assert not w.status_job.isVisibleTo(w) and w.matrix._hinweis_text is None
    assert QtWidgets.QApplication.overrideCursor() is None
    # Nicht abbrechbarer Job zeigt keinen Abbrechen-Knopf, aber Spinner/Status.
    w._starte_job(lambda melde: (melde(0, 0, "", phase="TDMS lesen"), "x")[1],
                  lambda r: None, "Lade …", abbrechbar=False)
    assert w.status_spinner.isVisibleTo(w) and not w.btn_abbrechen.isVisibleTo(w)
    _pumpe(800)
    assert w._job_laeuft is False
    w.close()


def test_matrix_hinweis_banner(app):
    from polderfit.gui.matrix_ansicht import MatrixAnsicht
    m = MatrixAnsicht()
    m.zeige(_mini_datensatz(5))
    m.zeige_hinweis("Auto-Fit läuft … 3/5")
    assert m._hinweis_artist is not None
    m.setze_verarbeitung(Verarbeitungskette.standard(), "betrag")   # Neuzeichnen behaelt Banner
    assert m._hinweis_artist is not None and m._hinweis_text == "Auto-Fit läuft … 3/5"
    m.zeige_hinweis(None)
    assert m._hinweis_artist is None


def test_zweistufiger_autofit_ergaenzt_moden():
    """Zweistufig: klassischer Ein-Moden-Fit, dann zweite Resonanz aus dem Residuum."""
    ds = _synth_datensatz(zwei_moden=True)
    st = fitte_alle(ds, nachfenster_faktor=0.0, n_moden=2, zweistufig=True)
    assert st.zweistufig and st.n_moden == 2
    ergaenzt = [e for e in st.ergebnisse if e.moden and len(e.moden) == 2]
    assert len(ergaenzt) >= 6
    for k, e in enumerate(st.ergebnisse):
        b = 0.62 + 0.02 * k
        if e.moden and len(e.moden) == 2:
            b1, b2 = sorted(m["B_res"] for m in e.moden)
            assert abs(b1 - b) < 0.004 and abs(b2 - (b + 0.035)) < 0.004
        else:
            assert abs(e.B_res - b) < 0.004


def test_zweistufiger_autofit_ohne_zweite_mode_bleibt_klassisch():
    """Ein-Moden-Daten: keine Phantom-Resonanzen, Hauptmode wie im klassischen Fit."""
    ds = _synth_datensatz(zwei_moden=False)
    st = fitte_alle(ds, nachfenster_faktor=0.0, n_moden=2, zweistufig=True)
    klassisch = fitte_alle(ds, nachfenster_faktor=0.0, n_moden=1)
    assert sum(e.problematisch for e in st.ergebnisse) <= sum(e.problematisch for e in klassisch.ergebnisse)
    for e, k in zip(st.ergebnisse, klassisch.ergebnisse):
        assert abs(e.B_res - k.B_res) < 0.002


def test_ergaenze_moden_laesst_klassisch_bei_platzhalter():
    from polderfit.fit.batch import ergaenze_moden, leerer_stapel
    ds = _synth_datensatz(zwei_moden=True)
    st = leerer_stapel(ds, n_moden=2)
    vorher = st.ergebnisse[0]
    assert ergaenze_moden(st, 0, 2) is vorher          # nicht gefittet -> unveraendert


def _band_geraden(b0, steigung, halbbreite, mode, f_lo=10e9, f_hi=24e9):
    """Zwei Geraden parallel zur Dispersion b(f) = b0 + steigung*(f - f_lo); gruen dazwischen."""
    from polderfit.fit.fenster_steuerung import Grenzgerade
    f_mitte = 0.5 * (f_lo + f_hi)
    b_mitte = b0 + steigung * (f_mitte - f_lo)
    geraden = []
    for vorz in (-1.0, +1.0):
        g = Grenzgerade(b1=b0 + vorz * halbbreite, f1=f_lo,
                        b2=b0 + steigung * (f_hi - f_lo) + vorz * halbbreite, f2=f_hi, mode=mode)
        iv = g.erlaubtes_intervall(f_mitte, 0.0, 2.0)
        if iv is None or not (iv[0] <= b_mitte <= iv[1]):
            g.seite_wechseln()
        geraden.append(g)
    return geraden


def test_grenzgeraden_baender_je_mode():
    """n Resonanzen = 2n Geraden: Mode k wird nur in ihrem Band gesucht."""
    from polderfit.fit.batch import leerer_stapel
    from polderfit.fit.fenster_steuerung import fitte_geraden_bereich
    ds = _synth_datensatz(zwei_moden=True)          # b = 0.62 + 0.02 k, Nebenmode +0.035
    steig = 0.02 / 2e9
    geraden = _band_geraden(0.62, steig, 0.012, 1) + _band_geraden(0.655, steig, 0.012, 2)
    st = leerer_stapel(ds, n_moden=2)
    neu, ueb = fitte_geraden_bereich(st, geraden)
    assert len(neu) == 8 and ueb == []
    assert sum(e.problematisch for e in st.ergebnisse) <= 1
    for k, e in enumerate(st.ergebnisse):
        b = 0.62 + 0.02 * k
        assert len(e.moden) == 2
        b1, b2 = sorted(m["B_res"] for m in e.moden)
        assert abs(b1 - b) < 0.004 and abs(b2 - (b + 0.035)) < 0.004
        lo, hi = st.fenster[k]
        assert lo < b - 0.012 and hi > b + 0.035 + 0.012          # Huelle + Rand


def test_grenzgeraden_band_leer_wird_uebersprungen():
    from polderfit.fit.batch import leerer_stapel
    from polderfit.fit.fenster_steuerung import fitte_geraden_bereich
    ds = _synth_datensatz(zwei_moden=True)
    steig = 0.02 / 2e9
    # Mode-2-Band ausserhalb des Feldbereichs (B nur 0.55-0.95 T) -> leer -> alle uebersprungen
    geraden = _band_geraden(0.62, steig, 0.012, 1) + _band_geraden(1.5, steig, 0.012, 2)
    st = leerer_stapel(ds, n_moden=2)
    neu, ueb = fitte_geraden_bereich(st, geraden)
    assert neu == [] and len(ueb) == 8


def test_sukzessive_baender_modenzahl_aus_baendern():
    """Sukzessives Vorgehen (Nutzerwunsch): Band 1 allein wird als Ein-Moden-Fit
    gerechnet (``n_moden=1`` trotz Stapel-Einstellung 2); mit Band 2 werden
    beide Moden GLEICHZEITIG gefittet (Ueberlagerung beruecksichtigt), jede in
    ihrem Band. Die Stapel-Einstellung bleibt die Obergrenze."""
    from polderfit.fit.batch import leerer_stapel
    from polderfit.fit.fenster_steuerung import fitte_geraden_bereich, zaehle_abgedeckt
    ds = _synth_datensatz(zwei_moden=True)          # b = 0.62 + 0.02 k, Nebenmode +0.035
    steig = 0.02 / 2e9
    band1 = _band_geraden(0.62, steig, 0.012, 1)
    st = leerer_stapel(ds, n_moden=2)
    assert zaehle_abgedeckt(st, band1, n_moden=1) == 8
    neu, ueb = fitte_geraden_bereich(st, band1, n_moden=1)
    assert len(neu) == 8 and ueb == []
    assert st.n_moden == 2                           # Einstellung unveraendert
    for k, e in enumerate(st.ergebnisse):
        assert len(e.moden) == 1 and abs(e.B_res - (0.62 + 0.02 * k)) < 0.004
    band2 = _band_geraden(0.655, steig, 0.012, 2)
    neu, ueb = fitte_geraden_bereich(st, band1 + band2, n_moden=2)
    assert len(neu) == 8 and ueb == []
    for k, e in enumerate(st.ergebnisse):
        assert len(e.moden) == 2
        b1, b2 = sorted(m["B_res"] for m in e.moden)
        assert abs(b1 - (0.62 + 0.02 * k)) < 0.004 and abs(b2 - (0.655 + 0.02 * k)) < 0.004


def test_grenzgerade_mode_persistenz():
    from dataclasses import asdict
    from polderfit.fit.fenster_steuerung import Grenzgerade
    from polderfit.persistenz.projekt import grenzgeraden_aus_sitzung
    g = Grenzgerade(b1=1.0, f1=1e9, b2=2.0, f2=2e9, mode=2)
    [zurueck] = grenzgeraden_aus_sitzung({"grenzgeraden": [asdict(g)]})
    assert zurueck.mode == 2
    [alt] = grenzgeraden_aus_sitzung({"grenzgeraden": [{"b1": 1, "f1": 1e9, "b2": 2, "f2": 2e9}]})
    assert alt.mode == 1


def test_band_geraden_und_abdeckung():
    from polderfit.fit.batch import leerer_stapel
    from polderfit.fit.fenster_steuerung import band_geraden, zaehle_abgedeckt
    ds = _synth_datensatz(zwei_moden=True)
    g = band_geraden(0.62, 10e9, 0.76, 24e9, 0.012, mode=2)
    assert len(g) == 2 and all(x.mode == 2 for x in g)
    iv = g[0].erlaubtes_intervall(17e9, 0.0, 2.0)
    iv = g[1].erlaubtes_intervall(17e9, iv[0], iv[1])
    assert iv is not None and abs(iv[0] - 0.678) < 1e-9 and abs(iv[1] - 0.702) < 1e-9
    st = leerer_stapel(ds, n_moden=2)
    assert zaehle_abgedeckt(st, band_geraden(0.62, 10e9, 0.76, 24e9, 0.012, 1) + g) == 8
    a, b = band_geraden(0.62, 10e9, 0.76, 24e9, 0.012, 1)
    a.seite_wechseln()
    b.seite_wechseln()                     # gruen jeweils nach aussen -> leer
    assert zaehle_abgedeckt(st, [a, b]) == 0
    with pytest.raises(ValueError):
        band_geraden(0.6, 10e9, 0.7, 10e9, 0.01)

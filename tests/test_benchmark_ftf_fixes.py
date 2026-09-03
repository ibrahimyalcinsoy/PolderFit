# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Tests zu den Befunden des FTF-Benchmarks (LabVIEW-Vergleich, Aug. 2026).

1. Zweiter Fit-Durchgang (``nachfenster``): Fitfenster ``B_res +/- k*dH`` macht
   die Linienbreite fensterunabhaengig (auf breiten Fenstern mit gekruemmtem
   Untergrund kam sie systematisch zu klein heraus).
2. alpha-Obergrenze als Parameter: sehr breite Resonanzen (alpha ~ 0.3) sind
   mit angehobener Schranke fitbar; mit Standardschranke wird geklemmt und
   das Ergebnis korrekt als problematisch gemeldet.
3. Kittel-ip: Entartung ``(Meff, Hu) -> (-Meff, Hu+Meff)`` – der Fit liefert
   immer den Ast ``Meff >= 0`` und endliche Unsicherheiten (auch mit Schranken).
4. Persistenz und Parameterdialog kennen ``alpha_max``/``nachfenster_faktor``.
"""

import os

import numpy as np
import pytest

from polderfit.io.datensatz import Linescan, Messdatensatz
from polderfit.physik.konstanten import GAMMA_STANDARD, gamma_aus_g
from polderfit.physik.fitmodell import s21_modell
from polderfit.physik.kittel_llg import fit_kittel_ip, kittel_ip
from polderfit.fit.linescan_fit import fitte_linescan
from polderfit.fit.batch import (
    NACHFENSTER_FAKTOR_STANDARD, StapelErgebnis, fitte_alle, fitte_mit_nachfenster,
    nachfenster,
)
from polderfit.fit.kriterien import ALPHA_MAX, alpha_plausibel_max


def _linescan(frequenz, B_res, alpha, A=0.01, phi=0.6, halbbreite=0.3, n=400,
              kruemmung=0.0, rausch=0.0, seed=0):
    """Synthetischer Linescan; ``kruemmung`` fuegt einen quadratischen
    Untergrund hinzu (nicht im linearen Fitmodell enthalten)."""
    gamma = GAMMA_STANDARD
    omega = 2 * np.pi * frequenz
    B = np.linspace(B_res - halbbreite, B_res + halbbreite, n)
    B_ref = float(B.mean())
    s = s21_modell(B, B_res, alpha, A, phi, 0.02, -0.01, 0.05, 0.03, omega, gamma, B_ref)
    chi_teil = s21_modell(B, B_res, alpha, A, phi, 0.0, 0.0, 0.0, 0.0, omega, gamma, B_ref)
    hub = float(np.abs(chi_teil - chi_teil.mean()).max())
    if kruemmung:
        s = s + kruemmung * hub * ((B - B_ref) / halbbreite) ** 2 * (1.0 + 0.5j)
    if rausch > 0:
        rng = np.random.default_rng(seed)
        s = s + rausch * hub * (rng.standard_normal(B.size) + 1j * rng.standard_normal(B.size))
    return Linescan(frequenz=frequenz, feld=B, re=s.real, im=s.imag)


# ---------------------------------------------------------------------------
# 1. Zweiter Fit-Durchgang
# ---------------------------------------------------------------------------
def test_nachfenster_verengt_um_erstes_ergebnis():
    ls = _linescan(20e9, 1.0, 5e-3)
    erg = fitte_linescan(ls)
    assert not erg.problematisch
    voll = (float(ls.feld.min()), float(ls.feld.max()))
    eng = nachfenster(ls, erg, voll, 2.5)
    assert eng is not None
    lo, hi = eng
    assert lo > voll[0] and hi < voll[1]
    assert np.isclose(0.5 * (lo + hi), erg.B_res, atol=1e-6)
    assert np.isclose(hi - lo, 2 * 2.5 * erg.dH, rtol=1e-6)


def test_nachfenster_aus_bei_faktor_null_oder_problemfit():
    ls = _linescan(20e9, 1.0, 5e-3)
    erg = fitte_linescan(ls)
    voll = (float(ls.feld.min()), float(ls.feld.max()))
    assert nachfenster(ls, erg, voll, 0.0) is None
    erg.problematisch = True
    assert nachfenster(ls, erg, voll, 2.5) is None


def test_nachfenster_erweitert_nie_und_haelt_mindestpunkte():
    ls = _linescan(20e9, 1.0, 5e-3, n=40)          # grob abgetastet
    erg = fitte_linescan(ls)
    # Bereits enges Fenster: kein zweiter Durchgang.
    schmal = (erg.B_res - 0.5 * erg.dH, erg.B_res + 0.5 * erg.dH)
    assert nachfenster(ls, erg, schmal, 2.5) is None
    voll = (float(ls.feld.min()), float(ls.feld.max()))
    eng = nachfenster(ls, erg, voll, 2.5)
    if eng is not None:
        n_pkt = int(np.count_nonzero((ls.feld >= eng[0]) & (ls.feld <= eng[1])))
        assert n_pkt >= 12


def test_zweiter_durchgang_macht_linienbreite_fensterunabhaengig():
    """Gekruemmter Untergrund auf breitem Fenster verfaelscht dH im ersten
    Durchgang; der Nachfit auf +/-2.5 dH trifft die Wahrheit deutlich besser."""
    alpha_wahr = 5e-3
    # Etwas Rauschen, damit der (bewusst falsche) breite Fit nicht ueber das
    # Chi2-Sicherheitsnetz als problematisch aussortiert wird.
    ls = _linescan(20e9, 1.0, alpha_wahr, halbbreite=0.3, kruemmung=0.6,
                   rausch=0.01, seed=5)
    voll = (float(ls.feld.min()), float(ls.feld.max()))
    einmal, _, _ = fitte_mit_nachfenster(ls, voll, GAMMA_STANDARD, nachfenster_faktor=0.0)
    zweimal, _, fenster = fitte_mit_nachfenster(ls, voll, GAMMA_STANDARD,
                                                nachfenster_faktor=2.5)
    fehler_einmal = abs(einmal.alpha - alpha_wahr) / alpha_wahr
    fehler_zweimal = abs(zweimal.alpha - alpha_wahr) / alpha_wahr
    assert fehler_einmal > 0.05          # der breite Fit ist merklich verzerrt
    assert fehler_zweimal < 0.02         # der Nachfit nicht
    assert fehler_zweimal < fehler_einmal
    assert fenster[1] - fenster[0] < voll[1] - voll[0]


def test_fitte_alle_uebernimmt_nachfenster_und_bleibt_bei_problemfits():
    # Fein genug abgetastet (>= 8 Punkte je Linienbreite), leicht verrauscht.
    linescans = [_linescan(f, 0.9 + (f - 10e9) / 1e9 * 0.036, 5e-3, halbbreite=0.15,
                           n=600, rausch=0.005, seed=int(f / 1e9))
                 for f in np.linspace(10e9, 20e9, 6)]
    ds = Messdatensatz(quelle="synth", format_typ="sortiert", linescans=linescans)
    st1 = fitte_alle(ds, nachfenster_faktor=0.0)
    st2 = fitte_alle(ds)                                # Standard: 2. Durchgang an
    assert st2.nachfenster_faktor == NACHFENSTER_FAKTOR_STANDARD
    assert st2.alpha_max == ALPHA_MAX
    for (u1, o1), (u2, o2), e2 in zip(st1.fenster, st2.fenster, st2.ergebnisse):
        assert o2 - u2 <= o1 - u1 + 1e-12
        assert not e2.problematisch
        assert u2 <= e2.B_res <= o2
        # Fensterangaben im Ergebnis liegen im verwendeten Fenster (Punktbereich).
        assert u2 <= e2.B_fenster_min + 1e-12 and e2.B_fenster_max <= o2 + 1e-12
        assert np.isclose(e2.alpha, 5e-3, rtol=0.05)


# ---------------------------------------------------------------------------
# 2. alpha-Obergrenze
# ---------------------------------------------------------------------------
def test_alpha_obergrenze_klemmt_und_meldet_bei_breiter_resonanz():
    ls = _linescan(20e9, 2.0, 0.3, halbbreite=2.0, n=800)   # sehr breit (FeCr2S4-artig)
    erg = fitte_linescan(ls)                                # Standard alpha_max=0.1
    assert erg.alpha <= ALPHA_MAX + 1e-12
    assert erg.problematisch
    assert any("alpha" in g for g in erg.problem_gruende)


def test_alpha_obergrenze_anhebbar_liefert_wahren_wert():
    ls = _linescan(20e9, 2.0, 0.3, halbbreite=2.0, n=800)
    erg = fitte_linescan(ls, alpha_max=1.0)
    assert erg.erfolg
    assert np.isclose(erg.alpha, 0.3, rtol=0.02)
    assert np.isclose(erg.B_res, 2.0, atol=2e-3)
    # Plausibilitaetsgrenze wandert mit (halbe Schranke): 0.3 < 0.5 -> nicht
    # als "alpha unphysikalisch" markiert.
    assert alpha_plausibel_max(1.0) == pytest.approx(0.5)
    assert "alpha unphysikalisch" not in erg.problem_gruende
    assert "alpha an Grenze" not in erg.problem_gruende


def test_alpha_obergrenze_wirkt_in_fitte_alle_und_fitte_neu():
    from polderfit.fit.batch import fitte_neu
    ls = _linescan(20e9, 2.0, 0.3, halbbreite=2.0, n=800)
    ds = Messdatensatz(quelle="synth", format_typ="sortiert", linescans=[ls])
    # Fenster vorgeben (die Automatik ist fuer Linien breiter als ~0.4 T
    # Halbbreite nicht ausgelegt – siehe Benchmark-Bericht, FeCr2S4).
    st = fitte_alle(ds, alpha_max=1.0, nachfenster_faktor=0.0,
                    zentren=np.array([2.0]), alpha_erwartet=0.3)
    assert st.alpha_max == 1.0
    # fitte_neu nutzt die im Stapel hinterlegte Schranke.
    erg = fitte_neu(st, 0, feld_unten=0.5, feld_oben=3.5)
    assert np.isclose(erg.alpha, 0.3, rtol=0.03)
    st.alpha_max = ALPHA_MAX
    erg2 = fitte_neu(st, 0)
    assert erg2.alpha <= ALPHA_MAX + 1e-12
    # Kriterien melden "alpha an Grenze"; ein Nachfit wird standardmaessig von
    # den Kriterien bewertet (nicht automatisch bestaetigt, P1-4).
    assert erg2.problematisch_auto and "alpha an Grenze" in erg2.problem_gruende
    assert erg2.bewertung == "auto" and erg2.problematisch
    erg3 = fitte_neu(st, 0, bestaetigen=True)
    assert not erg3.problematisch and erg3.bewertung == "bestaetigt"


# ---------------------------------------------------------------------------
# 3. Kittel-ip: Ast Meff >= 0, endliche Unsicherheiten
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("meff,hu", [(0.13, -0.0045), (2.25, 0.003), (0.05, 0.02)])
def test_kittel_ip_liefert_positiven_ast_mit_unsicherheiten(meff, hu):
    f = np.linspace(5e9, 50e9, 60)
    g_wahr = 2.08
    rng = np.random.default_rng(3)
    b = kittel_ip(f, meff, hu, gamma_aus_g(g_wahr)) + rng.normal(0, 3e-4, f.size)
    # Die Entartung ist exakt: gespiegelter Parametersatz -> identische Kurve.
    assert np.allclose(kittel_ip(f, meff, hu, gamma_aus_g(g_wahr)),
                       kittel_ip(f, -meff, hu + meff, gamma_aus_g(g_wahr)))
    r = fit_kittel_ip(f, b)
    assert r["mu0Meff"] >= 0.0
    assert np.isclose(r["mu0Meff"], meff, atol=0.01)
    assert np.isclose(r["mu0Hu"], hu, atol=2e-3)
    assert np.isclose(r["g_faktor"], g_wahr, atol=5e-3)
    for k in ("mu0Meff_err", "mu0Hu_err", "g_faktor_err", "gamma_err"):
        assert np.isfinite(r[k]) and r[k] > 0.0
    # gewichtet ebenso
    rw = fit_kittel_ip(f, b, B_res_err=np.full(f.size, 3e-4))
    assert rw["mu0Meff"] >= 0.0 and rw["g_faktor_err"] > 0.0


# ---------------------------------------------------------------------------
# 4. Persistenz + Dialog
# ---------------------------------------------------------------------------
def test_persistenz_alpha_max_und_nachfenster(tmp_path):
    from polderfit.persistenz.projekt import (
        lade_sitzung, speichere_sitzung, stelle_stapel_wieder_her,
    )
    ls = _linescan(20e9, 2.0, 0.3, halbbreite=2.0, n=400)
    ds = Messdatensatz(quelle="synth", format_typ="sortiert", linescans=[ls])
    st = fitte_alle(ds, alpha_max=1.0, nachfenster_faktor=3.0)
    pfad = tmp_path / "sitzung.json"
    speichere_sitzung(st, str(pfad))
    daten = lade_sitzung(str(pfad))
    assert daten["alpha_max"] == 1.0 and daten["nachfenster_faktor"] == 3.0
    neu = stelle_stapel_wieder_her(daten, ds)
    assert neu.alpha_max == 1.0 and neu.nachfenster_faktor == 3.0
    assert np.isclose(neu.ergebnisse[0].alpha, st.ergebnisse[0].alpha, rtol=1e-6)
    # Alte Sitzungen ohne die Felder: Standardwerte.
    daten.pop("alpha_max"); daten.pop("nachfenster_faktor")
    alt = stelle_stapel_wieder_her(daten, ds)
    assert alt.alpha_max == ALPHA_MAX
    assert alt.nachfenster_faktor == NACHFENSTER_FAKTOR_STANDARD


@pytest.mark.skipif(os.environ.get("POLDERFIT_OHNE_GUI") == "1", reason="ohne GUI")
def test_dialog_kennt_neue_parameter():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets
    from polderfit.gui.parameter_dialog import ParameterDialog, PhysikParameter
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    start = PhysikParameter(alpha_max=0.8, nachfenster_faktor=0.0)
    dlg = ParameterDialog(start)
    assert dlg.parameter() == start
    dlg.alpha_max_spin.setValue(0.5)
    dlg.nachfenster_spin.setValue(3.0)
    p = dlg.parameter()
    assert p.alpha_max == pytest.approx(0.5) and p.nachfenster_faktor == pytest.approx(3.0)
    assert "α max 0.5" in p.beschreibung()
    dlg._standardwerte()
    assert dlg.parameter() == PhysikParameter()

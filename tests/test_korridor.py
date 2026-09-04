# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Korridor-Konzept: Datenmodell, Einzelfit je Mode im Korridor, Persistenz."""

import numpy as np
import pytest

from polderfit.fit.korridor import Anker, Korridor, korridor_aus_linie, korridore_aus_grenzgeraden


def test_korridor_interpolation_und_fortsetzung():
    k = korridor_aus_linie(1, 2.0, 10e9, 3.0, 20e9, 0.05)
    assert k.grenzen(15e9) == pytest.approx((2.45, 2.55))
    assert k.grenzen(25e9) == pytest.approx((3.45, 3.55))   # linear fortgesetzt
    k.anker_setzen(15e9, 2.40, 2.60)
    assert len(k.anker) == 3 and k.grenzen(15e9) == pytest.approx((2.40, 2.60))
    k.anker_setzen(15e9 + 1.0, 2.41, 2.59, toleranz_hz=10.0)   # ersetzt statt anhaengen
    assert len(k.anker) == 3
    k.anker_verschieben(0, "rechts", 1.9)   # Grenzen sortiert, nie gekreuzt
    assert k.anker[0].b_links <= k.anker[0].b_rechts
    assert Korridor.aus_dict(k.als_dict()).grenzen(12.5e9) == k.grenzen(12.5e9)


def test_migration_aus_grenzgeraden_paaren():
    geraden = [{"b1": 2.0, "f1": 10e9, "b2": 3.0, "f2": 20e9, "gruen_positiv": True, "mode": 2},
               {"b1": 2.1, "f1": 10e9, "b2": 3.1, "f2": 20e9, "gruen_positiv": False, "mode": 2}]
    korridore = korridore_aus_grenzgeraden(geraden, 0.0, 5.0)
    assert [k.mode for k in korridore] == [1]
    assert korridore[0].grenzen(15e9) == pytest.approx((2.5, 2.6))


def test_einzelfit_je_mode_im_korridor(synthetischer_datensatz):
    from polderfit.fit.batch import fitte_alle
    from polderfit.fit.fenster_steuerung import fitte_korridor, zaehle_korridor
    d = synthetischer_datensatz
    st = fitte_alle(d)
    f = d.frequenzen
    b = np.array([e.B_res for e in st.ergebnisse])
    k2 = Korridor(mode=2, anker=[Anker(f[0], b[0] - 0.03, b[0] + 0.03),
                                 Anker(f[-1], b[-1] - 0.03, b[-1] + 0.03)])
    assert zaehle_korridor(st, k2) == len(f)
    neu, ueber = fitte_korridor(st, k2, schritt=2)
    assert len(neu) == (len(f) + 1) // 2 and st.moden_vorhanden() == [1, 2]
    l2 = st.ergebnisse_mode(2)
    for i in neu:
        assert l2[i].gefittet and l2[i].mode == 2
        lo, hi = k2.grenzen(f[i])
        assert lo <= l2[i].B_res <= hi          # nur Punkte im Korridor
        assert np.all((l2[i].feld >= lo - 1e-9) & (l2[i].feld <= hi + 1e-9))
    # Mode 1 bleibt unangetastet
    assert np.allclose([e.B_res for e in st.ergebnisse], b)


def test_projekt_rundlauf_mit_nebenmoden(synthetischer_datensatz, tmp_path):
    from polderfit.fit.batch import fitte_alle
    from polderfit.fit.fenster_steuerung import fitte_korridor
    from polderfit.persistenz.projekt import (korridore_aus_sitzung, lade_sitzung,
                                              speichere_sitzung, stelle_stapel_wieder_her)
    d = synthetischer_datensatz
    st = fitte_alle(d)
    f = d.frequenzen
    b = np.array([e.B_res for e in st.ergebnisse])
    k2 = Korridor(mode=2, anker=[Anker(f[0], b[0] - 0.03, b[0] + 0.03),
                                 Anker(f[-1], b[-1] - 0.03, b[-1] + 0.03)])
    neu, _ = fitte_korridor(st, k2)
    pfad = tmp_path / "p.json"
    speichere_sitzung(st, str(pfad), korridore=[k2])
    daten = lade_sitzung(str(pfad))
    kk = korridore_aus_sitzung(daten, *d.feld_bereich())
    st2 = stelle_stapel_wieder_her(daten, d, korridore=kk)
    assert [k.mode for k in kk] == [2]
    for i in neu:
        assert st2.ergebnisse_mode(2)[i].B_res == pytest.approx(st.ergebnisse_mode(2)[i].B_res)


@pytest.mark.parametrize("methode", ["trennung", "summe"])
def test_zwei_dips_im_korridor_hard_crop(methode):
    from polderfit.fit.batch import leerer_stapel, fitte_mode
    from polderfit.io.datensatz import Linescan, Messdatensatz
    from polderfit.physik.fitmodell import s21_modell
    from polderfit.physik.konstanten import GAMMA_STANDARD as g
    B = np.linspace(1.0, 3.65, 2400)   # 1.1 mT Schritt, wie reale Linescans (~2.5 mT)
    linescans = []
    for f in np.linspace(6e9, 30e9, 6):
        w = 2 * np.pi * f
        b1 = 1.37 + w / g
        s = (s21_modell(B, b1, 6e-3, 0.02, 0.5, 0, 0, 0, 0, w, g, float(B.mean()))
             + s21_modell(B, b1 + 0.04, 6e-3, 0.015, 0.5, 0, 0, 0, 0, w, g, float(B.mean()))
             + 0.2 + 0.1j)
        linescans.append(Linescan(frequenz=float(f), feld=B.copy(), re=s.real, im=s.imag))
    d = Messdatensatz(quelle="synth2", format_typ="unsortiert", linescans=linescans)
    st = leerer_stapel(d)
    f = d.frequenzen
    k = Korridor(mode=1, n_dips=2, moden=[1, 2], methode=methode,
                 anker=[Anker(f[0], 1.37 + 2 * np.pi * f[0] / g - 0.03, 1.37 + 2 * np.pi * f[0] / g + 0.07),
                        Anker(f[-1], 1.37 + 2 * np.pi * f[-1] / g - 0.03, 1.37 + 2 * np.pi * f[-1] / g + 0.07)])
    for i in range(len(f)):
        fitte_mode(st, i, k)
    for i in range(len(f)):
        b1 = 1.37 + 2 * np.pi * f[i] / g
        e1, e2 = st.ergebnisse[i], st.ergebnisse_mode(2)[i]
        assert e1.gefittet and e2.gefittet
        assert abs(e1.B_res - b1) < 2e-3 and abs(e2.B_res - (b1 + 0.04)) < 2e-3
        assert not e1.problematisch and not e2.problematisch
        if methode == "trennung":
            assert e1.feld.max() <= e2.feld.min() + 1e-9  # harte Trennung, keine Ueberlappung
        else:
            assert e1.B_res < e2.B_res                        # Reihenfolge der Segmente
            assert e1.B_fenster_min == e2.B_fenster_min       # Kriterienfenster = ganzer Korridor
    assert st.moden_vorhanden() == [1, 2]


def test_manuelle_trennlinien_wandern_mit_der_mode():
    k = Korridor(mode=1, n_dips=2, moden=[1, 2],
                 anker=[Anker(10e9, 2.0, 2.2), Anker(20e9, 2.5, 2.7)])
    assert k.trennstellen(15e9) is None
    k.trenner_setzen(10e9, [2.12])                              # +20 mT rechts der Mitte
    assert k.trennstellen(15e9) == pytest.approx([2.37])        # wandert mit der Korridormitte
    k.trenner_setzen(20e9, [2.64])                              # +40 mT
    assert k.trennstellen(15e9) == pytest.approx([2.38])        # Abstand linear dazwischen
    assert k.trennstellen(25e9) == pytest.approx([2.90])        # linear fortgesetzt
    k2 = Korridor.aus_dict(k.als_dict())
    assert k2.trennstellen(15e9) == pytest.approx([2.38])
    assert k.trenner_entfernen(20e9) and k.trennstellen(15e9) == pytest.approx([2.37])
    from polderfit.fit.korridor import segmente_aus_trennern
    assert segmente_aus_trennern(2.0, 2.3, [2.1]) == [(2.0, 2.1), (2.1, 2.3)]


@pytest.mark.parametrize("methode", ["summe", "trennung"])
def test_drei_dips_im_korridor_iterativ(methode):
    """Drei nahe Dips (Abstaende 25/30 mT, dH ~6 mT, SNR ~ 20) in EINEM Korridor:
    Dip-Positionen durch sequentielles Abschaelen, alle drei Moden ohne Befund."""
    from polderfit.fit.batch import leerer_stapel, fitte_mode
    from polderfit.io.datensatz import Linescan, Messdatensatz
    from polderfit.physik.fitmodell import s21_modell
    from polderfit.physik.konstanten import GAMMA_STANDARD as g
    B = np.linspace(1.0, 3.65, 2400)
    rng = np.random.default_rng(3)
    for f in (10e9, 20e9, 30e9):
        w = 2 * np.pi * f
        b1 = 1.37 + w / g
        wahr = [b1, b1 + 0.025, b1 + 0.055]
        rein = sum(s21_modell(B, bk, 4e-3, A, 0.4, 0, 0, 0, 0, w, g, float(B.mean()))
                   for bk, A in zip(wahr, (0.02, 0.012, 0.015)))
        rausch = np.abs(rein).max() / 20.0
        s = rein + 0.2 + 0.1j + rausch * (rng.normal(size=B.size) + 1j * rng.normal(size=B.size))
        d = Messdatensatz(quelle="x", format_typ="unsortiert",
                          linescans=[Linescan(frequenz=f, feld=B, re=s.real, im=s.imag)])
        st = leerer_stapel(d)
        k = Korridor(mode=1, n_dips=3, moden=[1, 2, 3], methode=methode,
                     anker=[Anker(f, b1 - 0.03, b1 + 0.085)])
        fitte_mode(st, 0, k)
        for m, bw in zip((1, 2, 3), wahr):
            e = st.ergebnisse_mode(m)[0]
            assert e.gefittet and abs(e.B_res - bw) < 1.5e-3, (methode, f, m, e.B_res, bw)


def test_bic_waehlt_dipzahl_automatisch():
    """Option dips_auto: bei zwei echten Dips und Vorgabe max. 3 bleibt Mode 3
    Platzhalter; bei drei Dips werden alle drei gefittet."""
    from polderfit.fit.batch import leerer_stapel, fitte_mode
    from polderfit.io.datensatz import Linescan, Messdatensatz
    from polderfit.physik.fitmodell import s21_modell
    from polderfit.physik.konstanten import GAMMA_STANDARD as g
    B = np.linspace(1.0, 3.65, 2400)
    rng = np.random.default_rng(5)
    f = 20e9
    w = 2 * np.pi * f
    b1 = 1.37 + w / g
    for lagen in ([b1, b1 + 0.03], [b1, b1 + 0.025, b1 + 0.055]):
        rein = sum(s21_modell(B, bk, 4e-3, A, 0.4, 0, 0, 0, 0, w, g, float(B.mean()))
                   for bk, A in zip(lagen, (0.02, 0.012, 0.015)))
        rausch = np.abs(rein).max() / 20.0
        s = rein + 0.2 + 0.1j + rausch * (rng.normal(size=B.size) + 1j * rng.normal(size=B.size))
        d = Messdatensatz(quelle="x", format_typ="unsortiert",
                          linescans=[Linescan(frequenz=f, feld=B, re=s.real, im=s.imag)])
        st = leerer_stapel(d)
        k = Korridor(mode=1, n_dips=3, moden=[1, 2, 3], methode="summe", dips_auto=True,
                     anker=[Anker(f, b1 - 0.03, b1 + 0.085)])
        fitte_mode(st, 0, k)
        gefittet = [m for m in (1, 2, 3) if st.ergebnisse_mode(m)[0].gefittet]
        assert gefittet == list(range(1, len(lagen) + 1)), (len(lagen), gefittet)
        for m, bw in zip(gefittet, lagen):
            assert abs(st.ergebnisse_mode(m)[0].B_res - bw) < 1.5e-3
        assert "BIC" in st.ergebnisse[0].meldung

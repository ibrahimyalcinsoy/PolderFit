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

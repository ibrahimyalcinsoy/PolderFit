"""Tests der Auswertungsauswahl (Frequenz-/Feld-Jumper + Bereichseinschraenkung)."""

import numpy as np
import pytest

from bbfmr.fit import Auswertungsauswahl, fitte_alle, parse_bereiche
from bbfmr.io.datensatz import Linescan, Messdatensatz
from bbfmr.physik.konstanten import GAMMA_STANDARD
from bbfmr.physik.suszeptibilitaet import chi_oop


def _datensatz(n_freq=20, n_feld=60, f0=5e9, f1=24e9):
    freqs = np.linspace(f0, f1, n_freq)
    B = np.linspace(1.0, 3.0, n_feld)
    ls = [Linescan(frequenz=float(f), feld=B, re=np.cos(B * f / 1e9),
                   im=np.sin(B * f / 1e9), temperatur=np.full(n_feld, 5.0))
          for f in freqs]
    return Messdatensatz(quelle="t", format_typ="sortiert", linescans=ls)


# --- parse_bereiche ---------------------------------------------------------------

def test_parse_bereiche():
    assert parse_bereiche("") == []
    assert parse_bereiche("3-5", einheit=1e9) == [(3e9, 5e9)]
    assert parse_bereiche("3-5; 10.2-11") == [(3.0, 5.0), (10.2, 11.0)]
    assert parse_bereiche("5-3") == [(3.0, 5.0)]  # verdreht wird sortiert
    with pytest.raises(ValueError):
        parse_bereiche("3..5")
    with pytest.raises(ValueError):
        parse_bereiche("drei-fuenf")


# --- waehle_indizes ----------------------------------------------------------------

def test_jeder_nte_linescan():
    ds = _datensatz(n_freq=20)
    auswahl = Auswertungsauswahl(n_frequenz=5)
    np.testing.assert_array_equal(auswahl.waehle_indizes(ds), [0, 5, 10, 15])


def test_frequenzfenster_und_ausschluss():
    ds = _datensatz(n_freq=20, f0=1e9, f1=20e9)  # 1,2,...,20 GHz
    auswahl = Auswertungsauswahl(
        frequenz_min_hz=2e9, frequenz_max_hz=18e9,
        frequenz_ausschluss=[(3e9, 5e9)])
    gewaehlt = ds.frequenzen[auswahl.waehle_indizes(ds)]
    assert gewaehlt.min() >= 2e9 and gewaehlt.max() <= 18e9
    assert not np.any((gewaehlt >= 3e9) & (gewaehlt <= 5e9))


def test_ausschluss_vor_unterabtastung():
    """Erst Bereiche/Ausschluesse, dann jeder n-te - Schrittweite bleibt konstant."""
    ds = _datensatz(n_freq=20, f0=1e9, f1=20e9)
    auswahl = Auswertungsauswahl(n_frequenz=3, frequenz_ausschluss=[(1e9, 6e9)])
    indizes = auswahl.waehle_indizes(ds)
    np.testing.assert_array_equal(indizes, [6, 9, 12, 15, 18])


# --- reduziere ----------------------------------------------------------------------

def test_reduziere_linescan_feldjumper_und_bereich():
    ds = _datensatz(n_feld=60)
    auswahl = Auswertungsauswahl(n_feld=4, feld_min_t=1.5, feld_max_t=2.5)
    klein = auswahl.reduziere_linescan(ds.linescans[0])
    assert klein.feld.min() >= 1.5 and klein.feld.max() <= 2.5
    # Jeder 4. Punkt des eingeschraenkten Bereichs; Zusatzspuren laufen mit.
    voll = ds.linescans[0]
    maske = (voll.feld >= 1.5) & (voll.feld <= 2.5)
    erwartet = voll.feld[np.flatnonzero(maske)[::4]]
    np.testing.assert_array_equal(klein.feld, erwartet)
    assert klein.temperatur is not None and klein.temperatur.size == klein.feld.size
    np.testing.assert_array_equal(klein.re, voll.re[np.flatnonzero(maske)[::4]])


def test_reduziere_datensatz_meta():
    ds = _datensatz()
    auswahl = Auswertungsauswahl(n_frequenz=2, n_feld=3)
    reduziert, indizes = auswahl.reduziere(ds)
    assert len(reduziert) == indizes.size == 10
    assert reduziert.meta["quell_indizes"] == [int(i) for i in indizes]
    kopie = Auswertungsauswahl.aus_dict(reduziert.meta["auswertungsauswahl"])
    assert kopie.n_frequenz == 2 and kopie.n_feld == 3
    # Original unangetastet.
    assert len(ds) == 20 and ds.linescans[0].feld.size == 60


def test_neutrale_auswahl_und_validierung():
    assert Auswertungsauswahl().ist_neutral
    assert not Auswertungsauswahl(n_frequenz=2).ist_neutral
    with pytest.raises(ValueError):
        Auswertungsauswahl(n_frequenz=0)
    with pytest.raises(ValueError):
        Auswertungsauswahl(n_feld=-1)


def test_beschreibung_enthaelt_kernangaben():
    ds = _datensatz()
    auswahl = Auswertungsauswahl(n_frequenz=10, frequenz_ausschluss=[(3e9, 5e9)])
    text = auswahl.beschreibung(ds)
    assert "jede 10. Frequenz" in text and "ohne 3-5 GHz" in text and "von 20" in text
    assert Auswertungsauswahl().beschreibung() == "alles auswerten"


# --- Integration mit fitte_alle -------------------------------------------------------

def _fmr_datensatz(n_freq=8, n_feld=120):
    """Physikalisch sinnvoller Mini-Datensatz (oop-Resonanz auf Kittel-Gerade)."""
    gamma = GAMMA_STANDARD
    mu0Meff = 0.4
    freqs = np.linspace(8e9, 22e9, n_freq)
    B = np.linspace(0.5, 1.4, n_feld)
    rng = np.random.default_rng(3)
    linescans = []
    b_res = []
    for f in freqs:
        omega = 2 * np.pi * f
        br = omega / gamma + mu0Meff
        b_res.append(br)
        chi = chi_oop(B, br, 0.01, omega, gamma)
        rauschen = (rng.normal(scale=2e-4, size=n_feld)
                    + 1j * rng.normal(scale=2e-4, size=n_feld))
        s = 5e4 * chi + (0.02 + 0.01j) + rauschen
        linescans.append(Linescan(frequenz=float(f), feld=B, re=s.real, im=s.imag))
    return Messdatensatz(quelle="t", format_typ="sortiert", linescans=linescans), np.array(b_res)


def test_fitte_alle_mit_auswahl_reduziert():
    ds, _ = _fmr_datensatz(n_freq=8, n_feld=120)
    auswahl = Auswertungsauswahl(n_frequenz=2, n_feld=2)
    stapel = fitte_alle(ds, auswahl=auswahl)
    assert len(stapel.ergebnisse) == 4
    assert len(stapel.datensatz) == 4
    assert stapel.datensatz.meta["quell_indizes"] == [0, 2, 4, 6]
    # Feld-Jumper: die gefitteten Linescans haben das halbierte Gitter.
    assert stapel.datensatz.linescans[0].feld.size == 60
    # Frequenzen entsprechen exakt den gewaehlten Original-Linescans.
    np.testing.assert_allclose(stapel.datensatz.frequenzen, ds.frequenzen[[0, 2, 4, 6]])


def test_fitte_alle_zentren_werden_mitreduziert():
    ds, b_res = _fmr_datensatz(n_freq=8, n_feld=120)
    auswahl = Auswertungsauswahl(n_frequenz=2)
    stapel = fitte_alle(ds, zentren=b_res, auswahl=auswahl)
    assert len(stapel.fenster) == 4
    # Fenster liegen um die (reduzierten) vorgegebenen Zentren.
    for (unten, oben), br in zip(stapel.fenster, b_res[[0, 2, 4, 6]]):
        assert unten < br < oben


def test_fitte_alle_neutral_wie_bisher():
    ds, _ = _fmr_datensatz(n_freq=4, n_feld=100)
    stapel_ohne = fitte_alle(ds)
    stapel_neutral = fitte_alle(ds, auswahl=Auswertungsauswahl())
    assert len(stapel_ohne.ergebnisse) == len(stapel_neutral.ergebnisse) == 4
    # Neutral bedeutet: exakt derselbe (nicht reduzierte) Datensatz.
    assert stapel_neutral.datensatz is ds

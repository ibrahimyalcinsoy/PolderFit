# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Tests des interaktiven In-Plot-Fittings (Kernlogik, Aufgabenbereich 5):

Dispersions-Trasse, mitwandernde Grenzen (Propagation), explizite
Fensterbreite in Punkten, Ausschlusszonen und der Ergaenzen-Modus.
"""

import numpy as np
import pytest

from polderfit.fit import (
    Ausschlusszone,
    dispersions_zentren,
    entferne_ausschlusszone,
    fitte_alle,
    fitte_bereich,
    fitte_neu,
    fuege_ausschlusszone_hinzu,
    propagiere_grenzen,
    setze_fensterbreite_punkte,
)
from polderfit.fit.batch import StapelErgebnis, ohne_ausschlusszonen
from polderfit.fit.linescan_fit import FitErgebnis
from polderfit.io.datensatz import Linescan, Messdatensatz
from polderfit.physik.konstanten import GAMMA_STANDARD
from polderfit.physik.suszeptibilitaet import chi_oop

GAMMA = GAMMA_STANDARD
MU0MEFF = 0.4


def _fmr_datensatz(n_freq=8, n_feld=150):
    """oop-Resonanz exakt auf der Kittel-Geraden, sauberes SNR."""
    freqs = np.linspace(8e9, 22e9, n_freq)
    B = np.linspace(0.5, 1.4, n_feld)
    rng = np.random.default_rng(5)
    linescans, b_res = [], []
    for f in freqs:
        omega = 2 * np.pi * f
        br = omega / GAMMA + MU0MEFF
        b_res.append(br)
        # Linienbreite bewusst breiter (alpha=0.03): eine gut mit Punkten
        # aufgeloeste Resonanz konditioniert den Fit so, dass lmfit fuer ALLE
        # Frequenzen Unsicherheiten bestimmen kann. Bei alpha=0.01 landen
        # einzelne (dennoch exzellent passende) Fits in einem Nebenminimum mit
        # nichttrivialem phi, dessen Jacobi singulaer wird -> "keine
        # Unsicherheiten" -> faelschlich problematisch. Die Ergaenzen-Semantik
        # (nur problematische Fits anfassen) soll hier gegen einen sauberen
        # Ausgangsstapel geprueft werden, nicht gegen dieses Fit-Artefakt.
        chi = chi_oop(B, br, 0.03, omega, GAMMA)
        s = 5e4 * chi + (0.02 + 0.01j)
        s += rng.normal(scale=2e-4, size=n_feld) + 1j * rng.normal(scale=2e-4, size=n_feld)
        linescans.append(Linescan(frequenz=float(f), feld=B, re=s.real, im=s.imag))
    ds = Messdatensatz(quelle="t", format_typ="sortiert", linescans=linescans)
    return ds, np.array(b_res)


def _kunst_stapel(frequenzen, b_res, problematisch=None):
    """Stapel mit von Hand gesetzten Ergebnissen (ohne echte Fits)."""
    ds = Messdatensatz(
        quelle="t", format_typ="sortiert",
        linescans=[Linescan(frequenz=float(f), feld=np.linspace(0.4, 1.6, 50),
                            re=np.zeros(50), im=np.zeros(50)) for f in frequenzen])
    problematisch = problematisch or [False] * len(frequenzen)
    stapel = StapelErgebnis(datensatz=ds)
    for f, b, p in zip(frequenzen, b_res, problematisch):
        stapel.ergebnisse.append(FitErgebnis(frequenz=float(f), erfolg=True,
                                             B_res=float(b), problematisch=p))
        stapel.fenster.append((b - 0.1, b + 0.1))
        stapel.zugeschnitten.append(ds.linescans[0])
    return stapel


# --- dispersions_zentren -------------------------------------------------------

def test_trasse_ist_ausgleichsgerade_und_ignoriert_ausreisser():
    f = np.linspace(10e9, 20e9, 6)
    b_wahr = 0.3 + 0.04e-9 * f  # linear
    b_mess = b_wahr.copy()
    b_mess[2] = 1.4             # grober Ausreisser ...
    stapel = _kunst_stapel(f, b_mess,
                           problematisch=[False, False, True, False, False, False])
    zentren = dispersions_zentren(stapel)  # ... ist problematisch markiert
    np.testing.assert_allclose(zentren, b_wahr, atol=1e-6)


def test_trasse_rueckfaelle():
    f = np.linspace(10e9, 20e9, 4)
    # Nur ein guter Fit -> konstante Trasse auf dessen B_res.
    stapel = _kunst_stapel(f, [0.7, 0.9, 1.1, 1.3],
                           problematisch=[True, False, True, True])
    np.testing.assert_allclose(dispersions_zentren(stapel), 0.9)
    # Keine Fits, aber Fenster -> Fenstermitten.
    stapel2 = _kunst_stapel(f, [0.7, 0.8, 0.9, 1.0])
    stapel2.ergebnisse = []
    np.testing.assert_allclose(dispersions_zentren(stapel2),
                               [0.7, 0.8, 0.9, 1.0], atol=1e-12)
    # Weder Fits noch Fenster -> klarer Fehler.
    stapel2.fenster = []
    with pytest.raises(ValueError):
        dispersions_zentren(stapel2)


# --- propagiere_grenzen ----------------------------------------------------------

def test_propagation_wandert_mit_der_trasse():
    ds, b_res = _fmr_datensatz()
    stapel = fitte_alle(ds)
    zentren = dispersions_zentren(stapel)

    neu = propagiere_grenzen(stapel, ab_index=3,
                             offset_links=-0.08, offset_rechts=+0.05,
                             zentren=zentren)
    assert neu == [3, 4, 5, 6, 7]
    for i in neu:
        unten, oben = stapel.fenster[i]
        # Fenster folgt der Trasse: Offsets relativ zum jeweiligen Zentrum.
        np.testing.assert_allclose(unten, zentren[i] - 0.08, atol=1e-12)
        np.testing.assert_allclose(oben, zentren[i] + 0.05, atol=1e-12)
        assert stapel.ergebnisse[i].nachbearbeitet
        # Fit findet die Mode im mitgewanderten Fenster.
        assert abs(stapel.ergebnisse[i].B_res - b_res[i]) < 0.02
    # Davor: unangetastet.
    assert not stapel.ergebnisse[0].nachbearbeitet


def test_propagation_ergaenzen_ueberspringt_gute_fits():
    ds, _ = _fmr_datensatz()
    stapel = fitte_alle(ds)
    stapel.ergebnisse[5].problematisch = True
    vorher = list(stapel.ergebnisse)
    neu = propagiere_grenzen(stapel, 3, -0.08, +0.05, modus="ergaenzen")
    assert neu == [5]
    assert all(stapel.ergebnisse[i] is vorher[i] for i in range(len(ds)) if i != 5)


def test_propagation_validierung():
    ds, _ = _fmr_datensatz()
    stapel = fitte_alle(ds)
    with pytest.raises(ValueError):
        propagiere_grenzen(stapel, 0, +0.05, -0.08)  # links >= rechts
    with pytest.raises(ValueError):
        propagiere_grenzen(stapel, 0, -0.08, +0.05, modus="quer")


# --- setze_fensterbreite_punkte -----------------------------------------------------

def test_fensterbreite_in_punkten():
    ds, _ = _fmr_datensatz(n_feld=150)
    stapel = fitte_alle(ds)
    neu = setze_fensterbreite_punkte(stapel, 25)
    assert neu == list(range(len(ds)))
    for i in neu:
        unten, oben = stapel.fenster[i]
        ls = ds.linescans[i]
        punkte = int(np.count_nonzero((ls.feld >= unten) & (ls.feld <= oben)))
        # Fenster kann am Datenrand beschnitten sein, sonst 25 +/- 1 Punkte.
        assert punkte <= 26
        if unten > ls.feld.min() and oben < ls.feld.max():
            assert 24 <= punkte <= 26

    with pytest.raises(ValueError):
        setze_fensterbreite_punkte(stapel, 3)  # < 4 sinnlos


# --- Ausschlusszonen -------------------------------------------------------------------

def test_ohne_ausschlusszonen_maskiert_punkte():
    b = np.linspace(1.0, 2.0, 40)
    ls = Linescan(frequenz=10e9, feld=b, re=np.cos(b), im=np.sin(b),
                  temperatur=np.full(40, 5.0))
    zone = Ausschlusszone(1.4, 1.6, 5e9, 15e9)
    klein = ohne_ausschlusszonen(ls, [zone])
    assert not np.any((klein.feld >= 1.4) & (klein.feld <= 1.6))
    assert klein.temperatur.size == klein.feld.size
    # Zone betrifft andere Frequenz nicht.
    zone_fremd = Ausschlusszone(1.4, 1.6, 20e9, 30e9)
    assert ohne_ausschlusszonen(ls, [zone_fremd]) is ls
    # Wuerde die Maske < 4 Punkte lassen -> unveraendert.
    zone_alles = Ausschlusszone(0.0, 3.0, 5e9, 15e9)
    assert ohne_ausschlusszonen(ls, [zone_alles]) is ls


def test_zone_wirkt_auf_nachfits_und_ist_rueckgaengig():
    ds, b_res = _fmr_datensatz()
    stapel = fitte_alle(ds)

    zone = Ausschlusszone(b_res[0] - 0.02, b_res[0] + 0.02,
                          ds.frequenzen[0] - 1, ds.frequenzen[0] + 1)
    betroffen = fuege_ausschlusszone_hinzu(stapel, zone)
    assert betroffen == [0]
    assert len(stapel.ausschlusszonen) == 1
    # Der beschnittene Linescan des Nachfits enthaelt keine Zonen-Punkte mehr.
    zg = stapel.zugeschnitten[0]
    assert not np.any((zg.feld >= zone.feld_min) & (zg.feld <= zone.feld_max))

    # Zone entfernen: betroffene Linescans erneut gefittet, Punkte wieder da.
    betroffen2 = entferne_ausschlusszone(stapel, 0)
    assert betroffen2 == [0] and stapel.ausschlusszonen == []
    zg2 = stapel.zugeschnitten[0]
    assert np.any((zg2.feld >= zone.feld_min) & (zg2.feld <= zone.feld_max))
    # Ohne Zone sitzt der Fit wieder auf der Mode.
    assert abs(stapel.ergebnisse[0].B_res - b_res[0]) < 0.02


# --- fitte_bereich im Ergaenzen-Modus ------------------------------------------------

def test_bereichsfit_ergaenzen_laesst_gute_fits_stehen():
    ds, _ = _fmr_datensatz()
    stapel = fitte_alle(ds)
    stapel.ergebnisse[2].problematisch = True
    vorher = list(stapel.ergebnisse)
    neu, uebersprungen = fitte_bereich(
        stapel, 0.5, 1.4, ds.frequenzen.min(), ds.frequenzen.max(),
        modus="ergaenzen")
    assert neu == [2]
    assert set(uebersprungen) == set(range(len(ds))) - {2}
    assert all(stapel.ergebnisse[i] is vorher[i] for i in range(len(ds)) if i != 2)

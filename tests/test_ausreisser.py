# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Tests des Ausreisser-Managements (Kernlogik) und der Projekt-Persistenz.

Kernszenario: Einzelne physikalisch sinnlose Ausreisser (stets in der
Minderheit) verfaelschen den linearen Kittel-Fit total - nach dem Ausschluss
stimmen die Parameter wieder.
"""

import numpy as np
import pytest
from nptdms import ChannelObject, TdmsWriter

from polderfit.auswertung.uebersicht import auswertung_kittel_llg
from polderfit.fit import Ausschlusszone, fitte_alle, fitte_neu
from polderfit.fit.batch import StapelErgebnis
from polderfit.fit.linescan_fit import FitErgebnis
from polderfit.io import lade_tdms
from polderfit.io.datensatz import Linescan, Messdatensatz
from polderfit.persistenz.projekt import (
    lade_sitzung,
    speichere_sitzung,
    stelle_stapel_wieder_her,
)
from polderfit.physik.konstanten import GAMMA_STANDARD
from polderfit.physik.kittel_llg import linienbreite
from polderfit.physik.suszeptibilitaet import chi_oop

GAMMA = GAMMA_STANDARD
MU0MEFF = 0.4
ALPHA = 0.008


def _ergebnis(f, b_res, dh, problematisch=False):
    return FitErgebnis(frequenz=float(f), erfolg=True, B_res=float(b_res),
                       dH=float(dh), problematisch=problematisch)


def _kittel_stapel(n=12, ausreisser_bei=()):
    """Stapel mit Ergebnissen exakt auf der oop-Kittel-Geraden; an den Indizes
    ``ausreisser_bei`` sitzen grobe, physikalisch sinnlose Ausreisser."""
    freqs = np.linspace(8e9, 30e9, n)
    ds = Messdatensatz(quelle="t", format_typ="sortiert", linescans=[
        Linescan(frequenz=float(f), feld=np.linspace(0.4, 1.6, 30),
                 re=np.zeros(30), im=np.zeros(30)) for f in freqs])
    stapel = StapelErgebnis(datensatz=ds)
    for i, f in enumerate(freqs):
        omega = 2 * np.pi * f
        b = omega / GAMMA + MU0MEFF
        dh = linienbreite(f, 2e-3, ALPHA, GAMMA)
        if i in ausreisser_bei:
            b = 0.05  # voellig neben der Geraden (z. B. Stoersignal-Fit)
        stapel.ergebnisse.append(_ergebnis(f, b, dh))
        stapel.fenster.append((b - 0.1, b + 0.1))
        stapel.zugeschnitten.append(ds.linescans[i])
    return stapel


# --- Umschalten & Filterung ---------------------------------------------------

def test_ausreisser_umschalten_und_aktive_liste():
    stapel = _kittel_stapel()
    assert stapel.ausreisser_umschalten(3) is True
    assert stapel.ausreisser_umschalten(7) is True
    assert stapel.ausreisser == [3, 7]
    assert stapel.ist_ausreisser(3) and not stapel.ist_ausreisser(4)
    aktiv = stapel.ergebnisse_aktiv()
    assert len(aktiv) == len(stapel.ergebnisse) - 2
    assert stapel.ergebnisse[3] not in aktiv
    # Zuruecknehmen.
    assert stapel.ausreisser_umschalten(3) is False
    assert stapel.ausreisser == [7]


def test_ausreisser_verfaelschen_kittel_und_ausschluss_repariert():
    stapel = _kittel_stapel(n=12, ausreisser_bei=(9, 10, 11))

    # MIT den Ausreissern (hohe Frequenzen, B_res ~ 0.05 T) kippt die
    # Kittel-Gerade sichtbar - mu0Meff ist grob falsch.
    info_kaputt = auswertung_kittel_llg(stapel.ergebnisse, geometrie="oop")
    assert abs(info_kaputt["kittel"]["mu0Meff"] - MU0MEFF) > 0.05

    # Ausreisser markieren -> Auswertung auf den aktiven Ergebnissen stimmt.
    for i in (9, 10, 11):
        stapel.ausreisser_umschalten(i)
    info = auswertung_kittel_llg(stapel.ergebnisse_aktiv(), geometrie="oop")
    assert abs(info["kittel"]["mu0Meff"] - MU0MEFF) < 1e-3
    assert abs(info["kittel"]["gamma"] - GAMMA) / GAMMA < 1e-3


# --- Projekt-Persistenz -----------------------------------------------------------

def _schreibe_sortiert_fmr(pfad, n_freq=6, n_feld=120):
    """Kleines echtes FMR-File im sortierten Layout (fuer den Lade-Roundtrip)."""
    rng = np.random.default_rng(9)
    frequenz, feld, re, im = [], [], [], []
    B = np.linspace(0.5, 1.4, n_feld)
    for f in np.linspace(8e9, 18e9, n_freq):
        omega = 2 * np.pi * f
        chi = chi_oop(B, omega / GAMMA + MU0MEFF, 0.03, omega, GAMMA)
        s = 5e4 * chi + (0.02 + 0.01j)
        s += rng.normal(scale=2e-4, size=n_feld) + 1j * rng.normal(scale=2e-4, size=n_feld)
        frequenz.append(np.full(n_feld, f))
        feld.append(B)
        re.append(s.real)
        im.append(s.imag)
    kanaele = [
        ChannelObject("ZVB", "frequency", np.concatenate(frequenz)),
        ChannelObject("ZVB", "ReS21", np.concatenate(re)),
        ChannelObject("ZVB", "ImS21", np.concatenate(im)),
        ChannelObject("Field", "Field-before", np.concatenate(feld) - 0.001),
        ChannelObject("Field", "Field-after", np.concatenate(feld) + 0.001),
    ]
    with TdmsWriter(str(pfad)) as schreiber:
        schreiber.write_segment(kanaele)


def test_projekt_roundtrip_mit_ausreissern_und_zonen(tmp_path):
    tdms_pfad = tmp_path / "messung.tdms"
    _schreibe_sortiert_fmr(tdms_pfad)
    ds = lade_tdms(tdms_pfad)
    stapel = fitte_alle(ds)

    # Sitzung "bearbeiten": manuelles Fenster, Zone, Ausreisser.
    fitte_neu(stapel, 2, feld_unten=stapel.fenster[2][0] - 0.05,
              feld_oben=stapel.fenster[2][1] + 0.05)
    stapel.ausschlusszonen.append(Ausschlusszone(0.50, 0.55, 0.0, 1e12))
    stapel.ausreisser_umschalten(4)

    projekt_pfad = tmp_path / "sitzung.json"
    speichere_sitzung(stapel, str(projekt_pfad))

    # Wiederherstellen: TDMS ueber die gespeicherte Zuordnung neu laden.
    daten = lade_sitzung(str(projekt_pfad))
    assert daten["polderfit_projekt_version"] == 2
    zuordnung = {rolle: tuple(paar) for rolle, paar in daten["zuordnung"].items()}
    ds2 = lade_tdms(daten["quelle"], zuordnung=zuordnung, layout=daten["format_typ"])
    stapel2 = stelle_stapel_wieder_her(daten, ds2)

    assert stapel2.fenster == stapel.fenster
    assert stapel2.ausreisser == [4]
    assert len(stapel2.ausschlusszonen) == 1
    assert stapel2.ergebnisse[2].nachbearbeitet is True
    assert stapel2.ergebnisse[0].nachbearbeitet is False
    # Deterministische Wiederherstellung: gleiche Fenster -> gleiche Resonanzen.
    for e1, e2 in zip(stapel.ergebnisse, stapel2.ergebnisse):
        if np.isfinite(e1.B_res) and np.isfinite(e2.B_res):
            assert abs(e1.B_res - e2.B_res) < 1e-6


def test_wiederherstellen_prueft_fensteranzahl(tmp_path):
    tdms_pfad = tmp_path / "messung.tdms"
    _schreibe_sortiert_fmr(tdms_pfad)
    ds = lade_tdms(tdms_pfad)
    stapel = fitte_alle(ds)
    projekt_pfad = tmp_path / "sitzung.json"
    speichere_sitzung(stapel, str(projekt_pfad))

    daten = lade_sitzung(str(projekt_pfad))
    kleiner = Messdatensatz(quelle=ds.quelle, format_typ=ds.format_typ,
                            linescans=ds.linescans[:-2], meta=dict(ds.meta))
    with pytest.raises(ValueError, match="Fenster"):
        stelle_stapel_wieder_her(daten, kleiner)


def test_ungueltige_ausreisser_indizes_werden_verworfen(tmp_path):
    tdms_pfad = tmp_path / "messung.tdms"
    _schreibe_sortiert_fmr(tdms_pfad)
    ds = lade_tdms(tdms_pfad)
    stapel = fitte_alle(ds)
    stapel.ausreisser = [0, 99]  # 99 existiert nicht (z. B. andere Auswahl)
    projekt_pfad = tmp_path / "sitzung.json"
    speichere_sitzung(stapel, str(projekt_pfad))
    daten = lade_sitzung(str(projekt_pfad))
    zuordnung = {rolle: tuple(paar) for rolle, paar in daten["zuordnung"].items()}
    ds2 = lade_tdms(daten["quelle"], zuordnung=zuordnung, layout=daten["format_typ"])
    stapel2 = stelle_stapel_wieder_her(daten, ds2)
    assert stapel2.ausreisser == [0]

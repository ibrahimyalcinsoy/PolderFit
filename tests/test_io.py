"""Tests des Einlesens beider TDMS-Formate und des Ergebnis-Schreibens."""

import os

import numpy as np

from ananas.io import lade_tdms, schreibe_ergebnis_tdms
from ananas.io.datensatz import Linescan


def test_lade_unsortiert(pfad_unsortiert):
    ds = lade_tdms(pfad_unsortiert)
    assert ds.format_typ == "unsortiert"
    assert ds.meta["n_feld"] == 725
    assert ds.meta["n_freq"] == 1001
    assert len(ds) == 1001
    ls = ds.linescans[500]
    assert ls.feld.size == 725
    # Feld monoton aufsteigend sortiert.
    assert np.all(np.diff(ls.feld) >= 0)
    assert ls.temperatur is not None


def test_lade_sortiert(pfad_sortiert):
    ds = lade_tdms(pfad_sortiert)
    assert ds.format_typ == "sortiert"
    assert 80 <= len(ds) <= 100  # ~90 eindeutige Frequenzen
    # Variable Punktzahl je Frequenz (nicht 1001).
    groessen = {ls.feld.size for ls in ds.linescans}
    assert max(groessen) < 200
    # Frequenzen aufsteigend.
    f = ds.frequenzen
    assert np.all(np.diff(f) > 0)


def test_anzeige_matrix(pfad_sortiert):
    ds = lade_tdms(pfad_sortiert)
    feld, freq, matrix = ds.anzeige_matrix(150)
    assert matrix.shape == (len(ds), 150)
    assert np.isfinite(matrix).any()


def test_schreibe_und_lese_zurueck(tmp_path):
    b = np.linspace(2.5, 3.5, 50)
    s = (np.cos(b) + 1j * np.sin(b)) * 0.01
    ls = Linescan(frequenz=20e9, feld=b, re=s.real, im=s.imag,
                  feld_before=b, feld_after=b)
    pfad = os.path.join(tmp_path, "ausgabe.tdms")
    schreibe_ergebnis_tdms(pfad, [ls], [s])
    assert os.path.exists(pfad)
    # Zuruecklesen ueber nptdms.
    from nptdms import TdmsFile
    t = TdmsFile.read(pfad)
    gruppen = {g.name for g in t.groups()}
    assert {"Rohdaten_zugeschnitten", "Fit", "Fenster"} <= gruppen
    assert t["Rohdaten_zugeschnitten"]["ReS21"][:].size == 50

"""End-to-End-Test: Laden -> Stapel-Fit -> Kittel/LLG -> Export."""

import os
import warnings

import numpy as np

from ananas.io import lade_tdms
from ananas.fit import fitte_alle
from ananas.auswertung import auswertung_kittel_llg
from ananas.persistenz.ergebnis_export import exportiere_excel, parameter_tabelle


def test_pipeline_sortiert(pfad_sortiert, tmp_path):
    warnings.filterwarnings("ignore")
    ds = lade_tdms(pfad_sortiert)
    stapel = fitte_alle(ds, r2_schwelle=0.9)
    r2 = np.array([e.R2 for e in stapel.ergebnisse])
    # Die meisten Fits sollten sehr gut sein (sauberes Resonanzband).
    assert np.median(r2) > 0.95
    assert np.mean([e.erfolg for e in stapel.ergebnisse]) > 0.8

    info = auswertung_kittel_llg(stapel.ergebnisse, geometrie="oop")
    # Physikalisch plausible Groessen.
    assert 1.5 < info["kittel"]["mu0Meff"] < 3.5
    assert 1.9 < info["kittel"]["g_faktor"] < 2.3
    assert 0 < info["llg"]["alpha"] < 0.05

    tab = parameter_tabelle(stapel.ergebnisse)
    assert {"frequenz_Hz", "B_res_T", "alpha", "R2"} <= set(tab.columns)

    pfad = os.path.join(tmp_path, "ergebnis.xlsx")
    global_param = {f"kittel_{k}": v for k, v in info["kittel"].items()}
    exportiere_excel(stapel.ergebnisse, pfad, global_param)
    assert os.path.exists(pfad)

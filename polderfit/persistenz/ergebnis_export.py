# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Export der Fitparameter und Kennzahlen als Excel/CSV.

Gespeichert werden alle im Protokoll geforderten Groessen: H_res (B_res), DeltaH,
Vorfaktor A, Phase phi, Offsets, Slopes, R² und die Unsicherheiten – zusammen mit
den uebergreifenden Auswerteergebnissen (Kittel/LLG).
"""

from __future__ import annotations

import pandas as pd

from ..fit.linescan_fit import FitErgebnis


def parameter_tabelle(ergebnisse: list[FitErgebnis],
                      ausreisser: list[int] | None = None) -> pd.DataFrame:
    """Baut die Parametertabelle (eine Zeile je Frequenz).

    ``ausreisser`` (Stapel-Indizes) kennzeichnet die manuell ausgeschlossenen
    Punkte in einer eigenen Spalte - sie bleiben im Export einsehbar, gehen
    aber in keine uebergreifende Auswertung (Kittel/LLG) ein.
    """
    gesperrt = set(ausreisser or [])
    zeilen = []
    for i, e in enumerate(ergebnisse):
        zeile = e.als_zeile()
        zeile["ausreisser"] = i in gesperrt
        zeilen.append(zeile)
    return pd.DataFrame(zeilen).sort_values("frequenz_Hz")


def _global_tabelle(global_param: dict | None) -> pd.DataFrame:
    if not global_param:
        return pd.DataFrame(columns=["Groesse", "Wert"])
    return pd.DataFrame(
        [{"Groesse": k, "Wert": v} for k, v in global_param.items()]
    )


def exportiere_csv(ergebnisse: list[FitErgebnis], pfad: str,
                   ausreisser: list[int] | None = None) -> None:
    """Schreibt die Parametertabelle als CSV."""
    parameter_tabelle(ergebnisse, ausreisser).to_csv(pfad, index=False)


def exportiere_excel(
    ergebnisse: list[FitErgebnis],
    pfad: str,
    global_param: dict | None = None,
    ausreisser: list[int] | None = None,
) -> None:
    """Schreibt Parameter (Blatt 'Einzelfits') und Kittel/LLG (Blatt 'Global')."""
    tab = parameter_tabelle(ergebnisse, ausreisser)
    with pd.ExcelWriter(pfad, engine="openpyxl") as writer:
        tab.to_excel(writer, sheet_name="Einzelfits", index=False)
        _global_tabelle(global_param).to_excel(writer, sheet_name="Global", index=False)

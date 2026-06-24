"""Export der Fitparameter und Kennzahlen als Excel/CSV.

Gespeichert werden alle im Protokoll geforderten Groessen: H_res (B_res), DeltaH,
Vorfaktor A, Phase phi, Offsets, Slopes, R² und die Unsicherheiten – zusammen mit
den uebergreifenden Auswerteergebnissen (Kittel/LLG).
"""

from __future__ import annotations

import pandas as pd

from ..fit.linescan_fit import FitErgebnis


def parameter_tabelle(ergebnisse: list[FitErgebnis]) -> pd.DataFrame:
    """Baut die Parametertabelle (eine Zeile je Frequenz)."""
    return pd.DataFrame([e.als_zeile() for e in ergebnisse]).sort_values("frequenz_Hz")


def _global_tabelle(global_param: dict | None) -> pd.DataFrame:
    if not global_param:
        return pd.DataFrame(columns=["Groesse", "Wert"])
    return pd.DataFrame(
        [{"Groesse": k, "Wert": v} for k, v in global_param.items()]
    )


def exportiere_csv(ergebnisse: list[FitErgebnis], pfad: str) -> None:
    """Schreibt die Parametertabelle als CSV."""
    parameter_tabelle(ergebnisse).to_csv(pfad, index=False)


def exportiere_excel(
    ergebnisse: list[FitErgebnis],
    pfad: str,
    global_param: dict | None = None,
) -> None:
    """Schreibt Parameter (Blatt 'Einzelfits') und Kittel/LLG (Blatt 'Global')."""
    tab = parameter_tabelle(ergebnisse)
    with pd.ExcelWriter(pfad, engine="openpyxl") as writer:
        tab.to_excel(writer, sheet_name="Einzelfits", index=False)
        _global_tabelle(global_param).to_excel(writer, sheet_name="Global", index=False)

# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Export der Fitparameter und Kennzahlen als Excel/CSV.

Gespeichert werden alle Groessen des Einzelfits – Resonanzfeld und
Linienbreite in **Tesla und Millitesla**, Gilbert-Daempfung, Amplitude/Phase
und komplexe Amplitude, Offsets/Steigungen, alle Guetemasse, Fitfenster,
Status/Bewertung und (bei mehreren Moden) die Parameter aller weiteren
Resonanzen – zusammen mit den uebergreifenden Auswerteergebnissen (Kittel/LLG)
und optionalen Zusatzblaettern (Einstellungen, Zonen/Grenzgeraden, Ausreisser).

Welche Spaltengruppen exportiert werden, ist waehlbar (:data:`SPALTEN_GRUPPEN`;
Standard: alle) und als Voreinstellung speicherbar
(:mod:`polderfit.persistenz.einstellungen`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..fit.linescan_fit import FitErgebnis

#: Spaltengruppen des Einzelfit-Exports: Schluessel -> (Titel, Spalten).
#: Die Gruppe ``nebenmoden`` enthaelt alle Spalten mit Moden-Suffix ``_2``, ``_3`` …
SPALTEN_GRUPPEN: dict[str, tuple[str, list[str]]] = {
    "kern": ("Resonanzfeld & Linienbreite (T und mT), α", [
        "frequenz_Hz", "frequenz_GHz", "B_res_T", "B_res_mT", "B_res_err_T",
        "mu0_dH_T", "mu0_dH_mT", "mu0_dH_err_T", "mu0_dH_err_mT", "alpha", "alpha_err"]),
    "amplitude": ("Amplitude, Phase, komplexe Amplitude", [
        "A", "A_err", "phi_rad", "phi_err_rad", "phi_deg", "A_komplex_re", "A_komplex_im"]),
    "untergrund": ("Untergrund (Offset, Steigung)", [
        "offset_re", "offset_im", "slope_re", "slope_im"]),
    "guete": ("Gütemaße (R², Residuum, χ²)", [
        "R2", "eins_minus_R2", "rmse_norm", "rmse_norm_re", "rmse_norm_im",
        "chi2_red", "signalhub"]),
    "fenster": ("Fitfenster", ["B_fenster_min_T", "B_fenster_max_T", "n_punkte_fenster"]),
    "status": ("Status & Bewertung", [
        "bewertung", "problematisch", "problematisch_auto", "problem_gruende",
        "nachbearbeitet", "gefittet", "erfolg", "kovarianz_ok", "ausreisser",
        "im_kittel_verwendet", "meldung"]),
    "nebenmoden": ("Weitere Resonanzen (Moden 2…n)", ["n_moden"]),
    "temperatur": ("Temperatur", ["temperatur_K"]),
}


def _ist_nebenmoden_spalte(name: str) -> bool:
    teile = name.split("_")
    return any(t.isdigit() and int(t) >= 2 for t in teile)


def spalten_fuer(gruppen: list[str] | None, verfuegbar: list[str]) -> list[str]:
    """Geordnete Spaltenliste fuer die gewaehlten Gruppen (``None``/leer = alle)."""
    gewaehlt = list(SPALTEN_GRUPPEN) if not gruppen else [g for g in gruppen if g in SPALTEN_GRUPPEN]
    spalten: list[str] = []
    for gruppe in SPALTEN_GRUPPEN:
        if gruppe not in gewaehlt:
            continue
        for name in SPALTEN_GRUPPEN[gruppe][1]:
            if name in verfuegbar and name not in spalten:
                spalten.append(name)
        if gruppe == "nebenmoden":
            for name in verfuegbar:
                if _ist_nebenmoden_spalte(name) and name not in spalten:
                    spalten.append(name)
    return spalten


def parameter_tabelle(ergebnisse: list[FitErgebnis],
                      ausreisser: list[int] | None = None,
                      spalten: list[str] | None = None,
                      nur_gefittete: bool = False,
                      verwendet: list[int] | None = None,
                      zugeschnitten=None) -> pd.DataFrame:
    """Baut die Parametertabelle (eine Zeile je Frequenz).

    ``ausreisser`` (Stapel-Indizes) kennzeichnet die manuell ausgeschlossenen
    Punkte in einer eigenen Spalte - sie bleiben im Export einsehbar, gehen
    aber in keine uebergreifende Auswertung (Kittel/LLG) ein. ``spalten``:
    Gruppen aus :data:`SPALTEN_GRUPPEN` (leer = alle). ``nur_gefittete``
    laesst Platzhalter ("nicht gefittet") weg. ``verwendet``: Indizes, die im
    Kittel-/LLG-Fit verwendet wurden (Spalte ``im_kittel_verwendet``).
    ``zugeschnitten``: Liste der beschnittenen Linescans (Punktzahl im Fenster).
    """
    gesperrt = set(ausreisser or [])
    benutzt = set(verwendet or [])
    zeilen = []
    for i, e in enumerate(ergebnisse):
        if nur_gefittete and not e.gefittet:
            continue
        zeile = e.als_zeile()
        zeile["ausreisser"] = i in gesperrt
        zeile["im_kittel_verwendet"] = i in benutzt
        n_punkte = np.nan
        if zugeschnitten is not None and i < len(zugeschnitten) and zugeschnitten[i] is not None:
            n_punkte = int(np.size(zugeschnitten[i].feld))
        elif e.feld is not None:
            n_punkte = int(np.size(e.feld))
        zeile["n_punkte_fenster"] = n_punkte
        zeilen.append(zeile)
    if not zeilen:
        return pd.DataFrame(columns=spalten_fuer(spalten, []))
    tab = pd.DataFrame(zeilen).sort_values("frequenz_Hz")
    auswahl = spalten_fuer(spalten, list(tab.columns))
    return tab[auswahl].reset_index(drop=True)


def _global_tabelle(global_param: dict | None) -> pd.DataFrame:
    if not global_param:
        return pd.DataFrame(columns=["Groesse", "Wert"])
    return pd.DataFrame(
        [{"Groesse": k, "Wert": v} for k, v in global_param.items()]
    )


def exportiere_csv(ergebnisse: list[FitErgebnis], pfad: str,
                   ausreisser: list[int] | None = None,
                   spalten: list[str] | None = None,
                   nur_gefittete: bool = False,
                   verwendet: list[int] | None = None,
                   deutsch: bool = False,
                   zugeschnitten=None) -> None:
    """Schreibt die Parametertabelle als CSV (Listendaten).

    ``deutsch=True``: Trennzeichen ``;`` und Dezimalkomma (direkt in deutschem
    Excel/LibreOffice lesbar); sonst ``,`` und Dezimalpunkt (maschinenlesbar).
    """
    tab = parameter_tabelle(ergebnisse, ausreisser, spalten=spalten,
                            nur_gefittete=nur_gefittete, verwendet=verwendet,
                            zugeschnitten=zugeschnitten)
    if deutsch:
        tab.to_csv(pfad, index=False, sep=";", decimal=",", encoding="utf-8-sig")
    else:
        tab.to_csv(pfad, index=False)


def exportiere_excel(
    ergebnisse: list[FitErgebnis],
    pfad: str,
    global_param: dict | None = None,
    ausreisser: list[int] | None = None,
    spalten: list[str] | None = None,
    nur_gefittete: bool = False,
    verwendet: list[int] | None = None,
    zusatzblaetter: dict[str, pd.DataFrame] | None = None,
    zugeschnitten=None,
) -> None:
    """Schreibt Parameter (Blatt 'Einzelfits'), Kittel/LLG (Blatt 'Global') und
    optionale Zusatzblaetter (z. B. 'Einstellungen', 'Zonen_Geraden', 'Ausreisser')."""
    tab = parameter_tabelle(ergebnisse, ausreisser, spalten=spalten,
                            nur_gefittete=nur_gefittete, verwendet=verwendet,
                            zugeschnitten=zugeschnitten)
    with pd.ExcelWriter(pfad, engine="openpyxl") as writer:
        tab.to_excel(writer, sheet_name="Einzelfits", index=False)
        _global_tabelle(global_param).to_excel(writer, sheet_name="Global", index=False)
        for name, blatt in (zusatzblaetter or {}).items():
            if blatt is None:
                continue
            blatt.to_excel(writer, sheet_name=str(name)[:31], index=False)


def kittel_llg_flach(info: dict, praefix: str = "") -> dict:
    """Kittel-/LLG-Parameter als flaches dict fuer das Blatt 'Global'
    (``kittel_*``/``llg_*``, Felder zusaetzlich in mT); ``praefix`` z. B.
    ``"mode2_"`` fuer die Auswertung je Mode."""
    kit, llg = info["kittel"], info["llg"]
    werte = {f"{praefix}kittel_{k}": v for k, v in kit.items()}
    werte[f"{praefix}kittel_mu0Meff_mT"] = kit["mu0Meff"] * 1e3
    werte[f"{praefix}kittel_mu0Meff_err_mT"] = kit["mu0Meff_err"] * 1e3
    if "mu0Hu" in kit:
        werte[f"{praefix}kittel_mu0Hu_mT"] = kit["mu0Hu"] * 1e3
        werte[f"{praefix}kittel_mu0Hu_err_mT"] = kit["mu0Hu_err"] * 1e3
    werte.update({f"{praefix}llg_{k}": v for k, v in llg.items()})
    werte[f"{praefix}llg_mu0Hinh_mT"] = llg["mu0Hinh"] * 1e3
    werte[f"{praefix}llg_mu0Hinh_err_mT"] = llg["mu0Hinh_err"] * 1e3
    werte[f"{praefix}kittel_geometrie"] = info.get("geometrie", "")
    return werte


def kittel_llg_tabelle(info: dict | None, gewichtet: bool = False,
                       n_punkte: int | None = None, n_ausreisser: int | None = None,
                       mode: int | None = None, mode_text: str = "") -> pd.DataFrame:
    """Physikalische Parameter des Kittel-/LLG-Fits als Tabelle (Wert, 1σ, Einheit)
    - Felder in Tesla UND Millitesla. ``mode``/``mode_text``: Auswertung je
    Mode (Zweig-Nummer und Zuordnungsregel als erste Zeile)."""
    zeilen = []
    if mode is not None:
        zeilen.append(("Mode", "Hauptmode" if int(mode) == 0 else int(mode), mode_text, ""))
    if info is not None:
        kit, llg = info["kittel"], info["llg"]
        g_err = kit.get("g_faktor_err", np.nan)
        zeilen += [
            ("Geometrie", info.get("geometrie", ""), "", ""),
            ("Gewichtung", "w=1/u² (GUM)" if gewichtet else "ungewichtet", "", ""),
            ("mu0_Meff", kit["mu0Meff"], kit["mu0Meff_err"], "T"),
            ("mu0_Meff_mT", kit["mu0Meff"] * 1e3, kit["mu0Meff_err"] * 1e3, "mT"),
            ("g_faktor", kit["g_faktor"], g_err, ""),
            ("gamma", kit["gamma"], kit["gamma_err"], "rad/(s*T)"),
        ]
        if "mu0Hu" in kit:
            zeilen += [("mu0_Hu", kit["mu0Hu"], kit["mu0Hu_err"], "T"),
                       ("mu0_Hu_mT", kit["mu0Hu"] * 1e3, kit["mu0Hu_err"] * 1e3, "mT")]
        zeilen += [
            ("R2_kittel", kit["R2"], "", ""),
            ("alpha", llg["alpha"], llg["alpha_err"], ""),
            ("mu0_Hinh", llg["mu0Hinh"], llg["mu0Hinh_err"], "T"),
            ("mu0_Hinh_mT", llg["mu0Hinh"] * 1e3, llg["mu0Hinh_err"] * 1e3, "mT"),
            ("R2_llg", llg["R2"], "", ""),
        ]
        if n_punkte is not None:
            zeilen.append(("N_punkte", int(n_punkte), "", ""))
        if n_ausreisser is not None:
            zeilen.append(("N_ausreisser", int(n_ausreisser), "", ""))
    return pd.DataFrame(zeilen, columns=["Groesse", "Wert", "Fehler_1sigma", "Einheit"])


def kittel_llg_punkte_tabelle(ergebnisse: list[FitErgebnis], ausreisser: list[int] | None,
                              verwendet: list[int] | None, indizes: list[int] | None = None,
                              mode: int | None = None) -> pd.DataFrame:
    """Alle Punkte der Kittel-/LLG-Auswertung mit Einzelfehlern (T und mT).

    ``indizes``: Stapel-Indizes der uebergebenen Ergebnisse (Standard: Position
    in der Liste) - fuer die Auswertung je Mode, wo ``ergebnisse`` die Kopien
    mit Mode ``mode`` als Hauptmode sind (Spalte ``mode``)."""
    gesperrt = set(ausreisser or [])
    benutzt = set(verwendet or [])
    if indizes is None:
        indizes = list(range(len(ergebnisse)))
    zeilen = []
    for i, e in zip(indizes, ergebnisse):
        if not e.gefittet:
            continue
        zeilen.append({
            **({"mode": int(mode)} if mode is not None else {}),
            "stapel_index": int(i),
            "frequenz_Hz": e.frequenz, "frequenz_GHz": e.frequenz / 1e9,
            "B_res_T": e.B_res, "B_res_err_T": e.B_res_err, "B_res_mT": e.B_res_mT,
            "alpha": e.alpha, "alpha_err": e.alpha_err,
            "mu0_dH_T": e.dH, "mu0_dH_err_T": e.dH_err,
            "mu0_dH_mT": e.dH_mT, "mu0_dH_err_mT": e.dH_err_mT,
            "R2_einzelfit": e.R2,
            "temperatur_K": e.temperatur if e.temperatur is not None else np.nan,
            "bewertung": e.bewertung,
            "problematisch": e.problematisch,
            "ausreisser": i in gesperrt,
            "im_kittel_fit_verwendet": i in benutzt,
        })
    return pd.DataFrame(zeilen).sort_values("frequenz_Hz") if zeilen else pd.DataFrame()

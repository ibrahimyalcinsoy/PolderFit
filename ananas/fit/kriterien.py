"""Zentrale Schwellwerte und Problem-Erkennung fuer Linescan-Fits.

Hier liegen ALLE Schranken und Schwellwerte an EINER Stelle (benannte Konstanten),
sowie die Funktion :func:`bewerte_fit`, die ein Fitergebnis als problematisch oder
in Ordnung einstuft und die konkreten Gruende zurueckgibt.

Hintergrund: Der reine R²-Wert ist als Guetemass wertlos, weil die Gesamtvarianz
des Signals vom konstanten Offset und vom feldabhaengigen Gradienten dominiert wird
(eine fast gerade Linie erreicht so R² ~ 1, obwohl sie die Resonanz ignoriert).
Primaeres Guetemass ist daher das **normierte Residuum** (RMSE der Residuen relativ
zum Signalhub NACH Offset-/Gradient-Abzug) bzw. das **reduzierte Chi-Quadrat**.
"""

from __future__ import annotations

import numpy as np

# --- Parameter-Schranken (physikalisch sinnvoll) ---------------------------
#: Untere/obere harte Fit-Schranke der Gilbert-Daempfung alpha (Spielraum fuer
#: den Optimierer; bewusst weiter gefasst als die Plausibilitaetsgrenze unten).
ALPHA_MIN: float = 1e-5
ALPHA_MAX: float = 0.1
#: alpha-Werte oberhalb dieses Wertes gelten als unphysikalisch (Kriterium d).
#: Liegt UNTER ALPHA_MAX: Werte in (0.05, 0.1) sind als Fitwert erlaubt, werden
#: aber als problematisch markiert (statt hart an die Schranke geklemmt zu werden).
ALPHA_PLAUSIBEL_MAX: float = 0.05

#: Schranken des Phasenwinkels phi.
PHI_MIN: float = -2.0 * np.pi
PHI_MAX: float = 2.0 * np.pi

# --- Schwellwerte der Problem-Erkennung ------------------------------------
#: Ein Parameter gilt als "an der Grenze", wenn er innerhalb dieses relativen
#: Anteils des Schrankenabstands an einer Schranke liegt (1 %).
GRENZ_NAEHE_REL: float = 0.01

#: Normiertes Residuum (RMSE/Signalhub) oberhalb dieses Werts -> problematisch.
#: Primaeres, skalenfreies Guetemass (unabhaengig vom dominierenden Untergrund).
RMSE_NORM_SCHWELLE: float = 0.35

#: Reduziertes Chi-Quadrat wird als ZUSAETZLICHE Kennzahl exportiert, aber NICHT
#: zur harten Problem-Einstufung herangezogen: Es haengt von einer verlaesslichen
#: Punkt-Rauschschaetzung ab, die hier nicht vorliegt; bei sehr rauscharmen, real
#: leicht modellabweichenden Resonanzen wuerde es sonst auch gute Fits verwerfen.
#: Dieser (grosszuegige) Wert dient nur als Sicherheitsnetz fuer Totalausreisser.
CHI2_RED_NOTBREMSE: float = 1e6

#: Maximale relative Unsicherheit des Resonanzfeldes (delta B_res / |B_res|).
B_RES_REL_UNSICHERHEIT_MAX: float = 0.02


def an_grenze(wert: float, unten: float, oben: float, rel: float = GRENZ_NAEHE_REL) -> bool:
    """True, wenn ``wert`` innerhalb ``rel`` des Schrankenabstands an einer Schranke liegt."""
    if not np.isfinite(wert):
        return False
    spanne = oben - unten
    if spanne <= 0:
        return False
    return (wert <= unten + rel * spanne) or (wert >= oben - rel * spanne)


def bewerte_fit(erg) -> tuple[bool, list[str]]:
    """Stuft ein :class:`FitErgebnis` ein und liefert ``(problematisch, gruende)``.

    Ein Fit ist problematisch, wenn EINE der folgenden Bedingungen zutrifft:

    a) normiertes Residuum / reduziertes Chi-Quadrat zu gross,
    b) ein Parameter an/nahe einer Schranke,
    c) B_res ausserhalb des Feldfensters,
    d) alpha ausserhalb des plausiblen Bereichs,
    e) keine Konvergenz / keine Kovarianz (keine Unsicherheiten bestimmbar),
    f) relative Parameter-Unsicherheit zu gross.
    """
    gruende: list[str] = []

    # (e) Konvergenz / Kovarianz
    if not erg.erfolg:
        gruende.append("keine Konvergenz")
    if not erg.kovarianz_ok:
        gruende.append("keine Unsicherheiten")

    # (b) Parameter an Schranke
    if an_grenze(erg.alpha, ALPHA_MIN, ALPHA_MAX):
        gruende.append("alpha an Grenze")
    if an_grenze(erg.phi, PHI_MIN, PHI_MAX):
        gruende.append("phi an Grenze")
    if np.isfinite(erg.B_fenster_min) and an_grenze(erg.B_res, erg.B_fenster_min, erg.B_fenster_max):
        gruende.append("B_res am Fensterrand")

    # (c) B_res ausserhalb des Feldfensters
    if np.isfinite(erg.B_fenster_min) and (
        erg.B_res < erg.B_fenster_min or erg.B_res > erg.B_fenster_max
    ):
        gruende.append("B_res ausserhalb Fenster")

    # (d) alpha unphysikalisch
    if np.isfinite(erg.alpha) and erg.alpha > ALPHA_PLAUSIBEL_MAX:
        gruende.append("alpha unphysikalisch")

    # (a) Residuum (primaer: normiertes Residuum, skalenfrei)
    if (not np.isfinite(erg.rmse_norm)) or erg.rmse_norm > RMSE_NORM_SCHWELLE:
        gruende.append("Residuum zu gross")
    elif np.isfinite(erg.chi2_red) and erg.chi2_red > CHI2_RED_NOTBREMSE:
        gruende.append("Chi2 extrem")  # nur Totalausreisser-Sicherheitsnetz

    # (f) relative Unsicherheit des Resonanzfeldes
    if np.isfinite(erg.B_res) and abs(erg.B_res) > 0 and np.isfinite(erg.B_res_err):
        if erg.B_res_err / abs(erg.B_res) > B_RES_REL_UNSICHERHEIT_MAX:
            gruende.append("B_res-Unsicherheit zu gross")

    # Duplikate entfernen, Reihenfolge erhalten.
    eindeutig = list(dict.fromkeys(gruende))
    return (len(eindeutig) > 0, eindeutig)

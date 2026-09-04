# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
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

#: Fehlende Kovarianz allein macht einen Fit NICHT mehr problematisch, wenn das
#: normierte Residuum unter dieser Schwelle liegt (exzellente Anpassung).
#: Hintergrund: Ein numerisch nahezu perfekter Fit kann in ein phi-Nebenminimum
#: laufen, dessen Jacobi-Matrix singulaer wird - lmfit liefert dann keine
#: Unsicherheiten, obwohl die Linienform exakt getroffen ist. Solche Fits als
#: hart problematisch zu markieren war eine der bekannten "Problemfit"-Ursachen.
RMSE_NORM_EXZELLENT: float = 0.10

#: Mindestzahl Messpunkte im Fitfenster/Korridor: 8 Parameter plus Sicherheitsmarge.
MIN_PUNKTE_FIT: int = 12

#: Eine Linie mit mu0*dH unter diesem Vielfachen des Feldschritts ist nicht
#: aufgeloest (Nadel-Linie auf 1-2 Messpunkten) und gilt als problematisch.
DH_MIN_FELDSCHRITTE: float = 1.5


def an_grenze(wert: float, unten: float, oben: float, rel: float = GRENZ_NAEHE_REL) -> bool:
    """True, wenn ``wert`` innerhalb ``rel`` des Schrankenabstands an einer Schranke liegt."""
    if not np.isfinite(wert):
        return False
    spanne = oben - unten
    if spanne <= 0:
        return False
    return (wert <= unten + rel * spanne) or (wert >= oben - rel * spanne)


def alpha_plausibel_max(alpha_max: float = ALPHA_MAX) -> float:
    """Plausibilitaetsgrenze fuer alpha zur eingestellten harten Schranke.

    Standard: ``ALPHA_PLAUSIBEL_MAX`` (0.05) bei ``ALPHA_MAX`` (0.1). Wird die
    harte Schranke vom Nutzer angehoben (sehr breite Resonanzen, z. B.
    FeCr2S4 mit alpha ~ 0.2-0.5), wandert die Plausibilitaetsgrenze im selben
    Verhaeltnis mit (halbe Schranke), damit solche Fits nicht pauschal als
    "alpha unphysikalisch" markiert werden.
    """
    if not np.isfinite(alpha_max) or alpha_max <= 0:
        return ALPHA_PLAUSIBEL_MAX
    return ALPHA_PLAUSIBEL_MAX * (alpha_max / ALPHA_MAX)


#: Problemgrund eines noch nicht gefitteten Platzhalters (z. B. Frequenzen
#: ausserhalb des gruenen Grenzgeraden-Bereichs vor dem ersten Auto-Fit).
GRUND_NICHT_GEFITTET: str = "nicht gefittet"


def bewerte_fit(erg, alpha_max: float = ALPHA_MAX,
                alpha_plausibel: float | None = None) -> tuple[bool, list[str]]:
    """Stuft ein :class:`FitErgebnis` ein und liefert ``(problematisch, gruende)``.

    ``alpha_max`` ist die im Fit verwendete harte alpha-Schranke (Kriterien b
    und d beziehen sich darauf; Standard ``ALPHA_MAX``). ``alpha_plausibel``
    (optional, einstellbar ueber die physikalischen Parameter) ersetzt die
    Standard-Plausibilitaetsgrenze ``alpha_max/2`` fuer Kriterium d - fuer
    "exotische" Proben mit real breiten Linien (nanostrukturiertes CoFe,
    FeCr2S4) sonst dauernd "alpha unphysikalisch". Ein Wert ``<= 0``/``None``
    bedeutet Automatik.

    Ein Fit ist problematisch, wenn EINE der folgenden Bedingungen zutrifft:

    a) normiertes Residuum / reduziertes Chi-Quadrat zu gross,
    b) ein Parameter an/nahe einer Schranke,
    c) B_res ausserhalb des Feldfensters,
    d) alpha ausserhalb des plausiblen Bereichs,
    e) keine Konvergenz / keine Kovarianz (keine Unsicherheiten bestimmbar),
    f) relative Parameter-Unsicherheit zu gross,
    g) zu wenige Messpunkte im Fenster/Korridor (:data:`MIN_PUNKTE_FIT`),
    h) Linie nicht aufgeloest (:data:`DH_MIN_FELDSCHRITTE`).
    """
    gruende: list[str] = []
    if not getattr(erg, "gefittet", True):
        return True, [GRUND_NICHT_GEFITTET]
    plausibel = (float(alpha_plausibel)
                 if alpha_plausibel is not None and np.isfinite(alpha_plausibel)
                 and alpha_plausibel > 0 else alpha_plausibel_max(alpha_max))

    # (e) Konvergenz / Kovarianz. Fehlende Kovarianz zaehlt nur dann als
    # Problem, wenn der Fit nicht ohnehin exzellent passt (phi-Nebenminimum
    # mit singulaerer Jacobi-Matrix, siehe RMSE_NORM_EXZELLENT).
    if not erg.erfolg:
        gruende.append("keine Konvergenz")
    if not erg.kovarianz_ok:
        exzellent = (erg.erfolg and np.isfinite(erg.rmse_norm)
                     and erg.rmse_norm <= RMSE_NORM_EXZELLENT)
        if not exzellent:
            gruende.append("keine Unsicherheiten")

    alpha, phi, b_res = erg.alpha, erg.phi, erg.B_res
    # (b) Parameter an Schranke
    if an_grenze(alpha, ALPHA_MIN, alpha_max):
        gruende.append("alpha an Grenze")
    if an_grenze(phi, PHI_MIN, PHI_MAX):
        gruende.append("phi an Grenze")
    if np.isfinite(erg.B_fenster_min) and an_grenze(b_res, erg.B_fenster_min,
                                                    erg.B_fenster_max):
        gruende.append("B_res am Fensterrand")
    # (c) B_res ausserhalb des Feldfensters
    if np.isfinite(erg.B_fenster_min) and np.isfinite(b_res) and (
        b_res < erg.B_fenster_min or b_res > erg.B_fenster_max
    ):
        gruende.append("B_res ausserhalb Fenster")
    # (d) alpha unphysikalisch
    if np.isfinite(alpha) and alpha > plausibel:
        gruende.append("alpha unphysikalisch")

    # (g) zu wenige Punkte, (h) Linie nicht aufgeloest - beides aus dem
    # Feldgitter des gefitteten Ausschnitts.
    feld = getattr(erg, "feld", None)
    n_punkte = int(np.size(feld)) if feld is not None else 0
    if 0 < n_punkte < MIN_PUNKTE_FIT:
        gruende.append("zu wenige Punkte")
    if n_punkte >= 2:
        schritt = float(np.ptp(np.asarray(feld, dtype=float))) / (n_punkte - 1)
        if schritt > 0 and np.isfinite(erg.dH) and erg.dH < DH_MIN_FELDSCHRITTE * schritt:
            gruende.append("Linie nicht aufgelöst")

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


#: Kompakte Darstellung der Problemgruende: Gruppe -> (Kuerzel, Titel).
#: A = Anpassung (Residuum/Konvergenz), P = Parameter an Grenze/unplausibel,
#: F = Fenster/Punkte, U = Unsicherheiten.
KRITERIEN_GRUPPEN: dict[str, tuple[str, str]] = {
    "Residuum zu gross": ("A", "Anpassung: normiertes Residuum > %.2f" % RMSE_NORM_SCHWELLE),
    "Chi2 extrem": ("A", "Anpassung: reduziertes Chi² extrem"),
    "keine Konvergenz": ("A", "Anpassung: Optimierer nicht konvergiert"),
    "alpha an Grenze": ("P", "Parameter: α an der Fit-Schranke"),
    "phi an Grenze": ("P", "Parameter: φ an der Schranke"),
    "alpha unphysikalisch": ("P", "Parameter: α über der Plausibilitätsgrenze"),
    "B_res am Fensterrand": ("F", "Fenster: B_res am Rand des Fitfensters"),
    "B_res ausserhalb Fenster": ("F", "Fenster: B_res außerhalb des Fitfensters"),
    "zu wenige Punkte": ("F", "Fenster: weniger als %d Messpunkte" % MIN_PUNKTE_FIT),
    "Linie nicht aufgelöst": ("F", "Fenster: µ₀ΔH unter %.1f Feldschritten" % DH_MIN_FELDSCHRITTE),
    "keine Unsicherheiten": ("U", "Unsicherheit: keine Kovarianz bestimmbar"),
    "B_res-Unsicherheit zu gross": ("U", "Unsicherheit: u(B_res)/B_res > %.0f %%"
                                    % (100 * B_RES_REL_UNSICHERHEIT_MAX)),
    GRUND_NICHT_GEFITTET: ("–", "noch nicht gefittet"),
}


def kriterien_kurz(erg) -> str:
    """Kuerzel der verletzten Kriteriengruppen (z. B. ``"A P"``), ``"OK"`` ohne
    Befund, sonst der Bewertungstext des Nutzers."""
    if getattr(erg, "bewertung", "auto") == "bestaetigt" and not erg.problematisch:
        return "bestätigt"
    gruende = list(getattr(erg, "problem_gruende", []) or [])
    if not gruende:
        return "OK"
    if gruende == [GRUND_NICHT_GEFITTET]:
        return GRUND_NICHT_GEFITTET
    kuerzel = []
    for g in gruende:
        k = KRITERIEN_GRUPPEN.get(g, ("?", g))[0]
        if k not in kuerzel:
            kuerzel.append(k)
    return " ".join(kuerzel) + (" (verworfen)" if getattr(erg, "bewertung", "") == "verworfen" else "")


def kriterien_text(erg) -> str:
    """Klartext aller verletzten Kriterien (eine Zeile je Grund) fuer Tooltips."""
    gruende = list(getattr(erg, "problem_gruende", []) or [])
    if not gruende:
        return "alle Kriterien erfüllt"
    return "\n".join(KRITERIEN_GRUPPEN.get(g, ("?", g))[1] for g in gruende)

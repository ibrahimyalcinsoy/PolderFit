"""AutoWindows: automatische Resonanzsuche und Fenstervorschlag.

Sucht je Frequenz die Resonanz ueber das Magnituden-Extremum (Peak ODER Dip,
nach Untergrundabzug) und legt ein symmetrisches Feldfenster um die Resonanz,
dessen Breite an die geschaetzte Linienbreite gekoppelt ist. Die Grenzen sind
spaeter in der GUI je Frequenz manuell verschiebbar.
"""

from __future__ import annotations

import numpy as np

from ..io.datensatz import Linescan, Messdatensatz
from ..physik.konstanten import GAMMA_STANDARD
from ..physik.fitmodell import schaetze_startwerte


def auto_fenster(
    linescan: Linescan,
    gamma: float = GAMMA_STANDARD,
    breite_faktor: float = 8.0,
) -> tuple[float, float]:
    """Schlaegt (Feld_unten, Feld_oben) um die Resonanz vor.

    Die Fensterbreite ist ``breite_faktor`` mal die geschaetzte Linienbreite,
    begrenzt auf den gemessenen Feldbereich.
    """
    omega = 2.0 * np.pi * linescan.frequenz
    sw = schaetze_startwerte(linescan.feld, linescan.s21, omega, gamma)
    # Linienbreite (Tesla) aus alpha: mu0*DeltaH = 2*omega*alpha/gamma.
    dB = 2.0 * omega * sw.alpha / gamma
    halb = max(breite_faktor * dB / 2.0, 3.0 * (np.ptp(linescan.feld) / linescan.feld.size))
    unten = max(sw.B_res - halb, float(linescan.feld.min()))
    oben = min(sw.B_res + halb, float(linescan.feld.max()))
    if oben <= unten:  # Rueckfall: ganzer Bereich
        unten, oben = float(linescan.feld.min()), float(linescan.feld.max())
    return unten, oben


def auto_fenster_alle(
    datensatz: Messdatensatz,
    gamma: float = GAMMA_STANDARD,
    breite_faktor: float = 8.0,
) -> list[tuple[float, float]]:
    """AutoWindows fuer alle Linescans eines Datensatzes."""
    fenster: list[tuple[float, float]] = []
    for ls in datensatz.linescans:
        try:
            fenster.append(auto_fenster(ls, gamma, breite_faktor))
        except Exception:
            fenster.append((float(ls.feld.min()), float(ls.feld.max())))
    return fenster


def schneide_band(linescan: Linescan, feld_unten: float, feld_oben: float) -> Linescan:
    """Liefert einen neuen Linescan, der auf [feld_unten, feld_oben] beschnitten ist."""
    maske = (linescan.feld >= feld_unten) & (linescan.feld <= feld_oben)
    if maske.sum() < 4:  # zu wenig Punkte -> Original behalten
        return linescan

    def _schnitt(arr):
        return arr[maske] if arr is not None else None

    return Linescan(
        frequenz=linescan.frequenz,
        feld=linescan.feld[maske],
        re=linescan.re[maske],
        im=linescan.im[maske],
        feld_before=_schnitt(linescan.feld_before),
        feld_after=_schnitt(linescan.feld_after),
        temperatur=_schnitt(linescan.temperatur),
    )

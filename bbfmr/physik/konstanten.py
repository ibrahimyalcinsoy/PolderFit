"""Physikalische Konstanten und Einheiten-Konvention.

WICHTIG (verbindlich aus dem Mathematica-Notebook und Kap. 2 der Dissertation):
Alle Magnetfelder werden konsequent als ``mu0*H`` in **Tesla** behandelt
(``mu0H0`` = aeusseres Feld, ``mu0Meff`` = effektive Magnetisierung).
Das gyromagnetische Verhaeltnis ``gamma`` ist in **rad/(s*T)** angegeben.

Niemals H (in A/m) mit mu0H (in T) mischen – das ist laut Protokoll die
wahrscheinlichste Fehlerquelle. Aus den TDMS-Dateien kommen die Felder bereits
in Tesla (``IPS X-Field`` bzw. ``Field-before``).
"""

from __future__ import annotations

import math

#: Magnetische Feldkonstante mu0 [T*m/A].
MU0: float = 4.0e-7 * math.pi

#: Bohrsches Magneton [J/T].
MU_B: float = 9.2740100783e-24

#: Reduziertes Plancksches Wirkungsquantum [J*s].
HBAR: float = 1.054571817e-34

#: Standard-Lande-g-Faktor (typischer Startwert; im Kittel-Fit anpassbar).
G_FAKTOR_STANDARD: float = 2.0


def gamma_aus_g(g: float = G_FAKTOR_STANDARD) -> float:
    """Gyromagnetisches Verhaeltnis ``gamma = g*mu_B/hbar`` in rad/(s*T).

    Fuer ``g = 2`` ergibt sich ``gamma ~ 1.7588e11 rad/(s*T)``. (Der oft zitierte
    Wert ``1.7609e11`` gehoert zum freien Elektron mit ``g_e ~ 2.0023``.)
    """
    return g * MU_B / HBAR


def g_aus_gamma(gamma: float) -> float:
    """Umkehrung von :func:`gamma_aus_g`: liefert den g-Faktor zu ``gamma``."""
    return gamma * HBAR / MU_B


#: Vorberechnetes gamma fuer den Standard-g-Faktor.
GAMMA_STANDARD: float = gamma_aus_g(G_FAKTOR_STANDARD)

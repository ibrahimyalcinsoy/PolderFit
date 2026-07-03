# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Verarbeitungskette fuer den Farbplot (portiert aus pybbfmr, modernisiert).

Operationen: divide-slice (Referenz-Slice-Normierung), derivative-divide
([Maier-Flaig 2018], Gl. (4)) und relation-amplitude (Nachbar-Slice-Division
mit frei waehlbarem Abstand Δn). Siehe :mod:`polderfit.verarbeitung.operationen`
fuer Mathematik und Paper-Referenzen.
"""

from .kette import (
    ANZEIGE_MODI,
    OPERATIONEN,
    KettenSchritt,
    Verarbeitungskette,
    anzeige_transform,
)
from .operationen import derivative_divide, divide_slice, relation_amplitude

__all__ = [
    "ANZEIGE_MODI",
    "OPERATIONEN",
    "KettenSchritt",
    "Verarbeitungskette",
    "anzeige_transform",
    "derivative_divide",
    "divide_slice",
    "relation_amplitude",
]

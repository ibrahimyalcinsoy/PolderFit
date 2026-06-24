"""Einlesen/Schreiben von TDMS und gemeinsame interne Datenstruktur."""

from .datensatz import Linescan, Messdatensatz
from .tdms_laden import lade_tdms
from .tdms_schreiben import schreibe_ergebnis_tdms

__all__ = [
    "Linescan",
    "Messdatensatz",
    "lade_tdms",
    "schreibe_ergebnis_tdms",
]

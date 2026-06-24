"""Sitzungszustand speichern/laden (Fenstergrenzen, Fitparameter) als JSON.

Erlaubt das Fortsetzen einer Auswertung: gespeichert werden Quelle, Gamma,
Fenstergrenzen je Frequenz und die wichtigsten Fitparameter. Die Rohdaten werden
nicht dupliziert, sondern beim Laden erneut aus der TDMS-Quelle gelesen.
"""

from __future__ import annotations

import json

import numpy as np

from ..fit.batch import StapelErgebnis


def _zahl(x):
    if x is None:
        return None
    if isinstance(x, (np.floating, np.integer)):
        return float(x)
    if isinstance(x, float) and np.isnan(x):
        return None
    return x


def speichere_sitzung(stapel: StapelErgebnis, pfad: str) -> None:
    """Serialisiert den Stapelzustand nach JSON."""
    daten = {
        "quelle": stapel.datensatz.quelle,
        "format_typ": stapel.datensatz.format_typ,
        "gamma": stapel.gamma,
        "r2_schwelle": stapel.r2_schwelle,
        "fenster": [[float(u), float(o)] for (u, o) in stapel.fenster],
        "ergebnisse": [
            {k: _zahl(v) for k, v in e.als_zeile().items()} for e in stapel.ergebnisse
        ],
    }
    with open(pfad, "w", encoding="utf-8") as fh:
        json.dump(daten, fh, indent=2, ensure_ascii=False)


def lade_sitzung(pfad: str) -> dict:
    """Laedt einen gespeicherten Sitzungszustand (rohes dict).

    Die TDMS-Quelle (``daten['quelle']``) wird vom Aufrufer erneut eingelesen.
    """
    with open(pfad, encoding="utf-8") as fh:
        return json.load(fh)

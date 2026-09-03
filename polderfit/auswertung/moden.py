# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Kittel/LLG-Auswertung je Mode.

Jede Mode ``k`` hat ihre eigene Ergebnisliste im Stapel
(:meth:`polderfit.fit.batch.StapelErgebnis.ergebnisse_mode`): Mode 1 = die
Hauptliste, Moden >= 2 = Einzelfits in ihrem Korridor. Es gibt keine
Zweig-Zuordnung mehr - die Mode-Nummer ist die Korridor-Nummer und damit ueber
alle Frequenzen konsistent. :func:`auswertung_je_mode` liefert je Mode Punkte,
Kittel-/LLG-Parameter (``auswertung_kittel_llg``) und Fehlertext - gemeinsame
Grundlage fuer das Auswertungsfenster, den Export und das Blatt *Global*.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..fit.linescan_fit import FitErgebnis
from ..physik.konstanten import GAMMA_STANDARD
from .uebersicht import auswertung_kittel_llg, ist_guter_fit

#: Auswahlwert "alle Moden" (jede Mode eigener Kittel-/LLG-Fit).
ALLE_MODEN = -1


def ergebnisse_fuer_mode(stapel, mode: int) -> list[tuple[int, FitErgebnis]]:
    """``(Stapel-Index, Ergebnis)`` je gefittetem Linescan der Mode ``mode``,
    ohne Linescan-Ausreisser (alle Moden) und ohne die Paare ``(index, mode)``
    aus ``stapel.ausreisser_moden``."""
    gesperrt = set(int(i) for i in stapel.ausreisser)
    gesperrt_moden = set((int(i), int(k)) for i, k in stapel.ausreisser_moden)
    paare = []
    for i, e in enumerate(stapel.ergebnisse_mode(mode)):
        if i in gesperrt or (i, int(mode)) in gesperrt_moden:
            continue
        if not getattr(e, "gefittet", True):
            continue
        paare.append((i, e))
    return paare


@dataclass
class ModenReihe:
    """Punkte und Kittel-/LLG-Ergebnis einer Mode (``info`` = None bei Fehler)."""

    mode: int
    indizes: np.ndarray
    f: np.ndarray
    b: np.ndarray
    dh: np.ndarray
    info: dict | None = None
    fehler: str = ""

    @property
    def n(self) -> int:
        return int(self.indizes.size)


def auswertung_je_mode(stapel, modi, geometrie: str = "oop",
                       gamma_fest: bool = False, gamma_start: float = GAMMA_STANDARD,
                       r2_min: float = 0.9, gewichtet: bool = False) -> dict[int, ModenReihe]:
    """Kittel-/LLG-Auswertung fuer jede Mode in ``modi`` (1..n).

    Punktauswahl wie :func:`polderfit.auswertung.uebersicht.auswertung_kittel_llg`
    (:func:`ist_guter_fit`), zusaetzlich ohne Ausreisser. Liefert je Mode eine
    :class:`ModenReihe`; ``info`` ist ``None`` mit ``fehler``-Text, wenn der
    Fit nicht moeglich war (unter 3 Punkte, numerischer Fehler).
    """
    reihen: dict[int, ModenReihe] = {}
    for mode in modi:
        paare = ergebnisse_fuer_mode(stapel, mode)
        gute = [(i, e) for i, e in paare if ist_guter_fit(e, r2_min)]
        reihe = ModenReihe(
            mode=int(mode),
            indizes=np.array([i for i, _ in gute], dtype=int),
            f=np.array([e.frequenz for _, e in gute], dtype=float),
            b=np.array([e.B_res for _, e in gute], dtype=float),
            dh=np.array([e.dH for _, e in gute], dtype=float))
        if len(gute) >= 3:
            try:
                reihe.info = auswertung_kittel_llg(
                    [e for _, e in gute], geometrie=geometrie, gamma_fest=gamma_fest,
                    gamma_start=gamma_start, r2_min=r2_min, gewichtet=gewichtet)
            except Exception as exc:
                reihe.fehler = str(exc)
        else:
            reihe.fehler = "Zu wenige gute Punkte fuer den Kittel-/LLG-Fit (min. 3)."
        reihen[int(mode)] = reihe
    return reihen

# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Zweig-Zuordnung mehrerer Resonanzen und Kittel/LLG-Auswertung je Mode.

Bei ``n_moden > 1`` enthaelt jedes :class:`~polderfit.fit.linescan_fit.FitErgebnis`
mehrere Resonanzen (``moden``, Hauptmode = groesste Signalhoehe zuerst). Die
Position in ``moden`` ist aber KEIN konsistenter Dispersionszweig ueber die
Frequenzen: Die Hauptmode kann zwischen zwei Linescans den Zweig wechseln,
die weiteren Moden stehen in Startwert-Reihenfolge. Fuer eine Kittel-/LLG-
Auswertung **je Mode** braucht es deshalb eine Zuordnung Resonanz -> Zweig.

Regel (:func:`zuordnung_moden`):

1. Gibt es Moden-Baender (Grenzgeraden mit ``mode > 1``, siehe
   :mod:`polderfit.fit.fenster_steuerung`), ist Mode k das Band Mk, in dem
   das Resonanzfeld bei dieser Frequenz liegt (eindeutig).
2. Sonst - und fuer alle nicht eindeutig zugeordneten Resonanzen - gilt die
   Reihenfolge **aufsteigend nach Resonanzfeld** (Mode 1 = niedrigstes Feld).
   Dispersionszweige verschiedener Moden kreuzen sich im Messbereich in der
   Regel nicht, die Feldordnung ist damit ein stabiler Zweig.

Die Auswertung selbst laeuft unveraendert ueber "virtuelle" Ergebnisse, in
denen Mode k zur Hauptmode gemacht wurde (:func:`hauptmode_wechseln`):
:func:`auswertung_je_mode` liefert je Mode Punkte, Kittel-/LLG-Parameter
(``auswertung_kittel_llg``) und Fehlertext - gemeinsame Grundlage fuer das
Auswertungsfenster, den Export und das Blatt *Global*.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..fit.linescan_fit import FitErgebnis, hauptmode_wechseln
from ..physik.konstanten import GAMMA_STANDARD
from .uebersicht import auswertung_kittel_llg, ist_guter_fit

#: Auswahlwert "Hauptmode" (bisheriges Verhalten: Felder des Ergebnisses).
HAUPTMODE = 0
#: Auswahlwert "alle Moden" (jede Mode eigener Kittel-/LLG-Fit).
ALLE_MODEN = -1


def max_moden(ergebnisse: list[FitErgebnis]) -> int:
    """Groesste Modenzahl eines gefitteten Ergebnisses (mindestens 1)."""
    return max((len(e.moden) for e in ergebnisse
                if getattr(e, "gefittet", True) and e.moden), default=1)


def moden_baender_bei(geraden, n_moden: int, frequenz: float,
                      lo: float = -1e6, hi: float = 1e6) -> list:
    """Je Mode 1..n das Feldband (Schnitt der gruenen Seiten ihrer Geraden)
    bei ``frequenz``; ``None`` fuer Moden ohne Geraden oder mit leerem Band.
    Geraden mit ``mode > n`` zaehlen zur Mode ``n``."""
    baender: list = []
    for k in range(1, n_moden + 1):
        gk = [g for g in geraden
              if min(max(int(getattr(g, "mode", 1)), 1), n_moden) == k]
        if not gk:
            baender.append(None)
            continue
        erlaubt = (float(lo), float(hi))
        for g in gk:
            if erlaubt is None:
                break
            erlaubt = g.erlaubtes_intervall(frequenz, erlaubt[0], erlaubt[1])
        baender.append(erlaubt)
    return baender


@dataclass
class ModenZuordnung:
    """Zweig-Nummer je Resonanz (``zweige[index][position]``; ``None`` = keine)."""

    zweige: dict = field(default_factory=dict)
    #: ``"band"`` (Moden-Baender) oder ``"feld"`` (aufsteigend nach Feld).
    regel: str = "feld"
    n_moden: int = 1

    def zweig(self, index: int, position: int) -> int | None:
        labels = self.zweige.get(int(index))
        if labels is None or not (0 <= position < len(labels)):
            return None
        return labels[position]

    def position(self, index: int, mode: int) -> int | None:
        """Position der Mode ``mode`` in ``ergebnisse[index].moden`` (oder None)."""
        labels = self.zweige.get(int(index))
        if not labels:
            return None
        for pos, k in enumerate(labels):
            if k == mode:
                return pos
        return None

    def beschreibung(self, mode: int) -> str:
        """Klartext der Regel fuer die Beschriftung, z. B. ``Band M2``."""
        if mode == HAUPTMODE:
            return "stärkste Resonanz je Linescan"
        if mode == ALLE_MODEN:
            return "alle Zweige"
        if self.regel == "band":
            return f"Band M{mode}"
        return f"{mode}. Resonanz nach Feld"


def zuordnung_moden(ergebnisse: list[FitErgebnis], geraden=None,
                    n_moden: int | None = None,
                    feld_bereich: tuple[float, float] | None = None) -> ModenZuordnung:
    """Ordnet jeder Resonanz einen Zweig 1..n zu (Regel siehe Modulkopf).

    ``geraden``: Grenzgeraden (Moden-Baender, wenn eine ``mode > 1`` traegt);
    ``n_moden``: Stapel-Einstellung (Band-Nummerierung M1..Mn); ``feld_bereich``:
    Feldbereich des Datensatzes fuer die Bandintervalle.
    """
    n_max = max_moden(ergebnisse)
    geraden = list(geraden or [])
    n_stapel = max(1, int(n_moden or 1))
    band_modus = (n_stapel > 1 or n_max > 1) and any(
        int(getattr(g, "mode", 1)) > 1 for g in geraden)
    n = max(n_max, n_stapel) if band_modus else n_max
    lo, hi = feld_bereich if feld_bereich else (-1e6, 1e6)

    zweige: dict = {}
    for i, e in enumerate(ergebnisse):
        if not getattr(e, "gefittet", True):
            continue
        moden = e.moden if e.moden else [{"B_res": e.B_res}]
        b = np.array([float(m.get("B_res", np.nan)) for m in moden], dtype=float)
        labels: list = [None] * len(moden)
        frei = list(range(1, n + 1))
        reihenfolge = [int(p) for p in np.argsort(b) if np.isfinite(b[p])]
        if band_modus:
            baender = moden_baender_bei(geraden, n, e.frequenz, lo, hi)
            for pos in reihenfolge:
                kandidaten = [k for k in frei if baender[k - 1] is not None
                              and baender[k - 1][0] <= b[pos] <= baender[k - 1][1]]
                if len(kandidaten) == 1:
                    labels[pos] = kandidaten[0]
                    frei.remove(kandidaten[0])
        rest = [pos for pos in reihenfolge if labels[pos] is None]
        for pos, k in zip(rest, frei):
            labels[pos] = k
        zweige[i] = labels
    return ModenZuordnung(zweige=zweige, regel="band" if band_modus else "feld", n_moden=n)


def ergebnisse_fuer_mode(ergebnisse: list[FitErgebnis], mode: int,
                         zuordnung: ModenZuordnung | None = None,
                         ausreisser=(), ausreisser_moden=()) -> list[tuple[int, FitErgebnis]]:
    """``(Stapel-Index, Ergebnis)`` je gefittetem Linescan fuer die Auswertung
    der Mode ``mode``.

    ``mode == HAUPTMODE``: die Ergebnisse selbst (bisheriges Verhalten).
    Sonst eine Kopie, in der Mode ``mode`` die Hauptmode ist; Linescans ohne
    diese Mode fehlen. Ausgeschlossen werden Linescan-Ausreisser (fuer alle
    Moden) und die Paare ``(index, mode)`` aus ``ausreisser_moden``.
    """
    gesperrt = set(int(i) for i in ausreisser)
    gesperrt_moden = set((int(i), int(k)) for i, k in ausreisser_moden)
    if zuordnung is None and mode != HAUPTMODE:
        zuordnung = zuordnung_moden(ergebnisse)
    paare = []
    for i, e in enumerate(ergebnisse):
        if i in gesperrt or not getattr(e, "gefittet", True):
            continue
        if mode == HAUPTMODE:
            paare.append((i, e))
            continue
        if (i, mode) in gesperrt_moden:
            continue
        pos = zuordnung.position(i, mode)
        if pos is None:
            continue
        paare.append((i, hauptmode_wechseln(e, pos)))
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


def auswertung_je_mode(ergebnisse: list[FitErgebnis], modi, zuordnung: ModenZuordnung | None = None,
                       ausreisser=(), ausreisser_moden=(), geometrie: str = "oop",
                       gamma_fest: bool = False, gamma_start: float = GAMMA_STANDARD,
                       r2_min: float = 0.9, gewichtet: bool = False) -> dict[int, ModenReihe]:
    """Kittel-/LLG-Auswertung fuer jede Mode in ``modi`` (``HAUPTMODE`` oder 1..n).

    Punktauswahl wie :func:`polderfit.auswertung.uebersicht.auswertung_kittel_llg`
    (:func:`ist_guter_fit`), zusaetzlich ohne Ausreisser. Liefert je Mode eine
    :class:`ModenReihe`; ``info`` ist ``None`` mit ``fehler``-Text, wenn der
    Fit nicht moeglich war (unter 3 Punkte, numerischer Fehler).
    """
    if zuordnung is None:
        zuordnung = zuordnung_moden(ergebnisse)
    reihen: dict[int, ModenReihe] = {}
    for mode in modi:
        paare = ergebnisse_fuer_mode(ergebnisse, mode, zuordnung, ausreisser, ausreisser_moden)
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

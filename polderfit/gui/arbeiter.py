# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Hintergrund-Worker: fuehrt eine Funktion in einem QThread aus.

Haelt die GUI waehrend langer Operationen (TDMS laden, Auto-Fit ueber alle
Frequenzen) reaktionsfaehig und speist Fortschrittsanzeige, Protokoll und
Live-Vorschau. Die auszufuehrende Funktion bekommt einen Callback
``melde(i, n, text="", daten=None, phase=None)``:

* ``i``/``n``   – Fortschritt (``n <= 0``: unbestimmt),
* ``text``      – optionale Protokollzeile,
* ``daten``     – optionaler Zwischenstand (z. B. ein fertiger Einzelfit), den
                  die GUI sofort einzeichnet,
* ``phase``     – optionaler Phasenname ("Fenstersuche", "Einzelfits", …).

``melde.abgebrochen()`` liefert ``True``, sobald der Nutzer den Abbruch
angefordert hat (:meth:`Arbeiter.abbrechen`); lange Schleifen fragen das nach
jedem Schritt ab und beenden sich geordnet. Die Callbacks laufen im
Worker-Thread und werden ueber Qt-Signale (Queued) sicher in den GUI-Thread
zugestellt – Widgets werden hier also NIE direkt angefasst.
"""

from __future__ import annotations

from typing import Callable

from PySide6 import QtCore


class Arbeiter(QtCore.QObject):
    """Fuehrt ``funktion(melde)`` im Hintergrund aus und meldet den Verlauf."""

    fortschritt = QtCore.Signal(int, int)   # (i, n) -> Fortschrittsbalken
    protokoll = QtCore.Signal(str)          # eine Protokollzeile
    zwischenstand = QtCore.Signal(object)   # Live-Vorschau (z. B. Einzelfit)
    phase = QtCore.Signal(str)              # Phasenname
    fertig = QtCore.Signal(object)          # Rueckgabewert der Funktion
    fehler = QtCore.Signal(str)             # Fehlertext (mit Traceback)

    def __init__(self, funktion: Callable):
        super().__init__()
        self._funktion = funktion
        self._abbruch = False
        self._letzte_phase: str | None = None

    def abbrechen(self) -> None:
        """Abbruch anfordern (thread-sicher: einfacher Flag, nur gelesen/gesetzt)."""
        self._abbruch = True

    def abbruch_angefordert(self) -> bool:
        return self._abbruch

    def _melde(self, i: int, n: int, text: str = "", daten=None, phase: str | None = None) -> None:
        """Vom Arbeitscode aufgerufener Fortschritts-Callback."""
        if phase is not None and phase != self._letzte_phase:
            self._letzte_phase = phase
            self.phase.emit(str(phase))
        self.fortschritt.emit(int(i), int(n))
        if text:
            self.protokoll.emit(text)
        if daten is not None:
            self.zwischenstand.emit(daten)

    @QtCore.Slot()
    def ausfuehren(self) -> None:
        """Im Worker-Thread ausgefuehrt (mit ``QThread.started`` verbunden)."""
        # Call-Trace (falls aktiv) im EIGENEN Thread installieren – QThreads erben
        # sys.setprofile nicht. Der Tracer meldet threadsicher per Qt-Signal.
        from .trace_panel import aktiver_tracer
        tracer = aktiver_tracer()
        if tracer is not None:
            tracer.installiere_hier()

        def melde(i, n, text="", daten=None, phase=None):
            self._melde(i, n, text, daten, phase)

        melde.abgebrochen = self.abbruch_angefordert
        try:
            ergebnis = self._funktion(melde)
        except Exception as exc:  # an die GUI melden statt den Thread zu killen
            import traceback
            self.fehler.emit(f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}")
            return
        finally:
            if tracer is not None:
                tracer.entferne_hier()
        self.fertig.emit(ergebnis)

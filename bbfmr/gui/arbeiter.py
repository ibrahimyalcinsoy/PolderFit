"""Hintergrund-Worker: fuehrt eine Funktion in einem QThread aus.

Haelt die GUI waehrend langer Operationen (TDMS laden, Auto-Fit ueber alle
Frequenzen) reaktionsfaehig und speist das Aktivitaetsprotokoll live. Die
auszufuehrende Funktion bekommt einen ``melde(i, n, text)``-Callback, mit dem sie
Fortschritt (``i`` von ``n``) und optionale Protokollzeilen senden kann. Die
Callbacks laufen im Worker-Thread und werden ueber Qt-Signale (Queued) sicher in
den GUI-Thread zugestellt – Widgets werden hier also NIE direkt angefasst.
"""

from __future__ import annotations

from typing import Callable

from PySide6 import QtCore


class Arbeiter(QtCore.QObject):
    """Fuehrt ``funktion(melde)`` im Hintergrund aus und meldet den Verlauf."""

    fortschritt = QtCore.Signal(int, int)   # (i, n) -> Fortschrittsbalken
    protokoll = QtCore.Signal(str)          # eine Protokollzeile
    fertig = QtCore.Signal(object)          # Rueckgabewert der Funktion
    fehler = QtCore.Signal(str)             # Fehlertext (mit Traceback)

    def __init__(self, funktion: Callable):
        super().__init__()
        self._funktion = funktion

    def _melde(self, i: int, n: int, text: str = "") -> None:
        """Vom Arbeitscode aufgerufener Fortschritts-Callback."""
        self.fortschritt.emit(int(i), int(n))
        if text:
            self.protokoll.emit(text)

    @QtCore.Slot()
    def ausfuehren(self) -> None:
        """Im Worker-Thread ausgefuehrt (mit ``QThread.started`` verbunden)."""
        try:
            ergebnis = self._funktion(self._melde)
        except Exception as exc:  # an die GUI melden statt den Thread zu killen
            import traceback
            self.fehler.emit(f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}")
            return
        self.fertig.emit(ergebnis)

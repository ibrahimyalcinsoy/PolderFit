# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Call-Trace-Panel: zeigt live, welche polderfit-Funktionen aufgerufen werden.

Ein optionales Entwickler-Werkzeug zur Fehlersuche und beim Ändern des Programms.
Standardmäßig inaktiv; das Aktivieren installiert einen ``sys.setprofile``-Tracer,
der ausschließlich Aufrufe innerhalb des ``polderfit``-Pakets meldet (nach
Aufruftiefe eingerückt). Da lange Rechnungen im Hintergrund-Thread laufen
(:mod:`polderfit.gui.arbeiter`), werden die Zeilen über ein Qt-Signal threadsicher
in den GUI-Thread zugestellt; der Arbeiter installiert den Profiler in seinem
eigenen Thread über :func:`aktiver_tracer`.
"""

from __future__ import annotations

import os
import sys
import threading

from PySide6 import QtCore, QtGui, QtWidgets

import polderfit

#: Wurzelpfad des Pakets – der Filter lässt nur Frames aus diesem Baum durch.
_PAKET_PFAD = os.path.dirname(os.path.abspath(polderfit.__file__))

#: Der gerade aktive Tracer (oder ``None``). Der Hintergrund-Arbeiter liest ihn,
#: um den Profiler in SEINEM Thread zu installieren (QThreads erben ``setprofile``
#: nicht automatisch).
_aktiver: "FunktionsTracer | None" = None


def aktiver_tracer() -> "FunktionsTracer | None":
    """Liefert den aktiven Tracer, damit andere Threads ihn installieren können."""
    return _aktiver


class FunktionsTracer(QtCore.QObject):
    """``sys.setprofile``-Tracer, gefiltert auf das ``polderfit``-Paket.

    Meldet jeden Funktionsaufruf über das ``zeile``-Signal; Qt stellt es
    threadsicher (Queued) im GUI-Thread zu. Aktivieren kostet Profiling-Overhead
    und ist daher nur zur Fehlersuche gedacht.
    """

    zeile = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tiefe: dict[int, int] = {}  # Aufruftiefe je Thread-id

    def _profil(self, frame, event, arg):
        # Nur Python-Aufrufe/-Returns im eigenen Paket; C-Aufrufe ignorieren.
        if event not in ("call", "return"):
            return
        code = frame.f_code
        if not code.co_filename.startswith(_PAKET_PFAD):
            return
        tid = threading.get_ident()
        if event == "call":
            tiefe = self._tiefe.get(tid, 0)
            modul = frame.f_globals.get("__name__", "?").replace("polderfit.", "")
            self.zeile.emit("  " * tiefe + f"{modul}.{code.co_name}()")
            self._tiefe[tid] = tiefe + 1
        else:  # return
            self._tiefe[tid] = max(0, self._tiefe.get(tid, 0) - 1)

    def installiere_hier(self) -> None:
        """Installiert den Profiler im AKTUELLEN Thread (vom Arbeiter genutzt)."""
        sys.setprofile(self._profil)

    def entferne_hier(self) -> None:
        sys.setprofile(None)

    def aktiviere(self) -> None:
        """Schaltet das Tracing ein (aktueller Thread + künftige Hintergrund-Jobs)."""
        global _aktiver
        _aktiver = self
        self._tiefe.clear()
        self.installiere_hier()

    def deaktiviere(self) -> None:
        global _aktiver
        if _aktiver is self:
            _aktiver = None
        self.entferne_hier()
        self._tiefe.clear()


class TracePanel(QtWidgets.QWidget):
    """Bedien- und Anzeigefläche des Call-Trace (Checkbox + Live-Protokoll)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tracer = FunktionsTracer(self)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)

        kopf = QtWidgets.QHBoxLayout()
        self.chk_aktiv = QtWidgets.QCheckBox("Tracing aktiv")
        self.chk_aktiv.setToolTip(
            "Zeigt live, welche polderfit-Funktionen aufgerufen werden. Nur zur "
            "Fehlersuche einschalten – das Profiling kostet Rechenzeit.")
        self.chk_aktiv.toggled.connect(self._umschalten)
        kopf.addWidget(self.chk_aktiv)
        kopf.addStretch(1)
        leeren = QtWidgets.QPushButton("Leeren")
        leeren.clicked.connect(lambda: self.ansicht.clear())
        kopf.addWidget(leeren)
        lay.addLayout(kopf)

        self.ansicht = QtWidgets.QPlainTextEdit()
        self.ansicht.setReadOnly(True)
        self.ansicht.setMaximumBlockCount(5000)  # begrenzt den Speicher bei hoher Aufruffrequenz
        mono = QtGui.QFont("monospace")
        mono.setStyleHint(QtGui.QFont.Monospace)
        mono.setPointSize(9)
        self.ansicht.setFont(mono)
        lay.addWidget(self.ansicht, 1)

        self.tracer.zeile.connect(self._auf_zeile)

    def _auf_zeile(self, text: str) -> None:
        self.ansicht.appendPlainText(text)

    def _umschalten(self, an: bool) -> None:
        if an:
            self.tracer.aktiviere()
        else:
            self.tracer.deaktiviere()

    def ist_aktiv(self) -> bool:
        return self.chk_aktiv.isChecked()

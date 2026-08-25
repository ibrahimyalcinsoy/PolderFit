# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Kleine, wiederverwendete Bedienelemente.

*Ruhige* Eingabefelder: Spin-Boxen und Auswahllisten reagieren auf das
Mausrad NUR, wenn sie den Tastaturfokus haben. Sonst aendert ein Scrollen
ueber einem Panel (typisch unter Windows mit Touchpad/Mausrad) unbemerkt
Werte wie Δn oder den Referenz-Index - das war der Ausloeser des
"schrumpfenden Farbplots" und ist grundsaetzlich ein Bedienrisiko
(DIN EN ISO 9241-110: Fehlertoleranz, Erwartungskonformitaet).
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class _RuhigMixin:
    """Mausrad nur mit Fokus; sonst wird das Ereignis an den Scrollbereich weitergereicht."""

    def _ruhig_einrichten(self) -> None:
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def wheelEvent(self, event):  # noqa: N802 (Qt-Name)
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


class RuhigeSpinBox(_RuhigMixin, QtWidgets.QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ruhig_einrichten()


class RuhigeDoubleSpinBox(_RuhigMixin, QtWidgets.QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ruhig_einrichten()


class RuhigeComboBox(_RuhigMixin, QtWidgets.QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ruhig_einrichten()

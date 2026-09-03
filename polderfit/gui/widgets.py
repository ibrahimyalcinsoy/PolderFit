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
        # Sichtbare, klickbare Knoepfe unabhaengig vom Stylesheet: +/- statt
        # Pfeil-Bildern (die das QSS sonst verschluckt).
        if isinstance(self, QtWidgets.QAbstractSpinBox):
            self.setButtonSymbols(QtWidgets.QAbstractSpinBox.PlusMinus)

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
    """Zusaetzlich: Punkt UND Komma gelten als Dezimalzeichen.

    Unter deutscher Locale ist der Punkt Tausendertrennzeichen - ein getipptes
    „5.51" wurde stillschweigend zu 55 (der Punkt verschluckt, die letzte
    Ziffer verworfen), unter englischer Locale entsprechend ein Komma. Das
    fremde Zeichen wird beim Tippen in das Dezimalzeichen der Locale
    umgeschrieben, solange dieses nicht selbst im Text vorkommt (ein
    eingefuegtes „1.234,5" bleibt unangetastet). Getippte Tausendertrenner
    werden bewusst nicht unterstuetzt: physikalische Groessen wie „1.234 T"
    sind mit Punkt als Dezimalzeichen gemeint, nicht als 1234 T.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ruhig_einrichten()

    def _dezimal_normiert(self, text: str) -> str:
        dezimal = str(self.locale().decimalPoint())
        fremd = "," if dezimal == "." else "."
        if fremd in text and dezimal not in text:
            return text.replace(fremd, dezimal)
        return text

    def validate(self, text: str, pos: int):  # noqa: N802 (Qt-Name)
        return super().validate(self._dezimal_normiert(text), pos)

    def valueFromText(self, text: str) -> float:  # noqa: N802 (Qt-Name)
        return super().valueFromText(self._dezimal_normiert(text))


class RuhigeComboBox(_RuhigMixin, QtWidgets.QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ruhig_einrichten()

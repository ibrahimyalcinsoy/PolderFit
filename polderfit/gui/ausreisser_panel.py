# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Ausreisser-Panel: Liste der ausgeschlossenen Punkte, Undo, Wiederaufnahme.

Als Ausreisser markierte Fit-Punkte (Klick/Kasten im Farbplot, Toolbar-Modus
"Ausreisser markieren") verschwinden aus der Darstellung und aus allen
uebergreifenden Rechnungen (insb. Kittel-/LLG-Fit). Dieses Panel macht die
Ausschluesse einsehbar und editierbar: einzeln oder komplett wieder
aufnehmen, letzter Schritt rueckgaengig.
"""

from __future__ import annotations

from PySide6 import QtWidgets


class AusreisserPanel(QtWidgets.QWidget):
    """Liste + Bedienung der Ausreisser-Ausschluesse.

    Callbacks: ``wieder_aufnehmen(indizes)``, ``rueckgaengig()``.
    """

    def __init__(self, wieder_aufnehmen=None, rueckgaengig=None, parent=None):
        super().__init__(parent)
        self._cb_wieder = wieder_aufnehmen
        self._cb_rueckgaengig = rueckgaengig
        self._indizes: list[int] = []

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

        hinweis = QtWidgets.QLabel(
            "Toolbar → „Ausreisser markieren“: Punkte im Farbplot anklicken oder "
            "per Kasten markieren. Markierte Punkte fliegen aus Darstellung und "
            "Kittel-/LLG-Fit.")
        hinweis.setWordWrap(True)
        lay.addWidget(hinweis)

        self.anzahl_label = QtWidgets.QLabel("Keine Ausreisser markiert.")
        lay.addWidget(self.anzahl_label)

        self.liste = QtWidgets.QListWidget()
        self.liste.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        lay.addWidget(self.liste, 1)

        knopfreihe = QtWidgets.QHBoxLayout()
        self.btn_wieder = QtWidgets.QPushButton("Wieder aufnehmen")
        self.btn_wieder.setToolTip("Ausgewaehlte Punkte wieder in die Auswertung aufnehmen.")
        self.btn_wieder.clicked.connect(self._wieder_geklickt)
        knopfreihe.addWidget(self.btn_wieder)
        self.btn_alle = QtWidgets.QPushButton("Alle wieder aufnehmen")
        self.btn_alle.clicked.connect(self._alle_geklickt)
        knopfreihe.addWidget(self.btn_alle)
        lay.addLayout(knopfreihe)

        self.btn_rueckgaengig = QtWidgets.QPushButton("Rueckgaengig (letzter Schritt)")
        self.btn_rueckgaengig.clicked.connect(
            lambda: self._cb_rueckgaengig and self._cb_rueckgaengig())
        lay.addWidget(self.btn_rueckgaengig)

    def zeige_ausreisser(self, stapel) -> None:
        """Fuellt die Liste aus dem Stapel (Index, Frequenz, B_res)."""
        self.liste.clear()
        self._indizes = list(stapel.ausreisser) if stapel is not None else []
        for i in self._indizes:
            e = stapel.ergebnisse[i]
            self.liste.addItem(
                f"#{i}:  f = {e.frequenz / 1e9:7.3f} GHz,  "
                f"B_res = {e.B_res:.4f} T"
                + ("  (problematisch)" if e.problematisch else ""))
        n = len(self._indizes)
        self.anzahl_label.setText(
            "Keine Ausreisser markiert." if n == 0
            else f"{n} Punkt(e) ausgeschlossen - fehlen in Darstellung und Kittel/LLG.")

    def gewaehlte_indizes(self) -> list[int]:
        """Stapel-Indizes der in der Liste ausgewaehlten Eintraege."""
        return [self._indizes[reihe.row()] for reihe in self.liste.selectedIndexes()]

    def _wieder_geklickt(self) -> None:
        indizes = self.gewaehlte_indizes()
        if indizes and self._cb_wieder is not None:
            self._cb_wieder(indizes)

    def _alle_geklickt(self) -> None:
        if self._indizes and self._cb_wieder is not None:
            self._cb_wieder(list(self._indizes))

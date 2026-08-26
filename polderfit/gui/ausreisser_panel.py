# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Ausreisser-Panel: Liste der ausgeschlossenen Punkte, Undo, Wiederaufnahme.

Als Ausreisser markierte Fit-Punkte (Klick/Kasten im Farbplot, Modus
"Ausreisser markieren") verschwinden aus der Darstellung und aus allen
uebergreifenden Rechnungen (insb. Kittel-/LLG-Fit). Dieses Panel macht die
Ausschluesse einsehbar und editierbar: einzeln oder komplett wieder
aufnehmen, letzter Schritt rueckgaengig.
"""

from __future__ import annotations

import numpy as np
from PySide6 import QtWidgets

from ..auswertung.moden import zuordnung_moden


class AusreisserPanel(QtWidgets.QWidget):
    """Liste + Bedienung der Ausreisser-Ausschluesse.

    Callbacks: ``wieder_aufnehmen(indizes)`` (Linescans), ``rueckgaengig()``,
    ``wieder_aufnehmen_moden(paare)`` fuer die nur je Mode ausgeschlossenen
    Punkte ``(index, mode)`` der Kittel/LLG-Auswertung.
    """

    def __init__(self, wieder_aufnehmen=None, rueckgaengig=None, parent=None,
                 wieder_aufnehmen_moden=None):
        super().__init__(parent)
        self._cb_wieder = wieder_aufnehmen
        self._cb_wieder_moden = wieder_aufnehmen_moden
        self._cb_rueckgaengig = rueckgaengig
        self._indizes: list[int] = []
        #: Listeneintraege: ``("linescan", i)`` oder ``("mode", i, k)``.
        self._eintraege: list[tuple] = []

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

        hinweis = QtWidgets.QLabel(
            "Funktionen → „Ausreißer markieren“ (Strg+M): Punkte im Farbplot "
            "anklicken oder per Kasten markieren. Markierte Punkte gelten als "
            "„ignoriert“ (grau) und fehlen in Darstellung und Kittel-/LLG-Fit. "
            "Im Kittel-Fenster (Strg+K) in einer Mode-Ansicht entfernte Punkte "
            "fehlen nur in der Auswertung dieser Mode.")
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
        """Fuellt die Liste aus dem Stapel: Linescan-Ausreisser (Index, Frequenz,
        B_res) und danach die nur je Mode ausgeschlossenen Punkte."""
        self.liste.clear()
        self._indizes = list(stapel.ausreisser) if stapel is not None else []
        self._eintraege = []
        for i in self._indizes:
            e = stapel.ergebnisse[i]
            self._eintraege.append(("linescan", i))
            self.liste.addItem(
                f"#{i}:  f = {e.frequenz / 1e9:7.3f} GHz,  "
                f"B_res = {e.B_res:.4f} T"
                + ("  (problematisch)" if e.problematisch else ""))
        paare = list(getattr(stapel, "ausreisser_moden", []) or []) if stapel is not None else []
        if paare:
            zuordnung = zuordnung_moden(stapel.ergebnisse, n_moden=getattr(stapel, "n_moden", 1))
            for i, k in paare:
                if not (0 <= i < len(stapel.ergebnisse)):
                    continue
                e = stapel.ergebnisse[i]
                pos = zuordnung.position(i, k)
                b = (e.moden[pos]["B_res"] if (pos is not None and e.moden and pos < len(e.moden))
                     else np.nan)
                self._eintraege.append(("mode", int(i), int(k)))
                self.liste.addItem(
                    f"#{i} · Mode {k}:  f = {e.frequenz / 1e9:7.3f} GHz,  "
                    f"B_res = {b:.4f} T  (nur Kittel/LLG dieser Mode)")
        n = len(self._indizes)
        text = ("Keine Ausreisser markiert." if n == 0
                else f"{n} Punkt(e) ausgeschlossen - fehlen in Darstellung und Kittel/LLG.")
        if paare:
            text += f" Zusaetzlich {len(paare)} Punkt(e) nur je Mode ausgeschlossen."
        self.anzahl_label.setText(text)

    def gewaehlte_indizes(self) -> list[int]:
        """Stapel-Indizes der in der Liste ausgewaehlten Linescan-Eintraege."""
        return [self._eintraege[r.row()][1] for r in self.liste.selectedIndexes()
                if self._eintraege[r.row()][0] == "linescan"]

    def gewaehlte_moden_paare(self) -> list[tuple[int, int]]:
        """``(index, mode)`` der ausgewaehlten Nur-je-Mode-Eintraege."""
        return [(self._eintraege[r.row()][1], self._eintraege[r.row()][2])
                for r in self.liste.selectedIndexes() if self._eintraege[r.row()][0] == "mode"]

    def _wieder_geklickt(self) -> None:
        indizes = self.gewaehlte_indizes()
        if indizes and self._cb_wieder is not None:
            self._cb_wieder(indizes)
        paare = self.gewaehlte_moden_paare()
        if paare and self._cb_wieder_moden is not None:
            self._cb_wieder_moden(paare)

    def _alle_geklickt(self) -> None:
        if self._indizes and self._cb_wieder is not None:
            self._cb_wieder(list(self._indizes))
        paare = [(e[1], e[2]) for e in self._eintraege if e[0] == "mode"]
        if paare and self._cb_wieder_moden is not None:
            self._cb_wieder_moden(paare)

# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Bedienpanel der Ausschlusszonen.

Ausschlusszonen nehmen Messpunkte (Rechteck Feld x Frequenz) aus allen
(Nach-)Fits aus - z. B. ein stoerendes, feldparalleles Artefakt. Das Zeichnen
laeuft als exklusiver Interaktionsmodus im Farbplot (Modus-Manager des
Hauptfensters); der Knopf zeigt den aktiven Modus als gedrueckten Zustand.

Kernlogik: :mod:`polderfit.fit.fenster_steuerung`.
"""

from __future__ import annotations

from PySide6 import QtWidgets


class ZonenPanel(QtWidgets.QWidget):
    """Liste und Steuerung der Ausschlusszonen.

    Callbacks des Hauptfensters:

    * ``zone_umschalten(an: bool)`` – Zeichenmodus starten/abbrechen
    * ``zone_entfernen(index: int)``
    """

    def __init__(self, zone_umschalten=None, zone_entfernen=None, parent=None):
        super().__init__(parent)
        self._cb_zone_umschalten = zone_umschalten
        self._cb_zone_entfernen = zone_entfernen

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

        hinweis = QtWidgets.QLabel(
            "Messpunkte in einer Zone werden aus ALLEN (Nach-)Fits ausgenommen; "
            "betroffene Linescans fitten sofort neu.")
        hinweis.setWordWrap(True)
        lay.addWidget(hinweis)

        self.btn_zone = QtWidgets.QPushButton("Zone im Farbplot einzeichnen")
        self.btn_zone.setCheckable(True)
        self.btn_zone.setToolTip(
            "Modus starten und Rechteck im Farbplot aufziehen.\n"
            "Esc oder erneuter Klick bricht ab.")
        self.btn_zone.toggled.connect(self._zone_umgeschaltet)
        lay.addWidget(self.btn_zone)

        self.zonen_liste = QtWidgets.QListWidget()
        self.zonen_liste.setMaximumHeight(140)
        lay.addWidget(self.zonen_liste)

        self.btn_zone_entfernen = QtWidgets.QPushButton("Gewaehlte Zone entfernen")
        self.btn_zone_entfernen.clicked.connect(self._zone_entfernen_geklickt)
        lay.addWidget(self.btn_zone_entfernen)
        lay.addStretch(1)

    # --- Zustand ---------------------------------------------------------------
    def setze_zonen(self, zonen) -> None:
        """Fuellt die (einsehbare, editierbare) Zonenliste."""
        self.zonen_liste.clear()
        for zone in zonen:
            self.zonen_liste.addItem(
                f"{zone.feld_min:.3f}–{zone.feld_max:.3f} T, "
                f"{zone.frequenz_min/1e9:.2f}–{zone.frequenz_max/1e9:.2f} GHz")

    def setze_modus_aktiv(self, an: bool) -> None:
        """Synchronisiert den Knopf mit dem Modus-Manager (ohne Rueckruf-Schleife)."""
        if self.btn_zone.isChecked() != bool(an):
            self.btn_zone.blockSignals(True)
            self.btn_zone.setChecked(bool(an))
            self.btn_zone.blockSignals(False)

    # --- intern ------------------------------------------------------------------
    def _zone_umgeschaltet(self, an: bool) -> None:
        if self._cb_zone_umschalten is not None:
            self._cb_zone_umschalten(bool(an))

    def _zone_entfernen_geklickt(self) -> None:
        zeile = self.zonen_liste.currentRow()
        if zeile >= 0 and self._cb_zone_entfernen is not None:
            self._cb_zone_entfernen(zeile)

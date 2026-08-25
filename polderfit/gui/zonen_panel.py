# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Bedienpanel der Nachfit-Bereiche: Ausschlusszonen und Grenzgeraden.

*Ausschlusszonen* nehmen Messpunkte (Rechteck Feld x Frequenz) aus allen
(Nach-)Fits aus - z. B. ein stoerendes, feldparalleles Artefakt.

*Grenzgeraden* werden wie in einem Textprogramm eingefuegt (zwei Klicks im
Farbplot, danach an den Endpunkten ziehbar -> verschieben/rotieren). Die
GRUENE Seite wird beim Grenzgeraden-Fit neu gefittet, die ROTE ignoriert;
mit zwei Geraden entsteht ein Band. Beide Zeichenwerkzeuge laufen als
exklusive Interaktionsmodi (Modus-Manager des Hauptfensters); die Knoepfe
zeigen den aktiven Modus als gedrueckten Zustand.

Kernlogik: :mod:`polderfit.fit.fenster_steuerung`.
"""

from __future__ import annotations

from PySide6 import QtWidgets


class ZonenPanel(QtWidgets.QWidget):
    """Listen und Steuerung der Ausschlusszonen und Grenzgeraden.

    Callbacks des Hauptfensters:

    * ``zone_umschalten(an: bool)`` – Zonen-Zeichenmodus starten/abbrechen
    * ``zone_entfernen(index: int)``
    * ``gerade_umschalten(an: bool)`` – Geraden-Zeichenmodus starten/abbrechen
    * ``gerade_seite(index: int)`` – gruene Seite der Geraden wechseln
    * ``gerade_entfernen(index: int)``
    * ``geraden_fit()`` – gruenen Bereich neu fitten
    """

    def __init__(self, zone_umschalten=None, zone_entfernen=None,
                 gerade_umschalten=None, gerade_seite=None,
                 gerade_entfernen=None, geraden_fit=None, parent=None):
        super().__init__(parent)
        self._cb_zone_umschalten = zone_umschalten
        self._cb_zone_entfernen = zone_entfernen
        self._cb_gerade_umschalten = gerade_umschalten
        self._cb_gerade_seite = gerade_seite
        self._cb_gerade_entfernen = gerade_entfernen
        self._cb_geraden_fit = geraden_fit

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

        # --- Grenzgeraden -----------------------------------------------------
        grp_geraden = QtWidgets.QGroupBox("Grenzgeraden (Neu-Fit-Bereich)")
        geraden_lay = QtWidgets.QVBoxLayout(grp_geraden)
        hinweis_g = QtWidgets.QLabel(
            "Gerade per zwei Klicks einfügen, an den Endpunkten ziehen "
            "(verschieben/rotieren). Grüner Saum = wird gefittet, "
            "roter Saum = wird ignoriert; Doppelklick auf die Linie wechselt "
            "die Seite. Zwei Geraden ergeben ein Band. Funktioniert direkt "
            "nach dem Laden – ohne Auto-Fit wird nur der grüne Bereich gefittet.")
        hinweis_g.setWordWrap(True)
        geraden_lay.addWidget(hinweis_g)

        self.btn_gerade = QtWidgets.QPushButton("Gerade einzeichnen (2 Klicks)")
        self.btn_gerade.setCheckable(True)
        self.btn_gerade.setToolTip(
            "Modus starten und zwei Punkte im Farbplot klicken.\n"
            "Esc oder erneuter Klick bricht ab.")
        self.btn_gerade.toggled.connect(self._gerade_umgeschaltet)
        geraden_lay.addWidget(self.btn_gerade)

        self.geraden_liste = QtWidgets.QListWidget()
        self.geraden_liste.setMaximumHeight(110)
        geraden_lay.addWidget(self.geraden_liste)

        zeile = QtWidgets.QHBoxLayout()
        self.btn_gerade_seite = QtWidgets.QPushButton("Seite wechseln")
        self.btn_gerade_seite.setToolTip(
            "Gruene (Neu-Fit-) und rote (Ignorier-)Seite der gewaehlten "
            "Geraden tauschen. Geht auch per Doppelklick auf die Linie.")
        self.btn_gerade_seite.clicked.connect(self._gerade_seite_geklickt)
        zeile.addWidget(self.btn_gerade_seite)
        self.btn_gerade_entfernen = QtWidgets.QPushButton("Entfernen")
        self.btn_gerade_entfernen.clicked.connect(self._gerade_entfernen_geklickt)
        zeile.addWidget(self.btn_gerade_entfernen)
        geraden_lay.addLayout(zeile)

        self.btn_geraden_fit = QtWidgets.QPushButton("Grünen Bereich fitten …")
        self.btn_geraden_fit.setToolTip(
            "Fenstersuche und Fit im grünen Bereich aller Geraden; im Dialog:\n"
            "Frequenz von … bis …, Feld von … bis …, Modus, Fensterbreite,\n"
            "Anzahl Resonanzen.")
        self.btn_geraden_fit.clicked.connect(
            lambda: self._cb_geraden_fit and self._cb_geraden_fit())
        geraden_lay.addWidget(self.btn_geraden_fit)
        lay.addWidget(grp_geraden)

        # --- Ausschlusszonen --------------------------------------------------
        grp_zonen = QtWidgets.QGroupBox("Ausschlusszonen")
        zonen_lay = QtWidgets.QVBoxLayout(grp_zonen)
        hinweis_z = QtWidgets.QLabel(
            "Messpunkte in einer Zone werden aus ALLEN (Nach-)Fits ausgenommen; "
            "bereits gefittete Linescans im Band rechnen sofort neu.")
        hinweis_z.setWordWrap(True)
        zonen_lay.addWidget(hinweis_z)

        self.btn_zone = QtWidgets.QPushButton("Zone im Farbplot einzeichnen")
        self.btn_zone.setCheckable(True)
        self.btn_zone.setToolTip(
            "Modus starten und Rechteck im Farbplot aufziehen.\n"
            "Esc oder erneuter Klick bricht ab.")
        self.btn_zone.toggled.connect(self._zone_umgeschaltet)
        zonen_lay.addWidget(self.btn_zone)

        self.zonen_liste = QtWidgets.QListWidget()
        self.zonen_liste.setMaximumHeight(110)
        zonen_lay.addWidget(self.zonen_liste)

        self.btn_zone_entfernen = QtWidgets.QPushButton("Gewaehlte Zone entfernen")
        self.btn_zone_entfernen.clicked.connect(self._zone_entfernen_geklickt)
        zonen_lay.addWidget(self.btn_zone_entfernen)
        lay.addWidget(grp_zonen)
        lay.addStretch(1)

    # --- Zustand ---------------------------------------------------------------
    def setze_zonen(self, zonen) -> None:
        """Fuellt die (einsehbare, editierbare) Zonenliste."""
        self.zonen_liste.clear()
        for zone in zonen:
            self.zonen_liste.addItem(
                f"{zone.feld_min:.3f}–{zone.feld_max:.3f} T, "
                f"{zone.frequenz_min/1e9:.2f}–{zone.frequenz_max/1e9:.2f} GHz")

    def setze_geraden(self, geraden) -> None:
        """Fuellt die Geradenliste (Handgriffe + gruene Seite)."""
        gewaehlt = self.geraden_liste.currentRow()
        self.geraden_liste.clear()
        for gerade in geraden:
            seite = "+" if gerade.gruen_positiv else "−"
            self.geraden_liste.addItem(
                f"({gerade.b1:.3f} T, {gerade.f1/1e9:.2f} GHz) – "
                f"({gerade.b2:.3f} T, {gerade.f2/1e9:.2f} GHz)  · grün: {seite}")
        if 0 <= gewaehlt < self.geraden_liste.count():
            self.geraden_liste.setCurrentRow(gewaehlt)

    def setze_modus_aktiv(self, an: bool) -> None:
        """Synchronisiert den Zonen-Knopf mit dem Modus-Manager (ohne Rueckruf)."""
        self._knopf_syncen(self.btn_zone, an)

    def setze_gerade_modus_aktiv(self, an: bool) -> None:
        """Synchronisiert den Geraden-Knopf mit dem Modus-Manager (ohne Rueckruf)."""
        self._knopf_syncen(self.btn_gerade, an)

    @staticmethod
    def _knopf_syncen(knopf: QtWidgets.QPushButton, an: bool) -> None:
        if knopf.isChecked() != bool(an):
            knopf.blockSignals(True)
            knopf.setChecked(bool(an))
            knopf.blockSignals(False)

    # --- intern ------------------------------------------------------------------
    def _zone_umgeschaltet(self, an: bool) -> None:
        if self._cb_zone_umschalten is not None:
            self._cb_zone_umschalten(bool(an))

    def _zone_entfernen_geklickt(self) -> None:
        zeile = self.zonen_liste.currentRow()
        if zeile >= 0 and self._cb_zone_entfernen is not None:
            self._cb_zone_entfernen(zeile)

    def _gerade_umgeschaltet(self, an: bool) -> None:
        if self._cb_gerade_umschalten is not None:
            self._cb_gerade_umschalten(bool(an))

    def _gerade_seite_geklickt(self) -> None:
        zeile = self.geraden_liste.currentRow()
        if zeile >= 0 and self._cb_gerade_seite is not None:
            self._cb_gerade_seite(zeile)

    def _gerade_entfernen_geklickt(self) -> None:
        zeile = self.geraden_liste.currentRow()
        if zeile >= 0 and self._cb_gerade_entfernen is not None:
            self._cb_gerade_entfernen(zeile)

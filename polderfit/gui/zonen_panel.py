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

from .widgets import RuhigeComboBox, RuhigeSpinBox


class ZonenPanel(QtWidgets.QWidget):
    """Listen und Steuerung der Ausschlusszonen und Grenzgeraden.

    Callbacks des Hauptfensters:

    * ``zone_umschalten(an: bool)`` – Zonen-Zeichenmodus starten/abbrechen
    * ``zone_entfernen(index: int)``
    * ``gerade_umschalten(an: bool)`` – Geraden-Zeichenmodus starten/abbrechen
    * ``gerade_seite(index: int)`` – gruene Seite der Geraden wechseln
    * ``gerade_entfernen(index: int)``
    * ``geraden_fit()`` – gruenen Bereich neu fitten
    * ``band_umschalten(an: bool)`` – Band-Werkzeug (n Moden) starten/abbrechen
    * ``n_moden_geaendert(n: int)`` – Resonanzen je Linescan im Panel gewaehlt
    * ``gerade_mode(index, mode)`` – Gerade einer Mode zuordnen
    """

    def __init__(self, zone_umschalten=None, zone_entfernen=None,
                 gerade_umschalten=None, gerade_seite=None,
                 gerade_entfernen=None, geraden_fit=None, gerade_mode=None,
                 band_umschalten=None, n_moden_geaendert=None, parent=None):
        super().__init__(parent)
        self._cb_zone_umschalten = zone_umschalten
        self._cb_zone_entfernen = zone_entfernen
        self._cb_gerade_umschalten = gerade_umschalten
        self._cb_gerade_seite = gerade_seite
        self._cb_gerade_entfernen = gerade_entfernen
        self._cb_geraden_fit = geraden_fit
        self._cb_gerade_mode = gerade_mode
        self._cb_band_umschalten = band_umschalten
        self._cb_n_moden_geaendert = n_moden_geaendert
        self._n_moden = 1
        self._geraden: list = []

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

        # --- Grenzgeraden / Moden-Baender ---------------------------------------
        grp_geraden = QtWidgets.QGroupBox("Grenzgeraden (Neu-Fit-Bereich)")
        geraden_lay = QtWidgets.QVBoxLayout(grp_geraden)

        # Resonanzen je Linescan - EINE sichtbare Stelle; synchron mit dem
        # Auto-Fit-Dialog und "Res." im Linescan-Panel (Hauptfenster._setze_n_moden).
        moden_zeile = QtWidgets.QHBoxLayout()
        moden_zeile.addWidget(QtWidgets.QLabel("Resonanzen je Linescan:"))
        self.n_moden_combo = RuhigeComboBox()
        self.n_moden_combo.addItem("1 – eine Mode (klassisch)", 1)
        self.n_moden_combo.addItem("2 – zwei Moden", 2)
        for k in range(3, 7):
            self.n_moden_combo.addItem(f"{k} Moden", k)
        self.n_moden_combo.setToolTip(
            "Anzahl simultan gefitteter Resonanzen je Linescan (gilt für Auto-Fit,\n"
            "Neu fitten und Grenzgeraden-Fit). Bei > 1: je Mode ein Band einzeichnen.")
        self.n_moden_combo.currentIndexChanged.connect(self._n_moden_gewaehlt)
        moden_zeile.addWidget(self.n_moden_combo, 1)
        geraden_lay.addLayout(moden_zeile)

        self.hinweis_g = QtWidgets.QLabel()
        self.hinweis_g.setWordWrap(True)
        geraden_lay.addWidget(self.hinweis_g)

        # Band je Mode (nur bei > 1 Resonanz sichtbar): Mode, Breite, Einzeichnen.
        self.band_box = QtWidgets.QWidget()
        band_lay = QtWidgets.QVBoxLayout(self.band_box)
        band_lay.setContentsMargins(0, 0, 0, 0)
        band_zeile = QtWidgets.QHBoxLayout()
        band_zeile.addWidget(QtWidgets.QLabel("Mode:"))
        self.mode_spin = RuhigeSpinBox()
        self.mode_spin.setRange(1, 1)
        self.mode_spin.setToolTip("Mode, für die das nächste Band bzw. die nächste Gerade gilt.")
        band_zeile.addWidget(self.mode_spin)
        band_zeile.addWidget(QtWidgets.QLabel("Breite ±"))
        self.breite_spin = RuhigeSpinBox()
        self.breite_spin.setRange(1, 500)
        self.breite_spin.setValue(10)
        self.breite_spin.setSuffix(" mT")
        self.breite_spin.setToolTip(
            "Halbe Bandbreite um die eingezeichnete Linie; die Mode wird nur darin gesucht.")
        band_zeile.addWidget(self.breite_spin)
        band_zeile.addStretch(1)
        band_lay.addLayout(band_zeile)
        self.btn_band = QtWidgets.QPushButton("Band einzeichnen (2 Klicks entlang der Mode)")
        self.btn_band.setCheckable(True)
        self.btn_band.setToolTip(
            "Zwei Punkte entlang der Mode klicken; das Band ± Breite entsteht als zwei\n"
            "Geraden dieser Mode, Seiten automatisch. Esc oder erneuter Klick bricht ab.")
        self.btn_band.toggled.connect(self._band_umgeschaltet)
        band_lay.addWidget(self.btn_band)
        self.band_status = QtWidgets.QLabel("")
        self.band_status.setWordWrap(True)
        band_lay.addWidget(self.band_status)
        geraden_lay.addWidget(self.band_box)

        self.btn_gerade = QtWidgets.QPushButton("Gerade einzeichnen (2 Klicks)")
        self.btn_gerade.setCheckable(True)
        self.btn_gerade.setToolTip(
            "Einzelne Grenzgerade: grüne Seite wird gefittet, rote ignoriert\n"
            "(Doppelklick auf die Linie tauscht). Esc oder erneuter Klick bricht ab.")
        self.btn_gerade.toggled.connect(self._gerade_umgeschaltet)
        geraden_lay.addWidget(self.btn_gerade)

        self.geraden_liste = QtWidgets.QListWidget()
        self.geraden_liste.setMaximumHeight(110)
        geraden_lay.addWidget(self.geraden_liste)

        zeile = QtWidgets.QHBoxLayout()
        self.btn_gerade_seite = QtWidgets.QPushButton("Seite wechseln")
        self.btn_gerade_seite.setToolTip(
            "Grüne (Fit-) und rote (ignorierte) Seite der gewählten Geraden tauschen.\n"
            "Geht auch per Doppelklick auf die Linie.")
        self.btn_gerade_seite.clicked.connect(self._gerade_seite_geklickt)
        zeile.addWidget(self.btn_gerade_seite)
        self.btn_gerade_mode = QtWidgets.QPushButton("Mode ändern")
        self.btn_gerade_mode.setToolTip(
            "Gewählte Gerade der nächsten Mode zuordnen (1 → 2 → … → 1).")
        self.btn_gerade_mode.clicked.connect(self._gerade_mode_geklickt)
        zeile.addWidget(self.btn_gerade_mode)
        self.btn_gerade_entfernen = QtWidgets.QPushButton("Entfernen")
        self.btn_gerade_entfernen.clicked.connect(self._gerade_entfernen_geklickt)
        zeile.addWidget(self.btn_gerade_entfernen)
        geraden_lay.addLayout(zeile)

        self.btn_geraden_fit = QtWidgets.QPushButton("Grünen Bereich fitten …")
        self.btn_geraden_fit.setToolTip(
            "Fenstersuche und Fit im grünen Bereich aller Geraden bzw. in den Moden-\n"
            "Bändern; im Dialog: Frequenz/Feld von … bis …, Modus, Fensterbreite.")
        self.btn_geraden_fit.clicked.connect(
            lambda: self._cb_geraden_fit and self._cb_geraden_fit())
        geraden_lay.addWidget(self.btn_geraden_fit)
        lay.addWidget(grp_geraden)
        self._moden_ansicht_aktualisieren()

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
        """Fuellt die Geradenliste (Handgriffe + gruene Seite; bei >1 Resonanz die Mode)."""
        gewaehlt = self.geraden_liste.currentRow()
        self._geraden = list(geraden)
        self.geraden_liste.clear()
        for gerade in geraden:
            seite = "+" if gerade.gruen_positiv else "−"
            praefix = (f"M{int(getattr(gerade, 'mode', 1))} · "
                       if self._n_moden > 1 else "")
            self.geraden_liste.addItem(
                f"{praefix}({gerade.b1:.3f} T, {gerade.f1/1e9:.2f} GHz) – "
                f"({gerade.b2:.3f} T, {gerade.f2/1e9:.2f} GHz)  · grün: {seite}")
        if 0 <= gewaehlt < self.geraden_liste.count():
            self.geraden_liste.setCurrentRow(gewaehlt)
        self._moden_ansicht_aktualisieren()

    def setze_n_moden(self, n: int) -> None:
        """Resonanzen je Linescan (vom Hauptfenster): Auswahl, Band-Werkzeug und
        Liste umschalten - ohne Rueckruf."""
        self._n_moden = max(1, int(n))
        self.mode_spin.setRange(1, self._n_moden)
        index = self.n_moden_combo.findData(min(self._n_moden, 6))
        if index >= 0 and index != self.n_moden_combo.currentIndex():
            self.n_moden_combo.blockSignals(True)
            self.n_moden_combo.setCurrentIndex(index)
            self.n_moden_combo.blockSignals(False)
        self.setze_geraden(self._geraden)

    def _n_moden_gewaehlt(self, *_args) -> None:
        n = int(self.n_moden_combo.currentData() or 1)
        if self._cb_n_moden_geaendert is not None:
            self._cb_n_moden_geaendert(n)
        else:
            self.setze_n_moden(n)

    def bandbreite_T(self) -> float:
        """Halbe Bandbreite des Band-Werkzeugs in Tesla."""
        return float(self.breite_spin.value()) / 1e3

    def setze_band_modus_aktiv(self, an: bool) -> None:
        """Synchronisiert den Band-Knopf mit dem Modus-Manager (ohne Rueckruf)."""
        self._knopf_syncen(self.btn_band, an)

    def _band_umgeschaltet(self, an: bool) -> None:
        if self._cb_band_umschalten is not None:
            self._cb_band_umschalten(bool(an))

    def _moden_ansicht_aktualisieren(self) -> None:
        """Ein-Moden-Ansicht (klassisch) oder Moden-Baender-Ansicht (n > 1)."""
        mehrere = self._n_moden > 1
        self.band_box.setVisible(mehrere)
        self.btn_gerade_mode.setVisible(mehrere)
        self.btn_geraden_fit.setText("Moden-Bänder fitten …" if mehrere
                                     else "Grünen Bereich fitten …")
        if mehrere:
            self.hinweis_g.setText(
                f"Ablauf bei {self._n_moden} Moden: Mode wählen → „Band einzeichnen“ "
                "(zwei Klicks entlang der Mode) → nächste Mode → „Moden-Bänder fitten …“. "
                "Jede Mode wird nur in ihrem Band gesucht; Moden ohne Band sind frei. "
                "Einzelne Geraden (grün/rot) bleiben als Experten-Werkzeug.")
            teile = []
            for k in range(1, self._n_moden + 1):
                anzahl = sum(1 for g in self._geraden
                             if min(max(int(getattr(g, "mode", 1)), 1), self._n_moden) == k)
                teile.append(f"M{k} {'✓' if anzahl >= 2 else '–'} ({anzahl})")
            self.band_status.setText("Bänder: " + " · ".join(teile)
                                     + ("" if any(int(getattr(g, "mode", 1)) > 1 for g in self._geraden)
                                        or not self._geraden
                                        else "  – alle Geraden gehören zu Mode 1!"))
        else:
            self.hinweis_g.setText(
                "Gerade per zwei Klicks einfügen, an den Endpunkten ziehen "
                "(verschieben/rotieren). Grüner Saum = wird gefittet, roter Saum = wird "
                "ignoriert; Doppelklick auf die Linie wechselt die Seite. Zwei Geraden "
                "ergeben ein Band. Funktioniert direkt nach dem Laden – ohne Auto-Fit "
                "wird nur der grüne Bereich gefittet.")

    def mode_neu(self) -> int:
        """Mode, die eine neu eingezeichnete Gerade bekommt (1 bei einer Resonanz)."""
        return int(self.mode_spin.value()) if self._n_moden > 1 else 1

    def _gerade_mode_geklickt(self) -> None:
        zeile = self.geraden_liste.currentRow()
        if 0 <= zeile < len(self._geraden) and self._cb_gerade_mode is not None:
            aktuell = int(getattr(self._geraden[zeile], "mode", 1))
            self._cb_gerade_mode(zeile, aktuell % self._n_moden + 1)

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

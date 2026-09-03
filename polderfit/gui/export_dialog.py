# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Dialoge des Speicher-Menues: "Alles speichern" und Export-Spalten.

*Alles speichern* schreibt auf Wunsch in EINEM Schritt in einen Ordner:
Projektdatei, Excel/CSV der Einzelfits, Kittel/LLG-Auswertung (Excel, CSV,
Plot), Farbplot (Bild + verarbeitete Matrix), Fitkurven-TDMS und die
Voreinstellungen - alles mit gemeinsamem Basisnamen.

*Export-Spalten* legt fest, welche Spaltengruppen Excel/CSV enthalten
(:data:`polderfit.persistenz.ergebnis_export.SPALTEN_GRUPPEN`), ob nur
gefittete Frequenzen exportiert werden und ob CSV im deutschen Format
(``;`` und Dezimalkomma) geschrieben wird. Die Wahl ist als Voreinstellung
speicherbar (Standard fuer jeden Export).
"""

from __future__ import annotations

import os

from PySide6 import QtWidgets

from ..persistenz.ergebnis_export import SPALTEN_GRUPPEN

#: Schluessel -> (Text, Tooltip, braucht_fits)
EXPORT_TEILE = {
    "projekt": ("Projektdatei (JSON) – Sitzung fortsetzen",
                "Quelle, Kanal-Zuordnung, Fenster, Zonen, Grenzgeraden, Ausreißer,\n"
                "Bewertungen, physikalische Parameter und Verarbeitungskette.", True),
    "excel": ("Einzelfits als Excel (.xlsx) – alle Parameter, Kittel/LLG, Einstellungen",
              "Blatt 'Einzelfits' (Spalten nach Export-Spalten-Einstellung),\n"
              "'Global' (Kittel/LLG in T und mT) und Zusatzblätter.", True),
    "csv": ("Einzelfits als CSV (Listendaten)",
            "Dieselben Spalten wie Excel als Textdatei.", True),
    "kittel": ("Kittel/LLG-Auswertung (Excel + CSV + Plot PNG/PDF)",
               "Physikalische Parameter mit 1σ-Fehlern (T und mT), alle Punkte,\n"
               "Dispersions- und Linienbreitenplot.", True),
    "farbplot": ("Farbplot als Bild (PNG + PDF, mit Overlays)",
                 "Aktuelle Ansicht des Farbplots samt Fit-Punkten, Zonen und Geraden.", False),
    "matrix": ("Farbplot-Matrix als CSV (verarbeitete Daten)",
               "Die angezeigte Matrix (nach Verarbeitungskette und Darstellung):\n"
               "Zeilen = Frequenzen, Spalten = Feldwerte.", False),
    "tdms": ("Fitkurven als TDMS",
             "Beschnittene Linescans und Fitkurven im TDMS-Format.", True),
    "einstellungen": ("Voreinstellungen (JSON)",
                      "Physikalische Parameter, Verarbeitung, Anzeige- und Export-Optionen.", False),
}


class AllesSpeichernDialog(QtWidgets.QDialog):
    """Auswahl der Bestandteile, Zielordner und Basisname."""

    def __init__(self, ordner_vorgabe: str, basis_vorgabe: str, hat_fits: bool,
                 hat_daten: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Alles speichern")
        self.setMinimumWidth(560)
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(
            "Alle gewählten Bestandteile werden mit gemeinsamem Basisnamen in den "
            "Zielordner geschrieben. Zoom, Fensterlayout und Achsengrößen werden "
            "nie gespeichert.")
        hinweis.setWordWrap(True)
        lay.addWidget(hinweis)

        self._boxen: dict[str, QtWidgets.QCheckBox] = {}
        for schluessel, (text, tip, braucht_fits) in EXPORT_TEILE.items():
            box = QtWidgets.QCheckBox(text)
            box.setToolTip(tip)
            moeglich = hat_daten and (hat_fits or not braucht_fits)
            box.setEnabled(moeglich)
            box.setChecked(moeglich and schluessel in ("projekt", "excel", "kittel", "farbplot"))
            self._boxen[schluessel] = box
            lay.addWidget(box)

        form = QtWidgets.QFormLayout()
        zeile = QtWidgets.QHBoxLayout()
        self.ordner = QtWidgets.QLineEdit(ordner_vorgabe)
        self.ordner.setToolTip("Zielordner (wird bei Bedarf angelegt).")
        zeile.addWidget(self.ordner, 1)
        btn = QtWidgets.QPushButton("Wählen …")
        btn.clicked.connect(self._ordner_waehlen)
        zeile.addWidget(btn)
        form.addRow("Zielordner:", zeile)
        self.basis = QtWidgets.QLineEdit(basis_vorgabe)
        self.basis.setToolTip("Gemeinsamer Dateiname ohne Endung, z. B. 'CoFe_5K_oop'.")
        form.addRow("Basisname:", self.basis)
        lay.addLayout(form)

        knoepfe = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        knoepfe.button(QtWidgets.QDialogButtonBox.Ok).setText("Speichern")
        knoepfe.button(QtWidgets.QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self._pruefen)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)

    def _ordner_waehlen(self) -> None:
        pfad = QtWidgets.QFileDialog.getExistingDirectory(self, "Zielordner", self.ordner.text())
        if pfad:
            self.ordner.setText(pfad)

    def _pruefen(self) -> None:
        if not self.basis.text().strip():
            QtWidgets.QMessageBox.warning(self, "Alles speichern", "Bitte einen Basisnamen angeben.")
            return
        if not any(b.isChecked() for b in self._boxen.values()):
            QtWidgets.QMessageBox.warning(self, "Alles speichern", "Bitte mindestens einen Bestandteil wählen.")
            return
        self.accept()

    def auswahl(self) -> dict:
        """``{"ordner", "basis", "teile": [...]}``."""
        return {
            "ordner": self.ordner.text().strip() or os.getcwd(),
            "basis": self.basis.text().strip(),
            "teile": [k for k, b in self._boxen.items() if b.isChecked()],
        }


class SpaltenDialog(QtWidgets.QDialog):
    """Spaltengruppen und Optionen des Excel-/CSV-Exports."""

    def __init__(self, export_einstellungen: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export-Spalten (Excel/CSV)")
        self.setMinimumWidth(520)
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(
            "Welche Spaltengruppen jeder Excel-/CSV-Export enthält. Die Auswahl gilt "
            "sofort und wird mit den Voreinstellungen gespeichert (Datei → Einstellungen).")
        hinweis.setWordWrap(True)
        lay.addWidget(hinweis)

        gewaehlt = set(export_einstellungen.get("spalten") or SPALTEN_GRUPPEN.keys())
        self._boxen: dict[str, QtWidgets.QCheckBox] = {}
        for schluessel, (titel, spalten) in SPALTEN_GRUPPEN.items():
            box = QtWidgets.QCheckBox(titel)
            box.setToolTip("Spalten: " + ", ".join(spalten)
                           + ("; zusätzlich alle *_2, *_3 … Spalten" if schluessel == "nebenmoden" else ""))
            box.setChecked(schluessel in gewaehlt)
            self._boxen[schluessel] = box
            lay.addWidget(box)

        lay.addSpacing(8)
        self.chk_nur_gefittete = QtWidgets.QCheckBox("Nur gefittete Frequenzen exportieren (keine Platzhalter)")
        self.chk_nur_gefittete.setChecked(bool(export_einstellungen.get("nur_gefittete", True)))
        lay.addWidget(self.chk_nur_gefittete)
        self.chk_csv_deutsch = QtWidgets.QCheckBox("CSV im deutschen Format (';' und Dezimalkomma)")
        self.chk_csv_deutsch.setChecked(bool(export_einstellungen.get("csv_deutsch", False)))
        self.chk_csv_deutsch.setToolTip("Direkt in deutschem Excel/LibreOffice lesbar; sonst ',' und Punkt.")
        lay.addWidget(self.chk_csv_deutsch)
        self.chk_zusatz = QtWidgets.QCheckBox("Zusatzblätter in Excel (Einstellungen, Zonen/Korridore, Ausreißer)")
        self.chk_zusatz.setChecked(bool(export_einstellungen.get("zusatzblaetter", True)))
        lay.addWidget(self.chk_zusatz)

        knoepfe = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        knoepfe.button(QtWidgets.QDialogButtonBox.Ok).setText("Übernehmen")
        knoepfe.button(QtWidgets.QDialogButtonBox.Cancel).setText("Abbrechen")
        alle = knoepfe.addButton("Alle", QtWidgets.QDialogButtonBox.ActionRole)
        alle.clicked.connect(lambda: [b.setChecked(True) for b in self._boxen.values()])
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)

    def einstellungen(self) -> dict:
        spalten = [k for k, b in self._boxen.items() if b.isChecked()]
        if not spalten:
            spalten = ["kern"]   # nichts gewaehlt = Kern (statt stillschweigend alles)
        return {
            "spalten": spalten if len(spalten) < len(SPALTEN_GRUPPEN) else [],
            "nur_gefittete": self.chk_nur_gefittete.isChecked(),
            "csv_deutsch": self.chk_csv_deutsch.isChecked(),
            "zusatzblaetter": self.chk_zusatz.isChecked(),
        }

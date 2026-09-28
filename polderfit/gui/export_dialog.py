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
from ..sprache import N_, tr

#: Schluessel -> (Text, Tooltip, braucht_fits)
EXPORT_TEILE = {
    "projekt": (N_("Projektdatei (JSON) – Sitzung fortsetzen"),
                N_("Quelle, Kanal-Zuordnung, Fenster, Zonen, Korridore, Ausreißer,\n"
                "Bewertungen, physikalische Parameter und Verarbeitungskette."), True),
    "excel": (N_("Einzelfits als Excel (.xlsx) – alle Parameter, Kittel/LLG, Einstellungen"),
              N_("Blatt 'Einzelfits' (Spalten nach Export-Spalten-Einstellung),\n"
              "'Global' (Kittel/LLG in T und mT) und Zusatzblätter."), True),
    "csv": (N_("Einzelfits als CSV (Listendaten)"),
            N_("Dieselben Spalten wie Excel als Textdatei."), True),
    "kittel": (N_("Kittel/LLG-Auswertung (Excel + CSV + Plot PNG/PDF)"),
               N_("Physikalische Parameter mit 1σ-Fehlern (T und mT), alle Punkte,\n"
               "Dispersions- und Linienbreitenplot."), True),
    "farbplot": (N_("Farbplot als Bild (PNG + PDF, mit Overlays)"),
                 N_("Aktuelle Ansicht des Farbplots samt Fit-Punkten, Zonen und Geraden."), False),
    "matrix": (N_("Farbplot-Matrix als CSV (verarbeitete Daten)"),
               N_("Die angezeigte Matrix (nach Verarbeitungskette und Darstellung):\n"
               "Zeilen = Frequenzen, Spalten = Feldwerte."), False),
    "tdms": (N_("Fitkurven als TDMS"),
             N_("Beschnittene Linescans und Fitkurven im TDMS-Format."), True),
    "einstellungen": (N_("Voreinstellungen (JSON)"),
                      N_("Physikalische Parameter, Verarbeitung, Anzeige- und Export-Optionen."), False),
}


class AllesSpeichernDialog(QtWidgets.QDialog):
    """Auswahl der Bestandteile, Zielordner und Basisname."""

    def __init__(self, ordner_vorgabe: str, basis_vorgabe: str, hat_fits: bool,
                 hat_daten: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Alles speichern"))
        self.setMinimumWidth(560)
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(
            tr("Alle gewählten Bestandteile werden mit gemeinsamem Basisnamen in den "
            "Zielordner geschrieben. Zoom, Fensterlayout und Achsengrößen werden "
            "nie gespeichert."))
        hinweis.setWordWrap(True)
        lay.addWidget(hinweis)

        self._boxen: dict[str, QtWidgets.QCheckBox] = {}
        for schluessel, (text, tip, braucht_fits) in EXPORT_TEILE.items():
            box = QtWidgets.QCheckBox(tr(text))
            box.setToolTip(tr(tip))
            moeglich = hat_daten and (hat_fits or not braucht_fits)
            box.setEnabled(moeglich)
            box.setChecked(moeglich and schluessel in ("projekt", "excel", "kittel", "farbplot"))
            self._boxen[schluessel] = box
            lay.addWidget(box)

        form = QtWidgets.QFormLayout()
        zeile = QtWidgets.QHBoxLayout()
        self.ordner = QtWidgets.QLineEdit(ordner_vorgabe)
        self.ordner.setToolTip(tr("Zielordner (wird bei Bedarf angelegt)."))
        zeile.addWidget(self.ordner, 1)
        btn = QtWidgets.QPushButton(tr("Wählen …"))
        btn.clicked.connect(self._ordner_waehlen)
        zeile.addWidget(btn)
        form.addRow(tr("Zielordner:"), zeile)
        self.basis = QtWidgets.QLineEdit(basis_vorgabe)
        self.basis.setToolTip(tr("Gemeinsamer Dateiname ohne Endung, z. B. 'CoFe_5K_oop'."))
        form.addRow(tr("Basisname:"), self.basis)
        lay.addLayout(form)

        knoepfe = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        knoepfe.button(QtWidgets.QDialogButtonBox.Ok).setText(tr("Speichern"))
        knoepfe.button(QtWidgets.QDialogButtonBox.Cancel).setText(tr("Abbrechen"))
        knoepfe.accepted.connect(self._pruefen)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)

    def _ordner_waehlen(self) -> None:
        pfad = QtWidgets.QFileDialog.getExistingDirectory(self, tr("Zielordner"), self.ordner.text())
        if pfad:
            self.ordner.setText(pfad)

    def _pruefen(self) -> None:
        if not self.basis.text().strip():
            QtWidgets.QMessageBox.warning(self, tr("Alles speichern"), tr("Bitte einen Basisnamen angeben."))
            return
        if not any(b.isChecked() for b in self._boxen.values()):
            QtWidgets.QMessageBox.warning(self, tr("Alles speichern"), tr("Bitte mindestens einen Bestandteil wählen."))
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
        self.setWindowTitle(tr("Export-Spalten (Excel/CSV)"))
        self.setMinimumWidth(520)
        lay = QtWidgets.QVBoxLayout(self)
        hinweis = QtWidgets.QLabel(
            tr("Welche Spaltengruppen jeder Excel-/CSV-Export enthält. Die Auswahl gilt "
            "sofort und wird mit den Voreinstellungen gespeichert (Datei → Einstellungen)."))
        hinweis.setWordWrap(True)
        lay.addWidget(hinweis)

        gewaehlt = set(export_einstellungen.get("spalten") or SPALTEN_GRUPPEN.keys())
        self._boxen: dict[str, QtWidgets.QCheckBox] = {}
        for schluessel, (titel, spalten) in SPALTEN_GRUPPEN.items():
            box = QtWidgets.QCheckBox(tr(titel))
            box.setToolTip(tr("Spalten: ") + ", ".join(spalten)
                           + (tr("; zusätzlich alle *_2, *_3 … Spalten") if schluessel == "nebenmoden" else ""))
            box.setChecked(schluessel in gewaehlt)
            self._boxen[schluessel] = box
            lay.addWidget(box)

        lay.addSpacing(8)
        self.chk_nur_gefittete = QtWidgets.QCheckBox(tr("Nur gefittete Frequenzen exportieren (keine Platzhalter)"))
        self.chk_nur_gefittete.setChecked(bool(export_einstellungen.get("nur_gefittete", True)))
        lay.addWidget(self.chk_nur_gefittete)
        self.chk_csv_deutsch = QtWidgets.QCheckBox(tr("CSV im deutschen Format (';' und Dezimalkomma)"))
        self.chk_csv_deutsch.setChecked(bool(export_einstellungen.get("csv_deutsch", False)))
        self.chk_csv_deutsch.setToolTip(tr("Direkt in deutschem Excel/LibreOffice lesbar; sonst ',' und Punkt."))
        lay.addWidget(self.chk_csv_deutsch)
        self.chk_zusatz = QtWidgets.QCheckBox(tr("Zusatzblätter in Excel (Einstellungen, Zonen/Korridore, Ausreißer)"))
        self.chk_zusatz.setChecked(bool(export_einstellungen.get("zusatzblaetter", True)))
        lay.addWidget(self.chk_zusatz)

        knoepfe = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        knoepfe.button(QtWidgets.QDialogButtonBox.Ok).setText(tr("Übernehmen"))
        knoepfe.button(QtWidgets.QDialogButtonBox.Cancel).setText(tr("Abbrechen"))
        alle = knoepfe.addButton(tr("Alle"), QtWidgets.QDialogButtonBox.ActionRole)
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

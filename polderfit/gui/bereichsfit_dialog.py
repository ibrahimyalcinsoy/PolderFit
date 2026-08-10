# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Optionen-Dialog des Bereichs-Fits (nach dem Aufziehen des Rechtecks).

Der Bereichs-Fit ist neben dem Grenzen-Ziehen im Linescan-Panel der einzige
Weg zum Nachfitten von Teilbereichen. Die frueheren Einzelwerkzeuge
(Propagation, "Breite auf alle anwenden", ziehbare Grenzen im Farbplot) sind
hier als Optionen aufgegangen: Modus (ueberschreiben/ergaenzen) und optional
eine feste Fensterbreite in Punkten.
"""

from __future__ import annotations

from PySide6 import QtWidgets

#: Anzeige-Texte des Ueberschreib-Modus (Reihenfolge = Combo-Reihenfolge).
_MODUS_TEXTE = {
    "ueberschreiben": "ueberschreiben (alle Fits im Rechteck ersetzen)",
    "ergaenzen": "ergaenzen (nur problematische Fits ersetzen)",
}


class BereichsFitDialog(QtWidgets.QDialog):
    """Fragt Modus und optionale Fensterbreite fuer den Bereichs-Fit ab."""

    def __init__(self, feld_min: float, feld_max: float,
                 f_min_ghz: float, f_max_ghz: float,
                 modus_vorgabe: str = "ueberschreiben",
                 breite_vorgabe: int | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bereich neu fitten")
        lay = QtWidgets.QVBoxLayout(self)

        info = QtWidgets.QLabel(
            f"Rechteck: {feld_min:.3f} – {feld_max:.3f} T, "
            f"{f_min_ghz:.2f} – {f_max_ghz:.2f} GHz.\n"
            "Dort werden Fenstersuche und Fit wiederholt; Ergebnisse ausserhalb "
            "bleiben unangetastet.")
        info.setWordWrap(True)
        lay.addWidget(info)

        form = QtWidgets.QFormLayout()
        self.modus_combo = QtWidgets.QComboBox()
        for schluessel, text in _MODUS_TEXTE.items():
            self.modus_combo.addItem(text, schluessel)
        index = self.modus_combo.findData(modus_vorgabe)
        if index >= 0:
            self.modus_combo.setCurrentIndex(index)
        form.addRow("Modus:", self.modus_combo)
        lay.addLayout(form)

        breite_zeile = QtWidgets.QHBoxLayout()
        self.chk_breite = QtWidgets.QCheckBox("Fensterbreite fest:")
        self.chk_breite.setToolTip(
            "Statt der automatischen Fensterbreite eine feste Breite in\n"
            "Feldpunkten um das gefundene Fensterzentrum erzwingen -\n"
            "der Hebel gegen zu enge Automatik-Fenster.")
        self.breite_spin = QtWidgets.QSpinBox()
        self.breite_spin.setRange(4, 100000)
        self.breite_spin.setValue(breite_vorgabe or 15)
        self.breite_spin.setSuffix(" Punkte")
        self.breite_spin.setEnabled(breite_vorgabe is not None)
        self.chk_breite.setChecked(breite_vorgabe is not None)
        self.chk_breite.toggled.connect(self.breite_spin.setEnabled)
        breite_zeile.addWidget(self.chk_breite)
        breite_zeile.addWidget(self.breite_spin)
        breite_zeile.addStretch(1)
        lay.addLayout(breite_zeile)

        knoepfe = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        knoepfe.button(QtWidgets.QDialogButtonBox.Ok).setText("Neu fitten")
        knoepfe.button(QtWidgets.QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)

    def modus(self) -> str:
        return self.modus_combo.currentData()

    def breite_punkte(self) -> int | None:
        """Feste Fensterbreite in Punkten oder ``None`` (Automatik)."""
        return int(self.breite_spin.value()) if self.chk_breite.isChecked() else None

# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Bedienpanel der Verarbeitungskette (divide-slice → derivative-divide →
relation-amplitude) fuer den Farbplot.

Jeder Schritt ist einzeln zu-/abschaltbar und parametrisierbar; jede
Aenderung meldet die neue Kette sofort ueber den ``geaendert``-Callback
(die Kette rechnet auf der gecachten komplexen Matrix – schnell genug fuer
Live-Aktualisierung ohne Hintergrund-Thread). Physik und Parameterbedeutung:
:mod:`polderfit.verarbeitung.operationen` (Maier-Flaig 2018, Gl. (3)/(4)).
"""

from __future__ import annotations

import numpy as np
from PySide6 import QtCore, QtWidgets

from ..verarbeitung import ANZEIGE_MODI, KettenSchritt, Verarbeitungskette

#: Auswahltexte fuer den ``achse``-Parameter.
_ACHSEN_TEXTE = {"feld": "Feldachse", "frequenz": "Frequenzachse"}


class VerarbeitungPanel(QtWidgets.QWidget):
    """Schaltet und parametrisiert die drei Verarbeitungsschritte.

    ``geaendert(kette, anzeige_modus)`` wird bei jeder Aenderung aufgerufen.
    """

    def __init__(self, geaendert=None, parent=None):
        super().__init__(parent)
        self.geaendert = geaendert
        self._feld_achse: np.ndarray | None = None
        self._blockiert = False  # unterdrueckt Callbacks waehrend programmatischer Aenderungen

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

        vorgabe = Verarbeitungskette.standard()
        js = {s.operation: s for s in vorgabe.schritte}

        # --- 1. divide-slice -------------------------------------------------
        self.grp_divide = QtWidgets.QGroupBox("1 · divide-slice (Referenz-Slice)")
        self.grp_divide.setCheckable(True)
        self.grp_divide.setChecked(js["divide_slice"].aktiv)
        self.grp_divide.setToolTip(
            "Ganze Matrix durch das Spektrum bei einem festen Feldwert teilen –\n"
            "entfernt den frequenzabhaengigen Untergrund (Maier-Flaig 2018, Gl. 3).\n"
            "Referenz sollte moeglichst resonanzfrei sein.")
        g1 = QtWidgets.QFormLayout(self.grp_divide)
        self.divide_achse = QtWidgets.QComboBox()
        for schluessel, text in _ACHSEN_TEXTE.items():
            self.divide_achse.addItem(f"Referenz-Slice auf {text}", schluessel)
        g1.addRow("Achse:", self.divide_achse)
        self.divide_index = QtWidgets.QSpinBox()
        self.divide_index.setRange(-1, 0)  # echte Grenzen kommen mit setze_achsen()
        self.divide_index.setValue(int(js["divide_slice"].parameter.get("index", 0)))
        self.divide_index.setToolTip("Achsenindex des Referenz-Slices (0 = erster, -1 = letzter).")
        g1.addRow("Index:", self.divide_index)
        self.divide_wert_label = QtWidgets.QLabel("–")
        g1.addRow("entspricht:", self.divide_wert_label)
        lay.addWidget(self.grp_divide)

        # --- 2. derivative-divide -------------------------------------------
        self.grp_dd = QtWidgets.QGroupBox("2 · derivative-divide")
        self.grp_dd.setCheckable(True)
        self.grp_dd.setChecked(js["derivative_divide"].aktiv)
        self.grp_dd.setToolTip(
            "Zentraler Differenzenquotient entlang des Feldes, geteilt durch den\n"
            "zentralen Wert (Maier-Flaig 2018, Gl. 4). Eliminiert Untergrund und\n"
            "Phase ohne Kalibrierung; Ergebnis ∝ dχ/dω.")
        g2 = QtWidgets.QFormLayout(self.grp_dd)
        self.dd_delta = QtWidgets.QSpinBox()
        self.dd_delta.setRange(1, 200)
        self.dd_delta.setValue(int(js["derivative_divide"].parameter.get("delta_n", 4)))
        self.dd_delta.setToolTip(
            "Punktabstand Δn der Differenzbildung (Modulationsamplitude in Gitter-\n"
            "punkten). Groesser = glatter, aber breitere Linien.")
        g2.addRow("Δn (Punkte):", self.dd_delta)
        self.dd_mitteln = QtWidgets.QCheckBox("Fenster mitteln (zusaetzliche Glaettung)")
        self.dd_mitteln.setChecked(bool(js["derivative_divide"].parameter.get("mitteln", True)))
        g2.addRow(self.dd_mitteln)
        self.dd_achse = QtWidgets.QComboBox()
        for schluessel, text in _ACHSEN_TEXTE.items():
            self.dd_achse.addItem(f"Ableitung entlang {text}", schluessel)
        g2.addRow("Achse:", self.dd_achse)
        lay.addWidget(self.grp_dd)

        # --- 3. relation-amplitude -------------------------------------------
        self.grp_rel = QtWidgets.QGroupBox("3 · relation-amplitude")
        self.grp_rel.setCheckable(True)
        self.grp_rel.setChecked(js["relation_amplitude"].aktiv)
        self.grp_rel.setToolTip(
            "Jeden Slice durch den Nachbar-Slice im Abstand Δn teilen (divisive\n"
            "Untergrund-Referenz, pybbfmr 'referenced fmr').")
        g3 = QtWidgets.QFormLayout(self.grp_rel)
        self.rel_delta = QtWidgets.QSpinBox()
        self.rel_delta.setRange(1, 200)
        self.rel_delta.setValue(int(js["relation_amplitude"].parameter.get("delta_n", 1)))
        g3.addRow("Δn (Punkte):", self.rel_delta)
        self.rel_achse = QtWidgets.QComboBox()
        for schluessel, text in _ACHSEN_TEXTE.items():
            self.rel_achse.addItem(f"Referenz entlang {text}", schluessel)
        g3.addRow("Achse:", self.rel_achse)
        lay.addWidget(self.grp_rel)

        # --- Anzeige ----------------------------------------------------------
        anzeige_reihe = QtWidgets.QFormLayout()
        self.anzeige_combo = QtWidgets.QComboBox()
        for schluessel, text in ANZEIGE_MODI.items():
            self.anzeige_combo.addItem(text, schluessel)
        anzeige_reihe.addRow("Anzeige:", self.anzeige_combo)
        lay.addLayout(anzeige_reihe)

        self.btn_roh = QtWidgets.QPushButton("Alles aus (Rohdaten |S21|)")
        self.btn_roh.clicked.connect(self._alles_aus)
        lay.addWidget(self.btn_roh)
        lay.addStretch(1)

        # Jede Aenderung -> Callback.
        for signal in (
            self.grp_divide.toggled, self.grp_dd.toggled, self.grp_rel.toggled,
            self.dd_mitteln.toggled,
        ):
            signal.connect(self._melde)
        for spin in (self.divide_index, self.dd_delta, self.rel_delta):
            spin.valueChanged.connect(self._melde)
        for combo in (self.divide_achse, self.dd_achse, self.rel_achse, self.anzeige_combo):
            combo.currentIndexChanged.connect(self._melde)

    # --- Zustand -> Kette -----------------------------------------------------
    def kette(self) -> Verarbeitungskette:
        """Aktuelle Kette aus dem Panel-Zustand (Projektreihenfolge 1→2→3)."""
        return Verarbeitungskette(schritte=[
            KettenSchritt("divide_slice", aktiv=self.grp_divide.isChecked(),
                          parameter={"achse": self.divide_achse.currentData(),
                                     "index": int(self.divide_index.value())}),
            KettenSchritt("derivative_divide", aktiv=self.grp_dd.isChecked(),
                          parameter={"delta_n": int(self.dd_delta.value()),
                                     "mitteln": self.dd_mitteln.isChecked(),
                                     "achse": self.dd_achse.currentData()}),
            KettenSchritt("relation_amplitude", aktiv=self.grp_rel.isChecked(),
                          parameter={"delta_n": int(self.rel_delta.value()),
                                     "achse": self.rel_achse.currentData()}),
        ])

    def anzeige_modus(self) -> str:
        return self.anzeige_combo.currentData()

    def setze_achsen(self, feld_achse: np.ndarray, freq_achse: np.ndarray) -> None:
        """Setzt Achsen des geladenen Datensatzes (Spinbox-Grenzen, Wert-Anzeige)."""
        self._feld_achse = np.asarray(feld_achse)
        self._freq_achse = np.asarray(freq_achse)
        self._blockiert = True
        try:
            n = max(self._feld_achse.size, self._freq_achse.size)
            self.divide_index.setRange(-n, n - 1)
            maximal = max(1, min(self._feld_achse.size, self._freq_achse.size) // 2 - 1)
            self.dd_delta.setMaximum(maximal)
            self.rel_delta.setMaximum(maximal)
        finally:
            self._blockiert = False
        self._zeige_divide_wert()

    def _zeige_divide_wert(self) -> None:
        """Zeigt den Achsenwert des gewaehlten Referenz-Index an."""
        achse = self.divide_achse.currentData()
        werte = self._feld_achse if achse == "feld" else getattr(self, "_freq_achse", None)
        if werte is None or werte.size == 0:
            self.divide_wert_label.setText("–")
            return
        index = int(self.divide_index.value())
        if not (-werte.size <= index < werte.size):
            self.divide_wert_label.setText("Index ausserhalb der Achse")
            return
        wert = float(werte[index])
        self.divide_wert_label.setText(
            f"{wert:.4f} T" if achse == "feld" else f"{wert / 1e9:.3f} GHz")

    def _alles_aus(self) -> None:
        """Alle Schritte deaktivieren, Anzeige auf Betrag (= Rohansicht)."""
        self._blockiert = True
        try:
            self.grp_divide.setChecked(False)
            self.grp_dd.setChecked(False)
            self.grp_rel.setChecked(False)
            self.anzeige_combo.setCurrentIndex(0)  # "betrag"
        finally:
            self._blockiert = False
        self._melde()

    def _melde(self, *_args) -> None:
        if self._blockiert:
            return
        self._zeige_divide_wert()
        if self.geaendert is not None:
            self.geaendert(self.kette(), self.anzeige_modus())

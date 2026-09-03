# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Bedienpanel der Verarbeitung des Farbplots (divide-slice, derivative-divide,
relation-amplitude).

Es ist immer hoechstens EINE Verarbeitung aktiv (Optionsfeld-Logik: das
Einschalten einer Operation schaltet die andere ab; "Alles aus" zeigt die
Rohdaten). Jede Option traegt einen Hover-Tooltip mit Erklaerung. Jede
Aenderung meldet die neue Kette ueber den ``geaendert``-Callback - leicht
verzoegert (Entprellung), damit schnelles Drehen am Mausrad nicht Dutzende
Neuberechnungen ausloest. Spin-Boxen reagieren auf das Mausrad nur mit
Tastaturfokus (:mod:`polderfit.gui.widgets`).

Physik und Parameterbedeutung: :mod:`polderfit.verarbeitung.operationen`
(Maier-Flaig 2018, Gl. (3)/(4)).
"""

from __future__ import annotations

import numpy as np
from PySide6 import QtCore, QtWidgets

from ..persistenz.einstellungen import FARBSKALEN
from ..verarbeitung import ANZEIGE_MODI, KettenSchritt, Verarbeitungskette
from .widgets import RuhigeComboBox, RuhigeSpinBox

#: Auswahltexte fuer den ``achse``-Parameter.
_ACHSEN_TEXTE = {"feld": "Feldachse", "frequenz": "Frequenzachse"}

_TIP_DIVIDE = (
    "divide-slice: Die ganze Matrix wird durch das Spektrum bei EINEM festen\n"
    "Feldwert (Referenz-Slice) geteilt. Entfernt den frequenzabhängigen\n"
    "Untergrund (Maier-Flaig 2018, Gl. 3). Der Referenzwert sollte möglichst\n"
    "resonanzfrei sein (z. B. Rand des Feldsweeps).")
_TIP_DD = (
    "derivative-divide: Zentraler Differenzenquotient entlang des Feldes,\n"
    "geteilt durch den Wert in der Mitte (Maier-Flaig 2018, Gl. 4).\n"
    "Beseitigt Untergrund und Phase ohne Kalibrierung; das Ergebnis ist\n"
    "proportional zu dχ/dω. Standardansicht für die Resonanzsuche.")
_TIP_REL = (
    "relation-amplitude: Jeder Slice wird durch den Nachbar-Slice im Abstand Δn\n"
    "geteilt (divisive Untergrund-Referenz, pybbfmr 'referenced fmr').\n"
    "Betont schmale Strukturen, die sich von Slice zu Slice ändern.")
_TIP_DELTA = (
    "Punktabstand Δn der Differenz-/Referenzbildung (Modulationsamplitude in\n"
    "Gitterpunkten). Größer = glatter und rauschärmer, aber breitere Linien;\n"
    "kleiner = schärfer, aber verrauschter. Typisch 2–8.\n"
    "Tipp: Mausrad wirkt nur, wenn das Feld den Fokus hat.")
_TIP_MITTELN = (
    "Statt der Zwei-Punkt-Differenz die Mittelwerte der Fenster [i−Δn, i) und\n"
    "[i, i+Δn] vergleichen – zusätzliche Glättung (pybbfmr-Standard).")
_TIP_ACHSE = (
    "Entlang welcher Achse gerechnet wird: Feldachse (Standard, wie im Paper)\n"
    "oder Frequenzachse.")
_TIP_INDEX = (
    "Achsenindex des Referenz-Slices (0 = erster, −1 = letzter Punkt).\n"
    "Der zugehörige Feld-/Frequenzwert steht darunter.")
_TIP_ANZEIGE = (
    "Welche reelle Größe des (komplexen) Ergebnisses gezeichnet wird:\n"
    "Betrag, Betrag in dB, Real-/Imaginärteil oder Phase.")
_TIP_FARBSKALA = (
    "Farbskala des Falschfarbenbilds. 'Grau' hält den Hintergrund neutral,\n"
    "damit die Signalfarben der Fit-Punkte (grün/gelb/rot/blau) hervorstechen;\n"
    "Viridis/Cividis sind wahrnehmungsgleich (auch für Farbfehlsichtige).")
_TIP_ROH = "Alle Verarbeitungen abschalten und die Rohdaten |S21| zeigen."


class VerarbeitungPanel(QtWidgets.QWidget):
    """Schaltet und parametrisiert die Verarbeitung (genau eine Operation aktiv).

    ``geaendert(kette, anzeige_modus)`` wird bei jeder Aenderung aufgerufen
    (entprellt, siehe :data:`VERZOEGERUNG_MS`); ``farbskala_geaendert(name)``
    beim Wechsel der Farbskala.
    """

    #: Entprellung der Aenderungsmeldung in ms (0 = sofort, z. B. in Tests).
    VERZOEGERUNG_MS: int = 150

    def __init__(self, geaendert=None, farbskala_geaendert=None, parent=None):
        super().__init__(parent)
        self.geaendert = geaendert
        self.farbskala_geaendert = farbskala_geaendert
        self._feld_achse: np.ndarray | None = None
        self._freq_achse: np.ndarray | None = None
        self._blockiert = False  # unterdrueckt Callbacks waehrend programmatischer Aenderungen
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._melde_jetzt)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

        self.setToolTip("Genau eine Verarbeitung ist aktiv; Erklärung je Option per Tooltip.")

        vorgabe = Verarbeitungskette.standard()
        js = {s.operation: s for s in vorgabe.schritte}

        # --- 1. divide-slice -------------------------------------------------
        self.grp_divide = QtWidgets.QGroupBox("divide-slice (Referenz-Slice)")
        self.grp_divide.setCheckable(True)
        self.grp_divide.setChecked(js["divide_slice"].aktiv)
        self.grp_divide.setToolTip(_TIP_DIVIDE)
        g1 = QtWidgets.QFormLayout(self.grp_divide)
        self.divide_achse = RuhigeComboBox()
        for schluessel, text in _ACHSEN_TEXTE.items():
            self.divide_achse.addItem(f"Referenz-Slice auf {text}", schluessel)
        self.divide_achse.setToolTip(_TIP_ACHSE)
        g1.addRow("Achse:", self.divide_achse)
        self.divide_index = RuhigeSpinBox()
        self.divide_index.setRange(-1, 0)  # echte Grenzen kommen mit setze_achsen()
        self.divide_index.setValue(int(js["divide_slice"].parameter.get("index", 0)))
        self.divide_index.setToolTip(_TIP_INDEX)
        g1.addRow("Index:", self.divide_index)
        self.divide_wert_label = QtWidgets.QLabel("–")
        self.divide_wert_label.setToolTip("Feld- bzw. Frequenzwert des gewählten Referenz-Index.")
        g1.addRow("entspricht:", self.divide_wert_label)
        lay.addWidget(self.grp_divide)

        # --- 2. derivative-divide -------------------------------------------
        self.grp_dd = QtWidgets.QGroupBox("derivative-divide")
        self.grp_dd.setCheckable(True)
        self.grp_dd.setChecked(js["derivative_divide"].aktiv)
        self.grp_dd.setToolTip(_TIP_DD)
        g2 = QtWidgets.QFormLayout(self.grp_dd)
        self.dd_delta = RuhigeSpinBox()
        self.dd_delta.setRange(1, 200)
        self.dd_delta.setValue(int(js["derivative_divide"].parameter.get("delta_n", 4)))
        self.dd_delta.setToolTip(_TIP_DELTA)
        g2.addRow("Δn (Punkte):", self.dd_delta)
        self.dd_mitteln = QtWidgets.QCheckBox("Fenster mitteln (zusätzliche Glättung)")
        self.dd_mitteln.setChecked(bool(js["derivative_divide"].parameter.get("mitteln", True)))
        self.dd_mitteln.setToolTip(_TIP_MITTELN)
        g2.addRow(self.dd_mitteln)
        self.dd_achse = RuhigeComboBox()
        for schluessel, text in _ACHSEN_TEXTE.items():
            self.dd_achse.addItem(f"Ableitung entlang {text}", schluessel)
        self.dd_achse.setToolTip(_TIP_ACHSE)
        g2.addRow("Achse:", self.dd_achse)
        lay.addWidget(self.grp_dd)

        # --- 3. relation-amplitude -------------------------------------------
        self.grp_rel = QtWidgets.QGroupBox("relation-amplitude")
        self.grp_rel.setCheckable(True)
        self.grp_rel.setChecked(js["relation_amplitude"].aktiv)
        self.grp_rel.setToolTip(_TIP_REL)
        g3 = QtWidgets.QFormLayout(self.grp_rel)
        self.rel_delta = RuhigeSpinBox()
        self.rel_delta.setRange(1, 200)
        self.rel_delta.setValue(int(js["relation_amplitude"].parameter.get("delta_n", 1)))
        self.rel_delta.setToolTip(_TIP_DELTA)
        g3.addRow("Δn (Punkte):", self.rel_delta)
        self.rel_achse = RuhigeComboBox()
        for schluessel, text in _ACHSEN_TEXTE.items():
            self.rel_achse.addItem(f"Referenz entlang {text}", schluessel)
        self.rel_achse.setToolTip(_TIP_ACHSE)
        g3.addRow("Achse:", self.rel_achse)
        lay.addWidget(self.grp_rel)

        # --- Anzeige ----------------------------------------------------------
        grp_anzeige = QtWidgets.QGroupBox("Darstellung")
        anzeige_reihe = QtWidgets.QFormLayout(grp_anzeige)
        self.anzeige_combo = RuhigeComboBox()
        for schluessel, text in ANZEIGE_MODI.items():
            self.anzeige_combo.addItem(text, schluessel)
        self.anzeige_combo.setToolTip(_TIP_ANZEIGE)
        anzeige_reihe.addRow("Größe:", self.anzeige_combo)
        self.farbskala_combo = RuhigeComboBox()
        for name, text in FARBSKALEN.items():
            self.farbskala_combo.addItem(text, name)
        self.farbskala_combo.setToolTip(_TIP_FARBSKALA)
        anzeige_reihe.addRow("Farbskala:", self.farbskala_combo)
        lay.addWidget(grp_anzeige)

        self.btn_roh = QtWidgets.QPushButton("Alles aus (Rohdaten |S21|)")
        self.btn_roh.setToolTip(_TIP_ROH)
        self.btn_roh.clicked.connect(self._alles_aus)
        lay.addWidget(self.btn_roh)
        lay.addStretch(1)

        # Genau eine Operation aktiv: Einschalten schaltet die anderen ab.
        self._gruppen = (self.grp_divide, self.grp_dd, self.grp_rel)
        for grp in self._gruppen:
            grp.toggled.connect(lambda an, g=grp: self._exklusiv(g, an))
        self.dd_mitteln.toggled.connect(self._melde)
        for spin in (self.divide_index, self.dd_delta, self.rel_delta):
            spin.valueChanged.connect(self._melde)
        for combo in (self.divide_achse, self.dd_achse, self.rel_achse, self.anzeige_combo):
            combo.currentIndexChanged.connect(self._melde)
        self.farbskala_combo.currentIndexChanged.connect(self._farbskala_gewaehlt)

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

    def farbskala(self) -> str:
        return self.farbskala_combo.currentData() or "viridis"

    def setze_kette(self, kette: Verarbeitungskette, anzeige_modus: str | None = None,
                    melden: bool = True) -> None:
        """Panel aus einer Kette (z. B. aus Voreinstellungen/Projekt) belegen.

        Ist mehr als ein Schritt aktiv (aeltere Dateien), bleibt nur der erste.
        """
        self._blockiert = True
        try:
            schritte = {s.operation: s for s in kette.schritte}
            aktiv_gesehen = False
            for grp, name in ((self.grp_divide, "divide_slice"), (self.grp_dd, "derivative_divide"),
                              (self.grp_rel, "relation_amplitude")):
                s = schritte.get(name)
                an = bool(s.aktiv) if s is not None else False
                if an and aktiv_gesehen:
                    an = False
                aktiv_gesehen = aktiv_gesehen or an
                grp.setChecked(an)
                if s is None:
                    continue
                par = s.parameter
                if name == "divide_slice":
                    self._setze_combo(self.divide_achse, par.get("achse", "feld"))
                    self.divide_index.setValue(int(par.get("index", 0)))
                elif name == "derivative_divide":
                    self.dd_delta.setValue(int(par.get("delta_n", 4)))
                    self.dd_mitteln.setChecked(bool(par.get("mitteln", True)))
                    self._setze_combo(self.dd_achse, par.get("achse", "feld"))
                else:
                    self.rel_delta.setValue(int(par.get("delta_n", 1)))
                    self._setze_combo(self.rel_achse, par.get("achse", "feld"))
            if anzeige_modus is not None:
                self._setze_combo(self.anzeige_combo, anzeige_modus)
        finally:
            self._blockiert = False
        if melden:
            self._melde()

    def setze_farbskala(self, name: str, melden: bool = False) -> None:
        self._blockiert = not melden
        try:
            self._setze_combo(self.farbskala_combo, name)
        finally:
            self._blockiert = False

    @staticmethod
    def _setze_combo(combo: QtWidgets.QComboBox, wert) -> None:
        index = combo.findData(wert)
        if index >= 0:
            combo.setCurrentIndex(index)

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
        werte = self._feld_achse if achse == "feld" else self._freq_achse
        if werte is None or werte.size == 0:
            self.divide_wert_label.setText("–")
            return
        index = int(self.divide_index.value())
        if not (-werte.size <= index < werte.size):
            self.divide_wert_label.setText("Index außerhalb der Achse")
            return
        wert = float(werte[index])
        self.divide_wert_label.setText(
            f"{wert:.4f} T" if achse == "feld" else f"{wert / 1e9:.3f} GHz")

    def _exklusiv(self, gruppe: QtWidgets.QGroupBox, an: bool) -> None:
        """Genau eine Operation aktiv: die anderen Gruppen abschalten."""
        if an and not self._blockiert:
            for andere in self._gruppen:
                if andere is not gruppe and andere.isChecked():
                    andere.blockSignals(True)
                    andere.setChecked(False)
                    andere.blockSignals(False)
        self._melde()

    def _alles_aus(self) -> None:
        """Alle Schritte deaktivieren, Anzeige auf Betrag (= Rohansicht)."""
        self._blockiert = True
        try:
            for grp in self._gruppen:
                grp.setChecked(False)
            self.anzeige_combo.setCurrentIndex(0)  # "betrag"
        finally:
            self._blockiert = False
        self._melde()

    def _farbskala_gewaehlt(self, *_args) -> None:
        if self._blockiert:
            return
        if self.farbskala_geaendert is not None:
            self.farbskala_geaendert(self.farbskala())

    def _melde(self, *_args) -> None:
        if self._blockiert:
            return
        self._zeige_divide_wert()
        if self.VERZOEGERUNG_MS <= 0:
            self._melde_jetzt()
        else:
            self._timer.start(int(self.VERZOEGERUNG_MS))

    def _melde_jetzt(self) -> None:
        if self.geaendert is not None:
            self.geaendert(self.kette(), self.anzeige_modus())

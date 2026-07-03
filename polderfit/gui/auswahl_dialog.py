# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Dialog "Auswertungsbereich & Jumper" - wird vor jeder Stapelauswertung gezeigt.

Fragt die Unterabtastung (jeden n-ten Punkt, getrennt fuer Frequenz- und
Feldachse) und die Bereichseinschraenkung ab (Frequenz-/Feldfenster plus
Frequenz-Ausschlussbaender wie "3-5" GHz). Eine Live-Zusammenfassung zeigt,
wie viele Linescans die aktuelle Auswahl uebrig laesst. Die zuletzt benutzte
Auswahl wird vorbelegt.
"""

from __future__ import annotations

import numpy as np
from PySide6 import QtWidgets

from ..fit.auswahl import Auswertungsauswahl, parse_bereiche
from ..io.datensatz import Messdatensatz


class AuswahlDialog(QtWidgets.QDialog):
    """Fragt die :class:`Auswertungsauswahl` fuer den naechsten Auto-Fit ab."""

    def __init__(self, datensatz: Messdatensatz,
                 letzte: Auswertungsauswahl | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Auswertungsbereich & Jumper")
        self.setModal(True)
        self._datensatz = datensatz
        vorgabe = letzte if letzte is not None else Auswertungsauswahl()

        frequenzen = datensatz.frequenzen
        b_min, b_max = datensatz.feld_bereich()
        f_min_ghz = float(frequenzen.min()) / 1e9 if frequenzen.size else 0.0
        f_max_ghz = float(frequenzen.max()) / 1e9 if frequenzen.size else 1.0

        lay = QtWidgets.QVBoxLayout(self)
        kopf = QtWidgets.QLabel(
            f"Auswertung von <b>{len(datensatz)}</b> Linescans "
            f"({f_min_ghz:.2f}-{f_max_ghz:.2f} GHz, {b_min:.3f}-{b_max:.3f} T). "
            f"Unterabtastung beschleunigt; Bereiche grenzen die Auswertung ein.")
        kopf.setWordWrap(True)
        lay.addWidget(kopf)

        # --- Jumper (jeden n-ten Punkt) --------------------------------------
        grp_n = QtWidgets.QGroupBox("Nur jeden n-ten Messpunkt auswerten")
        form_n = QtWidgets.QFormLayout(grp_n)
        self.n_frequenz = QtWidgets.QSpinBox()
        self.n_frequenz.setRange(1, max(1, len(datensatz)))
        self.n_frequenz.setValue(vorgabe.n_frequenz)
        self.n_frequenz.setToolTip("1 = jede Frequenz; 10 = jede 10. Frequenz (Linescan).")
        form_n.addRow("Frequenzachse - jeder n-te Linescan:", self.n_frequenz)
        self.n_feld = QtWidgets.QSpinBox()
        maximal_feld = max((ls.feld.size for ls in datensatz.linescans), default=1)
        self.n_feld.setRange(1, max(1, maximal_feld // 4))
        self.n_feld.setValue(vorgabe.n_feld)
        self.n_feld.setToolTip("1 = jeder Feldpunkt; 10 = jeder 10. Punkt je Linescan.")
        form_n.addRow("Feldachse - jeder n-te Punkt:", self.n_feld)
        lay.addWidget(grp_n)

        # --- Auszuwertender Bereich ------------------------------------------
        grp_b = QtWidgets.QGroupBox("Auszuwertender Bereich")
        form_b = QtWidgets.QFormLayout(grp_b)

        def _spin(minimum, maximum, wert, dezimalen, schritt, suffix):
            box = QtWidgets.QDoubleSpinBox()
            box.setRange(minimum, maximum)
            box.setDecimals(dezimalen)
            box.setSingleStep(schritt)
            box.setValue(wert)
            box.setSuffix(suffix)
            return box

        spanne_f = max(f_max_ghz - f_min_ghz, 1e-9)
        self.f_min = _spin(f_min_ghz - spanne_f, f_max_ghz + spanne_f,
                           (vorgabe.frequenz_min_hz / 1e9
                            if vorgabe.frequenz_min_hz is not None else f_min_ghz),
                           3, 0.5, " GHz")
        self.f_max = _spin(f_min_ghz - spanne_f, f_max_ghz + spanne_f,
                           (vorgabe.frequenz_max_hz / 1e9
                            if vorgabe.frequenz_max_hz is not None else f_max_ghz),
                           3, 0.5, " GHz")
        form_b.addRow("Frequenz von:", self.f_min)
        form_b.addRow("Frequenz bis:", self.f_max)

        spanne_b = max(b_max - b_min, 1e-9)
        self.b_min = _spin(b_min - spanne_b, b_max + spanne_b,
                           vorgabe.feld_min_t if vorgabe.feld_min_t is not None else b_min,
                           4, 0.05, " T")
        self.b_max = _spin(b_min - spanne_b, b_max + spanne_b,
                           vorgabe.feld_max_t if vorgabe.feld_max_t is not None else b_max,
                           4, 0.05, " T")
        form_b.addRow("Feld von:", self.b_min)
        form_b.addRow("Feld bis:", self.b_max)

        self.ausschluss = QtWidgets.QLineEdit(
            "; ".join(f"{lo/1e9:g}-{hi/1e9:g}" for lo, hi in vorgabe.frequenz_ausschluss))
        self.ausschluss.setPlaceholderText("z. B. 3-5; 10.2-11")
        self.ausschluss.setToolTip(
            "Frequenzbaender (GHz), die NICHT ausgewertet werden - mehrere mit ';' trennen.")
        form_b.addRow("Frequenz-Ausschluesse (GHz):", self.ausschluss)
        lay.addWidget(grp_b)

        self.zusammenfassung = QtWidgets.QLabel("")
        self.zusammenfassung.setWordWrap(True)
        lay.addWidget(self.zusammenfassung)

        self.knoepfe = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.knoepfe.button(QtWidgets.QDialogButtonBox.Ok).setText("Auswertung starten")
        self.knoepfe.accepted.connect(self._pruefe_und_akzeptiere)
        self.knoepfe.rejected.connect(self.reject)
        lay.addWidget(self.knoepfe)

        for box in (self.n_frequenz, self.n_feld):
            box.valueChanged.connect(self._aktualisiere_zusammenfassung)
        for box in (self.f_min, self.f_max, self.b_min, self.b_max):
            box.valueChanged.connect(self._aktualisiere_zusammenfassung)
        self.ausschluss.textChanged.connect(self._aktualisiere_zusammenfassung)
        self._aktualisiere_zusammenfassung()

    def auswahl(self) -> Auswertungsauswahl:
        """Aktuelle Auswahl aus den Dialogfeldern (wirft ValueError bei Parsefehler)."""
        frequenzen = self._datensatz.frequenzen
        b_min, b_max = self._datensatz.feld_bereich()
        f_min_ghz = float(frequenzen.min()) / 1e9 if frequenzen.size else 0.0
        f_max_ghz = float(frequenzen.max()) / 1e9 if frequenzen.size else 1.0

        def _oder_none(wert, standard):
            # Volle Spanne bedeutet "keine Einschraenkung" -> None (robust
            # gegen erneutes Laden mit anderem Datensatzbereich).
            return None if abs(wert - standard) < 1e-12 else wert

        return Auswertungsauswahl(
            n_frequenz=int(self.n_frequenz.value()),
            n_feld=int(self.n_feld.value()),
            frequenz_min_hz=(lambda v: None if v is None else v * 1e9)(
                _oder_none(self.f_min.value(), f_min_ghz)),
            frequenz_max_hz=(lambda v: None if v is None else v * 1e9)(
                _oder_none(self.f_max.value(), f_max_ghz)),
            feld_min_t=_oder_none(self.b_min.value(), b_min),
            feld_max_t=_oder_none(self.b_max.value(), b_max),
            frequenz_ausschluss=parse_bereiche(self.ausschluss.text(), einheit=1e9),
        )

    def _aktualisiere_zusammenfassung(self, *_args) -> None:
        try:
            auswahl = self.auswahl()
        except ValueError as fehler:
            self.zusammenfassung.setText(
                f'<span style="color:#C0392B">{fehler}</span>')
            self.knoepfe.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
            return
        n_linescans = auswahl.waehle_indizes(self._datensatz).size
        beispiel = self._datensatz.linescans[0] if self._datensatz.linescans else None
        n_punkte = (auswahl.reduziere_linescan(beispiel).feld.size
                    if beispiel is not None else 0)
        farbe = "#C0392B" if n_linescans == 0 or n_punkte < 4 else "#2E7D38"
        self.zusammenfassung.setText(
            f'<span style="color:{farbe}">{auswahl.beschreibung()} - '
            f'{n_linescans} von {len(self._datensatz)} Linescans, '
            f'~{n_punkte} Feldpunkte je Linescan.</span>')
        self.knoepfe.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(
            n_linescans > 0 and n_punkte >= 4)

    def _pruefe_und_akzeptiere(self) -> None:
        try:
            self.auswahl()
        except ValueError as fehler:
            QtWidgets.QMessageBox.warning(self, "Auswahl", str(fehler))
            return
        self.accept()

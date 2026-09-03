# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Optionen-Dialog des Bereichs-/Korridor-Fits.

Fragt Modus (ueberschreiben/ergaenzen), optional eine feste Fensterbreite in
Punkten und den auszuwertenden Bereich ab: **Frequenz von … bis …** und
**Feld von … bis …** - beim Rechteck mit dessen Werten vorbelegt (editierbar),
beim Korridor-Fit mit dem zuletzt benutzten Bereich (sonst dem ganzen
Datenbereich); dort zusaetzlich der Jumper "jede n-te Frequenz". Eingaben mit
Punkt oder Komma sind gleichwertig.
"""

from __future__ import annotations

from PySide6 import QtWidgets

from .widgets import RuhigeDoubleSpinBox, RuhigeSpinBox

#: Anzeige-Texte des Ueberschreib-Modus (Reihenfolge = Combo-Reihenfolge).
_MODUS_TEXTE = {
    "ueberschreiben": "überschreiben (alle Fits im Bereich ersetzen)",
    "ergaenzen": "ergänzen (nur problematische/ungefittete Fits ersetzen)",
}


class BereichsFitDialog(QtWidgets.QDialog):
    """Fragt Modus, optionale Fensterbreite und Frequenz-/Feldbereich ab."""

    def __init__(self, feld_min: float, feld_max: float,
                 f_min_ghz: float, f_max_ghz: float,
                 modus_vorgabe: str = "ueberschreiben",
                 breite_vorgabe: int | None = None,
                 info_text: str | None = None, titel: str | None = None,
                 daten_bereich: tuple[float, float, float, float] | None = None,
                 mit_feld: bool = True, mit_breite: bool = True,
                 schritt_vorgabe: int | None = None,
                 dips_auto_vorgabe: bool | None = None,
                 parent=None):
        """``daten_bereich`` = (feld_min, feld_max, f_min_ghz, f_max_ghz) der
        ganzen Messung (Grenzen der Eingabefelder); fehlt es, gilt das Rechteck.
        ``mit_feld``/``mit_breite``: Feldgrenzen bzw. feste Fensterbreite anbieten
        (beim Korridor-Fit nicht - der Korridor ist das Fenster). ``schritt_vorgabe``:
        Jumper "jede n-te Frequenz" anbieten (``None`` = ausblenden)."""
        super().__init__(parent)
        self.setWindowTitle(titel or "Bereich neu fitten")
        lay = QtWidgets.QVBoxLayout(self)

        info = QtWidgets.QLabel(info_text or (
            f"Rechteck: {feld_min:.3f} – {feld_max:.3f} T, "
            f"{f_min_ghz:.2f} – {f_max_ghz:.2f} GHz.\n"
            "Dort werden Fenstersuche und Fit wiederholt; Ergebnisse außerhalb "
            "bleiben unangetastet."))
        info.setWordWrap(True)
        lay.addWidget(info)

        form = QtWidgets.QFormLayout()
        self.modus_combo = QtWidgets.QComboBox()
        for schluessel, text in _MODUS_TEXTE.items():
            self.modus_combo.addItem(text, schluessel)
        self.modus_combo.setToolTip(
            "überschreiben: alle Fits im Bereich neu rechnen.\n"
            "ergänzen: nur problematische oder noch nicht gefittete Frequenzen.")
        index = self.modus_combo.findData(modus_vorgabe)
        if index >= 0:
            self.modus_combo.setCurrentIndex(index)
        form.addRow("Modus:", self.modus_combo)

        # Bereich: Frequenz von/bis, Feld von/bis.
        d_bmin, d_bmax, d_fmin, d_fmax = daten_bereich or (feld_min, feld_max, f_min_ghz, f_max_ghz)
        spanne_f = max(d_fmax - d_fmin, 1e-6)
        spanne_b = max(d_bmax - d_bmin, 1e-6)

        def _spin(lo, hi, wert, dez, schritt, suffix, tip):
            box = RuhigeDoubleSpinBox()
            box.setRange(lo, hi)
            box.setDecimals(dez)
            box.setSingleStep(schritt)
            box.setValue(wert)
            box.setSuffix(suffix)
            box.setToolTip(tip)
            return box

        self.f_von = _spin(d_fmin - spanne_f, d_fmax + spanne_f, f_min_ghz, 3, 0.5, " GHz",
                           "Untere Frequenzgrenze des Neu-Fits.")
        self.f_bis = _spin(d_fmin - spanne_f, d_fmax + spanne_f, f_max_ghz, 3, 0.5, " GHz",
                           "Obere Frequenzgrenze des Neu-Fits.")
        self.b_von = _spin(d_bmin - spanne_b, d_bmax + spanne_b, feld_min, 4, 0.05, " T",
                           "Untere Feldgrenze des Neu-Fits (µ₀H in Tesla).")
        self.b_bis = _spin(d_bmin - spanne_b, d_bmax + spanne_b, feld_max, 4, 0.05, " T",
                           "Obere Feldgrenze des Neu-Fits (µ₀H in Tesla).")
        form.addRow("Frequenz von:", self.f_von)
        form.addRow("Frequenz bis:", self.f_bis)
        if mit_feld:
            form.addRow("Feld von:", self.b_von)
            form.addRow("Feld bis:", self.b_bis)
        self.schritt_spin = RuhigeSpinBox()
        self.schritt_spin.setRange(1, 1000)
        self.schritt_spin.setValue(max(1, int(schritt_vorgabe or 1)))
        self.schritt_spin.setPrefix("jede ")
        self.schritt_spin.setSuffix(". Frequenz")
        self.schritt_spin.setToolTip(
            "Jumper: nur jede n-te Frequenz des Bereichs fitten (schneller;\n"
            "1 = alle Frequenzen).")
        if schritt_vorgabe is not None:
            form.addRow("Jumper:", self.schritt_spin)
        self.chk_dips_auto = QtWidgets.QCheckBox("Anzahl der Dips je Frequenz automatisch (BIC)")
        self.chk_dips_auto.setToolTip(
            "Zusatzoption: je Frequenz werden 1 … n Linien gefittet und das sparsamste\n"
            "Modell gewählt, das die Daten erklärt (BIC). Wo weniger Dips sind, entfällt\n"
            "die überzählige Linie. Nur Summenfit; manuelle Trennlinien haben Vorrang.\n"
            "Rechenzeit etwa 2–3-fach. Aus = Verhalten wie bisher.")
        self.chk_dips_auto.setChecked(bool(dips_auto_vorgabe))
        if dips_auto_vorgabe is not None:
            form.addRow("", self.chk_dips_auto)
        lay.addLayout(form)

        breite_zeile = QtWidgets.QHBoxLayout()
        self.chk_breite = QtWidgets.QCheckBox("Fensterbreite fest:")
        self.chk_breite.setToolTip(
            "Statt der automatischen Fensterbreite eine feste Breite in\n"
            "Feldpunkten um das gefundene Fensterzentrum erzwingen -\n"
            "der Hebel gegen zu enge Automatik-Fenster.")
        self.breite_spin = RuhigeSpinBox()
        self.breite_spin.setRange(4, 100000)
        self.breite_spin.setValue(breite_vorgabe or 15)
        self.breite_spin.setSuffix(" Punkte")
        self.breite_spin.setEnabled(breite_vorgabe is not None)
        self.chk_breite.setChecked(breite_vorgabe is not None)
        self.chk_breite.toggled.connect(self.breite_spin.setEnabled)
        breite_zeile.addWidget(self.chk_breite)
        breite_zeile.addWidget(self.breite_spin)
        breite_zeile.addStretch(1)
        if mit_breite:
            lay.addLayout(breite_zeile)
        else:
            self.chk_breite.setChecked(False)
            self.chk_breite.setVisible(False)
            self.breite_spin.setVisible(False)

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

    def frequenz_bereich(self) -> tuple[float, float]:
        """(f_min, f_max) in Hz (sortiert)."""
        a, b = float(self.f_von.value()) * 1e9, float(self.f_bis.value()) * 1e9
        return (min(a, b), max(a, b))

    def feld_bereich(self) -> tuple[float, float]:
        """(feld_min, feld_max) in Tesla (sortiert)."""
        a, b = float(self.b_von.value()), float(self.b_bis.value())
        return (min(a, b), max(a, b))

    def dips_auto(self) -> bool:
        return bool(self.chk_dips_auto.isChecked())

    def schritt(self) -> int:
        """Jumper: jede n-te Frequenz (1 = alle)."""
        return max(1, int(self.schritt_spin.value()))

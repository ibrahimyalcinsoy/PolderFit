# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Dialog fuer die einstellbaren physikalischen Parameter.

Die Datenklasse :class:`PhysikParameter` liegt GUI-frei in
:mod:`polderfit.fit.parameter` und wird hier nur wieder exportiert. Jeder
Eintrag traegt einen Hover-Tooltip; Spin-Boxen reagieren auf das Mausrad nur
mit Fokus. Konvention: Felder als µ0H in Tesla, γ = g·µ_B/ħ (Mueller 2023,
Kap. 2).
"""

from __future__ import annotations

from dataclasses import replace

from PySide6 import QtWidgets

from ..fit.parameter import GEOMETRIEN, PhysikParameter
from ..physik.konstanten import gamma_aus_g
from .widgets import RuhigeComboBox, RuhigeDoubleSpinBox, RuhigeSpinBox

__all__ = ["GEOMETRIEN", "ParameterDialog", "PhysikParameter"]


class ParameterDialog(QtWidgets.QDialog):
    """Dialog zum Einstellen der physikalischen Parameter."""

    def __init__(self, parameter: PhysikParameter, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Physikalische Parameter")
        self._vorgabe = parameter
        lay = QtWidgets.QVBoxLayout(self)

        hinweis = QtWidgets.QLabel(
            "Konvention: Felder als µ₀H in Tesla, γ = g·µ_B/ħ in rad/(s·T) "
            "(Müller 2023, Kap. 2). Änderungen wirken ab dem nächsten "
            "(Auto-/Nach-)Fit; die Kittel/LLG-Auswertung rechnet sofort neu. "
            "Speichern/Laden als Voreinstellung: Menü Datei → Einstellungen.")
        hinweis.setWordWrap(True)
        lay.addWidget(hinweis)

        form = QtWidgets.QFormLayout()

        self.g_spin = RuhigeDoubleSpinBox()
        self.g_spin.setRange(0.5, 10.0)
        self.g_spin.setDecimals(4)
        self.g_spin.setSingleStep(0.01)
        self.g_spin.setValue(parameter.g_faktor)
        self.g_spin.setToolTip(
            "Landé-g-Faktor. γ = g·µ_B/ħ wird daraus abgeleitet und überall\n"
            "verwendet: Einzelfits (ΔH = 2ωα/γ), Fenstersuche und als\n"
            "Startwert des Kittel-Fits.")
        self.g_spin.valueChanged.connect(self._zeige_gamma)
        form.addRow("g-Faktor:", self.g_spin)

        self.gamma_label = QtWidgets.QLabel("")
        form.addRow("→ γ:", self.gamma_label)
        self._zeige_gamma()

        self.chk_gamma_fest = QtWidgets.QCheckBox(
            "γ im Kittel-Fit festhalten (nur µ₀M_eff fitten)")
        self.chk_gamma_fest.setChecked(parameter.gamma_fest)
        self.chk_gamma_fest.setToolTip(
            "Kittel-oop-Fit mit festem γ (aus dem g-Faktor oben): nur µ₀M_eff frei.")
        form.addRow("", self.chk_gamma_fest)

        self.geo_combo = RuhigeComboBox()
        self.geo_combo.addItems(list(GEOMETRIEN))
        self.geo_combo.setCurrentText(parameter.geometrie)
        self.geo_combo.setToolTip(
            "Vorgabe für das Kittel/LLG-Auswertungsfenster:\n"
            "oop = Feld senkrecht zur Schicht (Gl. 2.24),\n"
            "ip = Feld in der Schichtebene (Gl. 2.26).")
        form.addRow("Kittel-Geometrie:", self.geo_combo)

        self.breite_spin = RuhigeDoubleSpinBox()
        self.breite_spin.setRange(1.0, 30.0)
        self.breite_spin.setDecimals(1)
        self.breite_spin.setSingleStep(0.5)
        self.breite_spin.setValue(parameter.breite_faktor)
        self.breite_spin.setToolTip(
            "Automatische Fensterbreite = Faktor × lokale Halbwertsbreite\n"
            "der Resonanz. Größer = mehr Untergrund im Fit, kleiner = enger.")
        form.addRow("Fensterbreite-Faktor:", self.breite_spin)

        self.r2_spin = RuhigeDoubleSpinBox()
        self.r2_spin.setRange(0.0, 1.0)
        self.r2_spin.setDecimals(3)
        self.r2_spin.setSingleStep(0.01)
        self.r2_spin.setValue(parameter.r2_schwelle)
        self.r2_spin.setToolTip(
            "Sekundäre R²-Schwelle der Einzelfit-Bewertung (primär zählt\n"
            "die Mehrkriterien-Einstufung).")
        form.addRow("R²-Schwelle (Einzelfit):", self.r2_spin)

        self.r2min_spin = RuhigeDoubleSpinBox()
        self.r2min_spin.setRange(0.0, 1.0)
        self.r2min_spin.setDecimals(3)
        self.r2min_spin.setSingleStep(0.01)
        self.r2min_spin.setValue(parameter.r2_min)
        self.r2min_spin.setToolTip(
            "Nur Einzelfits mit R² ≥ diesem Wert gehen in den\n"
            "Kittel-/LLG-Fit ein (zusätzlich zur Problem-Einstufung).")
        form.addRow("R²-Minimum (Kittel/LLG):", self.r2min_spin)

        self.alpha_max_spin = RuhigeDoubleSpinBox()
        self.alpha_max_spin.setRange(0.001, 2.0)
        self.alpha_max_spin.setDecimals(3)
        self.alpha_max_spin.setSingleStep(0.05)
        self.alpha_max_spin.setValue(parameter.alpha_max)
        self.alpha_max_spin.setToolTip(
            "Harte obere Schranke der Gilbert-Dämpfung α im Einzelfit.\n"
            "Standard 0.1 (Metalle/Granate). Für sehr breite Resonanzen\n"
            "(z. B. FeCr2S4 mit α ≈ 0.2–0.5) anheben – sonst klemmt der Fit\n"
            "an der Schranke ('alpha an Grenze').")
        form.addRow("α-Obergrenze (Einzelfit):", self.alpha_max_spin)

        self.alpha_plausibel_spin = RuhigeDoubleSpinBox()
        self.alpha_plausibel_spin.setRange(0.0, 2.0)
        self.alpha_plausibel_spin.setDecimals(3)
        self.alpha_plausibel_spin.setSingleStep(0.01)
        self.alpha_plausibel_spin.setSpecialValueText("automatisch (α max / 2)")
        self.alpha_plausibel_spin.setValue(parameter.alpha_plausibel)
        self.alpha_plausibel_spin.setToolTip(
            "Grenze des Kriteriums 'alpha unphysikalisch' (gelbe Warnung).\n"
            "0 = automatisch (halbe α-Obergrenze). Bei Proben mit real breiten\n"
            "Linien (nanostrukturiertes CoFe, FeCr2S4) anheben, damit gute Fits\n"
            "nicht dauernd als problematisch gelten.")
        form.addRow("α-Plausibilitätsgrenze:", self.alpha_plausibel_spin)

        self.nachfenster_spin = RuhigeDoubleSpinBox()
        self.nachfenster_spin.setRange(0.0, 10.0)
        self.nachfenster_spin.setDecimals(1)
        self.nachfenster_spin.setSingleStep(0.5)
        self.nachfenster_spin.setSpecialValueText("aus")
        self.nachfenster_spin.setValue(parameter.nachfenster_faktor)
        self.nachfenster_spin.setToolTip(
            "Zweiter Fit-Durchgang (Auto-/Bereichs-Fit): Fitfenster =\n"
            "B_res ± Faktor × ΔH aus dem ersten Durchgang; übernommen nur,\n"
            "wenn der Nachfit unproblematisch ist. Bis ≈ ±3 ΔH ist die\n"
            "Linienbreite fensterunabhängig; auf dem breiten Detektions-\n"
            "fenster (Faktor 8) fällt sie bei strukturiertem Untergrund\n"
            "systematisch 5–15 % zu klein aus (Benchmark gegen LabVIEW-FTF).\n"
            "0 = aus (nur ein Durchgang auf dem Detektionsfenster).")
        form.addRow("Nachfenster (± ΔH-Vielfache):", self.nachfenster_spin)

        self.gewicht_combo = RuhigeComboBox()
        self.gewicht_combo.addItems(["ungewichtet (Standard)", "gewichtet (GUM, w = 1/u²)"])
        self.gewicht_combo.setCurrentIndex(1 if parameter.gewichtet else 0)
        self.gewicht_combo.setToolTip(
            "Kittel-/LLG-Fits: ungewichtet (Standard, alle Punkte gleich – wie\n"
            "das LabVIEW-FTF) oder optional gewichtet mit den 1σ-Unsicherheiten\n"
            "der Einzelfits (w = 1/u², ABW Abschn. 6.3; betont die präzisesten\n"
            "Punkte, wenige Punkte können dominieren).\n"
            "Weichen beide Ergebnisse stark voneinander ab, tragen Modell-\n"
            "abweichungen (nicht Rauschen) die Streuung.")
        form.addRow("Kittel-/LLG-Gewichtung:", self.gewicht_combo)

        self.chk_bestaetigen = QtWidgets.QCheckBox(
            "Manuelle Nachfits automatisch als „gut – bestätigt“ bewerten")
        self.chk_bestaetigen.setChecked(parameter.nachfit_bestaetigen)
        self.chk_bestaetigen.setToolTip(
            "An (Standard): Grenzen ziehen, Bereichs-/Grenzgeraden-Fit und\n"
            "'Nochmal fitten' gelten als vom Nutzer geprüft → grüner Punkt mit\n"
            "blauem Rand, gehen in Kittel/LLG ein. Das Kriterienergebnis bleibt\n"
            "einsehbar (Export: problematisch_auto). Aus: Kriterien entscheiden\n"
            "auch nach manuellen Fits (gelb, wenn verletzt).")
        form.addRow("", self.chk_bestaetigen)

        lay.addLayout(form)

        knoepfe = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
            | QtWidgets.QDialogButtonBox.RestoreDefaults)
        knoepfe.button(QtWidgets.QDialogButtonBox.Ok).setText("Übernehmen")
        knoepfe.button(QtWidgets.QDialogButtonBox.Cancel).setText("Abbrechen")
        knoepfe.button(QtWidgets.QDialogButtonBox.RestoreDefaults).setText("Standardwerte")
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        knoepfe.button(QtWidgets.QDialogButtonBox.RestoreDefaults).clicked.connect(
            self._standardwerte)
        lay.addWidget(knoepfe)

    def _zeige_gamma(self) -> None:
        self.gamma_label.setText(
            f"{gamma_aus_g(float(self.g_spin.value())):.4e} rad/(s·T)")

    def _standardwerte(self) -> None:
        standard = PhysikParameter()
        self._vorgabe = standard
        self.g_spin.setValue(standard.g_faktor)
        self.chk_gamma_fest.setChecked(standard.gamma_fest)
        self.geo_combo.setCurrentText(standard.geometrie)
        self.breite_spin.setValue(standard.breite_faktor)
        self.r2_spin.setValue(standard.r2_schwelle)
        self.r2min_spin.setValue(standard.r2_min)
        self.alpha_max_spin.setValue(standard.alpha_max)
        self.alpha_plausibel_spin.setValue(standard.alpha_plausibel)
        self.nachfenster_spin.setValue(standard.nachfenster_faktor)
        self.gewicht_combo.setCurrentIndex(1 if standard.gewichtet else 0)
        self.chk_bestaetigen.setChecked(standard.nachfit_bestaetigen)

    def parameter(self) -> PhysikParameter:
        """Liefert die eingestellten Parameter als neue Datenklasse."""
        return replace(
            self._vorgabe,
            g_faktor=float(self.g_spin.value()),
            gamma_fest=self.chk_gamma_fest.isChecked(),
            geometrie=self.geo_combo.currentText(),
            breite_faktor=float(self.breite_spin.value()),
            r2_schwelle=float(self.r2_spin.value()),
            r2_min=float(self.r2min_spin.value()),
            alpha_max=float(self.alpha_max_spin.value()),
            alpha_plausibel=float(self.alpha_plausibel_spin.value()),
            nachfenster_faktor=float(self.nachfenster_spin.value()),
            gewichtet=self.gewicht_combo.currentIndex() == 1,
            nachfit_bestaetigen=self.chk_bestaetigen.isChecked(),
        )

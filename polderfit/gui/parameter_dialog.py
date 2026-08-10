# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Einstellbare physikalische Parameter der Auswertung (Dialog + Datenklasse).

Die Konventionen folgen Kap. 2 der Dissertation M. Mueller (2023) und dem
Protokoll: Felder als mu0*H in Tesla, ``gamma = g*mu_B/hbar`` in rad/(s*T)
(Gl. 2.24/2.26: Kittel; Gl. 2.28: Linienbreite). Der Nutzer stellt den
**g-Faktor** ein; gamma wird daraus abgeleitet und ueberall verwendet:
Einzelfits (Suszeptibilitaet, dH = 2*omega*alpha/gamma), Fenstersuche und
als Startwert (oder Festwert) des Kittel-Fits.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6 import QtWidgets

from ..physik.konstanten import G_FAKTOR_STANDARD, gamma_aus_g

#: Waehlbare Kittel-Geometrien.
GEOMETRIEN = ("oop", "ip")


@dataclass
class PhysikParameter:
    """Vom Nutzer einstellbare Parameter fuer Fit und Auswertung."""

    #: Lande-g-Faktor; ``gamma = g*mu_B/hbar`` folgt daraus.
    g_faktor: float = G_FAKTOR_STANDARD
    #: gamma im Kittel-Fit festhalten (nur mu0Meff fitten; oop).
    gamma_fest: bool = False
    #: Vorgabe der Kittel-Geometrie im Auswertungsfenster.
    geometrie: str = "oop"
    #: Fensterbreite der Automatik: Fenster = faktor * lokale FWHM.
    breite_faktor: float = 8.0
    #: R2-Schwelle der Einzelfit-Bewertung (sekundaeres Guetemass).
    r2_schwelle: float = 0.9
    #: R2-Mindestwert fuer die Punktauswahl der Kittel-/LLG-Auswertung.
    r2_min: float = 0.9
    #: Erwartete Daempfung alpha fuer die Fensterbreite bei "Resonanz vorgeben".
    alpha_erwartet: float = 0.01

    @property
    def gamma(self) -> float:
        """Gyromagnetisches Verhaeltnis in rad/(s*T) zum eingestellten g-Faktor."""
        return gamma_aus_g(self.g_faktor)

    def beschreibung(self) -> str:
        fest = ", γ fest" if self.gamma_fest else ""
        return (f"g={self.g_faktor:.4f} (γ={self.gamma:.4e} rad/(s·T)){fest}, "
                f"Geometrie {self.geometrie}, Fensterfaktor {self.breite_faktor:g}, "
                f"R²-Schwelle {self.r2_schwelle:g}, R²-Min (Kittel) {self.r2_min:g}, "
                f"α erwartet {self.alpha_erwartet:g}")


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
            "(Auto-/Nach-)Fit; die Kittel/LLG-Auswertung rechnet sofort neu.")
        hinweis.setWordWrap(True)
        lay.addWidget(hinweis)

        form = QtWidgets.QFormLayout()

        self.g_spin = QtWidgets.QDoubleSpinBox()
        self.g_spin.setRange(0.5, 10.0)
        self.g_spin.setDecimals(4)
        self.g_spin.setSingleStep(0.01)
        self.g_spin.setValue(parameter.g_faktor)
        self.g_spin.setToolTip(
            "Lande-g-Faktor. γ = g·µ_B/ħ wird daraus abgeleitet und ueberall\n"
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
        form.addRow("", self.chk_gamma_fest)

        self.geo_combo = QtWidgets.QComboBox()
        self.geo_combo.addItems(list(GEOMETRIEN))
        self.geo_combo.setCurrentText(parameter.geometrie)
        self.geo_combo.setToolTip(
            "Vorgabe fuer das Kittel/LLG-Auswertungsfenster:\n"
            "oop = Feld senkrecht zur Schicht (Gl. 2.24),\n"
            "ip = Feld in der Schichtebene (Gl. 2.26).")
        form.addRow("Kittel-Geometrie:", self.geo_combo)

        self.breite_spin = QtWidgets.QDoubleSpinBox()
        self.breite_spin.setRange(1.0, 30.0)
        self.breite_spin.setDecimals(1)
        self.breite_spin.setSingleStep(0.5)
        self.breite_spin.setValue(parameter.breite_faktor)
        self.breite_spin.setToolTip(
            "Automatische Fensterbreite = Faktor × lokale Halbwertsbreite\n"
            "der Resonanz. Groesser = mehr Untergrund im Fit, kleiner = enger.")
        form.addRow("Fensterbreite-Faktor:", self.breite_spin)

        self.r2_spin = QtWidgets.QDoubleSpinBox()
        self.r2_spin.setRange(0.0, 1.0)
        self.r2_spin.setDecimals(3)
        self.r2_spin.setSingleStep(0.01)
        self.r2_spin.setValue(parameter.r2_schwelle)
        self.r2_spin.setToolTip(
            "Sekundaere R²-Schwelle der Einzelfit-Bewertung (primaer zaehlt\n"
            "die Mehrkriterien-Einstufung).")
        form.addRow("R²-Schwelle (Einzelfit):", self.r2_spin)

        self.r2min_spin = QtWidgets.QDoubleSpinBox()
        self.r2min_spin.setRange(0.0, 1.0)
        self.r2min_spin.setDecimals(3)
        self.r2min_spin.setSingleStep(0.01)
        self.r2min_spin.setValue(parameter.r2_min)
        self.r2min_spin.setToolTip(
            "Nur Einzelfits mit R² >= diesem Wert gehen in den\n"
            "Kittel-/LLG-Fit ein (zusaetzlich zur Problem-Einstufung).")
        form.addRow("R²-Minimum (Kittel/LLG):", self.r2min_spin)

        self.alpha_spin = QtWidgets.QDoubleSpinBox()
        self.alpha_spin.setRange(0.0001, 0.5)
        self.alpha_spin.setDecimals(4)
        self.alpha_spin.setSingleStep(0.001)
        self.alpha_spin.setValue(parameter.alpha_erwartet)
        self.alpha_spin.setToolTip(
            "Erwartete Gilbert-Daempfung: bestimmt die Fensterbreite\n"
            "(ΔB = 2ωα/γ) beim Auto-Fit mit vorgegebener Resonanz.")
        form.addRow("Erwartetes α (Vorgabe-Fenster):", self.alpha_spin)

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
        self.g_spin.setValue(standard.g_faktor)
        self.chk_gamma_fest.setChecked(standard.gamma_fest)
        self.geo_combo.setCurrentText(standard.geometrie)
        self.breite_spin.setValue(standard.breite_faktor)
        self.r2_spin.setValue(standard.r2_schwelle)
        self.r2min_spin.setValue(standard.r2_min)
        self.alpha_spin.setValue(standard.alpha_erwartet)

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
            alpha_erwartet=float(self.alpha_spin.value()),
        )

"""Bedienpanel des interaktiven In-Plot-Fittings (Fenster & Grenzen).

Steuert die ziehbaren Fenstergrenzen im Farbplot, die Uebernahme (Propagation)
manuell gesetzter Grenzen auf folgende Linescans, die explizite Fensterbreite
in Punkten und die Ausschlusszonen. Kernlogik:
:mod:`bbfmr.fit.fenster_steuerung`.
"""

from __future__ import annotations

from PySide6 import QtWidgets

#: Anzeige-Texte des Ueberschreib-Modus (Reihenfolge = Combo-Reihenfolge).
_MODUS_TEXTE = {
    "ueberschreiben": "ueberschreiben (alle betroffenen Fits ersetzen)",
    "ergaenzen": "ergaenzen (nur problematische Fits ersetzen)",
}


class FensterPanel(QtWidgets.QWidget):
    """Fenster-/Grenzen-Steuerung fuer das interaktive Fitten im Farbplot.

    Alle Aktionen laufen ueber Callbacks des Hauptfensters:

    * ``grenzen_umschalten(an: bool)``
    * ``breite_anwenden(punkte: int, modus: str)``
    * ``propagieren(modus: str)``
    * ``zone_zeichnen()``
    * ``zone_entfernen(index: int)``
    """

    def __init__(self, grenzen_umschalten=None, breite_anwenden=None,
                 propagieren=None, zone_zeichnen=None, zone_entfernen=None,
                 parent=None):
        super().__init__(parent)
        self._cb_grenzen = grenzen_umschalten
        self._cb_breite = breite_anwenden
        self._cb_propagieren = propagieren
        self._cb_zone_zeichnen = zone_zeichnen
        self._cb_zone_entfernen = zone_entfernen

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

        # --- Grenzen im Farbplot ---------------------------------------------
        self.chk_grenzen = QtWidgets.QCheckBox("Grenzen im Farbplot anzeigen && ziehen")
        self.chk_grenzen.setToolTip(
            "Zeichnet die linke (orange) und rechte (blaue) Fenstergrenze als\n"
            "Polylinien ueber den Farbplot. Grenze mit der Maus anfassen und\n"
            "horizontal ziehen -> der betroffene Linescan wird sofort neu gefittet.")
        self.chk_grenzen.toggled.connect(self._grenzen_umgeschaltet)
        lay.addWidget(self.chk_grenzen)

        # --- Ueberschreib-Modus ------------------------------------------------
        modus_form = QtWidgets.QFormLayout()
        self.modus_combo = QtWidgets.QComboBox()
        for schluessel, text in _MODUS_TEXTE.items():
            self.modus_combo.addItem(text, schluessel)
        self.modus_combo.setToolTip(
            "Gilt fuer Propagation, Breite-Anwenden und den Bereichs-Fit:\n"
            "'ueberschreiben' ersetzt alle betroffenen Fits, 'ergaenzen' nur\n"
            "die als problematisch markierten - gute Fits bleiben unangetastet.")
        modus_form.addRow("Modus:", self.modus_combo)
        lay.addLayout(modus_form)

        # --- Propagation --------------------------------------------------------
        grp_prop = QtWidgets.QGroupBox("Uebernahme gezogener Grenzen")
        prop_lay = QtWidgets.QVBoxLayout(grp_prop)
        self.chk_auto_propagieren = QtWidgets.QCheckBox(
            "gezogene Grenze automatisch auf folgende Linescans uebernehmen")
        self.chk_auto_propagieren.setToolTip(
            "Nach jedem Ziehen einer Grenze werden die Offsets (relativ zur\n"
            "Dispersions-Trasse) sofort auf alle folgenden Linescans angewandt.\n"
            "Das Fenster wandert dabei mit der Resonanz-Geraden mit.")
        prop_lay.addWidget(self.chk_auto_propagieren)
        self.btn_propagieren = QtWidgets.QPushButton(
            "Grenzen des aktuellen Linescans auf folgende uebernehmen")
        self.btn_propagieren.clicked.connect(
            lambda: self._cb_propagieren and self._cb_propagieren(self.modus()))
        prop_lay.addWidget(self.btn_propagieren)
        lay.addWidget(grp_prop)

        # --- Fensterbreite in Punkten -------------------------------------------
        grp_breite = QtWidgets.QGroupBox("Fensterbreite explizit setzen")
        breite_lay = QtWidgets.QHBoxLayout(grp_breite)
        breite_lay.addWidget(QtWidgets.QLabel("Breite:"))
        self.breite_spin = QtWidgets.QSpinBox()
        self.breite_spin.setRange(4, 100000)
        self.breite_spin.setValue(15)
        self.breite_spin.setSuffix(" Punkte")
        self.breite_spin.setToolTip(
            "Fenster = Trassen-Zentrum +/- Breite/2 in Feldpunkten des jeweiligen\n"
            "Linescans. Expliziter Hebel bei zu engen Automatik-Fenstern - die\n"
            "Automatik ueberstimmt diese Wahl nie stillschweigend.")
        breite_lay.addWidget(self.breite_spin)
        self.btn_breite = QtWidgets.QPushButton("Auf alle anwenden")
        self.btn_breite.clicked.connect(
            lambda: self._cb_breite and self._cb_breite(
                int(self.breite_spin.value()), self.modus()))
        breite_lay.addWidget(self.btn_breite)
        lay.addWidget(grp_breite)

        self.breite_info = QtWidgets.QLabel("aktuelles Fenster: –")
        self.breite_info.setWordWrap(True)
        lay.addWidget(self.breite_info)

        # --- Ausschlusszonen -------------------------------------------------------
        grp_zonen = QtWidgets.QGroupBox("Ausschlusszonen (Punkte aus der Auswertung nehmen)")
        zonen_lay = QtWidgets.QVBoxLayout(grp_zonen)
        self.btn_zone = QtWidgets.QPushButton("Zone im Farbplot einzeichnen")
        self.btn_zone.setToolTip(
            "Rechteck im Farbplot aufziehen - die Messpunkte darin werden aus\n"
            "allen (Nach-)Fits ausgenommen; betroffene Linescans fitten sofort neu.\n"
            "Esc bricht das Zeichnen ab.")
        self.btn_zone.clicked.connect(
            lambda: self._cb_zone_zeichnen and self._cb_zone_zeichnen())
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
    def modus(self) -> str:
        return self.modus_combo.currentData()

    def grenzen_aktiv(self) -> bool:
        return self.chk_grenzen.isChecked()

    def auto_propagieren(self) -> bool:
        return self.chk_auto_propagieren.isChecked()

    def breite_punkte(self) -> int:
        return int(self.breite_spin.value())

    def setze_breite_info(self, punkte: int | None, unten: float | None = None,
                          oben: float | None = None) -> None:
        """Zeigt die tatsaechliche Fensterbreite des aktuellen Linescans an."""
        if punkte is None:
            self.breite_info.setText("aktuelles Fenster: –")
            return
        bereich = (f" [{unten:.3f} – {oben:.3f} T]"
                   if unten is not None and oben is not None else "")
        self.breite_info.setText(f"aktuelles Fenster: {punkte} Punkte{bereich}")

    def setze_zonen(self, zonen) -> None:
        """Fuellt die (einsehbare, editierbare) Zonenliste."""
        self.zonen_liste.clear()
        for zone in zonen:
            self.zonen_liste.addItem(
                f"{zone.feld_min:.3f}–{zone.feld_max:.3f} T, "
                f"{zone.frequenz_min/1e9:.2f}–{zone.frequenz_max/1e9:.2f} GHz")

    # --- intern ------------------------------------------------------------------
    def _grenzen_umgeschaltet(self, an: bool) -> None:
        if self._cb_grenzen is not None:
            self._cb_grenzen(bool(an))

    def _zone_entfernen_geklickt(self) -> None:
        zeile = self.zonen_liste.currentRow()
        if zeile >= 0 and self._cb_zone_entfernen is not None:
            self._cb_zone_entfernen(zeile)

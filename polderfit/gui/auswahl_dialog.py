# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Dialog "Auto-Fit: Bereich, Jumper & Resonanzen" - wird vor jeder Stapelauswertung gezeigt.

Fragt die Unterabtastung (jeden n-ten Punkt, getrennt fuer Frequenz- und
Feldachse) und die Bereichseinschraenkung ab (Frequenz-/Feldfenster plus
Frequenz-Ausschlussbaender wie "3-5" GHz). Eine Live-Zusammenfassung zeigt,
wie viele Linescans die aktuelle Auswahl uebrig laesst. Die zuletzt benutzte
Auswahl wird vorbelegt.

**ROI (Region of Interest) vor dem Auto-Fit:** Der Feld-/Frequenzbereich wird
aus dem gezoomten Farbplot vorbelegt (``zoom_bereich``) oder direkt als
Rechteck im Farbplot aufgezogen: "ROI im Farbplot aufziehen …" schliesst den
Dialog mit :attr:`AuswahlDialog.ROI_AUFZIEHEN`; das Hauptfenster startet den
Rechteck-Modus und oeffnet den Dialog danach mit dem Rechteck (``roi_bereich``)
wieder. Ein enger Feldbereich (und "jeder n-te Feldpunkt") beschleunigt den
Auto-Fit deutlich - bei mehreren Resonanzen je Linescan besonders.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6 import QtWidgets

from ..fit.auswahl import Auswertungsauswahl, parse_bereiche
from ..io.datensatz import Messdatensatz
from .widgets import RuhigeComboBox, RuhigeDoubleSpinBox


@dataclass
class RoiAnfrage:
    """Rueckgabe von ``Hauptfenster._frage_auswahl``: Nutzer will zuerst eine ROI
    im Farbplot aufziehen; ``auswahl`` sind die bisherigen Dialog-Eingaben."""

    auswahl: Auswertungsauswahl | None
    n_moden: int = 1
    zweistufig: bool = False


class AuswahlDialog(QtWidgets.QDialog):
    """Fragt die :class:`Auswertungsauswahl` fuer den naechsten Auto-Fit ab."""

    #: Rueckgabecode von ``exec()``: Nutzer will zuerst eine ROI (Rechteck) im
    #: Farbplot aufziehen; :meth:`zwischenstand` liefert die bisherigen Eingaben.
    ROI_AUFZIEHEN = 2

    def __init__(self, datensatz: Messdatensatz,
                 letzte: Auswertungsauswahl | None = None, parent=None,
                 n_moden: int = 1, zweistufig: bool = False,
                 zoom_bereich: tuple[float, float, float, float] | None = None,
                 roi_moeglich: bool = False,
                 roi_bereich: tuple[float, float, float, float] | None = None):
        """``n_moden``/``zweistufig``: Vorbelegung der Resonanzen je Linescan
        (Dropdown) und der erweiterten Option "erst klassisch, dann ergaenzen".
        ``zoom_bereich``/``roi_bereich``: ``(feld_min, feld_max, f_min_ghz,
        f_max_ghz)`` - sichtbarer Farbplot-Ausschnitt bzw. aufgezogenes
        Rechteck; belegt den Bereich vor (Rechteck vor Zoom vor letzter Auswahl).
        ``roi_moeglich``: Knopf "ROI im Farbplot aufziehen …" anbieten."""
        super().__init__(parent)
        self.setWindowTitle("Auto-Fit: Bereich, Jumper & Resonanzen")
        self.setModal(True)
        self._datensatz = datensatz
        self._zwischenstand: Auswertungsauswahl | None = None
        vorgabe = letzte if letzte is not None else Auswertungsauswahl()

        frequenzen = datensatz.frequenzen
        b_min, b_max = datensatz.feld_bereich()
        f_min_ghz = float(frequenzen.min()) / 1e9 if frequenzen.size else 0.0
        f_max_ghz = float(frequenzen.max()) / 1e9 if frequenzen.size else 1.0
        self._voller_bereich = (b_min, b_max, f_min_ghz, f_max_ghz)
        self._zoom_bereich = zoom_bereich

        lay = QtWidgets.QVBoxLayout(self)
        kopf = QtWidgets.QLabel(
            f"Auswertung von <b>{len(datensatz)}</b> Linescans "
            f"({f_min_ghz:.2f}-{f_max_ghz:.2f} GHz, {b_min:.3f}-{b_max:.3f} T). "
            f"Unterabtastung beschleunigt; Bereiche grenzen die Auswertung ein. "
            f"<b>Tipp:</b> Ein enger Feldbereich (ROI) und „jeder n-te Feldpunkt“ "
            f"machen den Auto-Fit deutlich schneller – bei mehreren Resonanzen besonders.")
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
            box = RuhigeDoubleSpinBox()   # Punkt und Komma; Mausrad nur mit Fokus
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
        roi_zeile = QtWidgets.QHBoxLayout()
        self.btn_roi = QtWidgets.QPushButton("ROI im Farbplot aufziehen …")
        self.btn_roi.setToolTip(
            "Dialog schließen, Rechteck (Feld × Frequenz) im Farbplot aufziehen –\n"
            "der Dialog öffnet sich danach mit diesem Bereich wieder.")
        self.btn_roi.setEnabled(bool(roi_moeglich))
        self.btn_roi.clicked.connect(self._roi_geklickt)
        roi_zeile.addWidget(self.btn_roi)
        self.btn_zoom = QtWidgets.QPushButton("Zoom-Ausschnitt übernehmen")
        self.btn_zoom.setToolTip("Sichtbaren Ausschnitt des Farbplots als Bereich verwenden.")
        self.btn_zoom.setEnabled(zoom_bereich is not None)
        self.btn_zoom.clicked.connect(self._zoom_uebernehmen)
        roi_zeile.addWidget(self.btn_zoom)
        self.btn_alles = QtWidgets.QPushButton("Ganzer Bereich")
        # Gebundene Methoden statt Lambdas: ein Lambda, das ``self`` einfaengt, bildet
        # einen Referenzzyklus, und ein parentloser Dialog wuerde dann erst beim
        # Interpreter-Ende (nach der QApplication) freigegeben -> Absturz.
        self.btn_alles.clicked.connect(self._ganzer_bereich)
        roi_zeile.addWidget(self.btn_alles)
        form_b.addRow("", roi_zeile)
        self.bereich_hinweis = QtWidgets.QLabel("")
        self.bereich_hinweis.setWordWrap(True)
        form_b.addRow("", self.bereich_hinweis)
        if roi_bereich is not None:
            self.setze_bereich(*roi_bereich)
            self.bereich_hinweis.setText("Bereich = im Farbplot aufgezogenes Rechteck (ROI).")
        elif zoom_bereich is not None:
            self.setze_bereich(*zoom_bereich)
            self.bereich_hinweis.setText("Bereich = sichtbarer Farbplot-Ausschnitt (Zoom).")

        self.ausschluss = QtWidgets.QLineEdit(
            "; ".join(f"{lo/1e9:g}-{hi/1e9:g}" for lo, hi in vorgabe.frequenz_ausschluss))
        self.ausschluss.setPlaceholderText("z. B. 3-5; 10.2-11")
        self.ausschluss.setToolTip(
            "Frequenzbaender (GHz), die NICHT ausgewertet werden - mehrere mit ';' trennen.")
        form_b.addRow("Frequenz-Ausschluesse (GHz):", self.ausschluss)
        lay.addWidget(grp_b)

        # --- Resonanzen je Linescan (Moden) ----------------------------------
        grp_m = QtWidgets.QGroupBox("Resonanzen je Linescan")
        form_m = QtWidgets.QFormLayout(grp_m)
        self.moden_combo = RuhigeComboBox()
        self.moden_combo.addItem("1 – klassisch (eine Resonanz)", 1)
        self.moden_combo.addItem("2 – zwei nahe Resonanzen", 2)
        for k in range(3, 7):
            self.moden_combo.addItem(f"{k} Resonanzen", k)
        self.moden_combo.setToolTip(
            "Anzahl simultan gefitteter Resonanzen je Linescan.\n"
            "1 = klassischer Auto-Fit; 2 = zwei nahe Dips (z. B. zwei magnetische Moden).")
        index_m = self.moden_combo.findData(max(1, min(6, int(n_moden))))
        self.moden_combo.setCurrentIndex(max(0, index_m))
        form_m.addRow("Anzahl:", self.moden_combo)
        self.chk_zweistufig = QtWidgets.QCheckBox(
            "Erweitert: erst klassischer Auto-Fit (1 Resonanz), dann weitere Resonanzen ergänzen")
        self.chk_zweistufig.setToolTip(
            "Stufe 1: klassischer Ein-Moden-Fit (robuste Fenstersuche, Hauptmode).\n"
            "Stufe 2: je Linescan weitere Resonanzen aus dem Residuum ergänzen und alle\n"
            "Moden simultan fitten. Gelingt Stufe 2 nicht, bleibt das klassische Ergebnis\n"
            "stehen – keine Phantom-Resonanzen auf Ein-Moden-Daten.")
        self.chk_zweistufig.setChecked(bool(zweistufig))
        form_m.addRow("", self.chk_zweistufig)
        self.moden_combo.currentIndexChanged.connect(self._moden_geaendert)
        self._moden_geaendert()
        lay.addWidget(grp_m)

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

    def n_moden(self) -> int:
        """Gewaehlte Anzahl Resonanzen je Linescan (1 = klassisch)."""
        return int(self.moden_combo.currentData() or 1)

    def setze_bereich(self, feld_min: float, feld_max: float,
                      f_min_ghz: float, f_max_ghz: float) -> None:
        """Feld-/Frequenzbereich (T, GHz) in die Eingabefelder uebernehmen."""
        self.b_min.setValue(float(min(feld_min, feld_max)))
        self.b_max.setValue(float(max(feld_min, feld_max)))
        self.f_min.setValue(float(min(f_min_ghz, f_max_ghz)))
        self.f_max.setValue(float(max(f_min_ghz, f_max_ghz)))

    def _ganzer_bereich(self) -> None:
        self.setze_bereich(*self._voller_bereich)
        self.bereich_hinweis.setText("")

    def _zoom_uebernehmen(self) -> None:
        if self._zoom_bereich is not None:
            self.setze_bereich(*self._zoom_bereich)
            self.bereich_hinweis.setText("Bereich = sichtbarer Farbplot-Ausschnitt (Zoom).")

    def _roi_geklickt(self) -> None:
        """Dialog mit ROI_AUFZIEHEN beenden; Eingaben bleiben als Zwischenstand."""
        try:
            self._zwischenstand = self.auswahl()
        except ValueError:
            self._zwischenstand = None
        self.done(self.ROI_AUFZIEHEN)

    def zwischenstand(self) -> Auswertungsauswahl | None:
        """Eingaben beim Klick auf "ROI im Farbplot aufziehen …" (Vorbelegung danach)."""
        return self._zwischenstand

    def zweistufig(self) -> bool:
        """Erweiterte Option: erst klassisch fitten, dann weitere Moden ergaenzen."""
        return self.n_moden() > 1 and self.chk_zweistufig.isChecked()

    def _moden_geaendert(self, *_args) -> None:
        self.chk_zweistufig.setEnabled(self.n_moden() > 1)

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

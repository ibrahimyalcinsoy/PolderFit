"""Hauptfenster der Ananas-GUI.

Verbindet die 2D-Uebersicht mit dem interaktiven Linescan-Panel und stellt den
gesamten Arbeitsablauf bereit: TDMS laden -> AutoWindows + Auto-Fit -> je
Frequenz Grenzen verschieben und neu fitten -> uebergreifende Auswertung ->
Export (TDMS, Excel/CSV). Der Korrekturlauf (continue / zurueck / nochmal fitten)
ist ueber die Navigations- und "Neu fitten"-Schaltflaechen abgebildet.
"""

from __future__ import annotations

import os

import numpy as np
from PySide6 import QtWidgets, QtCore

from ..io import lade_tdms, schreibe_ergebnis_tdms
from ..fit.batch import StapelErgebnis, fitte_alle, fitte_neu
from ..persistenz.ergebnis_export import exportiere_excel, exportiere_csv
from ..auswertung.uebersicht import auswertung_kittel_llg
from .matrix_ansicht import MatrixAnsicht
from .fit_ansicht import FitAnsicht


class Hauptfenster(QtWidgets.QMainWindow):
    """Zentrales Anwendungsfenster."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ananas – Breitband-FMR-Auswertung")
        self.resize(1300, 800)

        self.stapel: StapelErgebnis | None = None
        self.aktueller_index: int = 0

        self.matrix = MatrixAnsicht(frequenz_gewaehlt=self._frequenz_gewaehlt)
        self.fitansicht = FitAnsicht(grenzen_geaendert=self._grenzen_geaendert)

        self._baue_oberflaeche()
        self._baue_werkzeugleiste()
        self.statusBar().showMessage("Bereit. Bitte eine TDMS-Datei laden.")

    # --- Aufbau ------------------------------------------------------------
    def _baue_oberflaeche(self):
        zentral = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        zentral.addWidget(self.matrix)

        rechts = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(rechts)
        layout.addWidget(self.fitansicht)

        knopfreihe = QtWidgets.QHBoxLayout()
        self.btn_zurueck = QtWidgets.QPushButton("◀ Zurueck")
        self.btn_weiter = QtWidgets.QPushButton("Weiter ▶")
        self.btn_neu = QtWidgets.QPushButton("Nochmal fitten")
        self.btn_naechstes_problem = QtWidgets.QPushButton("Naechster Problemfit")
        self.btn_zurueck.clicked.connect(lambda: self._navigiere(-1))
        self.btn_weiter.clicked.connect(lambda: self._navigiere(+1))
        self.btn_neu.clicked.connect(self._neu_fitten)
        self.btn_naechstes_problem.clicked.connect(self._naechster_problemfit)
        for b in (self.btn_zurueck, self.btn_weiter, self.btn_neu, self.btn_naechstes_problem):
            knopfreihe.addWidget(b)
        layout.addLayout(knopfreihe)

        self.label_info = QtWidgets.QLabel("—")
        layout.addWidget(self.label_info)

        zentral.addWidget(rechts)
        zentral.setSizes([550, 750])
        self.setCentralWidget(zentral)

    def _baue_werkzeugleiste(self):
        leiste = self.addToolBar("Hauptaktionen")
        akt_laden = leiste.addAction("TDMS laden")
        akt_laden.triggered.connect(self._laden)
        akt_fit = leiste.addAction("Auto-Fit (alle)")
        akt_fit.triggered.connect(self._auto_fit)
        leiste.addSeparator()
        akt_kittel = leiste.addAction("Kittel/LLG-Auswertung")
        akt_kittel.triggered.connect(self._kittel_llg)
        leiste.addSeparator()
        akt_tdms = leiste.addAction("Export TDMS")
        akt_tdms.triggered.connect(self._export_tdms)
        akt_xlsx = leiste.addAction("Export Excel")
        akt_xlsx.triggered.connect(self._export_excel)
        akt_csv = leiste.addAction("Export CSV")
        akt_csv.triggered.connect(self._export_csv)

    # --- Aktionen ----------------------------------------------------------
    def _laden(self):
        pfad, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "TDMS-Datei laden", "", "TDMS (*.tdms)")
        if not pfad:
            return
        try:
            datensatz = lade_tdms(pfad)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"Laden fehlgeschlagen:\n{exc}")
            return
        self.matrix.zeige(datensatz)
        # Vorlaeufiger Stapel ohne Fit (nur Anzeige).
        self.stapel = StapelErgebnis(datensatz=datensatz)
        self.statusBar().showMessage(
            f"Geladen: {os.path.basename(pfad)} ({datensatz.format_typ}, "
            f"{len(datensatz)} Frequenzen). Jetzt 'Auto-Fit' starten.")

    def _auto_fit(self):
        if self.stapel is None:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst eine TDMS-Datei laden.")
            return
        self.statusBar().showMessage("Auto-Fit laeuft …")
        QtWidgets.QApplication.processEvents()
        self.stapel = fitte_alle(self.stapel.datensatz)
        self._aktualisiere_overlay()
        self.aktueller_index = 0
        self._zeige_aktuellen()
        n_prob = len(self.stapel.index_problematisch())
        statistik = self.stapel.problem_statistik()
        aufschluesselung = ", ".join(f"{g}: {n}" for g, n in statistik.items())
        self.statusBar().showMessage(
            f"Auto-Fit fertig. {len(self.stapel.ergebnisse)} Fits, "
            f"{n_prob} problematisch. {aufschluesselung}")

    def _aktualisiere_overlay(self):
        bres = np.array([e.B_res for e in self.stapel.ergebnisse])
        self.matrix.aktualisiere_resonanz(self.stapel.datensatz.frequenzen, bres)

    def _zeige_aktuellen(self):
        if not self.stapel or not self.stapel.ergebnisse:
            return
        i = self.aktueller_index
        ls = self.stapel.zugeschnitten[i] if self.stapel.zugeschnitten else self.stapel.datensatz.linescans[i]
        # Volldaten fuer die Anzeige (nicht beschnitten), Grenzen separat.
        voll = self.stapel.datensatz.linescans[i]
        unten, oben = self.stapel.fenster[i]
        self.fitansicht.zeige(voll, unten, oben, self.stapel.ergebnisse[i])
        self.matrix.markiere_frequenz(i)
        e = self.stapel.ergebnisse[i]
        status = f"PROBLEM: {e.problem_text}" if e.problematisch else "OK"
        # 1-R² in wissenschaftlicher Notation, damit echte Variation sichtbar wird.
        eins_minus_r2 = (1.0 - e.R2) if np.isfinite(e.R2) else float("nan")
        text = (
            f"[{i+1}/{len(self.stapel.ergebnisse)}] f={e.frequenz/1e9:.3f} GHz │ "
            f"B_res={e.B_res:.4f} T │ alpha={e.alpha:.2e} │ "
            f"rmse_norm={e.rmse_norm:.3f} │ 1-R²={eins_minus_r2:.1e} │ {status}")
        self.label_info.setText(text)
        self.statusBar().showMessage(text)

    def _navigiere(self, schritt: int):
        if not self.stapel or not self.stapel.ergebnisse:
            return
        self.aktueller_index = int(np.clip(self.aktueller_index + schritt, 0,
                                           len(self.stapel.ergebnisse) - 1))
        self._zeige_aktuellen()

    def _naechster_problemfit(self):
        if not self.stapel or not self.stapel.ergebnisse:
            return
        probleme = self.stapel.index_problematisch()
        spaeter = [i for i in probleme if i > self.aktueller_index]
        ziel = spaeter[0] if spaeter else (probleme[0] if probleme else None)
        if ziel is None:
            QtWidgets.QMessageBox.information(self, "Fertig", "Keine problematischen Fits mehr.")
            return
        self.aktueller_index = ziel
        self._zeige_aktuellen()

    def _grenzen_geaendert(self, unten: float, oben: float):
        """Callback aus dem Linescan-Panel: neue Bandgrenzen -> sofort neu fitten."""
        if not self.stapel or not self.stapel.ergebnisse:
            return
        i = self.aktueller_index
        fitte_neu(self.stapel, i, feld_unten=unten, feld_oben=oben)
        self._zeige_aktuellen()
        self._aktualisiere_overlay()

    def _neu_fitten(self):
        if not self.stapel or not self.stapel.ergebnisse:
            return
        i = self.aktueller_index
        unten, oben = self.stapel.fenster[i]
        fitte_neu(self.stapel, i, feld_unten=unten, feld_oben=oben)
        self._zeige_aktuellen()
        self._aktualisiere_overlay()

    def _kittel_llg(self):
        if not self.stapel or not self.stapel.ergebnisse:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst fitten.")
            return
        geo, ok = QtWidgets.QInputDialog.getItem(
            self, "Geometrie", "Kittel-Geometrie:", ["oop", "ip"], 0, False)
        if not ok:
            return
        try:
            info = auswertung_kittel_llg(self.stapel.ergebnisse, geometrie=geo)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Auswertung", str(exc))
            return
        from ..auswertung.uebersicht import (
            plot_resonanz_vs_frequenz, plot_linienbreite, plot_resonanz_vs_temperatur)
        plot_resonanz_vs_frequenz(self.stapel.ergebnisse, geometrie=geo)
        plot_linienbreite(self.stapel.ergebnisse, gamma=info["kittel"]["gamma"])
        plot_resonanz_vs_temperatur(self.stapel.ergebnisse)
        import matplotlib.pyplot as plt
        plt.show()

    # --- Export ------------------------------------------------------------
    def _export_tdms(self):
        if not self._fits_vorhanden():
            return
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, "TDMS speichern", "", "TDMS (*.tdms)")
        if not pfad:
            return
        schreibe_ergebnis_tdms(pfad, self.stapel.zugeschnitten, self.stapel.fitkurven())
        self.statusBar().showMessage(f"TDMS gespeichert: {pfad}")

    def _export_excel(self):
        if not self._fits_vorhanden():
            return
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Excel speichern", "", "Excel (*.xlsx)")
        if not pfad:
            return
        global_param = None
        try:
            info = auswertung_kittel_llg(self.stapel.ergebnisse)
            global_param = {**{f"kittel_{k}": v for k, v in info["kittel"].items()},
                            **{f"llg_{k}": v for k, v in info["llg"].items()}}
        except Exception:
            pass
        exportiere_excel(self.stapel.ergebnisse, pfad, global_param)
        self.statusBar().showMessage(f"Excel gespeichert: {pfad}")

    def _export_csv(self):
        if not self._fits_vorhanden():
            return
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, "CSV speichern", "", "CSV (*.csv)")
        if not pfad:
            return
        exportiere_csv(self.stapel.ergebnisse, pfad)
        self.statusBar().showMessage(f"CSV gespeichert: {pfad}")

    def _fits_vorhanden(self) -> bool:
        if not self.stapel or not self.stapel.ergebnisse:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst fitten.")
            return False
        return True

    def _frequenz_gewaehlt(self, index: int):
        if not self.stapel or not self.stapel.ergebnisse:
            return
        self.aktueller_index = index
        self._zeige_aktuellen()


def starte_gui(argv=None):
    """Startet die Qt-Anwendung."""
    import sys

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(argv or sys.argv)
    fenster = Hauptfenster()
    fenster.show()
    return app.exec()

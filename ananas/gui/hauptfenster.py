"""Hauptfenster der Ananas-GUI.

Verbindet die 2D-Uebersicht mit dem interaktiven Linescan-Panel und stellt den
gesamten Arbeitsablauf bereit: TDMS laden -> AutoWindows + Auto-Fit -> je
Frequenz Grenzen verschieben und neu fitten -> uebergreifende Auswertung ->
Export (TDMS, Excel/CSV). Der Korrekturlauf (continue / zurueck / nochmal fitten)
ist ueber die Navigations- und "Neu fitten"-Schaltflaechen abgebildet.

Lang laufende Schritte (Laden grosser Dateien, Auto-Fit ueber alle Frequenzen)
laufen in einem Hintergrund-Thread; ein andockbares Aktivitaets-Panel zeigt
Fortschrittsbalken und ein Live-Protokoll, damit die App nie "eingefroren" wirkt.
"""

from __future__ import annotations

import html
import os
from pathlib import Path

import numpy as np
from PySide6 import QtWidgets, QtCore, QtGui

from ..io import lade_tdms, schreibe_ergebnis_tdms
from ..fit.batch import StapelErgebnis, fitte_alle, fitte_neu
from ..persistenz.ergebnis_export import exportiere_excel, exportiere_csv
from ..auswertung.uebersicht import auswertung_kittel_llg
from .matrix_ansicht import MatrixAnsicht
from .fit_ansicht import FitAnsicht
from .navigator_ansicht import NavigatorAnsicht
from .arbeiter import Arbeiter
from .stil import ANANAS_QSS

#: Pfad zum Ananas-App-Icon (SVG, skaliert verlustfrei).
ICON_PFAD = str(Path(__file__).resolve().parent / "assets" / "ananas.svg")

#: Quellcode-Repository (im Hilfe-Dialog verlinkt).
REPO_URL = "https://github.com/ibrahimyalcinsoy/Ananas"

#: Farben fuer das Aktivitaetsprotokoll je Meldungsart.
_LOG_FARBEN = {
    "info": "#5A5648", "ok": "#2E7D38", "warn": "#B8860B",
    "problem": "#C0392B", "auto": "#6B6657",
}


def app_icon() -> QtGui.QIcon:
    """Liefert das Ananas-App-Icon (leeres QIcon, falls die Datei fehlt)."""
    return QtGui.QIcon(ICON_PFAD)


class Hauptfenster(QtWidgets.QMainWindow):
    """Zentrales Anwendungsfenster."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ananas – Breitband-FMR-Auswertung")
        self.setWindowIcon(app_icon())
        self.resize(1400, 860)

        self.stapel: StapelErgebnis | None = None
        self.aktueller_index: int = 0

        # Hintergrund-Job-Zustand.
        self._thread: QtCore.QThread | None = None
        self._arbeiter: Arbeiter | None = None
        self._job_laeuft: bool = False
        self._job_titel: str = ""
        self._bei_fertig = None

        self.matrix = MatrixAnsicht(frequenz_gewaehlt=self._frequenz_gewaehlt,
                                    zoom_geaendert=self._auf_zoom)
        self.fitansicht = FitAnsicht(grenzen_geaendert=self._grenzen_geaendert)
        self.navigator = NavigatorAnsicht(bereich_gewaehlt=self._navigator_bereich)

        self._baue_oberflaeche()
        self._baue_werkzeugleiste()
        self._baue_aktivitaet_dock()
        self._baue_navigator_dock()
        self.statusBar().showMessage("Bereit. Bitte eine TDMS-Datei laden.")
        self._log("Ananas bereit. Bitte eine TDMS-Datei laden.", "info")

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
        zentral.setSizes([560, 760])
        self.setCentralWidget(zentral)

    def _baue_werkzeugleiste(self):
        leiste = self.addToolBar("Hauptaktionen")
        leiste.setMovable(False)

        # Klickbares Ananas×WMI-Logo + Wortmarke ganz links -> oeffnet die Hilfe.
        self.btn_logo = QtWidgets.QToolButton()
        self.btn_logo.setIcon(app_icon())
        self.btn_logo.setIconSize(QtCore.QSize(26, 26))
        self.btn_logo.setText(" Ananas")
        self.btn_logo.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.btn_logo.setAutoRaise(True)
        self.btn_logo.setToolTip("Hilfe & Infos (Bedienung, Walther-Meißner-Institut, Repository)")
        self.btn_logo.setStyleSheet("font-weight: 600; font-size: 14px; padding: 2px 8px;")
        self.btn_logo.clicked.connect(self._zeige_hilfe)
        leiste.addWidget(self.btn_logo)
        leiste.addSeparator()

        self.akt_laden = leiste.addAction("TDMS laden")
        self.akt_laden.triggered.connect(self._laden)
        self.akt_fit = leiste.addAction("Auto-Fit (alle)")
        self.akt_fit.triggered.connect(self._auto_fit)
        leiste.addSeparator()
        self.akt_kittel = leiste.addAction("Kittel/LLG-Auswertung")
        self.akt_kittel.triggered.connect(self._kittel_llg)
        leiste.addSeparator()
        self.akt_tdms = leiste.addAction("Export TDMS")
        self.akt_tdms.triggered.connect(self._export_tdms)
        self.akt_xlsx = leiste.addAction("Export Excel")
        self.akt_xlsx.triggered.connect(self._export_excel)
        self.akt_csv = leiste.addAction("Export CSV")
        self.akt_csv.triggered.connect(self._export_csv)

        # Ansicht-Umschalter: ganzer Feldsweep statt Zoom aufs Resonanzband.
        leiste.addSeparator()
        self.akt_vollbereich = leiste.addAction("Vollbereich")
        self.akt_vollbereich.setCheckable(True)
        self.akt_vollbereich.setToolTip(
            "Ganzen Feldsweep zeigen statt aufs Resonanzband zu zoomen.")
        self.akt_vollbereich.toggled.connect(self._vollbereich_umschalten)

        # Problematische Fits im Resonanz-Overlay der Übersicht ausblenden.
        self.akt_problemfits = leiste.addAction("Problemfits ausblenden")
        self.akt_problemfits.setCheckable(True)
        self.akt_problemfits.setToolTip(
            "Problematische Fits im Resonanz-Overlay der Übersicht ausblenden.")
        self.akt_problemfits.toggled.connect(self._problemfits_umschalten)

        # Sichtbarkeits-Umschalter fuer das Aktivitaets-Panel (rechts).
        leiste.addSeparator()
        self.akt_aktivitaet = leiste.addAction("Aktivität")

    def _baue_aktivitaet_dock(self):
        """Andockbares (abtrennbares) Panel mit Fortschritt und Live-Protokoll."""
        dock = QtWidgets.QDockWidget("Aktivität / Hintergrund", self)
        dock.setObjectName("aktivitaet_dock")
        dock.setAllowedAreas(
            QtCore.Qt.RightDockWidgetArea | QtCore.Qt.LeftDockWidgetArea
            | QtCore.Qt.BottomDockWidgetArea
        )
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetClosable
        )

        inhalt = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(inhalt)
        lay.setContentsMargins(10, 8, 10, 10)

        self.aktivitaet_label = QtWidgets.QLabel("Bereit.")
        self.aktivitaet_label.setObjectName("aktivitaet")
        self.aktivitaet_label.setWordWrap(True)
        lay.addWidget(self.aktivitaet_label)

        self.fortschritt_balken = QtWidgets.QProgressBar()
        self.fortschritt_balken.setRange(0, 1)
        self.fortschritt_balken.setValue(0)
        lay.addWidget(self.fortschritt_balken)

        self.protokoll_ansicht = QtWidgets.QPlainTextEdit()
        self.protokoll_ansicht.setReadOnly(True)
        self.protokoll_ansicht.setMaximumBlockCount(5000)
        mono = QtGui.QFont("monospace")
        mono.setStyleHint(QtGui.QFont.Monospace)
        mono.setPointSize(9)
        self.protokoll_ansicht.setFont(mono)
        lay.addWidget(self.protokoll_ansicht, 1)

        leeren = QtWidgets.QPushButton("Protokoll leeren")
        leeren.clicked.connect(self.protokoll_ansicht.clear)
        lay.addWidget(leeren, 0, QtCore.Qt.AlignRight)

        dock.setWidget(inhalt)
        dock.setMinimumWidth(300)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self.aktivitaet_dock = dock
        # Toolbar-Umschalter mit der Sichtbarkeit des Docks verbinden.
        self.akt_aktivitaet.setCheckable(True)
        self.akt_aktivitaet.setChecked(True)
        self.akt_aktivitaet.toggled.connect(dock.setVisible)
        dock.visibilityChanged.connect(self.akt_aktivitaet.setChecked)

    def _baue_navigator_dock(self):
        """Navigator-Minimap (links); erscheint automatisch beim Zoomen der Übersicht."""
        dock = QtWidgets.QDockWidget("Navigator", self)
        dock.setObjectName("navigator_dock")
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea
            | QtCore.Qt.BottomDockWidgetArea
        )
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetClosable
        )
        dock.setWidget(self.navigator)
        dock.setMinimumWidth(220)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        dock.setVisible(False)  # erscheint erst, sobald gezoomt wird
        self.navigator_dock = dock

    # --- Aktivitaet / Protokoll -------------------------------------------
    def _log(self, text: str, art: str = "info") -> None:
        """Schreibt eine farbige, zeitgestempelte Protokollzeile (Auto-Scroll)."""
        farbe = _LOG_FARBEN.get(art, "#5A5648")
        stempel = QtCore.QTime.currentTime().toString("HH:mm:ss")
        zeile = (f'<span style="color:#B0A99A">{stempel}</span> '
                 f'<span style="color:{farbe}">{html.escape(text)}</span>')
        self.protokoll_ansicht.appendHtml(zeile)
        leiste = self.protokoll_ansicht.verticalScrollBar()
        leiste.setValue(leiste.maximum())

    def _setze_aktivitaet(self, text: str) -> None:
        self.aktivitaet_label.setText(text)

    def _setze_bedienelemente(self, an: bool) -> None:
        """Sperrt/entsperrt Aktionen und Navigation waehrend eines Hintergrund-Jobs."""
        for aktion in (self.akt_laden, self.akt_fit, self.akt_kittel,
                       self.akt_tdms, self.akt_xlsx, self.akt_csv):
            aktion.setEnabled(an)
        for knopf in (self.btn_zurueck, self.btn_weiter, self.btn_neu,
                      self.btn_naechstes_problem):
            knopf.setEnabled(an)

    # --- Job-Steuerung (Hintergrund-Thread) -------------------------------
    def _starte_job(self, funktion, bei_fertig, titel: str) -> None:
        """Fuehrt ``funktion(melde)`` im Hintergrund aus; ``bei_fertig(ergebnis)`` danach."""
        if self._job_laeuft:
            self._log("Es laeuft bereits ein Hintergrundprozess – bitte warten.", "warn")
            return
        self._job_laeuft = True
        self._job_titel = titel
        self._bei_fertig = bei_fertig
        self._setze_bedienelemente(False)
        self._setze_aktivitaet(titel)
        self._log(titel, "info")
        self.fortschritt_balken.setRange(0, 0)  # "busy", bis erster Fortschritt kommt

        self._thread = QtCore.QThread(self)
        self._arbeiter = Arbeiter(funktion)
        self._arbeiter.moveToThread(self._thread)
        self._thread.started.connect(self._arbeiter.ausfuehren)
        # WICHTIG: an gebundene Methoden des (Haupt-Thread-)Fensters binden, NICHT an
        # Lambdas – nur so erkennt Qt die Thread-Zugehoerigkeit und stellt die Slots
        # via QueuedConnection im GUI-Thread zu (sonst liefe der Aufraeum-Code im
        # Worker-Thread: "QThread tried to wait on itself").
        self._arbeiter.fortschritt.connect(self._auf_fortschritt)
        self._arbeiter.protokoll.connect(self._auf_protokoll)
        self._arbeiter.fehler.connect(self._auf_fehler)
        self._arbeiter.fertig.connect(self._auf_fertig)
        self._thread.start()

    def _auf_fortschritt(self, i: int, n: int) -> None:
        if n <= 0:
            self.fortschritt_balken.setRange(0, 0)
            return
        self.fortschritt_balken.setRange(0, n)
        self.fortschritt_balken.setValue(i)
        self._setze_aktivitaet(f"{self._job_titel}   {i}/{n}")

    def _auf_protokoll(self, text: str) -> None:
        art = "problem" if "⚠" in text else ("ok" if "✓" in text else "auto")
        self._log(text, art)

    def _auf_fertig(self, ergebnis) -> None:
        bei_fertig = self._bei_fertig
        try:
            if bei_fertig is not None:
                bei_fertig(ergebnis)
        finally:
            self._bei_fertig = None
            self._job_aufraeumen()

    def _auf_fehler(self, text: str) -> None:
        erste = text.splitlines()[0] if text else "Unbekannter Fehler"
        self._log("FEHLER: " + erste, "problem")
        QtWidgets.QMessageBox.critical(self, "Fehler", text)
        self._job_aufraeumen()

    def _job_aufraeumen(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._arbeiter.deleteLater()
            self._thread.deleteLater()
        self._thread = None
        self._arbeiter = None
        self._job_laeuft = False
        self.fortschritt_balken.setRange(0, 1)
        self.fortschritt_balken.setValue(0)
        self._setze_aktivitaet("Bereit.")
        self._setze_bedienelemente(True)

    # --- Aktionen ----------------------------------------------------------
    def _laden(self):
        if self._job_laeuft:
            return
        pfad, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "TDMS-Datei laden", "", "TDMS (*.tdms)")
        if not pfad:
            return

        def aufgabe(melde):
            melde(0, 0, f"Lade {os.path.basename(pfad)} …")
            datensatz = lade_tdms(pfad)
            melde(0, 0, f"Baue Übersicht auf ({len(datensatz)} Frequenzen) …")
            return (pfad, datensatz)

        def bei_fertig(res):
            pfad_, datensatz = res
            self.matrix.zeige(datensatz)
            mat, ext = self.matrix.thumbnail()
            self.navigator.zeige(mat, ext)
            self.navigator_dock.setVisible(False)  # erst beim Zoomen einblenden
            self.stapel = StapelErgebnis(datensatz=datensatz)
            self._log(
                f"Geladen: {os.path.basename(pfad_)} – {datensatz.format_typ}, "
                f"{len(datensatz)} Frequenzen.", "ok")
            self.statusBar().showMessage(
                f"Geladen: {os.path.basename(pfad_)} ({datensatz.format_typ}, "
                f"{len(datensatz)} Frequenzen). Jetzt 'Auto-Fit' starten.")

        self._starte_job(aufgabe, bei_fertig, f"Lade {os.path.basename(pfad)} …")

    def _auto_fit(self):
        if self.stapel is None:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst eine TDMS-Datei laden.")
            return
        datensatz = self.stapel.datensatz

        def aufgabe(melde):
            n = len(datensatz.linescans)
            schritt = max(1, n // 50)  # ~50 Protokollzeilen + alle Problemfits

            def fortschritt(i, total, erg):
                zeige = (i == 0) or (i + 1 == total) or ((i + 1) % schritt == 0) or erg.problematisch
                if zeige and erg.problematisch:
                    text = f"  {i+1}/{total}  f={erg.frequenz/1e9:6.2f} GHz  ⚠ {erg.problem_text}"
                elif zeige:
                    text = (f"  {i+1}/{total}  f={erg.frequenz/1e9:6.2f} GHz  "
                            f"✓ B_res={erg.B_res:.3f} T, α={erg.alpha:.1e}")
                else:
                    text = ""
                melde(i + 1, total, text)

            return fitte_alle(datensatz, fortschritt=fortschritt)

        def bei_fertig(stapel):
            self.stapel = stapel
            self._aktualisiere_overlay()
            self.aktueller_index = 0
            self._zeige_aktuellen()
            n_prob = len(stapel.index_problematisch())
            art = "ok" if n_prob == 0 else "warn"
            self._log(f"Auto-Fit fertig: {len(stapel.ergebnisse)} Fits, {n_prob} problematisch.", art)
            for grund, anzahl in stapel.problem_statistik().items():
                self._log(f"   • {grund}: {anzahl}", "warn")
            self.statusBar().showMessage(
                f"Auto-Fit fertig. {len(stapel.ergebnisse)} Fits, {n_prob} problematisch.")

        self._starte_job(aufgabe, bei_fertig, "Auto-Fit läuft …")

    def _aktualisiere_overlay(self):
        bres = np.array([e.B_res for e in self.stapel.ergebnisse])
        problem = np.array([e.problematisch for e in self.stapel.ergebnisse], dtype=bool)
        self.matrix.aktualisiere_resonanz(self.stapel.datensatz.frequenzen, bres, problem)

    def _zeige_aktuellen(self):
        if not self.stapel or not self.stapel.ergebnisse:
            return
        i = self.aktueller_index
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
            self._log("Keine problematischen Fits mehr.", "ok")
            return
        self.aktueller_index = ziel
        self._zeige_aktuellen()

    def _grenzen_geaendert(self, unten: float, oben: float):
        """Callback aus dem Linescan-Panel: neue Bandgrenzen -> sofort neu fitten."""
        if not self.stapel or not self.stapel.ergebnisse:
            return
        i = self.aktueller_index
        erg = fitte_neu(self.stapel, i, feld_unten=unten, feld_oben=oben)
        self._zeige_aktuellen()
        self._aktualisiere_overlay()
        art = "problem" if erg.problematisch else "ok"
        self._log(f"Neu gefittet f={erg.frequenz/1e9:.2f} GHz "
                  f"[{unten:.3f}–{oben:.3f} T] → {'⚠ ' + erg.problem_text if erg.problematisch else '✓ OK'}",
                  art)

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
            self._log(f"Kittel/LLG fehlgeschlagen: {exc}", "problem")
            return
        kit, llg = info["kittel"], info["llg"]
        self._log(
            f"Kittel {geo}: µ0Meff={kit['mu0Meff']:.4f} T, g={kit['g_faktor']:.3f}; "
            f"LLG: α={llg['alpha']:.3e}, µ0Hinh={llg['mu0Hinh']*1e3:.2f} mT.", "ok")
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
        self._log(f"TDMS gespeichert: {os.path.basename(pfad)}", "ok")

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
        self._log(f"Excel gespeichert: {os.path.basename(pfad)}", "ok")

    def _export_csv(self):
        if not self._fits_vorhanden():
            return
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, "CSV speichern", "", "CSV (*.csv)")
        if not pfad:
            return
        exportiere_csv(self.stapel.ergebnisse, pfad)
        self.statusBar().showMessage(f"CSV gespeichert: {pfad}")
        self._log(f"CSV gespeichert: {os.path.basename(pfad)}", "ok")

    def _fits_vorhanden(self) -> bool:
        if not self.stapel or not self.stapel.ergebnisse:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst fitten.")
            return False
        return True

    def _vollbereich_umschalten(self, an: bool):
        """Ganzen Feldsweep statt Zoom aufs Band zeigen (und aktuelle Anzeige erneuern)."""
        self.fitansicht.setze_vollbereich(an)
        self._zeige_aktuellen()

    def _problemfits_umschalten(self, an: bool):
        """Problematische Fits im Resonanz-Overlay der Übersicht aus-/einblenden."""
        self.matrix.setze_problemfits_ausblenden(an)

    def _auf_zoom(self, xlim, ylim, ist_gezoomt: bool):
        """Vom Matrix-Zoom aufgerufen: Navigator zeigen/aktualisieren bzw. ausblenden."""
        if ist_gezoomt:
            self.navigator.setze_ausschnitt(xlim, ylim)
            if not self.navigator_dock.isVisible():
                self.navigator_dock.setVisible(True)
        else:
            self.navigator_dock.setVisible(False)

    def _navigator_bereich(self, xlim, ylim):
        """Klick/Ziehen im Navigator -> sichtbaren Ausschnitt der Übersicht verschieben."""
        self.matrix.setze_ansicht(xlim, ylim)

    def _zeige_hilfe(self):
        """Oeffnet den Hilfe-Dialog (modal)."""
        self._baue_hilfe_dialog().exec()

    def _baue_hilfe_dialog(self) -> QtWidgets.QDialog:
        """Hilfe-Dialog: Bedienung, Physik-Kurzfassung, WMI-Bezug und Repository-Link."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Ananas – Hilfe & Infos")
        dlg.setWindowIcon(app_icon())
        dlg.resize(660, 580)
        lay = QtWidgets.QVBoxLayout(dlg)

        kopf = QtWidgets.QHBoxLayout()
        logo = QtWidgets.QLabel()
        logo.setPixmap(app_icon().pixmap(56, 56))
        kopf.addWidget(logo)
        titel = QtWidgets.QLabel(
            "<b style='font-size:16px'>Ananas</b><br>"
            "Breitband-FMR-Auswertung · Walther-Meißner-Institut")
        titel.setTextFormat(QtCore.Qt.RichText)
        kopf.addWidget(titel, 1)
        lay.addLayout(kopf)

        browser = QtWidgets.QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(self._hilfe_html())
        lay.addWidget(browser, 1)

        knoepfe = QtWidgets.QDialogButtonBox()
        b_repo = knoepfe.addButton("Repository öffnen", QtWidgets.QDialogButtonBox.ActionRole)
        b_repo.clicked.connect(
            lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(REPO_URL)))
        b_zu = knoepfe.addButton("Schließen", QtWidgets.QDialogButtonBox.AcceptRole)
        b_zu.clicked.connect(dlg.accept)
        lay.addWidget(knoepfe)
        return dlg

    @staticmethod
    def _hilfe_html() -> str:
        return f"""
        <html><body style="font-size:12px; line-height:1.45">
        <p><b>Ananas</b> wertet Breitband-Ferromagnetische-Resonanz-Messungen (bbFMR) aus:
        TDMS einlesen, je Frequenz an die <b>Polder-Suszeptibilität</b> fitten und
        übergreifend Kittel-/LLG-Parameter (µ₀M<sub>eff</sub>, g, α, µ₀H<sub>inh</sub>) bestimmen.</p>

        <h3>Arbeitsablauf</h3>
        <ol>
          <li><b>TDMS laden</b> – sortiertes oder unsortiertes Format wird erkannt.</li>
          <li><b>Auto-Fit (alle)</b> – sucht je Frequenz die Resonanz, schneidet ein Band
              und fittet Re &amp; Im gleichzeitig. Läuft im Hintergrund; Fortschritt und
              Live-Protokoll im <b>Aktivitäts-Panel</b> (rechts).</li>
          <li><b>Nachfitten</b> – im rechten Panel die <b>grünen Grenzlinien</b> ziehen
              (Band wird automatisch herangezoomt; „Vollbereich" zeigt den ganzen Sweep).
              <i>Zurück/Weiter/Nochmal fitten/Nächster Problemfit</i> steuern den Korrekturlauf.</li>
          <li><b>Kittel/LLG-Auswertung</b> – Resonanz vs. f (+Kittel), Linienbreite vs. f
              (LLG → α, H<sub>inh</sub>) und Resonanz vs. T.</li>
          <li><b>Export</b> – zugeschnittene Rohdaten + Fitkurven als TDMS, Parameter als Excel/CSV.</li>
        </ol>

        <h3>Übersicht (links) – Navigation &amp; Zoom</h3>
        <ul>
          <li><b>Klicken</b>: Frequenz wählen → der zugehörige Fit wird sofort geladen.</li>
          <li><b>Kästchen ziehen</b>: auf den markierten Bereich zoomen.</li>
          <li><b>Mausrad</b>: rein/raus zoomen · <b>Doppelklick</b>: Zoom zurücksetzen.</li>
          <li><b>Umschalt+Mausrad</b> oder <b>↑/↓</b> (Pos1/Ende, Bild↑/↓): Frequenz wechseln.</li>
          <li>Beim Zoomen erscheint links der <b>Navigator</b> – er zeigt, wo man sich in der
              Gesamtmessung befindet (Klick im Navigator verschiebt den Ausschnitt).</li>
          <li><b>„Problemfits ausblenden"</b>: blendet als problematisch markierte Fits im
              Resonanz-Overlay aus.</li>
        </ul>

        <h3>Physik (Kurzfassung)</h3>
        <p>Gefittet wird das komplexe S21 mit der Polder-Suszeptibilität (oop). Aus B<sub>res</sub>(f)
        folgt über die Kittel-Gleichung µ₀M<sub>eff</sub> und der g-Faktor, aus der Linienbreite
        µ₀ΔH(f) über das LLG-Modell die Gilbert-Dämpfung α und die inhomogene Verbreiterung
        µ₀H<sub>inh</sub>.</p>

        <hr>
        <p>Entstanden am <b>Walther-Meißner-Institut</b> (das Logo verbindet die Ananas mit dem
        WMI-Signet). Quellcode, Doku und Details:<br>
        <a href="{REPO_URL}">{REPO_URL}</a></p>
        </body></html>
        """

    def _frequenz_gewaehlt(self, index: int):
        if not self.stapel or not self.stapel.ergebnisse:
            return
        self.aktueller_index = index
        self._zeige_aktuellen()


def starte_gui(argv=None):
    """Startet die Qt-Anwendung."""
    import sys

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(argv or sys.argv)
    app.setApplicationName("Ananas")
    app.setWindowIcon(app_icon())
    app.setStyleSheet(ANANAS_QSS)
    fenster = Hauptfenster()
    fenster.show()
    return app.exec()

"""Hauptfenster der bbFMR-GUI.

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

from ..io import (
    EINGEBAUTE_PROFILE,
    finde_profil,
    inspiziere_tdms,
    lade_profile,
    lade_tdms,
    pruefe_datensatz,
    schreibe_ergebnis_tdms,
)
from ..fit.batch import Ausschlusszone, StapelErgebnis, fitte_alle, fitte_neu
from ..fit.fenster_steuerung import (
    dispersions_zentren,
    entferne_ausschlusszone,
    fitte_bereich,
    fuege_ausschlusszone_hinzu,
    propagiere_grenzen,
    setze_fensterbreite_punkte,
)
from ..persistenz.ergebnis_export import exportiere_excel, exportiere_csv
from ..persistenz.projekt import lade_sitzung, speichere_sitzung, stelle_stapel_wieder_her
from ..auswertung.uebersicht import auswertung_kittel_llg
from ..fit.auswahl import Auswertungsauswahl
from .ausreisser_panel import AusreisserPanel
from .auswahl_dialog import AuswahlDialog
from .fenster_panel import FensterPanel
from .matrix_ansicht import MatrixAnsicht
from .fit_ansicht import FitAnsicht
from .mapping_dialog import MappingDialog, VorschauDialog
from .navigator_ansicht import NavigatorAnsicht
from .verarbeitung_panel import VerarbeitungPanel
from .arbeiter import Arbeiter
from .stil import bbFMR_QSS

#: Pfad zum bbFMR-App-Icon (SVG, skaliert verlustfrei).
ICON_PFAD = str(Path(__file__).resolve().parent / "assets" / "bbfmr.svg")

#: Quellcode-Repository (im Hilfe-Dialog verlinkt).
REPO_URL = "https://github.com/ibrahimyalcinsoy/bbFMR"

#: Farben fuer das Aktivitaetsprotokoll je Meldungsart.
_LOG_FARBEN = {
    "info": "#5A5648", "ok": "#2E7D38", "warn": "#B8860B",
    "problem": "#C0392B", "auto": "#6B6657",
}


def app_icon() -> QtGui.QIcon:
    """Liefert das bbFMR-App-Icon (leeres QIcon, falls die Datei fehlt)."""
    return QtGui.QIcon(ICON_PFAD)


class Hauptfenster(QtWidgets.QMainWindow):
    """Zentrales Anwendungsfenster."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("bbFMR – Breitband-FMR-Auswertung")
        self.setWindowIcon(app_icon())
        self.resize(1400, 860)

        self.stapel: StapelErgebnis | None = None
        self.aktueller_index: int = 0
        # Voller geladener Datensatz. Der Stapel kann (Jumper/Bereich) auf einem
        # REDUZIERTEN Datensatz arbeiten - neue Auswertungen starten immer hier.
        self.datensatz_voll = None
        # Zuletzt benutzte Auswertungsauswahl (Jumper/Bereich) als Vorbelegung.
        self._letzte_auswahl: Auswertungsauswahl | None = None

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
        self.verarbeitung = VerarbeitungPanel(geaendert=self._verarbeitung_geaendert)
        self.fensterpanel = FensterPanel(
            grenzen_umschalten=self._grenzen_umschalten,
            breite_anwenden=self._breite_anwenden,
            propagieren=self._propagieren,
            zone_zeichnen=self._zone_zeichnen,
            zone_entfernen=self._zone_entfernen,
        )
        self.ausreisserpanel = AusreisserPanel(
            wieder_aufnehmen=self._ausreisser_wieder_aufnehmen,
            rueckgaengig=self._ausreisser_rueckgaengig,
        )
        #: Undo-Stapel der Ausreisser-Listen (Snapshot VOR jeder Aenderung).
        self._ausreisser_undo: list[list[int]] = []

        self._baue_oberflaeche()
        self._baue_werkzeugleiste()
        self._baue_aktivitaet_dock()
        self._baue_navigator_dock()
        self._baue_verarbeitung_dock()
        self._baue_fenster_dock()
        self._baue_ausreisser_dock()
        self.statusBar().showMessage("Bereit. Bitte eine TDMS-Datei laden.")
        self._log("bbFMR bereit. Bitte eine TDMS-Datei laden.", "info")

    # --- Aufbau ------------------------------------------------------------
    def _baue_oberflaeche(self):
        """Farbplot als Zentrum; das Linescan-Fit-Panel ist ein abdockbares
        Fenster (Multi-Monitor-Betrieb: Panel einfach auf den zweiten
        Bildschirm ziehen)."""
        self.setCentralWidget(self.matrix)

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

        dock = QtWidgets.QDockWidget("Linescan-Fit", self)
        dock.setObjectName("linescan_dock")
        dock.setAllowedAreas(
            QtCore.Qt.RightDockWidgetArea | QtCore.Qt.LeftDockWidgetArea
            | QtCore.Qt.BottomDockWidgetArea
        )
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetClosable
        )
        rechts.setMinimumWidth(480)
        dock.setWidget(rechts)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self.linescan_dock = dock

    def _baue_werkzeugleiste(self):
        leiste = self.addToolBar("Hauptaktionen")
        leiste.setMovable(False)

        # Klickbares bbFMR×WMI-Logo + Wortmarke ganz links -> oeffnet die Hilfe.
        self.btn_logo = QtWidgets.QToolButton()
        self.btn_logo.setIcon(app_icon())
        self.btn_logo.setIconSize(QtCore.QSize(26, 26))
        self.btn_logo.setText(" bbFMR")
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
        self.akt_seed = leiste.addAction("Resonanz vorgeben")
        self.akt_seed.setToolTip(
            "Zwei Punkte auf die Resonanz in der Übersicht klicken → die Fit-Fenster "
            "folgen dieser Dispersion (hilft, wenn der Auto-Fit an einem Störfeature hängt).")
        self.akt_seed.triggered.connect(self._resonanz_vorgeben)
        self.akt_bereich = leiste.addAction("Bereich neu fitten")
        self.akt_bereich.setToolTip(
            "Rechteck im Farbplot aufziehen → nur dort werden Fenstersuche und Fit "
            "wiederholt (löst Mehrdeutigkeiten neben der Mode auf). Esc bricht ab.")
        self.akt_bereich.triggered.connect(self._bereich_fitten)
        self.akt_ausreisser = leiste.addAction("Ausreißer markieren")
        self.akt_ausreisser.setCheckable(True)
        self.akt_ausreisser.setToolTip(
            "Modus: Fit-Punkte im Farbplot anklicken oder per Kasten markieren → "
            "raus aus Darstellung und allen Rechnungen (insb. Kittel-Fit). "
            "Rückgängig und Liste im Ausreißer-Panel.")
        self.akt_ausreisser.toggled.connect(self._ausreisser_modus)
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
        leiste.addSeparator()
        self.akt_projekt_speichern = leiste.addAction("Projekt speichern")
        self.akt_projekt_speichern.setToolTip(
            "Sitzung als JSON sichern: Quelle, Kanal-Zuordnung, Auswahl, Fenster, "
            "Ausschlusszonen, Ausreißer und Fitparameter.")
        self.akt_projekt_speichern.triggered.connect(self._projekt_speichern)
        self.akt_projekt_laden = leiste.addAction("Projekt laden")
        self.akt_projekt_laden.setToolTip(
            "Gespeicherte Sitzung fortsetzen: TDMS wird neu gelesen, die Fits werden "
            "mit den gespeicherten Fenstern deterministisch wiederhergestellt.")
        self.akt_projekt_laden.triggered.connect(self._projekt_laden)

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

        # Sichtbarkeits-Umschalter fuer die andockbaren Panels.
        leiste.addSeparator()
        self.akt_verarbeitung = leiste.addAction("Verarbeitung")
        self.akt_verarbeitung.setToolTip(
            "Verarbeitungskette des Farbplots (divide-slice, derivative-divide, "
            "relation-amplitude) ein-/ausblenden.")
        self.akt_fenster = leiste.addAction("Fenster && Grenzen")
        self.akt_fenster.setToolTip(
            "Interaktives In-Plot-Fitting: ziehbare Fenstergrenzen, Propagation, "
            "Fensterbreite in Punkten, Ausschlusszonen.")
        self.akt_linescan = leiste.addAction("Linescan-Fit")
        self.akt_linescan.setToolTip(
            "Linescan-Fit-Panel ein-/ausblenden (abdockbar fuer den zweiten Monitor).")
        self.akt_linescan.setCheckable(True)
        self.akt_linescan.setChecked(True)
        self.akt_linescan.toggled.connect(self.linescan_dock.setVisible)
        self.linescan_dock.visibilityChanged.connect(self.akt_linescan.setChecked)
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

    def _baue_verarbeitung_dock(self):
        """Verarbeitungskette (links): divide-slice, derivative-divide, relation-amplitude."""
        dock = QtWidgets.QDockWidget("Verarbeitung (Farbplot)", self)
        dock.setObjectName("verarbeitung_dock")
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea
        )
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetClosable
        )
        rollbereich = QtWidgets.QScrollArea()
        rollbereich.setWidgetResizable(True)
        rollbereich.setWidget(self.verarbeitung)
        dock.setWidget(rollbereich)
        dock.setMinimumWidth(280)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        self.verarbeitung_dock = dock
        self.akt_verarbeitung.setCheckable(True)
        self.akt_verarbeitung.setChecked(True)
        self.akt_verarbeitung.toggled.connect(dock.setVisible)
        dock.visibilityChanged.connect(self.akt_verarbeitung.setChecked)

    def _baue_fenster_dock(self):
        """Fenster & Grenzen (links): interaktives In-Plot-Fitting."""
        dock = QtWidgets.QDockWidget("Fenster & Grenzen", self)
        dock.setObjectName("fenster_dock")
        dock.setAllowedAreas(
            QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea
        )
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetClosable
        )
        rollbereich = QtWidgets.QScrollArea()
        rollbereich.setWidgetResizable(True)
        rollbereich.setWidget(self.fensterpanel)
        dock.setWidget(rollbereich)
        dock.setMinimumWidth(280)
        # Bewusst NICHT tabifiziert: hinter einem Tab liegende Docks melden
        # visibilityChanged(False), was die Toolbar-Toggles fehlleiten wuerde.
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        self.fenster_dock = dock

    def _baue_ausreisser_dock(self):
        """Ausreisser-Liste (rechts); erscheint mit dem Markier-Modus."""
        dock = QtWidgets.QDockWidget("Ausreißer", self)
        dock.setObjectName("ausreisser_dock")
        dock.setAllowedAreas(
            QtCore.Qt.RightDockWidgetArea | QtCore.Qt.LeftDockWidgetArea
            | QtCore.Qt.BottomDockWidgetArea
        )
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetClosable
        )
        dock.setWidget(self.ausreisserpanel)
        dock.setMinimumWidth(280)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        dock.setVisible(False)  # erscheint mit "Ausreißer markieren"
        self.ausreisser_dock = dock
        self.akt_fenster.setCheckable(True)
        self.akt_fenster.setChecked(True)
        self.akt_fenster.toggled.connect(dock.setVisible)
        dock.visibilityChanged.connect(self.akt_fenster.setChecked)

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
        for aktion in (self.akt_laden, self.akt_fit, self.akt_seed, self.akt_bereich,
                       self.akt_ausreisser, self.akt_kittel, self.akt_tdms,
                       self.akt_xlsx, self.akt_csv,
                       self.akt_projekt_speichern, self.akt_projekt_laden):
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
        self._lade_mit_mapping(pfad)

    def _lade_mit_mapping(self, pfad: str,
                          zuordnung_vorgabe: dict | None = None,
                          layout_vorgabe: str | None = None):
        """Lade-Ablauf: Struktur inspizieren -> Zuordnungs-Dialog -> Laden im
        Hintergrund -> Validierungs-Vorschau -> erst dann Uebernahme.

        ``zuordnung_vorgabe`` haelt beim erneuten Oeffnen (Vorschau verworfen)
        die zuletzt gewaehlte Zuordnung fest.
        """
        # 1) Nur Metadaten lesen: schnell, auch bei defekter Index-Datei.
        try:
            struktur, warnungen = inspiziere_tdms(pfad)
        except Exception as fehler:
            self._log(f"FEHLER beim Inspizieren: {fehler}", "problem")
            QtWidgets.QMessageBox.critical(self, "TDMS laden", str(fehler))
            return
        for warnung in warnungen:
            self._log("⚠ " + warnung, "warn")

        # 2) Zuordnungs-Dialog (Pflicht vor jedem Laden -> kein Fit auf
        #    ungemappten Daten). Passendes Profil wird vorausgewaehlt.
        profile = list(EINGEBAUTE_PROFILE) + lade_profile()
        vorschlag = finde_profil(struktur, profile)
        dialog = MappingDialog(pfad, struktur, profile, vorschlag, parent=self)
        if zuordnung_vorgabe is not None:
            dialog._setze_zuordnung(zuordnung_vorgabe, layout_vorgabe)
        if not dialog.exec():
            self._log("Laden abgebrochen (Zuordnung nicht bestaetigt).", "info")
            return
        zuordnung, layout = dialog.ergebnis()

        # 3) Laden + Validierung im Hintergrund.
        def aufgabe(melde):
            melde(0, 0, f"Lade {os.path.basename(pfad)} …")
            datensatz = lade_tdms(pfad, zuordnung=zuordnung, layout=layout)
            melde(0, 0, f"Pruefe Datensatz ({len(datensatz)} Frequenzen) …")
            bericht = pruefe_datensatz(datensatz)
            return (pfad, datensatz, bericht)

        def bei_fertig(res):
            pfad_, datensatz, bericht = res
            for warnung in datensatz.meta.get("lade_warnungen", []):
                self._log("⚠ " + warnung, "warn")

            # 4) Import-Validierung vor Uebernahme: Bericht + Vorschau.
            vorschau = VorschauDialog(datensatz, bericht, parent=self)
            if not vorschau.exec():
                self._log("Import verworfen – Zuordnung erneut bearbeiten.", "info")
                self._lade_mit_mapping(pfad_, zuordnung, datensatz.format_typ)
                return
            if bericht.warnungen:
                for warnung in bericht.warnungen:
                    self._log("⚠ Validierung: " + warnung, "warn")

            self.matrix.zeige(datensatz)
            feld_achse, freq_achse = self.matrix.achsen()
            self.verarbeitung.setze_achsen(feld_achse, freq_achse)
            self.matrix.setze_verarbeitung(self.verarbeitung.kette(),
                                           self.verarbeitung.anzeige_modus())
            mat, ext = self.matrix.thumbnail()
            self.navigator.zeige(mat, ext)
            self.navigator_dock.setVisible(False)  # erst beim Zoomen einblenden
            self.datensatz_voll = datensatz
            self.stapel = StapelErgebnis(datensatz=datensatz)
            self.fensterpanel.setze_zonen([])
            self.fensterpanel.setze_breite_info(None)
            self.fensterpanel.chk_grenzen.setChecked(False)  # neue Messung, alte Grenzen weg
            self._log(
                f"Geladen: {os.path.basename(pfad_)} – {datensatz.format_typ}, "
                f"{len(datensatz)} Frequenzen (Profil: "
                f"{datensatz.meta.get('mapping_profil', 'manuell')}).", "ok")
            self.statusBar().showMessage(
                f"Geladen: {os.path.basename(pfad_)} ({datensatz.format_typ}, "
                f"{len(datensatz)} Frequenzen). Jetzt 'Auto-Fit' starten.")

        self._starte_job(aufgabe, bei_fertig, f"Lade {os.path.basename(pfad)} …")

    def _mapping_vorhanden(self) -> bool:
        """Kein Fit auf ungemappten Daten: Zuordnung muss in den Metadaten stehen."""
        if self.stapel is not None and self.stapel.datensatz.meta.get("zuordnung"):
            return True
        QtWidgets.QMessageBox.information(
            self, "Hinweis",
            "Der Datensatz hat keine Kanal-Zuordnung. Bitte die TDMS-Datei ueber "
            "'TDMS laden' oeffnen und die Kanaele den Rollen zuordnen.")
        return False

    def _frage_auswahl(self) -> Auswertungsauswahl | None:
        """Zeigt vor der Auswertung den Jumper-/Bereichs-Dialog (Pflichtschritt).

        Liefert die Auswahl oder ``None`` bei Abbruch. Die zuletzt benutzte
        Auswahl ist vorbelegt.
        """
        dialog = AuswahlDialog(self.datensatz_voll, self._letzte_auswahl, parent=self)
        if not dialog.exec():
            return None
        auswahl = dialog.auswahl()
        self._letzte_auswahl = auswahl
        if not auswahl.ist_neutral:
            self._log("Auswertungsauswahl: "
                      + auswahl.beschreibung(self.datensatz_voll), "info")
        return auswahl

    def _auto_fit(self):
        if self.stapel is None or self.datensatz_voll is None:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst eine TDMS-Datei laden.")
            return
        if not self._mapping_vorhanden():
            return
        datensatz = self.datensatz_voll
        auswahl = self._frage_auswahl()
        if auswahl is None:
            return

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

            return fitte_alle(datensatz, fortschritt=fortschritt, auswahl=auswahl)

        def bei_fertig(stapel):
            self.stapel = stapel
            self._ausreisser_undo = []  # Undo-Stapel gehoert zum alten Stapel
            self._aktualisiere_overlay()
            # Neuer Stapel: Ausschlusszonen beginnen leer, Grenzen-Overlay neu.
            self.fensterpanel.setze_zonen(stapel.ausschlusszonen)
            self.matrix.zeige_ausschlusszonen(stapel.ausschlusszonen)
            self._aktualisiere_grenzen_overlay()
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

    def _resonanz_vorgeben(self):
        """Startet den Dispersions-Seed: zwei Klicks auf die Resonanz in der Übersicht."""
        if self.stapel is None:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst eine TDMS-Datei laden.")
            return
        if not self._mapping_vorhanden():
            return
        if self._job_laeuft:
            return
        self._log("Resonanz vorgeben: zwei Punkte auf die Resonanz in der Übersicht klicken "
                  "(tiefe und hohe Frequenz).", "info")
        self.statusBar().showMessage("Resonanz vorgeben: zwei Punkte auf die Resonanz klicken …")
        self.matrix.starte_dispersion_seed(self._seed_fertig)

    def _seed_fertig(self, punkte):
        """Callback nach zwei Klicks: Kittel-Gerade legen und mit Vorgabe neu fitten."""
        (b1, f1_ghz), (b2, f2_ghz) = punkte
        f1, f2 = f1_ghz * 1e9, f2_ghz * 1e9
        if abs(f2 - f1) < 1e6:
            QtWidgets.QMessageBox.warning(
                self, "Hinweis", "Bitte zwei Punkte bei DEUTLICH verschiedenen Frequenzen wählen.")
            self._log("Resonanz vorgeben abgebrochen (Punkte zu nah beieinander).", "warn")
            return
        steigung = (b2 - b1) / (f2 - f1)
        datensatz = self.datensatz_voll if self.datensatz_voll is not None else self.stapel.datensatz
        zentren = b1 + steigung * (datensatz.frequenzen - f1)  # Kittel-Gerade B_res(f)
        auswahl = self._frage_auswahl()
        if auswahl is None:
            self._log("Auto-Fit mit Vorgabe abgebrochen (keine Auswertungsauswahl).", "info")
            return
        self._log(f"Dispersion gesetzt: {b1:.3f} T @ {f1/1e9:.1f} GHz – "
                  f"{b2:.3f} T @ {f2/1e9:.1f} GHz → Auto-Fit mit Vorgabe …", "ok")

        def aufgabe(melde):
            n = len(datensatz.linescans)
            schritt = max(1, n // 50)

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

            return fitte_alle(datensatz, fortschritt=fortschritt, zentren=zentren,
                              auswahl=auswahl)

        def bei_fertig(stapel):
            self.stapel = stapel
            self._ausreisser_undo = []
            self._aktualisiere_overlay()
            self.fensterpanel.setze_zonen(stapel.ausschlusszonen)
            self.matrix.zeige_ausschlusszonen(stapel.ausschlusszonen)
            self._aktualisiere_grenzen_overlay()
            self.aktueller_index = 0
            self._zeige_aktuellen()
            n_prob = len(stapel.index_problematisch())
            self._log(f"Auto-Fit (mit Vorgabe) fertig: {len(stapel.ergebnisse)} Fits, "
                      f"{n_prob} problematisch.", "ok" if n_prob <= len(stapel.ergebnisse) // 3 else "warn")
            self.statusBar().showMessage(
                f"Auto-Fit (mit vorgegebener Dispersion) fertig. {n_prob} problematisch.")

        self._starte_job(aufgabe, bei_fertig, "Auto-Fit mit vorgegebener Dispersion …")

    def _bereich_fitten(self):
        """Startet den Bereichs-Fit: Rechteck im Farbplot aufziehen -> dort neu fitten."""
        if not self.stapel or not self.stapel.ergebnisse:
            QtWidgets.QMessageBox.information(
                self, "Hinweis", "Bitte zuerst einen Auto-Fit ausfuehren - der "
                "Bereichs-Fit ueberschreibt gezielt bestehende Fits.")
            return
        if self._job_laeuft:
            return
        self._log("Bereich neu fitten: Rechteck um die Mode aufziehen "
                  "(Esc bricht ab).", "info")
        self.statusBar().showMessage("Bereich neu fitten: Rechteck im Farbplot aufziehen …")
        self.matrix.starte_bereichs_fit(self._bereich_gewaehlt)

    def _bereich_gewaehlt(self, feld_min, feld_max, f_min_ghz, f_max_ghz):
        """Callback nach dem Aufziehen: nur im Rechteck neu fitten (Hintergrund)."""
        stapel = self.stapel
        f_min, f_max = f_min_ghz * 1e9, f_max_ghz * 1e9

        def aufgabe(melde):
            def fortschritt(k, n, erg):
                status = "⚠ " + erg.problem_text if erg.problematisch else \
                    f"✓ B_res={erg.B_res:.3f} T"
                melde(k, n, f"  {k}/{n}  f={erg.frequenz/1e9:6.2f} GHz  {status}")
            return fitte_bereich(stapel, feld_min, feld_max, f_min, f_max,
                                 modus=self.fensterpanel.modus(),
                                 fortschritt=fortschritt)

        def bei_fertig(res):
            neu, uebersprungen = res
            self._aktualisiere_overlay()
            self._aktualisiere_grenzen_overlay()
            self._zeige_aktuellen()
            probleme = [i for i in neu if stapel.ergebnisse[i].problematisch]
            text = (f"Bereichs-Fit [{feld_min:.3f}-{feld_max:.3f} T, "
                    f"{f_min_ghz:.2f}-{f_max_ghz:.2f} GHz]: {len(neu)} neu gefittet, "
                    f"{len(probleme)} problematisch, "
                    f"{len(uebersprungen)} uebersprungen (ohne Daten/Modus 'ergaenzen').")
            self._log(text, "warn" if probleme else "ok")
            self.statusBar().showMessage(text)

        self._starte_job(aufgabe, bei_fertig,
                         f"Bereichs-Fit {f_min_ghz:.1f}-{f_max_ghz:.1f} GHz …")

    def _aktualisiere_overlay(self):
        bres = np.array([e.B_res for e in self.stapel.ergebnisse])
        problem = np.array([e.problematisch for e in self.stapel.ergebnisse], dtype=bool)
        ausgeschlossen = np.zeros(len(self.stapel.ergebnisse), dtype=bool)
        gueltige = [i for i in self.stapel.ausreisser if i < ausgeschlossen.size]
        ausgeschlossen[gueltige] = True
        self.matrix.aktualisiere_resonanz(self.stapel.datensatz.frequenzen, bres,
                                          problem, ausgeschlossen)
        self.ausreisserpanel.zeige_ausreisser(self.stapel)

    def _zeige_aktuellen(self):
        if not self.stapel or not self.stapel.ergebnisse:
            return
        i = self.aktueller_index
        # Volldaten fuer die Anzeige (nicht beschnitten), Grenzen separat.
        voll = self.stapel.datensatz.linescans[i]
        unten, oben = self.stapel.fenster[i]
        self.fitansicht.zeige(voll, unten, oben, self.stapel.ergebnisse[i])
        # Wertbasiert markieren: der Stapel kann (Jumper) weniger Frequenzen
        # enthalten als die angezeigte Matrix.
        self.matrix.markiere_frequenz_wert(self.stapel.ergebnisse[i].frequenz)
        # Fenster-Panel: tatsaechliche Fensterbreite in Punkten anzeigen.
        punkte_im_fenster = int(np.count_nonzero((voll.feld >= unten) & (voll.feld <= oben)))
        self.fensterpanel.setze_breite_info(punkte_im_fenster, unten, oben)
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
        self._aktualisiere_grenzen_overlay()
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
        # Ausreisser fliegen aus ALLEN uebergreifenden Rechnungen und Plots.
        aktive = self.stapel.ergebnisse_aktiv()
        n_ausreisser = len(self.stapel.ausreisser)
        if n_ausreisser:
            self._log(f"Kittel/LLG: {n_ausreisser} Ausreißer ausgeschlossen "
                      f"({len(aktive)} Punkte verbleiben).", "info")
        try:
            info = auswertung_kittel_llg(aktive, geometrie=geo)
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
        plot_resonanz_vs_frequenz(aktive, geometrie=geo)
        plot_linienbreite(aktive, gamma=info["kittel"]["gamma"])
        plot_resonanz_vs_temperatur(aktive)
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
            info = auswertung_kittel_llg(self.stapel.ergebnisse_aktiv())
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

    # --- Interaktives In-Plot-Fitting (Fenster & Grenzen) --------------------
    def _aktualisiere_grenzen_overlay(self):
        """Zeichnet die ziehbaren Fenstergrenzen im Farbplot neu (falls aktiv)."""
        if not self.stapel or not self.stapel.fenster:
            return
        if self.fensterpanel.grenzen_aktiv():
            self.matrix.zeige_fenstergrenzen(
                self.stapel.datensatz.frequenzen, self.stapel.fenster,
                grenze_gezogen=self._grenze_im_plot_gezogen)

    def _grenzen_umschalten(self, an: bool):
        if not an:
            self.matrix.verstecke_fenstergrenzen()
            return
        if not self.stapel or not self.stapel.fenster:
            self._log("Grenzen anzeigen: erst nach einem Auto-Fit verfuegbar.", "warn")
            self.fensterpanel.chk_grenzen.setChecked(False)
            return
        self._aktualisiere_grenzen_overlay()
        self._log("Fenstergrenzen eingeblendet - Grenze anfassen und horizontal "
                  "ziehen; der Linescan fittet sofort neu.", "info")

    def _grenze_im_plot_gezogen(self, index: int, seite: str, wert: float):
        """Eine Grenze wurde im Farbplot losgelassen: diesen Linescan neu fitten."""
        if not self.stapel or not self.stapel.ergebnisse or self._job_laeuft:
            self._aktualisiere_grenzen_overlay()
            return
        unten, oben = self.stapel.fenster[index]
        if seite == "links":
            unten = wert
        else:
            oben = wert
        if oben <= unten:
            self._log("Grenze verworfen: linke Grenze muss links der rechten bleiben.", "warn")
            self._aktualisiere_grenzen_overlay()
            return
        ergebnis = fitte_neu(self.stapel, index, feld_unten=unten, feld_oben=oben)
        self.aktueller_index = index
        self._zeige_aktuellen()
        self._aktualisiere_overlay()
        self._aktualisiere_grenzen_overlay()
        art = "problem" if ergebnis.problematisch else "ok"
        self._log(f"Grenze ({seite}) gezogen: f={ergebnis.frequenz/1e9:.2f} GHz → "
                  f"[{unten:.3f}–{oben:.3f} T] "
                  f"{'⚠ ' + ergebnis.problem_text if ergebnis.problematisch else '✓'}", art)
        if self.fensterpanel.auto_propagieren():
            self._propagieren(self.fensterpanel.modus(), ab_index=index)

    def _propagieren(self, modus: str, ab_index: int | None = None):
        """Grenzen des aktuellen Linescans (als Trassen-Offsets) auf folgende anwenden."""
        if not self.stapel or not self.stapel.ergebnisse:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst fitten.")
            return
        if self._job_laeuft:
            return
        stapel = self.stapel
        basis = self.aktueller_index if ab_index is None else ab_index
        try:
            zentren = dispersions_zentren(stapel)
        except ValueError as fehler:
            self._log(f"Propagation nicht moeglich: {fehler}", "warn")
            return
        unten, oben = stapel.fenster[basis]
        offset_links = unten - float(zentren[basis])
        offset_rechts = oben - float(zentren[basis])
        if offset_rechts <= offset_links:
            self._log("Propagation verworfen: ungueltige Fenster-Offsets.", "warn")
            return
        f_basis = stapel.datensatz.frequenzen[basis] / 1e9

        def aufgabe(melde):
            def fortschritt(k, n, erg):
                melde(k, n, "" if not erg.problematisch else
                      f"  f={erg.frequenz/1e9:6.2f} GHz  ⚠ {erg.problem_text}")
            return propagiere_grenzen(stapel, basis + 1, offset_links, offset_rechts,
                                      zentren=zentren, modus=modus, fortschritt=fortschritt)

        def bei_fertig(neu):
            self._aktualisiere_overlay()
            self._aktualisiere_grenzen_overlay()
            self._zeige_aktuellen()
            self._log(f"Grenzen ab f={f_basis:.2f} GHz propagiert "
                      f"(Offsets {offset_links:+.3f}/{offset_rechts:+.3f} T zur Trasse): "
                      f"{len(neu)} Linescans neu gefittet ({modus}).", "ok")

        self._starte_job(aufgabe, bei_fertig, "Grenzen propagieren …")

    def _breite_anwenden(self, punkte: int, modus: str):
        """Fensterbreite in Punkten explizit auf alle Linescans anwenden."""
        if not self.stapel or not self.stapel.ergebnisse:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst fitten.")
            return
        if self._job_laeuft:
            return
        stapel = self.stapel
        try:
            zentren = dispersions_zentren(stapel)
        except ValueError as fehler:
            self._log(f"Fensterbreite nicht anwendbar: {fehler}", "warn")
            return

        def aufgabe(melde):
            def fortschritt(k, n, erg):
                melde(k, n, "" if not erg.problematisch else
                      f"  f={erg.frequenz/1e9:6.2f} GHz  ⚠ {erg.problem_text}")
            return setze_fensterbreite_punkte(stapel, punkte, zentren=zentren,
                                              modus=modus, fortschritt=fortschritt)

        def bei_fertig(neu):
            self._aktualisiere_overlay()
            self._aktualisiere_grenzen_overlay()
            self._zeige_aktuellen()
            self._log(f"Fensterbreite {punkte} Punkte angewandt: "
                      f"{len(neu)} Linescans neu gefittet ({modus}).", "ok")

        self._starte_job(aufgabe, bei_fertig, f"Fensterbreite {punkte} Punkte …")

    def _zone_zeichnen(self):
        """Startet das Einzeichnen einer Ausschlusszone im Farbplot."""
        if not self.stapel or not self.stapel.ergebnisse:
            QtWidgets.QMessageBox.information(
                self, "Hinweis", "Bitte zuerst einen Auto-Fit ausfuehren.")
            return
        if self._job_laeuft:
            return
        self._log("Ausschlusszone: Rechteck um die auszuschliessenden Punkte "
                  "aufziehen (Esc bricht ab).", "info")
        self.statusBar().showMessage("Ausschlusszone im Farbplot aufziehen …")
        self.matrix.starte_ausschluss_zeichnen(self._zone_gezeichnet)

    def _zone_gezeichnet(self, feld_min, feld_max, f_min_ghz, f_max_ghz):
        stapel = self.stapel
        zone = Ausschlusszone(feld_min, feld_max, f_min_ghz * 1e9, f_max_ghz * 1e9)

        def aufgabe(melde):
            def fortschritt(k, n, erg):
                melde(k, n, "")
            return fuege_ausschlusszone_hinzu(stapel, zone, fortschritt=fortschritt)

        def bei_fertig(betroffen):
            self.fensterpanel.setze_zonen(stapel.ausschlusszonen)
            self.matrix.zeige_ausschlusszonen(stapel.ausschlusszonen)
            self._aktualisiere_overlay()
            self._aktualisiere_grenzen_overlay()
            self._zeige_aktuellen()
            self._log(f"Ausschlusszone [{feld_min:.3f}–{feld_max:.3f} T, "
                      f"{f_min_ghz:.2f}–{f_max_ghz:.2f} GHz] aktiv: "
                      f"{len(betroffen)} Linescans neu gefittet.", "ok")

        self._starte_job(aufgabe, bei_fertig, "Ausschlusszone anwenden …")

    def _zone_entfernen(self, zonen_index: int):
        if not self.stapel or zonen_index >= len(self.stapel.ausschlusszonen):
            return
        if self._job_laeuft:
            return
        stapel = self.stapel

        def aufgabe(melde):
            return entferne_ausschlusszone(stapel, zonen_index,
                                           fortschritt=lambda k, n, e: melde(k, n, ""))

        def bei_fertig(betroffen):
            self.fensterpanel.setze_zonen(stapel.ausschlusszonen)
            self.matrix.zeige_ausschlusszonen(stapel.ausschlusszonen)
            self._aktualisiere_overlay()
            self._aktualisiere_grenzen_overlay()
            self._zeige_aktuellen()
            self._log(f"Ausschlusszone entfernt: {len(betroffen)} Linescans neu gefittet.", "ok")

        self._starte_job(aufgabe, bei_fertig, "Ausschlusszone entfernen …")

    # --- Ausreisser-Management (Bereich 6) -----------------------------------
    def _ausreisser_modus(self, an: bool):
        """Toolbar-Umschalter: Punkte anklicken/einrahmen -> Ausreisser."""
        if an and (not self.stapel or not self.stapel.ergebnisse):
            self._log("Ausreißer markieren: erst nach einem Auto-Fit moeglich.", "warn")
            self.akt_ausreisser.setChecked(False)
            return
        self.matrix.setze_ausreisser_modus(an, gewaehlt=self._ausreisser_gewaehlt)
        if an:
            self.ausreisser_dock.setVisible(True)
            self._log("Ausreißer markieren aktiv: Punkt anklicken oder Kasten "
                      "aufziehen. Erneut klicken auf den Toolbar-Knopf beendet.", "info")
        else:
            self.statusBar().showMessage("Ausreißer-Modus beendet.")

    def _ausreisser_snapshot(self):
        """Zustand VOR einer Aenderung fuer Undo sichern (begrenzte Tiefe)."""
        self._ausreisser_undo.append(list(self.stapel.ausreisser))
        del self._ausreisser_undo[:-50]

    def _ausreisser_gewaehlt(self, indizes: list[int]):
        """Callback aus dem Farbplot: markierte Punkte ausschliessen (Echtzeit)."""
        if not self.stapel or not indizes:
            return
        self._ausreisser_snapshot()
        for i in indizes:
            if not self.stapel.ist_ausreisser(i):
                self.stapel.ausreisser_umschalten(i)
        self._aktualisiere_overlay()
        frequenzen = [self.stapel.ergebnisse[i].frequenz / 1e9 for i in indizes]
        self._log(f"Ausreißer markiert: {len(indizes)} Punkt(e) "
                  f"({', '.join(f'{f:.2f}' for f in frequenzen[:6])}"
                  f"{' …' if len(frequenzen) > 6 else ''} GHz) – "
                  f"insgesamt {len(self.stapel.ausreisser)} ausgeschlossen.", "ok")

    def _ausreisser_wieder_aufnehmen(self, indizes: list[int]):
        """Aus der Liste: Punkte wieder in Darstellung und Rechnungen aufnehmen."""
        if not self.stapel or not indizes:
            return
        self._ausreisser_snapshot()
        for i in indizes:
            if self.stapel.ist_ausreisser(i):
                self.stapel.ausreisser_umschalten(i)
        self._aktualisiere_overlay()
        self._log(f"{len(indizes)} Ausreißer wieder aufgenommen – "
                  f"verbleibend {len(self.stapel.ausreisser)}.", "ok")

    def _ausreisser_rueckgaengig(self):
        if not self.stapel or not self._ausreisser_undo:
            self._log("Ausreißer: nichts rueckgaengig zu machen.", "info")
            return
        self.stapel.ausreisser = self._ausreisser_undo.pop()
        self._aktualisiere_overlay()
        self._log(f"Ausreißer: letzter Schritt rueckgaengig – "
                  f"aktuell {len(self.stapel.ausreisser)} ausgeschlossen.", "ok")

    # --- Projekt speichern / laden -------------------------------------------
    def _projekt_speichern(self):
        if not self.stapel or not self.stapel.ergebnisse:
            QtWidgets.QMessageBox.information(
                self, "Hinweis", "Bitte zuerst fitten – gespeichert wird der "
                "komplette Auswertungszustand.")
            return
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Projekt speichern", "", "bbFMR-Projekt (*.json)")
        if not pfad:
            return
        speichere_sitzung(self.stapel, pfad)
        self._log(f"Projekt gespeichert: {os.path.basename(pfad)} "
                  f"({len(self.stapel.ergebnisse)} Fits, "
                  f"{len(self.stapel.ausreisser)} Ausreißer, "
                  f"{len(self.stapel.ausschlusszonen)} Zonen).", "ok")

    def _projekt_laden(self):
        if self._job_laeuft:
            return
        pfad, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Projekt laden", "", "bbFMR-Projekt (*.json)")
        if not pfad:
            return
        try:
            daten = lade_sitzung(pfad)
        except Exception as fehler:
            QtWidgets.QMessageBox.critical(self, "Projekt laden", str(fehler))
            return

        quelle = daten.get("quelle", "")
        if not Path(quelle).exists():
            QtWidgets.QMessageBox.information(
                self, "Projekt laden",
                f"Die TDMS-Quelle {quelle!r} wurde nicht gefunden. "
                "Bitte die Messdatei auswaehlen.")
            quelle, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "TDMS-Quelle des Projekts", "", "TDMS (*.tdms)")
            if not quelle:
                return

        zuordnung = daten.get("zuordnung")
        if zuordnung is not None:
            zuordnung = {rolle: tuple(paar) for rolle, paar in zuordnung.items()}
        auswahl_dict = daten.get("auswertungsauswahl")

        def aufgabe(melde):
            melde(0, 0, f"Lade {os.path.basename(quelle)} …")
            if zuordnung is not None:
                voll = lade_tdms(quelle, zuordnung=zuordnung,
                                 layout=daten.get("format_typ"))
            else:
                voll = lade_tdms(quelle)  # Projektdatei Version 1: Auto-Profil
            reduziert = voll
            if auswahl_dict:
                auswahl = Auswertungsauswahl.aus_dict(auswahl_dict)
                reduziert, _indizes = auswahl.reduziere(voll)
            melde(0, 0, "Stelle Fits mit gespeicherten Fenstern wieder her …")
            stapel = stelle_stapel_wieder_her(
                daten, reduziert,
                fortschritt=lambda k, n, e: melde(k, n, ""))
            return (voll, stapel)

        def bei_fertig(res):
            voll, stapel = res
            self.datensatz_voll = voll
            self.stapel = stapel
            self._ausreisser_undo = []
            if auswahl_dict:
                self._letzte_auswahl = Auswertungsauswahl.aus_dict(auswahl_dict)
            self.matrix.zeige(voll)
            feld_achse, freq_achse = self.matrix.achsen()
            self.verarbeitung.setze_achsen(feld_achse, freq_achse)
            self.matrix.setze_verarbeitung(self.verarbeitung.kette(),
                                           self.verarbeitung.anzeige_modus())
            mat, ext = self.matrix.thumbnail()
            self.navigator.zeige(mat, ext)
            self.navigator_dock.setVisible(False)
            self._aktualisiere_overlay()
            self.fensterpanel.setze_zonen(stapel.ausschlusszonen)
            self.matrix.zeige_ausschlusszonen(stapel.ausschlusszonen)
            self._aktualisiere_grenzen_overlay()
            self.aktueller_index = 0
            self._zeige_aktuellen()
            self._log(f"Projekt geladen: {os.path.basename(pfad)} – "
                      f"{len(stapel.ergebnisse)} Fits wiederhergestellt, "
                      f"{len(stapel.ausreisser)} Ausreißer, "
                      f"{len(stapel.ausschlusszonen)} Zonen.", "ok")
            self.statusBar().showMessage(
                f"Projekt geladen ({len(stapel.ergebnisse)} Fits).")

        self._starte_job(aufgabe, bei_fertig, f"Lade Projekt {os.path.basename(pfad)} …")

    def _verarbeitung_geaendert(self, kette, anzeige_modus: str):
        """Callback des Verarbeitungspanels: Kette neu auf den Farbplot anwenden."""
        if self.stapel is None:
            return
        try:
            self.matrix.setze_verarbeitung(kette, anzeige_modus)
        except ValueError as fehler:
            # Unzulaessige Parameter (z. B. Δn groesser als halbes Gitter) nur
            # melden – der Plot behaelt den letzten gueltigen Zustand.
            self._log(f"Verarbeitung nicht anwendbar: {fehler}", "warn")
            return
        mat, ext = self.matrix.thumbnail()
        self.navigator.zeige(mat, ext)
        self._log(f"Verarbeitung: {kette.beschreibung()} · Anzeige {anzeige_modus}", "auto")

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
        dlg.setWindowTitle("bbFMR – Hilfe & Infos")
        dlg.setWindowIcon(app_icon())
        dlg.resize(660, 580)
        lay = QtWidgets.QVBoxLayout(dlg)

        kopf = QtWidgets.QHBoxLayout()
        logo = QtWidgets.QLabel()
        logo.setPixmap(app_icon().pixmap(56, 56))
        kopf.addWidget(logo)
        titel = QtWidgets.QLabel(
            "<b style='font-size:16px'>bbFMR</b><br>"
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
        <p><b>bbFMR</b> wertet Breitband-Ferromagnetische-Resonanz-Messungen (bbFMR) aus:
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
        <p>Entstanden am <b>Walther-Meißner-Institut</b>. Das Logo zeigt das Grundbild der
        ferromagnetischen Resonanz: die <b>Magnetisierung M</b> (rot) präzediert auf einem
        Kegel um das effektive <b>Feld H</b> (Achse); das transversale HF-Treiberfeld <b>h</b>
        steht senkrecht auf H. Quellcode, Doku und Details:<br>
        <a href="{REPO_URL}">{REPO_URL}</a></p>
        </body></html>
        """

    def _frequenz_gewaehlt(self, index: int):
        """Klick in der Uebersicht: Index der VOLLEN Frequenzachse -> Stapel-Index.

        Der Stapel kann durch die Auswertungsauswahl (Jumper) weniger
        Frequenzen enthalten; gewaehlt wird der wertmaessig naechste Fit.
        """
        if not self.stapel or not self.stapel.ergebnisse:
            return
        _, freq_achse = self.matrix.achsen()
        if freq_achse is None or index >= len(freq_achse):
            return
        f = float(freq_achse[index])
        self.aktueller_index = int(np.argmin(np.abs(self.stapel.datensatz.frequenzen - f)))
        self._zeige_aktuellen()


def starte_gui(argv=None):
    """Startet die Qt-Anwendung."""
    import sys

    # Harmlose, sehr gespraechige Wayland-Textinput-Warnung leise stellen
    # ("zwp_text_input_v3_leave: Got leave event for surface 0x0 ..."). Rein
    # kosmetisch; nur ergaenzen, falls der Nutzer QT_LOGGING_RULES nicht selbst setzt.
    regel = "qt.qpa.wayland.textinput=false"
    bestehend = os.environ.get("QT_LOGGING_RULES", "")
    if regel not in bestehend:
        os.environ["QT_LOGGING_RULES"] = f"{bestehend};{regel}".strip(";")

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(argv or sys.argv)
    app.setApplicationName("bbFMR")
    app.setWindowIcon(app_icon())
    app.setStyleSheet(bbFMR_QSS)
    fenster = Hauptfenster()
    fenster.show()
    return app.exec()

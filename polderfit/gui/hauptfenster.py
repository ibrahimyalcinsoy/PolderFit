# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Hauptfenster der PolderFit-GUI.

Im Zentrum steht der Farbplot der TDMS-Messung (Feld auf der x-, Frequenz auf
der y-Achse) in voller Breite - beim Start als leeres kariertes
Koordinatensystem, das sich mit "TDMS laden" fuellt. Damit laesst sich das
Programm auch allein zur Datenansicht nutzen (Verarbeitungskette:
derivative divide, divide slice, ... ganz ohne Fit).

Alle weiteren Funktionen sind in einem "Funktionen"-Dropdown der schlanken
Werkzeugleiste und in der Menueleiste untergebracht. Interaktive Modi
(Resonanz vorgeben, Bereich neu fitten, Ausschlusszone, Ausreisser markieren)
sind EXKLUSIV: es ist immer hoechstens ein Modus aktiv, der aktive Modus ist
in Werkzeugleiste und Statusleiste deutlich markiert, Esc bricht ihn ab.

Lang laufende Schritte (Laden grosser Dateien, Auto-Fit ueber alle Frequenzen)
laufen in einem Hintergrund-Thread; ein andockbares Aktivitaets-Panel zeigt
Fortschrittsbalken und ein Live-Protokoll, damit die App nie "eingefroren" wirkt.
"""

from __future__ import annotations

import html
import os
from dataclasses import replace
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
    Grenzgerade,
    entferne_ausschlusszone,
    fitte_bereich,
    fitte_geraden_bereich,
    fuege_ausschlusszone_hinzu,
)
from ..persistenz.ergebnis_export import exportiere_excel, exportiere_csv
from ..persistenz.projekt import lade_sitzung, speichere_sitzung, stelle_stapel_wieder_her
from ..auswertung.uebersicht import auswertung_kittel_llg
from ..fit.auswahl import Auswertungsauswahl
from .ausreisser_panel import AusreisserPanel
from .auswahl_dialog import AuswahlDialog
from .auswertung_fenster import AuswertungsFenster
from .bereichsfit_dialog import BereichsFitDialog
from .zonen_panel import ZonenPanel
from .matrix_ansicht import MatrixAnsicht
from .fit_ansicht import FitAnsicht
from .mapping_dialog import MappingDialog, VorschauDialog
from .navigator_ansicht import NavigatorAnsicht
from .verarbeitung_panel import VerarbeitungPanel
from .trace_panel import TracePanel
from .arbeiter import Arbeiter
from .stil import PolderFit_QSS

#: Pfad zum PolderFit-App-Icon (SVG, skaliert verlustfrei).
ICON_PFAD = str(Path(__file__).resolve().parent / "assets" / "polderfit.svg")

#: Quellcode-Repository (im Hilfe-Dialog verlinkt).
REPO_URL = "https://github.com/ibrahimyalcinsoy/PolderFit"

#: Farben fuer das Aktivitaetsprotokoll je Meldungsart.
_LOG_FARBEN = {
    "info": "#5A5648", "ok": "#2E7D38", "warn": "#B8860B",
    "problem": "#C0392B", "auto": "#6B6657",
}

#: Statusleisten-Text je aktivem Interaktionsmodus.
_MODUS_TEXTE = {
    "seed": "Modus: Resonanz vorgeben – zwei Punkte auf die Resonanz klicken · Esc bricht ab",
    "bereich": "Modus: Bereich neu fitten – Rechteck aufziehen · Esc bricht ab",
    "zone": "Modus: Ausschlusszone – Rechteck aufziehen · Esc bricht ab",
    "ausreisser": "Modus: Ausreißer markieren – Punkt anklicken oder Kasten aufziehen · Esc beendet",
    "gerade": "Modus: Grenzgerade – zwei Punkte klicken · Esc bricht ab",
}


def app_icon() -> QtGui.QIcon:
    """Liefert das PolderFit-App-Icon (leeres QIcon, falls die Datei fehlt)."""
    return QtGui.QIcon(ICON_PFAD)


class Hauptfenster(QtWidgets.QMainWindow):
    """Zentrales Anwendungsfenster."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PolderFit – Breitband-FMR-Auswertung")
        self.setWindowIcon(app_icon())
        self.resize(1400, 860)

        self.stapel: StapelErgebnis | None = None
        self.aktueller_index: int = 0
        # Voller geladener Datensatz. Der Stapel kann (Jumper/Bereich) auf einem
        # REDUZIERTEN Datensatz arbeiten - neue Auswertungen starten immer hier.
        self.datensatz_voll = None
        # Zuletzt benutzte Auswertungsauswahl (Jumper/Bereich) als Vorbelegung.
        self._letzte_auswahl: Auswertungsauswahl | None = None
        # Zuletzt benutzte Bereichs-Fit-Optionen (Vorbelegung des Dialogs).
        self._bereich_modus: str = "ueberschreiben"
        self._bereich_breite: int | None = None
        # Offenes Kittel/LLG-Auswertungsfenster (hoechstens eines).
        self._auswertungsfenster: AuswertungsFenster | None = None

        # Hintergrund-Job-Zustand.
        self._thread: QtCore.QThread | None = None
        self._arbeiter: Arbeiter | None = None
        self._job_laeuft: bool = False
        self._job_titel: str = ""
        self._bei_fertig = None

        self.matrix = MatrixAnsicht(frequenz_gewaehlt=self._frequenz_gewaehlt,
                                    zoom_geaendert=self._auf_zoom,
                                    modus_geaendert=self._auf_modus_geaendert)
        self.fitansicht = FitAnsicht(grenzen_geaendert=self._grenzen_geaendert)
        self.navigator = NavigatorAnsicht(bereich_gewaehlt=self._navigator_bereich)
        self.verarbeitung = VerarbeitungPanel(geaendert=self._verarbeitung_geaendert)
        self.zonenpanel = ZonenPanel(
            zone_umschalten=self._zone_modus,
            zone_entfernen=self._zone_entfernen,
            gerade_umschalten=self._gerade_modus,
            gerade_seite=self._gerade_seite,
            gerade_entfernen=self._gerade_entfernen,
            geraden_fit=self._geraden_fit,
        )
        #: Grenzgeraden (Neu-Fit-Bereich); bleiben ueber Auto-Fits erhalten,
        #: werden mit einem neuen Datensatz verworfen.
        self._grenzgeraden: list[Grenzgerade] = []
        self.ausreisserpanel = AusreisserPanel(
            wieder_aufnehmen=self._ausreisser_wieder_aufnehmen,
            rueckgaengig=self._rueckgaengig,
        )
        # Zentraler Rueckgaengig-/Wiederholen-Stapel (Strg+Z / Strg+Umschalt+Z):
        # Eintraege (beschreibung, vorher(), nachher()) mit Zustands-
        # Schnappschuessen - Zonen-Undo stellt die betroffenen Fits SOFORT
        # wieder her, ohne neu zu rechnen. Gilt fuer Grenzgeraden, Zonen,
        # Ausreisser und Nachfits; ein neuer Auto-Fit/Datensatz leert ihn.
        self._undo_stapel: list[tuple[str, object, object]] = []
        self._redo_stapel: list[tuple[str, object, object]] = []
        #: Kopien der Grenzgeraden im zuletzt angezeigten Zustand (Vorher-
        #: Schnappschuss fuer Undo - Endpunkt-Drags mutieren die Objekte live).
        self._geraden_schatten: list[Grenzgerade] = []
        self.tracepanel = TracePanel()

        self._baue_oberflaeche()
        self._baue_aktionen()
        self._baue_menue()
        self._baue_werkzeugleiste()
        self._baue_aktivitaet_dock()
        self._baue_navigator_dock()
        self._baue_verarbeitung_dock()
        self._baue_zonen_dock()
        self._baue_ausreisser_dock()
        self._baue_trace_dock()

        # Statusleiste: dauerhafte Modus-Anzeige (rechts), sichtbar nur im Modus.
        self.modus_label = QtWidgets.QLabel("")
        self.modus_label.setObjectName("modus_anzeige")
        self.modus_label.setVisible(False)
        self.statusBar().addPermanentWidget(self.modus_label)

        # Esc bricht jeden Interaktionsmodus ab - egal, welches Widget den
        # Tastaturfokus hat (der Canvas allein reicht nicht, wenn der Modus
        # aus Menue/Toolbar gestartet wurde).
        esc = QtGui.QShortcut(QtGui.QKeySequence("Escape"), self)
        esc.setContext(QtCore.Qt.WindowShortcut)
        esc.activated.connect(self.matrix.beende_modus)

        self.statusBar().showMessage("Bereit. Bitte eine TDMS-Datei laden (Strg+O).")
        self._log("PolderFit bereit. Bitte eine TDMS-Datei laden.", "info")

    # --- Aufbau ------------------------------------------------------------
    def _baue_oberflaeche(self):
        """Farbplot als Zentrum in voller Breite; das Linescan-Fit-Panel ist ein
        abdockbares Fenster, das erst nach dem ersten Auto-Fit erscheint
        (Multi-Monitor-Betrieb: Panel einfach auf den zweiten Bildschirm ziehen)."""
        # Der Farbplot ist IMMER das groesste Element: garantierte Mindestbreite,
        # Docks muessen sich fuegen (siehe auch _dock_schmal_halten).
        self.matrix.setMinimumWidth(520)
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
        # Vollbereich-Umschalter direkt am Linescan-Panel (gespiegelt mit der
        # Menue-Aktion akt_vollbereich; Verbindung in _baue_aktionen).
        self.chk_vollbereich = QtWidgets.QCheckBox("ganzer Feldsweep")
        self.chk_vollbereich.setToolTip(
            "Ganzen Feldsweep zeigen statt aufs Resonanzband zu zoomen.")
        knopfreihe.addWidget(self.chk_vollbereich)
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
        dock.setVisible(False)  # erscheint nach dem ersten Auto-Fit
        self.linescan_dock = dock

    def _dock_schmal_halten(self, dock: QtWidgets.QDockWidget,
                            breite: int | None = None,
                            hoehe: int | None = None) -> None:
        """Blendet ein Dock ein und klemmt es auf seine Sollgroesse.

        Ohne diese Klemme verteilt Qt beim Einblenden den Platz nach den
        (grossen) sizeHints der Matplotlib-Canvases - das Dock blaeht sich auf
        und quetscht den zentralen Farbplot zu einem Streifen zusammen.
        """
        dock.setVisible(True)
        if breite is not None:
            self.resizeDocks([dock], [breite], QtCore.Qt.Horizontal)
        if hoehe is not None:
            self.resizeDocks([dock], [hoehe], QtCore.Qt.Vertical)

    def _baue_aktionen(self):
        """Legt alle Aktionen einmalig an; sie werden in Menue UND Dropdown verwendet.

        Die Sichtbarkeits-Umschalter der Panels ohne bereits existierendes Dock
        (``akt_verarbeitung``, ``akt_zonen_panel``, ``akt_ausreisser_panel``,
        ``akt_aktivitaet``, ``akt_trace``) werden hier nur angelegt; ihre Verbindung
        mit dem jeweiligen Dock erfolgt in den ``_baue_*_dock``-Methoden. Nur
        ``akt_linescan`` wird direkt verbunden, weil das Linescan-Dock schon steht.
        """
        A = QtGui.QAction

        # --- Datei ----------------------------------------------------------
        self.akt_laden = A("TDMS laden …", self)
        self.akt_laden.setShortcut(QtGui.QKeySequence.Open)          # Strg+O
        self.akt_laden.triggered.connect(self._laden)
        self.akt_projekt_laden = A("Projekt laden …", self)
        self.akt_projekt_laden.setShortcut(QtGui.QKeySequence("Ctrl+Shift+O"))
        self.akt_projekt_laden.setToolTip(
            "Gespeicherte Sitzung fortsetzen: TDMS wird neu gelesen, die Fits werden "
            "mit den gespeicherten Fenstern deterministisch wiederhergestellt.")
        self.akt_projekt_laden.triggered.connect(self._projekt_laden)
        self.akt_projekt_speichern = A("Projekt speichern …", self)
        self.akt_projekt_speichern.setShortcut(QtGui.QKeySequence.Save)   # Strg+S
        self.akt_projekt_speichern.setToolTip(
            "Sitzung als JSON sichern: Quelle, Kanal-Zuordnung, Auswahl, Fenster, "
            "Ausschlusszonen, Ausreißer und Fitparameter.")
        self.akt_projekt_speichern.triggered.connect(self._projekt_speichern)
        self.akt_tdms = A("Export TDMS …", self)
        self.akt_tdms.setShortcut(QtGui.QKeySequence("Ctrl+Shift+T"))
        self.akt_tdms.triggered.connect(self._export_tdms)
        self.akt_xlsx = A("Export Excel …", self)
        self.akt_xlsx.setShortcut(QtGui.QKeySequence("Ctrl+E"))
        self.akt_xlsx.triggered.connect(self._export_excel)
        self.akt_csv = A("Export CSV …", self)
        self.akt_csv.setShortcut(QtGui.QKeySequence("Ctrl+Shift+E"))
        self.akt_csv.triggered.connect(self._export_csv)
        self.akt_beenden = A("Beenden", self)
        self.akt_beenden.setShortcut(QtGui.QKeySequence.Quit)             # Strg+Q
        self.akt_beenden.triggered.connect(self.close)

        # --- Bearbeiten (Rueckgaengig/Wiederholen) ---------------------------
        self.akt_rueckgaengig = A("Rückgängig", self)
        self.akt_rueckgaengig.setShortcut(QtGui.QKeySequence.Undo)        # Strg+Z
        self.akt_rueckgaengig.setToolTip(
            "Letzte Änderung zurücknehmen: Grenzgerade, Ausschlusszone, "
            "Ausreißer oder Nachfit (Strg+Z).")
        self.akt_rueckgaengig.setEnabled(False)
        self.akt_rueckgaengig.triggered.connect(self._rueckgaengig)
        self.akt_wiederholen = A("Wiederholen", self)
        self.akt_wiederholen.setShortcuts(
            [QtGui.QKeySequence.Redo, QtGui.QKeySequence("Ctrl+Y")])      # Strg+Umschalt+Z / Strg+Y
        self.akt_wiederholen.setToolTip(
            "Zurückgenommene Änderung wieder anwenden (Strg+Umschalt+Z oder Strg+Y).")
        self.akt_wiederholen.setEnabled(False)
        self.akt_wiederholen.triggered.connect(self._wiederholen)

        # --- Fit (interaktive Modi sind checkbar und EXKLUSIV) ---------------
        self.akt_fit = A("Auto-Fit (alle)", self)
        self.akt_fit.setShortcut(QtGui.QKeySequence("F5"))
        self.akt_fit.triggered.connect(self._auto_fit)
        self.akt_seed = A("Resonanz vorgeben", self)
        self.akt_seed.setShortcut(QtGui.QKeySequence("Ctrl+D"))
        self.akt_seed.setCheckable(True)
        self.akt_seed.setToolTip(
            "Modus: Zwei Punkte auf die Resonanz in der Übersicht klicken → die "
            "Fit-Fenster folgen dieser Dispersion (hilft, wenn der Auto-Fit an "
            "einem Störfeature hängt). Esc bricht ab.")
        self.akt_seed.toggled.connect(self._seed_umschalten)
        self.akt_bereich = A("Bereich neu fitten", self)
        self.akt_bereich.setShortcut(QtGui.QKeySequence("Ctrl+B"))
        self.akt_bereich.setCheckable(True)
        self.akt_bereich.setToolTip(
            "Modus: Rechteck im Farbplot aufziehen → nur dort werden Fenstersuche "
            "und Fit wiederholt (löst Mehrdeutigkeiten neben der Mode auf). "
            "Optionen (Modus, Fensterbreite) folgen im Dialog. Esc bricht ab.")
        self.akt_bereich.toggled.connect(self._bereich_umschalten)
        self.akt_ausreisser = A("Ausreißer markieren", self)
        self.akt_ausreisser.setShortcut(QtGui.QKeySequence("Ctrl+M"))
        self.akt_ausreisser.setCheckable(True)
        self.akt_ausreisser.setToolTip(
            "Modus: Fit-Punkte im Farbplot anklicken oder per Kasten markieren → "
            "raus aus Darstellung und ALLEN Rechnungen (insb. Kittel-Fit). "
            "Reversibel: Rückgängig und Liste im Ausreißer-Panel. Esc beendet.")
        self.akt_ausreisser.toggled.connect(self._ausreisser_modus)
        self.akt_kittel = A("Kittel/LLG-Auswertung …", self)
        self.akt_kittel.setShortcut(QtGui.QKeySequence("Ctrl+K"))
        self.akt_kittel.setToolTip(
            "Eigenes Auswertungsfenster: Kittel- und LLG-Fit mit Feld auf der "
            "x-Achse, Punkte direkt im Plot entfernen, Export mit Fehlermaßen.")
        self.akt_kittel.triggered.connect(self._kittel_llg)

        # --- Ansicht --------------------------------------------------------
        self.akt_vollbereich = A("Linescan: ganzer Feldsweep", self)
        self.akt_vollbereich.setCheckable(True)
        self.akt_vollbereich.setToolTip(
            "Im Linescan-Panel den ganzen Feldsweep zeigen statt aufs Resonanzband zu zoomen.")
        self.akt_vollbereich.toggled.connect(self._vollbereich_umschalten)
        # Checkbox im Linescan-Panel spiegelt die Aktion (beide Richtungen;
        # setChecked mit unveraendertem Wert loest kein toggled aus -> keine Schleife).
        self.chk_vollbereich.toggled.connect(self.akt_vollbereich.setChecked)
        self.akt_vollbereich.toggled.connect(self.chk_vollbereich.setChecked)
        self.akt_problemfits = A("Problemfits ausblenden", self)
        self.akt_problemfits.setCheckable(True)
        self.akt_problemfits.setToolTip(
            "Problematische Fits im Resonanz-Overlay der Übersicht ausblenden.")
        self.akt_problemfits.toggled.connect(self._problemfits_umschalten)

        # Panel-Umschalter (Verbindung mit dem Dock in der jeweiligen _baue_*_dock-Methode).
        self.akt_verarbeitung = A("Panel: Verarbeitung", self)
        self.akt_verarbeitung.setToolTip(
            "Verarbeitungskette des Farbplots (divide-slice, derivative-divide, "
            "relation-amplitude) ein-/ausblenden – funktioniert direkt nach dem "
            "Laden, ganz ohne Fit.")
        self.akt_zonen_panel = A("Panel: Zonen && Grenzgeraden", self)
        self.akt_zonen_panel.setToolTip(
            "Nachfit-Werkzeuge ein-/ausblenden: Ausschlusszonen (Messpunkte aus "
            "allen Fits ausnehmen) und Grenzgeraden (nur den grünen Bereich "
            "neu fitten).")
        self.akt_linescan = A("Panel: Linescan-Fit", self)
        self.akt_linescan.setToolTip(
            "Linescan-Fit-Panel ein-/ausblenden (abdockbar fuer den zweiten Monitor).")
        self.akt_linescan.setCheckable(True)
        self.akt_linescan.setChecked(False)
        self.akt_linescan.toggled.connect(self.linescan_dock.setVisible)
        self.linescan_dock.visibilityChanged.connect(self.akt_linescan.setChecked)
        self.akt_ausreisser_panel = A("Panel: Ausreißer-Liste", self)
        self.akt_ausreisser_panel.setToolTip(
            "Liste der als Ausreißer markierten Punkte ein-/ausblenden.")
        self.akt_aktivitaet = A("Panel: Aktivität", self)
        self.akt_aktivitaet.setToolTip("Aktivitäts- und Protokoll-Panel ein-/ausblenden.")
        self.akt_trace = A("Panel: Call-Trace (Debug)", self)
        self.akt_trace.setToolTip(
            "Entwickler-Werkzeug: zeigt live, welche polderfit-Funktionen aufgerufen "
            "werden. Nur zur Fehlersuche einschalten.")

        # --- Hilfe ----------------------------------------------------------
        self.akt_hilfe = A("Bedienung & Infos …", self)
        self.akt_hilfe.setShortcut(QtGui.QKeySequence.HelpContents)       # F1
        self.akt_hilfe.triggered.connect(self._zeige_hilfe)
        self.akt_repo = A("Repository öffnen", self)
        self.akt_repo.triggered.connect(
            lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(REPO_URL)))

    def _baue_menue(self):
        """Menueleiste mit allen Aktionen – bei kleinem Fenster stets erreichbar."""
        mb = self.menuBar()

        m_datei = mb.addMenu("&Datei")
        m_datei.addAction(self.akt_laden)
        m_datei.addAction(self.akt_projekt_laden)
        m_datei.addAction(self.akt_projekt_speichern)
        m_datei.addSeparator()
        m_datei.addAction(self.akt_tdms)
        m_datei.addAction(self.akt_xlsx)
        m_datei.addAction(self.akt_csv)
        m_datei.addSeparator()
        m_datei.addAction(self.akt_beenden)

        m_bearbeiten = mb.addMenu("&Bearbeiten")
        m_bearbeiten.addAction(self.akt_rueckgaengig)
        m_bearbeiten.addAction(self.akt_wiederholen)

        m_fit = mb.addMenu("&Fit")
        m_fit.addAction(self.akt_fit)
        m_fit.addAction(self.akt_seed)
        m_fit.addAction(self.akt_bereich)
        m_fit.addSeparator()
        m_fit.addAction(self.akt_ausreisser)
        m_fit.addAction(self.akt_kittel)

        m_ansicht = mb.addMenu("&Ansicht")
        m_ansicht.addAction(self.akt_vollbereich)
        m_ansicht.addAction(self.akt_problemfits)
        m_ansicht.addSeparator()
        m_ansicht.addAction(self.akt_verarbeitung)
        m_ansicht.addAction(self.akt_zonen_panel)
        m_ansicht.addAction(self.akt_linescan)
        m_ansicht.addAction(self.akt_ausreisser_panel)
        m_ansicht.addAction(self.akt_aktivitaet)
        m_ansicht.addAction(self.akt_trace)
        self.menue_ansicht = m_ansicht  # weitere Panels haengen sich hier ein

        m_hilfe = mb.addMenu("&Hilfe")
        m_hilfe.addAction(self.akt_hilfe)
        m_hilfe.addAction(self.akt_repo)

    def _baue_werkzeugleiste(self):
        """Radikal schlanke Werkzeugleiste: Laden + "Funktionen"-Dropdown.

        Alle Fit-/Auswerte-/Ansicht-Funktionen sind im Dropdown verborgen (und
        bleiben parallel in der Menueleiste samt Shortcuts erreichbar)."""
        leiste = self.addToolBar("Hauptaktionen")
        leiste.setObjectName("haupt_toolbar")
        leiste.setMovable(False)

        # Klickbares PolderFit-Logo + Wortmarke ganz links -> oeffnet die Hilfe.
        self.btn_logo = QtWidgets.QToolButton()
        self.btn_logo.setIcon(app_icon())
        self.btn_logo.setIconSize(QtCore.QSize(24, 24))
        self.btn_logo.setText(" PolderFit")
        self.btn_logo.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.btn_logo.setAutoRaise(True)
        self.btn_logo.setToolTip("Bedienung & Infos")
        self.btn_logo.setStyleSheet("font-weight: 600; font-size: 14px; padding: 2px 8px;")
        self.btn_logo.clicked.connect(self._zeige_hilfe)
        leiste.addWidget(self.btn_logo)
        leiste.addSeparator()

        leiste.addAction(self.akt_laden)

        # "Funktionen"-Dropdown mit allen weiteren Aktionen.
        self.funktionen_menue = QtWidgets.QMenu("Funktionen", self)
        self.funktionen_menue.addAction(self.akt_rueckgaengig)
        self.funktionen_menue.addAction(self.akt_wiederholen)
        self.funktionen_menue.addSeparator()
        self.funktionen_menue.addAction(self.akt_fit)
        self.funktionen_menue.addAction(self.akt_seed)
        self.funktionen_menue.addAction(self.akt_bereich)
        self.funktionen_menue.addAction(self.akt_ausreisser)
        self.funktionen_menue.addSeparator()
        self.funktionen_menue.addAction(self.akt_kittel)
        self.funktionen_menue.addSeparator()
        m_export = self.funktionen_menue.addMenu("Export")
        m_export.addAction(self.akt_tdms)
        m_export.addAction(self.akt_xlsx)
        m_export.addAction(self.akt_csv)
        m_ansicht = self.funktionen_menue.addMenu("Ansicht")
        m_ansicht.addAction(self.akt_vollbereich)
        m_ansicht.addAction(self.akt_problemfits)
        m_ansicht.addSeparator()
        m_ansicht.addAction(self.akt_verarbeitung)
        m_ansicht.addAction(self.akt_zonen_panel)
        m_ansicht.addAction(self.akt_linescan)
        m_ansicht.addAction(self.akt_ausreisser_panel)
        m_ansicht.addAction(self.akt_aktivitaet)
        m_ansicht.addAction(self.akt_trace)

        self.btn_funktionen = QtWidgets.QToolButton()
        self.btn_funktionen.setText("Funktionen ▾")
        self.btn_funktionen.setMenu(self.funktionen_menue)
        self.btn_funktionen.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.btn_funktionen.setToolTip(
            "Alle Fit-, Auswerte- und Ansichtsfunktionen (auch in der Menueleiste).")
        leiste.addWidget(self.btn_funktionen)

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
        # Unten andocken: nimmt dem Farbplot keine Breite weg. Erscheint
        # automatisch mit einem Hintergrund-Job und verschwindet danach wieder
        # (manuell jederzeit ueber Ansicht -> Panel: Aktivitaet).
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)
        dock.setVisible(False)
        self.aktivitaet_dock = dock
        self._aktivitaet_war_sichtbar = False
        # Toolbar-Umschalter mit der Sichtbarkeit des Docks verbinden.
        self.akt_aktivitaet.setCheckable(True)
        self.akt_aktivitaet.setChecked(False)
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
        dock.setVisible(False)  # erscheint mit der geladenen Messung
        self.verarbeitung_dock = dock
        self.akt_verarbeitung.setCheckable(True)
        self.akt_verarbeitung.setChecked(False)
        self.akt_verarbeitung.toggled.connect(dock.setVisible)
        dock.visibilityChanged.connect(self.akt_verarbeitung.setChecked)

    def _baue_zonen_dock(self):
        """Nachfit-Werkzeuge (links): Grenzgeraden und Ausschlusszonen."""
        dock = QtWidgets.QDockWidget("Zonen & Grenzgeraden", self)
        dock.setObjectName("zonen_dock")
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
        rollbereich.setWidget(self.zonenpanel)
        dock.setWidget(rollbereich)
        dock.setMinimumWidth(280)
        # Bewusst NICHT tabifiziert: hinter einem Tab liegende Docks melden
        # visibilityChanged(False), was die Toolbar-Toggles fehlleiten wuerde.
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        dock.setVisible(False)  # erscheint nach dem ersten Auto-Fit
        self.zonen_dock = dock
        self.akt_zonen_panel.setCheckable(True)
        self.akt_zonen_panel.setChecked(False)
        self.akt_zonen_panel.toggled.connect(dock.setVisible)
        dock.visibilityChanged.connect(self.akt_zonen_panel.setChecked)

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
        self.akt_ausreisser_panel.setCheckable(True)
        self.akt_ausreisser_panel.setChecked(False)
        self.akt_ausreisser_panel.toggled.connect(dock.setVisible)
        dock.visibilityChanged.connect(self.akt_ausreisser_panel.setChecked)

    def _baue_trace_dock(self):
        """Call-Trace-Panel (rechts, abdockbar); standardmaessig ausgeblendet."""
        dock = QtWidgets.QDockWidget("Call-Trace (Debug)", self)
        dock.setObjectName("trace_dock")
        dock.setAllowedAreas(
            QtCore.Qt.RightDockWidgetArea | QtCore.Qt.LeftDockWidgetArea
            | QtCore.Qt.BottomDockWidgetArea
        )
        dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetMovable
            | QtWidgets.QDockWidget.DockWidgetFloatable
            | QtWidgets.QDockWidget.DockWidgetClosable
        )
        dock.setWidget(self.tracepanel)
        dock.setMinimumWidth(320)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        dock.setVisible(False)  # erscheint ueber den Ansicht-Menue-Umschalter
        self.trace_dock = dock
        self.akt_trace.setCheckable(True)
        self.akt_trace.setChecked(False)
        self.akt_trace.toggled.connect(dock.setVisible)
        dock.visibilityChanged.connect(self.akt_trace.setChecked)

    # --- Modus-Verwaltung (exklusiv, sichtbar, Esc bricht ab) ----------------
    def _auf_modus_geaendert(self, modus: str | None):
        """Vom Modus-Manager der Matrix gemeldet: Anzeige und Umschalter syncen."""
        for aktion, name in ((self.akt_seed, "seed"),
                             (self.akt_bereich, "bereich"),
                             (self.akt_ausreisser, "ausreisser")):
            soll = (modus == name)
            if aktion.isChecked() != soll:
                aktion.blockSignals(True)
                aktion.setChecked(soll)
                aktion.blockSignals(False)
        self.zonenpanel.setze_modus_aktiv(modus == "zone")
        self.zonenpanel.setze_gerade_modus_aktiv(modus == "gerade")
        if modus is None:
            self.modus_label.setVisible(False)
            self.statusBar().showMessage("Modus beendet.", 4000)
        else:
            text = _MODUS_TEXTE.get(modus, modus)
            self.modus_label.setText(text.split(" – ")[0])
            self.modus_label.setVisible(True)
            self.statusBar().showMessage(text)

    def _modus_start_erlaubt(self, braucht_fits: bool = False) -> bool:
        """Gemeinsame Vorbedingungen aller Interaktionsmodi (nicht-modal gemeldet)."""
        if self._job_laeuft:
            self._log("Es laeuft ein Hintergrundprozess – Modus nicht gestartet.", "warn")
            return False
        if self.stapel is None or self.datensatz_voll is None:
            self._log("Modus nicht verfuegbar: bitte zuerst eine TDMS-Datei laden.", "warn")
            self.statusBar().showMessage("Bitte zuerst eine TDMS-Datei laden.", 5000)
            return False
        if braucht_fits and not self.stapel.ergebnisse:
            self._log("Modus nicht verfuegbar: bitte zuerst einen Auto-Fit ausfuehren.", "warn")
            self.statusBar().showMessage("Bitte zuerst einen Auto-Fit ausfuehren.", 5000)
            return False
        return True

    def _seed_umschalten(self, an: bool):
        """Umschalter 'Resonanz vorgeben' (Dispersions-Seed)."""
        if not an:
            if self.matrix.modus == "seed":
                self.matrix.beende_modus()
            return
        if not (self._modus_start_erlaubt() and self._mapping_vorhanden()):
            self.akt_seed.setChecked(False)
            return
        self._log("Resonanz vorgeben: zwei Punkte auf die Resonanz in der Übersicht "
                  "klicken (tiefe und hohe Frequenz). Esc bricht ab.", "info")
        self.matrix.starte_dispersion_seed(self._seed_fertig)

    def _bereich_umschalten(self, an: bool):
        """Umschalter 'Bereich neu fitten' (Rechteck-Nachfitten)."""
        if not an:
            if self.matrix.modus == "bereich":
                self.matrix.beende_modus()
            return
        if not self._modus_start_erlaubt(braucht_fits=True):
            self.akt_bereich.setChecked(False)
            return
        self._log("Bereich neu fitten: Rechteck um die Mode aufziehen "
                  "(Esc bricht ab).", "info")
        self.matrix.starte_bereichs_fit(self._bereich_gewaehlt)

    def _zone_modus(self, an: bool):
        """Umschalter des Zonen-Zeichenmodus (aus dem Ausschlusszonen-Panel)."""
        if not an:
            if self.matrix.modus == "zone":
                self.matrix.beende_modus()
            return
        if not self._modus_start_erlaubt(braucht_fits=True):
            self.zonenpanel.setze_modus_aktiv(False)
            return
        self._log("Ausschlusszone: Rechteck um die auszuschliessenden Punkte "
                  "aufziehen (Esc bricht ab).", "info")
        self.matrix.starte_ausschluss_zeichnen(self._zone_gezeichnet)

    def _gerade_modus(self, an: bool):
        """Umschalter des Grenzgeraden-Zeichenmodus (zwei Klicks im Farbplot)."""
        if not an:
            if self.matrix.modus == "gerade":
                self.matrix.beende_modus()
            return
        if not self._modus_start_erlaubt(braucht_fits=True):
            self.zonenpanel.setze_gerade_modus_aktiv(False)
            return
        self._log("Grenzgerade: zwei Punkte im Farbplot klicken – danach an den "
                  "Endpunkten ziehbar; Doppelklick auf die Linie wechselt die "
                  "grüne (Neu-Fit-)Seite. Esc bricht ab.", "info")
        self.matrix.starte_gerade_zeichnen(self._gerade_gezeichnet)

    def _gerade_gezeichnet(self, punkte):
        """Callback nach zwei Klicks: neue Grenzgerade anlegen und anzeigen."""
        (b1, f1_ghz), (b2, f2_ghz) = punkte
        vorher = self._geraden_schatten
        self._grenzgeraden.append(Grenzgerade(b1=float(b1), f1=f1_ghz * 1e9,
                                              b2=float(b2), f2=f2_ghz * 1e9))
        self._zeige_geraden()
        self._merke_geraden_aenderung("Grenzgerade eingefügt", vorher)
        self._log(f"Grenzgerade eingefügt: ({b1:.3f} T, {f1_ghz:.2f} GHz) – "
                  f"({b2:.3f} T, {f2_ghz:.2f} GHz). Grüner Saum = wird neu "
                  f"gefittet; Seite per Doppelklick oder im Panel wechseln.", "ok")

    def _zeige_geraden(self):
        """Synchronisiert Geraden-Overlay (Farbplot), Panel-Liste und Schatten."""
        self.zonenpanel.setze_geraden(self._grenzgeraden)
        self.matrix.zeige_grenzgeraden(self._grenzgeraden,
                                       endpunkt_geaendert=self._gerade_geaendert,
                                       seite_gewechselt=self._gerade_seite)
        self._geraden_schatten = self._geraden_kopie()

    def _merke_geraden_aenderung(self, beschreibung: str,
                                 vorher: list[Grenzgerade]) -> None:
        """Registriert eine Geraden-Aenderung (``vorher`` = Schatten-Kopien)."""
        nachher = self._geraden_schatten
        self._merke_aenderung(beschreibung,
                              lambda v=vorher: self._geraden_setzen(v),
                              lambda n=nachher: self._geraden_setzen(n))

    def _gerade_geaendert(self, index: int, b1: float, f1_ghz: float,
                          b2: float, f2_ghz: float):
        """Endpunkt im Farbplot gezogen: Geometrie uebernehmen.

        Der Vorher-Zustand kommt aus dem Schatten (die Drag-Bewegung hat das
        Objekt bereits live mutiert).
        """
        if not (0 <= index < len(self._grenzgeraden)):
            return
        vorher = self._geraden_schatten
        g = self._grenzgeraden[index]
        g.b1, g.f1, g.b2, g.f2 = float(b1), f1_ghz * 1e9, float(b2), f2_ghz * 1e9
        self.zonenpanel.setze_geraden(self._grenzgeraden)
        self._geraden_schatten = self._geraden_kopie()
        self._merke_geraden_aenderung("Grenzgerade verschoben", vorher)

    def _gerade_seite(self, index: int):
        """Gruene (Neu-Fit-)Seite der Geraden wechseln (Doppelklick/Panel)."""
        if not (0 <= index < len(self._grenzgeraden)):
            return
        vorher = self._geraden_schatten
        self._grenzgeraden[index].seite_wechseln()
        self._zeige_geraden()
        self._merke_geraden_aenderung("Grenzgerade: Seite gewechselt", vorher)
        self._log("Grenzgerade: Seiten getauscht (grün = wird neu gefittet).", "info")

    def _gerade_entfernen(self, index: int):
        if not (0 <= index < len(self._grenzgeraden)):
            return
        vorher = self._geraden_schatten
        del self._grenzgeraden[index]
        self._zeige_geraden()
        self._merke_geraden_aenderung("Grenzgerade entfernt", vorher)
        self._log("Grenzgerade entfernt.", "info")

    def _geraden_fit(self):
        """Nachfitten des gruenen Bereichs aller Grenzgeraden (mit Optionen)."""
        if not self.stapel or not self.stapel.ergebnisse:
            self._log("Grenzgeraden-Fit: bitte zuerst einen Auto-Fit ausfuehren.", "warn")
            return
        if not self._grenzgeraden:
            self._log("Grenzgeraden-Fit: bitte zuerst eine Gerade einzeichnen.", "warn")
            return
        if self._job_laeuft:
            return
        stapel = self.stapel
        geraden = list(self._grenzgeraden)
        dialog = BereichsFitDialog(
            0.0, 0.0, 0.0, 0.0,
            modus_vorgabe=self._bereich_modus, breite_vorgabe=self._bereich_breite,
            titel="Grünen Bereich neu fitten",
            info_text=(f"{len(geraden)} Grenzgerade(n): Im GRÜNEN Bereich werden "
                       "Fenstersuche und Fit wiederholt; die rote Seite bleibt "
                       "unangetastet."),
            parent=self)
        if not dialog.exec():
            self._log("Grenzgeraden-Fit abgebrochen.", "info")
            return
        modus = dialog.modus()
        breite = dialog.breite_punkte()
        self._bereich_modus, self._bereich_breite = modus, breite
        # Undo-Schnappschuss ueber alle Fits (jede Frequenz kann betroffen sein).
        fits_vorher = self._fit_zustand(range(len(stapel.ergebnisse)))

        def aufgabe(melde):
            def fortschritt(k, n, erg):
                status = "⚠ " + erg.problem_text if erg.problematisch else \
                    f"✓ B_res={erg.B_res:.3f} T"
                melde(k, n, f"  {k}/{n}  f={erg.frequenz/1e9:6.2f} GHz  {status}")
            return fitte_geraden_bereich(stapel, geraden, modus=modus,
                                         breite_punkte=breite,
                                         fortschritt=fortschritt)

        def bei_fertig(res):
            neu, uebersprungen = res
            self._aktualisiere_overlay()
            self._zeige_aktuellen()
            if self._auswertungsfenster is not None:
                self._auswertungsfenster.aktualisiere()
            if neu:
                fits_nachher = self._fit_zustand(range(len(stapel.ergebnisse)))
                self._merke_aenderung(
                    "Grenzgeraden-Fit",
                    lambda: self._fit_zustand_setzen(fits_vorher),
                    lambda: self._fit_zustand_setzen(fits_nachher))
            probleme = [i for i in neu if stapel.ergebnisse[i].problematisch]
            breite_text = f", Breite {breite} Punkte" if breite else ""
            text = (f"Grenzgeraden-Fit ({len(geraden)} Gerade(n){breite_text}): "
                    f"{len(neu)} neu gefittet, {len(probleme)} problematisch, "
                    f"{len(uebersprungen)} uebersprungen (rote Seite/ohne Daten).")
            self._log(text, "warn" if probleme else "ok")
            self.statusBar().showMessage(text)

        self._starte_job(aufgabe, bei_fertig, "Grenzgeraden-Fit läuft …")

    def _ausreisser_modus(self, an: bool):
        """Umschalter 'Ausreißer markieren': Punkte anklicken/einrahmen."""
        if not an:
            if self.matrix.modus == "ausreisser":
                self.matrix.beende_modus()
            return
        if not self._modus_start_erlaubt(braucht_fits=True):
            self.akt_ausreisser.setChecked(False)
            return
        self.matrix.setze_ausreisser_modus(True, gewaehlt=self._ausreisser_gewaehlt)
        self._dock_schmal_halten(self.ausreisser_dock, breite=300)
        self._log("Ausreißer markieren aktiv: Punkt anklicken oder Kasten "
                  "aufziehen. Esc oder erneutes Auslösen beendet den Modus.", "info")

    # --- Rueckgaengig / Wiederholen (zentraler Stapel) ------------------------
    def _merke_aenderung(self, beschreibung: str, vorher, nachher) -> None:
        """Registriert eine umkehrbare Aenderung.

        ``vorher()``/``nachher()`` stellen den Zustand VOR bzw. NACH der
        Aenderung wieder her (Schnappschuss-Closures). Eine neue Aenderung
        verwirft den Wiederholen-Stapel.
        """
        self._undo_stapel.append((beschreibung, vorher, nachher))
        del self._undo_stapel[:-50]
        self._redo_stapel.clear()
        self._aktualisiere_undo_aktionen()

    def _rueckgaengig(self) -> None:
        if self._job_laeuft:
            self._log("Rückgängig: bitte warten, ein Hintergrundprozess läuft.", "warn")
            return
        if not self._undo_stapel:
            self._log("Nichts rückgängig zu machen.", "info")
            return
        beschreibung, vorher, nachher = self._undo_stapel.pop()
        vorher()
        self._redo_stapel.append((beschreibung, vorher, nachher))
        self._aktualisiere_undo_aktionen()
        self._log(f"Rückgängig: {beschreibung}.", "ok")
        self.statusBar().showMessage(f"Rückgängig: {beschreibung}.", 5000)

    def _wiederholen(self) -> None:
        if self._job_laeuft:
            self._log("Wiederholen: bitte warten, ein Hintergrundprozess läuft.", "warn")
            return
        if not self._redo_stapel:
            self._log("Nichts zu wiederholen.", "info")
            return
        beschreibung, vorher, nachher = self._redo_stapel.pop()
        nachher()
        self._undo_stapel.append((beschreibung, vorher, nachher))
        self._aktualisiere_undo_aktionen()
        self._log(f"Wiederholt: {beschreibung}.", "ok")
        self.statusBar().showMessage(f"Wiederholt: {beschreibung}.", 5000)

    def _undo_verwerfen(self) -> None:
        """Leert beide Stapel (neuer Datensatz/Auto-Fit: alte Zustaende ungueltig)."""
        self._undo_stapel.clear()
        self._redo_stapel.clear()
        self._aktualisiere_undo_aktionen()

    def _aktualisiere_undo_aktionen(self) -> None:
        self.akt_rueckgaengig.setEnabled(bool(self._undo_stapel))
        self.akt_wiederholen.setEnabled(bool(self._redo_stapel))
        self.akt_rueckgaengig.setText(
            f"Rückgängig: {self._undo_stapel[-1][0]}" if self._undo_stapel
            else "Rückgängig")
        self.akt_wiederholen.setText(
            f"Wiederholen: {self._redo_stapel[-1][0]}" if self._redo_stapel
            else "Wiederholen")

    # Schnappschuss-Helfer -----------------------------------------------------
    def _geraden_kopie(self) -> list[Grenzgerade]:
        return [replace(g) for g in self._grenzgeraden]

    def _geraden_setzen(self, geraden: list[Grenzgerade]) -> None:
        self._grenzgeraden = [replace(g) for g in geraden]
        self._zeige_geraden()

    def _fit_zustand(self, indizes) -> dict:
        """Referenz-Schnappschuss der Fits an ``indizes`` (Fenster/Ergebnis/Beschnitt)."""
        st = self.stapel
        return {int(i): (st.fenster[i], st.ergebnisse[i], st.zugeschnitten[i])
                for i in indizes if 0 <= i < len(st.ergebnisse)}

    def _fit_zustand_setzen(self, zustand: dict) -> None:
        st = self.stapel
        if st is None:
            return
        for i, (fenster, ergebnis, beschnitt) in zustand.items():
            if i < len(st.ergebnisse):
                st.fenster[i] = fenster
                st.ergebnisse[i] = ergebnis
                st.zugeschnitten[i] = beschnitt
        self._aktualisiere_overlay()
        self._zeige_aktuellen()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()

    def _zonen_zustand_setzen(self, zonen: list, fit_zustand: dict) -> None:
        if self.stapel is None:
            return
        self.stapel.ausschlusszonen = list(zonen)
        self.zonenpanel.setze_zonen(self.stapel.ausschlusszonen)
        self.matrix.zeige_ausschlusszonen(self.stapel.ausschlusszonen)
        self._fit_zustand_setzen(fit_zustand)

    def _ausreisser_setzen(self, liste: list[int]) -> None:
        if self.stapel is None:
            return
        self.stapel.ausreisser = sorted(liste)
        self._aktualisiere_overlay()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()

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
        # Kein Interaktionsmodus parallel zu einem Hintergrund-Job.
        self.matrix.beende_modus()
        self._job_laeuft = True
        self._job_titel = titel
        self._bei_fertig = bei_fertig
        self._setze_bedienelemente(False)
        self._setze_aktivitaet(titel)
        self._log(titel, "info")
        # Aktivitaet nur fuer die Dauer des Jobs einblenden (unten, flach) -
        # war sie schon offen (manuell), bleibt sie es auch danach.
        self._aktivitaet_war_sichtbar = self.aktivitaet_dock.isVisible()
        self._dock_schmal_halten(self.aktivitaet_dock, hoehe=210)
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
        # Automatisch eingeblendetes Aktivitaets-Panel wieder schliessen -
        # der Farbplot soll das Bild dominieren (Protokoll bleibt erhalten).
        if not self._aktivitaet_war_sichtbar:
            self.aktivitaet_dock.setVisible(False)

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
            self.zonenpanel.setze_zonen([])
            self._grenzgeraden = []
            self._geraden_schatten = []
            self.zonenpanel.setze_geraden([])
            self._undo_verwerfen()  # alte Zustaende gehoeren zum alten Datensatz
            # Datenansicht sofort ermoeglichen: Verarbeitungs-Panel einblenden.
            self._dock_schmal_halten(self.verarbeitung_dock, breite=300)
            self._log(
                f"Geladen: {os.path.basename(pfad_)} – {datensatz.format_typ}, "
                f"{len(datensatz)} Frequenzen (Profil: "
                f"{datensatz.meta.get('mapping_profil', 'manuell')}).", "ok")
            self.statusBar().showMessage(
                f"Geladen: {os.path.basename(pfad_)} ({datensatz.format_typ}, "
                f"{len(datensatz)} Frequenzen). Daten ansehen (Verarbeitung) "
                f"oder 'Auto-Fit' starten.")

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

    def _nach_autofit(self, stapel: StapelErgebnis) -> None:
        """Gemeinsamer Abschluss beider Auto-Fit-Wege (mit/ohne Vorgabe)."""
        self.stapel = stapel
        self._undo_verwerfen()  # Undo-Stapel gehoert zum alten Stapel
        self._aktualisiere_overlay()
        # Neuer Stapel: Ausschlusszonen beginnen leer.
        self.zonenpanel.setze_zonen(stapel.ausschlusszonen)
        self.matrix.zeige_ausschlusszonen(stapel.ausschlusszonen)
        self.aktueller_index = 0
        # Fuer den Korrekturlauf: NUR das Linescan-Panel einblenden (schmal
        # geklemmt, der Farbplot bleibt das groesste Element). Zonen &
        # Grenzgeraden holt man sich bei Bedarf ueber Ansicht/Funktionen.
        self._dock_schmal_halten(self.linescan_dock, breite=500)
        self._zeige_aktuellen()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()

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
            self._nach_autofit(stapel)
            n_prob = len(stapel.index_problematisch())
            art = "ok" if n_prob == 0 else "warn"
            self._log(f"Auto-Fit fertig: {len(stapel.ergebnisse)} Fits, {n_prob} problematisch.", art)
            for grund, anzahl in stapel.problem_statistik().items():
                self._log(f"   • {grund}: {anzahl}", "warn")
            self.statusBar().showMessage(
                f"Auto-Fit fertig. {len(stapel.ergebnisse)} Fits, {n_prob} problematisch.")

        self._starte_job(aufgabe, bei_fertig, "Auto-Fit läuft …")

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
            self._nach_autofit(stapel)
            n_prob = len(stapel.index_problematisch())
            self._log(f"Auto-Fit (mit Vorgabe) fertig: {len(stapel.ergebnisse)} Fits, "
                      f"{n_prob} problematisch.", "ok" if n_prob <= len(stapel.ergebnisse) // 3 else "warn")
            self.statusBar().showMessage(
                f"Auto-Fit (mit vorgegebener Dispersion) fertig. {n_prob} problematisch.")

        self._starte_job(aufgabe, bei_fertig, "Auto-Fit mit vorgegebener Dispersion …")

    def _bereich_gewaehlt(self, feld_min, feld_max, f_min_ghz, f_max_ghz):
        """Callback nach dem Aufziehen: Optionen abfragen, dann im Rechteck neu fitten."""
        stapel = self.stapel
        if stapel is None or not stapel.ergebnisse:
            return
        dialog = BereichsFitDialog(feld_min, feld_max, f_min_ghz, f_max_ghz,
                                   modus_vorgabe=self._bereich_modus,
                                   breite_vorgabe=self._bereich_breite, parent=self)
        if not dialog.exec():
            self._log("Bereichs-Fit abgebrochen.", "info")
            return
        modus = dialog.modus()
        breite = dialog.breite_punkte()
        self._bereich_modus, self._bereich_breite = modus, breite
        f_min, f_max = f_min_ghz * 1e9, f_max_ghz * 1e9
        betroffen_vorab = [int(i) for i in np.flatnonzero(
            (stapel.datensatz.frequenzen >= f_min)
            & (stapel.datensatz.frequenzen <= f_max))]
        fits_vorher = self._fit_zustand(betroffen_vorab)

        def aufgabe(melde):
            def fortschritt(k, n, erg):
                status = "⚠ " + erg.problem_text if erg.problematisch else \
                    f"✓ B_res={erg.B_res:.3f} T"
                melde(k, n, f"  {k}/{n}  f={erg.frequenz/1e9:6.2f} GHz  {status}")
            return fitte_bereich(stapel, feld_min, feld_max, f_min, f_max,
                                 modus=modus, breite_punkte=breite,
                                 fortschritt=fortschritt)

        def bei_fertig(res):
            neu, uebersprungen = res
            self._aktualisiere_overlay()
            self._zeige_aktuellen()
            if self._auswertungsfenster is not None:
                self._auswertungsfenster.aktualisiere()
            if neu:
                fits_nachher = self._fit_zustand(betroffen_vorab)
                self._merke_aenderung(
                    "Bereichs-Fit",
                    lambda: self._fit_zustand_setzen(fits_vorher),
                    lambda: self._fit_zustand_setzen(fits_nachher))
            probleme = [i for i in neu if stapel.ergebnisse[i].problematisch]
            breite_text = f", Breite {breite} Punkte" if breite else ""
            text = (f"Bereichs-Fit [{feld_min:.3f}-{feld_max:.3f} T, "
                    f"{f_min_ghz:.2f}-{f_max_ghz:.2f} GHz{breite_text}]: "
                    f"{len(neu)} neu gefittet, {len(probleme)} problematisch, "
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
        punkte_im_fenster = int(np.count_nonzero((voll.feld >= unten) & (voll.feld <= oben)))
        e = self.stapel.ergebnisse[i]
        status = f"PROBLEM: {e.problem_text}" if e.problematisch else "OK"
        # 1-R² in wissenschaftlicher Notation, damit echte Variation sichtbar wird.
        eins_minus_r2 = (1.0 - e.R2) if np.isfinite(e.R2) else float("nan")
        dh_mt = e.dH * 1e3 if np.isfinite(e.dH) else float("nan")
        text = (
            f"[{i+1}/{len(self.stapel.ergebnisse)}] f={e.frequenz/1e9:.3f} GHz │ "
            f"B_res={e.B_res:.4f} T │ ΔH={dh_mt:.2f} mT │ alpha={e.alpha:.2e} │ "
            f"rmse_norm={e.rmse_norm:.3f} │ 1-R²={eins_minus_r2:.1e} │ "
            f"Fenster {punkte_im_fenster} Pkt │ {status}")
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
        fits_vorher = self._fit_zustand([i])
        erg = fitte_neu(self.stapel, i, feld_unten=unten, feld_oben=oben)
        fits_nachher = self._fit_zustand([i])
        self._merke_aenderung(
            f"Grenzen gezogen (f={erg.frequenz/1e9:.2f} GHz)",
            lambda: self._fit_zustand_setzen(fits_vorher),
            lambda: self._fit_zustand_setzen(fits_nachher))
        self._zeige_aktuellen()
        self._aktualisiere_overlay()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()
        art = "problem" if erg.problematisch else "ok"
        self._log(f"Neu gefittet f={erg.frequenz/1e9:.2f} GHz "
                  f"[{unten:.3f}–{oben:.3f} T] → {'⚠ ' + erg.problem_text if erg.problematisch else '✓ OK'}",
                  art)

    def _neu_fitten(self):
        if not self.stapel or not self.stapel.ergebnisse:
            return
        i = self.aktueller_index
        unten, oben = self.stapel.fenster[i]
        fits_vorher = self._fit_zustand([i])
        erg = fitte_neu(self.stapel, i, feld_unten=unten, feld_oben=oben)
        fits_nachher = self._fit_zustand([i])
        self._merke_aenderung(
            f"Nochmal gefittet (f={erg.frequenz/1e9:.2f} GHz)",
            lambda: self._fit_zustand_setzen(fits_vorher),
            lambda: self._fit_zustand_setzen(fits_nachher))
        self._zeige_aktuellen()
        self._aktualisiere_overlay()

    def _kittel_llg(self):
        """Oeffnet das Kittel/LLG-Auswertungsfenster (eigenes, nicht-modales Fenster)."""
        if not self.stapel or not self.stapel.ergebnisse:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst fitten.")
            return
        if self._auswertungsfenster is None:
            self._auswertungsfenster = AuswertungsFenster(
                hole_stapel=lambda: self.stapel,
                ausreisser_markieren=self._ausreisser_gewaehlt,
                ausreisser_rueckgaengig=self._rueckgaengig,
                parent=self)
            self._auswertungsfenster.finished.connect(self._auswertungsfenster_zu)
        else:
            self._auswertungsfenster.aktualisiere()
        self._auswertungsfenster.show()
        self._auswertungsfenster.raise_()
        self._auswertungsfenster.activateWindow()
        n_ausreisser = len(self.stapel.ausreisser)
        if n_ausreisser:
            self._log(f"Kittel/LLG: {n_ausreisser} Ausreißer ausgeschlossen "
                      f"({len(self.stapel.ergebnisse_aktiv())} Punkte verbleiben).", "info")

    def _auswertungsfenster_zu(self, *_args):
        self._auswertungsfenster = None

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
        exportiere_excel(self.stapel.ergebnisse, pfad, global_param,
                         ausreisser=self.stapel.ausreisser)
        self.statusBar().showMessage(f"Excel gespeichert: {pfad}")
        self._log(f"Excel gespeichert: {os.path.basename(pfad)}", "ok")

    def _export_csv(self):
        if not self._fits_vorhanden():
            return
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(self, "CSV speichern", "", "CSV (*.csv)")
        if not pfad:
            return
        exportiere_csv(self.stapel.ergebnisse, pfad, ausreisser=self.stapel.ausreisser)
        self.statusBar().showMessage(f"CSV gespeichert: {pfad}")
        self._log(f"CSV gespeichert: {os.path.basename(pfad)}", "ok")

    def _fits_vorhanden(self) -> bool:
        if not self.stapel or not self.stapel.ergebnisse:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst fitten.")
            return False
        return True

    # --- Ausschlusszonen ------------------------------------------------------
    def _zone_gezeichnet(self, feld_min, feld_max, f_min_ghz, f_max_ghz):
        stapel = self.stapel
        zone = Ausschlusszone(feld_min, feld_max, f_min_ghz * 1e9, f_max_ghz * 1e9)
        # Vorher-Schnappschuss fuer Undo: Zonenliste + Fits im betroffenen Band.
        betroffen_vorab = [int(i) for i in np.flatnonzero(
            (stapel.datensatz.frequenzen >= zone.frequenz_min)
            & (stapel.datensatz.frequenzen <= zone.frequenz_max))]
        zonen_vorher = list(stapel.ausschlusszonen)
        fits_vorher = self._fit_zustand(betroffen_vorab)

        def aufgabe(melde):
            def fortschritt(k, n, erg):
                melde(k, n, "")
            return fuege_ausschlusszone_hinzu(stapel, zone, fortschritt=fortschritt)

        def bei_fertig(betroffen):
            self.zonenpanel.setze_zonen(stapel.ausschlusszonen)
            self.matrix.zeige_ausschlusszonen(stapel.ausschlusszonen)
            self._aktualisiere_overlay()
            self._zeige_aktuellen()
            if self._auswertungsfenster is not None:
                self._auswertungsfenster.aktualisiere()
            zonen_nachher = list(stapel.ausschlusszonen)
            fits_nachher = self._fit_zustand(betroffen_vorab)
            self._merke_aenderung(
                "Ausschlusszone hinzugefügt",
                lambda: self._zonen_zustand_setzen(zonen_vorher, fits_vorher),
                lambda: self._zonen_zustand_setzen(zonen_nachher, fits_nachher))
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
        zone = stapel.ausschlusszonen[zonen_index]
        betroffen_vorab = [int(i) for i in np.flatnonzero(
            (stapel.datensatz.frequenzen >= zone.frequenz_min)
            & (stapel.datensatz.frequenzen <= zone.frequenz_max))]
        zonen_vorher = list(stapel.ausschlusszonen)
        fits_vorher = self._fit_zustand(betroffen_vorab)

        def aufgabe(melde):
            return entferne_ausschlusszone(stapel, zonen_index,
                                           fortschritt=lambda k, n, e: melde(k, n, ""))

        def bei_fertig(betroffen):
            self.zonenpanel.setze_zonen(stapel.ausschlusszonen)
            self.matrix.zeige_ausschlusszonen(stapel.ausschlusszonen)
            self._aktualisiere_overlay()
            self._zeige_aktuellen()
            if self._auswertungsfenster is not None:
                self._auswertungsfenster.aktualisiere()
            zonen_nachher = list(stapel.ausschlusszonen)
            fits_nachher = self._fit_zustand(betroffen_vorab)
            self._merke_aenderung(
                "Ausschlusszone entfernt",
                lambda: self._zonen_zustand_setzen(zonen_vorher, fits_vorher),
                lambda: self._zonen_zustand_setzen(zonen_nachher, fits_nachher))
            self._log(f"Ausschlusszone entfernt: {len(betroffen)} Linescans neu gefittet.", "ok")

        self._starte_job(aufgabe, bei_fertig, "Ausschlusszone entfernen …")

    # --- Ausreisser-Management -----------------------------------------------
    def _merke_ausreisser_aenderung(self, beschreibung: str,
                                    vorher: list[int]) -> None:
        nachher = list(self.stapel.ausreisser)
        self._merke_aenderung(beschreibung,
                              lambda v=vorher: self._ausreisser_setzen(v),
                              lambda n=nachher: self._ausreisser_setzen(n))

    def _ausreisser_gewaehlt(self, indizes: list[int]):
        """Callback aus Farbplot/Auswertungsfenster: Punkte ausschliessen (Echtzeit)."""
        if not self.stapel or not indizes:
            return
        neu = [i for i in indizes if not self.stapel.ist_ausreisser(i)]
        if not neu:
            return
        vorher = list(self.stapel.ausreisser)
        for i in neu:
            self.stapel.ausreisser_umschalten(i)
        self._merke_ausreisser_aenderung(
            f"Ausreißer markiert ({len(neu)} Punkt(e))", vorher)
        self._aktualisiere_overlay()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()
        frequenzen = [self.stapel.ergebnisse[i].frequenz / 1e9 for i in neu]
        self._log(f"Ausreißer markiert: {len(neu)} Punkt(e) "
                  f"({', '.join(f'{f:.2f}' for f in frequenzen[:6])}"
                  f"{' …' if len(frequenzen) > 6 else ''} GHz) – "
                  f"insgesamt {len(self.stapel.ausreisser)} ausgeschlossen.", "ok")

    def _ausreisser_wieder_aufnehmen(self, indizes: list[int]):
        """Aus der Liste: Punkte wieder in Darstellung und Rechnungen aufnehmen."""
        if not self.stapel or not indizes:
            return
        vorher = list(self.stapel.ausreisser)
        for i in indizes:
            if self.stapel.ist_ausreisser(i):
                self.stapel.ausreisser_umschalten(i)
        self._merke_ausreisser_aenderung(
            f"Ausreißer wieder aufgenommen ({len(indizes)})", vorher)
        self._aktualisiere_overlay()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()
        self._log(f"{len(indizes)} Ausreißer wieder aufgenommen – "
                  f"verbleibend {len(self.stapel.ausreisser)}.", "ok")

    # --- Projekt speichern / laden -------------------------------------------
    def _projekt_speichern(self):
        if not self.stapel or not self.stapel.ergebnisse:
            QtWidgets.QMessageBox.information(
                self, "Hinweis", "Bitte zuerst fitten – gespeichert wird der "
                "komplette Auswertungszustand.")
            return
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Projekt speichern", "", "PolderFit-Projekt (*.json)")
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
            self, "Projekt laden", "", "PolderFit-Projekt (*.json)")
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
            self._undo_verwerfen()
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
            self.zonenpanel.setze_zonen(stapel.ausschlusszonen)
            self.matrix.zeige_ausschlusszonen(stapel.ausschlusszonen)
            self.aktueller_index = 0
            self._dock_schmal_halten(self.verarbeitung_dock, breite=300)
            self._dock_schmal_halten(self.linescan_dock, breite=500)
            self._zeige_aktuellen()
            if self._auswertungsfenster is not None:
                self._auswertungsfenster.aktualisiere()
            self._log(f"Projekt geladen: {os.path.basename(pfad)} – "
                      f"{len(stapel.ergebnisse)} Fits wiederhergestellt, "
                      f"{len(stapel.ausreisser)} Ausreißer, "
                      f"{len(stapel.ausschlusszonen)} Zonen.", "ok")
            self.statusBar().showMessage(
                f"Projekt geladen ({len(stapel.ergebnisse)} Fits).")

        self._starte_job(aufgabe, bei_fertig, f"Lade Projekt {os.path.basename(pfad)} …")

    def _verarbeitung_geaendert(self, kette, anzeige_modus: str):
        """Callback des Verarbeitungspanels: Kette neu auf den Farbplot anwenden.

        Funktioniert ab dem Laden der Messung - ein Fit-Stapel ist NICHT noetig
        (reine Datenansicht: derivative divide & Co. ohne Auswertung).
        """
        if self.datensatz_voll is None:
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
        """Hilfe-Dialog: Bedienung und Repository-Link."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("PolderFit – Hilfe & Infos")
        dlg.setWindowIcon(app_icon())
        dlg.resize(660, 580)
        lay = QtWidgets.QVBoxLayout(dlg)

        kopf = QtWidgets.QHBoxLayout()
        logo = QtWidgets.QLabel()
        logo.setPixmap(app_icon().pixmap(56, 56))
        kopf.addWidget(logo)
        titel = QtWidgets.QLabel(
            "<b style='font-size:16px'>PolderFit</b><br>"
            "Breitband-FMR-Auswertung")
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
        <p><b>PolderFit</b> wertet Breitband-FMR-Messungen (bbFMR) aus: TDMS-Dateien einlesen,
        je Frequenz das Resonanzsignal fitten und daraus die Materialparameter bestimmen.
        Die Karte lässt sich auch <b>allein zur Datenansicht</b> nutzen (Verarbeitung:
        derivative divide, divide slice, … – ganz ohne Fit).</p>

        <h3>Arbeitsablauf</h3>
        <ol>
          <li><b>TDMS laden</b> (Strg+O) – sortiertes oder unsortiertes Format wird erkannt.
              Danach füllt die Messung den Farbplot; das Verarbeitungs-Panel erscheint.</li>
          <li><b>Auto-Fit (alle)</b> (F5) – sucht je Frequenz die Resonanz, schneidet ein Band
              und fittet Real- und Imaginärteil gleichzeitig. Läuft im Hintergrund;
              Fortschritt und Protokoll im <b>Aktivitäts-Panel</b>.</li>
          <li><b>Nachfitten</b> – <b>„Bereich neu fitten"</b> (Strg+B, Rechteck im
              Farbplot; Optionen: überschreiben/ergänzen, feste Fensterbreite), die
              <b>grünen Grenzlinien</b> im Linescan-Panel ziehen oder <b>Grenzgeraden</b>
              (Panel „Zonen &amp; Grenzgeraden"): Linie per zwei Klicks einfügen, an den
              Endpunkten ziehen (verschieben/rotieren), grüner Saum = wird neu gefittet,
              roter Saum = wird ignoriert (Doppelklick auf die Linie wechselt die Seite);
              zwei Geraden ergeben ein Band.
              <i>Zurück/Weiter/Nochmal fitten/Nächster Problemfit</i> steuern den Korrekturlauf.</li>
          <li><b>Ausreißer markieren</b> (Strg+M) – falsche Fit-Punkte anklicken oder per Kasten
              entfernen; reversibel (Liste + Rückgängig im Ausreißer-Panel). Ausgeschlossene
              Punkte fehlen in ALLEN Auswertungen und sind im Export gekennzeichnet.</li>
          <li><b>Kittel/LLG-Auswertung</b> (Strg+K) – eigenes Fenster mit Feld auf der x-Achse:
              Punkte direkt im Plot entfernen, Fit rechnet sofort neu; Export mit Plot,
              Parametern und Messfehlern.</li>
          <li><b>Export</b> – Rohdaten/Fitkurven als TDMS, Parameter samt Unsicherheiten
              als Excel (Strg+E)/CSV.</li>
        </ol>

        <h3>Interaktive Modi</h3>
        <ul>
          <li>Es ist immer höchstens <b>ein</b> Modus aktiv (Resonanz vorgeben, Bereich neu
              fitten, Ausschlusszone, Ausreißer markieren); der aktive Modus ist im
              „Funktionen"-Menü markiert und wird rechts in der Statusleiste angezeigt.</li>
          <li><b>Esc</b> bricht jeden Modus ab; das Starten eines Modus beendet den vorherigen.</li>
          <li><b>Strg+Z / Strg+Umschalt+Z</b> (auch Strg+Y): Änderungen rückgängig machen und
              wiederholen – Grenzgeraden, Ausschlusszonen, Ausreißer und Nachfits. Das
              Zurücknehmen einer Zone stellt die betroffenen Fits sofort wieder her,
              ohne neu zu rechnen.</li>
        </ul>

        <h3>Übersicht – Navigation &amp; Zoom</h3>
        <ul>
          <li><b>Klicken</b>: Frequenz wählen → der zugehörige Fit wird geladen.</li>
          <li><b>Kästchen ziehen</b>: auf den markierten Bereich zoomen.</li>
          <li><b>Mausrad</b>: rein/raus zoomen · <b>Doppelklick</b>: Zoom zurücksetzen.</li>
          <li><b>Umschalt+Mausrad</b> oder <b>↑/↓</b> (Pos1/Ende, Bild↑/↓): Frequenz wechseln.</li>
          <li>Beim Zoomen erscheint der <b>Navigator</b> – er zeigt die Position in der
              Gesamtmessung (Klick verschiebt den Ausschnitt).</li>
          <li><b>„Problemfits ausblenden"</b>: blendet problematische Fits im Overlay aus.</li>
        </ul>

        <hr>
        <p>Quellcode und Dokumentation:<br>
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
    app.setApplicationName("PolderFit")
    app.setWindowIcon(app_icon())
    app.setStyleSheet(PolderFit_QSS)
    fenster = Hauptfenster()
    # Farbplot in voller Breite: maximiert starten.
    fenster.showMaximized()
    return app.exec()

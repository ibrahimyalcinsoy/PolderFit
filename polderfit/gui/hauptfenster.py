# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Hauptfenster der PolderFit-GUI.

Im Zentrum steht der Farbplot der TDMS-Messung (Feld auf der x-, Frequenz auf
der y-Achse) in voller Breite - beim Start als leeres kariertes
Koordinatensystem, das sich mit "TDMS laden" fuellt. Damit laesst sich das
Programm auch allein zur Datenansicht nutzen (Verarbeitung: derivative divide,
divide slice, ... ganz ohne Fit).

Alle Funktionen sitzen in EINER Leiste: der Menueleiste mit klickbarem
Programmnamen (links), den Menues Datei/Bearbeiten/Funktionen/Ansicht/Hilfe
und dem "TDMS laden"-Schnellzugriff (rechts). Interaktive Modi (Bereich neu
fitten, Ausschlusszone, Grenzgerade, Ausreisser markieren) sind EXKLUSIV: es
ist immer hoechstens ein Modus aktiv, der aktive Modus ist im Menue und in der
Statusleiste markiert, Esc bricht ihn ab. Grenzgeraden, Zonen und Bereichs-Fit
funktionieren DIREKT nach dem Laden - ein Auto-Fit ist keine Voraussetzung
(:func:`polderfit.fit.batch.leerer_stapel`).

Bewertung der Fits (DIN EN 60073-Farben, :mod:`polderfit.gui.farben`): gruen =
gut, gelb = problematisch, rot = fehlgeschlagen, grau = ignoriert; manuelle
Nachfits gelten als vom Nutzer bestaetigt (gruen mit blauem Rand) und lassen
sich jederzeit umbewerten (Funktionen -> Bewertung, Strg+1/2/3, Strg+I).

Voreinstellungen (physikalische Parameter, Verarbeitung, Anzeige, Export)
werden ueber Datei -> Einstellungen gespeichert/geladen und beim Start aus
dem Konfigurationsverzeichnis uebernommen. Der Arbeitsstand wird nach jeder
Aenderung zeitversetzt in eine Auto-Sicherung geschrieben (Datei ->
Auto-Sicherung wiederherstellen). Anzeige-Zustaende (Zoom, Dock-Layout,
Achsengeometrie) werden nie gespeichert; Ansicht -> Fensterlayout
zuruecksetzen stellt den Auslieferungszustand her. F11 schaltet den
Vollbildmodus (auch unter Windows) um.

Lang laufende Schritte (Laden grosser Dateien, Auto-Fit ueber alle Frequenzen)
laufen in einem Hintergrund-Thread; ein andockbares Aktivitaets-Panel zeigt
Fortschrittsbalken und ein Live-Protokoll, damit die App nie "eingefroren" wirkt.
"""

from __future__ import annotations

import html
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
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
from ..fit.batch import Ausschlusszone, StapelErgebnis, fitte_alle, fitte_neu, leerer_stapel
from ..fit.fenster_steuerung import (
    Grenzgerade,
    entferne_ausschlusszone,
    fitte_bereich,
    fitte_geraden_bereich,
    fuege_ausschlusszone_hinzu,
)
from ..fit.linescan_fit import BEWERTUNG_TEXTE, hauptmode_wechseln
from ..fit.parameter import PhysikParameter
from ..persistenz.ergebnis_export import exportiere_excel, exportiere_csv
from ..persistenz.einstellungen import (
    DATEI_ENDUNG,
    FARBSKALEN,
    Einstellungen,
    autosicherung_pfad,
    lade_einstellungen,
    lade_standard,
    speichere_einstellungen,
    standard_pfad,
)
from ..persistenz.projekt import (
    grenzgeraden_aus_sitzung,
    lade_sitzung,
    speichere_sitzung,
    stelle_stapel_wieder_her,
)
from ..auswertung.uebersicht import auswertung_kittel_llg
from ..fit.auswahl import Auswertungsauswahl
from .ausreisser_panel import AusreisserPanel
from .auswahl_dialog import AuswahlDialog
from .parameter_dialog import ParameterDialog
from .auswertung_fenster import AuswertungsFenster
from .bereichsfit_dialog import BereichsFitDialog
from .export_dialog import AllesSpeichernDialog, SpaltenDialog
from .zonen_panel import ZonenPanel
from .matrix_ansicht import MatrixAnsicht
from .fit_ansicht import FitAnsicht
from .mapping_dialog import MappingDialog, VorschauDialog
from .navigator_ansicht import NavigatorAnsicht
from .verarbeitung_panel import VerarbeitungPanel
from .trace_panel import TracePanel
from .arbeiter import Arbeiter
from .stil import PolderFit_QSS
from .widgets import RuhigeSpinBox
from . import farben as F
from .. import PROGRAMMNAME

#: Quellcode-Repository (im Hilfe-Dialog verlinkt).
REPO_URL = "https://github.com/ibrahimyalcinsoy/PolderFit"

#: Farben fuer das Aktivitaetsprotokoll je Meldungsart (Normsemantik).
_LOG_FARBEN = F.LOG_FARBEN

#: Statusleisten-Text je aktivem Interaktionsmodus.
_MODUS_TEXTE = {
    "bereich": "Modus: Bereich neu fitten – Rechteck aufziehen · Esc bricht ab",
    "zone": "Modus: Ausschlusszone – Rechteck aufziehen · Esc bricht ab",
    "ausreisser": "Modus: Ausreißer markieren – Punkt anklicken oder Kasten aufziehen · Esc beendet",
    "gerade": "Modus: Grenzgerade – zwei Punkte klicken · Esc bricht ab",
}

#: Verzoegerung der Auto-Sicherung nach der letzten Aenderung (ms).
_AUTOSICHERUNG_MS = 15000


class Hauptfenster(QtWidgets.QMainWindow):
    """Zentrales Anwendungsfenster."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{PROGRAMMNAME} – Breitband-FMR-Auswertung")
        self.resize(1400, 860)

        self.stapel: StapelErgebnis | None = None
        self.aktueller_index: int = 0
        # Voller geladener Datensatz. Der Stapel kann (Jumper/Bereich) auf einem
        # REDUZIERTEN Datensatz arbeiten - neue Auswertungen starten immer hier.
        self.datensatz_voll = None
        # Zuletzt benutzte Auswertungsauswahl (Jumper/Bereich) als Vorbelegung.
        self._letzte_auswahl: Auswertungsauswahl | None = None
        #: Voreinstellungen (Datei -> Einstellungen); beim Start aus dem
        #: Konfigurationsverzeichnis geladen.
        self._einstellungen, self._einstellungen_geladen = lade_standard()
        # Zuletzt benutzte Bereichs-Fit-Optionen (Vorbelegung des Dialogs).
        self._bereich_modus: str = self._einstellungen.bereichsfit.get("modus", "ueberschreiben")
        self._bereich_breite: int | None = self._einstellungen.bereichsfit.get("breite_punkte")
        # Zuletzt benutzter Frequenz- (Hz) und Feldbereich (T) des Grenzgeraden-
        # Fits: Vorbelegung beim naechsten Aufruf, mit neuem Datensatz verworfen.
        self._bereich_frequenz: tuple[float, float] | None = None
        self._bereich_feld: tuple[float, float] | None = None
        #: Einstellbare physikalische Parameter (g-Faktor/gamma, Geometrie,
        #: Fensterfaktor, Schwellen, alpha-Grenzen, Moden) - Dialog: Strg+P.
        self._physik = self._einstellungen.physik_parameter()
        # Offenes Kittel/LLG-Auswertungsfenster (hoechstens eines).
        self._auswertungsfenster: AuswertungsFenster | None = None
        #: Zuletzt benutzter Ordner fuer Dialoge.
        self._letzter_ordner: str = ""

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
        self.verarbeitung = VerarbeitungPanel(geaendert=self._verarbeitung_geaendert,
                                              farbskala_geaendert=self._farbskala_geaendert)
        self.zonenpanel = ZonenPanel(
            zone_umschalten=self._zone_modus,
            zone_entfernen=self._zone_entfernen,
            gerade_umschalten=self._gerade_modus,
            gerade_seite=self._gerade_seite,
            gerade_entfernen=self._gerade_entfernen,
            geraden_fit=self._geraden_fit,
            gerade_mode=self._gerade_mode,
        )
        #: Grenzgeraden (Fit-Bereich); bleiben ueber Auto-Fits erhalten,
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
        # Ausreisser, Bewertungen und Nachfits; ein neuer Auto-Fit/Datensatz leert ihn.
        self._undo_stapel: list[tuple[str, object, object]] = []
        self._redo_stapel: list[tuple[str, object, object]] = []
        #: Kopien der Grenzgeraden im zuletzt angezeigten Zustand (Vorher-
        #: Schnappschuss fuer Undo - Endpunkt-Drags mutieren die Objekte live).
        self._geraden_schatten: list[Grenzgerade] = []
        self.tracepanel = TracePanel()

        # Auto-Sicherung des Arbeitsstands (zeitversetzt nach jeder Aenderung).
        self._autosicherung_timer = QtCore.QTimer(self)
        self._autosicherung_timer.setSingleShot(True)
        self._autosicherung_timer.setInterval(_AUTOSICHERUNG_MS)
        self._autosicherung_timer.timeout.connect(self._autosicherung_schreiben)

        self._baue_oberflaeche()
        self._baue_aktionen()
        self._baue_menue()
        self._baue_aktivitaet_dock()
        self._baue_navigator_dock()
        self._baue_verarbeitung_dock()
        self._baue_zonen_dock()
        self._baue_ausreisser_dock()
        self._baue_trace_dock()

        # Statusleiste: Job-Anzeige (immer sichtbar, solange etwas laeuft) und
        # dauerhafte Modus-Anzeige (rechts), sichtbar nur im Modus.
        self._baue_job_anzeige()
        self.modus_label = QtWidgets.QLabel("")
        self.modus_label.setObjectName("modus_anzeige")
        self.modus_label.setVisible(False)
        self.statusBar().addPermanentWidget(self.modus_label)

        # Esc bricht jeden Interaktionsmodus ab (bzw. verlaesst den Vollbildmodus)
        # - egal, welches Widget den Tastaturfokus hat.
        esc = QtGui.QShortcut(QtGui.QKeySequence("Escape"), self)
        esc.setContext(QtCore.Qt.WindowShortcut)
        esc.activated.connect(self._esc_gedrueckt)

        # Voreinstellungen (Anzeige, Verarbeitung) anwenden.
        self._einstellungen_anwenden(self._einstellungen, physik=False, melden=False)

        self.statusBar().showMessage("Bereit. Bitte eine TDMS-Datei laden (Strg+O).")
        self._log(f"{PROGRAMMNAME} bereit. Bitte eine TDMS-Datei laden.", "info")
        if self._einstellungen_geladen:
            self._log(f"Voreinstellungen geladen: {standard_pfad()}", "auto")
        if autosicherung_pfad().exists():
            self._log("Eine Auto-Sicherung des letzten Arbeitsstands ist vorhanden "
                      "(Datei → Auto-Sicherung wiederherstellen).", "info")

    # --- Aufbau ------------------------------------------------------------
    def _baue_oberflaeche(self):
        """Farbplot als Zentrum in voller Breite; das Linescan-Fit-Panel ist ein
        abdockbares Fenster, das mit dem ersten Fit (oder Klick in die Karte)
        erscheint (Multi-Monitor-Betrieb: Panel auf den zweiten Bildschirm ziehen)."""
        # Der Farbplot ist IMMER das groesste Element: garantierte Mindestbreite,
        # Docks muessen sich fuegen (siehe auch _dock_schmal_halten).
        self.matrix.setMinimumWidth(520)
        self.setCentralWidget(self.matrix)

        rechts = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(rechts)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        layout.addWidget(self.fitansicht, 1)

        # Bedienelemente in einem Raster (drei kurze Zeilen statt einer langen -
        # auf kleinen Bildschirmen wurden die Knoepfe sonst abgeschnitten).
        steuer = QtWidgets.QGridLayout()
        steuer.setHorizontalSpacing(6)
        steuer.setVerticalSpacing(4)
        self.btn_zurueck = QtWidgets.QPushButton("◀ Zurück")
        self.btn_weiter = QtWidgets.QPushButton("Weiter ▶")
        self.btn_naechstes_problem = QtWidgets.QPushButton("Problemfit ▶")
        self.btn_naechstes_problem.setToolTip("Zum nächsten gelb/rot markierten Fit springen.")
        self.btn_neu = QtWidgets.QPushButton("Neu fitten")
        self.btn_neu.setToolTip(
            "Diese Frequenz mit dem aktuellen Fenster neu fitten (mit der\n"
            "gewählten Anzahl Resonanzen). Gilt danach als vom Nutzer bestätigt.")
        self.spin_moden = RuhigeSpinBox()
        self.spin_moden.setRange(1, 6)
        self.spin_moden.setPrefix("Res.: ")
        self.spin_moden.setSuffix(" ×")
        self.spin_moden.setValue(max(1, int(self._physik.n_moden)))
        self.spin_moden.setToolTip(
            "Anzahl simultan gefitteter Resonanzen für 'Nochmal fitten' und\n"
            "das Grenzen-Ziehen (1 = Standard, 2 = Doppel-Dip).")
        self.btn_hauptmode = QtWidgets.QPushButton("Hauptmode ↻")
        self.btn_hauptmode.setToolTip(
            "Bei mehreren Resonanzen: die nächste Mode zur Hauptmode machen\n"
            "(B_res/ΔH/α für Kittel/LLG und Export).")
        self.btn_hauptmode.setToolTip(
            "Bei mehreren Resonanzen: die nächste Mode zur Hauptmode machen\n"
            "(B_res/ΔH/α für Kittel/LLG und Export).")
        self.btn_hauptmode.clicked.connect(self._hauptmode_wechseln)
        # Vollbereich-Umschalter direkt am Linescan-Panel (gespiegelt mit der
        # Menue-Aktion akt_vollbereich; Verbindung in _baue_aktionen).
        self.chk_vollbereich = QtWidgets.QCheckBox("ganzer Feldsweep")
        self.chk_vollbereich.setToolTip(
            "Ganzen Feldsweep zeigen statt aufs Resonanzband zu zoomen.")
        self.btn_zurueck.clicked.connect(lambda: self._navigiere(-1))
        self.btn_weiter.clicked.connect(lambda: self._navigiere(+1))
        self.btn_neu.clicked.connect(self._neu_fitten)
        self.btn_naechstes_problem.clicked.connect(self._naechster_problemfit)
        for b in (self.btn_zurueck, self.btn_weiter, self.btn_naechstes_problem, self.btn_neu,
                  self.btn_hauptmode, self.spin_moden):
            b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            b.setMinimumWidth(60)
        # Drei Spalten: passt auch bei 430 px Panelbreite ohne abgeschnittene Texte.
        steuer.addWidget(self.btn_zurueck, 0, 0)
        steuer.addWidget(self.btn_weiter, 0, 1)
        steuer.addWidget(self.btn_naechstes_problem, 0, 2)
        steuer.addWidget(self.btn_neu, 1, 0)
        steuer.addWidget(self.spin_moden, 1, 1)
        steuer.addWidget(self.btn_hauptmode, 1, 2)
        # Bewertungszeile: Status-Chip (Farbe wie im Farbplot) + Auswahlliste
        # (Strg+1/2/3, Strg+I).
        self.status_label = QtWidgets.QLabel("–")
        self.status_label.setObjectName("status_ignoriert")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setToolTip(
            "Wirksamer Status dieses Fits (Farbe/Form wie im Farbplot).")
        steuer.addWidget(self.status_label, 2, 0)
        self.bewertung_combo = QtWidgets.QComboBox()
        for text, art in (("gut bestätigen", "bestaetigt"),
                          ("problematisch", "verworfen"),
                          ("automatisch (Kriterien)", "auto"),
                          ("ignorieren (Ausreißer)", "ignorieren")):
            self.bewertung_combo.addItem(text, art)
        self.bewertung_combo.setToolTip(
            "Bewertung dieses Fits setzen: gut bestätigen (Strg+1), problematisch (Strg+2),\n"
            "automatisch nach Kriterien (Strg+3), ignorieren/wieder aufnehmen (Strg+I).")
        self.bewertung_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                           QtWidgets.QSizePolicy.Fixed)
        self._bewertung_blockiert = False
        self.bewertung_combo.activated.connect(self._bewertung_gewaehlt)
        steuer.addWidget(self.bewertung_combo, 2, 1, 1, 2)
        steuer.addWidget(self.chk_vollbereich, 3, 0, 1, 3)
        for spalte in range(3):
            steuer.setColumnStretch(spalte, 1)
        layout.addLayout(steuer)

        self.label_info = QtWidgets.QLabel("—")
        self.label_info.setWordWrap(True)
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
        rechts.setMinimumWidth(430)
        dock.setWidget(rechts)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        dock.setVisible(False)  # erscheint mit dem ersten Fit / Klick in die Karte
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
        """Legt alle Aktionen der Menueleiste einmalig an.

        Die Sichtbarkeits-Umschalter der Panels ohne bereits existierendes Dock
        werden hier nur angelegt; ihre Verbindung mit dem jeweiligen Dock
        erfolgt in den ``_baue_*_dock``-Methoden.
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
        self.akt_projekt_laden.triggered.connect(lambda: self._projekt_laden())
        self.akt_projekt_speichern = A("Projekt speichern …", self)
        self.akt_projekt_speichern.setShortcut(QtGui.QKeySequence.Save)   # Strg+S
        self.akt_projekt_speichern.setToolTip(
            "Sitzung als JSON sichern: Quelle, Kanal-Zuordnung, Auswahl, Fenster, "
            "Zonen, Grenzgeraden, Ausreißer, Bewertungen, Parameter und Verarbeitung "
            "(nie: Zoom oder Fensterlayout).")
        self.akt_projekt_speichern.triggered.connect(lambda: self._projekt_speichern())
        self.akt_autosicherung = A("Auto-Sicherung wiederherstellen …", self)
        self.akt_autosicherung.setToolTip(
            "Letzten automatisch gesicherten Arbeitsstand laden (wird 15 s nach "
            "jeder Änderung und beim Beenden geschrieben).")
        self.akt_autosicherung.triggered.connect(self._autosicherung_wiederherstellen)

        self.akt_alles_speichern = A("Alles speichern …", self)
        self.akt_alles_speichern.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        self.akt_alles_speichern.setToolTip(
            "Projekt, Excel/CSV, Kittel/LLG-Auswertung, Farbplot-Bild und -Matrix, "
            "TDMS und Einstellungen in einem Schritt in einen Ordner schreiben.")
        self.akt_alles_speichern.triggered.connect(self._alles_speichern)
        self.akt_tdms = A("Fitkurven als TDMS …", self)
        self.akt_tdms.setShortcut(QtGui.QKeySequence("Ctrl+Shift+T"))
        self.akt_tdms.triggered.connect(lambda: self._export_tdms())
        self.akt_xlsx = A("Einzelfits als Excel …", self)
        self.akt_xlsx.setShortcut(QtGui.QKeySequence("Ctrl+E"))
        self.akt_xlsx.setToolTip(
            "Alle Fitparameter (B_res und ΔH in T und mT, α, Amplitude/Phase, "
            "komplexe Amplitude, Offsets, Gütemaße, Status) + Kittel/LLG + Einstellungen.")
        self.akt_xlsx.triggered.connect(lambda: self._export_excel())
        self.akt_csv = A("Einzelfits als CSV (Listendaten) …", self)
        self.akt_csv.setShortcut(QtGui.QKeySequence("Ctrl+Shift+E"))
        self.akt_csv.triggered.connect(lambda: self._export_csv())
        self.akt_kittel_export = A("Kittel/LLG-Auswertung exportieren …", self)
        self.akt_kittel_export.setToolTip(
            "Physikalische Parameter mit Fehlern (T und mT) als Excel + CSV, Plot als PNG/PDF.")
        self.akt_kittel_export.triggered.connect(lambda: self._export_kittel())
        self.akt_farbplot_bild = A("Farbplot als Bild …", self)
        self.akt_farbplot_bild.setToolTip("Aktuelle Ansicht des Farbplots mit Overlays (PNG/PDF/SVG).")
        self.akt_farbplot_bild.triggered.connect(lambda: self._export_farbplot_bild())
        self.akt_matrix_csv = A("Farbplot-Matrix als CSV …", self)
        self.akt_matrix_csv.setToolTip(
            "Verarbeitete Matrix (nach Kette und Darstellung): Zeilen = Frequenzen, Spalten = Feld.")
        self.akt_matrix_csv.triggered.connect(lambda: self._export_matrix_csv())
        self.akt_spalten = A("Export-Spalten (Standard) …", self)
        self.akt_spalten.setToolTip(
            "Welche Spaltengruppen jeder Excel-/CSV-Export enthält; als Voreinstellung speicherbar.")
        self.akt_spalten.triggered.connect(self._spalten_dialog)

        self.akt_einst_speichern = A("Einstellungen speichern unter …", self)
        self.akt_einst_speichern.triggered.connect(self._einstellungen_speichern_unter)
        self.akt_einst_laden = A("Einstellungen laden …", self)
        self.akt_einst_laden.triggered.connect(self._einstellungen_laden)
        self.akt_einst_standard = A("Als Standard speichern (beim Start laden)", self)
        self.akt_einst_standard.setToolTip(f"Speichert nach {standard_pfad()}")
        self.akt_einst_standard.triggered.connect(self._einstellungen_als_standard)
        self.akt_einst_reset = A("Standardwerte wiederherstellen", self)
        self.akt_einst_reset.triggered.connect(self._einstellungen_zuruecksetzen)

        self.akt_beenden = A("Beenden", self)
        # QKeySequence.Quit ist unter Windows leer -> explizit Strg+Q.
        self.akt_beenden.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        self.akt_beenden.triggered.connect(self.close)

        # --- Bearbeiten (Rueckgaengig/Wiederholen) ---------------------------
        self.akt_rueckgaengig = A("Rückgängig", self)
        self.akt_rueckgaengig.setShortcut(QtGui.QKeySequence.Undo)        # Strg+Z
        self.akt_rueckgaengig.setToolTip(
            "Letzte Änderung zurücknehmen: Grenzgerade, Ausschlusszone, "
            "Ausreißer, Bewertung oder Nachfit (Strg+Z).")
        self.akt_rueckgaengig.setEnabled(False)
        self.akt_rueckgaengig.triggered.connect(self._rueckgaengig)
        self.akt_wiederholen = A("Wiederholen", self)
        self.akt_wiederholen.setShortcuts(
            [QtGui.QKeySequence.Redo, QtGui.QKeySequence("Ctrl+Y")])      # Strg+Umschalt+Z / Strg+Y
        self.akt_wiederholen.setToolTip(
            "Zurückgenommene Änderung wieder anwenden (Strg+Umschalt+Z oder Strg+Y).")
        self.akt_wiederholen.setEnabled(False)
        self.akt_wiederholen.triggered.connect(self._wiederholen)

        # --- Funktionen (interaktive Modi sind checkbar und EXKLUSIV) --------
        self.akt_fit = A("Auto-Fit (alle)", self)
        self.akt_fit.setShortcut(QtGui.QKeySequence("F5"))
        self.akt_fit.setToolTip(
            "Resonanz je Frequenz automatisch suchen und fitten (mit Dialog: "
            "Frequenz/Feld von … bis …, Jumper). Optional – Grenzgeraden und "
            "Bereichs-Fit funktionieren auch ohne.")
        self.akt_fit.triggered.connect(self._auto_fit)
        self.akt_bereich = A("Bereich neu fitten", self)
        self.akt_bereich.setShortcut(QtGui.QKeySequence("Ctrl+B"))
        self.akt_bereich.setCheckable(True)
        self.akt_bereich.setToolTip(
            "Modus: Rechteck im Farbplot aufziehen → nur dort werden Fenstersuche "
            "und Fit wiederholt (löst Mehrdeutigkeiten neben der Mode auf). "
            "Optionen (Frequenz/Feld von … bis …, Modus, Fensterbreite, Resonanzen) "
            "folgen im Dialog. Funktioniert auch ohne Auto-Fit. Esc bricht ab.")
        self.akt_bereich.toggled.connect(self._bereich_umschalten)
        self.akt_gerade = A("Grenzgerade einzeichnen", self)
        self.akt_gerade.setShortcut(QtGui.QKeySequence("Ctrl+L"))
        self.akt_gerade.setCheckable(True)
        self.akt_gerade.setToolTip(
            "Modus: zwei Punkte im Farbplot klicken → Gerade mit grüner (Fit-) und "
            "roter (Ignorier-)Seite; danach im Panel „Zonen & Grenzgeraden“ den "
            "grünen Bereich fitten. Funktioniert direkt nach dem Laden.")
        self.akt_gerade.toggled.connect(self._gerade_modus)
        self.akt_zone = A("Ausschlusszone einzeichnen", self)
        self.akt_zone.setCheckable(True)
        self.akt_zone.setToolTip(
            "Modus: Rechteck aufziehen → Messpunkte darin werden aus allen Fits ausgenommen.")
        self.akt_zone.toggled.connect(self._zone_modus)
        self.akt_ausreisser = A("Ausreißer markieren", self)
        self.akt_ausreisser.setShortcut(QtGui.QKeySequence("Ctrl+M"))
        self.akt_ausreisser.setCheckable(True)
        self.akt_ausreisser.setToolTip(
            "Modus: Fit-Punkte im Farbplot anklicken oder per Kasten markieren → "
            "ignoriert (grau): raus aus Darstellung und ALLEN Rechnungen (insb. Kittel-Fit). "
            "Reversibel: Rückgängig und Liste im Ausreißer-Panel. Esc beendet.")
        self.akt_ausreisser.toggled.connect(self._ausreisser_modus)
        self.akt_kittel = A("Kittel/LLG-Auswertung …", self)
        self.akt_kittel.setShortcut(QtGui.QKeySequence("Ctrl+K"))
        self.akt_kittel.setToolTip(
            "Eigenes Auswertungsfenster: Kittel- und LLG-Fit mit Feld auf der "
            "x-Achse, Punkte direkt im Plot entfernen, Export mit Fehlermaßen (T und mT).")
        self.akt_kittel.triggered.connect(self._kittel_llg)
        self.akt_physik = A("Physikalische Parameter …", self)
        self.akt_physik.setShortcut(QtGui.QKeySequence("Ctrl+P"))
        self.akt_physik.setToolTip(
            "g-Faktor/γ, Kittel-Geometrie, Fensterbreite-Faktor, R²-Schwellen, "
            "α-Grenzen, Resonanzen je Linescan und Nachfit-Bewertung einstellen "
            "(Konvention: µ₀H in Tesla, γ = g·µ_B/ħ; Müller 2023, Kap. 2).")
        self.akt_physik.triggered.connect(self._physik_dialog)

        # Bewertung des aktuellen Fits.
        self.akt_bew_gut = A("Aktuellen Fit als gut bestätigen", self)
        self.akt_bew_gut.setShortcut(QtGui.QKeySequence("Ctrl+1"))
        self.akt_bew_gut.triggered.connect(lambda: self._bewerte_aktuellen("bestaetigt"))
        self.akt_bew_problem = A("Aktuellen Fit als problematisch markieren", self)
        self.akt_bew_problem.setShortcut(QtGui.QKeySequence("Ctrl+2"))
        self.akt_bew_problem.triggered.connect(lambda: self._bewerte_aktuellen("verworfen"))
        self.akt_bew_auto = A("Aktuellen Fit automatisch bewerten (Kriterien)", self)
        self.akt_bew_auto.setShortcut(QtGui.QKeySequence("Ctrl+3"))
        self.akt_bew_auto.triggered.connect(lambda: self._bewerte_aktuellen("auto"))
        self.akt_bew_ignorieren = A("Aktuellen Fit ignorieren / wieder aufnehmen", self)
        self.akt_bew_ignorieren.setShortcut(QtGui.QKeySequence("Ctrl+I"))
        self.akt_bew_ignorieren.triggered.connect(lambda: self._bewerte_aktuellen("ignorieren"))
        self.akt_bew_alle_auto = A("Alle Bewertungen auf automatisch zurücksetzen", self)
        self.akt_bew_alle_auto.triggered.connect(self._alle_bewertungen_auto)

        # --- Ansicht --------------------------------------------------------
        self.akt_vollbild = A("Vollbild", self)
        self.akt_vollbild.setShortcut(QtGui.QKeySequence("F11"))
        self.akt_vollbild.setCheckable(True)
        self.akt_vollbild.setToolTip("Vollbildmodus ein-/ausschalten (F11; Esc verlässt ihn).")
        self.akt_vollbild.toggled.connect(self._vollbild_umschalten)
        self.akt_layout_reset = A("Fensterlayout zurücksetzen", self)
        self.akt_layout_reset.setShortcut(QtGui.QKeySequence("Ctrl+Shift+R"))
        self.akt_layout_reset.setToolTip(
            "Farbplot, Zoom und Panels auf den Auslieferungszustand bringen – "
            "ohne Daten oder Fits zu verlieren.")
        self.akt_layout_reset.triggered.connect(self._layout_zuruecksetzen)
        self.akt_vollbereich = A("Linescan: ganzer Feldsweep", self)
        self.akt_vollbereich.setCheckable(True)
        self.akt_vollbereich.setToolTip(
            "Im Linescan-Panel den ganzen Feldsweep zeigen statt aufs Resonanzband zu zoomen.")
        self.akt_vollbereich.toggled.connect(self._vollbereich_umschalten)
        # Checkbox im Linescan-Panel spiegelt die Aktion (beide Richtungen;
        # setChecked mit unveraendertem Wert loest kein toggled aus -> keine Schleife).
        self.chk_vollbereich.toggled.connect(self.akt_vollbereich.setChecked)
        self.akt_vollbereich.toggled.connect(self.chk_vollbereich.setChecked)
        self.akt_zoom = A("Zoom (Mausrad / Kästchen)", self)
        self.akt_zoom.setCheckable(True)
        self.akt_zoom.setChecked(False)
        self.akt_zoom.setToolTip(
            "Zoom in der Übersicht per Mausrad und aufgezogenem Kästchen ein-/ausschalten "
            "(Standard aus). Doppelklick setzt den Zoom zurück; Tasten +/-/0 wirken immer.")
        self.akt_zoom.toggled.connect(self.matrix.setze_zoom_aktiv)
        self.akt_problemfits = A("Problemfits ausblenden", self)
        self.akt_problemfits.setCheckable(True)
        self.akt_problemfits.setToolTip(
            "Problematische (gelb) und fehlgeschlagene (rot) Fits im Farbplot ausblenden.")
        self.akt_problemfits.toggled.connect(self._problemfits_umschalten)
        self.akt_ausreisser_anzeigen = A("Ignorierte Punkte (Ausreißer) grau anzeigen", self)
        self.akt_ausreisser_anzeigen.setCheckable(True)
        self.akt_ausreisser_anzeigen.toggled.connect(self.matrix.setze_ausreisser_anzeigen)
        self.akt_nebenmoden = A("Weitere Resonanzen (Nebenmoden) anzeigen", self)
        self.akt_nebenmoden.setCheckable(True)
        self.akt_nebenmoden.setChecked(True)
        self.akt_nebenmoden.toggled.connect(self.matrix.setze_nebenmoden_anzeigen)

        # Farbskala als Auswahlgruppe.
        self.farbskala_gruppe = QtGui.QActionGroup(self)
        self.farbskala_gruppe.setExclusive(True)
        self.akt_farbskalen: dict[str, QtGui.QAction] = {}
        for name, text in FARBSKALEN.items():
            akt = A(text, self)
            akt.setCheckable(True)
            akt.setData(name)
            akt.triggered.connect(lambda _c=False, n=name: self._farbskala_setzen(n))
            self.farbskala_gruppe.addAction(akt)
            self.akt_farbskalen[name] = akt
        self.akt_farbskalen["viridis"].setChecked(True)

        # Panel-Umschalter (Verbindung mit dem Dock in der jeweiligen _baue_*_dock-Methode).
        self.akt_verarbeitung = A("Panel: Verarbeitung", self)
        self.akt_verarbeitung.setToolTip(
            "Verarbeitung des Farbplots (divide-slice, derivative-divide, "
            "relation-amplitude, Farbskala) ein-/ausblenden – funktioniert direkt nach dem "
            "Laden, ganz ohne Fit.")
        self.akt_zonen_panel = A("Panel: Zonen && Grenzgeraden", self)
        self.akt_zonen_panel.setToolTip(
            "Fit-Werkzeuge ein-/ausblenden: Grenzgeraden (nur den grünen Bereich "
            "fitten) und Ausschlusszonen (Messpunkte aus allen Fits ausnehmen).")
        self.akt_linescan = A("Panel: Linescan-Fit", self)
        self.akt_linescan.setToolTip(
            "Linescan-Fit-Panel ein-/ausblenden (abdockbar für den zweiten Monitor).")
        self.akt_linescan.setCheckable(True)
        self.akt_linescan.setChecked(False)
        self.akt_linescan.toggled.connect(self.linescan_dock.setVisible)
        self.linescan_dock.visibilityChanged.connect(self.akt_linescan.setChecked)
        self.akt_ausreisser_panel = A("Panel: Ausreißer-Liste", self)
        self.akt_ausreisser_panel.setToolTip(
            "Liste der ignorierten Punkte ein-/ausblenden.")
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
        """EINE Leiste fuer alles: Menueleiste mit Programmname (links) und
        "TDMS laden"-Schnellzugriff (rechts) als Eckwidgets."""
        mb = self.menuBar()

        # Klickbarer Programmname (mit Version) ganz links -> oeffnet die Hilfe.
        self.btn_logo = QtWidgets.QToolButton()
        self.btn_logo.setText(f" {PROGRAMMNAME}")
        self.btn_logo.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.btn_logo.setAutoRaise(True)
        self.btn_logo.setToolTip("Bedienung & Infos")
        self.btn_logo.setStyleSheet(
            "font-weight: 600; font-size: 14px; padding: 2px 10px; border: none;")
        self.btn_logo.clicked.connect(self._zeige_hilfe)
        mb.setCornerWidget(self.btn_logo, QtCore.Qt.TopLeftCorner)

        m_datei = mb.addMenu("&Datei")
        m_datei.addAction(self.akt_laden)
        m_datei.addAction(self.akt_projekt_laden)
        m_datei.addAction(self.akt_projekt_speichern)
        m_datei.addAction(self.akt_autosicherung)
        m_datei.addSeparator()
        self.menue_speichern = m_datei.addMenu("&Speichern / Export")
        self.menue_speichern.addAction(self.akt_alles_speichern)
        self.menue_speichern.addSeparator()
        self.menue_speichern.addAction(self.akt_xlsx)
        self.menue_speichern.addAction(self.akt_csv)
        self.menue_speichern.addAction(self.akt_kittel_export)
        self.menue_speichern.addAction(self.akt_farbplot_bild)
        self.menue_speichern.addAction(self.akt_matrix_csv)
        self.menue_speichern.addAction(self.akt_tdms)
        self.menue_speichern.addSeparator()
        self.menue_speichern.addAction(self.akt_spalten)
        self.menue_einstellungen = m_datei.addMenu("&Einstellungen")
        self.menue_einstellungen.addAction(self.akt_physik)
        self.menue_einstellungen.addAction(self.akt_spalten)
        self.menue_einstellungen.addSeparator()
        self.menue_einstellungen.addAction(self.akt_einst_speichern)
        self.menue_einstellungen.addAction(self.akt_einst_laden)
        self.menue_einstellungen.addAction(self.akt_einst_standard)
        self.menue_einstellungen.addAction(self.akt_einst_reset)
        m_datei.addSeparator()
        m_datei.addAction(self.akt_beenden)

        m_bearbeiten = mb.addMenu("&Bearbeiten")
        m_bearbeiten.addAction(self.akt_rueckgaengig)
        m_bearbeiten.addAction(self.akt_wiederholen)

        self.funktionen_menue = mb.addMenu("Fun&ktionen")
        self.funktionen_menue.addAction(self.akt_fit)
        self.funktionen_menue.addAction(self.akt_bereich)
        self.funktionen_menue.addAction(self.akt_gerade)
        self.funktionen_menue.addAction(self.akt_zone)
        self.funktionen_menue.addSeparator()
        self.funktionen_menue.addAction(self.akt_ausreisser)
        self.menue_bewertung = self.funktionen_menue.addMenu("Be&wertung des aktuellen Fits")
        self.menue_bewertung.addAction(self.akt_bew_gut)
        self.menue_bewertung.addAction(self.akt_bew_problem)
        self.menue_bewertung.addAction(self.akt_bew_auto)
        self.menue_bewertung.addAction(self.akt_bew_ignorieren)
        self.menue_bewertung.addSeparator()
        self.menue_bewertung.addAction(self.akt_bew_alle_auto)
        self.funktionen_menue.addAction(self.akt_kittel)
        self.funktionen_menue.addSeparator()
        self.funktionen_menue.addAction(self.akt_physik)

        m_ansicht = mb.addMenu("&Ansicht")
        m_ansicht.addAction(self.akt_vollbild)
        m_ansicht.addAction(self.akt_layout_reset)
        m_ansicht.addSeparator()
        m_ansicht.addAction(self.akt_zoom)
        m_ansicht.addAction(self.akt_vollbereich)
        m_ansicht.addAction(self.akt_problemfits)
        m_ansicht.addAction(self.akt_ausreisser_anzeigen)
        m_ansicht.addAction(self.akt_nebenmoden)
        self.menue_farbskala = m_ansicht.addMenu("Farbskala des Farbplots")
        for akt in self.akt_farbskalen.values():
            self.menue_farbskala.addAction(akt)
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

        # Schnellzugriff "TDMS laden" ganz rechts in derselben Leiste.
        self.btn_laden = QtWidgets.QToolButton()
        self.btn_laden.setDefaultAction(self.akt_laden)
        self.btn_laden.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.btn_laden.setStyleSheet("padding: 3px 12px; font-weight: 600;")
        mb.setCornerWidget(self.btn_laden, QtCore.Qt.TopRightCorner)

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
        # Plattformgerechte Festbreitenschrift (unter Windows gibt es keine
        # Schriftfamilie "monospace").
        mono = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        mono.setPointSize(9)
        self.protokoll_ansicht.setFont(mono)
        lay.addWidget(self.protokoll_ansicht, 1)

        fuss = QtWidgets.QHBoxLayout()
        self.btn_abbrechen_dock = QtWidgets.QPushButton("Abbrechen")
        self.btn_abbrechen_dock.setObjectName("abbrechen")
        self.btn_abbrechen_dock.setToolTip(
            "Laufenden Auto-/Bereichs-/Grenzgeraden-Fit geordnet beenden; bisherige "
            "Ergebnisse bleiben erhalten.")
        self.btn_abbrechen_dock.clicked.connect(self._job_abbrechen)
        self.btn_abbrechen_dock.setVisible(False)
        fuss.addWidget(self.btn_abbrechen_dock)
        fuss.addStretch(1)
        leeren = QtWidgets.QPushButton("Protokoll leeren")
        leeren.clicked.connect(self.protokoll_ansicht.clear)
        fuss.addWidget(leeren)
        lay.addLayout(fuss)

        dock.setWidget(inhalt)
        dock.setMinimumWidth(300)
        # Unten andocken: nimmt dem Farbplot keine Breite weg. Erscheint
        # automatisch mit einem Hintergrund-Job und verschwindet danach wieder
        # (manuell jederzeit ueber Ansicht -> Panel: Aktivitaet).
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)
        dock.setVisible(False)
        self.aktivitaet_dock = dock
        self._aktivitaet_war_sichtbar = False
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
        """Verarbeitung (links): divide-slice, derivative-divide, relation-amplitude."""
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
        """Fit-Werkzeuge (links): Grenzgeraden und Ausschlusszonen."""
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
        # visibilityChanged(False), was die Menue-Toggles fehlleiten wuerde.
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        dock.setVisible(False)
        self.zonen_dock = dock
        self.akt_zonen_panel.setCheckable(True)
        self.akt_zonen_panel.setChecked(False)
        self.akt_zonen_panel.toggled.connect(dock.setVisible)
        dock.visibilityChanged.connect(self.akt_zonen_panel.setChecked)

    def _baue_ausreisser_dock(self):
        """Ausreisser-Liste (rechts); erscheint mit dem Markier-Modus."""
        dock = QtWidgets.QDockWidget("Ausreißer (ignoriert)", self)
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

    # --- Fenster: Vollbild, Layout, Esc, Schliessen ---------------------------
    def _vollbild_umschalten(self, an: bool) -> None:
        """F11: Vollbild ein/aus. Aus dem Vollbild zurueck erst showNormal(),
        dann showMaximized() - der direkte Wechsel klemmt unter Windows."""
        if an:
            if not self.isFullScreen():
                self.showFullScreen()
            self.statusBar().showMessage("Vollbild – F11 oder Esc beendet.", 5000)
        else:
            if self.isFullScreen():
                self.showNormal()
                self.showMaximized()

    def _esc_gedrueckt(self) -> None:
        if self.matrix.modus is not None:
            self.matrix.beende_modus()
        elif self.isFullScreen():
            self.akt_vollbild.setChecked(False)

    def _layout_zuruecksetzen(self) -> None:
        """Auslieferungslayout: Farbplot dominant, Zoom zurueck, Docks in Grundstellung."""
        self.matrix.layout_zuruecksetzen()
        for dock in (self.navigator_dock, self.zonen_dock, self.ausreisser_dock,
                     self.trace_dock, self.aktivitaet_dock):
            dock.setFloating(False)
            dock.setVisible(False)
        self.verarbeitung_dock.setFloating(False)
        self.linescan_dock.setFloating(False)
        if self.datensatz_voll is not None:
            self._dock_schmal_halten(self.verarbeitung_dock, breite=300)
        else:
            self.verarbeitung_dock.setVisible(False)
        if self.stapel is not None and self.stapel.index_gefittet():
            self._dock_schmal_halten(self.linescan_dock, breite=500)
            self._zeige_aktuellen()
        else:
            self.linescan_dock.setVisible(False)
        if not self.isFullScreen():
            self.showNormal()
            self.showMaximized()
        self._log("Fensterlayout zurückgesetzt.", "info")

    def closeEvent(self, event):  # noqa: N802 (Qt-Name)
        if self._job_laeuft:
            antwort = QtWidgets.QMessageBox.question(
                self, "Beenden", "Ein Hintergrundprozess läuft noch. Trotzdem beenden?")
            if antwort != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return
        self._autosicherung_timer.stop()
        self._autosicherung_schreiben()
        super().closeEvent(event)

    # --- Modus-Verwaltung (exklusiv, sichtbar, Esc bricht ab) ----------------
    def _auf_modus_geaendert(self, modus: str | None):
        """Vom Modus-Manager der Matrix gemeldet: Anzeige und Umschalter syncen."""
        for aktion, name in ((self.akt_bereich, "bereich"),
                             (self.akt_ausreisser, "ausreisser"),
                             (self.akt_gerade, "gerade"),
                             (self.akt_zone, "zone")):
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
            self._log("Es läuft ein Hintergrundprozess – Modus nicht gestartet.", "warn")
            return False
        if self.stapel is None or self.datensatz_voll is None:
            self._log("Modus nicht verfügbar: bitte zuerst eine TDMS-Datei laden.", "warn")
            self.statusBar().showMessage("Bitte zuerst eine TDMS-Datei laden.", 5000)
            return False
        if braucht_fits and not self.stapel.index_gefittet():
            self._log("Modus nicht verfügbar: es gibt noch keine Fit-Punkte "
                      "(Auto-Fit, Grenzgeraden- oder Bereichs-Fit ausführen).", "warn")
            self.statusBar().showMessage("Noch keine Fits vorhanden.", 5000)
            return False
        return True

    def _bereich_umschalten(self, an: bool):
        """Umschalter 'Bereich neu fitten' (Rechteck-Nachfitten; auch ohne Auto-Fit)."""
        if not an:
            if self.matrix.modus == "bereich":
                self.matrix.beende_modus()
            return
        if not (self._modus_start_erlaubt() and self._mapping_vorhanden()):
            self.akt_bereich.setChecked(False)
            return
        self._log("Bereich neu fitten: Rechteck um die Mode aufziehen "
                  "(Esc bricht ab).", "info")
        self.matrix.starte_bereichs_fit(self._bereich_gewaehlt)

    def _zone_modus(self, an: bool):
        """Umschalter des Zonen-Zeichenmodus (Panel oder Menue; auch ohne Auto-Fit)."""
        if not an:
            if self.matrix.modus == "zone":
                self.matrix.beende_modus()
            return
        if not self._modus_start_erlaubt():
            self.zonenpanel.setze_modus_aktiv(False)
            self.akt_zone.setChecked(False)
            return
        self._dock_schmal_halten(self.zonen_dock, breite=300)
        self._log("Ausschlusszone: Rechteck um die auszuschließenden Punkte "
                  "aufziehen (Esc bricht ab).", "info")
        self.matrix.starte_ausschluss_zeichnen(self._zone_gezeichnet)

    def _gerade_modus(self, an: bool):
        """Umschalter des Grenzgeraden-Zeichenmodus (zwei Klicks; auch ohne Auto-Fit)."""
        if not an:
            if self.matrix.modus == "gerade":
                self.matrix.beende_modus()
            return
        if not (self._modus_start_erlaubt() and self._mapping_vorhanden()):
            self.zonenpanel.setze_gerade_modus_aktiv(False)
            self.akt_gerade.setChecked(False)
            return
        self._dock_schmal_halten(self.zonen_dock, breite=300)
        self._log("Grenzgerade: zwei Punkte im Farbplot klicken – danach an den "
                  "Endpunkten ziehbar; Doppelklick auf die Linie wechselt die "
                  "grüne (Fit-)Seite. Esc bricht ab.", "info")
        self.matrix.starte_gerade_zeichnen(self._gerade_gezeichnet)

    def _gerade_gezeichnet(self, punkte):
        """Callback nach zwei Klicks: neue Grenzgerade anlegen und anzeigen."""
        (b1, f1_ghz), (b2, f2_ghz) = punkte
        vorher = self._geraden_schatten
        self._grenzgeraden.append(Grenzgerade(b1=float(b1), f1=f1_ghz * 1e9,
                                              b2=float(b2), f2=f2_ghz * 1e9,
                                              mode=self.zonenpanel.mode_neu()))
        self._zeige_geraden()
        self._merke_geraden_aenderung("Grenzgerade eingefügt", vorher)
        self._log(f"Grenzgerade eingefügt: ({b1:.3f} T, {f1_ghz:.2f} GHz) – "
                  f"({b2:.3f} T, {f2_ghz:.2f} GHz). Grüner Saum = wird "
                  f"gefittet; Seite per Doppelklick oder im Panel wechseln; "
                  f"dann „Grünen Bereich fitten …“.", "ok")

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
        """Endpunkt im Farbplot gezogen: Geometrie uebernehmen."""
        if not (0 <= index < len(self._grenzgeraden)):
            return
        vorher = self._geraden_schatten
        g = self._grenzgeraden[index]
        g.b1, g.f1, g.b2, g.f2 = float(b1), f1_ghz * 1e9, float(b2), f2_ghz * 1e9
        self.zonenpanel.setze_geraden(self._grenzgeraden)
        self._geraden_schatten = self._geraden_kopie()
        self._merke_geraden_aenderung("Grenzgerade verschoben", vorher)

    def _gerade_seite(self, index: int):
        """Gruene (Fit-)Seite der Geraden wechseln (Doppelklick/Panel)."""
        if not (0 <= index < len(self._grenzgeraden)):
            return
        vorher = self._geraden_schatten
        self._grenzgeraden[index].seite_wechseln()
        self._zeige_geraden()
        self._merke_geraden_aenderung("Grenzgerade: Seite gewechselt", vorher)
        self._log("Grenzgerade: Seiten getauscht (grün = wird gefittet).", "info")

    def _gerade_mode(self, index: int, mode: int):
        """Gerade einer anderen Mode zuordnen (n_moden > 1: je Mode ein Band)."""
        if not (0 <= index < len(self._grenzgeraden)):
            return
        vorher = self._geraden_schatten
        self._grenzgeraden[index].mode = max(1, int(mode))
        self._zeige_geraden()
        self._merke_geraden_aenderung("Grenzgerade: Mode geändert", vorher)
        self._log(f"Grenzgerade {index + 1} gehört jetzt zu Mode "
                  f"{self._grenzgeraden[index].mode}.", "info")

    def _gerade_entfernen(self, index: int):
        if not (0 <= index < len(self._grenzgeraden)):
            return
        vorher = self._geraden_schatten
        del self._grenzgeraden[index]
        self._zeige_geraden()
        self._merke_geraden_aenderung("Grenzgerade entfernt", vorher)
        self._log("Grenzgerade entfernt.", "info")

    def _daten_bereich(self) -> tuple[float, float, float, float]:
        """(feld_min, feld_max, f_min_ghz, f_max_ghz) des Stapel-Datensatzes."""
        ds = self.stapel.datensatz if self.stapel is not None else self.datensatz_voll
        b_min, b_max = ds.feld_bereich()
        f = ds.frequenzen
        return (b_min, b_max, float(f.min()) / 1e9 if f.size else 0.0,
                float(f.max()) / 1e9 if f.size else 1.0)

    def _geraden_bereich_vorgabe(self) -> tuple[tuple[float, float, float, float], bool]:
        """Vorbelegung ``(feld_min, feld_max, f_min_ghz, f_max_ghz)`` des
        Grenzgeraden-Dialogs: der zuletzt benutzte Bereich (an den Datenbereich
        geklemmt), sonst der ganze Datenbereich. Zweiter Wert: ``True``, wenn
        die Vorbelegung aus dem letzten Aufruf stammt."""
        b_min, b_max, f_min_ghz, f_max_ghz = self._daten_bereich()

        def _geklemmt(gemerkt, lo, hi):
            if gemerkt is None:
                return None
            a = min(max(float(gemerkt[0]), lo), hi)
            b = min(max(float(gemerkt[1]), lo), hi)
            return (a, b) if b > a else None

        feld = _geklemmt(self._bereich_feld, b_min, b_max)
        freq = _geklemmt(None if self._bereich_frequenz is None
                         else (self._bereich_frequenz[0] / 1e9, self._bereich_frequenz[1] / 1e9),
                         f_min_ghz, f_max_ghz)
        gemerkt = feld is not None or freq is not None
        feld = feld or (b_min, b_max)
        freq = freq or (f_min_ghz, f_max_ghz)
        return (feld[0], feld[1], freq[0], freq[1]), gemerkt

    def _geraden_fit(self):
        """Fitten des gruenen Bereichs aller Grenzgeraden (mit Optionen; auch ohne Auto-Fit)."""
        if self.stapel is None:
            self._log("Grenzgeraden-Fit: bitte zuerst eine TDMS-Datei laden.", "warn")
            return
        if not self._grenzgeraden:
            self._log("Grenzgeraden-Fit: bitte zuerst eine Gerade einzeichnen.", "warn")
            return
        if self._job_laeuft or not self._mapping_vorhanden():
            return
        stapel = self.stapel
        geraden = list(self._grenzgeraden)
        (b_von, b_bis, f_von_ghz, f_bis_ghz), gemerkt = self._geraden_bereich_vorgabe()
        dialog = BereichsFitDialog(
            b_von, b_bis, f_von_ghz, f_bis_ghz,
            modus_vorgabe=self._bereich_modus, breite_vorgabe=self._bereich_breite,
            titel="Grünen Bereich fitten",
            info_text=(f"{len(geraden)} Grenzgerade(n): Im GRÜNEN Bereich werden "
                       "Fenstersuche und Fit ausgeführt; die rote Seite bleibt "
                       "unangetastet. Frequenz-/Feldbereich unten grenzt zusätzlich ein"
                       + (" (vorbelegt: zuletzt benutzter Bereich)." if gemerkt else ".")),
            daten_bereich=self._daten_bereich(),
            n_moden=stapel.n_moden, parent=self)
        if not dialog.exec():
            self._log("Grenzgeraden-Fit abgebrochen.", "info")
            return
        modus = dialog.modus()
        breite = dialog.breite_punkte()
        f_von, f_bis = dialog.frequenz_bereich()
        b_von, b_bis = dialog.feld_bereich()
        self._bereich_modus, self._bereich_breite = modus, breite
        self._bereich_frequenz, self._bereich_feld = (f_von, f_bis), (b_von, b_bis)
        self._setze_n_moden(dialog.n_moden())
        if stapel.n_moden > 1 and any(g.mode > 1 for g in geraden):
            moden = sorted({min(g.mode, stapel.n_moden) for g in geraden})
            self._log(f"Grenzgeraden-Fit je Mode: Bänder für Mode {moden} "
                      f"(Moden ohne Geraden sind frei).", "info")
        # Undo-Schnappschuss ueber alle Fits (jede Frequenz kann betroffen sein).
        fits_vorher = self._fit_zustand(range(len(stapel.ergebnisse)))

        def aufgabe(melde):
            def fortschritt(k, n, erg):
                melde(k, n, self._fortschritt_text(k, n, erg),
                      daten=(erg.frequenz, erg.B_res, F.status_von(erg)), phase="Einzelfits")
            return fitte_geraden_bereich(stapel, geraden, modus=modus,
                                         breite_faktor=self._physik.breite_faktor,
                                         breite_punkte=breite,
                                         fortschritt=fortschritt,
                                         frequenz_min=f_von, frequenz_max=f_bis,
                                         feld_min=b_von, feld_max=b_bis,
                                         abbruch=melde.abgebrochen)

        def bei_fertig(res):
            neu, uebersprungen = res
            self._nach_nachfit(neu, fits_vorher, "Grenzgeraden-Fit")
            probleme = [i for i in neu if stapel.ergebnisse[i].problematisch]
            breite_text = f", Breite {breite} Punkte" if breite else ""
            text = (f"Grenzgeraden-Fit ({len(geraden)} Gerade(n), "
                    f"{f_von/1e9:.2f}–{f_bis/1e9:.2f} GHz{breite_text}): "
                    f"{len(neu)} gefittet, {len(probleme)} problematisch, "
                    f"{len(uebersprungen)} übersprungen (rote Seite/außerhalb/ohne Daten).")
            self._log(text, "warn" if probleme else "ok")
            self.statusBar().showMessage(text)

        self._starte_job(aufgabe, bei_fertig, "Grenzgeraden-Fit läuft …", live="ergaenzen")

    @staticmethod
    def _fortschritt_text(k, n, erg) -> str:
        if erg.problematisch:
            status = "⚠ " + erg.problem_text
        else:
            status = f"✓ B_res={erg.B_res:.3f} T, µ₀ΔH={erg.dH_mT:.2f} mT"
        return f"  {k}/{n}  f={erg.frequenz/1e9:6.2f} GHz  {status}"

    def _nach_nachfit(self, neu: list[int], fits_vorher: dict, beschreibung: str) -> None:
        """Gemeinsamer Abschluss von Bereichs-/Grenzgeraden-Fit."""
        stapel = self.stapel
        self._aktualisiere_overlay()
        if neu:
            self.aktueller_index = int(neu[0]) if self.aktueller_index not in neu else self.aktueller_index
            self._dock_schmal_halten(self.linescan_dock, breite=500)
            fits_nachher = self._fit_zustand(fits_vorher.keys())
            self._merke_aenderung(
                beschreibung,
                lambda: self._fit_zustand_setzen(fits_vorher),
                lambda: self._fit_zustand_setzen(fits_nachher))
        self._zeige_aktuellen()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()
        self._autosicherung_anstossen()

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
        """Registriert eine umkehrbare Aenderung (Schnappschuss-Closures)."""
        self._undo_stapel.append((beschreibung, vorher, nachher))
        del self._undo_stapel[:-50]
        self._redo_stapel.clear()
        self._aktualisiere_undo_aktionen()
        self._autosicherung_anstossen()

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
        self._autosicherung_anstossen()

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
        self._autosicherung_anstossen()

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
        self._zeige_aktuellen()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()

    # --- Aktivitaet / Protokoll -------------------------------------------
    def _log(self, text: str, art: str = "info") -> None:
        """Schreibt eine farbige, zeitgestempelte Protokollzeile (Auto-Scroll)."""
        farbe = _LOG_FARBEN.get(art, F.TEXT_GRAU)
        stempel = QtCore.QTime.currentTime().toString("HH:mm:ss")
        zeile = (f'<span style="color:{F.INAKTIV}">{stempel}</span> '
                 f'<span style="color:{farbe}">{html.escape(text)}</span>')
        self.protokoll_ansicht.appendHtml(zeile)
        leiste = self.protokoll_ansicht.verticalScrollBar()
        leiste.setValue(leiste.maximum())

    def _setze_aktivitaet(self, text: str) -> None:
        self.aktivitaet_label.setText(text)

    def _setze_bedienelemente(self, an: bool) -> None:
        """Sperrt/entsperrt Aktionen und Navigation waehrend eines Hintergrund-Jobs."""
        for aktion in (self.akt_laden, self.akt_fit, self.akt_bereich, self.akt_gerade,
                       self.akt_zone, self.akt_ausreisser, self.akt_kittel, self.akt_tdms,
                       self.akt_xlsx, self.akt_csv, self.akt_alles_speichern,
                       self.akt_kittel_export, self.akt_farbplot_bild, self.akt_matrix_csv,
                       self.akt_projekt_speichern, self.akt_projekt_laden,
                       self.akt_autosicherung, self.akt_bew_gut, self.akt_bew_problem,
                       self.akt_bew_auto, self.akt_bew_ignorieren, self.akt_bew_alle_auto,
                       self.akt_einst_laden, self.akt_einst_reset):
            aktion.setEnabled(an)
        for knopf in (self.btn_zurueck, self.btn_weiter, self.btn_neu,
                      self.btn_naechstes_problem, self.btn_hauptmode, self.bewertung_combo):
            knopf.setEnabled(an)

    # --- Job-Steuerung (Hintergrund-Thread) -------------------------------
    #: Spinner-Bilder der Statusleiste (Zeichen, die jede Systemschrift hat).
    _SPINNER = ("●○○", "○●○", "○○●", "○●○")

    def _baue_job_anzeige(self) -> None:
        """Dauerhafte Job-Anzeige in der Statusleiste: Spinner + Text + Balken + Abbrechen.

        Sichtbar nur, solange ein Hintergrund-Job laeuft - unabhaengig vom
        Aktivitaets-Panel, damit der Nutzer IMMER sieht, dass gearbeitet wird
        (Phase, Stand, verstrichene Zeit, Restzeit).
        """
        self.status_spinner = QtWidgets.QLabel("")
        self.status_spinner.setObjectName("job_spinner")
        self.status_job = QtWidgets.QLabel("")
        self.status_job.setObjectName("job_text")
        self.status_fortschritt = QtWidgets.QProgressBar()
        self.status_fortschritt.setFixedWidth(170)
        self.status_fortschritt.setRange(0, 100)
        self.status_fortschritt.setValue(0)
        self.status_fortschritt.setFormat("%p %")
        self.btn_abbrechen = QtWidgets.QPushButton("Abbrechen")
        self.btn_abbrechen.setObjectName("abbrechen")
        self.btn_abbrechen.setToolTip(
            "Laufenden Fit geordnet beenden – bisherige Ergebnisse bleiben erhalten.")
        self.btn_abbrechen.clicked.connect(self._job_abbrechen)
        for w in (self.status_spinner, self.status_job, self.status_fortschritt, self.btn_abbrechen):
            w.setVisible(False)
            self.statusBar().addPermanentWidget(w)
        self._spinner_timer = QtCore.QTimer(self)
        self._spinner_timer.setInterval(120)
        self._spinner_timer.timeout.connect(self._spinner_tick)
        self._spinner_index = 0
        self._busy_wert = 0
        self._job_start = 0.0
        self._phase_start = 0.0
        self._job_phase = ""
        self._job_i = 0
        self._job_n = 0
        self._job_abgebrochen = False
        self._hinweis_zuletzt = 0.0   # letzter Farbplot-Hinweis (Voll-Neuzeichnen!)
        # Live-Vorschau: Frequenz -> (B_res, Status); Zeichnen entprellt.
        self._live: dict[float, tuple[float, str]] = {}
        self._live_aktiv = False
        self._live_timer = QtCore.QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(300)
        self._live_timer.timeout.connect(self._live_zeichnen)

    def _starte_job(self, funktion, bei_fertig, titel: str,
                    abbrechbar: bool = True, live: str | None = None) -> None:
        """Fuehrt ``funktion(melde)`` im Hintergrund aus; ``bei_fertig(ergebnis)`` danach.

        ``abbrechbar``: Abbrechen-Knopf anbieten (der Job fragt ``melde.abgebrochen()``
        ab). ``live``: Live-Vorschau der Fit-Punkte im Farbplot – ``"neu"`` (Auto-Fit:
        Overlay beginnt leer) oder ``"ergaenzen"`` (Nachfit: bestehende Punkte bleiben).
        """
        if self._job_laeuft:
            self._log("Es läuft bereits ein Hintergrundprozess – bitte warten.", "warn")
            return
        # Kein Interaktionsmodus parallel zu einem Hintergrund-Job.
        self.matrix.beende_modus()
        self._job_laeuft = True
        self._job_titel = titel
        self._bei_fertig = bei_fertig
        self._job_abgebrochen = False
        self._job_start = self._phase_start = time.monotonic()
        self._job_phase = ""
        self._job_i = self._job_n = 0
        self._setze_bedienelemente(False)
        self._setze_aktivitaet(titel)
        self._log(titel, "info")
        # SOFORT sichtbare Rueckmeldung: Wartecursor, Statusleiste, Banner im Farbplot.
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.BusyCursor)
        self.status_spinner.setVisible(True)
        self.status_job.setText(titel)
        self.status_job.setVisible(True)
        self.status_fortschritt.setValue(0)
        self.status_fortschritt.setFormat("…")
        self.status_fortschritt.setVisible(True)
        self.btn_abbrechen.setVisible(bool(abbrechbar))
        self.btn_abbrechen.setEnabled(True)
        self.btn_abbrechen_dock.setVisible(bool(abbrechbar))
        self.btn_abbrechen_dock.setEnabled(True)
        self._spinner_timer.start()
        self.matrix.zeige_hinweis(f"{titel}")
        self.statusBar().showMessage(f"{titel} – das Programm arbeitet, die Anzeige "
                                     "aktualisiert sich laufend.")
        # Live-Vorschau vorbereiten.
        self._live_aktiv = live is not None
        self._live = {}
        if live == "ergaenzen" and self.stapel is not None:
            for i, e in enumerate(self.stapel.ergebnisse):
                if e.gefittet and np.isfinite(e.B_res):
                    self._live[float(e.frequenz)] = (
                        float(e.B_res), F.status_von(e, ignoriert=self.stapel.ist_ausreisser(i)))
        elif live == "neu":
            self.matrix.aktualisiere_resonanz(np.array([]), np.array([]))
        # Aktivitaet nur fuer die Dauer des Jobs einblenden (unten, flach) -
        # war sie schon offen (manuell), bleibt sie es auch danach.
        self._aktivitaet_war_sichtbar = self.aktivitaet_dock.isVisible()
        self._dock_schmal_halten(self.aktivitaet_dock, hoehe=210)
        self.fortschritt_balken.setRange(0, 100)
        self.fortschritt_balken.setValue(0)
        QtWidgets.QApplication.processEvents()  # Anzeige zeichnen, BEVOR gerechnet wird

        self._thread = QtCore.QThread(self)
        self._arbeiter = Arbeiter(funktion)
        self._arbeiter.moveToThread(self._thread)
        self._thread.started.connect(self._arbeiter.ausfuehren)
        # WICHTIG: an gebundene Methoden des (Haupt-Thread-)Fensters binden, NICHT an
        # Lambdas – nur so erkennt Qt die Thread-Zugehoerigkeit und stellt die Slots
        # via QueuedConnection im GUI-Thread zu.
        self._arbeiter.fortschritt.connect(self._auf_fortschritt)
        self._arbeiter.protokoll.connect(self._auf_protokoll)
        self._arbeiter.zwischenstand.connect(self._auf_zwischenstand)
        self._arbeiter.phase.connect(self._auf_phase)
        self._arbeiter.fehler.connect(self._auf_fehler)
        self._arbeiter.fertig.connect(self._auf_fertig)
        self._thread.start()

    def _job_abbrechen(self) -> None:
        """Abbruch anfordern; der laufende Job beendet sich nach dem aktuellen Schritt."""
        if not self._job_laeuft or self._arbeiter is None:
            return
        self._arbeiter.abbrechen()
        self._job_abgebrochen = True
        self.btn_abbrechen.setEnabled(False)
        self.btn_abbrechen_dock.setEnabled(False)
        self.status_job.setText(f"{self._job_titel}  – Abbruch angefordert, beende …")
        self.matrix.zeige_hinweis(f"{self._job_titel}\nAbbruch angefordert – bisherige Ergebnisse bleiben")
        self._log("Abbruch angefordert – der laufende Schritt wird noch beendet, "
                  "bisherige Ergebnisse bleiben erhalten.", "warn")

    def _spinner_tick(self) -> None:
        self._spinner_index = (self._spinner_index + 1) % len(self._SPINNER)
        self.status_spinner.setText(self._SPINNER[self._spinner_index])
        if self._job_n <= 0:
            # Unbestimmter Fortschritt: wandernder Balken (funktioniert auch dort,
            # wo Qt den "busy"-Modus mit Stylesheet nicht animiert, z. B. Windows).
            self._busy_wert = (self._busy_wert + 5) % 101
            self.status_fortschritt.setValue(self._busy_wert)
            self.fortschritt_balken.setValue(self._busy_wert)
            sekunden = time.monotonic() - self._job_start
            self.status_job.setText(f"{self._job_titel}  {sekunden:.0f} s")

    def _auf_phase(self, phase: str) -> None:
        self._job_phase = phase
        self._phase_start = time.monotonic()
        self._job_i = self._job_n = 0
        self._log(f"  Phase: {phase}", "auto")

    def _auf_fortschritt(self, i: int, n: int) -> None:
        self._job_i, self._job_n = int(i), int(n)
        if n <= 0:
            self.status_fortschritt.setFormat("…")
            return
        prozent = int(round(100.0 * i / n))
        self.fortschritt_balken.setRange(0, n)
        self.fortschritt_balken.setValue(i)
        self.status_fortschritt.setFormat("%p %")
        self.status_fortschritt.setValue(prozent)
        verstrichen = time.monotonic() - self._job_start
        phase_zeit = time.monotonic() - self._phase_start
        rest = f" · noch ≈ {phase_zeit / i * (n - i):.0f} s" if i > 0 and i < n else ""
        phase = f" {self._job_phase}" if self._job_phase else ""
        text = f"{self._job_titel}{phase}: {i}/{n} ({prozent} %) · {verstrichen:.0f} s{rest}"
        self.status_job.setText(text)
        self._setze_aktivitaet(text)
        # Der Hinweis im Farbplot zeichnet den ganzen Plot neu - hoechstens 4x/s
        # (Statusleiste/Aktivitaet oben sind billig und laufen ungedrosselt).
        jetzt = time.monotonic()
        if not self._job_abgebrochen and (i >= n or jetzt - self._hinweis_zuletzt >= 0.25):
            self._hinweis_zuletzt = jetzt
            self.matrix.zeige_hinweis(f"{self._job_titel}{phase}: {i}/{n}{rest}")

    def _auf_protokoll(self, text: str) -> None:
        art = "warn" if "⚠" in text else ("ok" if "✓" in text else "auto")
        self._log(text, art)

    def _auf_zwischenstand(self, daten) -> None:
        """Fertiger Einzelfit aus dem Worker: fuer die Live-Vorschau vormerken."""
        if not self._live_aktiv:
            return
        try:
            frequenz, b_res, status = daten
        except (TypeError, ValueError):
            return
        if b_res is not None and np.isfinite(b_res):
            self._live[float(frequenz)] = (float(b_res), str(status))
        elif float(frequenz) in self._live:
            del self._live[float(frequenz)]
        if not self._live_timer.isActive():
            self._live_timer.start()

    def _live_zeichnen(self) -> None:
        """Live-Vorschau der bisher gefitteten Punkte im Farbplot (entprellt)."""
        if not self._live_aktiv or self.datensatz_voll is None:
            return
        if not self._live:
            return
        frequenzen = np.array(sorted(self._live), dtype=float)
        bres = np.array([self._live[f][0] for f in frequenzen], dtype=float)
        status = [self._live[f][1] for f in frequenzen]
        problem = np.array([st_ in ("problem", "fehler") for st_ in status], dtype=bool)
        ausgeschlossen = np.array([st_ == "ignoriert" for st_ in status], dtype=bool)
        self.matrix.aktualisiere_resonanz(frequenzen, bres, problem, ausgeschlossen, status=status)

    def _job_anzeige_beenden(self) -> None:
        """Sichtbare Job-Rueckmeldung zuruecknehmen (vor bei_fertig - das darf Dialoge oeffnen)."""
        self._spinner_timer.stop()
        self._live_timer.stop()
        self._live_aktiv = False
        self._live = {}
        while QtWidgets.QApplication.overrideCursor() is not None:
            QtWidgets.QApplication.restoreOverrideCursor()
        for w in (self.status_spinner, self.status_job, self.status_fortschritt,
                  self.btn_abbrechen):
            w.setVisible(False)
        self.btn_abbrechen_dock.setVisible(False)
        self.matrix.zeige_hinweis(None)

    def _auf_fertig(self, ergebnis) -> None:
        bei_fertig = self._bei_fertig
        self._job_anzeige_beenden()
        try:
            if bei_fertig is not None:
                bei_fertig(ergebnis)
        finally:
            self._bei_fertig = None
            self._job_aufraeumen()

    def _auf_fehler(self, text: str) -> None:
        self._job_anzeige_beenden()
        erste = text.splitlines()[0] if text else "Unbekannter Fehler"
        self._log("FEHLER: " + erste, "problem")
        QtWidgets.QMessageBox.critical(self, "Fehler", text)
        self._job_aufraeumen()

    def _job_aufraeumen(self) -> None:
        self._job_anzeige_beenden()
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

    @contextmanager
    def _beschaeftigt(self, text: str):
        """Kurze synchrone Arbeiten (Export, Speichern): Wartecursor + Statusmeldung."""
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.status_job.setText(text)
        self.status_job.setVisible(True)
        self.statusBar().showMessage(text)
        QtWidgets.QApplication.processEvents()
        try:
            yield
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            if not self._job_laeuft:
                self.status_job.setVisible(False)

    # --- Laden ---------------------------------------------------------------
    def _laden(self):
        if self._job_laeuft:
            return
        pfad, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "TDMS-Datei laden", self._letzter_ordner, "TDMS (*.tdms)")
        if not pfad:
            return
        self._letzter_ordner = os.path.dirname(pfad)
        self._lade_mit_mapping(pfad)

    def _lade_mit_mapping(self, pfad: str,
                          zuordnung_vorgabe: dict | None = None,
                          layout_vorgabe: str | None = None):
        """Lade-Ablauf: Struktur inspizieren -> Zuordnungs-Dialog -> Laden im
        Hintergrund -> Validierungs-Vorschau -> erst dann Uebernahme."""
        try:
            struktur, warnungen = inspiziere_tdms(pfad)
        except Exception as fehler:
            self._log(f"FEHLER beim Inspizieren: {fehler}", "problem")
            QtWidgets.QMessageBox.critical(self, "TDMS laden", str(fehler))
            return
        for warnung in warnungen:
            self._log("⚠ " + warnung, "warn")

        profile = list(EINGEBAUTE_PROFILE) + lade_profile()
        vorschlag = finde_profil(struktur, profile)
        dialog = MappingDialog(pfad, struktur, profile, vorschlag, parent=self)
        if zuordnung_vorgabe is not None:
            dialog._setze_zuordnung(zuordnung_vorgabe, layout_vorgabe)
        if not dialog.exec():
            self._log("Laden abgebrochen (Zuordnung nicht bestätigt).", "info")
            return
        zuordnung, layout = dialog.ergebnis()

        def aufgabe(melde):
            melde(0, 0, f"Lade {os.path.basename(pfad)} … (große Dateien brauchen "
                        "bis zu einer Minute)", phase="TDMS lesen")
            datensatz = lade_tdms(pfad, zuordnung=zuordnung, layout=layout)
            melde(0, 0, f"Prüfe Datensatz ({len(datensatz)} Frequenzen) …", phase="Prüfen")
            bericht = pruefe_datensatz(datensatz)
            return (pfad, datensatz, bericht)

        def bei_fertig(res):
            pfad_, datensatz, bericht = res
            for warnung in datensatz.meta.get("lade_warnungen", []):
                self._log("⚠ " + warnung, "warn")
            vorschau = VorschauDialog(datensatz, bericht, parent=self)
            if not vorschau.exec():
                self._log("Import verworfen – Zuordnung erneut bearbeiten.", "info")
                self._lade_mit_mapping(pfad_, zuordnung, datensatz.format_typ)
                return
            if bericht.warnungen:
                for warnung in bericht.warnungen:
                    self._log("⚠ Validierung: " + warnung, "warn")
            self._datensatz_uebernehmen(datensatz)
            self._log(
                f"Geladen: {os.path.basename(pfad_)} – {datensatz.format_typ}, "
                f"{len(datensatz)} Frequenzen (Profil: "
                f"{datensatz.meta.get('mapping_profil', 'manuell')}).", "ok")
            self.statusBar().showMessage(
                f"Geladen: {os.path.basename(pfad_)} ({datensatz.format_typ}, "
                f"{len(datensatz)} Frequenzen). Daten ansehen (Verarbeitung), "
                f"Grenzgeraden/Bereich fitten oder Auto-Fit starten.")

        self._starte_job(aufgabe, bei_fertig, f"Lade {os.path.basename(pfad)} …",
                         abbrechbar=False)

    def _datensatz_uebernehmen(self, datensatz) -> None:
        """Neuer Datensatz: Farbplot fuellen, leeren Stapel anlegen, Werkzeuge freigeben."""
        self.matrix.zeige(datensatz)
        feld_achse, freq_achse = self.matrix.achsen()
        self.verarbeitung.setze_achsen(feld_achse, freq_achse)
        self.matrix.setze_verarbeitung(self.verarbeitung.kette(),
                                       self.verarbeitung.anzeige_modus())
        mat, ext = self.matrix.thumbnail()
        self.navigator.zeige(mat, ext)
        self.navigator_dock.setVisible(False)  # erst beim Zoomen einblenden
        self.datensatz_voll = datensatz
        self.stapel = self._leerer_stapel(datensatz)
        self.aktueller_index = 0
        self.zonenpanel.setze_zonen([])
        self._grenzgeraden = []
        self._geraden_schatten = []
        self.zonenpanel.setze_geraden([])
        self._bereich_frequenz = self._bereich_feld = None  # datensatzbezogen
        self._undo_verwerfen()  # alte Zustaende gehoeren zum alten Datensatz
        self.linescan_dock.setVisible(False)
        self._aktualisiere_overlay()
        # Datenansicht sofort ermoeglichen: Verarbeitungs-Panel einblenden.
        self._dock_schmal_halten(self.verarbeitung_dock, breite=300)
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()

    def _leerer_stapel(self, datensatz) -> StapelErgebnis:
        p = self._physik
        return leerer_stapel(datensatz, gamma=p.gamma, r2_schwelle=p.r2_schwelle,
                             alpha_max=p.alpha_max, nachfenster_faktor=p.nachfenster_faktor,
                             alpha_plausibel=p.alpha_plausibel_wirksam, n_moden=p.n_moden,
                             nachfit_bestaetigen=p.nachfit_bestaetigen)

    def _mapping_vorhanden(self) -> bool:
        """Kein Fit auf ungemappten Daten: Zuordnung muss in den Metadaten stehen."""
        if self.stapel is not None and self.stapel.datensatz.meta.get("zuordnung"):
            return True
        QtWidgets.QMessageBox.information(
            self, "Hinweis",
            "Der Datensatz hat keine Kanal-Zuordnung. Bitte die TDMS-Datei über "
            "'TDMS laden' öffnen und die Kanäle den Rollen zuordnen.")
        return False

    def _frage_auswahl(self) -> Auswertungsauswahl | None:
        """Zeigt vor der Auswertung den Jumper-/Bereichs-Dialog (Frequenz/Feld von … bis …)."""
        dialog = AuswahlDialog(self.datensatz_voll, self._letzte_auswahl, parent=self,
                               n_moden=self._physik.n_moden,
                               zweistufig=self._physik.auto_fit_zweistufig)
        if not dialog.exec():
            return None
        auswahl = dialog.auswahl()
        self._letzte_auswahl = auswahl
        self._setze_n_moden(dialog.n_moden())
        if dialog.zweistufig() != self._physik.auto_fit_zweistufig:
            self._physik = replace(self._physik, auto_fit_zweistufig=dialog.zweistufig())
            self._einstellungen.physik = self._physik.als_dict()
        if dialog.n_moden() > 1:
            self._log(f"Auto-Fit mit {dialog.n_moden()} Resonanzen je Linescan"
                      + (" – zweistufig (erst klassisch, dann Moden ergänzen)."
                         if dialog.zweistufig() else " (simultan)."), "info")
        if not auswahl.ist_neutral:
            self._log("Auswertungsauswahl: "
                      + auswahl.beschreibung(self.datensatz_voll), "info")
        return auswahl

    # --- Physikalische Parameter --------------------------------------------
    def _physik_dialog(self):
        """Dialog fuer die einstellbaren physikalischen Parameter (Strg+P)."""
        dialog = ParameterDialog(self._physik, parent=self)
        if not dialog.exec():
            return
        self._physik_uebernehmen(dialog.parameter())

    def _physik_uebernehmen(self, parameter: PhysikParameter, leise: bool = False) -> None:
        """Setzt neue Parameter und rechnet die Kittel/LLG-Auswertung neu."""
        self._physik = parameter
        self._einstellungen.physik = parameter.als_dict()
        self.spin_moden.blockSignals(True)
        self.spin_moden.setValue(max(1, int(parameter.n_moden)))
        self.spin_moden.blockSignals(False)
        if not leise:
            self._log("Physikalische Parameter: " + parameter.beschreibung(), "ok")
        if self.stapel is not None:
            # Wirkt sofort auf alle NACHfits (fitte_neu nutzt den Stapel);
            # bestehende Ergebnisse bleiben, bis neu gefittet wird.
            st = self.stapel
            st.gamma = parameter.gamma
            st.r2_schwelle = parameter.r2_schwelle
            st.alpha_max = parameter.alpha_max
            st.alpha_plausibel = parameter.alpha_plausibel_wirksam
            st.nachfenster_faktor = parameter.nachfenster_faktor
            st.n_moden = max(1, int(parameter.n_moden))
            st.nachfit_bestaetigen = parameter.nachfit_bestaetigen
            if not leise and st.index_gefittet():
                self._log("Hinweis: bestehende Einzelfits bleiben unverändert – "
                          "neue Parameter wirken ab dem nächsten (Auto-/Nach-)Fit; "
                          "die Kittel/LLG-Auswertung rechnet sofort neu.", "info")
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()
        self._autosicherung_anstossen()

    def _setze_n_moden(self, n: int) -> None:
        """Modenanzahl aus einem Dialog uebernehmen (Stapel + Parameter + Spin)."""
        n = max(1, int(n))
        if n != self._physik.n_moden:
            self._physik = replace(self._physik, n_moden=n)
            self._einstellungen.physik = self._physik.als_dict()
            self._log(f"Resonanzen je Linescan: {n}.", "info")
        if self.stapel is not None:
            self.stapel.n_moden = n
        self.spin_moden.blockSignals(True)
        self.spin_moden.setValue(n)
        self.spin_moden.blockSignals(False)
        self.zonenpanel.setze_n_moden(n)

    # --- Auto-Fit --------------------------------------------------------------
    def _nach_autofit(self, stapel: StapelErgebnis) -> None:
        """Gemeinsamer Abschluss des Auto-Fits."""
        self.stapel = stapel
        self._undo_verwerfen()  # Undo-Stapel gehoert zum alten Stapel
        self._aktualisiere_overlay()
        # Neuer Stapel: Ausschlusszonen beginnen leer.
        self.zonenpanel.setze_zonen(stapel.ausschlusszonen)
        self.matrix.zeige_ausschlusszonen(stapel.ausschlusszonen)
        self.aktueller_index = 0
        # Fuer den Korrekturlauf: NUR das Linescan-Panel einblenden (schmal
        # geklemmt, der Farbplot bleibt das groesste Element).
        self._dock_schmal_halten(self.linescan_dock, breite=500)
        self._zeige_aktuellen()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()
        self._autosicherung_anstossen()

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
        physik = self._physik

        def aufgabe(melde):
            n = len(datensatz.linescans)
            schritt = max(1, n // 50)  # ~50 Protokollzeilen + alle Problemfits

            def fortschritt_fenster(k, total):
                melde(k, total, "", phase="Fenstersuche")

            def fortschritt(i, total, erg):
                zeige = (i == 0) or (i + 1 == total) or ((i + 1) % schritt == 0) or erg.problematisch
                melde(i + 1, total, self._fortschritt_text(i + 1, total, erg) if zeige else "",
                      daten=(erg.frequenz, erg.B_res, F.status_von(erg)), phase="Einzelfits")

            def fortschritt_moden(i, total, erg):
                zeige = (i == 0) or (i + 1 == total) or ((i + 1) % schritt == 0)
                n_m = len(erg.moden) if erg.moden else 1
                melde(i + 1, total,
                      f"  {i + 1}/{total}  f={erg.frequenz / 1e9:6.2f} GHz  {n_m} Resonanz(en)"
                      if zeige else "",
                      daten=(erg.frequenz, erg.B_res, F.status_von(erg)), phase="Moden ergänzen")

            return fitte_alle(datensatz, gamma=physik.gamma,
                              breite_faktor=physik.breite_faktor,
                              r2_schwelle=physik.r2_schwelle,
                              fortschritt=fortschritt, auswahl=auswahl,
                              alpha_erwartet=physik.alpha_erwartet,
                              alpha_max=physik.alpha_max,
                              nachfenster_faktor=physik.nachfenster_faktor,
                              alpha_plausibel=physik.alpha_plausibel_wirksam,
                              n_moden=physik.n_moden,
                              nachfit_bestaetigen=physik.nachfit_bestaetigen,
                              fortschritt_fenster=fortschritt_fenster,
                              abbruch=melde.abgebrochen,
                              zweistufig=physik.auto_fit_zweistufig,
                              fortschritt_moden=fortschritt_moden)

        def bei_fertig(stapel):
            self._nach_autofit(stapel)
            n_fit = len(stapel.index_gefittet())
            n_prob = len(stapel.index_problematisch())
            art = "ok" if n_prob == 0 else "warn"
            if stapel.zweistufig:
                n_mehr = sum(1 for e in stapel.ergebnisse if e.moden and len(e.moden) > 1)
                self._log(f"Zweistufig: bei {n_mehr} von {n_fit} Linescans weitere Resonanzen "
                          f"ergänzt (Rest: klassisches Ergebnis).", "info")
            if n_fit < len(stapel.ergebnisse):
                self._log(f"Auto-Fit abgebrochen: {n_fit} von {len(stapel.ergebnisse)} "
                          f"Frequenzen gefittet, {n_prob} problematisch – der Rest bleibt "
                          "„nicht gefittet“ (Grenzgeraden/Bereich fitten den Rest bei Bedarf).", "warn")
            else:
                self._log(f"Auto-Fit fertig: {n_fit} Fits, {n_prob} problematisch.", art)
            for grund, anzahl in stapel.problem_statistik().items():
                self._log(f"   • {grund}: {anzahl}", "warn")
            self.statusBar().showMessage(
                f"Auto-Fit {'abgebrochen' if n_fit < len(stapel.ergebnisse) else 'fertig'}. "
                f"{n_fit} Fits, {n_prob} problematisch.")

        self._starte_job(aufgabe, bei_fertig, "Auto-Fit läuft …", live="neu")

    def _bereich_gewaehlt(self, feld_min, feld_max, f_min_ghz, f_max_ghz):
        """Callback nach dem Aufziehen: Optionen abfragen, dann im Bereich neu fitten."""
        stapel = self.stapel
        if stapel is None:
            return
        dialog = BereichsFitDialog(feld_min, feld_max, f_min_ghz, f_max_ghz,
                                   modus_vorgabe=self._bereich_modus,
                                   breite_vorgabe=self._bereich_breite,
                                   daten_bereich=self._daten_bereich(),
                                   n_moden=stapel.n_moden, parent=self)
        if not dialog.exec():
            self._log("Bereichs-Fit abgebrochen.", "info")
            return
        modus = dialog.modus()
        breite = dialog.breite_punkte()
        f_min, f_max = dialog.frequenz_bereich()
        feld_min, feld_max = dialog.feld_bereich()
        self._bereich_modus, self._bereich_breite = modus, breite
        self._setze_n_moden(dialog.n_moden())
        betroffen_vorab = [int(i) for i in np.flatnonzero(
            (stapel.datensatz.frequenzen >= f_min)
            & (stapel.datensatz.frequenzen <= f_max))]
        fits_vorher = self._fit_zustand(betroffen_vorab)

        def aufgabe(melde):
            def fortschritt(k, n, erg):
                melde(k, n, self._fortschritt_text(k, n, erg),
                      daten=(erg.frequenz, erg.B_res, F.status_von(erg)), phase="Einzelfits")
            return fitte_bereich(stapel, feld_min, feld_max, f_min, f_max,
                                 breite_faktor=self._physik.breite_faktor,
                                 modus=modus, breite_punkte=breite,
                                 fortschritt=fortschritt, abbruch=melde.abgebrochen)

        def bei_fertig(res):
            neu, uebersprungen = res
            self._nach_nachfit(neu, fits_vorher, "Bereichs-Fit")
            probleme = [i for i in neu if stapel.ergebnisse[i].problematisch]
            breite_text = f", Breite {breite} Punkte" if breite else ""
            text = (f"Bereichs-Fit [{feld_min:.3f}–{feld_max:.3f} T, "
                    f"{f_min/1e9:.2f}–{f_max/1e9:.2f} GHz{breite_text}]: "
                    f"{len(neu)} gefittet, {len(probleme)} problematisch, "
                    f"{len(uebersprungen)} übersprungen (ohne Daten/Modus 'ergänzen').")
            self._log(text, "warn" if probleme else "ok")
            self.statusBar().showMessage(text)

        self._starte_job(aufgabe, bei_fertig,
                         f"Bereichs-Fit {f_min/1e9:.1f}–{f_max/1e9:.1f} GHz …", live="ergaenzen")

    # --- Overlay / Anzeige ---------------------------------------------------
    def _status_liste(self) -> list[str]:
        st = self.stapel
        return [F.status_von(e, ignoriert=st.ist_ausreisser(i))
                for i, e in enumerate(st.ergebnisse)]

    def _tooltip_text(self, i: int, status: str) -> str:
        e = self.stapel.ergebnisse[i]
        if not e.gefittet:
            return f"f = {e.frequenz/1e9:.3f} GHz – nicht gefittet"
        zeilen = [f"<b>f = {e.frequenz/1e9:.3f} GHz</b>",
                  f"B_res = {e.B_res:.4f} T ({e.B_res_mT:.1f} mT)",
                  f"µ₀ΔH = {e.dH_mT:.2f} mT &nbsp; α = {e.alpha:.2e}",
                  f"R² = {e.R2:.4f}",
                  f"Status: {F.STATUS_TEXTE.get(status, status)}"]
        if e.problem_gruende and status not in ("gut", "bestaetigt"):
            zeilen.append("Gründe: " + ", ".join(e.problem_gruende))
        if e.n_moden > 1:
            weitere = ", ".join(f"{m['B_res']:.4f} T / {m['dH']*1e3:.1f} mT" for m in e.moden[1:])
            zeilen.append(f"{e.n_moden} Moden; weitere: {weitere}")
        return "<br>".join(zeilen)

    def _aktualisiere_overlay(self):
        st = self.stapel
        if st is None:
            return
        bres = np.array([e.B_res if e.gefittet else np.nan for e in st.ergebnisse], dtype=float)
        problem = np.array([e.problematisch for e in st.ergebnisse], dtype=bool)
        ausgeschlossen = np.zeros(len(st.ergebnisse), dtype=bool)
        gueltige = [i for i in st.ausreisser if i < ausgeschlossen.size]
        ausgeschlossen[gueltige] = True
        status = self._status_liste()
        info = [self._tooltip_text(i, s) for i, s in enumerate(status)]
        max_moden = max((e.n_moden for e in st.ergebnisse), default=1)
        nebenmoden = None
        if max_moden > 1:
            nebenmoden = []
            for k in range(1, max_moden):
                nebenmoden.append(np.array([
                    e.moden[k]["B_res"] if (e.gefittet and len(e.moden) > k) else np.nan
                    for e in st.ergebnisse], dtype=float))
        self.matrix.aktualisiere_resonanz(st.datensatz.frequenzen, bres, problem,
                                          ausgeschlossen, status=status, info=info,
                                          nebenmoden=nebenmoden)
        self.ausreisserpanel.zeige_ausreisser(st)

    def _zeige_aktuellen(self):
        if not self.stapel or not self.stapel.ergebnisse:
            return
        i = int(np.clip(self.aktueller_index, 0, len(self.stapel.ergebnisse) - 1))
        self.aktueller_index = i
        voll = self.stapel.datensatz.linescans[i]
        unten, oben = self.stapel.fenster[i]
        e = self.stapel.ergebnisse[i]
        status = F.status_von(e, ignoriert=self.stapel.ist_ausreisser(i))
        self.fitansicht.zeige(voll, unten, oben, e, status=status)
        # Wertbasiert markieren: der Stapel kann (Jumper) weniger Frequenzen
        # enthalten als die angezeigte Matrix.
        self.matrix.markiere_frequenz_wert(e.frequenz)
        self.status_label.setText(F.STATUS_KURZ.get(status, status))
        self.status_label.setToolTip(F.STATUS_TEXTE.get(status, status))
        self.status_label.setObjectName(f"status_{status}")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.btn_hauptmode.setEnabled(e.gefittet and e.n_moden > 1)
        # Auswahlliste auf den wirksamen Zustand stellen (ohne Rueckruf).
        art = "ignorieren" if status == "ignoriert" and self.stapel.ist_ausreisser(i) else e.bewertung
        self._bewertung_blockiert = True
        idx = self.bewertung_combo.findData(art)
        if idx >= 0:
            self.bewertung_combo.setCurrentIndex(idx)
        self._bewertung_blockiert = False
        punkte_im_fenster = int(np.count_nonzero((voll.feld >= unten) & (voll.feld <= oben)))
        if not e.gefittet:
            text = (f"[{i+1}/{len(self.stapel.ergebnisse)}] f={e.frequenz/1e9:.3f} GHz │ "
                    f"noch nicht gefittet – grüne Grenzen ziehen oder „Nochmal fitten“ "
                    f"fittet diese Frequenz │ Fenster {punkte_im_fenster} Pkt")
        else:
            text = (
                f"[{i+1}/{len(self.stapel.ergebnisse)}] f={e.frequenz/1e9:.3f} GHz │ "
                f"B_res={e.B_res:.4f} T ({e.B_res_mT:.1f} mT) │ µ₀ΔH={e.dH_mT:.2f} mT │ "
                f"α={e.alpha:.2e} │ R²={e.R2:.4f} │ Fenster {punkte_im_fenster} Pkt │ "
                f"{e.problem_text}")
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

    # --- Bewertung ----------------------------------------------------------------
    def _bewertung_gewaehlt(self, index: int) -> None:
        """Auswahlliste im Linescan-Panel: gewaehlte Bewertung anwenden."""
        if self._bewertung_blockiert:
            return
        art = self.bewertung_combo.itemData(index)
        st = self.stapel
        if art == "ignorieren" and st is not None and st.ist_ausreisser(self.aktueller_index):
            return  # schon ignoriert
        self._bewerte_aktuellen(art)

    def _bewerte_aktuellen(self, art: str) -> None:
        """Bewertung des aktuellen Fits setzen (gut/problematisch/auto/ignorieren).

        ``"ignorieren"`` schaltet den Ausreisser-Status um (Strg+I). Jede andere
        Bewertung nimmt einen ignorierten Punkt zuerst wieder auf.
        """
        st = self.stapel
        if not st or not st.ergebnisse or self._job_laeuft:
            return
        i = self.aktueller_index
        e = st.ergebnisse[i]
        if art == "ignorieren":
            if st.ist_ausreisser(i):
                self._ausreisser_wieder_aufnehmen([i])
            else:
                if not e.gefittet:
                    self._log("Bewertung: diese Frequenz ist noch nicht gefittet.", "warn")
                    return
                self._ausreisser_gewaehlt([i])
            self._zeige_aktuellen()
            return
        if not e.gefittet:
            self._log("Bewertung: diese Frequenz ist noch nicht gefittet.", "warn")
            return
        if st.ist_ausreisser(i):
            self._ausreisser_wieder_aufnehmen([i])
        vorher = self._fit_zustand([i])
        neu = st.bewerte(i, art)
        nachher = self._fit_zustand([i])
        self._merke_aenderung(
            f"Bewertung „{BEWERTUNG_TEXTE.get(neu.bewertung, art)}“ (f={e.frequenz/1e9:.2f} GHz)",
            lambda: self._fit_zustand_setzen(vorher),
            lambda: self._fit_zustand_setzen(nachher))
        self._aktualisiere_overlay()
        self._zeige_aktuellen()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()
        self._log(f"Bewertung f={e.frequenz/1e9:.2f} GHz: {neu.bewertung_text} "
                  f"(Kriterien: {'problematisch' if neu.problematisch_auto else 'OK'}).",
                  "ok" if not neu.problematisch else "warn")

    def _alle_bewertungen_auto(self) -> None:
        st = self.stapel
        if not st or not st.ergebnisse or self._job_laeuft:
            return
        indizes = [i for i, e in enumerate(st.ergebnisse) if e.bewertung != "auto"]
        if not indizes:
            self._log("Alle Bewertungen sind bereits automatisch.", "info")
            return
        vorher = self._fit_zustand(indizes)
        for i in indizes:
            st.bewerte(i, "auto")
        nachher = self._fit_zustand(indizes)
        self._merke_aenderung("Alle Bewertungen auf automatisch",
                              lambda: self._fit_zustand_setzen(vorher),
                              lambda: self._fit_zustand_setzen(nachher))
        self._aktualisiere_overlay()
        self._zeige_aktuellen()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()
        self._log(f"{len(indizes)} Bewertung(en) auf automatisch zurückgesetzt.", "ok")

    def _hauptmode_wechseln(self) -> None:
        st = self.stapel
        if not st or not st.ergebnisse:
            return
        i = self.aktueller_index
        e = st.ergebnisse[i]
        if not e.gefittet or e.n_moden < 2:
            return
        vorher = self._fit_zustand([i])
        st.ergebnisse[i] = hauptmode_wechseln(e, 1)
        nachher = self._fit_zustand([i])
        self._merke_aenderung(f"Hauptmode gewechselt (f={e.frequenz/1e9:.2f} GHz)",
                              lambda: self._fit_zustand_setzen(vorher),
                              lambda: self._fit_zustand_setzen(nachher))
        self._aktualisiere_overlay()
        self._zeige_aktuellen()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()

    # --- Nachfitten einzelner Frequenzen ------------------------------------------
    def _grenzen_geaendert(self, unten: float, oben: float):
        """Callback aus dem Linescan-Panel: neue Bandgrenzen -> sofort neu fitten."""
        if not self.stapel or not self.stapel.ergebnisse:
            return
        i = self.aktueller_index
        fits_vorher = self._fit_zustand([i])
        erg = fitte_neu(self.stapel, i, feld_unten=unten, feld_oben=oben,
                        n_moden=int(self.spin_moden.value()))
        fits_nachher = self._fit_zustand([i])
        self._merke_aenderung(
            f"Grenzen gezogen (f={erg.frequenz/1e9:.2f} GHz)",
            lambda: self._fit_zustand_setzen(fits_vorher),
            lambda: self._fit_zustand_setzen(fits_nachher))
        self._zeige_aktuellen()
        self._aktualisiere_overlay()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()
        self._log(f"Neu gefittet f={erg.frequenz/1e9:.2f} GHz "
                  f"[{unten:.3f}–{oben:.3f} T] → "
                  f"{'⚠ ' + erg.problem_text if erg.problematisch else '✓ ' + erg.problem_text}"
                  f" · B_res={erg.B_res:.4f} T, µ₀ΔH={erg.dH_mT:.2f} mT, R²={erg.R2:.4f}",
                  "warn" if erg.problematisch else "ok")

    def _neu_fitten(self):
        if not self.stapel or not self.stapel.ergebnisse:
            return
        i = self.aktueller_index
        unten, oben = self.stapel.fenster[i]
        fits_vorher = self._fit_zustand([i])
        erg = fitte_neu(self.stapel, i, feld_unten=unten, feld_oben=oben,
                        n_moden=int(self.spin_moden.value()))
        fits_nachher = self._fit_zustand([i])
        self._merke_aenderung(
            f"Nochmal gefittet (f={erg.frequenz/1e9:.2f} GHz)",
            lambda: self._fit_zustand_setzen(fits_vorher),
            lambda: self._fit_zustand_setzen(fits_nachher))
        self._zeige_aktuellen()
        self._aktualisiere_overlay()
        if self._auswertungsfenster is not None:
            self._auswertungsfenster.aktualisiere()

    # --- Kittel/LLG ------------------------------------------------------------------
    def _auswertungsfenster_holen(self) -> AuswertungsFenster:
        if self._auswertungsfenster is None:
            self._auswertungsfenster = AuswertungsFenster(
                hole_stapel=lambda: self.stapel,
                ausreisser_markieren=self._ausreisser_gewaehlt,
                ausreisser_rueckgaengig=self._rueckgaengig,
                geometrie=self._physik.geometrie,
                hole_parameter=lambda: self._physik,
                parent=self)
            self._auswertungsfenster.finished.connect(self._auswertungsfenster_zu)
        else:
            self._auswertungsfenster.aktualisiere()
        return self._auswertungsfenster

    def _kittel_llg(self):
        """Oeffnet das Kittel/LLG-Auswertungsfenster (eigenes, nicht-modales Fenster)."""
        if not self._fits_vorhanden():
            return
        fenster = self._auswertungsfenster_holen()
        fenster.show()
        fenster.raise_()
        fenster.activateWindow()
        n_ausreisser = len(self.stapel.ausreisser)
        if n_ausreisser:
            self._log(f"Kittel/LLG: {n_ausreisser} Ausreißer ausgeschlossen "
                      f"({len(self.stapel.ergebnisse_aktiv())} Punkte verbleiben).", "info")

    def _auswertungsfenster_zu(self, *_args):
        self._auswertungsfenster = None

    def _kittel_indizes(self) -> list[int]:
        """Stapel-Indizes, die in den Kittel-/LLG-Fit eingehen (gleiche Kriterien)."""
        st = self.stapel
        if st is None:
            return []
        gesperrt = set(st.ausreisser)
        r2_min = self._physik.r2_min
        return [i for i, e in enumerate(st.ergebnisse)
                if i not in gesperrt and e.gefittet and e.erfolg and not e.problematisch
                and np.isfinite(e.B_res) and (not np.isfinite(e.R2) or e.R2 >= r2_min)]

    # --- Export --------------------------------------------------------------------
    def _fits_vorhanden(self) -> bool:
        if not self.stapel or not self.stapel.index_gefittet():
            QtWidgets.QMessageBox.information(
                self, "Hinweis", "Bitte zuerst fitten (Auto-Fit, Grenzgeraden oder Bereich).")
            return False
        return True

    def _speicher_dialog(self, titel: str, vorgabe: str, filter_: str) -> str | None:
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, titel, os.path.join(self._letzter_ordner, vorgabe), filter_)
        if not pfad:
            return None
        self._letzter_ordner = os.path.dirname(pfad)
        return pfad

    def _basisname(self) -> str:
        quelle = self.stapel.datensatz.quelle if self.stapel else ""
        return Path(quelle).stem if quelle else "polderfit"

    def _global_parameter(self) -> dict:
        """Kittel/LLG (T und mT), Programm, Einstellungen fuer das Blatt 'Global'."""
        p = self._physik
        werte: dict = {
            "programm": PROGRAMMNAME,
            "datum": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "quelle": self.stapel.datensatz.quelle if self.stapel else "",
        }
        try:
            info = auswertung_kittel_llg(self.stapel.ergebnisse_aktiv(),
                                         geometrie=p.geometrie, gamma_fest=p.gamma_fest,
                                         gamma_start=p.gamma, r2_min=p.r2_min,
                                         gewichtet=p.gewichtet)
            kit, llg = info["kittel"], info["llg"]
            werte.update({f"kittel_{k}": v for k, v in kit.items()})
            werte["kittel_mu0Meff_mT"] = kit["mu0Meff"] * 1e3
            werte["kittel_mu0Meff_err_mT"] = kit["mu0Meff_err"] * 1e3
            if "mu0Hu" in kit:
                werte["kittel_mu0Hu_mT"] = kit["mu0Hu"] * 1e3
                werte["kittel_mu0Hu_err_mT"] = kit["mu0Hu_err"] * 1e3
            werte.update({f"llg_{k}": v for k, v in llg.items()})
            werte["llg_mu0Hinh_mT"] = llg["mu0Hinh"] * 1e3
            werte["llg_mu0Hinh_err_mT"] = llg["mu0Hinh_err"] * 1e3
            werte["gewichtung"] = "w=1/u^2 (GUM)" if p.gewichtet else "ungewichtet"
            werte["kittel_geometrie"] = info["geometrie"]
            werte["n_punkte_kittel"] = len(self._kittel_indizes())
        except Exception as exc:
            werte["kittel_llg"] = f"nicht berechenbar: {exc}"
        werte.update({f"physik_{k}": v for k, v in p.als_dict().items()})
        werte["verarbeitung"] = self.verarbeitung.kette().beschreibung()
        return werte

    def _zusatzblaetter(self) -> dict[str, pd.DataFrame]:
        st = self.stapel
        einst = [{"Groesse": f"physik_{k}", "Wert": v} for k, v in self._physik.als_dict().items()]
        einst.append({"Groesse": "verarbeitung", "Wert": self.verarbeitung.kette().beschreibung()})
        einst.append({"Groesse": "anzeige", "Wert": self.verarbeitung.anzeige_modus()})
        if st is not None and st.datensatz.meta.get("auswertungsauswahl"):
            einst.append({"Groesse": "auswertungsauswahl",
                          "Wert": str(st.datensatz.meta.get("auswertungsauswahl"))})
        zonen = [{"Typ": "Ausschlusszone", **z.als_dict()} for z in (st.ausschlusszonen if st else [])]
        zonen += [{"Typ": "Grenzgerade", "b1_T": g.b1, "f1_Hz": g.f1, "b2_T": g.b2, "f2_Hz": g.f2,
                   "gruen_positiv": g.gruen_positiv} for g in self._grenzgeraden]
        ausreisser = [{"index": i, "frequenz_Hz": st.ergebnisse[i].frequenz,
                       "B_res_T": st.ergebnisse[i].B_res}
                      for i in (st.ausreisser if st else []) if i < len(st.ergebnisse)]
        return {
            "Einstellungen": pd.DataFrame(einst),
            "Zonen_Geraden": pd.DataFrame(zonen) if zonen else pd.DataFrame(columns=["Typ"]),
            "Ausreisser": pd.DataFrame(ausreisser) if ausreisser else pd.DataFrame(columns=["index"]),
        }

    def _export_optionen(self) -> dict:
        return dict(self._einstellungen.export)

    def _export_excel(self, pfad: str | None = None) -> str | None:
        if not self._fits_vorhanden():
            return None
        if pfad is None:
            pfad = self._speicher_dialog("Excel speichern", self._basisname() + ".xlsx",
                                         "Excel (*.xlsx)")
            if not pfad:
                return None
        opt = self._export_optionen()
        with self._beschaeftigt(f"Schreibe Excel: {os.path.basename(pfad)} …"):
            exportiere_excel(self.stapel.ergebnisse, pfad, self._global_parameter(),
                             ausreisser=self.stapel.ausreisser,
                             spalten=opt.get("spalten") or None,
                             nur_gefittete=bool(opt.get("nur_gefittete", True)),
                             verwendet=self._kittel_indizes(),
                             zusatzblaetter=self._zusatzblaetter() if opt.get("zusatzblaetter", True) else None,
                             zugeschnitten=self.stapel.zugeschnitten)
        self.statusBar().showMessage(f"Excel gespeichert: {pfad}")
        self._log(f"Excel gespeichert: {os.path.basename(pfad)}", "ok")
        return pfad

    def _export_csv(self, pfad: str | None = None) -> str | None:
        if not self._fits_vorhanden():
            return None
        if pfad is None:
            pfad = self._speicher_dialog("CSV speichern", self._basisname() + ".csv", "CSV (*.csv)")
            if not pfad:
                return None
        opt = self._export_optionen()
        exportiere_csv(self.stapel.ergebnisse, pfad, ausreisser=self.stapel.ausreisser,
                       spalten=opt.get("spalten") or None,
                       nur_gefittete=bool(opt.get("nur_gefittete", True)),
                       verwendet=self._kittel_indizes(),
                       deutsch=bool(opt.get("csv_deutsch", False)),
                       zugeschnitten=self.stapel.zugeschnitten)
        self.statusBar().showMessage(f"CSV gespeichert: {pfad}")
        self._log(f"CSV gespeichert: {os.path.basename(pfad)}", "ok")
        return pfad

    def _export_tdms(self, pfad: str | None = None) -> str | None:
        if not self._fits_vorhanden():
            return None
        if pfad is None:
            pfad = self._speicher_dialog("TDMS speichern", self._basisname() + "_fit.tdms",
                                         "TDMS (*.tdms)")
            if not pfad:
                return None
        st = self.stapel
        indizes = st.index_gefittet()
        schreibe_ergebnis_tdms(pfad, [st.zugeschnitten[i] for i in indizes],
                               [st.ergebnisse[i].fitkurve for i in indizes])
        self.statusBar().showMessage(f"TDMS gespeichert: {pfad}")
        self._log(f"TDMS gespeichert: {os.path.basename(pfad)}", "ok")
        return pfad

    def _export_kittel(self, basis: str | None = None) -> list[str]:
        if not self._fits_vorhanden():
            return []
        if basis is None:
            pfad = self._speicher_dialog("Kittel/LLG-Auswertung exportieren",
                                         self._basisname() + "_kittel_llg.xlsx", "Excel (*.xlsx)")
            if not pfad:
                return []
            basis = os.path.splitext(pfad)[0]
        fenster = self._auswertungsfenster_holen()
        with self._beschaeftigt("Schreibe Kittel/LLG-Auswertung (Excel, CSV, Plot) …"):
            dateien = fenster.exportiere(basis, csv_deutsch=bool(self._export_optionen().get("csv_deutsch")))
        self._log("Kittel/LLG exportiert: " + ", ".join(os.path.basename(d) for d in dateien), "ok")
        return dateien

    def _export_farbplot_bild(self, pfad: str | None = None) -> str | None:
        if self.datensatz_voll is None:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst eine TDMS-Datei laden.")
            return None
        if pfad is None:
            pfad = self._speicher_dialog("Farbplot als Bild", self._basisname() + "_farbplot.png",
                                         "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
            if not pfad:
                return None
        self.matrix.speichere_bild(pfad)
        self._log(f"Farbplot gespeichert: {os.path.basename(pfad)}", "ok")
        return pfad

    def _export_matrix_csv(self, pfad: str | None = None) -> str | None:
        if self.datensatz_voll is None:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst eine TDMS-Datei laden.")
            return None
        if pfad is None:
            pfad = self._speicher_dialog("Farbplot-Matrix als CSV",
                                         self._basisname() + "_matrix.csv", "CSV (*.csv)")
            if not pfad:
                return None
        feld, freq, matrix = self.matrix.verarbeitete_matrix()
        if matrix is None:
            return None
        tab = pd.DataFrame(matrix, index=pd.Index(freq, name="frequenz_Hz"),
                           columns=[f"{b:.6f}" for b in feld])
        tab.columns.name = "feld_T"
        deutsch = bool(self._export_optionen().get("csv_deutsch", False))
        if deutsch:
            tab.to_csv(pfad, sep=";", decimal=",", encoding="utf-8-sig")
        else:
            tab.to_csv(pfad)
        self._log(f"Farbplot-Matrix gespeichert: {os.path.basename(pfad)} "
                  f"({self.verarbeitung.kette().beschreibung()} · {self.verarbeitung.anzeige_modus()})", "ok")
        return pfad

    def _alles_speichern(self) -> None:
        if self.datensatz_voll is None:
            QtWidgets.QMessageBox.information(self, "Hinweis", "Bitte zuerst eine TDMS-Datei laden.")
            return
        hat_fits = bool(self.stapel and self.stapel.index_gefittet())
        ordner = self._letzter_ordner or os.path.dirname(self.stapel.datensatz.quelle) or os.getcwd()
        dialog = AllesSpeichernDialog(ordner, self._basisname(), hat_fits, True, parent=self)
        if not dialog.exec():
            return
        wahl = dialog.auswahl()
        ordner = wahl["ordner"]
        Path(ordner).mkdir(parents=True, exist_ok=True)
        self._letzter_ordner = ordner
        basis = os.path.join(ordner, wahl["basis"])
        geschrieben: list[str] = []
        fehler: list[str] = []
        self._log(f"Alles speichern nach {ordner} …", "info")
        schritte = {
            "projekt": lambda: self._projekt_speichern(basis + ".polderfit-projekt.json"),
            "excel": lambda: self._export_excel(basis + ".xlsx"),
            "csv": lambda: self._export_csv(basis + ".csv"),
            "kittel": lambda: self._export_kittel(basis + "_kittel_llg"),
            "farbplot": lambda: [self._export_farbplot_bild(basis + "_farbplot.png"),
                                 self._export_farbplot_bild(basis + "_farbplot.pdf")],
            "matrix": lambda: self._export_matrix_csv(basis + "_matrix.csv"),
            "tdms": lambda: self._export_tdms(basis + "_fit.tdms"),
            "einstellungen": lambda: str(speichere_einstellungen(
                self._einstellungen_sammeln(), basis + DATEI_ENDUNG)),
        }
        for teil in wahl["teile"]:
            try:
                with self._beschaeftigt(f"Alles speichern: {teil} …"):
                    res = schritte[teil]()
            except Exception as exc:
                fehler.append(f"{teil}: {exc}")
                self._log(f"FEHLER beim Speichern ({teil}): {exc}", "problem")
                continue
            if isinstance(res, (list, tuple)):
                geschrieben += [r for r in res if r]
            elif res:
                geschrieben.append(str(res))
        text = f"{len(geschrieben)} Datei(en) in {ordner} geschrieben."
        if fehler:
            text += "\n\nFehler:\n" + "\n".join(fehler)
        self._log(text.replace("\n", " "), "problem" if fehler else "ok")
        QtWidgets.QMessageBox.information(self, "Alles speichern", text)

    def _spalten_dialog(self) -> None:
        dialog = SpaltenDialog(self._einstellungen.export, parent=self)
        if not dialog.exec():
            return
        self._einstellungen.export = dialog.einstellungen()
        gruppen = self._einstellungen.export.get("spalten") or ["alle"]
        self._log("Export-Spalten: " + ", ".join(gruppen)
                  + (", nur gefittete" if self._einstellungen.export.get("nur_gefittete") else "")
                  + (", CSV deutsch" if self._einstellungen.export.get("csv_deutsch") else ""), "ok")

    # --- Ausschlusszonen ------------------------------------------------------
    def _zone_gezeichnet(self, feld_min, feld_max, f_min_ghz, f_max_ghz):
        stapel = self.stapel
        zone = Ausschlusszone(feld_min, feld_max, f_min_ghz * 1e9, f_max_ghz * 1e9)
        betroffen_vorab = [int(i) for i in np.flatnonzero(
            (stapel.datensatz.frequenzen >= zone.frequenz_min)
            & (stapel.datensatz.frequenzen <= zone.frequenz_max))]
        zonen_vorher = list(stapel.ausschlusszonen)
        fits_vorher = self._fit_zustand(betroffen_vorab)

        def aufgabe(melde):
            return fuege_ausschlusszone_hinzu(stapel, zone, fortschritt=lambda k, n, e: melde(k, n, ""))

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

        self._starte_job(aufgabe, bei_fertig, "Ausschlusszone anwenden …", abbrechbar=False)

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

        self._starte_job(aufgabe, bei_fertig, "Ausschlusszone entfernen …", abbrechbar=False)

    # --- Ausreisser-Management -----------------------------------------------
    def _merke_ausreisser_aenderung(self, beschreibung: str,
                                    vorher: list[int]) -> None:
        nachher = list(self.stapel.ausreisser)
        self._merke_aenderung(beschreibung,
                              lambda v=vorher: self._ausreisser_setzen(v),
                              lambda n=nachher: self._ausreisser_setzen(n))

    def _ausreisser_gewaehlt(self, indizes: list[int]):
        """Callback aus Farbplot/Auswertungsfenster: Punkte ignorieren (Echtzeit)."""
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
        self._log(f"Ignoriert (Ausreißer): {len(neu)} Punkt(e) "
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
        self._log(f"{len(indizes)} Punkt(e) wieder aufgenommen – "
                  f"verbleibend {len(self.stapel.ausreisser)} ignoriert.", "ok")

    # --- Projekt speichern / laden / Auto-Sicherung --------------------------
    def _projekt_speichern(self, pfad: str | None = None) -> str | None:
        if not self.stapel or not self.stapel.index_gefittet():
            QtWidgets.QMessageBox.information(
                self, "Hinweis", "Bitte zuerst fitten – gespeichert wird der "
                "komplette Auswertungszustand.")
            return None
        if pfad is None:
            pfad = self._speicher_dialog("Projekt speichern",
                                         self._basisname() + ".polderfit-projekt.json",
                                         "PolderFit-Projekt (*.json)")
            if not pfad:
                return None
        speichere_sitzung(self.stapel, pfad, physik=self._physik.als_dict(),
                          verarbeitung=self.verarbeitung.kette().als_dict(),
                          grenzgeraden=self._grenzgeraden)
        self._log(f"Projekt gespeichert: {os.path.basename(pfad)} "
                  f"({len(self.stapel.index_gefittet())} Fits, "
                  f"{len(self.stapel.ausreisser)} Ausreißer, "
                  f"{len(self.stapel.ausschlusszonen)} Zonen, "
                  f"{len(self._grenzgeraden)} Grenzgeraden).", "ok")
        return pfad

    def _autosicherung_anstossen(self) -> None:
        """Auto-Sicherung zeitversetzt nach der letzten Aenderung schreiben."""
        if self.stapel is not None and self.stapel.index_gefittet():
            self._autosicherung_timer.start()

    def _autosicherung_schreiben(self) -> None:
        if self.stapel is None or not self.stapel.index_gefittet() or self._job_laeuft:
            return
        try:
            pfad = autosicherung_pfad()
            speichere_sitzung(self.stapel, str(pfad), physik=self._physik.als_dict(),
                              verarbeitung=self.verarbeitung.kette().als_dict(),
                              grenzgeraden=self._grenzgeraden)
            self._log(f"Auto-Sicherung geschrieben ({pfad.name}).", "auto")
        except Exception as exc:  # nie den Arbeitsfluss stoeren
            self._log(f"Auto-Sicherung fehlgeschlagen: {exc}", "warn")

    def _autosicherung_wiederherstellen(self) -> None:
        pfad = autosicherung_pfad()
        if not pfad.exists():
            QtWidgets.QMessageBox.information(
                self, "Auto-Sicherung", f"Keine Auto-Sicherung vorhanden ({pfad}).")
            return
        self._projekt_laden(str(pfad))

    def _projekt_laden(self, pfad: str | None = None):
        if self._job_laeuft:
            return
        if pfad is None:
            pfad, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Projekt laden", self._letzter_ordner, "PolderFit-Projekt (*.json)")
            if not pfad:
                return
            self._letzter_ordner = os.path.dirname(pfad)
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
                "Bitte die Messdatei auswählen.")
            quelle, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "TDMS-Quelle des Projekts", self._letzter_ordner, "TDMS (*.tdms)")
            if not quelle:
                return

        zuordnung = daten.get("zuordnung")
        if zuordnung is not None:
            zuordnung = {rolle: tuple(paar) for rolle, paar in zuordnung.items()}
        auswahl_dict = daten.get("auswertungsauswahl")

        def aufgabe(melde):
            melde(0, 0, f"Lade {os.path.basename(quelle)} …", phase="TDMS lesen")
            if zuordnung is not None:
                voll = lade_tdms(quelle, zuordnung=zuordnung,
                                 layout=daten.get("format_typ"))
            else:
                voll = lade_tdms(quelle)  # Projektdatei Version 1: Auto-Profil
            reduziert = voll
            if auswahl_dict:
                auswahl = Auswertungsauswahl.aus_dict(auswahl_dict)
                reduziert, _indizes = auswahl.reduziere(voll)
            melde(0, 0, "Stelle Fits mit gespeicherten Fenstern wieder her …", phase="Fits")
            stapel = stelle_stapel_wieder_her(
                daten, reduziert,
                fortschritt=lambda k, n, e: melde(k, n, "", phase="Fits wiederherstellen"))
            return (voll, stapel)

        def bei_fertig(res):
            voll, stapel = res
            if isinstance(daten.get("physik"), dict):
                self._physik_uebernehmen(PhysikParameter.aus_dict(daten["physik"]), leise=True)
            if isinstance(daten.get("verarbeitung"), dict):
                try:
                    from ..verarbeitung import Verarbeitungskette
                    self.verarbeitung.setze_kette(
                        Verarbeitungskette.aus_dict(daten["verarbeitung"]), melden=False)
                except Exception:
                    pass
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
            self._grenzgeraden = grenzgeraden_aus_sitzung(daten)
            self._zeige_geraden()
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
                      f"{len(stapel.index_gefittet())} Fits wiederhergestellt, "
                      f"{len(stapel.ausreisser)} Ausreißer, "
                      f"{len(stapel.ausschlusszonen)} Zonen, "
                      f"{len(self._grenzgeraden)} Grenzgeraden.", "ok")
            self.statusBar().showMessage(
                f"Projekt geladen ({len(stapel.index_gefittet())} Fits).")

        self._starte_job(aufgabe, bei_fertig, f"Lade Projekt {os.path.basename(pfad)} …",
                         abbrechbar=False)

    # --- Einstellungen (Voreinstellungen) -------------------------------------
    def _einstellungen_sammeln(self) -> Einstellungen:
        """Aktuelle Einstellungen aus GUI-Zustand (ohne Fenster-/Zoom-Zustand)."""
        e = self._einstellungen
        e.physik = self._physik.als_dict()
        e.verarbeitung = self.verarbeitung.kette().als_dict()
        e.anzeige = {
            "farbskala": self.matrix.farbskala(),
            "zoom_aktiv": self.akt_zoom.isChecked(),
            "problemfits_ausblenden": self.akt_problemfits.isChecked(),
            "vollbereich": self.akt_vollbereich.isChecked(),
            "ausreisser_anzeigen": self.akt_ausreisser_anzeigen.isChecked(),
            "nebenmoden_anzeigen": self.akt_nebenmoden.isChecked(),
        }
        e.bereichsfit = {"modus": self._bereich_modus, "breite_punkte": self._bereich_breite}
        return e

    def _einstellungen_anwenden(self, einst: Einstellungen, physik: bool = True,
                                melden: bool = True) -> None:
        self._einstellungen = einst
        if physik:
            self._physik_uebernehmen(einst.physik_parameter(), leise=not melden)
        anzeige = einst.anzeige
        self.akt_zoom.setChecked(bool(anzeige.get("zoom_aktiv", False)))
        self.akt_problemfits.setChecked(bool(anzeige.get("problemfits_ausblenden", False)))
        self.akt_vollbereich.setChecked(bool(anzeige.get("vollbereich", False)))
        self.akt_ausreisser_anzeigen.setChecked(bool(anzeige.get("ausreisser_anzeigen", False)))
        self.akt_nebenmoden.setChecked(bool(anzeige.get("nebenmoden_anzeigen", True)))
        self._farbskala_setzen(anzeige.get("farbskala", "viridis"))
        self._bereich_modus = einst.bereichsfit.get("modus", "ueberschreiben")
        self._bereich_breite = einst.bereichsfit.get("breite_punkte")
        self.verarbeitung.setze_kette(einst.verarbeitungskette(), melden=self.datensatz_voll is not None)
        if melden:
            self._log("Einstellungen angewendet.", "ok")

    def _einstellungen_speichern_unter(self) -> None:
        pfad = self._speicher_dialog("Einstellungen speichern", "polderfit" + DATEI_ENDUNG,
                                     f"PolderFit-Einstellungen (*{DATEI_ENDUNG});;JSON (*.json)")
        if not pfad:
            return
        speichere_einstellungen(self._einstellungen_sammeln(), pfad)
        self._log(f"Einstellungen gespeichert: {os.path.basename(pfad)}", "ok")

    def _einstellungen_laden(self) -> None:
        pfad, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Einstellungen laden", self._letzter_ordner,
            f"PolderFit-Einstellungen (*{DATEI_ENDUNG});;JSON (*.json)")
        if not pfad:
            return
        try:
            einst = lade_einstellungen(pfad)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Einstellungen laden", str(exc))
            return
        self._einstellungen_anwenden(einst)
        self._log(f"Einstellungen geladen: {os.path.basename(pfad)}", "ok")

    def _einstellungen_als_standard(self) -> None:
        pfad = speichere_einstellungen(self._einstellungen_sammeln(), standard_pfad())
        self._log(f"Als Standard gespeichert (wird beim Start geladen): {pfad}", "ok")
        self.statusBar().showMessage(f"Standard-Einstellungen gespeichert: {pfad}", 6000)

    def _einstellungen_zuruecksetzen(self) -> None:
        self._einstellungen_anwenden(Einstellungen())
        self._log("Einstellungen auf Programm-Standard zurückgesetzt (Datei bleibt, bis "
                  "„Als Standard speichern“ erneut ausgeführt wird).", "ok")

    # --- Verarbeitung / Ansicht ----------------------------------------------
    def _verarbeitung_geaendert(self, kette, anzeige_modus: str):
        """Callback des Verarbeitungspanels: Kette neu auf den Farbplot anwenden."""
        self._einstellungen.verarbeitung = kette.als_dict()
        if self.datensatz_voll is None:
            return
        try:
            self.matrix.setze_verarbeitung(kette, anzeige_modus)
        except ValueError as fehler:
            self._log(f"Verarbeitung nicht anwendbar: {fehler}", "warn")
            return
        mat, ext = self.matrix.thumbnail()
        self.navigator.zeige(mat, ext)
        self._log(f"Verarbeitung: {kette.beschreibung()} · Anzeige {anzeige_modus}", "auto")

    def _farbskala_geaendert(self, name: str) -> None:
        """Vom Verarbeitungspanel: Farbskala uebernehmen (Menue folgt)."""
        self._farbskala_setzen(name)

    def _farbskala_setzen(self, name: str) -> None:
        if name not in FARBSKALEN:
            name = "viridis"
        akt = self.akt_farbskalen.get(name)
        if akt is not None and not akt.isChecked():
            akt.setChecked(True)
        self.verarbeitung.setze_farbskala(name)
        if self.matrix.farbskala() != name:
            self.matrix.setze_farbskala(name)
            if self.datensatz_voll is not None:
                mat, ext = self.matrix.thumbnail()
                self.navigator.zeige(mat, ext)
        self._einstellungen.anzeige["farbskala"] = name

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

    def _frequenz_gewaehlt(self, index: int):
        """Klick in der Uebersicht: Index der VOLLEN Frequenzachse -> Stapel-Index.

        Der Stapel kann durch die Auswertungsauswahl (Jumper) weniger
        Frequenzen enthalten; gewaehlt wird der wertmaessig naechste Fit.
        Das Linescan-Panel erscheint beim ersten Klick (auch ohne Fit: dort
        lassen sich die Grenzen ziehen und die Frequenz fitten).
        """
        if not self.stapel or not self.stapel.ergebnisse:
            return
        _, freq_achse = self.matrix.achsen()
        if freq_achse is None or index >= len(freq_achse):
            return
        f = float(freq_achse[index])
        self.aktueller_index = int(np.argmin(np.abs(self.stapel.datensatz.frequenzen - f)))
        if self.linescan_dock.isHidden():
            self._dock_schmal_halten(self.linescan_dock, breite=500)
        self._zeige_aktuellen()

    # --- Hilfe ----------------------------------------------------------------
    def _zeige_hilfe(self):
        """Oeffnet den Hilfe-Dialog (modal)."""
        self._baue_hilfe_dialog().exec()

    def _baue_hilfe_dialog(self) -> QtWidgets.QDialog:
        """Hilfe-Dialog: Bedienung und Repository-Link."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"{PROGRAMMNAME} – Hilfe & Infos")
        dlg.resize(700, 620)
        lay = QtWidgets.QVBoxLayout(dlg)

        kopf = QtWidgets.QHBoxLayout()
        titel = QtWidgets.QLabel(
            f"<b style='font-size:16px'>{PROGRAMMNAME}</b><br>"
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
        <p><b>{PROGRAMMNAME}</b> wertet Breitband-FMR-Messungen (bbFMR) aus: TDMS-Dateien einlesen,
        je Frequenz das Resonanzsignal fitten und daraus die Materialparameter bestimmen.
        Die Karte lässt sich auch <b>allein zur Datenansicht</b> nutzen (Verarbeitung:
        derivative divide, divide slice, … – ganz ohne Fit).</p>

        <h3>Arbeitsablauf</h3>
        <ol>
          <li><b>TDMS laden</b> (Strg+O). Danach füllt die Messung den Farbplot; das
              Verarbeitungs-Panel erscheint (genau eine Verarbeitung aktiv, Erklärung per
              Maus-Hover, Farbskala wählbar).</li>
          <li><b>Physikalische Parameter</b> (Strg+P, optional) – g-Faktor/γ, Kittel-Geometrie
              (oop/ip), Fensterbreite-Faktor, R²-Schwellen, α-Obergrenze und
              α-Plausibilitätsgrenze, Resonanzen je Linescan (2 = Doppel-Dip).</li>
          <li><b>Fitten – drei Wege, alle direkt nach dem Laden möglich:</b>
              <ul>
              <li><b>Auto-Fit (alle)</b> (F5): Dialog mit Frequenz/Feld von … bis … und Jumper,
                  danach Fenstersuche und Fit je Frequenz im Hintergrund.</li>
              <li><b>Grenzgeraden</b> (Strg+L oder Panel „Zonen &amp; Grenzgeraden“): zwei Klicks
                  im Farbplot, Endpunkte ziehbar, grüner Saum = wird gefittet, roter = ignoriert
                  (Doppelklick tauscht), zwei Geraden = Band. „Grünen Bereich fitten …“ fragt
                  Frequenz/Feld von … bis …, Modus, Fensterbreite und Resonanzen ab.</li>
              <li><b>Bereich neu fitten</b> (Strg+B): Rechteck im Farbplot; derselbe Dialog.</li>
              </ul>
              Im <b>Linescan-Panel</b> (erscheint mit dem ersten Fit oder Klick in die Karte)
              die grünen Grenzlinien ziehen oder „Nochmal fitten“ – mit wählbarer Zahl
              Resonanzen. <i>Zurück/Weiter/Nächster Problemfit</i> steuern den Korrekturlauf.</li>
          <li><b>Bewertung</b>: Farbe und Form der Punkte folgen DIN EN 60073 –
              <span style="color:{F.TEXT_GRUEN}"><b>grün ●</b> gut</span> (blauer Rand = vom Nutzer
              bestätigt), <span style="color:{F.TEXT_GELB}"><b>gelb ▲</b> problematisch</span>
              (prüfen), <span style="color:{F.TEXT_ROT}"><b>rot ✕</b> Fit fehlgeschlagen</span>,
              <span style="color:{F.TEXT_GRAU}"><b>grau ●</b> ignoriert</span>. Ein gezielter
              Eingriff an einer Frequenz (Grenzen ziehen, „Nochmal fitten“) gilt als bestätigt
              (abschaltbar, Strg+P); Bereichs-/Grenzgeraden-Fits über viele Frequenzen bewerten
              die Kriterien. Umbewerten: Auswahlliste im Linescan-Panel oder Strg+1 gut, Strg+2
              problematisch, Strg+3 automatisch, Strg+I ignorieren; Punkt im Farbplot
              überfahren zeigt f, B_res, µ₀ΔH in mT, α, R² und Status.</li>
          <li><b>Ausreißer markieren</b> (Strg+M) – Punkte anklicken oder per Kasten
              ignorieren; reversibel (Liste + Rückgängig). Ignorierte Punkte fehlen in ALLEN
              Auswertungen und sind im Export gekennzeichnet.</li>
          <li><b>Kittel/LLG-Auswertung</b> (Strg+K) – eigenes Fenster mit Feld auf der x-Achse:
              Punkte direkt im Plot entfernen, Fit rechnet sofort neu; Ergebnisse in T und mT;
              Export Excel + CSV + Plot.</li>
          <li><b>Speichern</b> (Datei → Speichern / Export): <b>Alles speichern</b>
              (Strg+Umschalt+S) schreibt Projekt, Excel/CSV, Kittel/LLG, Farbplot-Bild und
              -Matrix, TDMS und Einstellungen in einen Ordner. Excel/CSV enthalten alle
              Fitparameter (B_res und µ₀ΔH in T <b>und mT</b>, α, Amplitude/Phase, komplexe
              Amplitude, Offsets, Gütemaße, Status, weitere Moden) – Spaltengruppen unter
              „Export-Spalten“ wählbar. <b>Einstellungen</b> (Physik, Verarbeitung, Anzeige,
              Export) lassen sich speichern, laden und als Start-Standard setzen.</li>
        </ol>

        <h3>Interaktive Modi</h3>
        <ul>
          <li>Es ist immer höchstens <b>ein</b> Modus aktiv (Bereich neu fitten, Grenzgerade,
              Ausschlusszone, Ausreißer markieren); der aktive Modus ist im
              „Funktionen"-Menü markiert und wird rechts in der Statusleiste angezeigt.</li>
          <li><b>Esc</b> bricht jeden Modus ab; das Starten eines Modus beendet den vorherigen.</li>
          <li><b>Strg+Z / Strg+Umschalt+Z</b> (auch Strg+Y): Änderungen rückgängig machen und
              wiederholen – Grenzgeraden, Ausschlusszonen, Ausreißer, Bewertungen und Nachfits.</li>
        </ul>

        <h3>Übersicht – Navigation, Zoom, Fenster</h3>
        <ul>
          <li><b>Klicken</b>: Frequenz wählen → der zugehörige Linescan wird geladen.</li>
          <li><b>Zoom</b> ist standardmäßig aus – einschalten unter <i>Ansicht → Zoom</i>.
              Dann: Kästchen ziehen zoomt, Mausrad rein/raus. <b>Doppelklick</b>: Zoom zurück.</li>
          <li><b>Umschalt+Mausrad</b> oder <b>↑/↓</b> (Pos1/Ende, Bild↑/↓): Frequenz wechseln.</li>
          <li><b>F11</b>: Vollbild (Esc verlässt es). <b>Ansicht → Fensterlayout zurücksetzen</b>
              (Strg+Umschalt+R) stellt Farbplot und Panels ohne Datenverlust wieder her.</li>
          <li>Mausrad über Eingabefeldern wirkt nur, wenn das Feld den Fokus hat – kein
              versehentliches Verstellen beim Scrollen.</li>
          <li>Der Arbeitsstand wird 15 s nach jeder Änderung automatisch gesichert
              (Datei → Auto-Sicherung wiederherstellen). Zoom, Fensterlayout und
              Achsengrößen werden nie gespeichert.</li>
          <li>Während Auto-Fit, Bereichs-/Grenzgeraden-Fit und Laden zeigt die Statusleiste
              Phase, Stand, verstrichene und geschätzte Restzeit; die gefitteten Punkte
              erscheinen sofort im Farbplot. <b>Abbrechen</b> beendet den Fit geordnet –
              bisherige Ergebnisse bleiben.</li>
        </ul>

        <hr>
        <p>Quellcode und Dokumentation:<br>
        <a href="{REPO_URL}">{REPO_URL}</a></p>
        </body></html>
        """


def starte_gui(argv=None):
    """Startet die Qt-Anwendung (Linux, Windows, macOS)."""
    import sys as _sys

    if sys.platform.startswith("win"):
        # Eigene Taskleisten-Gruppe/-Symbol statt "python.exe".
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PolderFit.App")
        except Exception:
            pass
    else:
        # Harmlose, sehr gespraechige Wayland-Textinput-Warnung leise stellen.
        regel = "qt.qpa.wayland.textinput=false"
        bestehend = os.environ.get("QT_LOGGING_RULES", "")
        if regel not in bestehend:
            os.environ["QT_LOGGING_RULES"] = f"{bestehend};{regel}".strip(";")

    # Windows-Skalierung 125 %/150 %: Bruchteile durchreichen statt runden
    # (sonst unscharfe/zu grosse Schrift). Muss VOR der QApplication gesetzt sein.
    try:
        QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(argv or _sys.argv)
    app.setApplicationName(PROGRAMMNAME)
    app.setOrganizationName("PolderFit")
    app.setStyleSheet(PolderFit_QSS)
    fenster = Hauptfenster()
    # Farbplot in voller Breite: maximiert starten.
    fenster.showMaximized()
    return app.exec()

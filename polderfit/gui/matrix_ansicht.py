# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""2D-Uebersicht: Magnituden-Matrix (Frequenz vs. Feld) mit Resonanzverlauf.

Zeigt die gesamte Messung als Falschfarbenbild, ueberlagert die gefitteten
Resonanzfelder und markiert die aktuell gewaehlte Frequenz mit einer horizontalen
Linie. Ohne geladene Daten erscheint ein leeres, kariertes Koordinatensystem
(Feld auf der x-, Frequenz auf der y-Achse) als Platzhalter.

Die Resonanzpunkte tragen ihren Status in Farbe UND Form (DIN EN 60073 /
DIN EN ISO 9241-125, siehe :mod:`polderfit.gui.farben`): gruener Punkt = guter
Fit (blauer Rand = vom Nutzer bestaetigt), gelbes Dreieck = problematisch,
rotes Kreuz = Fit fehlgeschlagen, grauer Ring = ignoriert (Ausreisser), gruene
Raute = Resonanz einer weiteren Mode (Korridor-Fit). Beim Ueberfahren eines Punkts erscheint
ein Tooltip mit Frequenz, B_res, Linienbreite in mT, alpha, R² und Status.

Bedienung:

* **Klicken** – springt zur naechstgelegenen Frequenz (laedt sofort deren Fit),
* **Aufziehen (Kaestchen)** – zoomt auf den markierten Bereich,
* **Mausrad** – rein/raus zoomen (zentriert auf den Cursor); Kaestchen- und
  Rad-Zoom sind nur aktiv, wenn im Menue *Ansicht -> Zoom* eingeschaltet,
* **Umschalt + Mausrad** – eine Frequenz hoch/runter,
* **Doppelklick** – Zoom zuruecksetzen (ganze Messung),
* **Pfeiltasten** ``hoch/runter`` (bzw. ``links/rechts``), ``Bild hoch/runter``
  (10er-Schritt), ``Pos1/Ende`` (erste/letzte Frequenz); ``+/-/0`` zoomen.

Interaktive Modi (Bereichs-Fit, Ausschlusszone, Ausreisser, Korridor, Anker) laufen
ueber einen ZENTRALEN Modus-Manager: es ist immer hoechstens EIN Modus aktiv,
das Starten eines Modus beendet den vorherigen, ``Esc`` bricht jeden Modus ab
und jede Aenderung wird ueber ``modus_geaendert(name | None)`` gemeldet, damit
die Menueleiste den aktiven Modus eindeutig anzeigen kann.

Layout-Stabilitaet: Das Figure-Layout wird vor JEDEM ``tight_layout`` auf die
Standardraender zurueckgesetzt und der Bedienhinweis unterhalb der Achse ist
vom Layout ausgenommen. Ohne diesen Reset schrumpfte die Achse bei jedem
Neuzeichnen (z. B. Mausrad ueber dem Δn-Feld der Verarbeitung) weiter, bis
der Farbplot unkenntlich schmal war.
"""

from __future__ import annotations

import warnings

import numpy as np
import matplotlib.patheffects as pe
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6 import QtCore, QtGui, QtWidgets

from ..io.datensatz import Messdatensatz
from ..verarbeitung import ANZEIGE_MODI, Verarbeitungskette, anzeige_transform
from . import farben as F

#: Robuste Farbskala: NaN-feste Perzentile gegen Ausreisser (v. a. nach
#: derivative divide, wo einzelne Punkte um Groessenordnungen herausragen
#: koennen und eine lineare Skala die Mode unsichtbar machen wuerden).
_CLIM_PERZENTILE = (2.0, 98.0)

#: Zoomfaktor pro Mausrad-Schritt (rein = sichtbaren Bereich verkleinern).
_ZOOM_REIN = 0.8
_ZOOM_RAUS = 1.25
#: Mindest-Mausbewegung (Anteil der sichtbaren Spanne), ab der aus einem Klick ein
#: Aufzieh-Kaestchen wird (darunter zaehlt es als Klick = Frequenzauswahl).
_BOX_SCHWELLE_REL = 0.02

#: Alle bekannten Interaktionsmodi (zentrale Verwaltung, exklusiv).
MODI = ("bereich", "zone", "ausreisser", "korridor", "anker")

#: Mauszeiger je Modus.
_MODUS_CURSOR = {
    "bereich": QtCore.Qt.CrossCursor,
    "zone": QtCore.Qt.CrossCursor,
    "ausreisser": QtCore.Qt.PointingHandCursor,
    "korridor": QtCore.Qt.CrossCursor,
    "anker": QtCore.Qt.CrossCursor,
}

#: Modi, die ueber ZWEI Klicks zwei Punkte einsammeln.
_ZWEI_PUNKT_MODI = ("korridor",)

#: Linienfarbe je Mode (Korridore; Mode 1 = Textfarbe).
_MODE_FARBEN = F.MODE_FARBEN
#: Fuellung der Korridore (Achsen-Alpha) - aktiver Korridor kraeftiger.
_KORRIDOR_ALPHA = 0.10
_KORRIDOR_ALPHA_AKTIV = 0.20
#: Relative Trefferdistanz fuer Anker-Griffe.
_GRIFF_TOLERANZ = 0.035
#: Relative Trefferdistanz fuer Hover-Tooltip / Ausreisser-Klick auf Punkte.
_PUNKT_TOLERANZ = 0.03

#: Standardraender der Figur (werden vor jedem Layout zurueckgesetzt).
_RAENDER_STANDARD = dict(left=0.10, right=0.985, top=0.93, bottom=0.14)

#: Reihenfolge und Matplotlib-Label der Statusklassen im Overlay.
_STATUS_LABEL = {
    "gut": "_resonanz",
    "bestaetigt": "_resonanz",
    "problem": "_resonanz_problem",
    "fehler": "_resonanz_fehler",
    "ignoriert": "_resonanz_ignoriert",
}


class MatrixAnsicht(FigureCanvasQTAgg):
    """Falschfarben-Uebersicht der Magnitude mit Resonanz-Overlay und Zoom."""

    def __init__(self, frequenz_gewaehlt=None, zoom_geaendert=None,
                 modus_geaendert=None):
        self.figur = Figure(figsize=(5, 5))
        super().__init__(self.figur)
        self.ax = self.figur.add_subplot(111)
        self.frequenz_gewaehlt = frequenz_gewaehlt
        self.zoom_geaendert = zoom_geaendert
        #: Meldet jeden Moduswechsel: ``modus_geaendert(name | None)``.
        self.modus_geaendert = modus_geaendert
        self._datensatz: Messdatensatz | None = None
        self._matrix = None
        self._freq_achse = None
        self._extent = None            # (feld_min, feld_max, f_min_GHz, f_max_GHz)
        # Verarbeitungskette: gecachte komplexe Rohmatrix + aktueller Zustand.
        self._Z_komplex = None         # (n_freq, n_feld), komplex, NaN ausserhalb
        self._feld_achse = None
        self._kette: Verarbeitungskette | None = None
        self._anzeige_modus: str = "betrag"
        self._farbskala: str = "viridis"
        self._markierung = None
        self._marker_label = None
        self._aktueller_index = 0
        # Resonanz-Overlay.
        self._res_freq = None
        self._res_bres = None
        self._res_problem = None
        self._res_status = None        # Statusklasse je Punkt (farben.STATUS_*)
        self._res_info = None          # Tooltip-Text je Punkt
        self._res_nebenmoden = None    # Liste (mode, B_res-Array, Status) je weiterer Mode
        self._res_aktiv_mode = 1       # hervorgehobene Mode (Korridorliste)
        self._res_versteckt = set()    # Moden ohne Punkte im Overlay (Haekchen aus)
        self._problemfits_ausblenden = False
        self._ausreisser_anzeigen = False
        self._nebenmoden_anzeigen = True
        self._hover_index = None
        #: Zoom per Mausrad/Kaestchen nur, wenn eingeschaltet (Menue Ansicht -> Zoom);
        #: Standard AUS, weil der Rad-Zoom als zu empfindlich empfunden wurde.
        self._zoom_aktiv: bool = False
        # Maus-/Box-Zustand.
        self._press_xy = None
        self._box_aktiv = False
        self._box_corner = None
        self._box_patch = None
        # ZENTRALER Modus-Manager: hoechstens ein Modus aktiv (siehe MODI).
        self._modus: str | None = None
        self._modus_cb = None              # fertig(...) bzw. gewaehlt(indizes)
        # Zwei-Punkt-Modus (Korridor): gesammelte Klicks und ihre Marker.
        self._punkt_liste: list[tuple[float, float]] = []
        self._punkt_marker: list = []
        # Ausschlusszonen (Anzeige).
        self._zonen: list = []
        self._zonen_patches: list = []
        # Korridore (Anzeige + Anker-Drag).
        self._korridore = []
        self._korridor_aktiv = 1
        self._korridor_artists: list = []
        self._anker_cb = None              # (mode, anker_index, seite, b)
        self._drag_anker = None            # (korridor_index, anker_index, seite)
        # Ausreisser-Overlay-Zustand.
        self._res_ausgeschlossen = None
        # Hinweis-Banner (laufender Hintergrund-Job).
        self._hinweis_text: str | None = None
        self._hinweis_artist = None

        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("motion_notify_event", self._on_move)
        self.mpl_connect("button_release_event", self._on_release)
        self.mpl_connect("scroll_event", self._on_scroll)
        self.mpl_connect("key_press_event", self._on_key)
        self.mpl_connect("figure_leave_event", self._on_leave)

        self._zeichne_platzhalter()

    # --- Modus-Manager -------------------------------------------------------
    @property
    def modus(self) -> str | None:
        """Name des aktiven Interaktionsmodus (oder ``None``)."""
        return self._modus

    def starte_modus(self, name: str, callback) -> None:
        """Aktiviert einen Interaktionsmodus; ein laufender Modus wird beendet.

        ``callback`` haengt vom Modus ab:

        * ``"korridor"`` – ``callback(punkte)`` mit ``[(B1, f1_GHz), (B2, f2_GHz)]``
        * ``"anker"``    – ``callback((B, f_GHz))``, mehrfach (Modus bleibt aktiv)
        * ``"bereich"``  – ``callback(feld_min, feld_max, f_min_ghz, f_max_ghz)``
        * ``"zone"``     – ``callback(feld_min, feld_max, f_min_ghz, f_max_ghz)``
        * ``"ausreisser"`` – ``callback(indizes)``, mehrfach (Modus bleibt aktiv)
        """
        if name not in MODI:
            raise ValueError(f"Unbekannter Modus {name!r} (erlaubt: {MODI}).")
        if self._modus is not None:
            self._modus_aufraeumen()
        self._modus = name
        self._modus_cb = callback
        if name in _ZWEI_PUNKT_MODI:
            self._punkt_liste = []
        self.setCursor(_MODUS_CURSOR[name])
        # Tastaturfokus sicherstellen, damit Esc sofort wirkt (auch wenn der
        # Modus aus dem Menue gestartet wurde und der Canvas nie geklickt war).
        self.setFocus()
        self._melde_modus()

    def beende_modus(self) -> None:
        """Beendet den aktiven Modus (Abbruch oder Abschluss); meldet den Wechsel."""
        if self._modus is None:
            return
        self._modus_aufraeumen()
        self._melde_modus()

    def _modus_aufraeumen(self) -> None:
        """Setzt allen Modus-Zustand zurueck (ohne Meldung)."""
        self._modus = None
        self._modus_cb = None
        self._punkt_liste = []
        for m in self._punkt_marker:
            m.remove()
        if self._punkt_marker:
            self._punkt_marker = []
            self.draw_idle()
        self.unsetCursor()

    def _melde_modus(self) -> None:
        if self.modus_geaendert is not None:
            self.modus_geaendert(self._modus)

    # Bequeme Starter (von Hauptfenster/Tests verwendet).
    def starte_bereichs_fit(self, fertig) -> None:
        """Bereichs-Fit-Modus: naechstes Rechteck wird als Fit-Bereich gemeldet."""
        self.starte_modus("bereich", fertig)

    def starte_ausschluss_zeichnen(self, fertig) -> None:
        """Zonen-Modus: naechstes Rechteck wird als Ausschlusszone gemeldet."""
        self.starte_modus("zone", fertig)

    def starte_korridor_zeichnen(self, fertig) -> None:
        """Korridor-Modus: zwei Klicks entlang der Resonanz definieren die Linie
        eines neuen Korridors; ``fertig(punkte)`` erhaelt ``[(B1, f1_GHz), (B2, f2_GHz)]``.
        """
        self.starte_modus("korridor", fertig)

    def starte_anker_setzen(self, geklickt) -> None:
        """Anker-Modus: jeder Klick meldet ``geklickt((B, f_GHz))``; der Modus
        bleibt aktiv (Esc beendet)."""
        self.starte_modus("anker", geklickt)

    def setze_ausreisser_modus(self, an: bool, gewaehlt=None) -> None:
        """Schaltet den (dauerhaften) Ausreisser-Markiermodus um.

        Aktiv: ein Klick waehlt den naechstgelegenen sichtbaren Resonanzpunkt,
        ein aufgezogener Kasten alle Punkte darin; ``gewaehlt(indizes)`` wird
        mit den getroffenen Stapel-Indizes aufgerufen (Echtzeit, mehrfach).
        Zoom per Kasten ist waehrenddessen ausgesetzt.
        """
        if an:
            self.starte_modus("ausreisser", gewaehlt)
        elif self._modus == "ausreisser":
            self.beende_modus()

    def zeige(self, datensatz: Messdatensatz) -> None:
        """Stellt den Datensatz dar (Rohmatrix cachen, aktuelle Kette anwenden)."""
        self._datensatz = datensatz
        feld, freq, Z = datensatz.komplexe_matrix()
        self._feld_achse = feld
        self._Z_komplex = Z
        self._freq_achse = freq
        self._extent = (float(feld.min()), float(feld.max()),
                        float(freq.min() / 1e9), float(freq.max() / 1e9))
        self._res_freq = self._res_bres = self._res_problem = None
        self._res_status = self._res_info = self._res_nebenmoden = None
        self._res_ausgeschlossen = None
        self._hover_index = None
        self._press_xy = None
        self._box_aktiv = False
        # Neuer Datensatz: Overlays und Modi des alten verwerfen.
        self._zonen = []
        self._korridore = []
        self._drag_anker = None
        self.beende_modus()
        self._render()

    def setze_verarbeitung(self, kette: Verarbeitungskette | None,
                           anzeige_modus: str = "betrag") -> None:
        """Wendet eine (neue) Verarbeitungskette an; Zoom und Overlays bleiben.

        Die Kette rechnet immer auf der gecachten komplexen **Rohmatrix** –
        Parameteraenderungen spielen also nie auf bereits verarbeiteten Daten auf.
        """
        kette_alt, modus_alt = self._kette, self._anzeige_modus
        self._kette = kette
        self._anzeige_modus = anzeige_modus
        if self._Z_komplex is None:
            return
        self._neu_zeichnen_mit_overlays(kette_alt, modus_alt)

    def _neu_zeichnen_mit_overlays(self, kette_alt=None, modus_alt=None) -> None:
        """Neu rendern und Zoom, Resonanz-Overlay und Frequenzmarker erhalten."""
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        gezoomt = self._ist_gezoomt()
        index = self._aktueller_index
        hatte_marker = self._markierung is not None
        try:
            self._render()
        except ValueError:
            # Unzulaessige Parameter (z. B. Δn > halbes Gitter): alten Zustand
            # behalten; die Berechnung laeuft vor ax.clear(), der Plot ist intakt.
            if kette_alt is not None or modus_alt is not None:
                self._kette, self._anzeige_modus = kette_alt, modus_alt
            raise
        if gezoomt:
            self.ax.set_xlim(xlim)
            self.ax.set_ylim(ylim)
        if self._res_freq is not None:
            self._zeichne_resonanz()
        if hatte_marker and self._freq_achse is not None and len(self._freq_achse):
            self.markiere_frequenz(index)
        self.draw_idle()

    def setze_farbskala(self, name: str) -> None:
        """Farbskala (Matplotlib-Colormap-Name) des Falschfarbenbilds setzen."""
        self._farbskala = str(name) or "viridis"
        if self._Z_komplex is not None:
            self._neu_zeichnen_mit_overlays()

    def farbskala(self) -> str:
        return self._farbskala

    def layout_zuruecksetzen(self) -> None:
        """Zoom und Figur-Layout auf den Auslieferungszustand zuruecksetzen."""
        if self._Z_komplex is None:
            self._zeichne_platzhalter()
            return
        self._zoom_zuruecksetzen()
        self._neu_zeichnen_mit_overlays()

    def _zeichne_platzhalter(self) -> None:
        """Leeres kariertes Koordinatensystem, solange keine Daten geladen sind."""
        self.ax.clear()
        self.ax.set_xlim(0.0, 1.0)
        self.ax.set_ylim(0.0, 1.0)
        self.ax.set_xticks(np.linspace(0.0, 1.0, 11))
        self.ax.set_yticks(np.linspace(0.0, 1.0, 11))
        self.ax.set_xticklabels([])
        self.ax.set_yticklabels([])
        self.ax.tick_params(length=0)
        self.ax.grid(True, which="both", color=F.RAND, lw=0.8)
        self.ax.set_facecolor("#FCFCFD")
        for kante in self.ax.spines.values():
            kante.set_color(F.RAND_STARK)
        self.ax.set_xlabel(r"Feld $\mu_0 H$ (T)")
        self.ax.set_ylabel("Frequenz (GHz)")
        self.ax.text(0.5, 0.55, "Keine Messung geladen",
                     transform=self.ax.transAxes, ha="center", va="center",
                     fontsize=15, fontweight="bold", color=F.TEXT_SCHWACH)
        self.ax.text(0.5, 0.45,
                     "Datei → „TDMS laden …“ (Strg+O) öffnet eine Messung.\n"
                     "Danach lässt sich die Karte allein zur Datenansicht nutzen\n"
                     "(Verarbeitung: derivative divide, divide slice, …).",
                     transform=self.ax.transAxes, ha="center", va="center",
                     fontsize=10, color=F.TEXT_SCHWACH)
        self._tight_layout_sicher()
        self.draw_idle()

    def _render(self) -> None:
        """Zeichnet das Falschfarbenbild aus Rohmatrix + Kette + Anzeige-Modus neu."""
        feld, freq, Z = self._feld_achse, self._freq_achse, self._Z_komplex
        if Z is None:
            self._zeichne_platzhalter()
            return
        if self._kette is not None:
            feld, freq, Z = self._kette.anwenden(feld, freq, Z)
        matrix = anzeige_transform(Z, self._anzeige_modus)
        matrix = np.where(np.isfinite(matrix), matrix, np.nan)
        self._matrix = matrix

        self._markierung = self._marker_label = None
        self._box_patch = None
        # ax.clear() entsorgt alle Overlay-Artists - Referenzen VOR dem
        # Neuzeichnen verwerfen (remove() auf toten Artists wuerde werfen).
        self._zonen_patches = []
        self._punkt_marker = []
        self._korridor_artists = []
        self.ax.clear()
        self.ax.grid(False)
        # Robuste Farbgrenzen: einzelne Ausreisser (nach dd haeufig) duerfen die
        # Skala nicht dominieren, sonst ist die Mode nicht mit dem Auge erkennbar.
        endlich = matrix[np.isfinite(matrix)]
        vmin = vmax = None
        if endlich.size:
            vmin, vmax = np.percentile(endlich, _CLIM_PERZENTILE)
            if vmin == vmax:
                vmin = vmax = None
        try:
            self.ax.imshow(matrix, aspect="auto", origin="lower", cmap=self._farbskala,
                           extent=list(self._extent), vmin=vmin, vmax=vmax)
        except ValueError:  # unbekannter Colormap-Name -> Standard
            self._farbskala = "viridis"
            self.ax.imshow(matrix, aspect="auto", origin="lower", cmap=self._farbskala,
                           extent=list(self._extent), vmin=vmin, vmax=vmax)
        self.ax.set_autoscale_on(False)  # Overlays/Marker veraendern den Zoom nicht
        self.ax.set_xlabel(r"Feld $\mu_0 H$ (T)")
        self.ax.set_ylabel("Frequenz (GHz)")
        beschreibung = self._kette.beschreibung() if self._kette is not None else "roh"
        anzeige = ANZEIGE_MODI.get(self._anzeige_modus, self._anzeige_modus)
        if beschreibung == "roh":
            titel = f"Übersicht S21 roh · {anzeige}"
        else:
            titel = f"Übersicht S21: {beschreibung} · {anzeige}"
        # Titel darf das Layout nie breiter machen als die Achse: umbrechen.
        self.ax.set_title(titel, fontsize=10, wrap=True)
        hinweis = self.ax.text(
            0.5, -0.13,
            "klicken = Frequenz · Kästchen ziehen = Zoom · Mausrad = rein/raus · "
            "Doppelklick = zurück · ↑/↓ · ⇧+Rad · Punkt überfahren = Fit-Info",
            transform=self.ax.transAxes, ha="center", va="top",
            fontsize=7.2, color=F.TEXT_SCHWACH)
        # Vom Layout ausnehmen: sonst wuerde jeder tight_layout-Aufruf die
        # Achse an die Breite dieses Texts anpassen (Schrumpf-Bug).
        hinweis.set_in_layout(False)
        if self._zonen:
            self._zeichne_zonen()
        if self._korridore:
            self._zeichne_korridore()
        self._hinweis_artist = None
        if self._hinweis_text:
            self._zeichne_hinweis()
        self._tight_layout_sicher()
        self.draw_idle()

    def zeige_hinweis(self, text: str | None) -> None:
        """Banner oben im Farbplot (z. B. "Auto-Fit läuft … 120/1001"); ``None`` entfernt es."""
        self._hinweis_text = text or None
        if self._hinweis_artist is not None:
            try:
                self._hinweis_artist.remove()
            except (ValueError, AttributeError):
                pass
            self._hinweis_artist = None
        if self._hinweis_text:
            self._zeichne_hinweis()
        self.draw_idle()

    def _zeichne_hinweis(self) -> None:
        self._hinweis_artist = self.ax.text(
            0.5, 0.975, self._hinweis_text, transform=self.ax.transAxes,
            ha="center", va="top", fontsize=11, fontweight="bold", color=F.TEXT, zorder=20,
            bbox=dict(boxstyle="round,pad=0.45", facecolor=F.HELL_BLAU,
                      edgecolor=F.SIGNAL_BLAU, lw=1.5, alpha=0.96))
        self._hinweis_artist.set_in_layout(False)

    def thumbnail(self):
        """Liefert ``(matrix, extent)`` der gesamten Messung (fuer den Navigator)."""
        return self._matrix, self._extent

    def achsen(self):
        """Liefert ``(feld_achse, frequenz_achse)`` des Rohgitters (oder ``(None, None)``)."""
        return self._feld_achse, self._freq_achse

    def verarbeitete_matrix(self):
        """``(feld_achse, frequenz_achse, matrix)`` der aktuellen Anzeige (nach
        Verarbeitungskette und Anzeige-Modus) - fuer den Matrix-Export."""
        if self._matrix is None:
            return None, None, None
        return self._feld_achse, self._freq_achse, self._matrix

    def speichere_bild(self, pfad: str, dpi: int = 200) -> None:
        """Speichert den Farbplot samt Overlays als Bild (PNG/PDF/SVG nach Endung)."""
        self.figur.savefig(pfad, dpi=dpi, bbox_inches="tight", facecolor="white")

    def _tight_layout_sicher(self) -> None:
        """Layout berechnen, ohne dass die Achse bei wiederholten Aufrufen schrumpft.

        Vor jedem Aufruf werden die Figurraender auf die Standardwerte gesetzt -
        ``tight_layout`` rechnet dann immer vom gleichen Ausgangszustand aus
        (``ax.clear()`` setzt die Raender NICHT zurueck; ohne Reset addierte sich
        jeder Aufruf und der Plot wurde immer schmaler).
        """
        w, h = self.figur.get_size_inches() * self.figur.dpi
        if w < 1 or h < 1:
            return
        self.figur.subplots_adjust(**_RAENDER_STANDARD)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                self.figur.tight_layout()
        except (np.linalg.LinAlgError, ValueError):
            pass
        # Sicherheitsnetz: nie schmaler als ~55 % der Figur (winzige Canvases).
        pos = self.ax.get_position()
        if pos.width < 0.55 or pos.height < 0.45:
            self.figur.subplots_adjust(**_RAENDER_STANDARD)

    # --- Resonanz-Overlay --------------------------------------------------
    def aktualisiere_resonanz(self, frequenzen, B_res, problematisch=None,
                              ausgeschlossen=None, status=None, info=None,
                              nebenmoden=None, aktiv_mode: int = 1, versteckt=None) -> None:
        """Speichert und zeichnet die Resonanzpunkte nach Statusklasse.

        ``status`` (optional): Klasse je Punkt (``gut``/``bestaetigt``/
        ``problem``/``fehler``/``ignoriert``, siehe :mod:`polderfit.gui.farben`);
        fehlt es, wird aus ``problematisch`` abgeleitet. ``ausgeschlossen``
        (bool-Array) sind Ausreisser - unsichtbar, ausser *Ansicht -> Ausreisser
        anzeigen* ist an. ``info`` (optional): Tooltip-Text je Punkt.
        ``nebenmoden``: Liste ``(mode, B_res-Array, Status-Array)`` weiterer
        Moden (Korridor-Fits; NaN, wo keine).
        """
        if self._datensatz is None:
            return
        self._res_freq = np.asarray(frequenzen, dtype=float)
        self._res_bres = np.asarray(B_res, dtype=float)
        n = self._res_freq.shape
        self._res_problem = (np.zeros(n, dtype=bool) if problematisch is None
                             else np.asarray(problematisch, dtype=bool))
        self._res_ausgeschlossen = (np.zeros(n, dtype=bool) if ausgeschlossen is None
                                    else np.asarray(ausgeschlossen, dtype=bool))
        if status is None:
            status = np.where(self._res_problem, "problem", "gut")
        self._res_status = np.asarray(status, dtype=object)
        self._res_info = list(info) if info is not None else None
        self._res_nebenmoden = ([(int(m), np.asarray(b, dtype=float), np.asarray(st, dtype=object))
                                 for m, b, st in nebenmoden] if nebenmoden else None)
        self._res_aktiv_mode = int(aktiv_mode)
        self._res_versteckt = set(int(m) for m in (versteckt or ()))
        self._hover_index = None
        self._zeichne_resonanz()

    def setze_problemfits_ausblenden(self, an: bool) -> None:
        self._problemfits_ausblenden = bool(an)
        self._zeichne_resonanz()

    def setze_ausreisser_anzeigen(self, an: bool) -> None:
        """Ignorierte Punkte (Ausreisser) als graue Ringe zeigen statt ausblenden."""
        self._ausreisser_anzeigen = bool(an)
        self._zeichne_resonanz()

    def setze_nebenmoden_anzeigen(self, an: bool) -> None:
        self._nebenmoden_anzeigen = bool(an)
        self._zeichne_resonanz()

    def _status_sichtbar(self, status: str) -> bool:
        if status == "ignoriert":
            return self._ausreisser_anzeigen
        if status in ("problem", "fehler"):
            return not self._problemfits_ausblenden
        return True

    def _zeichne_resonanz(self) -> None:
        if self._res_freq is None:
            return
        for ln in list(self.ax.lines):
            if str(ln.get_label()).startswith("_resonanz"):
                ln.remove()
        f_ghz = self._res_freq / 1e9
        status = self._status_array()
        # Nicht hervorgehobene Moden blass zeichnen (Auswahl in der Korridorliste).
        alpha_m1 = 1.0 if self._res_aktiv_mode == 1 or not self._res_nebenmoden else 0.35
        for klasse in ("ignoriert", "fehler", "problem", "gut", "bestaetigt"):
            if 1 in self._res_versteckt:
                break
            maske = (status == klasse) & np.isfinite(self._res_bres)
            if not maske.any() or not self._status_sichtbar(klasse):
                continue
            fuell, rand = F.STATUS_FARBEN[klasse]
            marker = F.STATUS_MARKER[klasse]
            if klasse == "ignoriert":
                # Grau gefuellt mit dunklem Rand: auf jedem Untergrund erkennbar.
                self.ax.plot(self._res_bres[maske], f_ghz[maske], marker, color=fuell,
                             mec=rand, ms=6, mew=0.9, ls="", label=_STATUS_LABEL[klasse], alpha=alpha_m1)
            elif klasse == "bestaetigt":
                self.ax.plot(self._res_bres[maske], f_ghz[maske], marker, color=fuell,
                             mec=rand, ms=6.5, mew=1.6, ls="", label=_STATUS_LABEL[klasse], alpha=alpha_m1)
            elif klasse == "fehler":
                self.ax.plot(self._res_bres[maske], f_ghz[maske], marker, color=fuell,
                             mec=rand, ms=7, mew=0.8, ls="", label=_STATUS_LABEL[klasse], alpha=alpha_m1)
            else:
                self.ax.plot(self._res_bres[maske], f_ghz[maske], marker, color=fuell,
                             mec=rand, ms=6 if klasse == "gut" else 7, mew=0.9, ls="",
                             label=_STATUS_LABEL[klasse], alpha=alpha_m1)
        if self._nebenmoden_anzeigen and self._res_nebenmoden:
            # Weitere Moden: runde Punkte in der Mode-Farbe; Problemfits als
            # Dreieck (wie Mode 1), ignorierte grau - dieselbe Sichtbarkeitslogik.
            for mode, moden_b, moden_status in self._res_nebenmoden:
                if int(mode) in self._res_versteckt:
                    continue
                farbe = F.mode_farbe(mode)
                aktiv = int(mode) == self._res_aktiv_mode
                alpha_k = 1.0 if aktiv else 0.35
                for klasse in ("ignoriert", "fehler", "problem", "gut", "bestaetigt"):
                    maske = (moden_status == klasse) & np.isfinite(moden_b)
                    if not maske.any() or not self._status_sichtbar(klasse):
                        continue
                    if klasse == "ignoriert":
                        fuell, rand = F.STATUS_FARBEN["ignoriert"]
                        self.ax.plot(moden_b[maske], f_ghz[maske], "o", color=fuell, mec=rand,
                                     ms=5.5, mew=0.9, ls="", label="_resonanz_nebenmode",
                                     alpha=alpha_k)
                    elif klasse in ("problem", "fehler"):
                        self.ax.plot(moden_b[maske], f_ghz[maske], F.STATUS_MARKER[klasse],
                                     color=F.STATUS_FARBEN[klasse][0], mec=farbe, ms=7, mew=1.2,
                                     ls="", label="_resonanz_nebenmode", alpha=alpha_k)
                    else:
                        # Keine weissen Raender: bei dichten Punkten wuerden sie das
                        # Overlay als weisses Band ueberdecken.
                        self.ax.plot(moden_b[maske], f_ghz[maske], "o", color=farbe, mec=farbe,
                                     ms=6 if aktiv else 5, mew=0.6 if klasse == "gut" else 1.4,
                                     ls="", label="_resonanz_nebenmode", alpha=alpha_k)
        self.draw_idle()

    def _status_array(self) -> np.ndarray:
        """Statusklassen unter Beruecksichtigung der Ausreisser-Maske."""
        status = (self._res_status.copy() if self._res_status is not None
                  else np.where(self._res_problem, "problem", "gut").astype(object))
        if self._res_ausgeschlossen is not None:
            status[self._res_ausgeschlossen] = "ignoriert"
        return status

    # --- Frequenz-Markierung ----------------------------------------------
    def markiere_frequenz(self, index: int) -> None:
        if self._freq_achse is None or len(self._freq_achse) == 0:
            return
        index = int(np.clip(index, 0, len(self._freq_achse) - 1))
        self._aktueller_index = index
        if self._markierung is not None:
            self._markierung.remove()
            self._markierung = None
        if self._marker_label is not None:
            self._marker_label.remove()
            self._marker_label = None
        f_ghz = self._freq_achse[index] / 1e9
        self._markierung = self.ax.axhline(f_ghz, color="white", lw=1.8, ls="--", zorder=6)
        self._markierung.set_path_effects(
            [pe.Stroke(linewidth=3.4, foreground="#00000088"), pe.Normal()])
        self._marker_label = self.ax.annotate(
            f"{f_ghz:.2f} GHz", xy=(0.0, f_ghz), xycoords=("axes fraction", "data"),
            xytext=(5, 3), textcoords="offset points", color="white", fontsize=8,
            fontweight="bold", zorder=7,
            path_effects=[pe.Stroke(linewidth=2.2, foreground="#00000099"), pe.Normal()])
        self.draw_idle()

    def markiere_frequenz_wert(self, f_hz: float) -> None:
        """Markiert die dem Wert naechstgelegene Frequenz (wertbasiert statt Index).

        Noetig, weil der Fit-Stapel durch die Auswertungsauswahl (Jumper)
        weniger Frequenzen enthalten kann als die angezeigte Matrix.
        """
        if self._freq_achse is None or len(self._freq_achse) == 0:
            return
        self.markiere_frequenz(int(np.argmin(np.abs(self._freq_achse - f_hz))))

    def _waehle_index(self, index: int) -> None:
        """Markiert ``index`` und meldet die Auswahl (laedt damit den Fit)."""
        if self._freq_achse is None or len(self._freq_achse) == 0:
            return
        index = int(np.clip(index, 0, len(self._freq_achse) - 1))
        if index == self._aktueller_index and self._markierung is not None:
            return
        self.markiere_frequenz(index)
        if self.frequenz_gewaehlt is not None:
            self.frequenz_gewaehlt(index)

    def _index_aus_y(self, ydata: float) -> int:
        return int(np.argmin(np.abs(self._freq_achse / 1e9 - ydata)))

    # --- Zoom --------------------------------------------------------------
    def setze_zoom_aktiv(self, aktiv: bool) -> None:
        """Mausrad-/Kaestchen-Zoom ein-/ausschalten (Doppelklick/Tasten +,-,0 bleiben)."""
        self._zoom_aktiv = bool(aktiv)
        if not self._zoom_aktiv and self._modus is None:
            self.unsetCursor()

    def zoom_aktiv(self) -> bool:
        return self._zoom_aktiv

    def _melde_zoom(self) -> None:
        if self.zoom_geaendert is not None:
            self.zoom_geaendert(self.ax.get_xlim(), self.ax.get_ylim(), self._ist_gezoomt())

    def _ist_gezoomt(self) -> bool:
        if self._extent is None:
            return False
        fx0, fx1, fy0, fy1 = self._extent
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        eps = 1e-6
        return bool((abs(x1 - x0) < abs(fx1 - fx0) - eps)
                    or (abs(y1 - y0) < abs(fy1 - fy0) - eps))

    def sichtbarer_bereich(self) -> tuple[float, float, float, float] | None:
        """``(feld_min, feld_max, f_min_ghz, f_max_ghz)`` des sichtbaren Ausschnitts,
        wenn gezoomt ist - sonst ``None`` (ganzer Datenbereich). Vorbelegung der
        ROI im Auto-Fit-Dialog."""
        if self._extent is None or not self._ist_gezoomt():
            return None
        x0, x1 = sorted(float(v) for v in self.ax.get_xlim())
        y0, y1 = sorted(float(v) for v in self.ax.get_ylim())
        return (x0, x1, y0, y1)

    def _zoom(self, event, faktor: float) -> None:
        if self._extent is None:
            return
        fx0, fx1, fy0, fy1 = self._extent
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        xc = event.xdata if event.xdata is not None else 0.5 * (x0 + x1)
        yc = event.ydata if event.ydata is not None else 0.5 * (y0 + y1)
        self.ax.set_xlim(*self._klemme(xc + (x0 - xc) * faktor, xc + (x1 - xc) * faktor, fx0, fx1))
        self.ax.set_ylim(*self._klemme(yc + (y0 - yc) * faktor, yc + (y1 - yc) * faktor, fy0, fy1))
        self.draw_idle()
        self._melde_zoom()

    def setze_ansicht(self, xlim, ylim) -> None:
        """Setzt den sichtbaren Ausschnitt (vom Navigator aufgerufen)."""
        if self._extent is None:
            return
        fx0, fx1, fy0, fy1 = self._extent
        self.ax.set_xlim(*self._klemme(min(xlim), max(xlim), fx0, fx1))
        self.ax.set_ylim(*self._klemme(min(ylim), max(ylim), fy0, fy1))
        self.draw_idle()
        self._melde_zoom()

    def _zoom_zuruecksetzen(self) -> None:
        if self._extent is None:
            return
        fx0, fx1, fy0, fy1 = self._extent
        self.ax.set_xlim(fx0, fx1)
        self.ax.set_ylim(fy0, fy1)
        self.draw_idle()
        self._melde_zoom()

    @staticmethod
    def _klemme(lo, hi, vmin, vmax):
        if hi - lo >= vmax - vmin:
            return vmin, vmax
        if lo < vmin:
            hi += vmin - lo
            lo = vmin
        if hi > vmax:
            lo -= hi - vmax
            hi = vmax
        return max(lo, vmin), min(hi, vmax)

    # --- Aufzieh-Kaestchen -------------------------------------------------
    def _schwelle(self):
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        return _BOX_SCHWELLE_REL * abs(x1 - x0), _BOX_SCHWELLE_REL * abs(y1 - y0)

    def _zeichne_box(self):
        if self._box_corner is None:
            return
        x0, y0, x1, y1 = self._box_corner
        if self._box_patch is None:
            self._box_patch = self.ax.add_patch(Rectangle(
                (min(x0, x1), min(y0, y1)), abs(x1 - x0), abs(y1 - y0),
                facecolor=F.SIGNAL_BLAU + "33", edgecolor=F.SIGNAL_BLAU, lw=1.4, zorder=8))
        else:
            self._box_patch.set_bounds(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
        self.draw_idle()

    def _entferne_box(self):
        if self._box_patch is not None:
            self._box_patch.remove()
            self._box_patch = None
        self.draw_idle()

    def _auf_box_zoom(self, x0, y0, x1, y1):
        if self._extent is None:
            return
        fx0, fx1, fy0, fy1 = self._extent
        nx = self._klemme(min(x0, x1), max(x0, x1), fx0, fx1)
        ny = self._klemme(min(y0, y1), max(y0, y1), fy0, fy1)
        if nx[1] - nx[0] < 1e-9 or ny[1] - ny[0] < 1e-9:
            return
        self.ax.set_xlim(*nx)
        self.ax.set_ylim(*ny)
        self.draw_idle()
        self._melde_zoom()

    # --- Ausschlusszonen (Anzeige) ------------------------------------------
    def zeige_ausschlusszonen(self, zonen) -> None:
        """Zeichnet die Ausschlusszonen als schraffierte Rechtecke."""
        self._zonen = list(zonen)
        self._zeichne_zonen()

    def _zeichne_zonen(self) -> None:
        for patch in self._zonen_patches:
            patch.remove()
        self._zonen_patches = []
        for zone in self._zonen:
            patch = self.ax.add_patch(Rectangle(
                (zone.feld_min, zone.frequenz_min / 1e9),
                zone.feld_max - zone.feld_min,
                (zone.frequenz_max - zone.frequenz_min) / 1e9,
                facecolor="#00000000", edgecolor=F.SIGNAL_ROT, hatch="///",
                lw=1.2, zorder=6, label="_ausschlusszone"))
            self._zonen_patches.append(patch)
        self.draw_idle()

    # --- Korridore (Anzeige + Anker-Drag) --------------------------------------
    def zeige_korridore(self, korridore, aktiv: int = 1, anker_geaendert=None) -> None:
        """Zeichnet die Korridore (Feldband je Mode entlang der Frequenz).

        ``korridore``: :class:`polderfit.fit.korridor.Korridor`-Objekte; ``aktiv``:
        Mode-Nummer des hervorgehobenen Korridors. Anker sind waagerecht ziehbar;
        nach dem Loslassen wird ``anker_geaendert(mode, anker_index, seite, b)``
        gerufen (``seite`` = ``"links"``/``"rechts"``).
        """
        self._korridore = list(korridore)
        self._korridor_aktiv = int(aktiv)
        if anker_geaendert is not None:
            self._anker_cb = anker_geaendert
        self._zeichne_korridore()

    def _fraktion(self, x: float, y: float) -> tuple[float, float]:
        """Datenkoordinaten (T, GHz) -> Achsen-Anteile des Extents."""
        fx0, fx1, fy0, fy1 = self._extent
        return ((x - fx0) / (fx1 - fx0 or 1.0), (y - fy0) / (fy1 - fy0 or 1.0))

    def _korridor_polygon(self, korridor):
        """Stuetzstellen (f_GHz, links, rechts) des Korridors ueber den Extent."""
        fx0, fx1, fy0, fy1 = self._extent
        f_stuetz = sorted({fy0, fy1} | {a.f / 1e9 for a in korridor.anker
                                        if fy0 <= a.f / 1e9 <= fy1})
        punkte = []
        for f_ghz in f_stuetz:
            g = korridor.grenzen(f_ghz * 1e9)
            if g is None:
                continue
            punkte.append((f_ghz, g[0], g[1]))
        return punkte

    def _zeichne_korridore(self) -> None:
        from matplotlib.patches import Polygon
        for artist in self._korridor_artists:
            artist.remove()
        self._korridor_artists = []
        if self._extent is None or not self._korridore:
            self.draw_idle()
            return
        for korridor in self._korridore:
            mode = int(korridor.mode)
            aktiv = mode == self._korridor_aktiv
            farbe = _MODE_FARBEN.get(mode, F.TEXT) if mode > 1 else F.TEXT
            punkte = self._korridor_polygon(korridor)
            if len(punkte) >= 2:
                ecken = ([(li, f) for f, li, _re in punkte]
                         + [(re, f) for f, _li, re in reversed(punkte)])
                patch = self.ax.add_patch(Polygon(
                    ecken, closed=True, facecolor=farbe, edgecolor="none",
                    alpha=_KORRIDOR_ALPHA_AKTIV if aktiv else _KORRIDOR_ALPHA,
                    zorder=5, label="_korridor"))
                self._korridor_artists.append(patch)
                for seite in (1, 2):
                    linie = self.ax.plot([p[seite] for p in punkte], [p[0] for p in punkte],
                                         "-", color=farbe, lw=1.8 if aktiv else 1.1,
                                         zorder=6, label="_korridor_rand")[0]
                    linie.set_path_effects(
                        [pe.Stroke(linewidth=3.0, foreground="#FFFFFFAA"), pe.Normal()])
                    self._korridor_artists.append(linie)
                fm, lm, rm = punkte[len(punkte) // 2]
                text = self.ax.text(0.5 * (lm + rm), fm, f"M{mode}", color=farbe,
                                    fontsize=8, fontweight="bold", ha="center",
                                    va="bottom", zorder=7, label="_korridor_mode")
                text.set_path_effects(
                    [pe.Stroke(linewidth=2.5, foreground="#FFFFFFCC"), pe.Normal()])
                self._korridor_artists.append(text)
            if getattr(korridor, "n_dips", 1) > 1 and len(punkte) >= 2:
                stuetz = [p[0] for p in punkte]
                trenn = [korridor.trennstellen(f_ghz * 1e9) for f_ghz in stuetz]
                if all(t is not None for t in trenn):
                    for j in range(len(trenn[0])):
                        linie = self.ax.plot([t[j] for t in trenn], stuetz, "--",
                                             color="#D4A500", lw=1.4 if aktiv else 1.0,
                                             zorder=6, label="_korridor_trenner")[0]
                        linie.set_path_effects(
                            [pe.Stroke(linewidth=2.6, foreground="#FFFFFFAA"), pe.Normal()])
                        self._korridor_artists.append(linie)
            if korridor.anker:
                xs = [a.b_links for a in korridor.anker] + [a.b_rechts for a in korridor.anker]
                ys = [a.f / 1e9 for a in korridor.anker] * 2
                griffe = self.ax.plot(xs, ys, "s", color=F.SIGNAL_BLAU if aktiv else farbe,
                                      mec="white", mew=1.2, ms=8 if aktiv else 6, ls="",
                                      zorder=9, label="_korridor_anker")[0]
                self._korridor_artists.append(griffe)
        self.draw_idle()

    def _finde_anker_griff(self, event):
        """``(korridor_index, anker_index, seite)`` des Ankers nahe der Maus, sonst None."""
        if not self._korridore or self._extent is None:
            return None
        if event.xdata is None or event.ydata is None:
            return None
        eu, ev = self._fraktion(event.xdata, event.ydata)
        bester = None
        bester_abstand = _GRIFF_TOLERANZ
        for ki, korridor in enumerate(self._korridore):
            for ai, anker in enumerate(korridor.anker):
                for seite, bb in (("links", anker.b_links), ("rechts", anker.b_rechts)):
                    u, v = self._fraktion(float(bb), float(anker.f) / 1e9)
                    abstand = float(np.hypot(eu - u, ev - v))
                    if abstand <= bester_abstand:
                        bester = (ki, ai, seite)
                        bester_abstand = abstand
        return bester

    def _anker_bewegen(self, event) -> None:
        ki, ai, seite = self._drag_anker
        if event.xdata is None or ki >= len(self._korridore):
            return
        korridor = self._korridore[ki]
        if ai >= len(korridor.anker):
            return
        korridor.anker_verschieben(ai, seite, float(event.xdata))
        self._zeichne_korridore()

    # --- Punkte finden (Hover / Ausreisser) ----------------------------------
    def _sichtbare_resonanzpunkte(self) -> np.ndarray:
        """Indizes der aktuell im Overlay gezeichneten Resonanzpunkte."""
        if self._res_freq is None:
            return np.array([], dtype=int)
        status = self._status_array()
        sichtbar = np.isfinite(self._res_bres)
        for klasse in ("gut", "bestaetigt", "problem", "fehler", "ignoriert"):
            if not self._status_sichtbar(klasse):
                sichtbar &= status != klasse
        return np.flatnonzero(sichtbar)

    def _naechster_punkt(self, event, toleranz: float = _PUNKT_TOLERANZ):
        """Index des naechsten sichtbaren Resonanzpunkts (relativ zur Achsenspanne)."""
        kandidaten = self._sichtbare_resonanzpunkte()
        if kandidaten.size == 0 or event.xdata is None or event.ydata is None:
            return None
        # Abstand in relativen Achseneinheiten (Feld- und Frequenzspanne
        # unterscheiden sich um Groessenordnungen).
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        dx = (self._res_bres[kandidaten] - event.xdata) / max(abs(x1 - x0), 1e-12)
        dy = (self._res_freq[kandidaten] / 1e9 - event.ydata) / max(abs(y1 - y0), 1e-12)
        abstand = np.hypot(dx, dy)
        naechster = int(np.argmin(abstand))
        if abstand[naechster] <= toleranz:
            return int(kandidaten[naechster])
        return None

    def _hover(self, event) -> None:
        """Tooltip mit Fit-Kennzahlen, wenn die Maus ueber einem Punkt steht."""
        index = self._naechster_punkt(event) if self._res_info is not None else None
        if index == self._hover_index:
            return
        self._hover_index = index
        try:
            if index is None:
                QtWidgets.QToolTip.hideText()
            else:
                QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self._res_info[index], self)
        except Exception:  # z. B. ohne Fenster/Display – reine Anzeigehilfe
            pass

    def _ausreisser_klick(self, event) -> None:
        """Klick im Ausreisser-Modus: naechstgelegenen sichtbaren Punkt melden."""
        index = self._naechster_punkt(event)
        if index is not None and self._modus_cb is not None:
            self._modus_cb([index])

    def _ausreisser_kasten(self, x0, y0, x1, y1) -> None:
        """Kasten im Ausreisser-Modus: alle sichtbaren Punkte darin melden."""
        kandidaten = self._sichtbare_resonanzpunkte()
        if kandidaten.size == 0:
            return
        b = self._res_bres[kandidaten]
        f_ghz = self._res_freq[kandidaten] / 1e9
        drin = ((b >= min(x0, x1)) & (b <= max(x0, x1))
                & (f_ghz >= min(y0, y1)) & (f_ghz <= max(y0, y1)))
        if drin.any() and self._modus_cb is not None:
            self._modus_cb([int(i) for i in kandidaten[drin]])

    # --- Modus-Abschluesse ----------------------------------------------------
    def _rechteck_abschliessen(self, x0, y0, x1, y1) -> None:
        """Beendet Bereichs-/Zonen-Modus mit dem aufgezogenen Rechteck."""
        fertig = self._modus_cb
        self.beende_modus()
        if fertig is not None:
            fertig(min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1))

    def _zwei_punkt_klick(self, event) -> None:
        """Zwei-Punkt-Modus (Korridor): Klicks sammeln, nach dem zweiten melden."""
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            return
        self._punkt_liste.append((float(event.xdata), float(event.ydata)))  # (B [T], f [GHz])
        mk = self.ax.plot([event.xdata], [event.ydata], "P", color=F.SIGNAL_BLAU,
                          mec="white", mew=1.2, ms=12, zorder=9)[0]
        self._punkt_marker.append(mk)
        self.draw_idle()
        if len(self._punkt_liste) >= 2:
            fertig = self._modus_cb
            punkte = list(self._punkt_liste)
            self.beende_modus()
            if fertig is not None:
                fertig(punkte)

    # --- Maus / Tastatur ---------------------------------------------------
    def _on_press(self, event):
        if event.inaxes != self.ax or self._freq_achse is None:
            return
        self.setFocus()
        if self._modus in _ZWEI_PUNKT_MODI:   # Korridor: Klick sammelt Punkte
            self._zwei_punkt_klick(event)
            return
        if self._modus == "anker":
            if event.xdata is not None and event.ydata is not None and self._modus_cb is not None:
                self._modus_cb((float(event.xdata), float(event.ydata)))
            return
        if getattr(event, "dblclick", False):
            self._press_xy = None
            self._zoom_zuruecksetzen()
            return
        # Anker eines Korridors anfassen (nur ausserhalb der Modi).
        if self._modus is None:
            griff = self._finde_anker_griff(event)
            if griff is not None:
                self._drag_anker = griff
                self.setCursor(QtCore.Qt.ClosedHandCursor)
                return
        if event.xdata is None or event.ydata is None:
            return
        self._press_xy = (event.xdata, event.ydata)
        self._box_aktiv = False
        self._box_corner = None

    def _on_move(self, event):
        if self._drag_anker is not None:
            if event.inaxes == self.ax:
                self._anker_bewegen(event)
            return
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            if not self._box_aktiv:
                self._setze_ruhe_cursor(ausserhalb=True)
                self._hover(event)
            return
        if self._press_xy is None and self._modus is None \
                and self._finde_anker_griff(event) is not None:
            self.setCursor(QtCore.Qt.OpenHandCursor)   # Griff in Reichweite
            return
        if self._press_xy is not None:
            if self._modus is None and not self._zoom_aktiv:
                return                       # kein Zoom-Kaestchen: Klick waehlt nur die Frequenz
            x0, y0 = self._press_xy
            if not self._box_aktiv:
                sx, sy = self._schwelle()
                if abs(event.xdata - x0) > sx or abs(event.ydata - y0) > sy:
                    self._box_aktiv = True
            if self._box_aktiv:
                self._box_corner = (x0, y0, event.xdata, event.ydata)
                self._zeichne_box()
            return
        self._setze_ruhe_cursor()
        if self._modus in (None, "ausreisser"):
            self._hover(event)

    def _setze_ruhe_cursor(self, ausserhalb: bool = False) -> None:
        """Cursor ausserhalb von Drags: Modus-Cursor halten, sonst Standard."""
        if self._modus is not None:
            self.setCursor(_MODUS_CURSOR[self._modus])
        elif ausserhalb or not self._zoom_aktiv:
            self.unsetCursor()
        else:
            self.setCursor(QtCore.Qt.CrossCursor)  # Hinweis: Kästchen aufziehbar

    def _on_release(self, event):
        if self._drag_anker is not None:
            ki, ai, seite = self._drag_anker
            self._drag_anker = None
            self.unsetCursor()
            if ki < len(self._korridore) and self._anker_cb is not None:
                k = self._korridore[ki]
                if ai < len(k.anker):
                    b = k.anker[ai].b_links if seite == "links" else k.anker[ai].b_rechts
                    self._anker_cb(int(k.mode), ai, seite, float(b))
            return
        if self._press_xy is None:
            return
        war_box = self._box_aktiv
        box = self._box_corner
        self._press_xy = None
        self._box_aktiv = False
        self._box_corner = None
        self._entferne_box()
        if war_box and box is not None:
            if self._modus == "zone":
                self._rechteck_abschliessen(*box)    # Ausschlusszone einzeichnen
            elif self._modus == "bereich":
                self._rechteck_abschliessen(*box)    # Bereichs-Fit statt Zoom
            elif self._modus == "ausreisser":
                self._ausreisser_kasten(*box)        # Ausreisser gemeinsam markieren
            else:
                self._auf_box_zoom(*box)
        elif event.inaxes == self.ax and event.ydata is not None:
            if self._modus == "ausreisser":
                self._ausreisser_klick(event)        # Einzelpunkt markieren
            else:
                self._waehle_index(self._index_aus_y(event.ydata))

    def _on_leave(self, event):
        if self._modus is None:
            self.unsetCursor()
        self._hover_index = None
        try:
            QtWidgets.QToolTip.hideText()
        except Exception:
            pass

    def _on_scroll(self, event):
        if self._freq_achse is None:
            return
        modifier = getattr(event, "key", None) or ""
        if "shift" in modifier:
            self._waehle_index(self._aktueller_index + (1 if event.step > 0 else -1))
        elif self._zoom_aktiv:
            self._zoom(event, _ZOOM_REIN if event.step > 0 else _ZOOM_RAUS)

    def _on_key(self, event):
        if event.key == "escape" and self._modus is not None:
            self.beende_modus()
            return
        if self._freq_achse is None:
            return
        n = len(self._freq_achse)
        spruenge = {"up": +1, "right": +1, "down": -1, "left": -1,
                    "pageup": +10, "pagedown": -10}
        if event.key in spruenge:
            self._waehle_index(self._aktueller_index + spruenge[event.key])
        elif event.key == "home":
            self._waehle_index(0)
        elif event.key == "end":
            self._waehle_index(n - 1)
        elif event.key in ("+", "="):
            self._zoom(event, _ZOOM_REIN)
        elif event.key == "-":
            self._zoom(event, _ZOOM_RAUS)
        elif event.key in ("0", "r"):
            self._zoom_zuruecksetzen()

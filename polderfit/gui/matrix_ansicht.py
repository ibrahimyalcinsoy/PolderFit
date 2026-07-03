# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""2D-Uebersicht: Magnituden-Matrix (Frequenz vs. Feld) mit Resonanzverlauf.

Zeigt die gesamte Messung als Falschfarbenbild, ueberlagert die gefitteten
Resonanzfelder und markiert die aktuell gewaehlte Frequenz mit einer horizontalen
Linie.

Bedienung:

* **Klicken** – springt zur naechstgelegenen Frequenz (laedt sofort deren Fit),
* **Aufziehen (Kaestchen)** – zoomt auf den markierten Bereich,
* **Mausrad** – rein/raus zoomen (zentriert auf den Cursor),
* **Umschalt + Mausrad** – eine Frequenz hoch/runter,
* **Doppelklick** – Zoom zuruecksetzen (ganze Messung),
* **Pfeiltasten** ``hoch/runter`` (bzw. ``links/rechts``), ``Bild hoch/runter``
  (10er-Schritt), ``Pos1/Ende`` (erste/letzte Frequenz); ``+/-/0`` zoomen.

Jede Frequenzauswahl meldet den Index ueber ``frequenz_gewaehlt(index)``; Zoom-
Aenderungen melden ``zoom_geaendert(xlim, ylim, ist_gezoomt)`` (fuer den Navigator).
Problematische Fits lassen sich im Resonanz-Overlay optional ausblenden.
"""

from __future__ import annotations

import numpy as np
import matplotlib.patheffects as pe
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6 import QtCore

from ..io.datensatz import Messdatensatz
from ..verarbeitung import ANZEIGE_MODI, Verarbeitungskette, anzeige_transform

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


class MatrixAnsicht(FigureCanvasQTAgg):
    """Falschfarben-Uebersicht der Magnitude mit Resonanz-Overlay und Zoom."""

    def __init__(self, frequenz_gewaehlt=None, zoom_geaendert=None):
        self.figur = Figure(figsize=(5, 5))
        super().__init__(self.figur)
        self.ax = self.figur.add_subplot(111)
        self.frequenz_gewaehlt = frequenz_gewaehlt
        self.zoom_geaendert = zoom_geaendert
        self._datensatz: Messdatensatz | None = None
        self._matrix = None
        self._freq_achse = None
        self._extent = None            # (feld_min, feld_max, f_min_GHz, f_max_GHz)
        # Verarbeitungskette: gecachte komplexe Rohmatrix + aktueller Zustand.
        self._Z_komplex = None         # (n_freq, n_feld), komplex, NaN ausserhalb
        self._feld_achse = None
        self._kette: Verarbeitungskette | None = None
        self._anzeige_modus: str = "betrag"
        self._markierung = None
        self._marker_label = None
        self._aktueller_index = 0
        # Resonanz-Overlay.
        self._res_freq = None
        self._res_bres = None
        self._res_problem = None
        self._problemfits_ausblenden = False
        # Maus-/Box-Zustand.
        self._press_xy = None
        self._box_aktiv = False
        self._box_corner = None
        self._box_patch = None
        # Dispersions-Seed: zwei Klicks auf die Resonanz vorgeben.
        self._seed_fertig = None
        self._seed_punkte: list[tuple[float, float]] = []
        self._seed_marker: list = []
        # Bereichs-Fit-Modus: naechstes aufgezogenes Rechteck neu fitten statt zoomen.
        self._bereich_fertig = None
        # Fenstergrenzen-Overlay (interaktives In-Plot-Fitting): zwei ziehbare
        # Polylinien links/rechts der Resonanz; nur der Bereich dazwischen fittet.
        self._grenzen_freq = None          # Hz-Array der Stapel-Frequenzen
        self._grenzen_fenster = None       # list[(unten, oben)] je Stapel-Index
        self._grenzen_sichtbar = False
        self._grenze_gezogen = None        # Callback(index, seite, neuer_feldwert)
        self._grenzen_linien: dict = {}    # "links"/"rechts" -> Line2D
        self._drag_grenze = None           # (seite, index) waehrend des Ziehens
        # Ausschlusszonen: Anzeige + Zeichenmodus.
        self._zonen: list = []
        self._zonen_patches: list = []
        self._ausschluss_fertig = None
        # Ausreisser-Markiermodus: Klick/Kasten waehlt Resonanzpunkte aus.
        self._res_ausgeschlossen = None
        self._ausreisser_aktiv = False
        self._ausreisser_gewaehlt = None   # Callback(liste_von_indizes)

        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("motion_notify_event", self._on_move)
        self.mpl_connect("button_release_event", self._on_release)
        self.mpl_connect("scroll_event", self._on_scroll)
        self.mpl_connect("key_press_event", self._on_key)
        self.mpl_connect("figure_leave_event", self._on_leave)

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
        self._press_xy = None
        self._box_aktiv = False
        # Neuer Datensatz: Overlays des alten (Grenzen, Zonen, Modi) verwerfen.
        self._grenzen_freq = None
        self._grenzen_fenster = None
        self._grenzen_sichtbar = False
        self._drag_grenze = None
        self._zonen = []
        self._bereich_fertig = None
        self._ausschluss_fertig = None
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
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        gezoomt = self._ist_gezoomt()
        index = self._aktueller_index
        hatte_marker = self._markierung is not None
        res = (self._res_freq, self._res_bres, self._res_problem)
        try:
            self._render()
        except ValueError:
            # Unzulaessige Parameter (z. B. Δn > halbes Gitter): alten Zustand
            # behalten; die Berechnung laeuft vor ax.clear(), der Plot ist intakt.
            self._kette, self._anzeige_modus = kette_alt, modus_alt
            raise
        if gezoomt:
            self.ax.set_xlim(xlim)
            self.ax.set_ylim(ylim)
        if res[0] is not None:
            self._res_freq, self._res_bres, self._res_problem = res
            self._zeichne_resonanz()
        if hatte_marker and self._freq_achse is not None and len(self._freq_achse):
            self.markiere_frequenz(index)
        self.draw_idle()

    def _render(self) -> None:
        """Zeichnet das Falschfarbenbild aus Rohmatrix + Kette + Anzeige-Modus neu."""
        feld, freq, Z = self._feld_achse, self._freq_achse, self._Z_komplex
        if self._kette is not None:
            feld, freq, Z = self._kette.anwenden(feld, freq, Z)
        matrix = anzeige_transform(Z, self._anzeige_modus)
        matrix = np.where(np.isfinite(matrix), matrix, np.nan)
        self._matrix = matrix

        self._markierung = self._marker_label = None
        self._box_patch = None
        # ax.clear() entsorgt alle Overlay-Artists - Referenzen VOR dem
        # Neuzeichnen verwerfen (remove() auf toten Artists wuerde werfen).
        self._grenzen_linien = {}
        self._zonen_patches = []
        self.ax.clear()
        # Robuste Farbgrenzen: einzelne Ausreisser (nach dd haeufig) duerfen die
        # Skala nicht dominieren, sonst ist die Mode nicht mit dem Auge erkennbar.
        endlich = matrix[np.isfinite(matrix)]
        vmin = vmax = None
        if endlich.size:
            vmin, vmax = np.percentile(endlich, _CLIM_PERZENTILE)
            if vmin == vmax:
                vmin = vmax = None
        self.ax.imshow(matrix, aspect="auto", origin="lower", cmap="viridis",
                       extent=list(self._extent), vmin=vmin, vmax=vmax)
        self.ax.set_autoscale_on(False)  # Overlays/Marker veraendern den Zoom nicht
        self.ax.set_xlabel(r"Feld $\mu_0 H$ (T)")
        self.ax.set_ylabel("Frequenz (GHz)")
        beschreibung = self._kette.beschreibung() if self._kette is not None else "roh"
        anzeige = ANZEIGE_MODI.get(self._anzeige_modus, self._anzeige_modus)
        if beschreibung == "roh":
            self.ax.set_title(f"Uebersicht S21 roh · {anzeige}")
        else:
            self.ax.set_title(f"Uebersicht S21: {beschreibung} · {anzeige}", fontsize=10)
        self.ax.text(
            0.5, -0.13,
            "klicken = Frequenz · Kästchen ziehen = Zoom · Mausrad = rein/raus · "
            "Doppelklick = zurück · ↑/↓ · ⇧+Rad",
            transform=self.ax.transAxes, ha="center", va="top",
            fontsize=7.2, color="#6B6657")
        if self._grenzen_sichtbar:
            self._zeichne_grenzen()
        if self._zonen:
            self._zeichne_zonen()
        self._tight_layout_sicher()
        self.draw_idle()

    def thumbnail(self):
        """Liefert ``(matrix, extent)`` der gesamten Messung (fuer den Navigator)."""
        return self._matrix, self._extent

    def achsen(self):
        """Liefert ``(feld_achse, frequenz_achse)`` des Rohgitters (oder ``(None, None)``)."""
        return self._feld_achse, self._freq_achse

    def _tight_layout_sicher(self) -> None:
        w, h = self.figur.get_size_inches() * self.figur.dpi
        if w < 1 or h < 1:
            return
        try:
            self.figur.tight_layout()
        except (np.linalg.LinAlgError, ValueError):
            pass

    # --- Resonanz-Overlay --------------------------------------------------
    def aktualisiere_resonanz(self, frequenzen, B_res, problematisch=None,
                              ausgeschlossen=None) -> None:
        """Speichert und zeichnet die Resonanzpunkte (gut rot, problematisch grau ×).

        ``ausgeschlossen`` (bool-Array) blendet Ausreisser komplett aus der
        Darstellung aus - sie sind nur noch ueber die Ausreisser-Liste
        einsehbar und wieder aufnehmbar.
        """
        if self._datensatz is None:
            return
        self._res_freq = np.asarray(frequenzen, dtype=float)
        self._res_bres = np.asarray(B_res, dtype=float)
        self._res_problem = (np.zeros(self._res_freq.shape, dtype=bool)
                             if problematisch is None
                             else np.asarray(problematisch, dtype=bool))
        self._res_ausgeschlossen = (np.zeros(self._res_freq.shape, dtype=bool)
                                    if ausgeschlossen is None
                                    else np.asarray(ausgeschlossen, dtype=bool))
        self._zeichne_resonanz()

    def setze_problemfits_ausblenden(self, an: bool) -> None:
        self._problemfits_ausblenden = bool(an)
        self._zeichne_resonanz()

    def _zeichne_resonanz(self) -> None:
        if self._res_freq is None:
            return
        for ln in list(self.ax.lines):
            if ln.get_label() in ("_resonanz", "_resonanz_problem"):
                ln.remove()
        f_ghz = self._res_freq / 1e9
        ausgeschlossen = getattr(self, "_res_ausgeschlossen", None)
        if ausgeschlossen is None:
            ausgeschlossen = np.zeros(self._res_freq.shape, dtype=bool)
        gut = ~self._res_problem & ~ausgeschlossen
        self.ax.plot(self._res_bres[gut], f_ghz[gut], ".", color="red", ms=4, label="_resonanz")
        problem = self._res_problem & ~ausgeschlossen
        if not self._problemfits_ausblenden and problem.any():
            self.ax.plot(self._res_bres[problem], f_ghz[problem],
                         "x", color="#BBBBBB", ms=4, mew=1.0, label="_resonanz_problem")
        self.draw_idle()

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
                facecolor="#E8A31733", edgecolor="#E8A317", lw=1.4, zorder=8))
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

    # --- Fenstergrenzen (ziehbare Polylinien links/rechts der Resonanz) -----
    def zeige_fenstergrenzen(self, frequenzen, fenster, grenze_gezogen=None) -> None:
        """Zeichnet die Fenstergrenzen als ziehbare Polylinien uebers Bild.

        ``frequenzen`` (Hz) und ``fenster`` (Liste ``(unten, oben)`` in T)
        gehoeren zum Fit-Stapel. ``grenze_gezogen(index, seite, feldwert)``
        wird nach dem Loslassen einer gezogenen Grenze aufgerufen
        (``seite`` = "links"/"rechts", ``index`` = Stapel-Index).
        """
        self._grenzen_freq = np.asarray(frequenzen, dtype=float)
        self._grenzen_fenster = [tuple(f) for f in fenster]
        if grenze_gezogen is not None:
            self._grenze_gezogen = grenze_gezogen
        self._grenzen_sichtbar = True
        self._zeichne_grenzen()

    def verstecke_fenstergrenzen(self) -> None:
        self._grenzen_sichtbar = False
        self._drag_grenze = None
        for linie in self._grenzen_linien.values():
            linie.remove()
        self._grenzen_linien = {}
        self.draw_idle()

    def _zeichne_grenzen(self) -> None:
        for linie in self._grenzen_linien.values():
            linie.remove()
        self._grenzen_linien = {}
        if not self._grenzen_sichtbar or self._grenzen_freq is None:
            return
        f_ghz = self._grenzen_freq / 1e9
        stil = dict(lw=1.8, ls="-", marker="", zorder=7, alpha=0.9,
                    path_effects=[pe.Stroke(linewidth=3.0, foreground="#00000066"),
                                  pe.Normal()])
        self._grenzen_linien["links"] = self.ax.plot(
            [f[0] for f in self._grenzen_fenster], f_ghz,
            color="#E8A317", label="_grenze_links", **stil)[0]
        self._grenzen_linien["rechts"] = self.ax.plot(
            [f[1] for f in self._grenzen_fenster], f_ghz,
            color="#4FC3F7", label="_grenze_rechts", **stil)[0]
        self.draw_idle()

    def _finde_grenze(self, event) -> tuple[str, int] | None:
        """(seite, index) der Grenze nahe am Mauszeiger, sonst None."""
        if not self._grenzen_sichtbar or self._grenzen_freq is None:
            return None
        if event.xdata is None or event.ydata is None:
            return None
        x0, x1 = self.ax.get_xlim()
        toleranz = 0.015 * abs(x1 - x0)
        index = int(np.argmin(np.abs(self._grenzen_freq / 1e9 - event.ydata)))
        unten, oben = self._grenzen_fenster[index]
        abstaende = {"links": abs(event.xdata - unten), "rechts": abs(event.xdata - oben)}
        seite = min(abstaende, key=abstaende.get)
        return (seite, index) if abstaende[seite] <= toleranz else None

    def _grenze_bewegen(self, event) -> None:
        """Waehrend des Ziehens: den einen Polylinien-Stuetzpunkt live mitfuehren."""
        seite, index = self._drag_grenze
        if event.xdata is None:
            return
        unten, oben = self._grenzen_fenster[index]
        if seite == "links":
            self._grenzen_fenster[index] = (float(event.xdata), oben)
        else:
            self._grenzen_fenster[index] = (unten, float(event.xdata))
        linie = self._grenzen_linien.get(seite)
        if linie is not None:
            x = linie.get_xdata()
            x[index] = event.xdata
            linie.set_xdata(x)
            self.draw_idle()

    # --- Ausschlusszonen ----------------------------------------------------
    def starte_ausschluss_zeichnen(self, fertig) -> None:
        """Naechstes aufgezogenes Rechteck wird als Ausschlusszone gemeldet.

        ``fertig(feld_min, feld_max, f_min_ghz, f_max_ghz)``; ``Esc`` bricht ab.
        """
        self._ausschluss_fertig = fertig
        self._bereich_fertig = None
        self._seed_fertig = None
        self.setCursor(QtCore.Qt.CrossCursor)

    def ausschluss_zeichnen_abbrechen(self) -> None:
        self._ausschluss_fertig = None
        self.unsetCursor()

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
                facecolor="#00000000", edgecolor="#C0392B", hatch="///",
                lw=1.2, zorder=6, label="_ausschlusszone"))
            self._zonen_patches.append(patch)
        self.draw_idle()

    # --- Ausreisser-Markiermodus ---------------------------------------------
    def setze_ausreisser_modus(self, an: bool, gewaehlt=None) -> None:
        """Schaltet den Ausreisser-Modus (Toolbar-Umschalter, bleibt aktiv).

        Aktiv: ein Klick waehlt den naechstgelegenen sichtbaren Resonanzpunkt,
        ein aufgezogener Kasten alle Punkte darin; ``gewaehlt(indizes)`` wird
        mit den getroffenen Stapel-Indizes aufgerufen (Echtzeit, mehrfach).
        Zoom per Kasten ist waehrenddessen ausgesetzt.
        """
        self._ausreisser_aktiv = bool(an)
        if gewaehlt is not None:
            self._ausreisser_gewaehlt = gewaehlt
        if an:
            self.setCursor(QtCore.Qt.PointingHandCursor)
        else:
            self.unsetCursor()

    def _sichtbare_resonanzpunkte(self) -> np.ndarray:
        """Indizes der aktuell im Overlay gezeichneten Resonanzpunkte."""
        if self._res_freq is None:
            return np.array([], dtype=int)
        ausgeschlossen = (self._res_ausgeschlossen
                          if self._res_ausgeschlossen is not None
                          else np.zeros(self._res_freq.shape, dtype=bool))
        sichtbar = ~ausgeschlossen
        if self._problemfits_ausblenden:
            sichtbar &= ~self._res_problem
        return np.flatnonzero(sichtbar)

    def _ausreisser_klick(self, event) -> None:
        """Klick im Ausreisser-Modus: naechstgelegenen sichtbaren Punkt melden."""
        kandidaten = self._sichtbare_resonanzpunkte()
        if kandidaten.size == 0 or event.xdata is None or event.ydata is None:
            return
        # Abstand in relativen Achseneinheiten (Feld- und Frequenzspanne
        # unterscheiden sich um Groessenordnungen).
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        dx = (self._res_bres[kandidaten] - event.xdata) / max(abs(x1 - x0), 1e-12)
        dy = (self._res_freq[kandidaten] / 1e9 - event.ydata) / max(abs(y1 - y0), 1e-12)
        abstand = np.hypot(dx, dy)
        naechster = int(np.argmin(abstand))
        if abstand[naechster] <= 0.03 and self._ausreisser_gewaehlt is not None:
            self._ausreisser_gewaehlt([int(kandidaten[naechster])])

    def _ausreisser_kasten(self, x0, y0, x1, y1) -> None:
        """Kasten im Ausreisser-Modus: alle sichtbaren Punkte darin melden."""
        kandidaten = self._sichtbare_resonanzpunkte()
        if kandidaten.size == 0:
            return
        b = self._res_bres[kandidaten]
        f_ghz = self._res_freq[kandidaten] / 1e9
        drin = ((b >= min(x0, x1)) & (b <= max(x0, x1))
                & (f_ghz >= min(y0, y1)) & (f_ghz <= max(y0, y1)))
        if drin.any() and self._ausreisser_gewaehlt is not None:
            self._ausreisser_gewaehlt([int(i) for i in kandidaten[drin]])

    # --- Bereichs-Fit (Rechteck aufziehen -> nur dort neu fitten) -----------
    def starte_bereichs_fit(self, fertig) -> None:
        """Aktiviert den Bereichs-Fit-Modus: das naechste aufgezogene Rechteck
        wird als Fit-Bereich gemeldet statt zu zoomen.

        ``fertig(feld_min, feld_max, f_min_ghz, f_max_ghz)`` wird mit den
        Rechteck-Grenzen in Plot-Einheiten (Tesla, GHz) aufgerufen.
        ``Esc`` bricht den Modus ab.
        """
        self._bereich_fertig = fertig
        self._seed_fertig = None  # Modi schliessen sich gegenseitig aus
        self.setCursor(QtCore.Qt.CrossCursor)

    def bereichs_fit_abbrechen(self) -> None:
        self._bereich_fertig = None
        self.unsetCursor()

    def _bereich_abschliessen(self, x0, y0, x1, y1) -> None:
        fertig = self._bereich_fertig
        self._bereich_fertig = None
        self.unsetCursor()
        if fertig is not None:
            fertig(min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1))

    # --- Dispersions-Seed (zwei Klicks auf die Resonanz) -------------------
    def starte_dispersion_seed(self, fertig) -> None:
        """Aktiviert den Seed-Modus: die naechsten zwei Klicks markieren die Resonanz.

        ``fertig(punkte)`` wird mit ``[(B1, f1_GHz), (B2, f2_GHz)]`` aufgerufen.
        """
        self._seed_fertig = fertig
        self._seed_punkte = []
        for m in self._seed_marker:
            m.remove()
        self._seed_marker = []
        self.setCursor(QtCore.Qt.CrossCursor)
        self.draw_idle()

    def _seed_klick(self, event) -> None:
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            return
        self._seed_punkte.append((float(event.xdata), float(event.ydata)))  # (B [T], f [GHz])
        mk = self.ax.plot([event.xdata], [event.ydata], "P", color="#E8A317",
                          mec="white", mew=1.2, ms=12, zorder=9)[0]
        self._seed_marker.append(mk)
        self.draw_idle()
        if len(self._seed_punkte) >= 2:
            fertig = self._seed_fertig
            punkte = list(self._seed_punkte)
            self._seed_fertig = None
            self._seed_punkte = []
            self.unsetCursor()
            for m in self._seed_marker:
                m.remove()
            self._seed_marker = []
            self.draw_idle()
            if fertig is not None:
                fertig(punkte)

    # --- Maus / Tastatur ---------------------------------------------------
    def _on_press(self, event):
        if event.inaxes != self.ax or self._freq_achse is None:
            return
        self.setFocus()
        if self._seed_fertig is not None:   # Seed-Modus: Klick als Resonanzpunkt
            self._seed_klick(event)
            return
        # Fenstergrenze anfassen (hat Vorrang vor Box/Klick, ausser ein
        # Zeichenmodus ist aktiv).
        if self._ausschluss_fertig is None and self._bereich_fertig is None:
            treffer = self._finde_grenze(event)
            if treffer is not None:
                self._drag_grenze = treffer
                self.setCursor(QtCore.Qt.SizeHorCursor)
                return
        if getattr(event, "dblclick", False):
            self._press_xy = None
            self._zoom_zuruecksetzen()
            return
        if event.xdata is None or event.ydata is None:
            return
        self._press_xy = (event.xdata, event.ydata)
        self._box_aktiv = False
        self._box_corner = None

    def _on_move(self, event):
        if self._drag_grenze is not None:
            if event.inaxes == self.ax:
                self._grenze_bewegen(event)
            return
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            if not self._box_aktiv:
                self.unsetCursor()
            return
        if self._press_xy is None and self._grenzen_sichtbar \
                and self._ausschluss_fertig is None and self._bereich_fertig is None:
            # Hinweis-Cursor: Grenze in Reichweite -> horizontal ziehbar.
            if self._finde_grenze(event) is not None:
                self.setCursor(QtCore.Qt.SizeHorCursor)
                return
        if self._press_xy is not None:
            x0, y0 = self._press_xy
            if not self._box_aktiv:
                sx, sy = self._schwelle()
                if abs(event.xdata - x0) > sx or abs(event.ydata - y0) > sy:
                    self._box_aktiv = True
            if self._box_aktiv:
                self._box_corner = (x0, y0, event.xdata, event.ydata)
                self._zeichne_box()
            return
        self.setCursor(QtCore.Qt.CrossCursor)  # Hinweis: Kästchen aufziehbar

    def _on_release(self, event):
        if self._drag_grenze is not None:
            seite, index = self._drag_grenze
            self._drag_grenze = None
            self.unsetCursor()
            # Endwert aus dem live mitgefuehrten Fenster (robust, falls die
            # Maus ausserhalb der Achse losgelassen wurde).
            unten, oben = self._grenzen_fenster[index]
            wert = unten if seite == "links" else oben
            if self._grenze_gezogen is not None:
                self._grenze_gezogen(index, seite, float(wert))
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
            if self._ausschluss_fertig is not None:
                self._ausschluss_abschliessen(*box)  # Ausschlusszone einzeichnen
            elif self._bereich_fertig is not None:
                self._bereich_abschliessen(*box)     # Bereichs-Fit statt Zoom
            elif self._ausreisser_aktiv:
                self._ausreisser_kasten(*box)        # Ausreisser gemeinsam markieren
            else:
                self._auf_box_zoom(*box)
        elif event.inaxes == self.ax and event.ydata is not None:
            if self._ausreisser_aktiv:
                self._ausreisser_klick(event)        # Einzelpunkt markieren
            else:
                self._waehle_index(self._index_aus_y(event.ydata))

    def _ausschluss_abschliessen(self, x0, y0, x1, y1) -> None:
        fertig = self._ausschluss_fertig
        self._ausschluss_fertig = None
        self.unsetCursor()
        if fertig is not None:
            fertig(min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1))

    def _on_leave(self, event):
        self.unsetCursor()

    def _on_scroll(self, event):
        if self._freq_achse is None:
            return
        modifier = getattr(event, "key", None) or ""
        if "shift" in modifier:
            self._waehle_index(self._aktueller_index + (1 if event.step > 0 else -1))
        else:
            self._zoom(event, _ZOOM_REIN if event.step > 0 else _ZOOM_RAUS)

    def _on_key(self, event):
        if event.key == "escape":
            if self._bereich_fertig is not None:
                self.bereichs_fit_abbrechen()
                return
            if self._ausschluss_fertig is not None:
                self.ausschluss_zeichnen_abbrechen()
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

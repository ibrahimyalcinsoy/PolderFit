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

        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("motion_notify_event", self._on_move)
        self.mpl_connect("button_release_event", self._on_release)
        self.mpl_connect("scroll_event", self._on_scroll)
        self.mpl_connect("key_press_event", self._on_key)
        self.mpl_connect("figure_leave_event", self._on_leave)

    def zeige(self, datensatz: Messdatensatz) -> None:
        """Stellt die Magnituden-Matrix des Datensatzes dar."""
        self._datensatz = datensatz
        feld, freq, matrix = datensatz.anzeige_matrix()
        self._matrix = matrix
        self._freq_achse = freq
        self._extent = (float(feld.min()), float(feld.max()),
                        float(freq.min() / 1e9), float(freq.max() / 1e9))
        self._markierung = self._marker_label = None
        self._res_freq = self._res_bres = self._res_problem = None
        self._press_xy = None
        self._box_aktiv = False
        self._box_patch = None
        self.ax.clear()
        self.ax.imshow(matrix, aspect="auto", origin="lower", cmap="viridis",
                       extent=list(self._extent))
        self.ax.set_autoscale_on(False)  # Overlays/Marker veraendern den Zoom nicht
        self.ax.set_xlabel(r"Feld $\mu_0 H$ (T)")
        self.ax.set_ylabel("Frequenz (GHz)")
        self.ax.set_title("Uebersicht |S21| (Frequenz vs. Feld)")
        self.ax.text(
            0.5, -0.13,
            "klicken = Frequenz · Kästchen ziehen = Zoom · Mausrad = rein/raus · "
            "Doppelklick = zurück · ↑/↓ · ⇧+Rad",
            transform=self.ax.transAxes, ha="center", va="top",
            fontsize=7.2, color="#6B6657")
        self._tight_layout_sicher()
        self.draw_idle()

    def thumbnail(self):
        """Liefert ``(matrix, extent)`` der gesamten Messung (fuer den Navigator)."""
        return self._matrix, self._extent

    def _tight_layout_sicher(self) -> None:
        w, h = self.figur.get_size_inches() * self.figur.dpi
        if w < 1 or h < 1:
            return
        try:
            self.figur.tight_layout()
        except (np.linalg.LinAlgError, ValueError):
            pass

    # --- Resonanz-Overlay --------------------------------------------------
    def aktualisiere_resonanz(self, frequenzen, B_res, problematisch=None) -> None:
        """Speichert und zeichnet die Resonanzpunkte (gut rot, problematisch grau ×)."""
        if self._datensatz is None:
            return
        self._res_freq = np.asarray(frequenzen, dtype=float)
        self._res_bres = np.asarray(B_res, dtype=float)
        self._res_problem = (np.zeros(self._res_freq.shape, dtype=bool)
                             if problematisch is None
                             else np.asarray(problematisch, dtype=bool))
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
        gut = ~self._res_problem
        self.ax.plot(self._res_bres[gut], f_ghz[gut], ".", color="red", ms=4, label="_resonanz")
        if not self._problemfits_ausblenden and self._res_problem.any():
            self.ax.plot(self._res_bres[self._res_problem], f_ghz[self._res_problem],
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
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            if not self._box_aktiv:
                self.unsetCursor()
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
        if self._press_xy is None:
            return
        war_box = self._box_aktiv
        box = self._box_corner
        self._press_xy = None
        self._box_aktiv = False
        self._box_corner = None
        self._entferne_box()
        if war_box and box is not None:
            self._auf_box_zoom(*box)
        elif event.inaxes == self.ax and event.ydata is not None:
            self._waehle_index(self._index_aus_y(event.ydata))

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

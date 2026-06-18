"""Navigator: Mini-Uebersicht der gesamten Messung mit Ausschnitt-Markierung.

Zeigt das gesamte |S21|-Falschfarbenbild verkleinert und markiert mit einem roten
Rechteck den aktuell in der Hauptuebersicht sichtbaren (gezoomten) Ausschnitt –
damit man sieht, *wo* man sich gerade befindet. Klicken/Ziehen im Navigator
verschiebt den Ausschnitt (Recentern) ueber den Callback ``bereich_gewaehlt``.
"""

from __future__ import annotations

import numpy as np
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class NavigatorAnsicht(FigureCanvasQTAgg):
    """Verkleinerte Gesamtuebersicht mit Viewport-Rechteck."""

    def __init__(self, bereich_gewaehlt=None):
        self.figur = Figure(figsize=(2.6, 2.4))
        super().__init__(self.figur)
        self.ax = self.figur.add_subplot(111)
        self.bereich_gewaehlt = bereich_gewaehlt
        self._extent = None
        self._rect = None
        self._viewport = None      # (xlim, ylim) des aktuellen Ausschnitts
        self._ziehen = False

        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("motion_notify_event", self._on_move)
        self.mpl_connect("button_release_event", self._on_release)

    def zeige(self, matrix, extent) -> None:
        """Zeigt das Gesamtbild (Thumbnail der Messung)."""
        self.ax.clear()
        if matrix is not None and extent is not None:
            self.ax.imshow(matrix, aspect="auto", origin="lower", cmap="viridis",
                           extent=list(extent))
        self.ax.set_autoscale_on(False)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_title("Navigator – Gesamtübersicht", fontsize=8)
        self._extent = extent
        self._rect = None
        self._viewport = None
        self._tight_layout_sicher()
        self.draw_idle()

    def setze_ausschnitt(self, xlim, ylim) -> None:
        """Zeichnet das Viewport-Rechteck fuer den aktuell sichtbaren Ausschnitt."""
        self._viewport = (tuple(xlim), tuple(ylim))
        if self._rect is not None:
            self._rect.remove()
            self._rect = None
        x0, x1 = min(xlim), max(xlim)
        y0, y1 = min(ylim), max(ylim)
        self._rect = self.ax.add_patch(Rectangle(
            (x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor="red", lw=1.8, zorder=5))
        self.draw_idle()

    def _tight_layout_sicher(self) -> None:
        w, h = self.figur.get_size_inches() * self.figur.dpi
        if w < 1 or h < 1:
            return
        try:
            self.figur.tight_layout()
        except (np.linalg.LinAlgError, ValueError):
            pass

    # --- Recentern per Klick/Ziehen ---------------------------------------
    def _recenter(self, event) -> None:
        if (self._viewport is None or event.xdata is None or event.ydata is None
                or self.bereich_gewaehlt is None):
            return
        (xl, yl) = self._viewport
        wx = abs(xl[1] - xl[0])
        wy = abs(yl[1] - yl[0])
        nx = (event.xdata - wx / 2.0, event.xdata + wx / 2.0)
        ny = (event.ydata - wy / 2.0, event.ydata + wy / 2.0)
        self.bereich_gewaehlt(nx, ny)

    def _on_press(self, event):
        if event.inaxes != self.ax:
            return
        self._ziehen = True
        self._recenter(event)

    def _on_move(self, event):
        if self._ziehen and event.inaxes == self.ax:
            self._recenter(event)

    def _on_release(self, event):
        self._ziehen = False

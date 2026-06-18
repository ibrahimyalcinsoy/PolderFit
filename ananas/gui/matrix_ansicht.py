"""2D-Uebersicht: Magnituden-Matrix (Frequenz vs. Feld) mit Resonanzverlauf.

Zeigt die gesamte Messung als Falschfarbenbild, ueberlagert die gefitteten
Resonanzfelder und markiert die aktuell gewaehlte Frequenz mit einer horizontalen
Linie. Die Frequenz (also die Linie) laesst sich auf mehrere Arten bewegen:

* **Klicken** – springt zur naechstgelegenen Frequenz,
* **Ziehen** – die Linie folgt der Maus (kontinuierliches Durchscrubben),
* **Mausrad** – eine Frequenz hoch/runter,
* **Pfeiltasten** ``hoch/runter`` (bzw. ``links/rechts``) – Einzelschritt,
  ``Bild hoch/runter`` – 10er-Schritt, ``Pos1/Ende`` – erste/letzte Frequenz.

Jede Auswahl meldet den Index ueber ``frequenz_gewaehlt(index)`` zurueck.
"""

from __future__ import annotations

import numpy as np
import matplotlib.patheffects as pe
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6 import QtCore

from ..io.datensatz import Messdatensatz

#: Toleranz (Anteil des Frequenzbereichs), in dem die Linie als "gegriffen" gilt.
_GREIF_TOLERANZ_REL = 0.02


class MatrixAnsicht(FigureCanvasQTAgg):
    """Falschfarben-Uebersicht der Magnitude mit Resonanz-Overlay."""

    def __init__(self, frequenz_gewaehlt=None):
        self.figur = Figure(figsize=(5, 5))
        super().__init__(self.figur)
        self.ax = self.figur.add_subplot(111)
        self.frequenz_gewaehlt = frequenz_gewaehlt
        self._datensatz: Messdatensatz | None = None
        self._freq_achse = None
        self._markierung = None
        self._marker_label = None
        self._aktueller_index = 0
        self._ziehen = False

        # Tastatur-Fokus, damit Pfeiltasten ankommen (Fokus beim Klick/Hover).
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
        self._freq_achse = freq
        self._markierung = None
        self._marker_label = None
        self.ax.clear()
        self.ax.imshow(
            matrix, aspect="auto", origin="lower", cmap="viridis",
            extent=[feld.min(), feld.max(), freq.min() / 1e9, freq.max() / 1e9],
        )
        self.ax.set_xlabel(r"Feld $\mu_0 H$ (T)")
        self.ax.set_ylabel("Frequenz (GHz)")
        self.ax.set_title("Uebersicht |S21| (Frequenz vs. Feld)")
        # Kurzer Bedienhinweis (Navigation der horizontalen Linie).
        self.ax.text(0.5, -0.13, "Linie bewegen:  klicken · ziehen · scrollen · ↑/↓ · Bild↑/↓ · Pos1/Ende",
                     transform=self.ax.transAxes, ha="center", va="top",
                     fontsize=7.5, color="#6B6657")
        # tight_layout toleriert ein noch nicht ausgemessenes (0x0) Canvas.
        w, h = self.figur.get_size_inches() * self.figur.dpi
        if w >= 1 and h >= 1:
            try:
                self.figur.tight_layout()
            except (np.linalg.LinAlgError, ValueError):
                pass
        self.draw_idle()

    def aktualisiere_resonanz(self, frequenzen, B_res) -> None:
        """Ueberlagert die gefitteten Resonanzfelder als Punkte."""
        if self._datensatz is None:
            return
        for ln in list(self.ax.lines):
            if ln.get_label() == "_resonanz":
                ln.remove()
        self.ax.plot(B_res, np.asarray(frequenzen) / 1e9, ".", color="red",
                     ms=4, label="_resonanz")
        self.draw_idle()

    def markiere_frequenz(self, index: int) -> None:
        """Markiert die aktuell gewaehlte Frequenz mit einer horizontalen Linie."""
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
        # Dunkler Halo -> auf hellen wie dunklen Bildbereichen sichtbar.
        self._markierung.set_path_effects(
            [pe.Stroke(linewidth=3.4, foreground="#00000088"), pe.Normal()])
        self._marker_label = self.ax.annotate(
            f"{f_ghz:.2f} GHz", xy=(0.0, f_ghz), xycoords=("axes fraction", "data"),
            xytext=(5, 3), textcoords="offset points", color="white", fontsize=8,
            fontweight="bold", zorder=7,
            path_effects=[pe.Stroke(linewidth=2.2, foreground="#00000099"), pe.Normal()])
        self.draw_idle()

    # --- Auswahl-Logik -----------------------------------------------------
    def _waehle_index(self, index: int) -> None:
        """Markiert ``index`` und meldet die Auswahl (no-op, wenn unveraendert)."""
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

    def _nahe_linie(self, ydata: float) -> bool:
        if self._freq_achse is None or len(self._freq_achse) == 0:
            return False
        f_akt = self._freq_achse[self._aktueller_index] / 1e9
        spanne = (self._freq_achse.max() - self._freq_achse.min()) / 1e9 or 1.0
        return abs(ydata - f_akt) <= _GREIF_TOLERANZ_REL * spanne

    # --- Maus / Tastatur ---------------------------------------------------
    def _on_press(self, event):
        if event.inaxes != self.ax or event.ydata is None or self._freq_achse is None:
            return
        self.setFocus()  # Tastatur-Fokus fuer anschliessende Pfeiltasten-Navigation
        self._ziehen = True
        self._waehle_index(self._index_aus_y(event.ydata))

    def _on_move(self, event):
        if event.inaxes != self.ax or event.ydata is None or self._freq_achse is None:
            self.unsetCursor()
            return
        if self._ziehen:
            self._waehle_index(self._index_aus_y(event.ydata))
            return
        # Hover nahe der Linie -> vertikaler Resize-Cursor als Greif-Hinweis.
        if self._nahe_linie(event.ydata):
            self.setCursor(QtCore.Qt.SizeVerCursor)
        else:
            self.unsetCursor()

    def _on_release(self, event):
        self._ziehen = False

    def _on_leave(self, event):
        self._ziehen = False
        self.unsetCursor()

    def _on_scroll(self, event):
        if self._freq_achse is None:
            return
        schritt = 1 if event.step > 0 else -1   # hochscrollen -> hoehere Frequenz
        self._waehle_index(self._aktueller_index + schritt)

    def _on_key(self, event):
        if self._freq_achse is None:
            return
        n = len(self._freq_achse)
        spruenge = {
            "up": +1, "right": +1, "down": -1, "left": -1,
            "pageup": +10, "pagedown": -10,
        }
        if event.key in spruenge:
            self._waehle_index(self._aktueller_index + spruenge[event.key])
        elif event.key == "home":
            self._waehle_index(0)
        elif event.key == "end":
            self._waehle_index(n - 1)

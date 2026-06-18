"""2D-Uebersicht: Magnituden-Matrix (Frequenz vs. Feld) mit Resonanzverlauf.

Zeigt die gesamte Messung als Falschfarbenbild, ueberlagert die gefitteten
Resonanzfelder und markiert die aktuell gewaehlte Frequenz. Ein Klick waehlt die
naechstgelegene Frequenz aus (Callback ``frequenz_gewaehlt(index)``).
"""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ..io.datensatz import Messdatensatz


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
        self.mpl_connect("button_press_event", self._on_press)

    def zeige(self, datensatz: Messdatensatz) -> None:
        """Stellt die Magnituden-Matrix des Datensatzes dar."""
        self._datensatz = datensatz
        feld, freq, matrix = datensatz.anzeige_matrix()
        self._freq_achse = freq
        self.ax.clear()
        self.ax.imshow(
            matrix, aspect="auto", origin="lower", cmap="viridis",
            extent=[feld.min(), feld.max(), freq.min() / 1e9, freq.max() / 1e9],
        )
        self.ax.set_xlabel(r"Feld $\mu_0 H$ (T)")
        self.ax.set_ylabel("Frequenz (GHz)")
        self.ax.set_title("Uebersicht |S21| (Frequenz vs. Feld)")
        self._markierung = None
        self.figur.tight_layout()
        self.draw_idle()

    def aktualisiere_resonanz(self, frequenzen, B_res) -> None:
        """Ueberlagert die gefitteten Resonanzfelder als Punkte."""
        if self._datensatz is None:
            return
        # Vorhandene Resonanz-Overlays entfernen.
        for ln in list(self.ax.lines):
            if ln.get_label() == "_resonanz":
                ln.remove()
        self.ax.plot(B_res, np.asarray(frequenzen) / 1e9, ".", color="red",
                     ms=4, label="_resonanz")
        self.draw_idle()

    def markiere_frequenz(self, index: int) -> None:
        """Markiert die aktuell gewaehlte Frequenz mit einer horizontalen Linie."""
        if self._freq_achse is None:
            return
        if self._markierung is not None:
            self._markierung.remove()
        f_ghz = self._freq_achse[index] / 1e9
        self._markierung = self.ax.axhline(f_ghz, color="white", lw=1.0, ls="--")
        self.draw_idle()

    def _on_press(self, event):
        if event.inaxes != self.ax or event.ydata is None or self._freq_achse is None:
            return
        index = int(np.argmin(np.abs(self._freq_achse / 1e9 - event.ydata)))
        self.markiere_frequenz(index)
        if self.frequenz_gewaehlt is not None:
            self.frequenz_gewaehlt(index)

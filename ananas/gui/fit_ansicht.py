"""Interaktives Linescan-Panel: Re und Im gleichzeitig + Fit, verschiebbare Grenzen.

Zeigt fuer die aktuell gewaehlte Frequenz Real- und Imaginaerteil von S21 gegen
das Feld, ueberlagert die Fitkurve und stellt zwei frei verschiebbare vertikale
Linien (Bandgrenzen) bereit. Beim Verschieben wird ein Callback ausgeloest, der
den Datensatz mit den neuen Grenzen neu fitten kann ("rumfitten").
"""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ..fit.linescan_fit import FitErgebnis
from ..io.datensatz import Linescan


class FitAnsicht(FigureCanvasQTAgg):
    """Matplotlib-Canvas mit zwei Achsen (Re/Im) und verschiebbaren Grenzlinien."""

    def __init__(self, grenzen_geaendert=None):
        self.figur = Figure(figsize=(6, 5))
        super().__init__(self.figur)
        self.ax_re = self.figur.add_subplot(211)
        self.ax_im = self.figur.add_subplot(212, sharex=self.ax_re)
        self.grenzen_geaendert = grenzen_geaendert

        self._linescan: Linescan | None = None
        self._grenze_unten = None
        self._grenze_oben = None
        self._gezogen = None  # 'unten' | 'oben' | None
        self._linien = []

        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("motion_notify_event", self._on_move)
        self.mpl_connect("button_release_event", self._on_release)

    def zeige(
        self,
        linescan: Linescan,
        grenze_unten: float,
        grenze_oben: float,
        ergebnis: FitErgebnis | None = None,
    ) -> None:
        """Stellt einen Linescan samt Bandgrenzen und (optional) Fitkurve dar."""
        self._linescan = linescan
        self._grenze_unten = grenze_unten
        self._grenze_oben = grenze_oben

        self.ax_re.clear()
        self.ax_im.clear()
        self._linien = []

        b = linescan.feld
        self.ax_re.plot(b, linescan.re, ".", ms=3, color="C0", label="Re S21 (Messung)")
        self.ax_im.plot(b, linescan.im, ".", ms=3, color="C1", label="Im S21 (Messung)")

        if ergebnis is not None and ergebnis.fitkurve is not None and ergebnis.feld is not None:
            self.ax_re.plot(ergebnis.feld, ergebnis.fitkurve.real, "-", color="k", lw=1.2, label="Fit Re")
            self.ax_im.plot(ergebnis.feld, ergebnis.fitkurve.imag, "-", color="k", lw=1.2, label="Fit Im")
            self.ax_re.axvline(ergebnis.B_res, color="red", ls="--", lw=0.8)
            self.ax_im.axvline(ergebnis.B_res, color="red", ls="--", lw=0.8)

        for ax in (self.ax_re, self.ax_im):
            lu = ax.axvline(grenze_unten, color="green", lw=1.5, picker=True)
            lo = ax.axvline(grenze_oben, color="green", lw=1.5, picker=True)
            self._linien.append((ax, lu, lo))

        titel = f"f = {linescan.frequenz/1e9:.3f} GHz"
        if ergebnis is not None:
            titel += (f"   |   B_res = {ergebnis.B_res:.4f} T, "
                      f"alpha = {ergebnis.alpha:.2e}, R² = {ergebnis.R2:.4f}")
        self.ax_re.set_title(titel)
        self.ax_re.set_ylabel("Re S21")
        self.ax_im.set_ylabel("Im S21")
        self.ax_im.set_xlabel(r"Feld $\mu_0 H$ (T)")
        self.ax_re.legend(fontsize=8, loc="best")
        self.ax_im.legend(fontsize=8, loc="best")
        self.figur.tight_layout()
        self.draw_idle()

    # --- Maus-Interaktion fuer die Grenzlinien -----------------------------
    def _on_press(self, event):
        if event.inaxes not in (self.ax_re, self.ax_im) or event.xdata is None:
            return
        d_unten = abs(event.xdata - self._grenze_unten)
        d_oben = abs(event.xdata - self._grenze_oben)
        toleranz = 0.02 * (np.ptp(self._linescan.feld) or 1.0)
        if min(d_unten, d_oben) > toleranz:
            return
        self._gezogen = "unten" if d_unten < d_oben else "oben"

    def _on_move(self, event):
        if self._gezogen is None or event.xdata is None:
            return
        if self._gezogen == "unten":
            self._grenze_unten = float(event.xdata)
        else:
            self._grenze_oben = float(event.xdata)
        for (_ax, lu, lo) in self._linien:
            lu.set_xdata([self._grenze_unten, self._grenze_unten])
            lo.set_xdata([self._grenze_oben, self._grenze_oben])
        self.draw_idle()

    def _on_release(self, event):
        if self._gezogen is None:
            return
        self._gezogen = None
        unten = min(self._grenze_unten, self._grenze_oben)
        oben = max(self._grenze_unten, self._grenze_oben)
        self._grenze_unten, self._grenze_oben = unten, oben
        if self.grenzen_geaendert is not None:
            self.grenzen_geaendert(unten, oben)

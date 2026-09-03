# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Interaktives Linescan-Panel: Re und Im gleichzeitig + Fit, verschiebbare Grenzen.

Zeigt fuer die aktuell gewaehlte Frequenz Real- und Imaginaerteil von S21 gegen
das Feld, ueberlagert die Fitkurve der GEWAEHLTEN Mode (andere Moden erscheinen
nur als Korridor im Farbplot) und stellt zwei frei verschiebbare vertikale
Linien (Fenstergrenzen) bereit. Beim Verschieben wird ein Callback ausgeloest, der den Datensatz mit
den neuen Grenzen neu fittet ("rumfitten").

Farben nach :mod:`polderfit.gui.farben`: Messdaten in neutralen Serienfarben,
Fit schwarz, die Resonanzlinie in der Statusfarbe des Fits (gruen = gut, gelb =
problematisch, rot = fehlgeschlagen), Bandgrenzen gruen (= Fit-Bereich, wie die
gruene Seite der Grenzgeraden), Band hellblau (Auswahl).
"""

from __future__ import annotations

import numpy as np
import matplotlib.patheffects as pe
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6 import QtCore

from ..fit.linescan_fit import FitErgebnis
from ..io.datensatz import Linescan
from . import farben as F

# --- Darstellung der verschiebbaren Bandgrenzen ---------------------------
GRENZ_FARBE = F.SIGNAL_GRUEN
GRENZ_LW = 2.4
GRENZ_LW_HOVER = 3.6
GRIFF_MS = 9
GRIFF_MS_HOVER = 13
BAND_FARBE = F.SIGNAL_BLAU
BAND_ALPHA = 0.10
GREIF_TOLERANZ_REL = 0.03    # Anteil der Feldbreite, in dem eine Linie "gegriffen" wird
_HALO = [pe.Stroke(linewidth=GRENZ_LW + 2.0, foreground="white"), pe.Normal()]
#: Serienfarben der Messdaten (neutral, keine Statusbedeutung).
_FARBE_RE = F.TEXT_BLAU
_FARBE_IM = "#B35C00"
_FARBE_FIT = F.TEXT


class FitAnsicht(FigureCanvasQTAgg):
    """Matplotlib-Canvas mit zwei Achsen (Re/Im) und verschiebbaren Grenzlinien."""

    def __init__(self, grenzen_geaendert=None):
        self.figur = Figure(figsize=(6, 5))
        super().__init__(self.figur)
        self.ax_re = self.figur.add_subplot(211)
        self.ax_im = self.figur.add_subplot(212, sharex=self.ax_re)
        self.grenzen_geaendert = grenzen_geaendert

        self._linescan: Linescan | None = None
        self._grenze_unten: float | None = None
        self._grenze_oben: float | None = None
        self._gezogen: str | None = None   # 'unten' | 'oben' | None
        self._hover: str | None = None      # 'unten' | 'oben' | None
        self._vollbereich: bool = False     # True -> ganzer Feldsweep statt Zoom aufs Band
        # Grafik-Objekte je Achse (zum Live-Aktualisieren beim Ziehen).
        self._linien_unten = []
        self._linien_oben = []
        self._griffe_unten = []
        self._griffe_oben = []
        self._baender = []
        self._hinweis = None

        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("motion_notify_event", self._on_move)
        self.mpl_connect("button_release_event", self._on_release)
        self.mpl_connect("figure_leave_event", self._on_leave)

    def zeige(
        self,
        linescan: Linescan,
        grenze_unten: float,
        grenze_oben: float,
        ergebnis: FitErgebnis | None = None,
        status: str | None = None,
    ) -> None:
        """Stellt einen Linescan samt Bandgrenzen und (optional) Fitkurve dar.

        ``status``: Statusklasse des Fits (:mod:`polderfit.gui.farben`) fuer
        die Farbe der Resonanzlinie; fehlt sie, wird sie aus dem Ergebnis
        abgeleitet.
        """
        self._linescan = linescan
        self._grenze_unten = float(grenze_unten)
        self._grenze_oben = float(grenze_oben)
        self._gezogen = None
        self._hover = None

        self.ax_re.clear()
        self.ax_im.clear()
        self._linien_unten, self._linien_oben = [], []
        self._griffe_unten, self._griffe_oben = [], []
        self._baender = []
        if self._hinweis is not None:
            try:
                self._hinweis.remove()
            except (ValueError, AttributeError):
                pass
            self._hinweis = None

        b = linescan.feld
        self.ax_re.plot(b, linescan.re, ".", ms=3, color=_FARBE_RE, label="Re S21 (Messung)")
        self.ax_im.plot(b, linescan.im, ".", ms=3, color=_FARBE_IM, label="Im S21 (Messung)")

        gefittet = (ergebnis is not None and ergebnis.fitkurve is not None
                    and ergebnis.feld is not None)
        if gefittet:
            if status is None:
                status = F.status_von(ergebnis)
            farbe_res = F.STATUS_FARBEN.get(status, (F.SIGNAL_GRUEN, ""))[0]
            if farbe_res == "none":
                farbe_res = F.SIGNAL_GRUEN
            # Summenfit: Einzelbeitraege der Dips gestrichelt in Mode-Farbe.
            for mode_k, kurve_k in (getattr(ergebnis, "beitraege", None) or []):
                farbe_k = F.mode_farbe(int(mode_k)) if int(mode_k) > 1 else "#6B6F76"
                self.ax_re.plot(ergebnis.feld, kurve_k.real, "--", color=farbe_k, lw=0.9,
                                label=f"M{int(mode_k)}")
                self.ax_im.plot(ergebnis.feld, kurve_k.imag, "--", color=farbe_k, lw=0.9)
            self.ax_re.plot(ergebnis.feld, ergebnis.fitkurve.real, "-", color=_FARBE_FIT,
                            lw=1.4, label="Fit Re")
            self.ax_im.plot(ergebnis.feld, ergebnis.fitkurve.imag, "-", color=_FARBE_FIT,
                            lw=1.4, label="Fit Im")
            for ax in (self.ax_re, self.ax_im):
                ax.axvline(ergebnis.B_res, color=farbe_res, ls="--", lw=1.2, zorder=2)

        for ax in (self.ax_re, self.ax_im):
            span = ax.axvspan(self._grenze_unten, self._grenze_oben,
                              color=BAND_FARBE, alpha=BAND_ALPHA, lw=0, zorder=0)
            self._baender.append((ax, span))
            lu = ax.axvline(self._grenze_unten, color=GRENZ_FARBE, lw=GRENZ_LW, zorder=5)
            lo = ax.axvline(self._grenze_oben, color=GRENZ_FARBE, lw=GRENZ_LW, zorder=5)
            lu.set_path_effects(_HALO)
            lo.set_path_effects(_HALO)
            self._linien_unten.append(lu)
            self._linien_oben.append(lo)
            # Griff-Marker am oberen Rand (x in Daten, y in Achsen-Anteil).
            trans = ax.get_xaxis_transform()
            gu = ax.plot([self._grenze_unten], [1.0], marker="v", ms=GRIFF_MS,
                         color=GRENZ_FARBE, mec="white", mew=1.0,
                         transform=trans, clip_on=False, zorder=6)[0]
            go = ax.plot([self._grenze_oben], [1.0], marker="v", ms=GRIFF_MS,
                         color=GRENZ_FARBE, mec="white", mew=1.0,
                         transform=trans, clip_on=False, zorder=6)[0]
            self._griffe_unten.append(gu)
            self._griffe_oben.append(go)

        # Zwei explizite Zeilen: tight_layout misst mehrzeilige Titel korrekt,
        # ein automatischer Umbruch (wrap) wuerde in die Achse hineinragen.
        titel = f"{linescan.frequenz/1e9:.3f} GHz"
        if ergebnis is not None and int(getattr(ergebnis, "mode", 1)) > 1:
            titel += f" · M{int(ergebnis.mode)}"
        if ergebnis is not None and ergebnis.gefittet:
            titel += (f" · B_res {ergebnis.B_res:.4f} T ({ergebnis.B_res_mT:.1f} mT)\n"
                      f"µ₀ΔH {ergebnis.dH_mT:.2f} mT · α {ergebnis.alpha:.2e} · R² {ergebnis.R2:.4f}")
        elif ergebnis is not None:
            titel += "\nnoch nicht gefittet – Grenzen ziehen fittet diese Frequenz"
        self.ax_re.set_title(titel, fontsize=9)
        self.ax_re.set_ylabel("Re S21")
        self.ax_im.set_ylabel("Im S21")
        self.ax_im.set_xlabel(r"Feld $\mu_0 H$ (T)")
        self.ax_re.legend(fontsize=8, loc="best")
        self.ax_im.legend(fontsize=8, loc="best")
        # Standardmaessig auf das Resonanzband zoomen, damit die beiden Grenzlinien
        # nicht – wie ueber dem vollen Feldsweep – fast aufeinanderliegen.
        self.ax_re.set_xlim(*self._berechne_xlim(b))
        self._tight_layout_sicher()
        # Dezenter Bedienhinweis (nach tight_layout, damit er nicht verschoben wird).
        self._hinweis = self.figur.text(
            0.995, 0.004, "grüne Linien ziehen = Fenster ändern",
            ha="right", va="bottom", fontsize=7.5, color=GRENZ_FARBE, alpha=0.85)
        self._hinweis.set_in_layout(False)
        self.draw_idle()

    def _tight_layout_sicher(self) -> None:
        """tight_layout, das ein noch nicht ausgemessenes Canvas (0x0 Pixel) toleriert.

        Solange das Qt-Widget noch keine Groesse hat, ist die Figur-Transformation
        nicht invertierbar und Matplotlib wirft ``LinAlgError: Singular matrix``.
        Das ist rein ein Layout-Timing-Problem; beim naechsten echten Zeichnen mit
        gueltiger Groesse greift das Layout ohnehin. Vor jedem Aufruf werden die
        Raender zurueckgesetzt (kein kumulatives Schrumpfen).
        """
        w, h = self.figur.get_size_inches() * self.figur.dpi
        if w < 1 or h < 1:
            return
        self.figur.subplots_adjust(left=0.12, right=0.98, top=0.92, bottom=0.12, hspace=0.3)
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                self.figur.tight_layout()
        except (np.linalg.LinAlgError, ValueError):
            pass

    def _berechne_xlim(self, b) -> tuple[float, float]:
        """x-Grenzen der Anzeige: Zoom aufs Band (Standard) oder ganzer Sweep."""
        bmin, bmax = float(np.min(b)), float(np.max(b))
        if self._vollbereich or self._grenze_unten is None or self._grenze_oben is None:
            return bmin, bmax
        bw = abs(self._grenze_oben - self._grenze_unten)
        zentrum = 0.5 * (self._grenze_oben + self._grenze_unten)
        # Rand je Seite: mind. 40 mT (absolut), damit auch ein schmales Band Luft zum
        # Greifen hat und etwas Untergrund sichtbar bleibt.
        rand = max(1.3 * bw, 0.04)
        links = max(zentrum - bw / 2.0 - rand, bmin)
        rechts = min(zentrum + bw / 2.0 + rand, bmax)
        if rechts - links < 1e-9:
            return bmin, bmax
        return links, rechts

    def setze_vollbereich(self, an: bool) -> None:
        """Schaltet zwischen Zoom aufs Band und ganzem Feldsweep um (Neuanzeige durch Aufrufer)."""
        self._vollbereich = bool(an)

    # --- Grenzen live aktualisieren ---------------------------------------
    def _aktualisiere_grenzen_grafik(self) -> None:
        xl, xr = self._grenze_unten, self._grenze_oben
        for lu in self._linien_unten:
            lu.set_xdata([xl, xl])
        for lo in self._linien_oben:
            lo.set_xdata([xr, xr])
        for gu in self._griffe_unten:
            gu.set_xdata([xl])
        for go in self._griffe_oben:
            go.set_xdata([xr])
        # Band neu setzen (axvspan liefert je nach Matplotlib-Version Polygon ODER
        # Rectangle; Entfernen + Neuanlegen ist versionsunabhaengig robust).
        neue_baender = []
        for ax, span in self._baender:
            span.remove()
            span_neu = ax.axvspan(xl, xr, color=BAND_FARBE, alpha=BAND_ALPHA, lw=0, zorder=0)
            neue_baender.append((ax, span_neu))
        self._baender = neue_baender
        self.draw_idle()

    # --- Hilfen fuer Greifen/Hover ----------------------------------------
    def _naechste_grenze(self, x: float | None) -> str | None:
        """Liefert 'unten'/'oben', wenn x nahe genug an einer Grenze liegt, sonst None."""
        if self._linescan is None or x is None:
            return None
        d_unten = abs(x - self._grenze_unten)
        d_oben = abs(x - self._grenze_oben)
        toleranz = GREIF_TOLERANZ_REL * (np.ptp(self._linescan.feld) or 1.0)
        if min(d_unten, d_oben) > toleranz:
            return None
        return "unten" if d_unten <= d_oben else "oben"

    def _setze_hover(self, welche: str | None) -> None:
        if welche == self._hover:
            return
        self._hover = welche
        for lu in self._linien_unten:
            lu.set_linewidth(GRENZ_LW_HOVER if welche == "unten" else GRENZ_LW)
        for lo in self._linien_oben:
            lo.set_linewidth(GRENZ_LW_HOVER if welche == "oben" else GRENZ_LW)
        for gu in self._griffe_unten:
            gu.set_markersize(GRIFF_MS_HOVER if welche == "unten" else GRIFF_MS)
        for go in self._griffe_oben:
            go.set_markersize(GRIFF_MS_HOVER if welche == "oben" else GRIFF_MS)
        if welche is None:
            self.unsetCursor()
        else:
            self.setCursor(QtCore.Qt.SizeHorCursor)
        self.draw_idle()

    # --- Maus-Interaktion fuer die Grenzlinien -----------------------------
    def _on_press(self, event):
        if event.inaxes not in (self.ax_re, self.ax_im) or event.xdata is None:
            return
        self._gezogen = self._naechste_grenze(event.xdata)

    def _on_move(self, event):
        # Ziehen hat Vorrang.
        if self._gezogen is not None and event.xdata is not None:
            if self._gezogen == "unten":
                self._grenze_unten = float(event.xdata)
            else:
                self._grenze_oben = float(event.xdata)
            self._aktualisiere_grenzen_grafik()
            return
        # Sonst: Hover-Hervorhebung + Cursor.
        if event.inaxes in (self.ax_re, self.ax_im):
            self._setze_hover(self._naechste_grenze(event.xdata))
        else:
            self._setze_hover(None)

    def _on_release(self, event):
        if self._gezogen is None:
            return
        self._gezogen = None
        unten = min(self._grenze_unten, self._grenze_oben)
        oben = max(self._grenze_unten, self._grenze_oben)
        self._grenze_unten, self._grenze_oben = unten, oben
        self._aktualisiere_grenzen_grafik()
        if self.grenzen_geaendert is not None:
            self.grenzen_geaendert(unten, oben)

    def _on_leave(self, event):
        if self._gezogen is None:
            self._setze_hover(None)

# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Kittel/LLG-Auswertungsfenster (eigenes, nicht-modales Fenster).

Zeigt die uebergreifende Auswertung mit Feld auf der x-Achse (wie im Farbplot):

* Dispersion: Resonanzfeld (x) gegen Frequenz (y) mit Kittel-Fit,
* Linienbreite: mu0*DeltaH (y) ueber dem Resonanzfeld (x) mit LLG-Fit.

**Mehrere Moden** (Korridore): Die Auswahl "Mode" schaltet zwischen
*Mode 1 … n* (je ein Korridor mit eigenem Kittel-/LLG-Fit und eigenem Plot)
und *Alle Moden* um; die Mode-Nummer ist die Korridor-Nummer
(:mod:`polderfit.auswertung.moden`).

Unerwuenschte Punkte lassen sich DIREKT im Plot entfernen (Einzelklick oder
Kasten aufziehen): bei einer Mode als Ausreisser des Linescans (gleiche Liste
wie im Hauptfenster), bei mehreren Moden nur fuer die angezeigte Mode
(``StapelErgebnis.ausreisser_moden``) - jeweils reversibel, der Fit rechnet
sofort neu. "Exportieren" schreibt Plot (PNG + PDF), eine Excel-Datei
mit den physikalischen Parametern samt Messfehlern und allen Datenpunkten
inklusive Einzelfehlern und Ausreisser-Kennzeichnung (bei mehreren Moden
zusaetzlich je Mode die Blaetter ``Parameter_M<k>`` / ``Punkte_M<k>``) sowie
die Punkte als CSV (Fehlerrechnung: Kovarianz der Kittel-/LLG-Fits,
lmfit-stderr je Linescan; vgl. Dissertation M. Mueller 2023, Kap. 2, und
Maier-Flaig et al. 2018).
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6 import QtCore, QtWidgets

from ..auswertung.moden import (
    ALLE_MODEN,
    ModenReihe,
    auswertung_je_mode,
    ergebnisse_fuer_mode,
)
from ..persistenz.ergebnis_export import kittel_llg_punkte_tabelle, kittel_llg_tabelle
from ..physik.kittel_llg import kittel_ip, kittel_oop, linienbreite
from . import farben as F

#: Relative Trefferdistanz (Anteil der Achsenspanne) fuer den Einzelklick.
_KLICK_TOLERANZ = 0.03
#: Mindest-Mausbewegung (Anteil der Spanne), ab der ein Klick zum Kasten wird.
_BOX_SCHWELLE_REL = 0.02


def _leere_reihe(mode: int) -> ModenReihe:
    return ModenReihe(mode=int(mode), indizes=np.array([], dtype=int), f=np.array([]),
                      b=np.array([]), dh=np.array([]), info=None, fehler="")


class AuswertungsFenster(QtWidgets.QDialog):
    """Interaktive Kittel/LLG-Auswertung mit Moden-Auswahl, Punkt-Entfernen und Export.

    ``hole_stapel()`` liefert den aktuellen Fit-Stapel des Hauptfensters;
    ``ausreisser_markieren(indizes)`` (Linescans), ``ausreisser_mode_markieren(paare)``
    (``(index, mode)``-Paare, nur die Auswertung dieser Mode) und
    ``ausreisser_rueckgaengig()`` laufen ueber das Hauptfenster (gemeinsame
    Listen, Undo, Overlay-Sync). Das Hauptfenster ruft :meth:`aktualisiere`
    auf, wenn sich Fits, Ausreisser oder Korridore aendern.
    """

    def __init__(self, hole_stapel, ausreisser_markieren=None,
                 ausreisser_rueckgaengig=None, geometrie: str = "oop",
                 hole_parameter=None, parent=None,
                 ausreisser_mode_markieren=None, geometrie_geaendert=None):
        super().__init__(parent)
        #: Liefert die aktuellen PhysikParameter (g/gamma, gamma_fest, r2_min)
        #: des Hauptfensters - oder None (Standardwerte).
        self._hole_parameter = hole_parameter
        self._cb_geometrie = geometrie_geaendert
        self.setWindowFlag(QtCore.Qt.Window, True)  # eigenes Fenster, nicht modal
        self.setWindowTitle("Kittel/LLG-Auswertung")
        self.resize(1080, 640)
        self._hole_stapel = hole_stapel
        self._cb_markieren = ausreisser_markieren
        self._cb_markieren_mode = ausreisser_mode_markieren
        self._cb_rueckgaengig = ausreisser_rueckgaengig
        self._info: dict | None = None      # Kittel/LLG der gewaehlten Einzel-Ansicht
        self._reihen: dict[int, ModenReihe] = {}
        self._moden: list[int] = [1]
        self._moden_aktiv = False           # Mode-Auswahl sichtbar (mehrere Moden)
        self._gewichtet = False
        self._fit_argumente: dict = {}
        self._punkt_indizes = np.array([], dtype=int)  # Stapel-Indizes der Plotpunkte
        self._punkt_moden = np.array([], dtype=int)    # Mode je Plotpunkt
        self._punkt_b = np.array([])
        self._punkt_f = np.array([])
        self._punkt_dh = np.array([])
        self._press = None                  # (ax, x, y) beim Druecken
        self._box_patch = None

        lay = QtWidgets.QVBoxLayout(self)

        kopf = QtWidgets.QHBoxLayout()
        kopf.addWidget(QtWidgets.QLabel("Kittel-Geometrie:"))
        self.geo_combo = QtWidgets.QComboBox()
        self.geo_combo.addItems(["oop", "ip"])
        self.geo_combo.setCurrentText(geometrie)
        self.geo_combo.currentTextChanged.connect(self._geometrie_gewaehlt)
        kopf.addWidget(self.geo_combo)
        kopf.addSpacing(12)
        self.mode_label = QtWidgets.QLabel("Mode:")
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.setToolTip(
            "Mode 1 … n (je ein Korridor mit eigenem Kittel-/LLG-Fit) oder alle Moden.")
        self.mode_combo.currentIndexChanged.connect(lambda _i: self.aktualisiere())
        kopf.addWidget(self.mode_label)
        kopf.addWidget(self.mode_combo)
        self.mode_label.setVisible(False)
        self.mode_combo.setVisible(False)
        kopf.addSpacing(16)
        hinweis = QtWidgets.QLabel("Klick/Kasten = Punkt ausschließen")
        hinweis.setToolTip(
            "Punkt anklicken oder Kasten aufziehen → Punkt wird als Ausreißer entfernt\n"
            "(bei mehreren Moden nur für die angezeigte Mode); der Fit rechnet sofort\n"
            "neu (reversibel).")
        kopf.addWidget(hinweis, 1)
        lay.addLayout(kopf)

        inhalt = QtWidgets.QHBoxLayout()
        self.figur = Figure(figsize=(8.5, 4.4))
        self.canvas = FigureCanvasQTAgg(self.figur)
        self.ax_disp = self.figur.add_subplot(121)
        self.ax_lb = self.figur.add_subplot(122)
        inhalt.addWidget(self.canvas, 1)

        self.param_text = QtWidgets.QTextBrowser()
        self.param_text.setMinimumWidth(290)
        self.param_text.setMaximumWidth(340)
        inhalt.addWidget(self.param_text)
        lay.addLayout(inhalt, 1)

        fuss = QtWidgets.QHBoxLayout()
        self.btn_rueckgaengig = QtWidgets.QPushButton("Rückgängig (letzter Schritt)")
        self.btn_rueckgaengig.clicked.connect(self._rueckgaengig)
        fuss.addWidget(self.btn_rueckgaengig)
        fuss.addStretch(1)
        self.btn_export = QtWidgets.QPushButton("Exportieren … (Excel + CSV + Plot)")
        self.btn_export.setToolTip(
            "Excel (Parameter mit 1σ-Fehlern in T und mT, alle Punkte; bei mehreren\n"
            "Moden zusätzlich je Mode ein Blatt), CSV der Punkte (Listendaten) und\n"
            "Plot als PNG + PDF.")
        self.btn_export.clicked.connect(self._exportieren)
        fuss.addWidget(self.btn_export)
        btn_zu = QtWidgets.QPushButton("Schließen")
        btn_zu.clicked.connect(self.close)
        fuss.addWidget(btn_zu)
        lay.addLayout(fuss)

        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_move)
        self.canvas.mpl_connect("button_release_event", self._on_release)

        self.aktualisiere()

    def _geometrie_gewaehlt(self, text: str) -> None:
        if self._cb_geometrie is not None:
            self._cb_geometrie(str(text))
        self.aktualisiere()

    # --- Moden-Auswahl ----------------------------------------------------------
    def mode_gewaehlt(self) -> int:
        """Gewaehlte Ansicht: Mode 1..n oder ``ALLE_MODEN`` (-1)."""
        if not self._moden_aktiv or self.mode_combo.count() == 0:
            return 1
        daten = self.mode_combo.currentData()
        return 1 if daten is None else int(daten)

    def setze_mode(self, mode: int) -> None:
        """Ansicht umschalten (Hauptmode / Mode k / alle) - wie die Auswahl im Kopf."""
        index = self.mode_combo.findData(int(mode))
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)   # loest aktualisiere() aus

    def _combo_befuellen(self, moden: list[int]) -> None:
        """Eintraege Mode k (je vorhandener Mode) / Alle Moden; sichtbar nur bei
        mehreren Moden. Beim ersten Erscheinen ist Mode 1 vorgewaehlt, danach
        bleibt die Auswahl erhalten."""
        aktiv = len(moden) > 1
        self._moden_aktiv = aktiv
        self.mode_label.setVisible(aktiv)
        self.mode_combo.setVisible(aktiv)
        if not aktiv:
            if self.mode_combo.count():
                self.mode_combo.blockSignals(True)
                self.mode_combo.clear()
                self.mode_combo.blockSignals(False)
            return
        gewuenscht = ([(f"Mode {k}", k) for k in moden]
                      + [("Alle Moden", ALLE_MODEN)])
        vorhanden = [(self.mode_combo.itemText(i), self.mode_combo.itemData(i))
                     for i in range(self.mode_combo.count())]
        if vorhanden == gewuenscht:
            return
        aktuell = self.mode_combo.currentData() if self.mode_combo.count() else None
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        for text, daten in gewuenscht:
            self.mode_combo.addItem(text, daten)
        ziel = 1 if aktuell is None else int(aktuell)
        index = self.mode_combo.findData(ziel)
        self.mode_combo.setCurrentIndex(index if index >= 0 else 0)
        self.mode_combo.blockSignals(False)

    @staticmethod
    def _farbe(mode: int, einzeln: bool) -> str:
        return F.SIGNAL_GRUEN if einzeln or mode <= 1 else F.mode_farbe(mode)

    def _titel_zusatz(self, mode: int) -> str:
        if not self._moden_aktiv:
            return ""
        if mode == ALLE_MODEN:
            return " – alle Moden"
        return f" – Mode {mode}"

    # --- Auswertung + Darstellung -------------------------------------------
    def aktualisiere(self) -> None:
        """Rechnet Kittel/LLG (je gewaehlter Mode) mit den aktiven Punkten neu und
        zeichnet alles."""
        stapel = self._hole_stapel()
        self.ax_disp.clear()
        self.ax_lb.clear()
        self._box_patch = None
        leer = np.array([], dtype=int)
        if stapel is None or not stapel.ergebnisse:
            self._reihen = {}
            self._info = None
            self._punkt_indizes = leer
            self._punkt_moden = leer.copy()
            self._punkt_b = self._punkt_f = self._punkt_dh = np.array([])
            self.param_text.setHtml("<p>Keine Fits vorhanden.</p>")
            self.canvas.draw_idle()
            return

        # Einstellbare Parameter (g/gamma, gamma_fest, r2_min) des Hauptfensters.
        p = self._hole_parameter() if self._hole_parameter is not None else None
        r2_min = p.r2_min if p is not None else 0.9
        self._moden = list(stapel.moden_vorhanden())
        self._combo_befuellen(self._moden)
        mode = self.mode_gewaehlt()
        if mode == ALLE_MODEN:
            modi = list(self._moden)
        else:
            modi = [mode]

        geometrie = self.geo_combo.currentText()
        self._gewichtet = bool(getattr(p, "gewichtet", False)) if p is not None else False
        self._fit_argumente = dict(geometrie=geometrie, r2_min=r2_min, gewichtet=self._gewichtet)
        if p is not None:
            self._fit_argumente.update(gamma_fest=p.gamma_fest, gamma_start=p.gamma)
        self._reihen = auswertung_je_mode(stapel, modi, **self._fit_argumente)
        reihen = list(self._reihen.values())
        self._punkt_indizes = (np.concatenate([r.indizes for r in reihen]).astype(int)
                               if reihen else leer)
        self._punkt_moden = (np.concatenate([np.full(r.n, r.mode, dtype=int) for r in reihen])
                             if reihen else leer.copy())
        self._punkt_f = np.concatenate([r.f for r in reihen]) if reihen else np.array([])
        self._punkt_b = np.concatenate([r.b for r in reihen]) if reihen else np.array([])
        self._punkt_dh = np.concatenate([r.dh for r in reihen]) if reihen else np.array([])
        self._info = self._reihen[mode].info if mode in self._reihen else None

        einzeln = len(reihen) == 1
        for r in reihen:
            farbe = self._farbe(r.mode, einzeln)
            label = "verwendete Fits" if einzeln else f"Mode {r.mode}"
            # Dispersionsplot: Feld (x) gegen Frequenz (y); Linienbreite ueber dem Feld.
            self.ax_disp.plot(r.b, r.f / 1e9, "o", ms=4.5, color=farbe, mec="white",
                              mew=0.6, label=label)
            self.ax_lb.plot(r.b, r.dh * 1e3, "o", ms=4.5, color=farbe, mec="white",
                            mew=0.6, label=label)
            if r.info is None or r.n == 0:
                continue
            kit, llg = r.info["kittel"], r.info["llg"]
            ff = np.linspace(r.f.min(), r.f.max(), 400)
            if geometrie == "ip":
                bb = kittel_ip(ff, kit["mu0Meff"], kit["mu0Hu"], kit["gamma"])
            else:
                bb = kittel_oop(ff, kit["mu0Meff"], kit["gamma"])
            linie = F.TEXT if einzeln else farbe
            self.ax_disp.plot(bb, ff / 1e9, "-", color=linie,
                              label="Kittel-Fit" if einzeln else f"Kittel M{r.mode}")
            reihenfolge = np.argsort(r.b)
            self.ax_lb.plot(
                r.b[reihenfolge],
                linienbreite(r.f[reihenfolge], llg["mu0Hinh"], llg["alpha"], llg["gamma"]) * 1e3,
                "-", color=linie, label="LLG-Fit" if einzeln else f"LLG M{r.mode}")
        zusatz = self._titel_zusatz(mode)
        self.ax_disp.set_xlabel(r"Resonanzfeld $\mu_0 H_{res}$ (T)")
        self.ax_disp.set_ylabel("Frequenz (GHz)")
        self.ax_disp.set_title(f"Dispersion (Kittel, {geometrie}){zusatz}")
        self.ax_disp.legend(fontsize=8)
        self.ax_lb.set_xlabel(r"Resonanzfeld $\mu_0 H_{res}$ (T)")
        self.ax_lb.set_ylabel(r"Linienbreite $\mu_0\Delta H$ (mT)")
        self.ax_lb.set_title(f"Linienbreite (LLG){zusatz}")
        self.ax_lb.legend(fontsize=8)
        try:
            self.figur.tight_layout()
        except Exception:
            pass
        self.canvas.draw_idle()
        self._zeige_parameter(stapel, mode)

    def _zeige_parameter(self, stapel, mode: int) -> None:
        paare = list(getattr(stapel, "ausreisser_moden", []))
        zeilen = [f"<p><b>Punkte:</b> {self._punkt_indizes.size} verwendet, "
                  f"{len(stapel.ausreisser)} Ausreißer ausgeschlossen"
                  + (f", {len(paare)} Punkt(e) nur je Mode ausgeschlossen" if paare else "")
                  + "</p>"]
        if self._moden_aktiv:
            was = "alle Moden" if mode == ALLE_MODEN else f"Mode {mode} (Korridor M{mode})"
            zeilen.append(f"<p><b>Mode:</b> {was}</p>")
        mehrere = len(self._reihen) > 1
        irgendein_fit = False
        for r in self._reihen.values():
            if mehrere:
                zeilen.append(f"<h3 style='color:{self._farbe(r.mode, False)}'>"
                              f"Mode {r.mode} – {r.n} Punkte</h3>")
            if r.info is None:
                zeilen.append(f"<p style='color:{F.TEXT_ROT}'>{r.fehler}</p>")
                continue
            irgendein_fit = True
            kit, llg = r.info["kittel"], r.info["llg"]
            g_err = kit.get("g_faktor_err", float("nan"))

            def w(wert, err, faktor=1.0, fmt=".4f"):
                # Nur der Wert - Unsicherheiten stehen im Export (Nutzerwunsch: keine
                # Statistik in der Anzeige).
                return f"{wert*faktor:{fmt}}"

            ueberschrift = "h4" if mehrere else "h3"
            zeilen.append(f"<{ueberschrift}>Kittel</{ueberschrift}><ul>"
                          f"<li>µ₀M<sub>eff</sub> = {w(kit['mu0Meff'], kit['mu0Meff_err'])} T "
                          f"= {w(kit['mu0Meff'], kit['mu0Meff_err'], 1e3, '.1f')} mT</li>"
                          f"<li>g = {w(kit['g_faktor'], g_err, fmt='.4f')}</li>")
            if "mu0Hu" in kit:
                zeilen.append(f"<li>µ₀H<sub>u</sub> = {w(kit['mu0Hu'], kit['mu0Hu_err'])} T "
                              f"= {w(kit['mu0Hu'], kit['mu0Hu_err'], 1e3, '.2f')} mT</li>")
            zeilen.append(f"<li>γ = {kit['gamma']:.4e} rad/(s·T)</li>"
                          f"<li>R² = {kit['R2']:.5f}</li></ul>")
            zeilen.append(f"<{ueberschrift}>LLG (Dämpfung)</{ueberschrift}><ul>"
                          f"<li>α = {w(llg['alpha'], llg['alpha_err'], fmt='.3e')}</li>"
                          f"<li>µ₀ΔH<sub>0</sub> (inhomogen) = "
                          f"{w(llg['mu0Hinh'], llg['mu0Hinh_err'], 1e3, '.3f')} mT "
                          f"= {w(llg['mu0Hinh'], llg['mu0Hinh_err'], 1.0, '.5f')} T</li>"
                          f"<li>R² = {llg['R2']:.5f}</li></ul>")
        if irgendein_fit:
            modus = "gewichtet" if self._gewichtet else "ungewichtet"
            zeilen.append(f"<p style='color:{F.TEXT_SCHWACH};font-size:11px'>Kittel-/LLG-Fit "
                          f"{modus} (umschaltbar: Strg+P). Unsicherheiten der Parameter: "
                          "im Export.</p>")
        self.param_text.setHtml("".join(zeilen))

    # --- Punkt-Entfernen ------------------------------------------------------
    def _rueckgaengig(self) -> None:
        if self._cb_rueckgaengig is not None:
            self._cb_rueckgaengig()
        self.aktualisiere()

    def _achsen_punkte(self, ax):
        """(x, y) der Plotpunkte im Koordinatensystem der jeweiligen Achse."""
        if ax is self.ax_disp:
            return self._punkt_b, self._punkt_f / 1e9
        return self._punkt_b, self._punkt_dh * 1e3

    def _on_press(self, event):
        if event.inaxes not in (self.ax_disp, self.ax_lb):
            return
        if event.xdata is None or event.ydata is None:
            return
        self._press = (event.inaxes, event.xdata, event.ydata)

    def _on_move(self, event):
        if self._press is None:
            return
        ax, x0, y0 = self._press
        if event.inaxes is not ax or event.xdata is None:
            return
        from matplotlib.patches import Rectangle
        if self._box_patch is None:
            xs = abs(np.diff(ax.get_xlim())[0]) * _BOX_SCHWELLE_REL
            ys = abs(np.diff(ax.get_ylim())[0]) * _BOX_SCHWELLE_REL
            if abs(event.xdata - x0) <= xs and abs(event.ydata - y0) <= ys:
                return
            self._box_patch = ax.add_patch(Rectangle(
                (x0, y0), 0, 0, facecolor=F.SIGNAL_BLAU + "33", edgecolor=F.SIGNAL_BLAU, lw=1.2))
        self._box_patch.set_bounds(min(x0, event.xdata), min(y0, event.ydata),
                                   abs(event.xdata - x0), abs(event.ydata - y0))
        self.canvas.draw_idle()

    def _on_release(self, event):
        if self._press is None:
            return
        ax, x0, y0 = self._press
        self._press = None
        war_box = self._box_patch is not None
        if war_box:
            self._box_patch.remove()
            self._box_patch = None
            self.canvas.draw_idle()
        if self._punkt_indizes.size == 0:
            return
        px, py = self._achsen_punkte(ax)
        if war_box and event.xdata is not None and event.ydata is not None:
            x1, y1 = event.xdata, event.ydata
            drin = ((px >= min(x0, x1)) & (px <= max(x0, x1))
                    & (py >= min(y0, y1)) & (py <= max(y0, y1)))
            treffer = [int(k) for k in np.flatnonzero(drin)]
        elif not war_box and event.inaxes is ax:
            xs = abs(np.diff(ax.get_xlim())[0]) or 1e-12
            ys = abs(np.diff(ax.get_ylim())[0]) or 1e-12
            abstand = np.hypot((px - x0) / xs, (py - y0) / ys)
            naechster = int(np.argmin(abstand))
            if abstand[naechster] > _KLICK_TOLERANZ:
                return
            treffer = [naechster]
        else:
            return
        self._punkte_entfernen(treffer)

    def _punkte_entfernen(self, treffer: list[int]) -> None:
        """Plotpunkte (Positionen) als Ausreisser melden: eine Mode ->
        Linescan-Ausreisser, mehrere Moden -> nur ``(index, mode)``."""
        if not self._moden_aktiv:
            linescans = [int(self._punkt_indizes[k]) for k in treffer]
            paare = []
        else:
            linescans = []
            paare = [(int(self._punkt_indizes[k]), int(self._punkt_moden[k])) for k in treffer]
        geaendert = False
        if linescans and self._cb_markieren is not None:
            self._cb_markieren(linescans)
            geaendert = True
        if paare and self._cb_markieren_mode is not None:
            self._cb_markieren_mode(paare)
            geaendert = True
        if geaendert:
            self.aktualisiere()

    # --- Export ---------------------------------------------------------------
    def verwendete_indizes(self) -> list[int]:
        """Stapel-Indizes der in der aktuellen Ansicht verwendeten Punkte."""
        return [int(i) for i in self._punkt_indizes]

    def _reihen_alle_moden(self, stapel) -> dict[int, ModenReihe]:
        modi = list(self._moden)
        if all(k in self._reihen for k in modi):
            return {k: self._reihen[k] for k in modi}
        return auswertung_je_mode(stapel, modi, **self._fit_argumente)

    def _parameter_tabelle(self, stapel, reihe: ModenReihe, kennzeichnen: bool) -> pd.DataFrame:
        mode = reihe.mode
        paare = [(i, k) for i, k in getattr(stapel, "ausreisser_moden", []) if int(k) == mode]
        n_aus = len(stapel.ausreisser) + len(paare)
        return kittel_llg_tabelle(reihe.info, gewichtet=self._gewichtet, n_punkte=reihe.n,
                                  n_ausreisser=n_aus, mode=mode if kennzeichnen else None,
                                  mode_text=f"Mode M{mode}" if kennzeichnen else "")

    def _punkte_tabelle(self, stapel, reihe: ModenReihe, kennzeichnen: bool) -> pd.DataFrame:
        mode = reihe.mode
        verwendet = [int(i) for i in reihe.indizes]
        liste = stapel.ergebnisse_mode(mode)
        gesperrt = set(stapel.ausreisser) | {
            int(i) for i, k in getattr(stapel, "ausreisser_moden", []) if int(k) == mode}
        return kittel_llg_punkte_tabelle(liste, sorted(gesperrt), verwendet,
                                         mode=mode if kennzeichnen else None)

    def exportiere(self, basis: str, csv_deutsch: bool = False) -> list[str]:
        """Schreibt ``<basis>.xlsx``, ``<basis>_punkte.csv``, ``<basis>.png/.pdf``.

        Excel: Blaetter ``Parameter``/``Punkte`` der aktuellen Ansicht; bei
        mehreren Moden zusaetzlich ``Parameter_M<k>``/``Punkte_M<k>`` je Mode.
        Liefert die geschriebenen Pfade. Wird auch von "Alles speichern" genutzt.
        """
        stapel = self._hole_stapel()
        if stapel is None or not stapel.ergebnisse:
            return []
        geschrieben = []
        self.figur.savefig(basis + ".png", dpi=300)
        self.figur.savefig(basis + ".pdf")
        geschrieben += [basis + ".png", basis + ".pdf"]

        def _zusammen(tabellen):
            voll = [t for t in tabellen if not t.empty]
            return pd.concat(voll, ignore_index=True) if voll else pd.DataFrame()

        mode = self.mode_gewaehlt()
        mehrere = self._moden_aktiv
        if mode == ALLE_MODEN:
            reihen = list(self._reihen.values())
            tab_param = _zusammen([self._parameter_tabelle(stapel, r, True) for r in reihen])
            tab_punkte = _zusammen([self._punkte_tabelle(stapel, r, True) for r in reihen])
        else:
            reihe = self._reihen.get(mode) or _leere_reihe(mode)
            tab_param = self._parameter_tabelle(stapel, reihe, mehrere)
            tab_punkte = self._punkte_tabelle(stapel, reihe, mehrere)
        if mehrere:
            # Je Mode ein Blatt - keine doppelten Blaetter fuer die aktuelle Ansicht.
            blaetter = []
            for k, r in self._reihen_alle_moden(stapel).items():
                blaetter.append((f"Parameter_M{k}", self._parameter_tabelle(stapel, r, True)))
                blaetter.append((f"Punkte_M{k}", self._punkte_tabelle(stapel, r, True)))
        else:
            blaetter = [("Parameter", tab_param), ("Punkte", tab_punkte)]
        with pd.ExcelWriter(basis + ".xlsx", engine="openpyxl") as writer:
            for name, tab in blaetter:
                tab.to_excel(writer, sheet_name=name, index=False)
        geschrieben.append(basis + ".xlsx")
        csv_pfad = basis + "_punkte.csv"
        if mehrere:
            # CSV mit den Punkten ALLER Moden (Spalte mode), nicht nur der Ansicht.
            tab_punkte = _zusammen([self._punkte_tabelle(stapel, r, True)
                                    for r in self._reihen_alle_moden(stapel).values()])
        if csv_deutsch:
            tab_punkte.to_csv(csv_pfad, index=False, sep=";", decimal=",", encoding="utf-8-sig")
        else:
            tab_punkte.to_csv(csv_pfad, index=False)
        geschrieben.append(csv_pfad)
        return geschrieben

    def _exportieren(self) -> None:
        stapel = self._hole_stapel()
        if stapel is None or not stapel.ergebnisse:
            return
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Auswertung exportieren", "kittel_llg_auswertung.xlsx",
            "Excel (*.xlsx)")
        if not pfad:
            return
        basis, _endung = os.path.splitext(pfad)
        p = self._hole_parameter() if self._hole_parameter is not None else None
        csv_deutsch = bool(getattr(p, "csv_deutsch", False)) if p is not None else False
        dateien = self.exportiere(basis, csv_deutsch=csv_deutsch)
        QtWidgets.QMessageBox.information(
            self, "Export", "Gespeichert:\n" + "\n".join(dateien))

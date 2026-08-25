# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Kittel/LLG-Auswertungsfenster (eigenes, nicht-modales Fenster).

Zeigt die uebergreifende Auswertung mit Feld auf der x-Achse (wie im Farbplot):

* Dispersion: Resonanzfeld (x) gegen Frequenz (y) mit Kittel-Fit,
* Linienbreite: mu0*DeltaH (y) ueber dem Resonanzfeld (x) mit LLG-Fit.

Unerwuenschte Punkte lassen sich DIREKT im Plot entfernen (Einzelklick oder
Kasten aufziehen) - sie werden als Ausreisser des Fit-Stapels markiert
(reversibel, gleiche Liste wie im Hauptfenster) und der Kittel-/LLG-Fit
rechnet sofort neu. "Exportieren" schreibt Plot (PNG + PDF) und eine
Excel-Datei mit den physikalischen Parametern samt Messfehlern sowie allen
Datenpunkten inklusive Einzelfehlern und Ausreisser-Kennzeichnung
(Fehlerrechnung: Kovarianz der Kittel-/LLG-Fits, lmfit-stderr je Linescan;
vgl. Dissertation M. Mueller 2023, Kap. 2, und Maier-Flaig et al. 2018).
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6 import QtCore, QtWidgets

from ..auswertung.uebersicht import auswertung_kittel_llg
from ..persistenz.ergebnis_export import kittel_llg_punkte_tabelle, kittel_llg_tabelle
from ..physik.kittel_llg import kittel_ip, kittel_oop, linienbreite
from . import farben as F

#: Relative Trefferdistanz (Anteil der Achsenspanne) fuer den Einzelklick.
_KLICK_TOLERANZ = 0.03
#: Mindest-Mausbewegung (Anteil der Spanne), ab der ein Klick zum Kasten wird.
_BOX_SCHWELLE_REL = 0.02


class AuswertungsFenster(QtWidgets.QDialog):
    """Interaktive Kittel/LLG-Auswertung mit Punkt-Entfernen und Export.

    ``hole_stapel()`` liefert den aktuellen Fit-Stapel des Hauptfensters;
    ``ausreisser_markieren(indizes)`` und ``ausreisser_rueckgaengig()`` laufen
    ueber das Hauptfenster (gemeinsame Ausreisser-Liste, Undo, Overlay-Sync).
    Das Hauptfenster ruft :meth:`aktualisiere` auf, wenn sich die Liste
    anderweitig aendert.
    """

    def __init__(self, hole_stapel, ausreisser_markieren=None,
                 ausreisser_rueckgaengig=None, geometrie: str = "oop",
                 hole_parameter=None, parent=None):
        super().__init__(parent)
        #: Liefert die aktuellen PhysikParameter (g/gamma, gamma_fest, r2_min)
        #: des Hauptfensters - oder None (Standardwerte).
        self._hole_parameter = hole_parameter
        self.setWindowFlag(QtCore.Qt.Window, True)  # eigenes Fenster, nicht modal
        self.setWindowTitle("Kittel/LLG-Auswertung")
        self.resize(1080, 640)
        self._hole_stapel = hole_stapel
        self._cb_markieren = ausreisser_markieren
        self._cb_rueckgaengig = ausreisser_rueckgaengig
        self._info: dict | None = None      # letzter erfolgreicher Auswertungslauf
        self._punkt_indizes = np.array([], dtype=int)  # Stapel-Indizes der Plotpunkte
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
        self.geo_combo.currentTextChanged.connect(lambda _t: self.aktualisiere())
        kopf.addWidget(self.geo_combo)
        kopf.addSpacing(16)
        hinweis = QtWidgets.QLabel(
            "Punkt anklicken oder Kasten aufziehen → Punkt wird als Ausreißer "
            "entfernt und der Fit rechnet sofort neu (reversibel).")
        hinweis.setWordWrap(True)
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
            "Excel (Parameter mit 1σ-Fehlern in T und mT, alle Punkte), CSV der\n"
            "Punkte (Listendaten) und Plot als PNG + PDF.")
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

    # --- Auswertung + Darstellung -------------------------------------------
    def aktualisiere(self) -> None:
        """Rechnet Kittel/LLG mit den aktiven Punkten neu und zeichnet alles."""
        stapel = self._hole_stapel()
        self.ax_disp.clear()
        self.ax_lb.clear()
        if self._box_patch is not None:
            self._box_patch = None
        if stapel is None or not stapel.ergebnisse:
            self.param_text.setHtml("<p>Keine Fits vorhanden.</p>")
            self.canvas.draw_idle()
            return

        # Einstellbare Parameter (g/gamma, gamma_fest, r2_min) des Hauptfensters.
        p = self._hole_parameter() if self._hole_parameter is not None else None
        r2_min = p.r2_min if p is not None else 0.9

        # Plotpunkte = aktive (nicht ausgeschlossene), brauchbare Einzelfits;
        # gleiche Kriterien wie die Auswertung selbst (_gute_ergebnisse).
        gesperrt = set(stapel.ausreisser)
        idx, f, b, dh = [], [], [], []
        for i, e in enumerate(stapel.ergebnisse):
            if i in gesperrt:
                continue
            gut = (e.erfolg and not e.problematisch and np.isfinite(e.B_res)
                   and (not np.isfinite(e.R2) or e.R2 >= r2_min))
            if gut:
                idx.append(i)
                f.append(e.frequenz)
                b.append(e.B_res)
                dh.append(e.dH)
        self._punkt_indizes = np.array(idx, dtype=int)
        self._punkt_f = np.array(f)
        self._punkt_b = np.array(b)
        self._punkt_dh = np.array(dh)

        geometrie = self.geo_combo.currentText()
        self._gewichtet = getattr(p, "gewichtet", False) if p is not None else False
        self._info = None
        fehler_text = ""
        if self._punkt_indizes.size >= 3:
            try:
                if p is not None:
                    self._info = auswertung_kittel_llg(
                        stapel.ergebnisse_aktiv(), geometrie=geometrie,
                        gamma_fest=p.gamma_fest, gamma_start=p.gamma,
                        r2_min=p.r2_min,
                        gewichtet=getattr(p, "gewichtet", False))
                else:
                    self._info = auswertung_kittel_llg(stapel.ergebnisse_aktiv(),
                                                       geometrie=geometrie)
            except Exception as exc:
                fehler_text = str(exc)
        else:
            fehler_text = "Zu wenige gute Punkte fuer den Kittel-/LLG-Fit (min. 3)."

        # Dispersionsplot: Feld (x) gegen Frequenz (y).
        self.ax_disp.plot(self._punkt_b, self._punkt_f / 1e9, "o", ms=4.5,
                          color=F.SIGNAL_GRUEN, mec="white", mew=0.6, label="verwendete Fits")
        # Linienbreite ueber dem Feld.
        self.ax_lb.plot(self._punkt_b, self._punkt_dh * 1e3, "o", ms=4.5,
                        color=F.SIGNAL_GRUEN, mec="white", mew=0.6, label="verwendete Fits")
        if self._info is not None:
            kit, llg = self._info["kittel"], self._info["llg"]
            ff = np.linspace(self._punkt_f.min(), self._punkt_f.max(), 400)
            if geometrie == "ip":
                bb = kittel_ip(ff, kit["mu0Meff"], kit["mu0Hu"], kit["gamma"])
            else:
                bb = kittel_oop(ff, kit["mu0Meff"], kit["gamma"])
            self.ax_disp.plot(bb, ff / 1e9, "-", color=F.TEXT, label="Kittel-Fit")
            reihenfolge = np.argsort(self._punkt_b)
            self.ax_lb.plot(
                self._punkt_b[reihenfolge],
                linienbreite(self._punkt_f[reihenfolge], llg["mu0Hinh"],
                             llg["alpha"], llg["gamma"]) * 1e3,
                "-", color=F.TEXT, label="LLG-Fit")
        self.ax_disp.set_xlabel(r"Resonanzfeld $\mu_0 H_{res}$ (T)")
        self.ax_disp.set_ylabel("Frequenz (GHz)")
        self.ax_disp.set_title(f"Dispersion (Kittel, {geometrie})")
        self.ax_disp.legend(fontsize=8)
        self.ax_lb.set_xlabel(r"Resonanzfeld $\mu_0 H_{res}$ (T)")
        self.ax_lb.set_ylabel(r"Linienbreite $\mu_0\Delta H$ (mT)")
        self.ax_lb.set_title("Linienbreite (LLG)")
        self.ax_lb.legend(fontsize=8)
        try:
            self.figur.tight_layout()
        except Exception:
            pass
        self.canvas.draw_idle()
        self._zeige_parameter(stapel, fehler_text)

    def _zeige_parameter(self, stapel, fehler_text: str) -> None:
        n_aus = len(stapel.ausreisser)
        zeilen = [f"<p><b>Punkte:</b> {self._punkt_indizes.size} verwendet, "
                  f"{n_aus} Ausreißer ausgeschlossen</p>"]
        if self._info is None:
            zeilen.append(f"<p style='color:{F.TEXT_ROT}'>{fehler_text}</p>")
        else:
            kit, llg = self._info["kittel"], self._info["llg"]
            g_err = kit.get("g_faktor_err", float("nan"))

            def w(wert, err, faktor=1.0, fmt=".4f"):
                # Nur der Wert - Unsicherheiten stehen im Export (Nutzerwunsch: keine
                # Statistik in der Anzeige).
                return f"{wert*faktor:{fmt}}"

            zeilen.append("<h3>Kittel</h3><ul>"
                          f"<li>µ₀M<sub>eff</sub> = {w(kit['mu0Meff'], kit['mu0Meff_err'])} T "
                          f"= {w(kit['mu0Meff'], kit['mu0Meff_err'], 1e3, '.1f')} mT</li>"
                          f"<li>g = {w(kit['g_faktor'], g_err, fmt='.4f')}</li>")
            if "mu0Hu" in kit:
                zeilen.append(f"<li>µ₀H<sub>u</sub> = {w(kit['mu0Hu'], kit['mu0Hu_err'])} T "
                              f"= {w(kit['mu0Hu'], kit['mu0Hu_err'], 1e3, '.2f')} mT</li>")
            zeilen.append(f"<li>γ = {kit['gamma']:.4e} rad/(s·T)</li>"
                          f"<li>R² = {kit['R2']:.5f}</li></ul>")
            zeilen.append("<h3>LLG (Dämpfung)</h3><ul>"
                          f"<li>α = {w(llg['alpha'], llg['alpha_err'], fmt='.3e')}</li>"
                          f"<li>µ₀ΔH<sub>0</sub> (inhomogen) = "
                          f"{w(llg['mu0Hinh'], llg['mu0Hinh_err'], 1e3, '.3f')} mT "
                          f"= {w(llg['mu0Hinh'], llg['mu0Hinh_err'], 1.0, '.5f')} T</li>"
                          f"<li>R² = {llg['R2']:.5f}</li></ul>")
            modus = ("gewichtet" if getattr(self, "_gewichtet", False) else "ungewichtet")
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
            indizes = [int(i) for i in self._punkt_indizes[drin]]
        elif not war_box and event.inaxes is ax:
            xs = abs(np.diff(ax.get_xlim())[0]) or 1e-12
            ys = abs(np.diff(ax.get_ylim())[0]) or 1e-12
            abstand = np.hypot((px - x0) / xs, (py - y0) / ys)
            naechster = int(np.argmin(abstand))
            if abstand[naechster] > _KLICK_TOLERANZ:
                return
            indizes = [int(self._punkt_indizes[naechster])]
        else:
            return
        if indizes and self._cb_markieren is not None:
            self._cb_markieren(indizes)
            self.aktualisiere()

    # --- Export ---------------------------------------------------------------
    def verwendete_indizes(self) -> list[int]:
        """Stapel-Indizes der im Kittel-/LLG-Fit verwendeten Punkte."""
        return [int(i) for i in self._punkt_indizes]

    def exportiere(self, basis: str, csv_deutsch: bool = False) -> list[str]:
        """Schreibt ``<basis>.xlsx``, ``<basis>_punkte.csv``, ``<basis>.png/.pdf``.

        Liefert die geschriebenen Pfade. Wird auch von "Alles speichern" genutzt.
        """
        stapel = self._hole_stapel()
        if stapel is None or not stapel.ergebnisse:
            return []
        geschrieben = []
        self.figur.savefig(basis + ".png", dpi=300)
        self.figur.savefig(basis + ".pdf")
        geschrieben += [basis + ".png", basis + ".pdf"]
        tab_param = kittel_llg_tabelle(self._info, gewichtet=getattr(self, "_gewichtet", False),
                                       n_punkte=int(self._punkt_indizes.size),
                                       n_ausreisser=len(stapel.ausreisser))
        tab_punkte = kittel_llg_punkte_tabelle(stapel.ergebnisse, stapel.ausreisser,
                                               self.verwendete_indizes())
        with pd.ExcelWriter(basis + ".xlsx", engine="openpyxl") as writer:
            tab_param.to_excel(writer, sheet_name="Parameter", index=False)
            tab_punkte.to_excel(writer, sheet_name="Punkte", index=False)
        geschrieben.append(basis + ".xlsx")
        csv_pfad = basis + "_punkte.csv"
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

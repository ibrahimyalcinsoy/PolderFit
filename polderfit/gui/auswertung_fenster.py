# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Kittel/LLG-Auswertungsfenster (eigenes, nicht-modales Fenster).

Zeigt die uebergreifende Auswertung mit Feld auf der x-Achse (wie im Farbplot):

* Dispersion: Resonanzfeld (x) gegen Frequenz (y) mit Kittel-Fit,
* Linienbreite: mu0*DeltaH (y) ueber dem Resonanzfeld (x) mit LLG-Fit.

**Mehrere Moden** (Korridore): Die Auswahl "Mode" schaltet zwischen
*Mode 1 … n* (je ein Korridor mit eigenem Kittel-/LLG-Fit und eigenem Plot)
und *Alle Moden* um; die Mode-Nummer ist die Korridor-Nummer
(:mod:`polderfit.auswertung.moden`).

Werkzeugleiste im Plot: *Auswaehlen* (Punkt anklicken schaltet ihn in die
Auswahl, Kasten fuegt alle Punkte darin hinzu), Gesamtansicht, Verschieben,
Zoom. *Auswahl ausblenden* (Entf) schliesst die gewaehlten Punkte aus: bei
einer Mode als Ausreisser des Linescans (gleiche Liste wie im Hauptfenster,
Farbplot grau), bei mehreren Moden nur fuer die jeweilige Mode
(``StapelErgebnis.ausreisser_moden``). Ausgeblendete Punkte lassen sich grau
einblenden, auswaehlen und wieder aufnehmen; der Fit rechnet sofort neu. "Exportieren" schreibt Plot (PNG + PDF), eine Excel-Datei
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
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6 import QtCore, QtGui, QtWidgets

from ..auswertung.moden import (
    ALLE_MODEN,
    ModenReihe,
    auswertung_je_mode,
    ergebnisse_fuer_mode,
)
from ..persistenz.ergebnis_export import kittel_llg_punkte_tabelle, kittel_llg_tabelle
from ..physik.kittel_llg import kittel_ip, kittel_oop, linienbreite
from . import farben as F
from ..sprache import N_, tr

#: Relative Trefferdistanz (Anteil der Achsenspanne) fuer den Einzelklick.
_KLICK_TOLERANZ = 0.03
#: Mindest-Mausbewegung (Anteil der Spanne), ab der ein Klick zum Kasten wird.
_BOX_SCHWELLE_REL = 0.02
_HINWEIS = N_("Auswählen: Punkt anklicken (an/aus) oder Kasten aufziehen → "
              "„Auswahl ausblenden“ (Entf)")


class _Werkzeugleiste(NavigationToolbar2QT):
    """Matplotlib-Werkzeugleiste, reduziert auf Gesamtansicht, Verschieben, Zoom."""

    toolitems = [
        ("Home", N_("Gesamtansicht (alle Punkte)"), "home", "home"),
        ("Pan", N_("Verschieben: linke Maustaste ziehen\nZoomen: rechte Maustaste ziehen"),
         "move", "pan"),
        ("Zoom", N_("Hineinzoomen: Rechteck aufziehen"), "zoom_to_rect", "zoom"),
    ]

    def __init__(self, canvas, parent=None):
        super().__init__(canvas, parent, coordinates=True)
        self.gesamtansicht = None
        for _text, tip, _bild, methode in self.toolitems:
            self._actions[methode].setToolTip(tr(tip))

    def home(self, *args):
        if self.gesamtansicht is not None:
            self.gesamtansicht()
        else:
            super().home(*args)


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
                 ausreisser_mode_markieren=None, geometrie_geaendert=None,
                 ausreisser_wieder_aufnehmen=None, ausreisser_mode_wieder_aufnehmen=None):
        super().__init__(parent)
        #: Liefert die aktuellen PhysikParameter (g/gamma, gamma_fest, r2_min)
        #: des Hauptfensters - oder None (Standardwerte).
        self._hole_parameter = hole_parameter
        self._cb_geometrie = geometrie_geaendert
        self.setWindowFlag(QtCore.Qt.Window, True)  # eigenes Fenster, nicht modal
        self.setWindowTitle(tr("Kittel/LLG-Auswertung"))
        self.resize(1080, 640)
        self._hole_stapel = hole_stapel
        self._cb_markieren = ausreisser_markieren
        self._cb_markieren_mode = ausreisser_mode_markieren
        self._cb_rueckgaengig = ausreisser_rueckgaengig
        self._cb_wieder = ausreisser_wieder_aufnehmen
        self._cb_wieder_mode = ausreisser_mode_wieder_aufnehmen
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
        # Auswaehlbare Punkte: verwendete ("v") und - falls eingeblendet - ausgeblendete
        # ("a"); Schluessel (art, Stapel-Index, Mode).
        self._kand_keys: list[tuple[str, int, int]] = []
        self._kand_b = np.array([])
        self._kand_f = np.array([])
        self._kand_dh = np.array([])
        self._aus_art: dict[tuple[int, int], str] = {}   # (index, mode) -> "ls"/"mode"
        self._auswahl: set[tuple[str, int, int]] = set()
        self._markierung: dict = {}
        self._auto_ansicht = None           # Achsgrenzen der Gesamtansicht
        self._press = None                  # (ax, x, y) beim Druecken
        self._box_patch = None

        lay = QtWidgets.QVBoxLayout(self)

        kopf = QtWidgets.QHBoxLayout()
        kopf.addWidget(QtWidgets.QLabel(tr("Kittel-Geometrie:")))
        self.geo_combo = QtWidgets.QComboBox()
        self.geo_combo.addItems(["oop", "ip"])
        self.geo_combo.setCurrentText(geometrie)
        self.geo_combo.currentTextChanged.connect(self._geometrie_gewaehlt)
        kopf.addWidget(self.geo_combo)
        kopf.addSpacing(12)
        self.mode_label = QtWidgets.QLabel(tr("Mode:"))
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.setToolTip(
            tr("Mode 1 … n (je ein Korridor mit eigenem Kittel-/LLG-Fit) oder alle Moden."))
        self.mode_combo.currentIndexChanged.connect(
            lambda _i: self.aktualisiere(ansicht_behalten=False))
        kopf.addWidget(self.mode_label)
        kopf.addWidget(self.mode_combo)
        self.mode_label.setVisible(False)
        self.mode_combo.setVisible(False)
        kopf.addSpacing(16)
        self.hinweis = QtWidgets.QLabel(tr(_HINWEIS))
        self.hinweis.setToolTip(
            tr("Werkzeug „Auswählen“: Punkt anklicken schaltet ihn in die Auswahl (blauer\n"
            "Ring, in beiden Plots), Kasten aufziehen fügt alle Punkte darin hinzu.\n"
            "„Auswahl ausblenden“ (Entf) schließt sie aus der Auswertung aus – auch im\n"
            "Hauptfenster/Farbplot (grau; bei mehreren Moden nur für die jeweilige Mode).\n"
            "Zoom/Verschieben für dichte Punktwolken; „ausgeblendete Punkte zeigen“ +\n"
            "„Auswahl einblenden“ nimmt Punkte wieder auf. Esc = Auswahl aufheben."))
        kopf.addWidget(self.hinweis, 1)
        lay.addLayout(kopf)

        self.figur = Figure(figsize=(8.5, 4.4))
        self.canvas = FigureCanvasQTAgg(self.figur)
        self.ax_disp = self.figur.add_subplot(121)
        self.ax_lb = self.figur.add_subplot(122)
        self.werkzeuge = _Werkzeugleiste(self.canvas, self)
        self.werkzeuge.gesamtansicht = self._gesamtansicht
        self._werkzeuge_einrichten()
        lay.addWidget(self.werkzeuge)

        inhalt = QtWidgets.QHBoxLayout()
        inhalt.addWidget(self.canvas, 1)

        self.param_text = QtWidgets.QTextBrowser()
        self.param_text.setMinimumWidth(290)
        self.param_text.setMaximumWidth(340)
        inhalt.addWidget(self.param_text)
        lay.addLayout(inhalt, 1)

        fuss = QtWidgets.QHBoxLayout()
        self.btn_rueckgaengig = QtWidgets.QPushButton(tr("Rückgängig (letzter Schritt)"))
        self.btn_rueckgaengig.clicked.connect(self._rueckgaengig)
        fuss.addWidget(self.btn_rueckgaengig)
        fuss.addStretch(1)
        self.btn_export = QtWidgets.QPushButton(tr("Exportieren … (Excel + CSV + Plot)"))
        self.btn_export.setToolTip(
            tr("Excel (Parameter mit 1σ-Fehlern in T und mT, alle Punkte; bei mehreren\n"
            "Moden zusätzlich je Mode ein Blatt), CSV der Punkte (Listendaten) und\n"
            "Plot als PNG + PDF."))
        self.btn_export.clicked.connect(self._exportieren)
        fuss.addWidget(self.btn_export)
        btn_zu = QtWidgets.QPushButton(tr("Schließen"))
        btn_zu.clicked.connect(self.close)
        fuss.addWidget(btn_zu)
        lay.addLayout(fuss)

        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_move)
        self.canvas.mpl_connect("button_release_event", self._on_release)

        self.aktualisiere()

    def _werkzeuge_einrichten(self) -> None:
        leiste = self.werkzeuge
        erste = leiste.actions()[0]
        self.act_auswahl = QtGui.QAction(tr("Auswählen"), self)
        self.act_auswahl.setCheckable(True)
        self.act_auswahl.setChecked(True)
        self.act_auswahl.setToolTip(
            tr("Auswahlwerkzeug: Punkt anklicken (an/aus) oder Kasten aufziehen.\n"
            "Aktiv, solange Verschieben/Zoom aus sind."))
        self.act_auswahl.triggered.connect(self._auswahl_werkzeug)
        leiste.insertAction(erste, self.act_auswahl)
        leiste.insertSeparator(erste)
        for name in ("pan", "zoom"):
            leiste._actions[name].toggled.connect(self._navigation_umgeschaltet)

        koordinaten = next((a for a in leiste.actions()
                            if leiste.widgetForAction(a) is getattr(leiste, "locLabel", None)),
                           None)
        self.act_ausblenden = QtGui.QAction(tr("Auswahl ausblenden"), self)
        self.act_ausblenden.setShortcuts([QtGui.QKeySequence(QtCore.Qt.Key_Delete),
                                          QtGui.QKeySequence(QtCore.Qt.Key_Backspace)])
        self.act_ausblenden.setToolTip(
            tr("Gewählte Punkte aus der Kittel-/LLG-Auswertung ausschließen (Entf) –\n"
            "wird ins Hauptfenster/den Farbplot übernommen (grau); rückgängig: Strg+Z."))
        self.act_ausblenden.triggered.connect(self._ausblenden)
        self.act_einblenden = QtGui.QAction(tr("Auswahl einblenden"), self)
        self.act_einblenden.setToolTip(
            tr("Gewählte ausgeblendete (graue) Punkte wieder in die Auswertung aufnehmen."))
        self.act_einblenden.triggered.connect(self._einblenden)
        self.act_aufheben = QtGui.QAction(tr("Auswahl aufheben"), self)
        self.act_aufheben.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Escape))
        self.act_aufheben.setToolTip(tr("Auswahl leeren (Esc)."))
        self.act_aufheben.triggered.connect(self._auswahl_aufheben)
        self.chk_ausgeblendete = QtWidgets.QCheckBox(tr("ausgeblendete Punkte zeigen"))
        self.chk_ausgeblendete.setToolTip(
            tr("Ausgeblendete Punkte grau (hohl) anzeigen – auswählbar zum Wiederaufnehmen."))
        self.chk_ausgeblendete.toggled.connect(
            lambda _an: self.aktualisiere(ansicht_behalten=False))
        leiste.insertSeparator(koordinaten)
        for aktion in (self.act_ausblenden, self.act_einblenden, self.act_aufheben):
            leiste.insertAction(koordinaten, aktion)
        leiste.insertSeparator(koordinaten)
        leiste.insertWidget(koordinaten, self.chk_ausgeblendete)
        self._auswahl_geaendert(zeichnen=False)

    def _navigation_aktiv(self) -> bool:
        aktionen = self.werkzeuge._actions
        return aktionen["pan"].isChecked() or aktionen["zoom"].isChecked()

    def _navigation_umgeschaltet(self, _an: bool = False) -> None:
        self.act_auswahl.setChecked(not self._navigation_aktiv())

    def _auswahl_werkzeug(self, _checked: bool = False) -> None:
        """Verschieben/Zoom ausschalten -> Auswahlwerkzeug aktiv."""
        aktionen = self.werkzeuge._actions
        if aktionen["pan"].isChecked():
            self.werkzeuge.pan()
        if aktionen["zoom"].isChecked():
            self.werkzeuge.zoom()
        self.act_auswahl.setChecked(True)

    def _ansicht(self) -> list:
        return [(tuple(ax.get_xlim()), tuple(ax.get_ylim())) for ax in (self.ax_disp, self.ax_lb)]

    def _ansicht_setzen(self, ansicht) -> None:
        for ax, (xlim, ylim) in zip((self.ax_disp, self.ax_lb), ansicht):
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)

    def _gesamtansicht(self) -> None:
        if self._auto_ansicht is not None:
            self._ansicht_setzen(self._auto_ansicht)
            self.canvas.draw_idle()

    def _geometrie_gewaehlt(self, text: str) -> None:
        if self._cb_geometrie is not None:
            self._cb_geometrie(str(text))
        self.aktualisiere(ansicht_behalten=False)

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
        gewuenscht = ([(tr("Mode {0}", k), k) for k in moden]
                      + [(tr("Alle Moden"), ALLE_MODEN)])
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
            return tr(" – alle Moden")
        return tr(" – Mode {0}", mode)

    # --- Auswertung + Darstellung -------------------------------------------
    def aktualisiere(self, ansicht_behalten: bool = True) -> None:
        """Rechnet Kittel/LLG (je gewaehlter Mode) mit den aktiven Punkten neu und
        zeichnet alles. Eine gezoomte/verschobene Ansicht bleibt bei
        ``ansicht_behalten`` erhalten (Moden-/Geometriewechsel: Gesamtansicht)."""
        stapel = self._hole_stapel()
        vorher = None
        if ansicht_behalten and self._auto_ansicht is not None:
            aktuell = self._ansicht()
            if not np.allclose(np.array(aktuell, dtype=float),
                               np.array(self._auto_ansicht, dtype=float)):
                vorher = aktuell
        self.ax_disp.clear()
        self.ax_lb.clear()
        self._box_patch = None
        self._markierung = {}
        leer = np.array([], dtype=int)
        if stapel is None or not stapel.ergebnisse:
            self._reihen = {}
            self._info = None
            self._punkt_indizes = leer
            self._punkt_moden = leer.copy()
            self._punkt_b = self._punkt_f = self._punkt_dh = np.array([])
            self._kandidaten_setzen([], [])
            self._auto_ansicht = None
            self.param_text.setHtml(tr("<p>Keine Fits vorhanden.</p>"))
            self._auswahl_geaendert(zeichnen=False)
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
            label = tr("verwendete Fits") if einzeln else tr("Mode {0}", r.mode)
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
                              label=tr("Kittel-Fit") if einzeln else tr("Kittel M{0}", r.mode))
            reihenfolge = np.argsort(r.b)
            self.ax_lb.plot(
                r.b[reihenfolge],
                linienbreite(r.f[reihenfolge], llg["mu0Hinh"], llg["alpha"], llg["gamma"]) * 1e3,
                "-", color=linie, label=tr("LLG-Fit") if einzeln else tr("LLG M{0}", r.mode))
        ausgeblendet = (self._ausgeblendete_punkte(stapel, modi)
                        if self.chk_ausgeblendete.isChecked() else [])
        if ausgeblendet:
            ab = np.array([p[3] for p in ausgeblendet])
            self.ax_disp.plot(ab, np.array([p[4] for p in ausgeblendet]) / 1e9, "o", ms=4.5,
                              mfc="none", mec=F.NEUTRAL_GRAU, mew=1.0, label="ausgeblendet")
            self.ax_lb.plot(ab, np.array([p[5] for p in ausgeblendet]) * 1e3, "o", ms=4.5,
                            mfc="none", mec=F.NEUTRAL_GRAU, mew=1.0, label="ausgeblendet")
        self._kandidaten_setzen(reihen, ausgeblendet)
        zusatz = self._titel_zusatz(mode)
        self.ax_disp.set_xlabel(tr(r"Resonanzfeld $\mu_0 H_{res}$ (T)"))
        self.ax_disp.set_ylabel(tr("Frequenz (GHz)"))
        self.ax_disp.set_title(tr("Dispersion (Kittel, {0}){1}", geometrie, zusatz))
        self.ax_disp.legend(fontsize=8)
        self.ax_lb.set_xlabel(tr(r"Resonanzfeld $\mu_0 H_{res}$ (T)"))
        self.ax_lb.set_ylabel(tr(r"Linienbreite $\mu_0\Delta H$ (mT)"))
        self.ax_lb.set_title(tr("Linienbreite (LLG){0}", zusatz))
        self.ax_lb.legend(fontsize=8)
        for ax in (self.ax_disp, self.ax_lb):
            self._markierung[ax] = ax.plot([], [], "o", ms=10, mfc="none", mec=F.SIGNAL_BLAU,
                                           mew=1.8, zorder=5, label="_auswahl")[0]
        try:
            self.figur.tight_layout()
        except Exception:
            pass
        self._auto_ansicht = self._ansicht()
        if vorher is not None:
            self._ansicht_setzen(vorher)
        self.werkzeuge.update()
        self._auswahl_geaendert(zeichnen=False)
        self.canvas.draw_idle()
        self._zeige_parameter(stapel, mode)

    def _ausgeblendete_punkte(self, stapel, modi) -> list[tuple]:
        """``(index, mode, art, B_res, f, dH)`` der ausgeblendeten, gefitteten Punkte
        der Moden ``modi``; art ``"ls"`` = Linescan-Ausreisser (alle Moden),
        ``"mode"`` = nur fuer diese Mode ausgeschlossen."""
        ls_aus = {int(i) for i in stapel.ausreisser}
        paare = {(int(i), int(k)) for i, k in getattr(stapel, "ausreisser_moden", [])}
        punkte = []
        for k in modi:
            liste = stapel.ergebnisse_mode(k)
            for i in sorted(ls_aus | {i for i, m in paare if m == int(k)}):
                if i >= len(liste):
                    continue
                e = liste[i]
                if not getattr(e, "gefittet", True) or not (
                        np.isfinite(e.B_res) and np.isfinite(e.dH)):
                    continue
                art = "ls" if i in ls_aus else "mode"
                punkte.append((int(i), int(k), art, float(e.B_res), float(e.frequenz),
                               float(e.dH)))
        return punkte

    def _kandidaten_setzen(self, reihen, ausgeblendet) -> None:
        keys = [("v", int(i), int(r.mode)) for r in reihen for i in r.indizes]
        keys += [("a", p[0], p[1]) for p in ausgeblendet]
        self._kand_keys = keys
        self._kand_b = np.array([*self._punkt_b, *(p[3] for p in ausgeblendet)], dtype=float)
        self._kand_f = np.array([*self._punkt_f, *(p[4] for p in ausgeblendet)], dtype=float)
        self._kand_dh = np.array([*self._punkt_dh, *(p[5] for p in ausgeblendet)], dtype=float)
        self._aus_art = {(p[0], p[1]): p[2] for p in ausgeblendet}

    def _zeige_parameter(self, stapel, mode: int) -> None:
        paare = list(getattr(stapel, "ausreisser_moden", []))
        zeilen = [tr("<p><b>Punkte:</b> {0} verwendet, {1} Ausreißer ausgeblendet", self._punkt_indizes.size, len(stapel.ausreisser))
                  + (tr(", {0} Punkt(e) nur je Mode ausgeschlossen", len(paare)) if paare else "")
                  + "</p>"]
        if self._moden_aktiv:
            was = tr("alle Moden") if mode == ALLE_MODEN else tr("Mode {0} (Korridor M{0})", mode)
            zeilen.append(f"<p><b>Mode:</b> {was}</p>")
        mehrere = len(self._reihen) > 1
        irgendein_fit = False
        for r in self._reihen.values():
            if mehrere:
                zeilen.append(tr("<h3 style='color:{0}'>Mode {1} – {2} Punkte</h3>", self._farbe(r.mode, False), r.mode, r.n))
            if r.info is None:
                zeilen.append(f"<p style='color:{F.TEXT_ROT}'>{tr(r.fehler)}</p>")
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
            zeilen.append(tr("<{0}>LLG (Dämpfung)</{0}><ul><li>α = {1}</li><li>µ₀ΔH<sub>0</sub> "
                             "(inhomogen) = {2} mT = {3} T</li><li>R² = {4:.5f}</li></ul>", ueberschrift, w(llg['alpha'], llg['alpha_err'], fmt='.3e'), w(llg['mu0Hinh'], llg['mu0Hinh_err'], 1e3, '.3f'), w(llg['mu0Hinh'], llg['mu0Hinh_err'], 1.0, '.5f'), llg['R2']))
        if irgendein_fit:
            modus = tr("gewichtet") if self._gewichtet else tr("ungewichtet")
            zeilen.append(tr("<p style='color:{0};font-size:11px'>Kittel-/LLG-Fit {1} (umschaltbar: "
                             "Strg+P). Unsicherheiten der Parameter: im Export.</p>", F.TEXT_SCHWACH, modus))
        self.param_text.setHtml("".join(zeilen))

    # --- Auswahl / Ausblenden -------------------------------------------------
    def _rueckgaengig(self) -> None:
        if self._cb_rueckgaengig is not None:
            self._cb_rueckgaengig()
        self.aktualisiere()

    def _achsen_punkte(self, ax):
        """(x, y) der auswaehlbaren Punkte im Koordinatensystem der Achse."""
        if ax is self.ax_disp:
            return self._kand_b, self._kand_f / 1e9
        return self._kand_b, self._kand_dh * 1e3

    def auswahl(self) -> list[tuple[str, int, int]]:
        """Gewaehlte Punkte als ``(art, Stapel-Index, Mode)``, art ``"v"`` = verwendet,
        ``"a"`` = ausgeblendet."""
        return sorted(self._auswahl)

    def _auswahl_geaendert(self, zeichnen: bool = True) -> None:
        """Auswahl auf vorhandene Punkte beschraenken, Ringe/Knoepfe/Hinweis nachziehen."""
        vorhanden = set(self._kand_keys)
        self._auswahl &= vorhanden
        position = {k: n for n, k in enumerate(self._kand_keys)}
        pos = np.array(sorted(position[k] for k in self._auswahl), dtype=int)
        for ax, linie in self._markierung.items():
            x, y = self._achsen_punkte(ax)
            linie.set_data(x[pos], y[pos])
        n_v = sum(1 for k in self._auswahl if k[0] == "v")
        n_a = len(self._auswahl) - n_v
        self.act_ausblenden.setEnabled(n_v > 0)
        self.act_einblenden.setEnabled(n_a > 0)
        self.act_aufheben.setEnabled(bool(self._auswahl))
        if self._auswahl:
            f_ghz = sorted(self._kand_f[pos] / 1e9)
            liste = ", ".join(f"{f:.2f}" for f in f_ghz[:5]) + (" …" if len(f_ghz) > 5 else "")
            self.hinweis.setText(tr("{0} Punkt(e) ausgewählt ({1} GHz) – Entf = ausblenden, Esc = Auswahl "
                                    "aufheben", len(self._auswahl), liste))
        else:
            self.hinweis.setText(tr(_HINWEIS))
        if zeichnen:
            self.canvas.draw_idle()

    def _auswahl_aufheben(self) -> None:
        self._auswahl.clear()
        self._auswahl_geaendert()

    def _ausblenden(self) -> None:
        """Gewaehlte verwendete Punkte ausschliessen: eine Mode -> Linescan-
        Ausreisser, mehrere Moden -> nur ``(index, mode)``."""
        gewaehlt = sorted(k for k in self._auswahl if k[0] == "v")
        if not gewaehlt:
            return
        self._auswahl.clear()
        if not self._moden_aktiv:
            if self._cb_markieren is not None:
                self._cb_markieren(sorted({i for _a, i, _m in gewaehlt}))
        elif self._cb_markieren_mode is not None:
            self._cb_markieren_mode([(i, m) for _a, i, m in gewaehlt])
        self.aktualisiere()

    def _einblenden(self) -> None:
        """Gewaehlte ausgeblendete Punkte wieder aufnehmen (Linescan-Ausreisser
        bzw. Ausschluss je Mode)."""
        gewaehlt = [k for k in self._auswahl if k[0] == "a"]
        if not gewaehlt:
            return
        self._auswahl -= set(gewaehlt)
        linescans = sorted({i for _a, i, m in gewaehlt if self._aus_art.get((i, m)) == "ls"})
        paare = sorted({(i, m) for _a, i, m in gewaehlt if self._aus_art.get((i, m)) == "mode"})
        if linescans and self._cb_wieder is not None:
            self._cb_wieder(linescans)
        if paare and self._cb_wieder_mode is not None:
            self._cb_wieder_mode(paare)
        self.aktualisiere()

    def _on_press(self, event):
        if event.inaxes not in (self.ax_disp, self.ax_lb) or self._navigation_aktiv():
            return
        if getattr(event, "button", 1) != 1:
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
        if not self._kand_keys:
            return
        px, py = self._achsen_punkte(ax)
        if war_box and event.xdata is not None and event.ydata is not None:
            x1, y1 = event.xdata, event.ydata
            drin = ((px >= min(x0, x1)) & (px <= max(x0, x1))
                    & (py >= min(y0, y1)) & (py <= max(y0, y1)))
            self._auswahl.update(self._kand_keys[int(k)] for k in np.flatnonzero(drin))
        elif not war_box and event.inaxes is ax:
            xs = abs(np.diff(ax.get_xlim())[0]) or 1e-12
            ys = abs(np.diff(ax.get_ylim())[0]) or 1e-12
            abstand = np.hypot((px - x0) / xs, (py - y0) / ys)
            naechster = int(np.argmin(abstand))
            if abstand[naechster] > _KLICK_TOLERANZ:
                return
            self._auswahl ^= {self._kand_keys[naechster]}
        else:
            return
        self._auswahl_geaendert()

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
            self, tr("Auswertung exportieren"), "kittel_llg_auswertung.xlsx",
            tr("Excel (*.xlsx)"))
        if not pfad:
            return
        basis, _endung = os.path.splitext(pfad)
        p = self._hole_parameter() if self._hole_parameter is not None else None
        csv_deutsch = bool(getattr(p, "csv_deutsch", False)) if p is not None else False
        dateien = self.exportiere(basis, csv_deutsch=csv_deutsch)
        QtWidgets.QMessageBox.information(
            self, tr("Export"), tr("Gespeichert:\n") + "\n".join(dateien))

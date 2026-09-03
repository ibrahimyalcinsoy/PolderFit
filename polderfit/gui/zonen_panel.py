# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Bedienpanel der Korridore (Moden) und Ausschlusszonen.

*Korridore*: je Mode ein Feldband entlang der Resonanz (Ankerpunkte an wenigen
Frequenzen, dazwischen linear; :mod:`polderfit.fit.korridor`). Die Liste M1..Mn
ist die EINZIGE Quelle des Moden-Zustands; die gewaehlte Zeile ist die Mode,
die das Linescan-Panel zeigt. Werkzeuge: Korridor anlegen (2 Klicks entlang der
Resonanz), Anker setzen (Klick), Anker/Korridor entfernen, Korridor fitten.

*Ausschlusszonen* nehmen Messpunkte (Rechteck Feld x Frequenz) aus allen
(Nach-)Fits aus - z. B. ein stoerendes, feldparalleles Artefakt.

Wenig Text im Panel; Erklaerungen als Tooltips.
"""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..fit.korridor import METHODEN_TEXTE
from .widgets import RuhigeComboBox, RuhigeSpinBox


class ZonenPanel(QtWidgets.QWidget):
    """Korridorliste, Werkzeuge und Ausschlusszonen.

    Callbacks des Hauptfensters:

    * ``zone_umschalten(an)`` / ``zone_entfernen(index)``
    * ``korridor_umschalten(an)`` – Werkzeug "Korridor anlegen" (2 Klicks)
    * ``anker_umschalten(an)`` – Werkzeug "Anker setzen" (Klick)
    * ``korridor_gewaehlt(mode)`` – Zeile in der Korridorliste gewaehlt
    * ``korridor_entfernen(mode)``
    * ``anker_entfernen(mode, index)``
    * ``korridor_fit(mode | None)`` – Korridor fitten (``None`` = alle)
    * ``dips_geaendert(mode, n, methode)`` – Zahl der Resonanzen (Dips) im
      Korridor und Verfahren (``"summe"``/``"trennung"``)
    * ``trenner_umschalten(an)`` – Trennlinie im Linescan-Panel setzen (Klick)
    * ``trenner_loeschen()`` – Trennlinien an der angezeigten Frequenz loeschen
    * ``breite_geaendert(mode, halbbreite_T)`` – Breite des gewaehlten Korridors
    """

    def __init__(self, zone_umschalten=None, zone_entfernen=None,
                 korridor_umschalten=None, anker_umschalten=None,
                 korridor_gewaehlt=None, korridor_entfernen=None,
                 anker_entfernen=None, korridor_fit=None, dips_geaendert=None,
                 trenner_umschalten=None, trenner_loeschen=None, breite_geaendert=None,
                 parent=None):
        super().__init__(parent)
        self._cb_zone_umschalten = zone_umschalten
        self._cb_zone_entfernen = zone_entfernen
        self._cb_korridor_umschalten = korridor_umschalten
        self._cb_anker_umschalten = anker_umschalten
        self._cb_korridor_gewaehlt = korridor_gewaehlt
        self._cb_korridor_entfernen = korridor_entfernen
        self._cb_anker_entfernen = anker_entfernen
        self._cb_korridor_fit = korridor_fit
        self._cb_dips_geaendert = dips_geaendert
        self._cb_trenner_umschalten = trenner_umschalten
        self._cb_trenner_loeschen = trenner_loeschen
        self._cb_breite_geaendert = breite_geaendert
        self._korridore: list = []
        self._mode_aktiv: int = 1
        self._blockiert = False

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(8)

        # --- Korridore (Moden) ---------------------------------------------------
        grp_k = QtWidgets.QGroupBox("Korridore (Moden)")
        grp_k.setToolTip(
            "Je Mode ein Korridor entlang der Resonanz. Jede Mode wird NUR auf den\n"
            "Messpunkten ihres Korridors gefittet (Einzelfit, kein Summenfit).\n"
            "Ohne Korridor gilt für Mode 1 das AutoWindow-Fenster des Auto-Fits.\n"
            "Die gewählte Zeile ist die Mode im Linescan-Panel.")
        k_lay = QtWidgets.QVBoxLayout(grp_k)

        self.korridor_liste = QtWidgets.QListWidget()
        self.korridor_liste.setMaximumHeight(96)
        self.korridor_liste.setToolTip("Gewählte Zeile = Mode im Linescan-Panel.")
        self.korridor_liste.currentRowChanged.connect(self._zeile_gewaehlt)
        k_lay.addWidget(self.korridor_liste)

        zeile1 = QtWidgets.QHBoxLayout()
        self.btn_neu = QtWidgets.QPushButton("Korridor anlegen")
        self.btn_neu.setCheckable(True)
        self.btn_neu.setToolTip(
            "Zwei Punkte entlang der Resonanz im Farbplot klicken → neuer Korridor\n"
            "± Breite (nächste Mode-Nummer). Esc oder erneuter Klick bricht ab.")
        self.btn_neu.toggled.connect(self._korridor_umgeschaltet)
        zeile1.addWidget(self.btn_neu, 1)
        self.breite_spin = RuhigeSpinBox()
        self.breite_spin.setRange(1, 500)
        self.breite_spin.setValue(10)
        self.breite_spin.setPrefix("± ")
        self.breite_spin.setSuffix(" mT")
        self.breite_spin.setToolTip(
            "Halbe Korridorbreite (eng halten): gilt für den gewählten Korridor – Ändern\n"
            "setzt alle seine Anker sofort auf Mitte ± Wert – und für neu angelegte.")
        self.breite_spin.valueChanged.connect(self._breite_gewaehlt)
        zeile1.addWidget(self.breite_spin)
        k_lay.addLayout(zeile1)

        zeile_d = QtWidgets.QHBoxLayout()
        lbl_d = QtWidgets.QLabel("Resonanzen im Korridor:")
        lbl_d.setToolTip(
            "Vorgabe: so viele Dips liegen in diesem Korridor. Bei > 1 wird der Korridor\n"
            "je Frequenz zwischen den Dips hart getrennt (Hard Crop) und jeder Dip einzeln\n"
            "gefittet - kein Summenfit. Jeder Dip bekommt eine eigene Mode-Nummer.")
        zeile_d.addWidget(lbl_d, 1)
        self.dips_spin = RuhigeSpinBox()
        self.dips_spin.setRange(1, 4)
        self.dips_spin.setValue(1)
        self.dips_spin.setToolTip(lbl_d.toolTip())
        self.dips_spin.valueChanged.connect(self._dips_gewaehlt)
        zeile_d.addWidget(self.dips_spin)
        k_lay.addLayout(zeile_d)
        self.methode_combo = RuhigeComboBox()
        for schluessel, text in METHODEN_TEXTE.items():
            self.methode_combo.addItem(text, schluessel)
        self.methode_combo.setToolTip(
            "harte Trennung: Korridor wird je Frequenz zwischen den Dips getrennt, jeder\n"
            "Dip einzeln gefittet (Nachbar-Dip abgezogen).\n"
            "Summenfit: alle Dips gemeinsam auf den Korridorpunkten, jedes B_res hart auf\n"
            "sein Segment beschränkt (gemeinsamer Untergrund).")
        self.methode_combo.currentIndexChanged.connect(self._dips_gewaehlt)
        self.methode_combo.setVisible(False)
        k_lay.addWidget(self.methode_combo)
        zeile_t = QtWidgets.QHBoxLayout()
        self.btn_trenner = QtWidgets.QPushButton("Trennlinie setzen")
        self.btn_trenner.setCheckable(True)
        self._trenner_tip = (
            "Im Linescan-Panel zwischen zwei Dips klicken → gelbe Trennlinie (harte\n"
            "Grenze). Sie wandert entlang der Mode mit (relativ zur Korridormitte) und\n"
            "gilt für alle Fits dieses Korridors; an anderen Frequenzen nachsetzen oder\n"
            "ziehen, wenn sie abweicht. Esc oder erneuter Klick auf den Knopf beendet.")
        self.btn_trenner.setToolTip(self._trenner_tip)
        self.btn_trenner.toggled.connect(
            lambda an: self._cb_trenner_umschalten and self._cb_trenner_umschalten(bool(an)))
        zeile_t.addWidget(self.btn_trenner, 1)
        self.btn_trenner_loeschen = QtWidgets.QPushButton("löschen")
        self.btn_trenner_loeschen.setToolTip("Trennlinien an der angezeigten Frequenz löschen.")
        self.btn_trenner_loeschen.clicked.connect(
            lambda: self._cb_trenner_loeschen and self._cb_trenner_loeschen())
        zeile_t.addWidget(self.btn_trenner_loeschen)
        self.trenner_box = QtWidgets.QWidget()
        self.trenner_box.setLayout(zeile_t)
        self.trenner_box.setEnabled(False)
        k_lay.addWidget(self.trenner_box)

        zeile2 = QtWidgets.QHBoxLayout()
        self.btn_anker = QtWidgets.QPushButton("Anker setzen")
        self.btn_anker.setCheckable(True)
        self.btn_anker.setToolTip(
            "Klick im Farbplot setzt am gewählten Korridor bei dieser Frequenz die\n"
            "nähere Grenze auf das geklickte Feld (Anker). Anker im Farbplot ziehbar.\n"
            "Mehrere Klicks möglich; Esc beendet.")
        self.btn_anker.toggled.connect(self._anker_umgeschaltet)
        zeile2.addWidget(self.btn_anker, 1)
        self.btn_entfernen = QtWidgets.QPushButton("Entfernen")
        self.btn_entfernen.setToolTip("Gewählten Korridor samt Fits dieser Mode entfernen.")
        self.btn_entfernen.clicked.connect(self._entfernen_geklickt)
        zeile2.addWidget(self.btn_entfernen)
        k_lay.addLayout(zeile2)

        zeile3 = QtWidgets.QHBoxLayout()
        self.btn_fit = QtWidgets.QPushButton("Korridor fitten …")
        self.btn_fit.setToolTip(
            "Gewählte Mode an allen Frequenzen im Korridor fitten (Einzelfit je\n"
            "Frequenz, nur Punkte im Korridor). Dialog: Frequenzbereich, Modus, Jumper.")
        self.btn_fit.clicked.connect(lambda: self._cb_korridor_fit and self._cb_korridor_fit(self.mode_aktiv()))
        zeile3.addWidget(self.btn_fit, 1)
        self.btn_fit_alle = QtWidgets.QPushButton("Alle")
        self.btn_fit_alle.setToolTip("Alle Korridore nacheinander fitten.")
        self.btn_fit_alle.clicked.connect(lambda: self._cb_korridor_fit and self._cb_korridor_fit(None))
        zeile3.addWidget(self.btn_fit_alle)
        k_lay.addLayout(zeile3)

        lay.addWidget(grp_k)

        # --- Ausschlusszonen --------------------------------------------------
        grp_zonen = QtWidgets.QGroupBox("Ausschlusszonen")
        grp_zonen.setToolTip(
            "Messpunkte in einer Zone (Rechteck Feld × Frequenz) werden aus ALLEN\n"
            "(Nach-)Fits ausgenommen; betroffene Linescans rechnen sofort neu.")
        zonen_lay = QtWidgets.QVBoxLayout(grp_zonen)
        self.btn_zone = QtWidgets.QPushButton("Zone einzeichnen")
        self.btn_zone.setCheckable(True)
        self.btn_zone.setToolTip("Rechteck im Farbplot aufziehen. Esc oder erneuter Klick bricht ab.")
        self.btn_zone.toggled.connect(self._zone_umgeschaltet)
        zonen_lay.addWidget(self.btn_zone)
        self.zonen_liste = QtWidgets.QListWidget()
        self.zonen_liste.setMaximumHeight(90)
        zonen_lay.addWidget(self.zonen_liste)
        self.btn_zone_entfernen = QtWidgets.QPushButton("Zone entfernen")
        self.btn_zone_entfernen.setToolTip("Gewählte (sonst zuletzt gezeichnete) Zone entfernen.")
        self.btn_zone_entfernen.clicked.connect(self._zone_entfernen_geklickt)
        zonen_lay.addWidget(self.btn_zone_entfernen)
        lay.addWidget(grp_zonen)
        lay.addStretch(1)
        self._aktualisiere_knoepfe()

    # --- Zustand ---------------------------------------------------------------
    def setze_zonen(self, zonen) -> None:
        """Fuellt die (einsehbare, editierbare) Zonenliste."""
        self.zonen_liste.clear()
        for zone in zonen:
            self.zonen_liste.addItem(
                f"{zone.feld_min:.3f}–{zone.feld_max:.3f} T, "
                f"{zone.frequenz_min/1e9:.2f}–{zone.frequenz_max/1e9:.2f} GHz")

    def setze_korridore(self, korridore, statistik: dict | None = None) -> None:
        """Fuellt die Korridorliste (``statistik[mode] = (n_gefittet, n_problematisch)``).

        Ohne Korridore steht eine Zeile "M1 – AutoWindow" (Mode 1 ohne Korridor).
        Die aktive Mode bleibt, wenn sie noch existiert; sonst Mode 1.
        """
        self._korridore = list(korridore)
        statistik = statistik or {}
        self._blockiert = True
        self.korridor_liste.clear()
        moden = [int(m) for k in self._korridore for m in k.moden]
        if 1 not in moden:
            self.korridor_liste.addItem(self._zeile_text(1, None, statistik.get(1)))
            self.korridor_liste.item(0).setData(QtCore.Qt.UserRole, 1)
        for k in self._korridore:
            item = QtWidgets.QListWidgetItem(self._zeile_text(k.mode, k, statistik.get(k.mode)))
            item.setData(QtCore.Qt.UserRole, int(k.mode))
            self.korridor_liste.addItem(item)
            for j, m in enumerate(k.moden[1:], start=2):
                stat = statistik.get(m)
                text = f"   ↳ M{m} · Dip {j} von {len(k.moden)}"
                if stat:
                    text += f" · {stat[0]} Fits" + (f" ({stat[1]} ⚠)" if stat[1] else "")
                sub = QtWidgets.QListWidgetItem(text)
                sub.setData(QtCore.Qt.UserRole, int(m))
                self.korridor_liste.addItem(sub)
        if self._mode_aktiv not in moden and self._mode_aktiv != 1:
            self._mode_aktiv = 1
        for r in range(self.korridor_liste.count()):
            if self.korridor_liste.item(r).data(QtCore.Qt.UserRole) == self._mode_aktiv:
                self.korridor_liste.setCurrentRow(r)
                break
        self._blockiert = False
        self._anker_liste_fuellen()
        self._aktualisiere_knoepfe()

    @staticmethod
    def _zeile_text(mode: int, korridor, stat) -> str:
        if korridor is None:
            text = f"M{mode} · AutoWindow (kein Korridor)"
        else:
            n = len(korridor.anker)
            text = f"M{mode} · {n} Anker"
            if korridor.n_dips > 1:
                text += f" · {korridor.n_dips} Dips"
        if stat:
            n_fit, n_prob = stat
            text += f" · {n_fit} Fits" + (f" ({n_prob} ⚠)" if n_prob else "")
        return text

    def mode_aktiv(self) -> int:
        return int(self._mode_aktiv)

    def setze_mode_aktiv(self, mode: int) -> None:
        self._mode_aktiv = max(1, int(mode))
        self.setze_korridore(self._korridore)

    def korridor_aktiv(self):
        """Korridor, zu dem die aktive Mode gehoert (auch als weiterer Dip), oder ``None``."""
        for k in self._korridore:
            if k.enthaelt_mode(self._mode_aktiv):
                return k
        return None

    def mode_neu(self) -> int:
        """Naechste freie Mode-Nummer (ueber alle Korridore und Dips)."""
        return max((int(m) for k in self._korridore for m in k.moden), default=0) + 1

    def bandbreite_T(self) -> float:
        """Halbe Korridorbreite beim Anlegen in Tesla."""
        return float(self.breite_spin.value()) / 1e3


    # --- Modus-Synchronisation (ohne Rueckruf) ---------------------------------
    def setze_modus_aktiv(self, an: bool) -> None:
        self._knopf_syncen(self.btn_zone, an)

    def setze_korridor_modus_aktiv(self, an: bool) -> None:
        self._knopf_syncen(self.btn_neu, an)

    def setze_anker_modus_aktiv(self, an: bool) -> None:
        self._knopf_syncen(self.btn_anker, an)

    def setze_trenner_modus_aktiv(self, an: bool) -> None:
        self._knopf_syncen(self.btn_trenner, an)

    @staticmethod
    def _knopf_syncen(knopf: QtWidgets.QPushButton, an: bool) -> None:
        if knopf.isChecked() != bool(an):
            knopf.blockSignals(True)
            knopf.setChecked(bool(an))
            knopf.blockSignals(False)

    # --- intern ------------------------------------------------------------------
    def _aktualisiere_knoepfe(self) -> None:
        hat = self.korridor_aktiv() is not None
        k = self.korridor_aktiv()
        self.dips_spin.blockSignals(True)
        self.dips_spin.setValue(int(k.n_dips) if k is not None else 1)
        self.dips_spin.blockSignals(False)
        self.dips_spin.setEnabled(hat)
        if k is not None and k.halbbreite() is not None:
            self.breite_spin.blockSignals(True)
            self.breite_spin.setValue(int(round(k.halbbreite() * 1e3)))
            self.breite_spin.blockSignals(False)
        self.methode_combo.blockSignals(True)
        idx = self.methode_combo.findData(k.methode if k is not None else "summe")
        self.methode_combo.setCurrentIndex(max(0, idx))
        self.methode_combo.blockSignals(False)
        mehrere = k is not None and k.n_dips > 1
        self.methode_combo.setVisible(mehrere)

        self.trenner_box.setEnabled(mehrere)
        self.btn_trenner.setToolTip(self._trenner_tip if mehrere else
                                    "Erst „Resonanzen im Korridor“ auf 2 oder mehr stellen.")
        self.btn_anker.setEnabled(hat)
        self.btn_entfernen.setEnabled(hat)
        self.btn_fit.setEnabled(hat)
        self.btn_fit_alle.setEnabled(bool(self._korridore))


    def _anker_liste_fuellen(self) -> None:
        return   # kein Anker-Detailbereich mehr (Anker werden im Farbplot gezogen)

    def _zeile_gewaehlt(self, zeile: int) -> None:
        if self._blockiert or zeile < 0:
            return
        item = self.korridor_liste.item(zeile)
        mode = int(item.data(QtCore.Qt.UserRole) or 1)
        if mode == self._mode_aktiv:
            return
        self._mode_aktiv = mode
        self._anker_liste_fuellen()
        self._aktualisiere_knoepfe()
        if self._cb_korridor_gewaehlt is not None:
            self._cb_korridor_gewaehlt(mode)

    def _korridor_umgeschaltet(self, an: bool) -> None:
        if self._cb_korridor_umschalten is not None:
            self._cb_korridor_umschalten(bool(an))

    def _anker_umgeschaltet(self, an: bool) -> None:
        if self._cb_anker_umschalten is not None:
            self._cb_anker_umschalten(bool(an))

    def _breite_gewaehlt(self, wert: int) -> None:
        k = self.korridor_aktiv()
        if k is not None and self._cb_breite_geaendert is not None:
            self._cb_breite_geaendert(int(k.mode), float(wert) / 1e3)

    def _dips_gewaehlt(self, *_args) -> None:
        k = self.korridor_aktiv()
        if k is not None and self._cb_dips_geaendert is not None:
            self._cb_dips_geaendert(int(k.mode), int(self.dips_spin.value()),
                                    str(self.methode_combo.currentData() or "summe"))
        self.methode_combo.setVisible(k is not None and int(self.dips_spin.value()) > 1)
        self.trenner_box.setEnabled(k is not None and int(self.dips_spin.value()) > 1)

    def _entfernen_geklickt(self) -> None:
        k = self.korridor_aktiv()
        if k is not None and self._cb_korridor_entfernen is not None:
            self._cb_korridor_entfernen(int(k.mode))


    def _zone_umgeschaltet(self, an: bool) -> None:
        if self._cb_zone_umschalten is not None:
            self._cb_zone_umschalten(bool(an))

    def _zone_entfernen_geklickt(self) -> None:
        zeile = self.zonen_liste.currentRow()
        if zeile < 0 and self.zonen_liste.count():
            zeile = self.zonen_liste.count() - 1
        if zeile >= 0 and self._cb_zone_entfernen is not None:
            self._cb_zone_entfernen(zeile)

"""Dialoge fuer das TDMS-Kanal-Mapping.

:class:`MappingDialog`  – Nutzer ordnet jeder kanonischen Rolle (Feld,
Frequenz, Re/Im(S21), Temperatur) eine (Gruppe, Kanal)-Kombination der
geladenen Datei zu; Profile koennen angewendet, gespeichert und geladen
werden. :class:`VorschauDialog` – zeigt nach dem Laden den Validierungs-
Bericht plus Daten-Vorschau; erst mit "Uebernehmen" wird der Datensatz
aktiv (Import-Validierung vor Uebernahme, verpflichtend vor jedem Autofit).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtWidgets

from ..io.datensatz import Messdatensatz
from ..io.kanal_mapping import (
    LAYOUTS,
    ROLLEN,
    MappingProfil,
    TdmsStruktur,
    fehlende_rollen,
    rate_zuordnung,
    schlage_layout_vor,
    speichere_profil,
    lade_profil,
    standard_profil_verzeichnis,
)
from ..io.tdms_laden import PruefBericht

#: Anzeige-Text fuer "Rolle nicht zugeordnet" (nur optionale Rollen).
_KEINE = "(nicht zugeordnet)"

#: Anzeige-Texte der Speicher-Layouts.
_LAYOUT_TEXTE = {
    "unsortiert": "unsortiert/roh (Matrix: je Feldschritt ein Frequenzsweep)",
    "sortiert": "sortiert/vorverarbeitet (ein Eintrag je Messpunkt)",
}


class MappingDialog(QtWidgets.QDialog):
    """Manuelle Zuordnung der TDMS-Kanaele zu den kanonischen Rollen."""

    def __init__(self, pfad: str, struktur: TdmsStruktur,
                 profile: list[MappingProfil], vorschlag: MappingProfil | None = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("TDMS-Kanaele zuordnen")
        self.setModal(True)
        self.resize(680, 520)
        # Erst nach dem vollstaendigen Aufbau darf _pruefe() laufen: das Fuellen
        # der Kanal-Combos in der ROLLEN-Schleife loest _pruefe() aus, waehrend
        # noch nicht alle Combos/Widgets (layout_combo, knoepfe) existieren.
        self._bereit = False
        self._struktur = struktur
        self._profile = list(profile)
        self._gruppen = sorted(struktur.keys())

        lay = QtWidgets.QVBoxLayout(self)

        kopf = QtWidgets.QLabel(
            f"<b>{Path(pfad).name}</b> – bitte die Kanaele den Rollen zuordnen. "
            f"Pflichtrollen sind mit * markiert.")
        kopf.setWordWrap(True)
        lay.addWidget(kopf)

        # Profil-Zeile: anwenden / speichern / laden.
        profil_reihe = QtWidgets.QHBoxLayout()
        profil_reihe.addWidget(QtWidgets.QLabel("Profil:"))
        self.profil_combo = QtWidgets.QComboBox()
        self.profil_combo.addItem("– manuell / Heuristik –", None)
        for p in self._profile:
            passt = " ✓" if p.passt_auf(struktur) else ""
            self.profil_combo.addItem(p.name + passt, p)
        self.profil_combo.currentIndexChanged.connect(self._profil_gewaehlt)
        profil_reihe.addWidget(self.profil_combo, 1)
        btn_speichern = QtWidgets.QPushButton("Profil speichern …")
        btn_speichern.clicked.connect(self._profil_speichern)
        profil_reihe.addWidget(btn_speichern)
        btn_laden = QtWidgets.QPushButton("Profil laden …")
        btn_laden.clicked.connect(self._profil_laden)
        profil_reihe.addWidget(btn_laden)
        lay.addLayout(profil_reihe)

        # Zuordnungs-Gitter: je Rolle (Label, Gruppe-Combo, Kanal-Combo).
        gitter = QtWidgets.QGridLayout()
        gitter.setColumnStretch(1, 1)
        gitter.setColumnStretch(2, 1)
        gitter.addWidget(QtWidgets.QLabel("<i>Rolle</i>"), 0, 0)
        gitter.addWidget(QtWidgets.QLabel("<i>Gruppe</i>"), 0, 1)
        gitter.addWidget(QtWidgets.QLabel("<i>Kanal</i>"), 0, 2)
        self._gruppe_combos: dict[str, QtWidgets.QComboBox] = {}
        self._kanal_combos: dict[str, QtWidgets.QComboBox] = {}
        for zeile, rolle in enumerate(ROLLEN, start=1):
            stern = " *" if rolle.erforderlich else ""
            gitter.addWidget(QtWidgets.QLabel(rolle.label + stern), zeile, 0)

            g_combo = QtWidgets.QComboBox()
            if not rolle.erforderlich:
                g_combo.addItem(_KEINE)
            g_combo.addItems(self._gruppen)
            g_combo.currentTextChanged.connect(
                lambda _t, r=rolle.name: self._fuelle_kanaele(r))
            gitter.addWidget(g_combo, zeile, 1)
            self._gruppe_combos[rolle.name] = g_combo

            k_combo = QtWidgets.QComboBox()
            k_combo.currentIndexChanged.connect(lambda _i: self._pruefe())
            gitter.addWidget(k_combo, zeile, 2)
            self._kanal_combos[rolle.name] = k_combo
            self._fuelle_kanaele(rolle.name)
        lay.addLayout(gitter)

        # Layout-Wahl.
        layout_reihe = QtWidgets.QHBoxLayout()
        layout_reihe.addWidget(QtWidgets.QLabel("Speicher-Layout:"))
        self.layout_combo = QtWidgets.QComboBox()
        self.layout_combo.addItem("automatisch aus Kanal-Laengen", None)
        for l in LAYOUTS:
            self.layout_combo.addItem(_LAYOUT_TEXTE[l], l)
        self.layout_combo.currentIndexChanged.connect(lambda _i: self._pruefe())
        layout_reihe.addWidget(self.layout_combo, 1)
        lay.addLayout(layout_reihe)

        # Live-Plausibilitaet.
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setWordWrap(True)
        lay.addWidget(self.status_label)

        self.knoepfe = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.knoepfe.button(QtWidgets.QDialogButtonBox.Ok).setText("Weiter zur Vorschau")
        self.knoepfe.accepted.connect(self.accept)
        self.knoepfe.rejected.connect(self.reject)
        lay.addWidget(self.knoepfe)

        # Ab hier stehen alle Widgets und Combos: Live-Pruefung freigeben.
        self._bereit = True

        # Vorbelegung: passendes Profil, sonst Namens-Heuristik.
        if vorschlag is not None:
            index = self.profil_combo.findData(vorschlag)
            if index >= 0:
                self.profil_combo.setCurrentIndex(index)  # loest _profil_gewaehlt aus
            else:
                self._setze_zuordnung(vorschlag.zuordnung, vorschlag.layout)
        else:
            self._setze_zuordnung(rate_zuordnung(struktur), None)
        self._pruefe()

    # --- Zuordnung lesen/schreiben -----------------------------------------
    def zuordnung(self) -> dict[str, tuple[str, str]]:
        """Aktuelle Zuordnung Rollen -> (Gruppe, Kanal) aus den Combos."""
        ergebnis: dict[str, tuple[str, str]] = {}
        for rolle in ROLLEN:
            gruppe = self._gruppe_combos[rolle.name].currentText()
            kanal = self._kanal_combos[rolle.name].currentData()
            if gruppe == _KEINE or not kanal:
                continue
            ergebnis[rolle.name] = (gruppe, kanal)
        return ergebnis

    def layout(self) -> str | None:
        """Explizit gewaehltes Layout oder ``None`` (= automatisch)."""
        return self.layout_combo.currentData()

    def ergebnis(self) -> tuple[dict[str, tuple[str, str]], str | None]:
        """(zuordnung, layout) – Layout ``None`` bedeutet automatisch."""
        layout = self.layout()
        if layout is None:
            layout = schlage_layout_vor(self._struktur, self.zuordnung())
        return self.zuordnung(), layout

    def _setze_zuordnung(self, zuordnung: dict[str, tuple[str, str]],
                         layout: str | None) -> None:
        for rolle in ROLLEN:
            paar = zuordnung.get(rolle.name)
            g_combo = self._gruppe_combos[rolle.name]
            if paar is None:
                if not rolle.erforderlich:
                    g_combo.setCurrentText(_KEINE)
                continue
            gruppe, kanal = paar
            if gruppe not in self._struktur:
                continue
            g_combo.setCurrentText(gruppe)
            k_combo = self._kanal_combos[rolle.name]
            index = k_combo.findData(kanal)
            if index >= 0:
                k_combo.setCurrentIndex(index)
        index = self.layout_combo.findData(layout)
        self.layout_combo.setCurrentIndex(index if index >= 0 else 0)
        self._pruefe()

    def _fuelle_kanaele(self, rollen_name: str) -> None:
        """Kanal-Combo einer Rolle mit den Kanaelen der gewaehlten Gruppe fuellen."""
        gruppe = self._gruppe_combos[rollen_name].currentText()
        k_combo = self._kanal_combos[rollen_name]
        k_combo.blockSignals(True)
        k_combo.clear()
        if gruppe != _KEINE and gruppe in self._struktur:
            for kanal, laenge in self._struktur[gruppe].items():
                k_combo.addItem(f"{kanal}  ({laenge} Werte)", kanal)
        k_combo.blockSignals(False)
        self._pruefe()

    # --- Profil-Aktionen -----------------------------------------------------
    def _profil_gewaehlt(self, index: int) -> None:
        profil = self.profil_combo.itemData(index)
        if profil is not None:
            self._setze_zuordnung(profil.zuordnung, profil.layout)

    def _profil_speichern(self) -> None:
        zuordnung = self.zuordnung()
        fehlt = fehlende_rollen(self._struktur, zuordnung)
        if fehlt:
            QtWidgets.QMessageBox.warning(
                self, "Profil speichern",
                f"Zuordnung unvollstaendig (fehlende Pflichtrollen: {', '.join(fehlt)}).")
            return
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Profil speichern", "Profilname (z. B. Messrechner-Bezeichnung):")
        if not ok or not name.strip():
            return
        name = name.strip()
        layout = self.layout() or schlage_layout_vor(self._struktur, zuordnung)
        if layout is None:
            QtWidgets.QMessageBox.warning(
                self, "Profil speichern",
                "Layout nicht automatisch bestimmbar – bitte explizit waehlen.")
            return
        verzeichnis = standard_profil_verzeichnis()
        vorgabe = verzeichnis / (name.replace(" ", "_") + ".json")
        pfad, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Profil speichern", str(vorgabe), "JSON (*.json)")
        if not pfad:
            return
        profil = MappingProfil(name=name, layout=layout, zuordnung=zuordnung)
        speichere_profil(profil, pfad)
        self._profile.append(profil)
        self.profil_combo.addItem(profil.name + " ✓", profil)
        self.profil_combo.setCurrentIndex(self.profil_combo.count() - 1)

    def _profil_laden(self) -> None:
        pfad, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Profil laden", str(standard_profil_verzeichnis()), "JSON (*.json)")
        if not pfad:
            return
        try:
            profil = lade_profil(pfad)
        except Exception as fehler:
            QtWidgets.QMessageBox.warning(self, "Profil laden", str(fehler))
            return
        self._profile.append(profil)
        passt = " ✓" if profil.passt_auf(self._struktur) else ""
        self.profil_combo.addItem(profil.name + passt, profil)
        self.profil_combo.setCurrentIndex(self.profil_combo.count() - 1)

    # --- Live-Plausibilitaet ---------------------------------------------------
    def _pruefe(self) -> None:
        if not self._bereit:  # waehrend des Dialog-Aufbaus noch nicht pruefen
            return
        zuordnung = self.zuordnung()
        fehlt = fehlende_rollen(self._struktur, zuordnung)
        meldungen: list[str] = []
        if fehlt:
            labels = [ROLLEN[[r.name for r in ROLLEN].index(f)].label for f in fehlt]
            meldungen.append("Fehlende Pflichtrollen: " + ", ".join(labels))
        vorschlag = schlage_layout_vor(self._struktur, zuordnung)
        if self.layout_combo.currentData() is None:
            if vorschlag is not None:
                meldungen.append(f"Layout-Vorschlag: {_LAYOUT_TEXTE[vorschlag]}")
            elif not fehlt:
                meldungen.append(
                    "Layout nicht automatisch bestimmbar (Kanal-Laengen passen zu "
                    "keinem bekannten Muster) – bitte explizit waehlen.")
        # Doppelt vergebene Kanaele sind fast immer ein Versehen.
        paare = list(zuordnung.values())
        doppelte = {p for p in paare if paare.count(p) > 1}
        if doppelte:
            meldungen.append(
                "Achtung: derselbe Kanal ist mehreren Rollen zugeordnet: "
                + ", ".join(f"{g}/{k}" for g, k in sorted(doppelte)))
        ok_erlaubt = not fehlt and (
            self.layout_combo.currentData() is not None or vorschlag is not None)
        knopf = self.knoepfe.button(QtWidgets.QDialogButtonBox.Ok)
        if knopf is not None:
            knopf.setEnabled(ok_erlaubt)
        farbe = "#C0392B" if (fehlt or doppelte) else "#2E7D38"
        self.status_label.setText(
            f'<span style="color:{farbe}">' + "<br>".join(meldungen) + "</span>"
            if meldungen else "")


class VorschauDialog(QtWidgets.QDialog):
    """Validierungs-Bericht + Daten-Vorschau vor Uebernahme des Datensatzes."""

    #: Maximale Zeilenzahl der Vorschau-Tabelle.
    MAX_ZEILEN = 8

    def __init__(self, datensatz: Messdatensatz, bericht: PruefBericht,
                 warnungen: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import-Vorschau")
        self.setModal(True)
        self.resize(640, 480)
        lay = QtWidgets.QVBoxLayout(self)

        kopf = QtWidgets.QLabel(
            f"<b>{Path(datensatz.quelle).name}</b> – "
            f"Profil: {datensatz.meta.get('mapping_profil', '?')}, "
            f"Layout: {datensatz.format_typ}")
        kopf.setWordWrap(True)
        lay.addWidget(kopf)

        # Lade-Warnungen (z. B. Index-Datei-Fallback) prominent anzeigen.
        for warnung in (warnungen or datensatz.meta.get("lade_warnungen", [])):
            w_label = QtWidgets.QLabel("⚠ " + warnung)
            w_label.setWordWrap(True)
            w_label.setStyleSheet("color: #B8860B;")
            lay.addWidget(w_label)

        bericht_text = QtWidgets.QPlainTextEdit(bericht.als_text())
        bericht_text.setReadOnly(True)
        bericht_text.setMaximumHeight(150)
        lay.addWidget(bericht_text)

        # Vorschau: gleichmaessig ueber die Frequenzen verteilte Linescans.
        tabelle = QtWidgets.QTableWidget()
        tabelle.setColumnCount(5)
        tabelle.setHorizontalHeaderLabels(
            ["f (GHz)", "Punkte", "B min (T)", "B max (T)", "⟨|S21|⟩"])
        tabelle.horizontalHeader().setStretchLastSection(True)
        tabelle.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        n = len(datensatz.linescans)
        indizes = np.unique(np.linspace(0, n - 1, min(self.MAX_ZEILEN, n)).astype(int)) if n else []
        tabelle.setRowCount(len(indizes))
        for zeile, i in enumerate(indizes):
            ls = datensatz.linescans[int(i)]
            werte = (
                f"{ls.frequenz / 1e9:.3f}",
                f"{ls.feld.size}",
                f"{float(np.min(ls.feld)):.4f}" if ls.feld.size else "–",
                f"{float(np.max(ls.feld)):.4f}" if ls.feld.size else "–",
                f"{float(np.nanmean(ls.magnitude)):.3e}" if ls.feld.size else "–",
            )
            for spalte, wert in enumerate(werte):
                tabelle.setItem(zeile, spalte, QtWidgets.QTableWidgetItem(wert))
        tabelle.resizeColumnsToContents()
        lay.addWidget(tabelle, 1)

        knoepfe = QtWidgets.QDialogButtonBox()
        b_ok = knoepfe.addButton("Uebernehmen", QtWidgets.QDialogButtonBox.AcceptRole)
        b_zurueck = knoepfe.addButton("Zuordnung aendern", QtWidgets.QDialogButtonBox.RejectRole)
        b_ok.clicked.connect(self.accept)
        b_zurueck.clicked.connect(self.reject)
        if not bericht.in_ordnung:
            b_ok.setText("Trotz Warnungen uebernehmen")
        lay.addWidget(knoepfe)
        # Fokus bewusst auf "Zuordnung aendern", wenn es Warnungen gibt.
        (b_zurueck if not bericht.in_ordnung else b_ok).setDefault(True)

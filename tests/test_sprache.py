# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Oberflaechensprache: tr()/Woerterbuch, Sprachwahl-Datei, englische Oberflaeche."""

import os
import re

import pytest

from polderfit import sprache as S

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

#: Deutsche Merkmale in sichtbaren Texten (Eigennamen ausgenommen).
_DEUTSCH = re.compile(r"[äöüÄÖÜß]|\b(und|oder|nicht|der|die|das|mit|für|Fenster|Bereich|"
                      r"Einstellungen|Speichern|laden|Punkte|Auswahl|gefittet)\b")
_ERLAUBT = ("Müller", "Maier-Flaig", "Deutsch", "Sprache")


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def englisch():
    S.setze_sprache("en")
    yield
    S.setze_sprache("de")


def test_tr_uebersetzt_und_formatiert():
    S.setze_sprache("en")
    try:
        assert S.tr("Abbrechen") == "Cancel"
        assert S.tr("Korridor M{0} angelegt", 2) == "Corridor M2 created"
        assert S.tr("gibt es nicht") == "gibt es nicht"
    finally:
        S.setze_sprache("de")
    assert S.tr("Abbrechen") == "Abbrechen"
    assert S.tr("Korridor M{0} angelegt", 2) == "Korridor M2 angelegt"
    assert S.N_("Abbrechen") == "Abbrechen"


def test_woerterbuch_vollstaendig_und_platzhalter_gleich():
    from polderfit.gui._uebersetzung_schluessel import fehlende
    from polderfit.gui.uebersetzung_en import EN
    assert fehlende() == []
    for deutsch, englisch in EN.items():
        assert sorted(re.findall(r"\{[^{}]*\}", deutsch)) == \
            sorted(re.findall(r"\{[^{}]*\}", englisch)), deutsch
        assert deutsch.count("&") == englisch.count("&"), deutsch


def test_sprachwahl_wird_gespeichert(tmp_path, monkeypatch):
    monkeypatch.setenv("POLDERFIT_KONFIG", str(tmp_path))
    monkeypatch.delenv("POLDERFIT_SPRACHE", raising=False)
    assert S.gespeicherte_sprache() == "en"          # Standard: Englisch
    S.speichere_sprache("de")
    assert S.gespeicherte_sprache() == "de"
    monkeypatch.setenv("POLDERFIT_SPRACHE", "en")
    assert S.gespeicherte_sprache() == "en"          # Umgebung hat Vorrang
    with pytest.raises(ValueError):
        S.speichere_sprache("fr")


def test_menue_sprachwahl_speichert_und_fragt_nach_neustart(app, tmp_path, monkeypatch):
    from unittest.mock import patch
    from polderfit.gui.hauptfenster import Hauptfenster
    monkeypatch.setenv("POLDERFIT_KONFIG", str(tmp_path))
    monkeypatch.delenv("POLDERFIT_SPRACHE", raising=False)
    w = Hauptfenster()
    assert w.akt_sprachen["de"].isChecked()          # Tests laufen auf Deutsch
    with patch.object(QtWidgets.QMessageBox, "question",
                      return_value=QtWidgets.QMessageBox.No) as frage, \
         patch.object(w, "_neu_starten") as neustart:
        w.akt_sprachen["en"].trigger()
    assert S.gespeicherte_sprache() == "en"
    frage.assert_called_once()
    neustart.assert_not_called()
    assert S.sprache() == "de"                       # wirkt erst nach Neustart


def _texte(wurzel) -> list[str]:
    texte = []
    widgets = [wurzel, *wurzel.findChildren(QtWidgets.QWidget)]
    for w in widgets:
        texte += [w.toolTip(), w.windowTitle() if w.isWindow() else ""]
        if isinstance(w, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
            texte.append(w.text())
        if isinstance(w, QtWidgets.QGroupBox):
            texte.append(w.title())
        if isinstance(w, QtWidgets.QMenu):
            texte.append(w.title())
        if isinstance(w, QtWidgets.QComboBox):
            texte += [w.itemText(i) for i in range(w.count())]
        if isinstance(w, QtWidgets.QAbstractSpinBox):
            texte.append(w.specialValueText())
        for a in w.actions():
            texte += [a.text(), a.toolTip(), a.statusTip()]
    return [t for t in texte if t]


def _deutsche_reste(wurzel) -> list[str]:
    reste = []
    for t in _texte(wurzel):
        pruef = t
        for name in _ERLAUBT:
            pruef = pruef.replace(name, "")
        if _DEUTSCH.search(pruef):
            reste.append(t)
    return sorted(set(reste))


def test_englische_oberflaeche_ohne_deutsche_reste(app, englisch):
    from polderfit.gui.hauptfenster import Hauptfenster
    from polderfit.gui.parameter_dialog import ParameterDialog, PhysikParameter
    from polderfit.gui.export_dialog import AllesSpeichernDialog
    from polderfit.gui.bereichsfit_dialog import BereichsFitDialog
    w = Hauptfenster()
    titel = [a.text() for a in w.menuBar().actions()]
    assert titel[:3] == ["&File", "&Edit", "F&unctions"]
    assert "Language" in w.menue_sprache.title()
    assert w.akt_sprachen["en"].isChecked()
    dialoge = [w, ParameterDialog(PhysikParameter()),
               AllesSpeichernDialog("/tmp", "x", True, True),
               BereichsFitDialog(0.1, 1.0, 5.0, 20.0), w._baue_hilfe_dialog()]
    reste = [t for d in dialoge for t in _deutsche_reste(d)]
    assert reste == []
    assert "Workflow" in w._hilfe_html()

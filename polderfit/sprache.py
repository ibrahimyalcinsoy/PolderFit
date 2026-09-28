# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Oberflaechensprache (Englisch/Deutsch).

Quelltexte der Oberflaeche sind deutsch und zugleich Schluessel des englischen
Woerterbuchs (:mod:`polderfit.gui.uebersetzung_en`). :func:`tr` liefert den
Text in der aktiven Sprache (fehlende Eintraege: deutsch) und setzt optionale
Platzhalter per ``str.format`` ein; :func:`N_` markiert Texte, die erst an der
Verwendungsstelle uebersetzt werden (Modulkonstanten). Die Sprachwahl liegt
in ``<Konfigurationsverzeichnis>/oberflaeche.json`` und wirkt ab dem naechsten
Start; Standard ist Englisch. Umgebungsvariable ``POLDERFIT_SPRACHE`` (en/de)
hat Vorrang.
"""

from __future__ import annotations

import json
import os

SPRACHEN = {"en": "English", "de": "Deutsch"}
STANDARD_SPRACHE = "en"

_sprache = STANDARD_SPRACHE
_woerterbuch: dict[str, str] | None = None


def _en() -> dict[str, str]:
    global _woerterbuch
    if _woerterbuch is None:
        from .gui.uebersetzung_en import EN
        _woerterbuch = EN
    return _woerterbuch


def setze_sprache(code: str) -> str:
    """Aktive Sprache setzen (unbekannt -> Standard); liefert den wirksamen Code."""
    global _sprache
    _sprache = code if code in SPRACHEN else STANDARD_SPRACHE
    return _sprache


def sprache() -> str:
    return _sprache


def tr(text: str, *args, **kwargs) -> str:
    """Text in der aktiven Sprache; mit Argumenten zusaetzlich ``format``."""
    if _sprache == "en":
        text = _en().get(text, text)
    return text.format(*args, **kwargs) if (args or kwargs) else text


def N_(text: str) -> str:
    """Markiert ``text`` zur Uebersetzung, ohne ihn schon jetzt zu uebersetzen."""
    return text


def _datei():
    from .persistenz.einstellungen import konfig_verzeichnis
    return konfig_verzeichnis() / "oberflaeche.json"


def gespeicherte_sprache() -> str:
    """Sprachwahl aus Umgebung bzw. Konfigurationsdatei (Standard: Englisch)."""
    umgebung = os.environ.get("POLDERFIT_SPRACHE", "").strip().lower()
    if umgebung in SPRACHEN:
        return umgebung
    try:
        daten = json.loads(_datei().read_text(encoding="utf-8"))
        code = str(daten.get("sprache", ""))
    except Exception:
        return STANDARD_SPRACHE
    return code if code in SPRACHEN else STANDARD_SPRACHE


def speichere_sprache(code: str) -> None:
    """Sprachwahl dauerhaft ablegen (wirkt beim naechsten Start)."""
    if code not in SPRACHEN:
        raise ValueError(f"Unbekannte Sprache: {code}")
    pfad = _datei()
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        if not isinstance(daten, dict):
            daten = {}
    except Exception:
        daten = {}
    daten["sprache"] = code
    pfad.write_text(json.dumps(daten, indent=2) + "\n", encoding="utf-8")

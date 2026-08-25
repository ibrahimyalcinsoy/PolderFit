# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Voreinstellungen (Programmeinstellungen) speichern und laden.

Gebuendelt werden alle Einstellungen, die NICHT zu einer bestimmten Messung
gehoeren, sondern zur Arbeitsweise des Nutzers:

* ``physik``       – :class:`polderfit.fit.parameter.PhysikParameter` (g-Faktor,
                     Geometrie, Fensterfaktor, Schwellen, α-Grenzen, n Moden …)
* ``verarbeitung`` – Verarbeitungskette des Farbplots (:class:`Verarbeitungskette`)
* ``anzeige``      – Farbskala, Zoom, Problemfits ausblenden, ganzer Feldsweep …
* ``export``       – Spaltengruppen und Optionen des Excel-/CSV-Exports
* ``bereichsfit``  – zuletzt benutzte Optionen des Bereichs-/Grenzgeraden-Fits

Bewusst NICHT enthalten: Fenstergeometrie, Dock-Layout, Zoom-Ausschnitt oder
Achsengroessen - solche Anzeige-Zustaende werden nie gespeichert, damit ein
verklemmtes Layout nicht "mitgespeichert" und beim naechsten Start wieder
eingeschleppt wird (Ansicht -> Fensterlayout zuruecksetzen stellt immer den
Auslieferungszustand her).

Dateiformat: JSON (UTF-8), Endung ``.polderfit-einstellungen.json``. Die
Datei im Konfigurationsverzeichnis (:func:`standard_pfad`) wird beim
Programmstart automatisch geladen ("Als Standard speichern").
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .. import PROGRAMMNAME
from ..fit.parameter import PhysikParameter
from ..verarbeitung import Verarbeitungskette

EINSTELLUNGEN_VERSION = 1
DATEI_ENDUNG = ".polderfit-einstellungen.json"

#: Waehlbare Farbskalen des Farbplots (Name -> Beschreibung fuer die GUI).
FARBSKALEN = {
    "viridis": "Viridis (wahrnehmungsgleich, Standard)",
    "gray": "Grau (neutral – Signalfarben der Fits stechen hervor)",
    "cividis": "Cividis (farbfehlsichtigkeitsfreundlich)",
    "magma": "Magma",
    "RdBu_r": "Rot-Blau (divergierend, für derivative divide)",
}

STANDARD_ANZEIGE = {
    "farbskala": "viridis",
    "zoom_aktiv": False,
    "problemfits_ausblenden": False,
    "vollbereich": False,
    "ausreisser_anzeigen": False,
    "nebenmoden_anzeigen": True,
}

STANDARD_EXPORT = {
    #: Spaltengruppen (Schluessel siehe ergebnis_export.SPALTEN_GRUPPEN); leer = alle.
    "spalten": [],
    #: Nur Frequenzen mit echtem Fitergebnis exportieren (keine Platzhalter).
    "nur_gefittete": True,
    #: CSV mit ';' und Dezimalkomma (deutsches Excel) statt ',' und Punkt.
    "csv_deutsch": False,
    #: Zusatzblaetter in der Excel-Datei (Einstellungen, Zonen/Geraden, Ausreisser).
    "zusatzblaetter": True,
}

STANDARD_BEREICHSFIT = {"modus": "ueberschreiben", "breite_punkte": None}


@dataclass
class Einstellungen:
    """Alle speicherbaren Voreinstellungen (siehe Modulkopf)."""

    physik: dict = field(default_factory=lambda: PhysikParameter().als_dict())
    verarbeitung: dict = field(default_factory=lambda: Verarbeitungskette.standard().als_dict())
    anzeige: dict = field(default_factory=lambda: dict(STANDARD_ANZEIGE))
    export: dict = field(default_factory=lambda: dict(STANDARD_EXPORT))
    bereichsfit: dict = field(default_factory=lambda: dict(STANDARD_BEREICHSFIT))

    # --- bequeme Zugriffe -----------------------------------------------------
    def physik_parameter(self) -> PhysikParameter:
        return PhysikParameter.aus_dict(self.physik)

    def verarbeitungskette(self) -> Verarbeitungskette:
        try:
            kette = Verarbeitungskette.aus_dict(self.verarbeitung)
        except Exception:
            kette = Verarbeitungskette.standard()
        if not kette.schritte:
            kette = Verarbeitungskette.standard()
        return kette

    def als_dict(self) -> dict:
        return {
            "polderfit_einstellungen_version": EINSTELLUNGEN_VERSION,
            "programm": PROGRAMMNAME,
            "physik": dict(self.physik),
            "verarbeitung": dict(self.verarbeitung),
            "anzeige": {**STANDARD_ANZEIGE, **self.anzeige},
            "export": {**STANDARD_EXPORT, **self.export},
            "bereichsfit": {**STANDARD_BEREICHSFIT, **self.bereichsfit},
        }

    @classmethod
    def aus_dict(cls, daten: dict | None) -> "Einstellungen":
        daten = dict(daten or {})
        e = cls()
        if isinstance(daten.get("physik"), dict):
            e.physik = PhysikParameter.aus_dict(daten["physik"]).als_dict()
        if isinstance(daten.get("verarbeitung"), dict):
            e.verarbeitung = dict(daten["verarbeitung"])
        for name, standard in (("anzeige", STANDARD_ANZEIGE), ("export", STANDARD_EXPORT),
                               ("bereichsfit", STANDARD_BEREICHSFIT)):
            wert = daten.get(name)
            if isinstance(wert, dict):
                setattr(e, name, {**standard, **{k: v for k, v in wert.items() if k in standard}})
        if e.anzeige.get("farbskala") not in FARBSKALEN:
            e.anzeige["farbskala"] = STANDARD_ANZEIGE["farbskala"]
        return e


# --- Dateien ---------------------------------------------------------------------
def konfig_verzeichnis() -> Path:
    """Plattformgerechtes Konfigurationsverzeichnis (wird bei Bedarf angelegt).

    Windows: ``%APPDATA%\\PolderFit``; macOS: ``~/Library/Application Support/
    PolderFit``; Linux: ``$XDG_CONFIG_HOME/polderfit`` bzw. ``~/.config/polderfit``.
    Ueberschreibbar mit der Umgebungsvariable ``POLDERFIT_KONFIG``.
    """
    eigen = os.environ.get("POLDERFIT_KONFIG")
    if eigen:
        pfad = Path(eigen)
    elif sys.platform.startswith("win"):
        basis = os.environ.get("APPDATA") or str(Path.home())
        pfad = Path(basis) / "PolderFit"
    elif sys.platform == "darwin":
        pfad = Path.home() / "Library" / "Application Support" / "PolderFit"
    else:
        basis = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        pfad = Path(basis) / "polderfit"
    try:
        pfad.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return pfad


def standard_pfad() -> Path:
    """Datei der beim Start automatisch geladenen Voreinstellungen."""
    return konfig_verzeichnis() / f"standard{DATEI_ENDUNG}"


def autosicherung_pfad() -> Path:
    """Datei der automatischen Sicherung des Arbeitsstands (Projekt-JSON)."""
    return konfig_verzeichnis() / "autosicherung.polderfit-projekt.json"


def speichere_einstellungen(einstellungen: Einstellungen, pfad: str | Path) -> Path:
    """Schreibt die Voreinstellungen als JSON (UTF-8); liefert den Pfad."""
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(einstellungen.als_dict(), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return pfad


def lade_einstellungen(pfad: str | Path) -> Einstellungen:
    """Liest Voreinstellungen; unbekannte Schluessel werden ignoriert."""
    daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
    if not isinstance(daten, dict):
        raise ValueError("Einstellungsdatei enthaelt kein JSON-Objekt.")
    return Einstellungen.aus_dict(daten)


def lade_standard() -> tuple[Einstellungen, bool]:
    """Voreinstellungen aus :func:`standard_pfad` (falls vorhanden und lesbar).

    Liefert ``(einstellungen, geladen)``; bei fehlender/defekter Datei die
    Programm-Standardwerte und ``False``.
    """
    pfad = standard_pfad()
    if pfad.exists():
        try:
            return lade_einstellungen(pfad), True
        except Exception:
            return Einstellungen(), False
    return Einstellungen(), False

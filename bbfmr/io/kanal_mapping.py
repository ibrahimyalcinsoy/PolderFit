"""Kanal-Mapping: TDMS-Gruppen/-Kanaele auf kanonische Rollen abbilden.

Verschiedene Messrechner erzeugen unterschiedlich benannte und sortierte
TDMS-Dateien. Damit die restliche Pipeline (Fit, Auswertung, Export) davon
nichts mitbekommt, wird beim Laden jede Datei ueber ein *Mapping* auf
kanonische Rollen abgebildet (Frequenz, Re/Im(S21), Feld vor/nach Sweep,
Temperatur). Saemtliche Verarbeitung rechnet ausschliesslich mit diesen
internen Rollen; die Original-Kanalnamen tauchen danach nur noch in den
Metadaten auf.

Ein :class:`MappingProfil` buendelt eine solche Zuordnung inklusive
Speicher-Layout und ist als JSON speicher-/ladbar, damit man pro Messrechner
nur einmal zuordnen muss. Zwei Profile fuer die am WMI bekannten Layouts
werden mitgeliefert (:data:`EINGEBAUTE_PROFILE`).

Speicher-Layouts (``layout``):

* ``"unsortiert"``  – Rohdaten-Messfile: pro Feldschritt ein kompletter,
  identischer Frequenzsweep. Die Feldkanaele haben ``n_feld`` Eintraege, die
  Signalkanaele ``n_feld * n_freq`` (Matrix per Reshape).
* ``"sortiert"``    – vorverarbeitetes File: ein Eintrag pro Messpunkt, alle
  Kanaele gleich lang; die Punkte werden nach Frequenz gruppiert (variable
  Feldpunktzahl je Frequenz).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

#: Struktur einer TDMS-Datei wie von ``inspiziere_tdms`` geliefert:
#: ``{gruppe: {kanal: anzahl_werte}}``.
TdmsStruktur = dict[str, dict[str, int]]

#: Gueltige Speicher-Layouts.
LAYOUTS = ("unsortiert", "sortiert")


@dataclass(frozen=True)
class Rolle:
    """Eine kanonische Rolle, der ein TDMS-Kanal zugeordnet werden kann."""

    name: str          #: interner Schluessel (stabil, wird in JSON verwendet)
    label: str         #: Anzeigename fuer Dialoge
    erforderlich: bool #: ohne diese Rolle ist kein Laden moeglich


#: Alle kanonischen Rollen in Anzeige-Reihenfolge. Einheiten-Konvention des
#: Projekts: Feld in Tesla, Frequenz in Hz, Temperatur in Kelvin.
ROLLEN: tuple[Rolle, ...] = (
    Rolle("frequenz", "Frequenz (Hz)", True),
    Rolle("re_s21", "Re(S21)", True),
    Rolle("im_s21", "Im(S21)", True),
    Rolle("feld_before", "Externes Feld vor Sweep (T)", True),
    Rolle("feld_after", "Externes Feld nach Sweep (T)", False),
    Rolle("temperatur", "Temperatur (K)", False),
)

#: Schneller Zugriff: Rollenname -> Rolle.
ROLLE_JE_NAME = {r.name: r for r in ROLLEN}

#: Namen der Pflicht-Rollen.
ERFORDERLICHE_ROLLEN = tuple(r.name for r in ROLLEN if r.erforderlich)


@dataclass
class MappingProfil:
    """Benannte Zuordnung Rollen -> (Gruppe, Kanal) fuer einen Messrechner.

    ``zuordnung`` enthaelt je Rolle ein ``(gruppe, kanal)``-Paar; optionale
    Rollen duerfen fehlen. ``layout`` ist eines von :data:`LAYOUTS`.
    """

    name: str
    layout: str
    zuordnung: dict[str, tuple[str, str]] = field(default_factory=dict)
    beschreibung: str = ""

    def __post_init__(self):
        if self.layout not in LAYOUTS:
            raise ValueError(f"Unbekanntes Layout {self.layout!r} (erlaubt: {LAYOUTS})")
        # JSON-geladene Listen in Tupel normalisieren.
        self.zuordnung = {r: tuple(gk) for r, gk in self.zuordnung.items()}

    def passt_auf(self, struktur: TdmsStruktur) -> bool:
        """True, wenn alle Pflicht-Rollen dieses Profils in der Datei existieren."""
        for rolle in ERFORDERLICHE_ROLLEN:
            paar = self.zuordnung.get(rolle)
            if paar is None:
                return False
            gruppe, kanal = paar
            if kanal not in struktur.get(gruppe, {}):
                return False
        return True

    def als_dict(self) -> dict:
        return {
            "bbfmr_mapping_profil": 1,
            "name": self.name,
            "layout": self.layout,
            "beschreibung": self.beschreibung,
            "zuordnung": {r: list(gk) for r, gk in self.zuordnung.items()},
        }

    @classmethod
    def aus_dict(cls, daten: dict) -> "MappingProfil":
        if "zuordnung" not in daten or "layout" not in daten:
            raise ValueError("Kein gueltiges bbFMR-Mapping-Profil (zuordnung/layout fehlt).")
        unbekannt = set(daten["zuordnung"]) - set(ROLLE_JE_NAME)
        if unbekannt:
            raise ValueError(f"Unbekannte Rollen im Profil: {sorted(unbekannt)}")
        return cls(
            name=str(daten.get("name", "unbenannt")),
            layout=str(daten["layout"]),
            zuordnung={r: tuple(gk) for r, gk in daten["zuordnung"].items()},
            beschreibung=str(daten.get("beschreibung", "")),
        )


# --- Mitgelieferte Profile fuer die bekannten Messrechner-Layouts -----------

PROFIL_UNSORTIERT = MappingProfil(
    name="WMI unsortiert/roh (Read.PNAX)",
    layout="unsortiert",
    zuordnung={
        "frequenz": ("Read.PNAX", "Frequency"),
        "re_s21": ("Read.PNAX", "REALS21"),
        "im_s21": ("Read.PNAX", "IMAGinaryS21"),
        "feld_before": ("Read.Fieldbefore", "IPS X-Field"),
        "feld_after": ("Read.Fieldafter", "IPS X-Field"),
        "temperatur": ("Read.Temperature", "LakeshoreTemperature"),
    },
    beschreibung="Rohdaten-Messfile des PNA-X-Messrechners: pro Feldschritt ein Frequenzsweep.",
)

PROFIL_SORTIERT = MappingProfil(
    name="WMI sortiert/vorverarbeitet (ZVB)",
    layout="sortiert",
    zuordnung={
        "frequenz": ("ZVB", "frequency"),
        "re_s21": ("ZVB", "ReS21"),
        "im_s21": ("ZVB", "ImS21"),
        "feld_before": ("Field", "Field-before"),
        "feld_after": ("Field", "Field-after"),
    },
    beschreibung="Vorverarbeitetes (sortiertes) File: ein Eintrag je Messpunkt, nach Frequenz gruppierbar.",
)

EINGEBAUTE_PROFILE: tuple[MappingProfil, ...] = (PROFIL_UNSORTIERT, PROFIL_SORTIERT)


# --- Profil-Dateien (JSON, UTF-8) -------------------------------------------

def standard_profil_verzeichnis() -> Path:
    """Verzeichnis fuer Nutzer-Profile (plattformunabhaengig im Home)."""
    return Path.home() / ".bbfmr" / "mapping-profile"


def speichere_profil(profil: MappingProfil, pfad: Path | str) -> Path:
    """Schreibt ein Profil als JSON (UTF-8). Legt Elternverzeichnisse an."""
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        json.dumps(profil.als_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return pfad


def lade_profil(pfad: Path | str) -> MappingProfil:
    """Liest ein Profil aus einer JSON-Datei (UTF-8)."""
    return MappingProfil.aus_dict(json.loads(Path(pfad).read_text(encoding="utf-8")))


def lade_profile(verzeichnis: Path | str | None = None) -> list[MappingProfil]:
    """Alle gueltigen ``*.json``-Profile eines Verzeichnisses (still ueberspringend)."""
    verzeichnis = Path(verzeichnis) if verzeichnis is not None else standard_profil_verzeichnis()
    profile: list[MappingProfil] = []
    if not verzeichnis.is_dir():
        return profile
    for datei in sorted(verzeichnis.glob("*.json")):
        try:
            profile.append(lade_profil(datei))
        except (ValueError, OSError, json.JSONDecodeError):
            continue  # fremde/defekte JSON-Dateien nicht als Profil anbieten
    return profile


# --- Auswahl-Hilfen -----------------------------------------------------------

def finde_profil(struktur: TdmsStruktur,
                 profile: list[MappingProfil] | tuple[MappingProfil, ...] | None = None
                 ) -> MappingProfil | None:
    """Erstes Profil, dessen Pflicht-Rollen vollstaendig in der Datei vorkommen.

    Nutzerprofile (falls uebergeben) haben Vorrang vor den eingebauten.
    """
    kandidaten = list(profile) if profile is not None else []
    for p in EINGEBAUTE_PROFILE:
        if p not in kandidaten:
            kandidaten.append(p)
    for p in kandidaten:
        if p.passt_auf(struktur):
            return p
    return None


#: Substring-Heuristik je Rolle fuer unbekannte Layouts (Reihenfolge = Prioritaet;
#: Vergleich case-insensitiv auf dem Kanalnamen).
_NAMENS_HINWEISE: dict[str, tuple[str, ...]] = {
    "frequenz": ("frequency", "frequenz", "freq"),
    "re_s21": ("reals21", "res21", "real", "re("),
    "im_s21": ("imaginarys21", "ims21", "imag", "im("),
    "feld_before": ("field-before", "fieldbefore", "field (t)", "field", "feld"),
    "feld_after": ("field-after", "fieldafter",),
    "temperatur": ("temperature", "temperatur", "temp"),
}


def rate_zuordnung(struktur: TdmsStruktur) -> dict[str, tuple[str, str]]:
    """Heuristischer Zuordnungs-Vorschlag fuer eine unbekannte Datei.

    Sucht je Rolle den ersten Kanal, dessen Name einen der bekannten
    Substrings enthaelt (case-insensitiv). Bereits vergebene Kanaele werden
    nicht doppelt vorgeschlagen. Nur ein Vorschlag – die Entscheidung trifft
    der Nutzer im Dialog.
    """
    vorschlag: dict[str, tuple[str, str]] = {}
    vergeben: set[tuple[str, str]] = set()
    for rolle in ROLLEN:
        for hinweis in _NAMENS_HINWEISE.get(rolle.name, ()):
            treffer = None
            for gruppe, kanaele in struktur.items():
                for kanal in kanaele:
                    if hinweis in kanal.lower() and (gruppe, kanal) not in vergeben:
                        treffer = (gruppe, kanal)
                        break
                if treffer:
                    break
            if treffer:
                vorschlag[rolle.name] = treffer
                vergeben.add(treffer)
                break
    return vorschlag


def schlage_layout_vor(struktur: TdmsStruktur,
                       zuordnung: dict[str, tuple[str, str]]) -> str | None:
    """Layout-Vorschlag aus den Kanal-Laengen der gewaehlten Zuordnung.

    * Frequenz- und Feldkanal gleich lang           -> ``"sortiert"``
    * Frequenzlaenge ganzzahliges Vielfaches (> 1)
      der Feldlaenge                                -> ``"unsortiert"``
    * sonst ``None`` (Nutzer muss entscheiden).
    """
    def laenge(rolle: str) -> int | None:
        paar = zuordnung.get(rolle)
        if paar is None:
            return None
        gruppe, kanal = paar
        return struktur.get(gruppe, {}).get(kanal)

    n_freq = laenge("frequenz")
    n_feld = laenge("feld_before")
    if not n_freq or not n_feld:
        return None
    if n_freq == n_feld:
        return "sortiert"
    if n_freq % n_feld == 0 and n_freq // n_feld > 1:
        return "unsortiert"
    return None


def fehlende_rollen(struktur: TdmsStruktur,
                    zuordnung: dict[str, tuple[str, str]]) -> list[str]:
    """Pflicht-Rollen, die fehlen oder auf nicht existierende Kanaele zeigen."""
    fehlt: list[str] = []
    for rolle in ERFORDERLICHE_ROLLEN:
        paar = zuordnung.get(rolle)
        if paar is None:
            fehlt.append(rolle)
            continue
        gruppe, kanal = paar
        if kanal not in struktur.get(gruppe, {}):
            fehlt.append(rolle)
    return fehlt

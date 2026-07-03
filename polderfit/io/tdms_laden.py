# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Einlesen von TDMS-Dateien ueber kanonisches Kanal-Mapping.

Jede Datei wird ueber eine Zuordnung Rollen -> (Gruppe, Kanal) eingelesen
(siehe :mod:`polderfit.io.kanal_mapping`). Fuer die beiden am WMI bekannten
Layouts existieren eingebaute Profile, die automatisch erkannt werden –
``lade_tdms(pfad)`` verhaelt sich damit wie bisher:

* Profil "unsortiert/roh"          (Gruppen ``Read.PNAX``, ``Read.Fieldbefore`` ...)
* Profil "sortiert/vorverarbeitet" (Gruppen ``ZVB``, ``Field``)

Unbekannte Layouts loesen :class:`MappingErforderlich` aus; die GUI faengt das
ab und oeffnet den Zuordnungs-Dialog. Felder liegen in Tesla vor, Frequenzen
in Hz (Konvention des Projekts).

Robustheit gegen defekte Index-Dateien (bekannter Windows-Fall): liegt neben
der ``.tdms``-Datei eine nicht dazu passende ``.tdms_index``-Datei, schlaegt
nptdms mit ``ValueError: ... did not find segment start header ...`` fehl.
In dem Fall wird die Datei erneut ueber ein offenes Dateiobjekt gelesen –
dann ignoriert nptdms die Index-Datei – und eine Warnung vermerkt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from nptdms import TdmsFile

from .datensatz import Linescan, Messdatensatz
from .kanal_mapping import (
    EINGEBAUTE_PROFILE,
    LAYOUTS,
    MappingProfil,
    TdmsStruktur,
    fehlende_rollen,
    finde_profil,
    schlage_layout_vor,
)


class MappingErforderlich(ValueError):
    """Kein (mitgeliefertes oder uebergebenes) Profil passt auf die Datei.

    Traegt die inspizierte ``struktur`` (Gruppen/Kanaele), damit ein Dialog
    dem Nutzer die manuelle Zuordnung anbieten kann.
    """

    def __init__(self, pfad: str, struktur: TdmsStruktur):
        self.pfad = str(pfad)
        self.struktur = struktur
        gruppen = {g: sorted(k) for g, k in sorted(struktur.items())}
        super().__init__(
            f"Kein Mapping-Profil passt auf {Path(pfad).name!r}. "
            f"Bitte Kanaele manuell zuordnen. Vorhandene Gruppen/Kanaele: {gruppen}"
        )


# --- Robustes Lesen (Index-Datei-Fallback) -----------------------------------

def _index_pfad(pfad: Path) -> Path:
    """Pfad der zugehoerigen Index-Datei (``<name>.tdms_index``)."""
    return Path(str(pfad) + "_index")


def _index_warnung(index: Path, grund: str) -> str:
    """Einheitlicher Warntext fuer den Index-Datei-Fallback."""
    return (
        f"Die Index-Datei {index.name!r} passt nicht zur Datendatei "
        f"({grund}). Die Datei wurde ohne Index-Datei gelesen; Daten sind "
        f"vollstaendig, das Laden dauert nur etwas laenger. Empfehlung: die "
        f"veraltete .tdms_index-Datei loeschen oder neu erzeugen."
    )


def _lese_ohne_index(pfad: Path, lese):
    """TDMS ueber offenes Dateiobjekt lesen – nptdms zieht dann keine Index-Datei heran."""
    with open(pfad, "rb") as datei:
        return lese(datei)


def _lese_robust(pfad: Path | str, metadaten_nur: bool = False
                 ) -> tuple[TdmsFile, list[str]]:
    """Liest eine TDMS-Datei; bei defekter/fremder Index-Datei ohne Index erneut.

    nptdms zieht eine neben der Datendatei liegende ``.tdms_index``-Datei
    automatisch heran. Passt sie nicht zur Datendatei (typisch: Datei kopiert/
    umbenannt, Index veraltet), gibt es zwei Fehlerbilder:

    * Der Index hat einen lesbaren, aber falschen Segment-Header – nptdms bricht
      mit ``ValueError`` (bzw. ``KeyError``/``EOFError``) ab.
    * Der Index ist zu kurz/kaputt – nptdms deutet das erste EOF als Dateiende,
      bricht die Segment-Schleife OHNE Fehler ab und liefert eine LEERE Struktur.

    In beiden Faellen wird die Datei ueber ein offenes Dateiobjekt erneut
    gelesen (dann sucht nptdms keine Index-Datei) und eine Warnung vermerkt.
    Liefert ``(tdms, warnungen)``.
    """
    pfad = Path(pfad)
    index = _index_pfad(pfad)
    lese = TdmsFile.read_metadata if metadaten_nur else TdmsFile.read
    try:
        tdms = lese(pfad)
    except (ValueError, KeyError, EOFError) as fehler:
        if not index.exists():
            raise
        try:
            tdms = _lese_ohne_index(pfad, lese)
        except Exception:
            raise fehler from None
        return tdms, [_index_warnung(index, str(fehler))]

    # Stiller Defekt: Index vorhanden, aber indexbasiertes Lesen liefert keine
    # Gruppe. Ohne Index erneut lesen; kommen dann Gruppen zurueck, war der
    # Index schuld (sonst ist die Datei tatsaechlich leer -> Original zurueck).
    if index.exists() and not tdms.groups():
        try:
            ohne = _lese_ohne_index(pfad, lese)
        except Exception:
            return tdms, []
        if ohne.groups():
            return ohne, [_index_warnung(index, "Index-Datei unlesbar oder leer")]
    return tdms, []


def inspiziere_tdms(pfad: Path | str) -> tuple[TdmsStruktur, list[str]]:
    """Listet Gruppen/Kanaele einer TDMS-Datei ohne die Daten zu laden.

    Liefert ``({gruppe: {kanal: anzahl_werte}}, warnungen)``.
    """
    tdms, warnungen = _lese_robust(pfad, metadaten_nur=True)
    struktur: TdmsStruktur = {}
    for gruppe in tdms.groups():
        kanaele: dict[str, int] = {}
        for kanal in gruppe.channels():
            try:
                kanaele[kanal.name] = len(kanal)
            except (TypeError, KeyError):
                kanaele[kanal.name] = 0
        struktur[gruppe.name] = kanaele
    return struktur, warnungen


# --- Laden --------------------------------------------------------------------

def lade_tdms(
    pfad: Path | str,
    profil: MappingProfil | None = None,
    zuordnung: dict[str, tuple[str, str]] | None = None,
    layout: str | None = None,
    profile: list[MappingProfil] | None = None,
) -> Messdatensatz:
    """Liest eine TDMS-Datei ueber ein Kanal-Mapping ein.

    Aufruf-Varianten:

    * ``lade_tdms(pfad)`` – Profil automatisch erkennen (eingebaute Profile
      plus optionale ``profile``-Liste). Passt keines: :class:`MappingErforderlich`.
    * ``lade_tdms(pfad, profil=...)`` – explizites Profil verwenden.
    * ``lade_tdms(pfad, zuordnung=..., layout=...)`` – manuelle Zuordnung aus
      dem Dialog; ``layout`` (``"unsortiert"``/``"sortiert"``) darf fehlen und
      wird dann aus den Kanal-Laengen vorgeschlagen.
    """
    pfad = Path(pfad)
    struktur, warnungen = inspiziere_tdms(pfad)

    profil_name = "manuell"
    if zuordnung is None:
        if profil is None:
            profil = finde_profil(struktur, profile)
        if profil is None:
            raise MappingErforderlich(str(pfad), struktur)
        if not profil.passt_auf(struktur):
            fehlt = fehlende_rollen(struktur, profil.zuordnung)
            raise ValueError(
                f"Profil {profil.name!r} passt nicht auf {pfad.name!r}: "
                f"fehlende Pflicht-Rollen {fehlt}."
            )
        zuordnung = dict(profil.zuordnung)
        layout = profil.layout
        profil_name = profil.name

    fehlt = fehlende_rollen(struktur, zuordnung)
    if fehlt:
        raise ValueError(
            f"Zuordnung unvollstaendig fuer {pfad.name!r}: fehlende Pflicht-Rollen {fehlt}."
        )
    if layout is None:
        layout = schlage_layout_vor(struktur, zuordnung)
    if layout not in LAYOUTS:
        raise ValueError(
            f"Speicher-Layout nicht bestimmbar fuer {pfad.name!r} – bitte explizit "
            f"'unsortiert' oder 'sortiert' angeben (Kanal-Laengen: "
            f"Frequenz und Feld passen zu keinem bekannten Layout)."
        )

    tdms, lese_warnungen = _lese_robust(pfad)
    warnungen = warnungen + [w for w in lese_warnungen if w not in warnungen]

    if layout == "unsortiert":
        datensatz = _lade_unsortiert(tdms, str(pfad), zuordnung)
    else:
        datensatz = _lade_sortiert(tdms, str(pfad), zuordnung)

    datensatz.meta["mapping_profil"] = profil_name
    datensatz.meta["zuordnung"] = {r: list(gk) for r, gk in zuordnung.items()}
    if warnungen:
        datensatz.meta["lade_warnungen"] = warnungen
    return datensatz


def _rolle(tdms, zuordnung: dict[str, tuple[str, str]], rolle: str,
           optional: bool = False) -> np.ndarray | None:
    """Kanaldaten einer Rolle; ``None`` fuer nicht zugeordnete optionale Rollen."""
    paar = zuordnung.get(rolle)
    if paar is None:
        if optional:
            return None
        raise KeyError(f"Rolle {rolle!r} ist nicht zugeordnet.")
    gruppe, kanal = paar
    try:
        return np.asarray(tdms[gruppe][kanal][:])
    except KeyError:
        if optional:
            return None
        raise


def _sweep_periode(frequenz: np.ndarray, atol_hz: float = 1.0) -> int | None:
    """Sweep-Laenge n_freq aus der Frequenzspur ableiten.

    Liefert den kleinsten Index ``p >= 2``, an dem die Frequenz wieder auf den
    Startwert ``frequenz[0]`` zurueckkehrt (innerhalb ``atol_hz``) – also den
    Beginn des naechsten Frequenzsweeps. ``None``, falls keine Periode gefunden.
    """
    f0 = frequenz[0]
    for p in range(2, frequenz.size):
        if abs(frequenz[p] - f0) <= atol_hz:
            return p
    return None


def _lade_unsortiert(tdms, pfad: str, zuordnung: dict[str, tuple[str, str]]) -> Messdatensatz:
    """Rohdaten-Messfile: n_feld x n_freq Matrix (reshape statt Schleife)."""
    frequenz = _rolle(tdms, zuordnung, "frequenz")
    re = _rolle(tdms, zuordnung, "re_s21")
    im = _rolle(tdms, zuordnung, "im_s21")

    feld_before = _rolle(tdms, zuordnung, "feld_before")
    feld_after = _rolle(tdms, zuordnung, "feld_after", optional=True)
    if feld_after is None:
        feld_after = np.array([])
    n_feld = feld_before.size

    # Temperatur (je Feldwert) optional – frueh laden, damit ein evtl. mitten im
    # Sweep "geflushtes" File (siehe unten) auch die Temperaturspur korrekt kuerzt.
    temperatur = _rolle(tdms, zuordnung, "temperatur", optional=True)

    if frequenz.size % n_feld != 0:
        # Mitten im Sweep auf Platte geschriebenes ("_flush") Messfile: der letzte
        # Feldschritt wurde begonnen, aber nicht zu Ende gesweept. Dadurch hat
        # Fieldbefore einen Eintrag mehr (N+1) als vollstaendige Sweeps (N), und
        # frequenz.size (= N*n_freq) ist nicht durch feld_before.size teilbar.
        # -> n_freq aus der Sweep-Periode ableiten und auf vollstaendige Sweeps kuerzen.
        n_freq = _sweep_periode(frequenz)
        if n_freq is None or frequenz.size % n_freq != 0:
            raise ValueError(
                f"Punktzahl {frequenz.size} nicht durch Feldanzahl {n_feld} teilbar "
                "und Sweep-Periode nicht eindeutig bestimmbar – Reshape nicht moeglich."
            )
        n_complete = frequenz.size // n_freq
        if n_complete < 1:
            raise ValueError(
                f"Unsortiertes TDMS (flush): kein vollstaendiger Frequenzsweep "
                f"({frequenz.size} Punkte, Periode {n_freq}) – Reshape nicht moeglich."
            )

        # Auf die vollstaendig gemessenen Sweeps kuerzen.
        n_punkte = n_complete * n_freq
        frequenz = frequenz[:n_punkte]
        re = re[:n_punkte]
        im = im[:n_punkte]
        feld_before = feld_before[:n_complete]
        feld_after = feld_after[:n_complete]
        if temperatur is not None:
            temperatur = temperatur[:n_complete]
        n_feld = n_complete

    if frequenz.size % n_feld != 0:
        raise ValueError(
            f"Punktzahl {frequenz.size} nicht durch Feldanzahl {n_feld} teilbar – "
            "Reshape nicht moeglich."
        )
    n_freq = frequenz.size // n_feld

    # Reihenfolge: pro Feldwert ein voller Frequenzsweep -> (n_feld, n_freq).
    freq_m = frequenz.reshape(n_feld, n_freq)
    re_m = re.reshape(n_feld, n_freq)
    im_m = im.reshape(n_feld, n_freq)
    freq_achse = freq_m[0]  # Sweep ist je Zeile identisch.

    # Dokumentierte Annahme (Protokoll 3.1): je Feldwert ein IDENTISCHER
    # Frequenzsweep. n_feld*n_freq teilt sich i. d. R. in beiden Orientierungen
    # (z. B. 725725 = 725*1001); ein abweichend "feld-schnell" gespeichertes File
    # wuerde sonst still zu vertauschten Linescans fuehren. Daher absichern:
    if not np.allclose(freq_m, freq_achse, rtol=0.0, atol=1.0):
        raise ValueError(
            "Unsortiertes TDMS: Frequenzsweep ist nicht je Feldwert identisch – "
            "vermutlich abweichendes Speicher-Layout (Feld als schnelle Achse?). "
            "Reshape (n_feld x n_freq) ist hier nicht zulaessig."
        )

    # Temperatur (je Feldwert) muss zur Feldanzahl passen, sonst verwerfen.
    if temperatur is not None and temperatur.size != n_feld:
        temperatur = None

    # Feld je Feldwert: Mittel aus before/after (robust); Fallback before.
    feld_punkt = 0.5 * (feld_before + feld_after) if feld_after.size == n_feld else feld_before
    ordnung = np.argsort(feld_punkt)

    linescans: list[Linescan] = []
    for j in range(n_freq):
        feld = feld_punkt[ordnung]
        linescans.append(
            Linescan(
                frequenz=float(freq_achse[j]),
                feld=feld,
                re=re_m[ordnung, j],
                im=im_m[ordnung, j],
                feld_before=feld_before[ordnung],
                feld_after=feld_after[ordnung] if feld_after.size == n_feld else None,
                temperatur=temperatur[ordnung] if temperatur is not None else None,
            )
        )

    meta = {
        "n_feld": int(n_feld),
        "n_freq": int(n_freq),
        "frequenz_start_hz": float(freq_achse.min()),
        "frequenz_stop_hz": float(freq_achse.max()),
    }
    return Messdatensatz(quelle=pfad, format_typ="unsortiert", linescans=linescans, meta=meta)


def _lade_sortiert(tdms, pfad: str, zuordnung: dict[str, tuple[str, str]]) -> Messdatensatz:
    """Sortiertes File: Punktzahl je Frequenz NICHT konstant – aus Daten ableiten."""
    frequenz = _rolle(tdms, zuordnung, "frequenz")
    re = _rolle(tdms, zuordnung, "re_s21")
    im = _rolle(tdms, zuordnung, "im_s21")
    feld_before = _rolle(tdms, zuordnung, "feld_before")
    feld_after = _rolle(tdms, zuordnung, "feld_after", optional=True)
    temperatur = _rolle(tdms, zuordnung, "temperatur", optional=True)

    hat_after = feld_after is not None and feld_after.size == feld_before.size
    feld_punkt = 0.5 * (feld_before + feld_after) if hat_after else feld_before
    hat_temperatur = temperatur is not None and temperatur.size == feld_before.size

    # Frequenzen gruppieren (auf 1 kHz runden gegen Float-Rauschen).
    schluessel = np.round(frequenz, -3)
    eindeutige = np.unique(schluessel)

    linescans: list[Linescan] = []
    for uf in eindeutige:
        maske = schluessel == uf
        feld = feld_punkt[maske]
        ordnung = np.argsort(feld)
        linescans.append(
            Linescan(
                frequenz=float(np.mean(frequenz[maske])),
                feld=feld[ordnung],
                re=re[maske][ordnung],
                im=im[maske][ordnung],
                feld_before=feld_before[maske][ordnung],
                feld_after=feld_after[maske][ordnung] if hat_after else None,
                temperatur=temperatur[maske][ordnung] if hat_temperatur else None,
            )
        )

    linescans.sort(key=lambda ls: ls.frequenz)
    meta = {
        "n_freq": len(linescans),
        "frequenz_start_hz": float(eindeutige.min()),
        "frequenz_stop_hz": float(eindeutige.max()),
    }
    return Messdatensatz(quelle=pfad, format_typ="sortiert", linescans=linescans, meta=meta)


# --- Import-Validierung vor Uebernahme ----------------------------------------

@dataclass
class PruefBericht:
    """Ergebnis der Import-Validierung eines frisch geladenen Datensatzes.

    ``warnungen`` enthaelt alles, was der Nutzer vor der Uebernahme sehen
    sollte; ein leerer Bericht bedeutet: unauffaellig.
    """

    n_frequenzen: int = 0
    punkte_min: int = 0
    punkte_max: int = 0
    feld_min_t: float = float("nan")
    feld_max_t: float = float("nan")
    freq_min_hz: float = float("nan")
    freq_max_hz: float = float("nan")
    nan_anteil: float = 0.0
    warnungen: list[str] = field(default_factory=list)

    @property
    def in_ordnung(self) -> bool:
        return not self.warnungen

    def als_text(self) -> str:
        """Kompakte, menschenlesbare Zusammenfassung fuer Dialog und Protokoll."""
        zeilen = [
            f"Frequenzen: {self.n_frequenzen}  "
            f"({self.freq_min_hz/1e9:.3f} – {self.freq_max_hz/1e9:.3f} GHz)",
            f"Feldpunkte je Linescan: {self.punkte_min} – {self.punkte_max}",
            f"Feldbereich: {self.feld_min_t:.4f} – {self.feld_max_t:.4f} T",
            f"NaN-Anteil im Signal: {self.nan_anteil:.2%}",
        ]
        if self.warnungen:
            zeilen.append("Warnungen:")
            zeilen.extend(f"  • {w}" for w in self.warnungen)
        else:
            zeilen.append("Keine Auffaelligkeiten.")
        return "\n".join(zeilen)


def pruefe_datensatz(datensatz: Messdatensatz) -> PruefBericht:
    """Import-Validierung: Dimensionen, Achsen-Monotonie, NaN-Anteil.

    Wird vor der Uebernahme in die Auswertung aufgerufen (verpflichtend vor
    jedem Autofit); die GUI zeigt den Bericht zusammen mit einer Daten-Vorschau.
    """
    bericht = PruefBericht(n_frequenzen=len(datensatz))
    if not datensatz.linescans:
        bericht.warnungen.append("Datensatz enthaelt keine Linescans.")
        return bericht

    groessen = [ls.feld.size for ls in datensatz.linescans]
    bericht.punkte_min = int(min(groessen))
    bericht.punkte_max = int(max(groessen))
    bericht.feld_min_t, bericht.feld_max_t = datensatz.feld_bereich()
    frequenzen = datensatz.frequenzen
    bericht.freq_min_hz = float(frequenzen.min())
    bericht.freq_max_hz = float(frequenzen.max())

    if bericht.punkte_min < 4:
        bericht.warnungen.append(
            f"Mindestens ein Linescan hat nur {bericht.punkte_min} Feldpunkte (< 4) – "
            "zu wenig fuer einen Fit."
        )

    # Frequenzachse: streng aufsteigend und ohne Doppelungen.
    if frequenzen.size > 1 and not np.all(np.diff(frequenzen) > 0):
        bericht.warnungen.append("Frequenzachse ist nicht streng aufsteigend (Doppelungen?).")

    # Feldachse je Linescan: nach dem Laden aufsteigend sortiert; ein konstantes
    # Feld (keinerlei Variation) deutet auf einen falsch zugeordneten Kanal hin.
    nicht_monoton = sum(
        1 for ls in datensatz.linescans
        if ls.feld.size > 1 and not np.all(np.diff(ls.feld) >= 0)
    )
    if nicht_monoton:
        bericht.warnungen.append(
            f"{nicht_monoton} Linescan(s) mit nicht aufsteigender Feldachse."
        )
    konstant = sum(
        1 for ls in datensatz.linescans
        if ls.feld.size > 1 and float(np.ptp(ls.feld)) == 0.0
    )
    if konstant:
        bericht.warnungen.append(
            f"{konstant} Linescan(s) mit konstantem Feld – Feldkanal richtig zugeordnet?"
        )

    # NaN-Anteil ueber Feld und Signal.
    n_werte = 0
    n_nan = 0
    for ls in datensatz.linescans:
        for arr in (ls.feld, ls.re, ls.im):
            n_werte += arr.size
            n_nan += int(np.count_nonzero(~np.isfinite(arr)))
    bericht.nan_anteil = (n_nan / n_werte) if n_werte else 0.0
    if n_nan:
        bericht.warnungen.append(
            f"{n_nan} nicht-endliche Werte (NaN/Inf) in Feld/Signal ({bericht.nan_anteil:.2%})."
        )

    return bericht

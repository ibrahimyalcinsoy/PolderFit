"""Einlesen beider TDMS-Formate (unsortiert/Rohdaten und sortiert/vorverarbeitet).

Die Format-Erkennung erfolgt anhand der vorhandenen Gruppen:

* Gruppe ``Read.PNAX``  -> unsortiertes Rohdaten-Messfile (Matrix n_feld x n_freq).
* Gruppe ``ZVB``        -> sortiertes File (variable Feldzahl je Frequenz).

Felder liegen in beiden Formaten bereits in Tesla vor, Frequenzen in Hz.
"""

from __future__ import annotations

import numpy as np
from nptdms import TdmsFile

from .datensatz import Linescan, Messdatensatz


def lade_tdms(pfad: str) -> Messdatensatz:
    """Liest eine TDMS-Datei ein und erkennt das Format automatisch."""
    tdms = TdmsFile.read(pfad)
    gruppen = {g.name for g in tdms.groups()}

    if "Read.PNAX" in gruppen:
        return _lade_unsortiert(tdms, pfad)
    if "ZVB" in gruppen:
        return _lade_sortiert(tdms, pfad)
    raise ValueError(
        f"Unbekanntes TDMS-Format in {pfad!r}: weder 'Read.PNAX' noch 'ZVB' gefunden. "
        f"Vorhandene Gruppen: {sorted(gruppen)}"
    )


def _kanal(tdms, gruppe: str, kanal: str) -> np.ndarray:
    return np.asarray(tdms[gruppe][kanal][:])


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


def _lade_unsortiert(tdms, pfad: str) -> Messdatensatz:
    """Rohdaten-Messfile: 725 Feldwerte x 1001 Frequenzpunkte (reshape statt Schleife)."""
    frequenz = _kanal(tdms, "Read.PNAX", "Frequency")
    re = _kanal(tdms, "Read.PNAX", "REALS21")
    im = _kanal(tdms, "Read.PNAX", "IMAGinaryS21")

    feld_before = _kanal(tdms, "Read.Fieldbefore", "IPS X-Field")
    feld_after = _kanal(tdms, "Read.Fieldafter", "IPS X-Field")
    n_feld = feld_before.size

    # Temperatur (je Feldwert) optional – frueh laden, damit ein evtl. mitten im
    # Sweep "geflushtes" File (siehe unten) auch die Temperaturspur korrekt kuerzt.
    temperatur = None
    try:
        temperatur = _kanal(tdms, "Read.Temperature", "LakeshoreTemperature")
    except KeyError:
        temperatur = None

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


def _lade_sortiert(tdms, pfad: str) -> Messdatensatz:
    """Sortiertes File: Punktzahl je Frequenz NICHT konstant – aus Daten ableiten."""
    frequenz = _kanal(tdms, "ZVB", "frequency")
    re = _kanal(tdms, "ZVB", "ReS21")
    im = _kanal(tdms, "ZVB", "ImS21")
    feld_before = _kanal(tdms, "Field", "Field-before")
    feld_after = _kanal(tdms, "Field", "Field-after")

    feld_punkt = 0.5 * (feld_before + feld_after)

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
                feld_after=feld_after[maske][ordnung],
                temperatur=None,
            )
        )

    linescans.sort(key=lambda ls: ls.frequenz)
    meta = {
        "n_freq": len(linescans),
        "frequenz_start_hz": float(eindeutige.min()),
        "frequenz_stop_hz": float(eindeutige.max()),
    }
    return Messdatensatz(quelle=pfad, format_typ="sortiert", linescans=linescans, meta=meta)

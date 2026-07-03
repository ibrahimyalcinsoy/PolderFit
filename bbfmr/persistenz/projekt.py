"""Sitzungszustand speichern/laden (Projektdatei) als JSON.

Erlaubt das Fortsetzen einer Auswertung: gespeichert werden Quelle,
Kanal-Zuordnung, Auswertungsauswahl (Jumper/Bereiche), Gamma, Fenstergrenzen
je Frequenz, Ausschlusszonen, Ausreisser-Markierungen und die wichtigsten
Fitparameter. Die Rohdaten werden nicht dupliziert, sondern beim Laden erneut
aus der TDMS-Quelle gelesen; die Fits werden mit den gespeicherten Fenstern
deterministisch neu gerechnet.

Format-Version 2 (Version 1 ohne Zuordnung/Zonen/Ausreisser wird beim Laden
weiterhin akzeptiert).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..fit.batch import Ausschlusszone, StapelErgebnis
from ..physik.konstanten import GAMMA_STANDARD


def _zahl(x):
    if x is None:
        return None
    if isinstance(x, (np.floating, np.integer)):
        return float(x)
    if isinstance(x, float) and np.isnan(x):
        return None
    return x


def speichere_sitzung(stapel: StapelErgebnis, pfad: str) -> None:
    """Serialisiert den Stapelzustand nach JSON (UTF-8)."""
    meta = stapel.datensatz.meta
    daten = {
        "bbfmr_projekt_version": 2,
        "quelle": stapel.datensatz.quelle,
        "format_typ": stapel.datensatz.format_typ,
        "zuordnung": meta.get("zuordnung"),
        "mapping_profil": meta.get("mapping_profil"),
        "auswertungsauswahl": meta.get("auswertungsauswahl"),
        "gamma": stapel.gamma,
        "r2_schwelle": stapel.r2_schwelle,
        "fenster": [[float(u), float(o)] for (u, o) in stapel.fenster],
        "ausschlusszonen": [z.als_dict() for z in stapel.ausschlusszonen],
        "ausreisser": [int(i) for i in stapel.ausreisser],
        "ergebnisse": [
            {k: _zahl(v) for k, v in e.als_zeile().items()} for e in stapel.ergebnisse
        ],
    }
    Path(pfad).write_text(
        json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def lade_sitzung(pfad: str) -> dict:
    """Laedt einen gespeicherten Sitzungszustand (rohes dict).

    Die TDMS-Quelle (``daten['quelle']``) wird vom Aufrufer erneut eingelesen;
    :func:`stelle_stapel_wieder_her` baut daraus den Stapel auf.
    """
    return json.loads(Path(pfad).read_text(encoding="utf-8"))


def stelle_stapel_wieder_her(daten: dict, datensatz, fortschritt=None) -> StapelErgebnis:
    """Baut den Stapel aus Sitzungsdaten + frisch geladenem Datensatz wieder auf.

    ``datensatz`` muss bereits gemappt und (falls die Sitzung eine
    Auswertungsauswahl enthielt) identisch reduziert sein - die Fensterliste
    der Sitzung muss zur Linescan-Anzahl passen. Alle Linescans werden mit den
    gespeicherten Fenstern (und aktiven Ausschlusszonen) deterministisch neu
    gefittet; anschliessend werden die Ausreisser-Markierungen uebernommen.
    """
    from ..fit.batch import fitte_neu  # spaeter Import vermeidet Zyklen

    fenster = [tuple(f) for f in daten.get("fenster", [])]
    if len(fenster) != len(datensatz.linescans):
        raise ValueError(
            f"Sitzung passt nicht zum Datensatz: {len(fenster)} Fenster fuer "
            f"{len(datensatz.linescans)} Linescans. Wurde die Datei mit einer "
            f"anderen Auswertungsauswahl geladen?")

    stapel = StapelErgebnis(
        datensatz=datensatz,
        gamma=float(daten.get("gamma", GAMMA_STANDARD)),
        r2_schwelle=float(daten.get("r2_schwelle", 0.9)),
        fenster=fenster,
        ausschlusszonen=[Ausschlusszone.aus_dict(z)
                         for z in daten.get("ausschlusszonen", [])],
    )
    # Platzhalter, damit fitte_neu(index) die Listen fuellen kann.
    stapel.ergebnisse = [None] * len(fenster)
    stapel.zugeschnitten = [None] * len(fenster)
    gespeicherte = daten.get("ergebnisse", [])
    for i in range(len(fenster)):
        ergebnis = fitte_neu(stapel, i)
        # fitte_neu markiert nachbearbeitet - beim Wiederherstellen zaehlt
        # aber der GESPEICHERTE Bearbeitungsstand, nicht der Neuaufbau.
        if i < len(gespeicherte):
            ergebnis.nachbearbeitet = bool(gespeicherte[i].get("nachbearbeitet", False))
        else:
            ergebnis.nachbearbeitet = False
        if fortschritt is not None:
            fortschritt(i + 1, len(fenster), ergebnis)

    n = len(fenster)
    stapel.ausreisser = sorted(
        int(i) for i in daten.get("ausreisser", []) if 0 <= int(i) < n)
    return stapel

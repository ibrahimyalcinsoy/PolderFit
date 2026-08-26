# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Sitzungszustand speichern/laden (Projektdatei) als JSON.

Erlaubt das Fortsetzen einer Auswertung: gespeichert werden Quelle,
Kanal-Zuordnung, Auswertungsauswahl (Jumper/Bereiche), Gamma, Fenstergrenzen
je Frequenz, Ausschlusszonen, Ausreisser-Markierungen und die wichtigsten
Fitparameter. Die Rohdaten werden nicht dupliziert, sondern beim Laden erneut
aus der TDMS-Quelle gelesen; die Fits werden mit den gespeicherten Fenstern
deterministisch neu gerechnet.

Format-Version 3: zusaetzlich physikalische Parameter, Verarbeitungskette des
Farbplots, Grenzgeraden, Nutzer-Bewertung je Fit ("bestaetigt"/"verworfen"),
Platzhalter (nicht gefittete Frequenzen) und Modenanzahl je Fit. Versionen 1
und 2 werden weiterhin gelesen.

Bewusst NICHT gespeichert: Zoom-Ausschnitt, Fenster-/Dock-Layout oder
Achsengeometrie - ein verklemmtes Layout darf nie in eine Datei wandern.
"""

from __future__ import annotations

from .. import PROGRAMMNAME

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from ..fit.batch import NACHFENSTER_FAKTOR_STANDARD, Ausschlusszone, StapelErgebnis
from ..fit.kriterien import ALPHA_MAX
from ..fit.linescan_fit import BEWERTUNGEN, FitErgebnis
from ..physik.konstanten import GAMMA_STANDARD

PROJEKT_VERSION = 3


def _zahl(x):
    if x is None:
        return None
    if isinstance(x, (np.floating, np.integer)):
        return float(x)
    if isinstance(x, float) and np.isnan(x):
        return None
    return x


def sitzung_als_dict(stapel: StapelErgebnis, physik: dict | None = None,
                     verarbeitung: dict | None = None,
                     grenzgeraden: list | None = None) -> dict:
    """Serialisierbarer Sitzungszustand (siehe Modulkopf).

    ``physik``: ``PhysikParameter.als_dict()``; ``verarbeitung``:
    ``Verarbeitungskette.als_dict()``; ``grenzgeraden``: Liste von
    :class:`~polderfit.fit.fenster_steuerung.Grenzgerade`.
    """
    meta = stapel.datensatz.meta
    return {
        "polderfit_projekt_version": PROJEKT_VERSION,
        "programm": PROGRAMMNAME,
        "quelle": stapel.datensatz.quelle,
        "format_typ": stapel.datensatz.format_typ,
        "zuordnung": meta.get("zuordnung"),
        "mapping_profil": meta.get("mapping_profil"),
        "auswertungsauswahl": meta.get("auswertungsauswahl"),
        "gamma": stapel.gamma,
        "r2_schwelle": stapel.r2_schwelle,
        "alpha_max": stapel.alpha_max,
        "alpha_plausibel": stapel.alpha_plausibel,
        "nachfenster_faktor": stapel.nachfenster_faktor,
        "n_moden": int(stapel.n_moden),
        "nachfit_bestaetigen": bool(stapel.nachfit_bestaetigen),
        "physik": dict(physik) if physik else None,
        "verarbeitung": dict(verarbeitung) if verarbeitung else None,
        "grenzgeraden": [asdict(g) for g in (grenzgeraden or [])],
        "fenster": [[float(u), float(o)] for (u, o) in stapel.fenster],
        "ausschlusszonen": [z.als_dict() for z in stapel.ausschlusszonen],
        "ausreisser": [int(i) for i in stapel.ausreisser],
        "ergebnisse": [
            {k: _zahl(v) for k, v in e.als_zeile(hauptmode_nur=True).items()}
            for e in stapel.ergebnisse
        ],
    }


def speichere_sitzung(stapel: StapelErgebnis, pfad: str, physik: dict | None = None,
                      verarbeitung: dict | None = None,
                      grenzgeraden: list | None = None) -> None:
    """Serialisiert den Stapelzustand nach JSON (UTF-8); atomar (erst .tmp)."""
    daten = sitzung_als_dict(stapel, physik=physik, verarbeitung=verarbeitung,
                             grenzgeraden=grenzgeraden)
    ziel = Path(pfad)
    tmp = ziel.with_name(ziel.name + ".tmp")
    tmp.write_text(json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(ziel)


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

    alpha_plausibel = daten.get("alpha_plausibel")
    stapel = StapelErgebnis(
        datensatz=datensatz,
        gamma=float(daten.get("gamma", GAMMA_STANDARD)),
        r2_schwelle=float(daten.get("r2_schwelle", 0.9)),
        alpha_max=float(daten.get("alpha_max", ALPHA_MAX)),
        alpha_plausibel=(float(alpha_plausibel) if alpha_plausibel else None),
        nachfenster_faktor=float(daten.get("nachfenster_faktor",
                                           NACHFENSTER_FAKTOR_STANDARD)),
        n_moden=max(1, int(daten.get("n_moden", 1))),
        nachfit_bestaetigen=bool(daten.get("nachfit_bestaetigen", True)),
        fenster=fenster,
        ausschlusszonen=[Ausschlusszone.aus_dict(z)
                         for z in daten.get("ausschlusszonen", [])],
    )
    # Platzhalter, damit fitte_neu(index) die Listen fuellen kann.
    stapel.ergebnisse = [None] * len(fenster)
    stapel.zugeschnitten = [None] * len(fenster)
    gespeicherte = daten.get("ergebnisse", [])
    for i in range(len(fenster)):
        zeile = gespeicherte[i] if i < len(gespeicherte) else {}
        if zeile and not zeile.get("gefittet", True):
            # Nie gefittete Frequenz (z. B. ausserhalb der Grenzgeraden) bleibt Platzhalter.
            ls = datensatz.linescans[i]
            stapel.zugeschnitten[i] = ls
            ergebnis = FitErgebnis.platzhalter(ls.frequenz, ls.feld)
            stapel.ergebnisse[i] = ergebnis
        else:
            n_moden = zeile.get("n_moden") if zeile else None
            ergebnis = fitte_neu(stapel, i, bestaetigen=False,
                                 n_moden=(int(n_moden) if n_moden else None))
            # fitte_neu markiert nachbearbeitet - beim Wiederherstellen zaehlt
            # aber der GESPEICHERTE Bearbeitungsstand, nicht der Neuaufbau.
            ergebnis.nachbearbeitet = bool(zeile.get("nachbearbeitet", False)) if zeile else False
            bewertung = zeile.get("bewertung", "auto") if zeile else "auto"
            if bewertung in BEWERTUNGEN and bewertung != "auto":
                ergebnis = stapel.bewerte(i, bewertung)
        if fortschritt is not None:
            fortschritt(i + 1, len(fenster), ergebnis)

    n = len(fenster)
    stapel.ausreisser = sorted(
        int(i) for i in daten.get("ausreisser", []) if 0 <= int(i) < n)
    return stapel


def grenzgeraden_aus_sitzung(daten: dict) -> list:
    """Grenzgeraden einer Sitzung (Version >= 3) als Objekte; sonst ``[]``."""
    from ..fit.fenster_steuerung import Grenzgerade  # spaeter Import vermeidet Zyklen
    geraden = []
    for g in daten.get("grenzgeraden", []) or []:
        try:
            geraden.append(Grenzgerade(b1=float(g["b1"]), f1=float(g["f1"]),
                                       b2=float(g["b2"]), f2=float(g["f2"]),
                                       gruen_positiv=bool(g.get("gruen_positiv", True)),
                                       mode=max(1, int(g.get("mode", 1)))))
        except (KeyError, TypeError, ValueError):
            continue
    return geraden

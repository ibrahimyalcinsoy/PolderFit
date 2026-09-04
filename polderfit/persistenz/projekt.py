# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Sitzungszustand speichern/laden (Projektdatei) als JSON.

Erlaubt das Fortsetzen einer Auswertung: gespeichert werden Quelle,
Kanal-Zuordnung, Auswertungsauswahl (Jumper/Bereiche), Gamma, Fenstergrenzen
je Frequenz, Ausschlusszonen, Ausreisser-Markierungen und die wichtigsten
Fitparameter. Die Rohdaten werden nicht dupliziert, sondern beim Laden erneut
aus der TDMS-Quelle gelesen; die Fits werden mit den gespeicherten Fenstern
deterministisch neu gerechnet.

Format-Version 4: Korridore je Mode (:mod:`polderfit.fit.korridor`) und die
Ergebnisse weiterer Moden (``nebenmoden``); Version 3 (Grenzgeraden, Modenzahl
je Fit) wird beim Laden in Korridore migriert, Versionen 1 und 2 werden
weiterhin gelesen.

Bewusst NICHT gespeichert: Zoom-Ausschnitt, Fenster-/Dock-Layout oder
Achsengeometrie - ein verklemmtes Layout darf nie in eine Datei wandern.
"""

from __future__ import annotations

from .. import PROGRAMMNAME

import json
from pathlib import Path

import numpy as np

from ..fit.batch import NACHFENSTER_FAKTOR_STANDARD, Ausschlusszone, StapelErgebnis
from ..fit.korridor import Anker, Korridor, korridore_aus_grenzgeraden
from ..fit.kriterien import ALPHA_MAX
from ..fit.linescan_fit import BEWERTUNGEN, FitErgebnis
from ..physik.konstanten import GAMMA_STANDARD

PROJEKT_VERSION = 5


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
                     korridore: list | None = None) -> dict:
    """Serialisierbarer Sitzungszustand (siehe Modulkopf).

    ``physik``: ``PhysikParameter.als_dict()``; ``verarbeitung``:
    ``Verarbeitungskette.als_dict()``; ``korridore``: Liste von
    :class:`~polderfit.fit.korridor.Korridor`.
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
        "nachfit_bestaetigen": bool(stapel.nachfit_bestaetigen),
        "auto_n_dips": int(getattr(stapel, "auto_n_dips", 1)),
        "auto_dips_auto": bool(getattr(stapel, "auto_dips_auto", False)),
        "physik": dict(physik) if physik else None,
        "verarbeitung": dict(verarbeitung) if verarbeitung else None,
        "korridore": [k.als_dict() for k in (korridore or [])],
        "fenster": [[float(u), float(o)] for (u, o) in stapel.fenster],
        "ausschlusszonen": [z.als_dict() for z in stapel.ausschlusszonen],
        "ausreisser": [int(i) for i in stapel.ausreisser],
        "ausreisser_moden": [[int(i), int(k)] for i, k in stapel.ausreisser_moden],
        "ergebnisse": [
            {k: _zahl(v) for k, v in e.als_zeile().items()}
            for e in stapel.ergebnisse
        ],
        "nebenmoden": {
            str(mode): [{k: _zahl(v) for k, v in e.als_zeile().items()} for e in liste]
            for mode, liste in sorted(stapel.nebenmoden.items())
            if any(e.gefittet for e in liste)
        },
    }


def speichere_sitzung(stapel: StapelErgebnis, pfad: str, physik: dict | None = None,
                      verarbeitung: dict | None = None,
                      korridore: list | None = None) -> None:
    """Serialisiert den Stapelzustand nach JSON (UTF-8); atomar (erst .tmp)."""
    daten = sitzung_als_dict(stapel, physik=physik, verarbeitung=verarbeitung,
                             korridore=korridore)
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


def stelle_stapel_wieder_her(daten: dict, datensatz, fortschritt=None,
                             korridore: list | None = None) -> StapelErgebnis:
    """Baut den Stapel aus Sitzungsdaten + frisch geladenem Datensatz wieder auf.

    ``datensatz`` muss bereits gemappt und (falls die Sitzung eine
    Auswertungsauswahl enthielt) identisch reduziert sein - die Fensterliste
    der Sitzung muss zur Linescan-Anzahl passen. Alle Linescans werden mit den
    gespeicherten Fenstern (und aktiven Ausschlusszonen) deterministisch neu
    gefittet; weitere Moden (``nebenmoden``) je Frequenz in ihrem Korridor
    (``korridore``; sonst mit dem gespeicherten Fenster der Mode);
    anschliessend werden die Ausreisser-Markierungen uebernommen.
    """
    from ..fit.batch import fitte_mode, fitte_neu  # spaeter Import vermeidet Zyklen

    fenster = [tuple(f) for f in daten.get("fenster", [])]
    if len(fenster) != len(datensatz.linescans) and int(daten.get("polderfit_projekt_version", 0)) < 5:
        daten = _auf_volles_gitter(daten, datensatz)
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
        nachfit_bestaetigen=bool(daten.get("nachfit_bestaetigen", True)),
        auto_n_dips=max(1, int(daten.get("auto_n_dips", 1))),
        auto_dips_auto=bool(daten.get("auto_dips_auto", False)),
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
            ergebnis = fitte_neu(stapel, i, bestaetigen=False)
            # fitte_neu markiert nachbearbeitet - beim Wiederherstellen zaehlt
            # aber der GESPEICHERTE Bearbeitungsstand, nicht der Neuaufbau.
            ergebnis.nachbearbeitet = bool(zeile.get("nachbearbeitet", False)) if zeile else False
            bewertung = zeile.get("bewertung", "auto") if zeile else "auto"
            if bewertung in BEWERTUNGEN and bewertung != "auto":
                ergebnis = stapel.bewerte(i, bewertung)
        if fortschritt is not None:
            fortschritt(i + 1, len(fenster), ergebnis)

    # Auto-Fit mit mehreren Dips je Fenster (ohne Korridor fuer Mode 1): dieselbe
    # Kette wie beim Auto-Fit nachbauen (Temp-Korridor = gespeichertes Fenster).
    bereits = set()
    korridor_je_mode = {int(m): k for k in (korridore or []) for m in k.moden}
    if stapel.auto_n_dips > 1 and 1 not in korridor_je_mode:
        n_d = int(stapel.auto_n_dips)
        for i, ls in enumerate(datensatz.linescans):
            e = stapel.ergebnisse[i]
            if not (e is not None and e.gefittet) or not ls.feld.size:
                continue
            tmp = Korridor(mode=1, n_dips=n_d, moden=list(range(1, n_d + 1)), methode="summe",
                           dips_auto=bool(stapel.auto_dips_auto),
                           anker=[Anker(ls.frequenz, float(fenster[i][0]), float(fenster[i][1]))])
            fitte_mode(stapel, i, tmp, bestaetigen=False)
            for m in range(1, n_d + 1):
                bereits.add((m, i))
        # Bewertungen der Mode 1 erneut anwenden (fitte_mode hat neu gefittet).
        for i in range(len(fenster)):
            zeile = gespeicherte[i] if i < len(gespeicherte) else {}
            bewertung = zeile.get("bewertung", "auto") if zeile else "auto"
            if zeile and zeile.get("gefittet", True) and bewertung in BEWERTUNGEN and bewertung != "auto":
                stapel.bewerte(i, bewertung)
    # Weitere Moden: je Frequenz im Korridor der Mode (sonst gespeichertes Fenster).
    for mode_text, zeilen in (daten.get("nebenmoden") or {}).items():
        try:
            mode = int(mode_text)
        except (TypeError, ValueError):
            continue
        if mode < 2 or len(zeilen) != len(fenster):
            continue
        liste = stapel.ergebnisse_mode(mode)
        korridor = korridor_je_mode.get(mode)
        for i, zeile in enumerate(zeilen):
            if not zeile or not zeile.get("gefittet", True):
                continue
            if (mode, i) in bereits:
                ergebnis = liste[i]
                if ergebnis.gefittet:
                    bewertung = zeile.get("bewertung", "auto")
                    if bewertung in BEWERTUNGEN and bewertung != "auto":
                        liste[i] = stapel.bewerte(i, bewertung, mode=mode)
                continue
            ergebnis = None
            if korridor is not None and (id(korridor), i) not in bereits:
                bereits.add((id(korridor), i))
                fitte_mode(stapel, i, korridor, bestaetigen=False)   # fittet alle Dips
                ergebnis = liste[i] if liste[i].gefittet else None
            elif korridor is not None:
                ergebnis = liste[i] if liste[i].gefittet else None
            if ergebnis is None:
                lo, hi = zeile.get("B_fenster_min_T"), zeile.get("B_fenster_max_T")
                if lo is None or hi is None:
                    continue
                ergebnis = fitte_neu(stapel, i, feld_unten=float(lo), feld_oben=float(hi),
                                     bestaetigen=False, mode=mode)
            ergebnis.nachbearbeitet = bool(zeile.get("nachbearbeitet", False))
            bewertung = zeile.get("bewertung", "auto")
            if bewertung in BEWERTUNGEN and bewertung != "auto":
                liste[i] = stapel.bewerte(i, bewertung, mode=mode)

    n = len(fenster)
    stapel.ausreisser = sorted(
        int(i) for i in daten.get("ausreisser", []) if 0 <= int(i) < n)
    stapel.ausreisser_moden = sorted(
        (int(i), int(k)) for i, k in daten.get("ausreisser_moden", [])
        if 0 <= int(i) < n and int(k) >= 1)
    return stapel


def _auf_volles_gitter(daten: dict, datensatz) -> dict:
    """Projekte aus Staenden mit REDUZIERTEM Stapel (Jumper: nur jede n-te
    Frequenz im Stapel) auf das volle Frequenzgitter heben: gespeicherte
    Eintraege wandern an ihre Original-Indizes, der Rest wird Platzhalter."""
    from ..fit.auswahl import Auswertungsauswahl
    auswahl_dict = daten.get("auswertungsauswahl")
    if not auswahl_dict:
        return daten
    try:
        auswahl = Auswertungsauswahl.aus_dict(auswahl_dict)
    except Exception:
        return daten
    n = len(datensatz.linescans)
    alt = [tuple(f) for f in daten.get("fenster", [])]
    # Frueheres (relatives) Jumper-Schema: Bereich, dann jeder n-te Eintrag.
    frequenzen = datensatz.frequenzen
    maske = np.ones(frequenzen.size, dtype=bool)
    if auswahl.frequenz_min_hz is not None:
        maske &= frequenzen >= auswahl.frequenz_min_hz
    if auswahl.frequenz_max_hz is not None:
        maske &= frequenzen <= auswahl.frequenz_max_hz
    for lo, hi in auswahl.frequenz_ausschluss:
        maske &= ~((frequenzen >= lo) & (frequenzen <= hi))
    quell = np.flatnonzero(maske)[:: auswahl.n_frequenz]
    if len(quell) != len(alt):
        return daten
    neu = dict(daten)
    voll_f = [[float(ls.feld.min()), float(ls.feld.max())] if ls.feld.size else [0.0, 0.0]
              for ls in datensatz.linescans]
    voll_e = [{"gefittet": False} for _ in range(n)]
    for k, i in enumerate(quell):
        voll_f[int(i)] = list(alt[k])
        zeilen = daten.get("ergebnisse", [])
        if k < len(zeilen):
            voll_e[int(i)] = zeilen[k]
    neu["fenster"] = voll_f
    neu["ergebnisse"] = voll_e
    abbildung = {k: int(i) for k, i in enumerate(quell)}
    neu["ausreisser"] = [abbildung[int(i)] for i in daten.get("ausreisser", []) if int(i) in abbildung]
    neu["ausreisser_moden"] = [[abbildung[int(i)], int(m)] for i, m in daten.get("ausreisser_moden", [])
                               if int(i) in abbildung]
    nebenmoden = {}
    for mode, zeilen in (daten.get("nebenmoden") or {}).items():
        voll = [{"gefittet": False} for _ in range(n)]
        for k, i in enumerate(quell):
            if k < len(zeilen):
                voll[int(i)] = zeilen[k]
        nebenmoden[mode] = voll
    neu["nebenmoden"] = nebenmoden
    return neu


def korridore_aus_sitzung(daten: dict, feld_min: float = -1e6,
                          feld_max: float = 1e6) -> list:
    """Korridore einer Sitzung: Version >= 4 direkt, Version 3 (Grenzgeraden je
    Mode) migriert ueber :func:`korridore_aus_grenzgeraden`; sonst ``[]``."""
    korridore = []
    for k in daten.get("korridore", []) or []:
        try:
            korridore.append(Korridor.aus_dict(k))
        except (KeyError, TypeError, ValueError):
            continue
    if korridore:
        return korridore
    geraden = daten.get("grenzgeraden", []) or []
    if geraden:
        try:
            return korridore_aus_grenzgeraden(geraden, feld_min, feld_max)
        except (KeyError, TypeError, ValueError):
            return []
    return []

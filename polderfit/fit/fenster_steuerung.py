# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Gezieltes Neu-Fitten von Teilbereichen der 2D-Karte (Fenster-Steuerung).

Grundlage fuer das manuelle Moden-Fitting: Der Nutzer markiert im Farbplot
ein Rechteck (Feld x Frequenz), und NUR dort wird die Fenstersuche und der
Fit wiederholt. Zweck: Mehrdeutigkeiten aufloesen - liegen zwei aehnlich
starke Signale im Sweep (echte Mode auf der Kittel-Geraden vs. Stoermode/
Artefakt daneben), zwingt die Rechteck-Einschraenkung Fenstersuche UND
Resonanzfeld ``B_res`` in den markierten Bereich. Ergebnisse ausserhalb des
Rechtecks bleiben unangetastet.

Dieses Modul ist die gemeinsame Basis fuer das Rechteck-Nachfitten
(Aufgabenbereich 3) und wird vom interaktiven In-Plot-Fitting
(Aufgabenbereich 5) weiterverwendet.
"""

from __future__ import annotations

import numpy as np

from .autowindows import auto_fenster_intervalle
from .batch import Ausschlusszone, StapelErgebnis, fitte_mode, fitte_neu, nachfenster
from .korridor import Korridor

#: Gueltige Modi fuer das Ueberschreib-Verhalten beim Neu-Fitten.
MODI = ("ueberschreiben", "ergaenzen")


def _pruefe_modus(modus: str) -> None:
    if modus not in MODI:
        raise ValueError(f"Unbekannter Modus {modus!r} (erlaubt: {MODI}). "
                         "'ueberschreiben' ersetzt alle betroffenen Fits, "
                         "'ergaenzen' nur die als problematisch markierten.")


def dispersions_zentren(stapel: StapelErgebnis) -> np.ndarray:
    """Robuste lineare Trasse ``B(f)`` durch die aktuellen Resonanzfelder.

    Die Resonanz liegt (Kittel) in guter Naeherung auf einer Geraden
    ``B_res(f) = a + b*f``. Die Trasse wird per Ausgleichsgerade durch die
    NICHT problematischen Fits gelegt; Ausreisser (> 3 sigma des Residuums)
    werden in einem zweiten Durchgang entfernt. Rueckfaelle: Median der guten
    Fits (zu wenige Punkte fuer eine Gerade) bzw. die aktuellen Fenstermitten
    (noch gar keine Fits).

    Diese Zentren sind der Anker fuer alle "mitwandernden" Fenster: Grenzen
    werden als Offsets RELATIV zu dieser Geraden gefuehrt, nie als feste
    Feldwerte oder Punktindizes.
    """
    frequenzen = stapel.datensatz.frequenzen
    if stapel.ergebnisse:
        gute = np.array([i for i, e in enumerate(stapel.ergebnisse)
                         if not e.problematisch and np.isfinite(e.B_res)], dtype=int)
        if gute.size >= 2:
            f, b = frequenzen[gute], np.array([stapel.ergebnisse[i].B_res for i in gute])
            koeff = np.polyfit(f, b, 1)
            residuum = b - np.polyval(koeff, f)
            streuung = float(np.std(residuum)) or 1e-12
            kern = np.abs(residuum) <= 3.0 * streuung
            if kern.sum() >= 2:
                koeff = np.polyfit(f[kern], b[kern], 1)
            return np.polyval(koeff, frequenzen)
        if gute.size == 1:
            return np.full(frequenzen.size, stapel.ergebnisse[int(gute[0])].B_res)
        alle_bres = np.array([e.B_res for e in stapel.ergebnisse if np.isfinite(e.B_res)])
        if alle_bres.size:
            return np.full(frequenzen.size, float(np.median(alle_bres)))
    if stapel.fenster:
        return np.array([0.5 * (u + o) for u, o in stapel.fenster])
    raise ValueError("Keine Fits und keine Fenster vorhanden - Trasse nicht bestimmbar.")


def setze_fensterbreite_punkte(
    stapel: StapelErgebnis,
    breite_punkte: int,
    indizes: list[int] | None = None,
    zentren: np.ndarray | None = None,
    modus: str = "ueberschreiben",
    fortschritt=None,
) -> list[int]:
    """Setzt die Fensterbreite explizit in PUNKTEN und fittet neu.

    Fenster = Trassen-Zentrum +/- (breite_punkte/2) * lokale Feldschrittweite
    des jeweiligen Linescans. Das ist der explizite Nutzer-Hebel gegen zu enge
    Automatik-Fenster ("aktuell 15 Punkte -> auf 25 stellen"); die Automatik
    ueberstimmt diese Wahl nie stillschweigend - sie gilt, bis der Nutzer
    erneut eingreift oder einen neuen Auto-Fit startet.
    """
    _pruefe_modus(modus)
    breite_punkte = int(breite_punkte)
    if breite_punkte < 4:
        raise ValueError(f"breite_punkte muss >= 4 sein (erhalten: {breite_punkte}).")
    if zentren is None:
        zentren = dispersions_zentren(stapel)
    if indizes is None:
        indizes = list(range(len(stapel.datensatz.linescans)))

    neu_gefittet: list[int] = []
    for k, i in enumerate(indizes):
        if modus == "ergaenzen" and stapel.ergebnisse and not stapel.ergebnisse[i].problematisch:
            continue
        ls = stapel.datensatz.linescans[i]
        if ls.feld.size < 2:
            continue
        schritt = float(np.ptp(ls.feld)) / max(ls.feld.size - 1, 1)
        halb = 0.5 * breite_punkte * schritt
        ergebnis = fitte_neu(stapel, i,
                             feld_unten=float(zentren[i] - halb),
                             feld_oben=float(zentren[i] + halb))
        neu_gefittet.append(i)
        if fortschritt is not None:
            fortschritt(k + 1, len(indizes), ergebnis)
    return neu_gefittet


def propagiere_grenzen(
    stapel: StapelErgebnis,
    ab_index: int,
    offset_links: float,
    offset_rechts: float,
    zentren: np.ndarray | None = None,
    modus: str = "ueberschreiben",
    fortschritt=None,
) -> list[int]:
    """Uebernimmt manuell gesetzte Grenzen fuer alle folgenden Linescans.

    ``offset_links``/``offset_rechts`` sind die Grenzabstaende (Tesla, links
    negativ) RELATIV zum Trassen-Zentrum - typisch aus einer von Hand
    gezogenen Grenze bestimmt: ``offset = grenze - zentrum[i]``. Weil die
    Offsets relativ zur (linearen) Dispersion gefuehrt werden, wandert das
    Fenster fuer jede folgende Frequenz mit der Resonanz mit, statt an festen
    Feldwerten zu kleben. Alle Linescans ab ``ab_index`` werden neu gefittet
    (``modus='ergaenzen'``: nur die problematischen).
    """
    _pruefe_modus(modus)
    if offset_rechts <= offset_links:
        raise ValueError(
            f"offset_rechts ({offset_rechts:+.4f} T) muss groesser als "
            f"offset_links ({offset_links:+.4f} T) sein.")
    if zentren is None:
        zentren = dispersions_zentren(stapel)

    n = len(stapel.datensatz.linescans)
    indizes = list(range(max(0, int(ab_index)), n))
    neu_gefittet: list[int] = []
    for k, i in enumerate(indizes):
        if modus == "ergaenzen" and stapel.ergebnisse and not stapel.ergebnisse[i].problematisch:
            continue
        ergebnis = fitte_neu(stapel, i,
                             feld_unten=float(zentren[i] + offset_links),
                             feld_oben=float(zentren[i] + offset_rechts))
        neu_gefittet.append(i)
        if fortschritt is not None:
            fortschritt(k + 1, len(indizes), ergebnis)
    return neu_gefittet


def fuege_ausschlusszone_hinzu(
    stapel: StapelErgebnis,
    zone: Ausschlusszone,
    fortschritt=None,
) -> list[int]:
    """Haengt eine Ausschlusszone an und fittet alle betroffenen Linescans neu.

    Die Zone wirkt danach auf ALLE weiteren Nachfits dieses Stapels
    (:func:`polderfit.fit.batch.ohne_ausschlusszonen` in ``fitte_neu``).
    """
    stapel.ausschlusszonen.append(zone)
    return _fitte_zonen_band(stapel, zone, fortschritt)


def entferne_ausschlusszone(
    stapel: StapelErgebnis,
    zonen_index: int,
    fortschritt=None,
) -> list[int]:
    """Entfernt eine Zone und fittet die zuvor betroffenen Linescans neu."""
    zone = stapel.ausschlusszonen.pop(zonen_index)
    return _fitte_zonen_band(stapel, zone, fortschritt)


def _fitte_zonen_band(stapel: StapelErgebnis, zone: Ausschlusszone,
                      fortschritt=None) -> list[int]:
    """Fittet alle Linescans im Frequenzband einer Zone mit bestehendem Fenster neu."""
    if not stapel.ergebnisse:
        return []
    frequenzen = stapel.datensatz.frequenzen
    betroffen = [int(i) for i in np.flatnonzero(
        (frequenzen >= zone.frequenz_min) & (frequenzen <= zone.frequenz_max))
        if stapel.ergebnisse[int(i)].gefittet]   # Platzhalter bleiben ungefittet
    for k, i in enumerate(betroffen):
        # Bestehendes Fenster, neue Punktmaske. Keine Nutzer-Freigabe: die
        # Zone maskiert nur Punkte, der Nutzer hat den Fit nicht geprueft.
        ergebnis = fitte_neu(stapel, i, bestaetigen=False)
        if fortschritt is not None:
            fortschritt(k + 1, len(betroffen), ergebnis)
    return betroffen


def fitte_bereich(
    stapel: StapelErgebnis,
    feld_min: float,
    feld_max: float,
    frequenz_min: float,
    frequenz_max: float,
    breite_faktor: float = 8.0,
    modus: str = "ueberschreiben",
    breite_punkte: int | None = None,
    fortschritt=None,
    abbruch=None,
) -> tuple[list[int], list[int]]:
    """Fittet alle Linescans im Rechteck (Feld x Frequenz) neu.

    Ablauf je betroffener Frequenz:

    1. Linescan auf den Feldbereich des Rechtecks beschneiden.
    2. Fenstersuche NUR in diesem Ausschnitt (:func:`auto_fenster`) - das
       gefundene Fenster liegt damit garantiert im Rechteck.
    3. Neu fitten (:func:`fitte_neu`): ueberschreibt Fenster, Beschnitt und
       Ergebnis an diesem Index; ``B_res`` ist durch die Fit-Schranken ans
       Fenster (und damit ans Rechteck) gebunden. Der Fit wird als
       ``nachbearbeitet`` markiert.

    Frequenzen, deren Linescan im Rechteck weniger als 4 Feldpunkte hat,
    werden uebersprungen (unveraendert). ``modus='ergaenzen'`` ueberschreibt
    nur die als problematisch markierten Fits - bereits gute Ergebnisse
    anderer Bereiche bleiben unangetastet (waehlbar: ueberschreiben vs.
    hinzufuegen). ``breite_punkte`` (optional) erzwingt eine feste
    Fensterbreite in Feldpunkten um das gefundene Fensterzentrum (ans
    Rechteck geklemmt) - der explizite Nutzer-Hebel gegen zu enge
    Automatik-Fenster, jetzt direkt am Bereichs-Fit. ``fortschritt(k, n,
    ergebnis)`` ist ein optionaler GUI-Callback.

    Liefert ``(neu_gefittet, uebersprungen)`` - Listen von Stapel-Indizes.
    """
    if feld_max < feld_min:
        feld_min, feld_max = feld_max, feld_min
    if frequenz_max < frequenz_min:
        frequenz_min, frequenz_max = frequenz_max, frequenz_min

    frequenzen = stapel.datensatz.frequenzen
    betroffen = [int(i) for i in np.flatnonzero(
        (frequenzen >= frequenz_min) & (frequenzen <= frequenz_max))]
    intervalle = {i: (float(feld_min), float(feld_max)) for i in betroffen}
    return _fitte_mit_intervallen(stapel, intervalle, modus=modus,
                                  breite_faktor=breite_faktor,
                                  breite_punkte=breite_punkte,
                                  fortschritt=fortschritt, abbruch=abbruch)


def _fitte_mit_intervallen(
    stapel: StapelErgebnis,
    intervalle: dict[int, tuple[float, float]],
    modus: str = "ueberschreiben",
    breite_faktor: float = 8.0,
    breite_punkte: int | None = None,
    fortschritt=None,
    abbruch=None,
) -> tuple[list[int], list[int]]:
    """Kern des Rechteck-Fits (Mode 1).

    ``abbruch()`` (optional) wird nach jedem Fit abgefragt; bei ``True`` werden
    die restlichen Indizes uebersprungen (unveraendert) und gemeldet.

    Fenstersuche mit Stationaer-Abzug ueber :func:`auto_fenster_intervalle`
    (siehe dort - behebt das Haengenbleiben an senkrechten Stoerstreifen),
    danach je Index :func:`fitte_neu`. Liefert ``(neu_gefittet,
    uebersprungen)``.
    """
    _pruefe_modus(modus)
    if breite_punkte is not None and int(breite_punkte) < 4:
        raise ValueError(f"breite_punkte muss >= 4 sein (erhalten: {breite_punkte}).")

    uebersprungen: list[int] = []
    zu_fitten: dict[int, tuple[float, float]] = {}
    for i, grenzen in intervalle.items():
        if (modus == "ergaenzen" and stapel.ergebnisse
                and not stapel.ergebnisse[i].problematisch):
            uebersprungen.append(i)
            continue
        zu_fitten[i] = grenzen

    fenster = auto_fenster_intervalle(stapel.datensatz, zu_fitten, stapel.gamma,
                                      breite_faktor=breite_faktor,
                                      breite_punkte=breite_punkte)
    neu_gefittet: list[int] = []
    reihenfolge = sorted(zu_fitten)
    for k, i in enumerate(reihenfolge):
        if abbruch is not None and abbruch():
            uebersprungen.extend(reihenfolge[k:])
            break
        grenzen = fenster.get(i)
        if grenzen is None:  # zu wenige Messpunkte im Intervall
            uebersprungen.append(i)
            continue
        ergebnis = _fitte_neu_mit_nachfenster(stapel, i, grenzen[0], grenzen[1])
        neu_gefittet.append(i)
        if fortschritt is not None:
            fortschritt(k + 1, len(reihenfolge), ergebnis)

    return neu_gefittet, sorted(uebersprungen)


def _fitte_neu_mit_nachfenster(stapel: StapelErgebnis, i: int,
                               unten: float, oben: float,
                               bestaetigen: bool | None = False):
    """``fitte_neu`` mit anschliessendem zweiten Durchgang auf
    ``B_res +/- stapel.nachfenster_faktor * dH`` (wie im Auto-Fit, siehe
    :func:`polderfit.fit.batch.fitte_mit_nachfenster`). Faellt der Nachfit
    problematisch aus, wird das Ergebnis des ersten Durchgangs deterministisch
    wiederhergestellt."""
    # Bereichs-/Grenzgeraden-Fits rechnen viele Frequenzen auf einmal - das ist
    # keine Einzelfreigabe durch den Nutzer: die Kriterien entscheiden (Bewertung
    # "auto"). Bestaetigt wird nur ein gezielter Eingriff an EINER Frequenz
    # (Grenzen ziehen, Nochmal fitten) oder die explizite Bewertung.
    ergebnis = fitte_neu(stapel, i, feld_unten=unten, feld_oben=oben, bestaetigen=bestaetigen)
    eng = nachfenster(stapel.datensatz.linescans[i], ergebnis, (unten, oben),
                      stapel.nachfenster_faktor)
    if eng is None:
        return ergebnis
    zweites = fitte_neu(stapel, i, feld_unten=eng[0], feld_oben=eng[1], bestaetigen=bestaetigen)
    if zweites.erfolg and not zweites.problematisch:
        return zweites
    return fitte_neu(stapel, i, feld_unten=unten, feld_oben=oben, bestaetigen=bestaetigen)


def zaehle_korridor(stapel: StapelErgebnis, korridor: Korridor,
                    frequenz_min: float | None = None,
                    frequenz_max: float | None = None) -> int:
    """Anzahl Linescans, bei denen der Korridor nicht leer ist (Vorpruefung)."""
    anzahl = 0
    for ls in stapel.datensatz.linescans:
        if frequenz_min is not None and ls.frequenz < frequenz_min:
            continue
        if frequenz_max is not None and ls.frequenz > frequenz_max:
            continue
        if not ls.feld.size:
            continue
        if korridor.gilt(ls.frequenz, float(ls.feld.min()), float(ls.feld.max())):
            anzahl += 1
    return anzahl


def fitte_korridor(
    stapel: StapelErgebnis,
    korridor: Korridor,
    modus: str = "ueberschreiben",
    fortschritt=None,
    abbruch=None,
    frequenz_min: float | None = None,
    frequenz_max: float | None = None,
    schritt: int = 1,
    ausschluss=None,
) -> tuple[list[int], list[int]]:
    """Fittet die Mode des Korridors an allen Frequenzen, an denen der Korridor
    nicht leer ist - je Frequenz ein Einzelfit NUR auf den Punkten im Korridor
    (:func:`polderfit.fit.batch.fitte_mode`). Kein Summenfit, keine
    Fenstersuche: der Korridor IST das Fenster.

    ``schritt`` (Jumper): nur Frequenzen mit Index ``i % schritt == 0`` des
    VOLLEN Gitters fitten (absolut, wie der Auto-Fit-Jumper).
    ``modus='ergaenzen'``: nur Frequenzen, die fuer diese Mode noch nicht gut
    gefittet sind. ``abbruch()`` wird nach jedem Fit abgefragt. Liefert
    ``(neu_gefittet, uebersprungen)``.
    """
    _pruefe_modus(modus)
    schritt = max(1, int(schritt))
    liste = stapel.ergebnisse_mode(korridor.mode)
    kandidaten: list[int] = []
    uebersprungen: list[int] = []
    for i, ls in enumerate(stapel.datensatz.linescans):
        if frequenz_min is not None and ls.frequenz < frequenz_min:
            uebersprungen.append(i)
            continue
        if frequenz_max is not None and ls.frequenz > frequenz_max:
            uebersprungen.append(i)
            continue
        if any(lo <= ls.frequenz <= hi for lo, hi in (ausschluss or [])):
            uebersprungen.append(i)
            continue
        if not ls.feld.size or not korridor.gilt(ls.frequenz, float(ls.feld.min()),
                                                 float(ls.feld.max())):
            uebersprungen.append(i)
            continue
        kandidaten.append(i)
    # Jumper absolut auf dem Frequenzgitter (Index i mit i % schritt == 0) -
    # kongruent zum Auto-Fit-Jumper, unabhaengig vom Korridoranfang.
    reihenfolge = [i for i in kandidaten if i % schritt == 0]
    gewaehlt = set(reihenfolge)
    uebersprungen.extend(i for i in kandidaten if i not in gewaehlt)
    neu: list[int] = []
    for k, i in enumerate(reihenfolge):
        if abbruch is not None and abbruch():
            uebersprungen.extend(reihenfolge[k:])
            break
        if modus == "ergaenzen" and liste[i].gefittet and not liste[i].problematisch:
            uebersprungen.append(i)
            continue
        ergebnis = fitte_mode(stapel, i, korridor, bestaetigen=False)
        if ergebnis is None:
            uebersprungen.append(i)
            continue
        neu.append(i)
        if fortschritt is not None:
            fortschritt(k + 1, len(reihenfolge), ergebnis)
    return neu, sorted(set(uebersprungen))

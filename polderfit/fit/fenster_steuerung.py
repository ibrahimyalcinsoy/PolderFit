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

from .autowindows import auto_fenster, schneide_band
from .batch import Ausschlusszone, StapelErgebnis, fitte_neu

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
        (frequenzen >= zone.frequenz_min) & (frequenzen <= zone.frequenz_max))]
    for k, i in enumerate(betroffen):
        ergebnis = fitte_neu(stapel, i)  # bestehendes Fenster, neue Punktmaske
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
    fortschritt=None,
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
    hinzufuegen). ``fortschritt(k, n, ergebnis)`` ist ein optionaler
    GUI-Callback.

    Liefert ``(neu_gefittet, uebersprungen)`` - Listen von Stapel-Indizes.
    """
    _pruefe_modus(modus)
    if feld_max < feld_min:
        feld_min, feld_max = feld_max, feld_min
    if frequenz_max < frequenz_min:
        frequenz_min, frequenz_max = frequenz_max, frequenz_min

    frequenzen = stapel.datensatz.frequenzen
    betroffen = [int(i) for i in np.flatnonzero(
        (frequenzen >= frequenz_min) & (frequenzen <= frequenz_max))]

    neu_gefittet: list[int] = []
    uebersprungen: list[int] = []
    for k, i in enumerate(betroffen):
        if (modus == "ergaenzen" and stapel.ergebnisse
                and not stapel.ergebnisse[i].problematisch):
            uebersprungen.append(i)
            continue
        ls = stapel.datensatz.linescans[i]
        im_rechteck = int(np.count_nonzero(
            (ls.feld >= feld_min) & (ls.feld <= feld_max)))
        if im_rechteck < 4:
            uebersprungen.append(i)
            continue

        ausschnitt = schneide_band(ls, feld_min, feld_max)
        unten, oben = auto_fenster(ausschnitt, stapel.gamma, breite_faktor)
        # Sicherheitsklemme: das Fenster darf das Rechteck nicht verlassen
        # (auto_fenster arbeitet auf dem Ausschnitt, daher normalerweise ein
        # No-Op - aber explizit ist hier besser als implizit).
        unten = max(unten, feld_min)
        oben = min(oben, feld_max)
        ergebnis = fitte_neu(stapel, i, feld_unten=unten, feld_oben=oben)
        neu_gefittet.append(i)
        if fortschritt is not None:
            fortschritt(k + 1, len(betroffen), ergebnis)

    return neu_gefittet, uebersprungen

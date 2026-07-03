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
from .batch import StapelErgebnis, fitte_neu


def fitte_bereich(
    stapel: StapelErgebnis,
    feld_min: float,
    feld_max: float,
    frequenz_min: float,
    frequenz_max: float,
    breite_faktor: float = 8.0,
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
    werden uebersprungen (unveraendert). ``fortschritt(k, n, ergebnis)`` ist
    ein optionaler GUI-Callback.

    Liefert ``(neu_gefittet, uebersprungen)`` - Listen von Stapel-Indizes.
    """
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

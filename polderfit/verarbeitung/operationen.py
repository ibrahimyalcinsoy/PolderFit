# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Portierte pybbfmr-Verarbeitungsoperationen fuer die 2D-Matrix (komplex).

Alle Operationen arbeiten auf der Darstellung des Projekts::

    feld     : (n_feld,)          gemeinsames Feldgitter in Tesla (aufsteigend)
    frequenz : (n_freq,)          Frequenzachse in Hz (aufsteigend)
    Z        : (n_freq, n_feld)   komplexes S21; NaN ausserhalb des Messbereichs

(Zeilen = Frequenzen, Spalten = Feldwerte – die Orientierung des Farbplots.
Das historische pybbfmr nutzte die transponierte Konvention; beim Portieren
wurde entsprechend gespiegelt.) Jede Operation hat die einheitliche Signatur
``op(feld, frequenz, Z, **parameter) -> (feld, frequenz, Z_neu)`` und laesst
die Eingaben unveraendert (keine In-place-Aenderungen).

Physikalische Grundlage: H. Maier-Flaig et al., "Derivative divide, a method
for the analysis of broadband ferromagnetic resonance in the frequency
domain", Rev. Sci. Instrum. 89, 076101 (2018), https://doi.org/10.1063/1.5045135
– im Folgenden [Maier-Flaig 2018]. Dort ist S21 (Gl. (3))::

    S21(omega, H0) = (-i*omega*A*V_o*chi(omega, H0) + V_o^BG(omega)) / V_i * e^(i*phi)

Der frequenzabhaengige Untergrund ``V_o^BG(omega)`` und die Phase ``e^(i*phi)``
(elektrische Laenge des Aufbaus) verdecken das Resonanzsignal; die Operationen
in diesem Modul entfernen beides ohne Mikrowellen-Kalibrierung.

Abweichungen von pybbfmr (dokumentiert, gewollt):

* Randpunkte, fuer die der Differenzenquotient nicht gebildet werden kann,
  werden NaN statt 0 (pybbfmr) – NaN wird im Farbplot maskiert, 0 wuerde
  faelschlich als Messwert eingefaerbt.
* ``relation_amplitude`` behaelt die Matrixform bei (NaN-Rand) statt die
  Matrix zu kuerzen – so bleiben alle Operationen frei kombinierbar.
"""

from __future__ import annotations

import warnings

import numpy as np

__all__ = ["divide_slice", "derivative_divide", "relation_amplitude", "ACHSEN"]

#: Gueltige Werte des ``achse``-Parameters.
ACHSEN = ("feld", "frequenz")


def _pruefe_achse(achse: str) -> None:
    if achse not in ACHSEN:
        raise ValueError(f"Unbekannte Achse {achse!r} (erlaubt: {ACHSEN}).")


def _index_aus_wert(achsen_werte: np.ndarray, index: int | None,
                    wert: float | None, name: str) -> int:
    """Slice-Index aus explizitem Index oder naechstgelegenem Achsenwert."""
    if index is None and wert is None:
        raise ValueError(f"Bitte {name}-Index oder -Wert angeben.")
    if index is None:
        index = int(np.argmin(np.abs(achsen_werte - wert)))
    index = int(index)
    if not (-achsen_werte.size <= index < achsen_werte.size):
        raise ValueError(f"{name}-Index {index} ausserhalb der Achse "
                         f"(Laenge {achsen_werte.size}).")
    return index


def divide_slice(
    feld: np.ndarray,
    frequenz: np.ndarray,
    Z: np.ndarray,
    achse: str = "feld",
    index: int | None = 0,
    wert: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Normierung durch einen Referenz-Slice (erster Verarbeitungsschritt).

    Teilt die gesamte Matrix punktweise durch einen einzelnen Slice:

    * ``achse="feld"``: Referenz ist das komplette **Spektrum bei einem festen
      Feldwert** (eine Spalte, alle Frequenzen). Division entfernt den
      frequenzabhaengigen Untergrund ``V_o^BG(omega)/V_i * e^(i*phi)`` aus
      [Maier-Flaig 2018] Gl. (3), sofern der Referenz-Slice resonanzfrei ist.
      Das ist der klassische "divide by reference slice"-Schritt.
    * ``achse="frequenz"``: Referenz ist der **Feldsweep bei einer festen
      Frequenz** (eine Zeile) – entfernt feldabhaengige, frequenzunabhaengige
      Strukturen (z. B. Feldsensor-Drift).

    Der Slice wird ueber ``index`` (Achsenindex, auch negativ) oder ``wert``
    (naechstgelegener Achsenwert in T bzw. Hz) gewaehlt. Portiert aus pybbfmr
    ``processing.divide_slice`` (dort ueber ``cut()``); Broadcasting statt
    expliziter Schleife.
    """
    _pruefe_achse(achse)
    Z = np.asarray(Z)
    if achse == "feld":
        i = _index_aus_wert(np.asarray(feld), index, wert, "Feld")
        referenz = Z[:, i][:, np.newaxis]      # (n_freq, 1) -> alle Spalten
    else:
        j = _index_aus_wert(np.asarray(frequenz), index, wert, "Frequenz")
        referenz = Z[j, :][np.newaxis, :]      # (1, n_feld) -> alle Zeilen
    with np.errstate(divide="ignore", invalid="ignore"):
        return feld, frequenz, Z / referenz


def derivative_divide(
    feld: np.ndarray,
    frequenz: np.ndarray,
    Z: np.ndarray,
    delta_n: int = 1,
    mitteln: bool = True,
    achse: str = "feld",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Derivative divide: zentraler Differenzenquotient geteilt durch die Mitte.

    Kern des Verfahrens aus [Maier-Flaig 2018], Gl. (4)::

        d_D S21(omega, H0) = [S21(omega, H0 + dH) - S21(omega, H0 - dH)]
                             / [S21(omega, H0) * dH]
                           ~ -i * omega * A' * dchi/domega

    Die Division durch den zentralen Wert ``S21(omega, H0)`` eliminiert
    Untergrund ``V_o^BG`` und Phase ``e^(i*phi)`` (deshalb entfaellt jede
    Mikrowellen-Kalibrierung); die Differenz wirkt wie eine Feldmodulation
    mit Modulationsamplitude ``dH``.

    Parameter
    ---------
    delta_n:
        Der frei einstellbare Punktabstand Δn der Differenzbildung
        (pybbfmr: ``modulation_amp``). Verglichen werden die Slices
        ``i - delta_n`` und ``i + delta_n``; die effektive Modulations-
        amplitude ist ``dH = delta_n * Feldschrittweite``. Groesseres Δn
        glaettet das Spektrum (noetig, um schwache Moden sichtbar zu machen),
        verbreitert aber Strukturen, die schmaler als ``2*dH`` sind – fuer
        quantitative Fits ist dann [Maier-Flaig 2018] Gl. (5) (Differenzen-
        quotient von chi mit bekanntem ``d_omega = dH * gamma * mu0``) statt
        der reinen Ableitung zu verwenden.
    mitteln:
        ``True`` (pybbfmr-Default): statt der Zwei-Punkt-Differenz werden die
        Mittelwerte der Fenster ``[i-delta_n, i)`` und ``[i, i+delta_n]``
        verglichen – zusaetzliche Glaettung. ``False``: reine Zwei-Punkt-
        Zentraldifferenz (die im pybbfmr-Testbestand bit-genau verifizierte
        Variante).
    achse:
        ``"feld"`` (Standard, wie im Paper: Ableitung nach H0) oder
        ``"frequenz"``.

    Die Schrittweite je Punkt ist der Mittelwert der Gitterabstaende ueber das
    Differenzfenster, ``d = (x[i+Δn] - x[i-Δn]) / (2*Δn)`` – identisch zu
    pybbfmr (wichtig bei ungleichmaessigem Gitter). Randpunkte (die ersten und
    letzten ``delta_n`` Slices) werden NaN.
    """
    _pruefe_achse(achse)
    delta_n = int(delta_n)
    if delta_n < 1:
        raise ValueError(f"delta_n muss >= 1 sein (erhalten: {delta_n}).")

    if achse == "frequenz":
        # Entlang der Frequenzachse: transponiert rechnen, Ergebnis zuruecktransponieren.
        f2, _, G = derivative_divide(frequenz, feld, np.asarray(Z).T,
                                     delta_n=delta_n, mitteln=mitteln, achse="feld")
        return feld, frequenz, G.T

    x = np.asarray(feld, dtype=float)
    Z = np.asarray(Z)
    n = Z.shape[1]
    if x.size != n:
        raise ValueError(f"Feldachse ({x.size}) passt nicht zu Z ({Z.shape}).")
    if n < 2 * delta_n + 1:
        raise ValueError(
            f"Zu wenige Feldpunkte ({n}) fuer delta_n={delta_n} "
            f"(mindestens {2 * delta_n + 1} noetig).")

    G = np.full(Z.shape, np.nan, dtype=complex)
    dx = np.diff(x)
    with np.errstate(divide="ignore", invalid="ignore"), warnings.catch_warnings():
        # Komplett NaN-gefuellte Fenster (ausserhalb des Messbereichs sortierter
        # Daten) liefern erwartungsgemaess NaN – die nanmean-Warnung dazu ist
        # reines Rauschen.
        warnings.filterwarnings("ignore", message="Mean of empty slice",
                                category=RuntimeWarning)
        for i in range(delta_n, n - delta_n):
            if mitteln:
                # Fenstermittel wie pybbfmr: links [i-Δn, i), rechts [i, i+Δn].
                z_links = np.nanmean(Z[:, i - delta_n:i], axis=1)
                z_rechts = np.nanmean(Z[:, i:i + delta_n + 1], axis=1)
            else:
                z_links = Z[:, i - delta_n]
                z_rechts = Z[:, i + delta_n]
            # Mittlere Schrittweite ueber das Fenster = (x[i+Δn]-x[i-Δn])/(2Δn).
            d = float(np.mean(dx[i - delta_n:i + delta_n]))
            G[:, i] = (z_rechts - z_links) / Z[:, i] / d
    return feld, frequenz, G


def relation_amplitude(
    feld: np.ndarray,
    frequenz: np.ndarray,
    Z: np.ndarray,
    delta_n: int = 1,
    achse: str = "feld",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Division durch den Nachbar-Slice im Abstand Δn (pybbfmr: ``referenced_fmr``).

    Fuer jeden Slice ``i`` wird ``Z[i] / Z[i + delta_n]`` gebildet: der um
    ``delta_n`` Punkte entfernte Slice dient als lokale Untergrund-Referenz.
    Amplitude und Phase des Aufbaus kuerzen sich heraus, solange sich der
    Untergrund ueber den Abstand ``delta_n`` kaum aendert; das Resonanzsignal
    bleibt als Verhaeltnis-Anomalie stehen. Divisive Alternative zum
    (derivativen) :func:`derivative_divide` – die Wahl von Δn steuert auch
    hier Glaettung vs. Aufloesung.

    Die letzten ``delta_n`` Slices haben keinen Referenzpartner und werden
    NaN (pybbfmr kuerzte stattdessen die Matrix).
    """
    _pruefe_achse(achse)
    delta_n = int(delta_n)
    if delta_n < 1:
        raise ValueError(f"delta_n muss >= 1 sein (erhalten: {delta_n}).")

    Z = np.asarray(Z)
    G = np.full(Z.shape, np.nan, dtype=complex)
    with np.errstate(divide="ignore", invalid="ignore"):
        if achse == "feld":
            if Z.shape[1] <= delta_n:
                raise ValueError(f"Zu wenige Feldpunkte ({Z.shape[1]}) fuer delta_n={delta_n}.")
            G[:, :-delta_n] = Z[:, :-delta_n] / Z[:, delta_n:]
        else:
            if Z.shape[0] <= delta_n:
                raise ValueError(f"Zu wenige Frequenzen ({Z.shape[0]}) fuer delta_n={delta_n}.")
            G[:-delta_n, :] = Z[:-delta_n, :] / Z[delta_n:, :]
    return feld, frequenz, G

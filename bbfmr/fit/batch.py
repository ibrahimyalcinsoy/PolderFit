"""Stapelverarbeitung aller Linescans mit iterativem Korrekturlauf.

Kapselt den Ablauf: AutoWindows -> Beschnitt -> Einzelfit je Frequenz, mit
Bewertung der Fitguete (R²-Schwelle). Einzelne Datensaetze koennen mit
angepassten Grenzen oder Startwerten nachgefittet werden (continue / zurueck /
nochmal fitten). Diese Klasse haelt den Zustand fuer GUI und Skriptbetrieb.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..io.datensatz import Linescan, Messdatensatz
from ..physik.konstanten import GAMMA_STANDARD
from ..physik.fitmodell import Startwerte
from .auswahl import Auswertungsauswahl
from .autowindows import auto_fenster_alle, fenster_aus_trasse, schneide_band
from .linescan_fit import FitErgebnis, fitte_linescan


@dataclass
class Ausschlusszone:
    """Rechteck (Feld x Frequenz), dessen Messpunkte von Fits ausgenommen werden.

    Interaktiv im Farbplot eingezeichnet (z. B. ein stoerender, zur Feldachse
    paralleler Abschnitt). Wirkt auf alle Nachfit-Wege (``fitte_neu`` und
    alles, was darauf aufbaut); ein neuer Auto-Fit setzt die Zonenliste des
    neuen Stapels bewusst leer auf.
    """

    feld_min: float
    feld_max: float
    frequenz_min: float
    frequenz_max: float

    def __post_init__(self):
        if self.feld_max < self.feld_min:
            self.feld_min, self.feld_max = self.feld_max, self.feld_min
        if self.frequenz_max < self.frequenz_min:
            self.frequenz_min, self.frequenz_max = self.frequenz_max, self.frequenz_min

    def betrifft(self, frequenz: float) -> bool:
        return self.frequenz_min <= frequenz <= self.frequenz_max

    def als_dict(self) -> dict:
        return {"feld_min": self.feld_min, "feld_max": self.feld_max,
                "frequenz_min": self.frequenz_min, "frequenz_max": self.frequenz_max}

    @classmethod
    def aus_dict(cls, daten: dict) -> "Ausschlusszone":
        return cls(**{k: float(daten[k]) for k in
                      ("feld_min", "feld_max", "frequenz_min", "frequenz_max")})


def ohne_ausschlusszonen(linescan: Linescan, zonen: list[Ausschlusszone]) -> Linescan:
    """Entfernt Messpunkte des Linescans, die in einer Ausschlusszone liegen.

    Blieben dabei weniger als 4 Punkte uebrig, wird der Linescan unveraendert
    zurueckgegeben (ein Fit auf < 4 Punkten ist sinnlos; die Bewertung meldet
    solche Faelle ohnehin als problematisch).
    """
    relevante = [z for z in zonen if z.betrifft(linescan.frequenz)]
    if not relevante:
        return linescan
    maske = np.ones(linescan.feld.size, dtype=bool)
    for zone in relevante:
        maske &= ~((linescan.feld >= zone.feld_min) & (linescan.feld <= zone.feld_max))
    if maske.sum() < 4 or maske.all():
        return linescan

    def _teil(arr):
        return arr[maske] if arr is not None else None

    return Linescan(
        frequenz=linescan.frequenz,
        feld=linescan.feld[maske],
        re=linescan.re[maske],
        im=linescan.im[maske],
        feld_before=_teil(linescan.feld_before),
        feld_after=_teil(linescan.feld_after),
        temperatur=_teil(linescan.temperatur),
    )


@dataclass
class StapelErgebnis:
    """Zustand und Ergebnisse der Stapelverarbeitung."""

    datensatz: Messdatensatz
    gamma: float = GAMMA_STANDARD
    r2_schwelle: float = 0.9
    fenster: list[tuple[float, float]] = field(default_factory=list)
    ergebnisse: list[FitErgebnis] = field(default_factory=list)
    zugeschnitten: list[Linescan] = field(default_factory=list)
    #: Interaktiv eingezeichnete Ausschlusszonen (wirken auf alle Nachfits).
    ausschlusszonen: list[Ausschlusszone] = field(default_factory=list)
    #: Als Ausreisser markierte Stapel-Indizes: aus Darstellung UND allen
    #: uebergreifenden Rechnungen (insb. Kittel-/LLG-Fit) ausgenommen.
    ausreisser: list[int] = field(default_factory=list)

    def ist_ausreisser(self, index: int) -> bool:
        return index in self.ausreisser

    def ausreisser_umschalten(self, index: int) -> bool:
        """Schaltet den Ausreisser-Status eines Punkts um.

        Liefert ``True``, wenn der Punkt jetzt ausgeschlossen ist. Die Liste
        bleibt sortiert (Anzeige-/Speicherreihenfolge deterministisch).
        """
        index = int(index)
        if index in self.ausreisser:
            self.ausreisser.remove(index)
            return False
        self.ausreisser.append(index)
        self.ausreisser.sort()
        return True

    def ergebnisse_aktiv(self) -> list[FitErgebnis]:
        """Ergebnisse ohne die als Ausreisser markierten Punkte.

        Das ist die Eingabe fuer alle uebergreifenden Auswertungen
        (Kittel/LLG, Publikationsplots) - einzelne physikalisch sinnlose
        Ausreisser wuerden den linearen Fit sonst bis hin zu negativer
        Steigung verfaelschen.
        """
        gesperrt = set(self.ausreisser)
        return [e for i, e in enumerate(self.ergebnisse) if i not in gesperrt]

    def index_problematisch(self) -> list[int]:
        """Indizes der Frequenzen, deren Fit als problematisch eingestuft ist.

        Stuetzt sich auf die Mehrkriterien-Einstufung (siehe
        :func:`bbfmr.fit.kriterien.bewerte_fit`), nicht auf das wertlose R².
        """
        return [i for i, e in enumerate(self.ergebnisse) if e.problematisch]

    def problem_statistik(self) -> dict[str, int]:
        """Aufschluesselung: wie oft trat welcher Problemgrund auf."""
        zaehler: dict[str, int] = {}
        for e in self.ergebnisse:
            for grund in e.problem_gruende:
                zaehler[grund] = zaehler.get(grund, 0) + 1
        return dict(sorted(zaehler.items(), key=lambda kv: -kv[1]))

    def fitkurven(self) -> list[np.ndarray]:
        return [e.fitkurve for e in self.ergebnisse]


def fitte_alle(
    datensatz: Messdatensatz,
    gamma: float = GAMMA_STANDARD,
    breite_faktor: float = 8.0,
    r2_schwelle: float = 0.9,
    fortschritt=None,
    zentren=None,
    auswahl: Auswertungsauswahl | None = None,
) -> StapelErgebnis:
    """Fittet alle Linescans automatisch (AutoWindows + Beschnitt + Einzelfit).

    ``fortschritt`` ist ein optionaler Callback ``f(i, n, ergebnis)`` fuer die GUI.
    ``zentren`` (optional): vorgegebene Fenstermitten ``B_res(f)`` je Frequenz (z. B.
    aus einem manuellen Dispersions-Seed); dann wird die Auto-Detektion uebersprungen.
    ``auswahl`` (optional): Unterabtastung/Bereichseinschraenkung
    (:class:`bbfmr.fit.auswahl.Auswertungsauswahl`) – der Stapel arbeitet dann
    auf dem reduzierten Datensatz; ``zentren`` (auf den vollen Datensatz
    bezogen) wird deckungsgleich mit reduziert.
    """
    if auswahl is not None and not auswahl.ist_neutral:
        datensatz, indizes = auswahl.reduziere(datensatz)
        if zentren is not None:
            zentren = np.asarray(zentren)[indizes]

    if zentren is not None:
        fenster = fenster_aus_trasse(datensatz, zentren, gamma, breite_faktor)
    else:
        fenster = auto_fenster_alle(datensatz, gamma, breite_faktor)
    stapel = StapelErgebnis(
        datensatz=datensatz, gamma=gamma, r2_schwelle=r2_schwelle, fenster=fenster,
    )
    n = len(datensatz.linescans)
    for i, ls in enumerate(datensatz.linescans):
        unten, oben = fenster[i]
        beschnitten = schneide_band(ls, unten, oben)
        ergebnis = fitte_linescan(beschnitten, gamma)
        stapel.zugeschnitten.append(beschnitten)
        stapel.ergebnisse.append(ergebnis)
        if fortschritt is not None:
            fortschritt(i, n, ergebnis)
    return stapel


def fitte_neu(
    stapel: StapelErgebnis,
    index: int,
    feld_unten: float | None = None,
    feld_oben: float | None = None,
    startwerte: Startwerte | None = None,
    B_res_vorgabe: float | None = None,
) -> FitErgebnis:
    """Fittet einen einzelnen Datensatz neu (manuelles Nachfitten).

    Optional mit neuen Bandgrenzen, expliziten Startwerten oder nur neuem
    Resonanzfeld. Aktualisiert den Stapel an Position ``index`` und gibt das
    neue Ergebnis zurueck.
    """
    ls = stapel.datensatz.linescans[index]
    unten, oben = stapel.fenster[index]
    if feld_unten is not None:
        unten = feld_unten
    if feld_oben is not None:
        oben = feld_oben
    stapel.fenster[index] = (unten, oben)

    beschnitten = schneide_band(ls, unten, oben)
    if stapel.ausschlusszonen:
        beschnitten = ohne_ausschlusszonen(beschnitten, stapel.ausschlusszonen)
    ergebnis = fitte_linescan(
        beschnitten, stapel.gamma, startwerte=startwerte, B_res_vorgabe=B_res_vorgabe,
    )
    ergebnis.nachbearbeitet = True
    stapel.zugeschnitten[index] = beschnitten
    stapel.ergebnisse[index] = ergebnis
    return ergebnis

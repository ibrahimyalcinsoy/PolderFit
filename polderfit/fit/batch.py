# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Stapelverarbeitung aller Linescans mit iterativem Korrekturlauf.

Kapselt den Ablauf: AutoWindows -> Beschnitt -> Einzelfit je Frequenz, mit
Bewertung der Fitguete (R²-Schwelle). Einzelne Datensaetze koennen mit
angepassten Grenzen oder Startwerten nachgefittet werden (continue / zurueck /
nochmal fitten). Diese Klasse haelt den Zustand fuer GUI und Skriptbetrieb.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from ..io.datensatz import Linescan, Messdatensatz
from ..physik.konstanten import GAMMA_STANDARD
from ..physik.fitmodell import Startwerte, s21_modell
from .auswahl import Auswertungsauswahl
from .autowindows import auto_fenster_alle, fenster_aus_trasse, schneide_band
from .korridor import Korridor, dip_segmente, segmente_aus_trennern
from .kriterien import ALPHA_MAX
from .linescan_fit import FitErgebnis, fitte_linescan, fitte_linescan_summe, setze_bewertung

#: Standard des zweiten Fit-Durchgangs: Fitfenster = B_res +/- Faktor * mu0*dH
#: (Linienbreite aus dem ersten Durchgang). 0 schaltet den Durchgang ab.
#:
#: Hintergrund (Benchmark gegen das LabVIEW-FTF, CoFe-Datensaetze): Das
#: Auto-Fenster der Detektion ist bewusst breit (Faktor 8 auf die Magnituden-
#: FWHM, d. h. ~ +/-7 Linienbreiten). Auf so breiten Fenstern passt der lineare
#: Untergrund bei strukturiertem Hintergrund (Ripple, Nachbarsignale) nicht
#: mehr, und die Linienbreite kommt systematisch 5-15 % zu klein heraus. Bis
#: etwa +/-3 Linienbreiten liegt dH auf einem Plateau (fensterunabhaengig);
#: dort landet auch das FTF mit von Hand gewaehlten Fenstern. Der zweite
#: Durchgang engt deshalb um das erste Fitergebnis herum ein und uebernimmt das
#: Ergebnis nur, wenn der Nachfit nicht problematisch ist.
NACHFENSTER_FAKTOR_STANDARD: float = 2.5
#: Mindestanzahl Messpunkte im verengten Fenster (sonst bleibt der 1. Durchgang).
NACHFENSTER_MIN_PUNKTE: int = 12


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
    #: Harte obere alpha-Schranke der Einzelfits (auch fuer alle Nachfits).
    alpha_max: float = ALPHA_MAX
    #: Faktor des zweiten Fit-Durchgangs (Fenster = B_res +/- Faktor*dH); 0 = aus.
    nachfenster_faktor: float = NACHFENSTER_FAKTOR_STANDARD
    #: Plausibilitaetsgrenze "alpha unphysikalisch" (None = alpha_max/2).
    alpha_plausibel: float | None = None
    #: Manuelle Nachfits automatisch als "gut - vom Nutzer bestaetigt" bewerten
    #: (Standard aus: die Kriterien entscheiden, bestaetigt wird explizit).
    nachfit_bestaetigen: bool = False
    #: Fitfenster je Frequenz (Mode 1; das "gruene Fenster").
    fenster: list[tuple[float, float]] = field(default_factory=list)
    #: Ergebnisse der Mode 1 je Frequenz (Hauptmode: Overlay, Problemliste, Export).
    ergebnisse: list[FitErgebnis] = field(default_factory=list)
    zugeschnitten: list[Linescan] = field(default_factory=list)
    #: Ergebnisse weiterer Moden: ``{mode: [FitErgebnis je Frequenz]}`` (Mode >= 2),
    #: je Mode ein Einzelfit auf den Punkten ihres Korridors (siehe
    #: :func:`fitte_mode`); nicht gefittete Frequenzen sind Platzhalter.
    nebenmoden: dict = field(default_factory=dict)
    #: Interaktiv eingezeichnete Ausschlusszonen (wirken auf alle Nachfits).
    ausschlusszonen: list[Ausschlusszone] = field(default_factory=list)
    #: Als Ausreisser markierte Stapel-Indizes: aus Darstellung UND allen
    #: uebergreifenden Rechnungen (insb. Kittel-/LLG-Fit) ausgenommen.
    ausreisser: list[int] = field(default_factory=list)
    #: Nur fuer die Kittel-/LLG-Auswertung JE MODE ausgeschlossene Paare
    #: ``(Stapel-Index, Mode)`` (Mode = Zweig-Nummer 1..n, siehe
    #: :mod:`polderfit.auswertung.moden`); der Linescan selbst und seine
    #: anderen Moden bleiben in der Auswertung.
    ausreisser_moden: list[tuple[int, int]] = field(default_factory=list)

    # --- Moden ---------------------------------------------------------------
    def ergebnisse_mode(self, mode: int) -> list[FitErgebnis]:
        """Ergebnisliste der Mode ``mode`` (1 = ``ergebnisse``; sonst Platzhalter
        anlegen, falls noch nicht vorhanden)."""
        mode = max(1, int(mode))
        if mode == 1:
            return self.ergebnisse
        liste = self.nebenmoden.get(mode)
        if liste is None or len(liste) != len(self.datensatz.linescans):
            liste = [FitErgebnis.platzhalter(ls.frequenz, ls.feld, mode=mode)
                     for ls in self.datensatz.linescans]
            self.nebenmoden[mode] = liste
        return liste

    def moden_vorhanden(self) -> list[int]:
        """Mode-Nummern mit mindestens einem gefitteten Ergebnis (immer mit 1)."""
        moden = [1]
        for k in sorted(self.nebenmoden):
            if any(e.gefittet for e in self.nebenmoden[k]):
                moden.append(int(k))
        return moden

    def mode_entfernen(self, mode: int) -> None:
        """Ergebnisse einer Nebenmode verwerfen (z. B. Korridor geloescht)."""
        if int(mode) >= 2:
            self.nebenmoden.pop(int(mode), None)
            self.ausreisser_moden = [(i, k) for i, k in self.ausreisser_moden
                                     if int(k) != int(mode)]

    def ist_ausreisser(self, index: int) -> bool:
        return index in self.ausreisser

    def ist_ausreisser_mode(self, index: int, mode: int) -> bool:
        return (int(index), int(mode)) in set(map(tuple, self.ausreisser_moden))

    def ausreisser_mode_umschalten(self, index: int, mode: int) -> bool:
        """Schaltet den Ausschluss der Mode ``mode`` am Linescan ``index`` um.

        Liefert ``True``, wenn das Paar jetzt ausgeschlossen ist. Liste bleibt
        sortiert (Index, dann Mode).
        """
        paar = (int(index), int(mode))
        paare = [tuple(p) for p in self.ausreisser_moden]
        if paar in paare:
            paare.remove(paar)
            self.ausreisser_moden = sorted(paare)
            return False
        paare.append(paar)
        self.ausreisser_moden = sorted(paare)
        return True

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
        :func:`polderfit.fit.kriterien.bewerte_fit`), nicht auf das wertlose R².
        """
        return [i for i, e in enumerate(self.ergebnisse)
                if e.problematisch and e.gefittet]

    def index_gefittet(self) -> list[int]:
        """Indizes mit echtem Fitergebnis (keine Platzhalter)."""
        return [i for i, e in enumerate(self.ergebnisse) if e.gefittet]

    def bewerte(self, index: int, bewertung: str, mode: int = 1) -> FitErgebnis:
        """Setzt die Nutzer-Bewertung des Fits ``index`` der Mode ``mode``
        (Kopie, Undo-sicher)."""
        liste = self.ergebnisse_mode(mode)
        neu = setze_bewertung(liste[index], bewertung)
        liste[index] = neu
        return neu

    def problem_statistik(self) -> dict[str, int]:
        """Aufschluesselung: wie oft trat welcher Problemgrund auf."""
        zaehler: dict[str, int] = {}
        for e in self.ergebnisse:
            for grund in e.problem_gruende:
                zaehler[grund] = zaehler.get(grund, 0) + 1
        return dict(sorted(zaehler.items(), key=lambda kv: -kv[1]))

    def fitkurven(self) -> list[np.ndarray]:
        return [e.fitkurve for e in self.ergebnisse]


def nachfenster(linescan: Linescan, ergebnis: FitErgebnis, fenster: tuple[float, float],
                faktor: float) -> tuple[float, float] | None:
    """Verengtes Fitfenster ``B_res +/- faktor*dH`` fuer den zweiten Durchgang.

    Liefert ``None``, wenn kein zweiter Durchgang sinnvoll ist (Faktor 0, erster
    Fit problematisch/ohne Linienbreite, oder das verengte Fenster waere nicht
    enger als das bestehende). Das Fenster wird nur verengt, nie erweitert
    (Schnitt mit ``fenster``), und unterschreitet nie ``NACHFENSTER_MIN_PUNKTE``
    Messpunkte bzw. 6 Feldschritte Halbbreite.
    """
    if not faktor or faktor <= 0:
        return None
    if ergebnis.problematisch or not ergebnis.erfolg:
        return None
    if not (np.isfinite(ergebnis.B_res) and np.isfinite(ergebnis.dH) and ergebnis.dH > 0):
        return None
    B = np.asarray(linescan.feld, dtype=float)
    if B.size < 2:
        return None
    spacing = float(np.ptp(B)) / B.size
    halb = max(faktor * float(ergebnis.dH), 6.0 * spacing)
    unten = max(float(ergebnis.B_res) - halb, float(fenster[0]))
    oben = min(float(ergebnis.B_res) + halb, float(fenster[1]))
    if oben - unten >= (fenster[1] - fenster[0]) * (1.0 - 1e-9):
        return None  # nicht enger als bisher
    if np.count_nonzero((B >= unten) & (B <= oben)) < NACHFENSTER_MIN_PUNKTE:
        return None
    return unten, oben


def fitte_mit_nachfenster(
    linescan: Linescan,
    fenster: tuple[float, float],
    gamma: float,
    alpha_max: float = ALPHA_MAX,
    nachfenster_faktor: float = NACHFENSTER_FAKTOR_STANDARD,
    alpha_plausibel: float | None = None,
    mode: int = 1,
    B_res_vorgabe: float | None = None,
) -> tuple[FitErgebnis, Linescan, tuple[float, float]]:
    """Einzelfit in ``fenster``, dann verengter zweiter Durchgang (siehe
    :data:`NACHFENSTER_FAKTOR_STANDARD`).

    Liefert ``(ergebnis, beschnittener_linescan, verwendetes_fenster)``. Der
    zweite Durchgang wird nur uebernommen, wenn er erfolgreich und nicht
    problematisch ist – sonst bleibt der erste Durchgang bestehen.
    """
    unten, oben = fenster
    beschnitten = schneide_band(linescan, unten, oben)
    ergebnis = fitte_linescan(beschnitten, gamma, alpha_max=alpha_max,
                              alpha_plausibel=alpha_plausibel, mode=mode,
                              B_res_vorgabe=B_res_vorgabe)
    eng = nachfenster(linescan, ergebnis, (unten, oben), nachfenster_faktor)
    if eng is None:
        return ergebnis, beschnitten, (unten, oben)
    beschnitten2 = schneide_band(linescan, eng[0], eng[1])
    ergebnis2 = fitte_linescan(beschnitten2, gamma, alpha_max=alpha_max,
                               alpha_plausibel=alpha_plausibel, mode=mode)
    if ergebnis2.erfolg and not ergebnis2.problematisch:
        return ergebnis2, beschnitten2, eng
    return ergebnis, beschnitten, (unten, oben)


def fitte_alle(
    datensatz: Messdatensatz,
    gamma: float = GAMMA_STANDARD,
    breite_faktor: float = 8.0,
    r2_schwelle: float = 0.9,
    fortschritt=None,
    zentren=None,
    auswahl: Auswertungsauswahl | None = None,
    alpha_erwartet: float = 0.01,
    alpha_max: float = ALPHA_MAX,
    nachfenster_faktor: float = NACHFENSTER_FAKTOR_STANDARD,
    alpha_plausibel: float | None = None,
    nachfit_bestaetigen: bool = False,
    fortschritt_fenster=None,
    abbruch=None,
    korridor: Korridor | None = None,
) -> StapelErgebnis:
    """Fittet alle Linescans automatisch (AutoWindows + Beschnitt + Einzelfit).

    ``fortschritt_fenster(k, n)`` meldet die Fenstersuche (Phase 1),
    ``fortschritt(i, n, ergebnis)`` die Einzelfits (Phase 2). ``abbruch()``
    (optional) wird nach jedem Einzelfit abgefragt; liefert es ``True``, bleiben
    die restlichen Frequenzen als Platzhalter ("nicht gefittet") stehen und der
    bis dahin erreichte Stapel wird zurueckgegeben.

    ``fortschritt`` ist ein optionaler Callback ``f(i, n, ergebnis)`` fuer die GUI.
    ``zentren`` (optional): vorgegebene Fenstermitten ``B_res(f)`` je Frequenz (z. B.
    aus einem manuellen Dispersions-Seed); dann wird die Auto-Detektion uebersprungen.
    ``auswahl`` (optional): Unterabtastung/Bereichseinschraenkung
    (:class:`polderfit.fit.auswahl.Auswertungsauswahl`) – der Stapel arbeitet dann
    auf dem reduzierten Datensatz; ``zentren`` (auf den vollen Datensatz
    bezogen) wird deckungsgleich mit reduziert.
    ``alpha_max``: harte obere alpha-Schranke der Einzelfits.
    ``nachfenster_faktor``: zweiter Fit-Durchgang auf ``B_res +/- Faktor*dH``
    (siehe :data:`NACHFENSTER_FAKTOR_STANDARD`; 0 = nur ein Durchgang).
    ``korridor`` (optional): Korridor der Mode 1 - dann wird je Frequenz NUR
    im Korridor gefittet (Fenster = Korridor, keine Fenstersuche); Frequenzen
    ohne Korridor bleiben Platzhalter. Weitere Moden: :func:`fitte_mode`.
    """
    if auswahl is not None and not auswahl.ist_neutral:
        datensatz, indizes = auswahl.reduziere(datensatz)
        if zentren is not None:
            zentren = np.asarray(zentren)[indizes]

    if korridor is not None and korridor.definiert:
        fenster = []
        for ls in datensatz.linescans:
            g = (korridor.grenzen_im_bereich(ls.frequenz, float(ls.feld.min()),
                                             float(ls.feld.max()))
                 if ls.feld.size else None)
            fenster.append(g if g is not None else (np.nan, np.nan))
    elif zentren is not None:
        fenster = fenster_aus_trasse(datensatz, zentren, gamma, breite_faktor,
                                     alpha_erwartet=alpha_erwartet)
    else:
        fenster = auto_fenster_alle(datensatz, gamma, breite_faktor,
                                    fortschritt=fortschritt_fenster)
    stapel = StapelErgebnis(
        datensatz=datensatz, gamma=gamma, r2_schwelle=r2_schwelle, fenster=list(fenster),
        alpha_max=alpha_max, nachfenster_faktor=nachfenster_faktor,
        alpha_plausibel=alpha_plausibel,
        nachfit_bestaetigen=nachfit_bestaetigen,
    )
    n = len(datensatz.linescans)
    for i, ls in enumerate(datensatz.linescans):
        if abbruch is not None and abbruch():
            # Rest als Platzhalter: der Stapel bleibt konsistent und nutzbar.
            for rest in datensatz.linescans[i:]:
                stapel.zugeschnitten.append(rest)
                stapel.ergebnisse.append(FitErgebnis.platzhalter(rest.frequenz, rest.feld))
            break
        if not np.all(np.isfinite(fenster[i])):
            # Ausserhalb des Korridors: nicht gefittet.
            stapel.fenster[i] = ((float(ls.feld.min()), float(ls.feld.max()))
                                 if ls.feld.size else (0.0, 0.0))
            stapel.zugeschnitten.append(ls)
            stapel.ergebnisse.append(FitErgebnis.platzhalter(ls.frequenz, ls.feld))
            continue
        ergebnis, beschnitten, verwendet = fitte_mit_nachfenster(
            ls, fenster[i], gamma, alpha_max=alpha_max,
            nachfenster_faktor=nachfenster_faktor, alpha_plausibel=alpha_plausibel)
        stapel.fenster[i] = verwendet
        stapel.zugeschnitten.append(beschnitten)
        stapel.ergebnisse.append(ergebnis)
        if fortschritt is not None:
            fortschritt(i, n, ergebnis)
    return stapel


def _nachbar_b_res(ergebnisse: list, i: int, fenster) -> float | None:
    """Resonanzfeld des naechsten gut gefitteten Nachbarn (erst links, dann
    rechts), falls es im Fenster liegt - Rueckfall-Startwert fuer den
    Korridor-Fit, wenn der lokale Dip nicht zum Ziel fuehrt."""
    for j in (i - 1, i + 1):
        if not (0 <= j < len(ergebnisse)):
            continue
        e = ergebnisse[j]
        if not (getattr(e, "gefittet", False) and e.erfolg and not e.problematisch):
            continue
        b = float(e.B_res)
        if fenster is not None and fenster[0] < b < fenster[1]:
            return b
    return None


def leerer_stapel(
    datensatz: Messdatensatz,
    gamma: float = GAMMA_STANDARD,
    r2_schwelle: float = 0.9,
    alpha_max: float = ALPHA_MAX,
    nachfenster_faktor: float = NACHFENSTER_FAKTOR_STANDARD,
    alpha_plausibel: float | None = None,
    nachfit_bestaetigen: bool = False,
    breite_faktor: float = 8.0,
) -> StapelErgebnis:
    """Stapel OHNE Fits: je Frequenz ein Platzhalter und das AutoWindow-Fenster.

    Damit funktionieren alle Nachfit-Werkzeuge (Grenzgeraden, Bereichs-Fit,
    Grenzen ziehen) auch direkt nach dem Laden - ohne vorherigen Auto-Fit.
    Nur die vom Nutzer bearbeiteten Frequenzen erhalten ein Ergebnis; der
    Rest bleibt als "nicht gefittet" unsichtbar und ausserhalb aller
    Auswertungen.

    Das Fenster je Frequenz ist dasselbe wie in Phase 1 des Auto-Fits
    (:func:`polderfit.fit.autowindows.auto_fenster_alle`, entlang der Mode),
    NICHT der ganze Feldsweep: ein Nachfit ueber den vollen Sweep ueberschaetzt
    die Linienbreite systematisch (bis +34 % gemessen, R^2 unauffaellig).
    Schlaegt die Fenstersuche fehl, bleibt der volle Sweep als Rueckfall.
    """
    stapel = StapelErgebnis(
        datensatz=datensatz, gamma=gamma, r2_schwelle=r2_schwelle,
        alpha_max=alpha_max, nachfenster_faktor=nachfenster_faktor,
        alpha_plausibel=alpha_plausibel,
        nachfit_bestaetigen=nachfit_bestaetigen,
    )
    try:
        fenster = auto_fenster_alle(datensatz, gamma, breite_faktor)
    except Exception:  # Fenstersuche darf das Laden nie verhindern
        fenster = None
    for k, ls in enumerate(datensatz.linescans):
        if fenster is not None and k < len(fenster) and np.all(np.isfinite(fenster[k])):
            stapel.fenster.append((float(fenster[k][0]), float(fenster[k][1])))
        elif ls.feld.size:
            stapel.fenster.append((float(ls.feld.min()), float(ls.feld.max())))
        else:
            stapel.fenster.append((0.0, 0.0))
        stapel.zugeschnitten.append(ls)
        stapel.ergebnisse.append(FitErgebnis.platzhalter(ls.frequenz, ls.feld))
    return stapel


def fenster_anteil(stapel: StapelErgebnis, index: int) -> float:
    """Anteil des Fitfensters am Feldsweep (0..1) - Warnschwelle siehe
    :data:`FENSTER_ANTEIL_WARNUNG`."""
    ls = stapel.datensatz.linescans[index]
    B = np.asarray(ls.feld, dtype=float)
    if B.size < 2 or not np.isfinite(B).any():
        return 0.0
    spanne = float(np.nanmax(B) - np.nanmin(B))
    if spanne <= 0:
        return 0.0
    unten, oben = stapel.fenster[index]
    return max(0.0, min(1.0, (float(oben) - float(unten)) / spanne))


#: Ab diesem Fensteranteil am Sweep wird vor ueberschaetzter Linienbreite gewarnt.
FENSTER_ANTEIL_WARNUNG = 0.6


def fitte_neu(
    stapel: StapelErgebnis,
    index: int,
    feld_unten: float | None = None,
    feld_oben: float | None = None,
    startwerte: Startwerte | None = None,
    B_res_vorgabe: float | None = None,
    bestaetigen: bool | None = None,
    mode: int = 1,
    linescan: Linescan | None = None,
) -> FitErgebnis:
    """Fittet einen einzelnen Datensatz neu (manuelles Nachfitten).

    ``linescan`` (optional) ersetzt die Messdaten dieser Frequenz (z. B. nach
    Abzug der Nachbar-Resonanzen beim Mehr-Dip-Korridor); Fenster und Listen
    beziehen sich weiter auf ``index``.

    Optional mit neuen Bandgrenzen, expliziten Startwerten oder nur neuem
    Resonanzfeld. Aktualisiert den Stapel an Position ``index`` und gibt das
    neue Ergebnis zurueck. ``mode >= 2``: Ergebnis landet in
    ``stapel.ergebnisse_mode(mode)``; ``stapel.fenster`` (Mode 1) bleibt
    unveraendert, das Fenster der Mode steht im Ergebnis (``B_fenster_min/max``).

    ``bestaetigen``: das Ergebnis als "gut - vom Nutzer bestaetigt" bewerten
    (nur wenn der Fit ein Ergebnis liefert). ``None`` = Stapel-Einstellung
    ``nachfit_bestaetigen`` (Standard AUS: auch ein Nachfit wird von den
    Kriterien bewertet; bestaetigt wird explizit ueber die Bewertung - sonst
    verschwinden Problemfits durch blosses "Neu fitten" aus der Liste).
    """
    mode = max(1, int(mode))
    ls = linescan if linescan is not None else stapel.datensatz.linescans[index]
    liste = stapel.ergebnisse_mode(mode)
    if mode == 1:
        unten, oben = stapel.fenster[index]
    else:
        alt = liste[index]
        unten, oben = alt.B_fenster_min, alt.B_fenster_max
        if not (np.isfinite(unten) and np.isfinite(oben)):
            unten, oben = stapel.fenster[index]
    if feld_unten is not None:
        unten = feld_unten
    if feld_oben is not None:
        oben = feld_oben
    if mode == 1:
        stapel.fenster[index] = (unten, oben)

    beschnitten = schneide_band(ls, unten, oben)
    if stapel.ausschlusszonen:
        beschnitten = ohne_ausschlusszonen(beschnitten, stapel.ausschlusszonen)
    ergebnis = fitte_linescan(
        beschnitten, stapel.gamma, startwerte=startwerte, B_res_vorgabe=B_res_vorgabe,
        alpha_max=stapel.alpha_max, alpha_plausibel=stapel.alpha_plausibel, mode=mode,
    )
    ergebnis.nachbearbeitet = True
    if bestaetigen is None:
        bestaetigen = bool(stapel.nachfit_bestaetigen)
    if bestaetigen:
        ergebnis = setze_bewertung(ergebnis, "bestaetigt")
    if mode == 1:
        stapel.zugeschnitten[index] = beschnitten
    liste[index] = ergebnis
    return ergebnis


def fitte_mode(
    stapel: StapelErgebnis,
    index: int,
    korridor: Korridor,
    bestaetigen: bool | None = False,
) -> FitErgebnis | None:
    """Einzelfit der Mode(n) des Korridors an Frequenz ``index`` AUSSCHLIESSLICH
    auf den Messpunkten im Korridor (Punkte ausserhalb sind maskiert, nicht
    mitmodelliert), mit Nachfenster-Durchgang ``B_res +/- Faktor*dH`` innerhalb
    des Korridors. Startwert ``B_res``: lokaler Dip im Korridor (Startwert-
    Schaetzung), sonst das Ergebnis der Nachbarfrequenz.

    ``korridor.n_dips > 1``: der Korridor wird bei dieser Frequenz zwischen den
    n prominentesten Dips hart getrennt (:func:`dip_segmente`); Segment j wird
    als Einzelfit in die Mode ``korridor.moden[j]`` gefittet. Liefert das
    Ergebnis der ersten Mode, ``None`` bei leerem Korridor.
    """
    ls = stapel.datensatz.linescans[index]
    if not ls.feld.size:
        return None
    grenzen = korridor.grenzen_im_bereich(ls.frequenz, float(ls.feld.min()),
                                          float(ls.feld.max()))
    if grenzen is None:
        return None
    if korridor.n_dips <= 1 or len(korridor.moden) <= 1:
        return _fitte_mode_im_fenster(stapel, index, korridor.mode, grenzen, bestaetigen)
    ausschnitt = schneide_band(ls, grenzen[0], grenzen[1])
    if stapel.ausschlusszonen:
        ausschnitt = ohne_ausschlusszonen(ausschnitt, stapel.ausschlusszonen)
    manuell = korridor.trennstellen(ls.frequenz)
    if manuell is not None:
        segmente = segmente_aus_trennern(float(ausschnitt.feld.min()),
                                         float(ausschnitt.feld.max()), manuell)
    else:
        segmente = dip_segmente(ausschnitt.feld, ausschnitt.s21, len(korridor.moden))
    ergebnisse: dict[int, FitErgebnis] = {}
    # Durchgang 1: jeder Dip in seinem Segment (harte Trennung).
    for j, mode in enumerate(korridor.moden):
        if j < len(segmente):
            ergebnisse[mode] = _fitte_mode_im_fenster(stapel, index, mode, segmente[j],
                                                      bestaetigen,
                                                      nachfenster_pass=len(segmente) == 1)
        else:
            erg = FitErgebnis.platzhalter(ls.frequenz, ls.feld, mode=mode)
            erg.meldung = "Dip im Korridor nicht gefunden"
            stapel.ergebnisse_mode(mode)[index] = erg
    if korridor.methode == "summe" and len(segmente) > 1:
        # Durchgang 2 (Summenfit): alle Dips gemeinsam auf den Korridorpunkten,
        # B_res_k hart auf sein Segment beschraenkt, gemeinsamer Untergrund.
        moden = list(korridor.moden[:len(segmente)])
        try:
            summe = fitte_linescan_summe(
                ausschnitt, stapel.gamma, segmente, [ergebnisse.get(m) for m in moden], moden,
                alpha_max=stapel.alpha_max, alpha_plausibel=stapel.alpha_plausibel)
        except Exception:
            summe = None
        if summe is not None:
            for mode, erg in zip(moden, summe):
                erg.nachbearbeitet = True
                if bestaetigen is None:
                    bestaetigen_wirksam = bool(stapel.nachfit_bestaetigen)
                else:
                    bestaetigen_wirksam = bool(bestaetigen)
                if bestaetigen_wirksam:
                    erg = setze_bewertung(erg, "bestaetigt")
                stapel.ergebnisse_mode(mode)[index] = erg
                if mode == 1:
                    stapel.fenster[index] = grenzen
                    stapel.zugeschnitten[index] = ausschnitt
                ergebnisse[mode] = erg
        return ergebnisse.get(korridor.moden[0])
    # Durchgang 2 (Trennung): Ausläufer der Nachbar-Dips (Resonanzanteil des
    # Durchgangs 1) abziehen und jeden Dip in seinem Segment erneut einzeln
    # fitten - kein Summenfit, aber die Segmente werden vom Nachbarn befreit.
    # Zwei Runden: ein zunaechst schlechter Dip wird nicht abgezogen, sondern
    # profitiert erst vom guten Nachbarn und verbessert diesen in Runde 2.
    if len(segmente) > 1:
        omega = 2.0 * np.pi * ls.frequenz
        for runde in range(2):
            geaendert = False
            for j, mode in enumerate(korridor.moden[:len(segmente)]):
                rest = np.asarray(ls.s21, dtype=complex).copy()
                abgezogen = 0
                for m2, e2 in ergebnisse.items():
                    if m2 == mode or not (e2.gefittet and e2.erfolg and not e2.problematisch
                                          and np.isfinite(e2.B_res)):
                        continue
                    rest -= s21_modell(ls.feld, e2.B_res, e2.alpha, e2.A, e2.phi, 0.0, 0.0,
                                       0.0, 0.0, omega, stapel.gamma, float(np.mean(ls.feld)))
                    abgezogen += 1
                if not abgezogen:
                    continue
                bereinigt = Linescan(frequenz=ls.frequenz, feld=ls.feld, re=rest.real,
                                     im=rest.imag,
                                     feld_before=getattr(ls, "feld_before", None),
                                     feld_after=getattr(ls, "feld_after", None),
                                     temperatur=getattr(ls, "temperatur", None))
                alt = ergebnisse[mode]
                neu = _fitte_mode_im_fenster(stapel, index, mode, segmente[j], bestaetigen,
                                             linescan=bereinigt)
                alt_gut = alt.erfolg and not alt.problematisch
                neu_gut = neu.erfolg and not neu.problematisch
                besser = (neu_gut and not alt_gut) or (
                    neu_gut == alt_gut and np.isfinite(neu.rmse_norm)
                    and (not np.isfinite(alt.rmse_norm) or neu.rmse_norm <= alt.rmse_norm))
                if besser:
                    geaendert = geaendert or (abs(neu.B_res - alt.B_res) > 1e-6
                                              or abs(neu.dH - alt.dH) > 1e-6)
                    ergebnisse[mode] = neu
                else:
                    stapel.ergebnisse_mode(mode)[index] = alt
            if not geaendert:
                break   # zweite Runde nur, wenn die erste etwas veraendert hat
    return ergebnisse.get(korridor.moden[0])


def _fitte_mode_im_fenster(stapel: StapelErgebnis, index: int, mode: int,
                           grenzen: tuple[float, float],
                           bestaetigen: bool | None, linescan: Linescan | None = None,
                           nachfenster_pass: bool = True) -> FitErgebnis:
    """Einzelfit einer Mode im harten Fenster ``grenzen`` mit Nachbar-Rueckfall
    und (``nachfenster_pass``) Nachfenster-Durchgang (siehe :func:`fitte_mode`).
    ``linescan``: ersetzt die Messdaten (Nachbar-Dips abgezogen)."""
    ls = linescan if linescan is not None else stapel.datensatz.linescans[index]
    liste = stapel.ergebnisse_mode(mode)
    vorgabe = _nachbar_b_res(liste, index, grenzen)
    # 1. Durchgang: Startwert aus dem lokalen Dip im Fenster.
    ergebnis = fitte_neu(stapel, index, feld_unten=grenzen[0], feld_oben=grenzen[1],
                         bestaetigen=bestaetigen, mode=mode, linescan=linescan)
    if ergebnis.problematisch and vorgabe is not None:
        # Rueckfall: Startwert vom Nachbarn - nur uebernehmen, wenn besser.
        zweiter = fitte_neu(stapel, index, feld_unten=grenzen[0], feld_oben=grenzen[1],
                            B_res_vorgabe=vorgabe, bestaetigen=bestaetigen, mode=mode,
                            linescan=linescan)
        if not (zweiter.problematisch and not ergebnis.problematisch) and (
                not zweiter.problematisch
                or (np.isfinite(zweiter.rmse_norm) and (not np.isfinite(ergebnis.rmse_norm)
                                                        or zweiter.rmse_norm < ergebnis.rmse_norm))):
            ergebnis = zweiter
        else:
            ergebnis = fitte_neu(stapel, index, feld_unten=grenzen[0], feld_oben=grenzen[1],
                                 bestaetigen=bestaetigen, mode=mode, linescan=linescan)
    # 2. Durchgang: Nachfenster innerhalb des Fensters.
    eng = nachfenster(ls, ergebnis, grenzen, stapel.nachfenster_faktor) if nachfenster_pass else None
    if eng is not None:
        b_start = float(ergebnis.B_res)
        zweites = fitte_neu(stapel, index, feld_unten=eng[0], feld_oben=eng[1],
                            bestaetigen=bestaetigen, mode=mode, linescan=linescan)
        if zweites.erfolg and not zweites.problematisch:
            return zweites
        ergebnis = fitte_neu(stapel, index, feld_unten=grenzen[0], feld_oben=grenzen[1],
                             B_res_vorgabe=b_start, bestaetigen=bestaetigen, mode=mode,
                             linescan=linescan)
    return ergebnis

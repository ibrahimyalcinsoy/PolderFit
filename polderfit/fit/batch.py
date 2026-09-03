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
from ..physik.fitmodell import Startwerte, s21_modell_multi, schaetze_startwerte_multi
from .auswahl import Auswertungsauswahl
from .autowindows import auto_fenster_alle, fenster_aus_trasse, schneide_band
from .kriterien import ALPHA_MAX
from .linescan_fit import FitErgebnis, fitte_linescan, setze_bewertung

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
    #: Anzahl simultan gefitteter Resonanzen je Linescan (1 = Standard).
    n_moden: int = 1
    #: Auto-Fit lief zweistufig (klassisch, danach Moden ergaenzt; siehe fitte_alle).
    zweistufig: bool = False
    #: Manuelle Nachfits automatisch als "gut - vom Nutzer bestaetigt" bewerten.
    nachfit_bestaetigen: bool = True
    fenster: list[tuple[float, float]] = field(default_factory=list)
    ergebnisse: list[FitErgebnis] = field(default_factory=list)
    zugeschnitten: list[Linescan] = field(default_factory=list)
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

    def bewerte(self, index: int, bewertung: str) -> FitErgebnis:
        """Setzt die Nutzer-Bewertung des Fits ``index`` (Kopie, Undo-sicher)."""
        neu = setze_bewertung(self.ergebnisse[index], bewertung)
        self.ergebnisse[index] = neu
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
    n_moden: int = 1,
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
                              alpha_plausibel=alpha_plausibel, n_moden=n_moden)
    eng = nachfenster(linescan, ergebnis, (unten, oben), nachfenster_faktor)
    if eng is None:
        return ergebnis, beschnitten, (unten, oben)
    beschnitten2 = schneide_band(linescan, eng[0], eng[1])
    ergebnis2 = fitte_linescan(beschnitten2, gamma, alpha_max=alpha_max,
                               alpha_plausibel=alpha_plausibel, n_moden=n_moden)
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
    n_moden: int = 1,
    nachfit_bestaetigen: bool = True,
    fortschritt_fenster=None,
    abbruch=None,
    zweistufig: bool = False,
    fortschritt_moden=None,
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
    ``zweistufig`` (nur bei ``n_moden > 1``): Stufe 1 ist der klassische
    Ein-Moden-Auto-Fit (robuste Fenstersuche, Hauptmode), Stufe 2 ergaenzt je
    Linescan weitere Resonanzen (:func:`ergaenze_moden`; Fortschritt ueber
    ``fortschritt_moden(i, n, ergebnis)``). Gelingt Stufe 2 an einem Linescan
    nicht, bleibt dort das klassische Ergebnis stehen.
    """
    if auswahl is not None and not auswahl.ist_neutral:
        datensatz, indizes = auswahl.reduziere(datensatz)
        if zentren is not None:
            zentren = np.asarray(zentren)[indizes]

    if zentren is not None:
        fenster = fenster_aus_trasse(datensatz, zentren, gamma, breite_faktor,
                                     alpha_erwartet=alpha_erwartet)
    else:
        fenster = auto_fenster_alle(datensatz, gamma, breite_faktor,
                                    fortschritt=fortschritt_fenster)
    stapel = StapelErgebnis(
        datensatz=datensatz, gamma=gamma, r2_schwelle=r2_schwelle, fenster=fenster,
        alpha_max=alpha_max, nachfenster_faktor=nachfenster_faktor,
        alpha_plausibel=alpha_plausibel, n_moden=max(1, int(n_moden)),
        nachfit_bestaetigen=nachfit_bestaetigen,
    )
    n = len(datensatz.linescans)
    zweistufig_aktiv = bool(zweistufig) and stapel.n_moden > 1
    fenster_auto = list(fenster)   # stapel.fenster wird unten je Index ueberschrieben
    for i, ls in enumerate(datensatz.linescans):
        if abbruch is not None and abbruch():
            # Rest als Platzhalter: der Stapel bleibt konsistent und nutzbar.
            for rest in datensatz.linescans[i:]:
                stapel.zugeschnitten.append(rest)
                stapel.ergebnisse.append(FitErgebnis.platzhalter(rest.frequenz, rest.feld))
            break
        ergebnis, beschnitten, verwendet = fitte_mit_nachfenster(
            ls, fenster[i], gamma, alpha_max=alpha_max,
            nachfenster_faktor=nachfenster_faktor, alpha_plausibel=alpha_plausibel,
            n_moden=1 if zweistufig_aktiv else stapel.n_moden)
        stapel.fenster[i] = verwendet
        stapel.zugeschnitten.append(beschnitten)
        stapel.ergebnisse.append(ergebnis)
        if fortschritt is not None:
            fortschritt(i, n, ergebnis)
    if zweistufig_aktiv:
        stapel.zweistufig = True
        for i in range(len(stapel.ergebnisse)):
            if abbruch is not None and abbruch():
                break
            ergebnis = ergaenze_moden(stapel, i, stapel.n_moden, fenster=fenster_auto[i])
            if fortschritt_moden is not None:
                fortschritt_moden(i, n, ergebnis)
    return stapel


#: Stufe 2 des zweistufigen Auto-Fits: eine weitere Mode gilt nur als echt, wenn
#: das normierte Residuum um mindestens diesen Faktor unter dem Ein-Moden-Fit liegt.
PHANTOM_FAKTOR = 0.95


def ergaenze_moden(
    stapel: StapelErgebnis,
    index: int,
    n_moden: int,
    fenster: tuple[float, float] | None = None,
) -> FitErgebnis:
    """Stufe 2 des zweistufigen Auto-Fits: weitere Resonanzen ergaenzen.

    Ausgangspunkt ist das klassische Ein-Moden-Ergebnis an ``index``. Mode 1
    startet bei diesem Ergebnis, die ``n_moden - 1`` weiteren bei den Maxima
    des Residuums (Messung minus Mode 1, ausserhalb +-FWHM der Hauptmode);
    danach werden alle Moden simultan im Fenster ``fenster`` gefittet (Standard:
    Stapelfenster; das breitere von beiden gilt, damit Nachbarmoden Platz haben).

    Uebernommen wird der Mehr-Moden-Fit nur, wenn er erfolgreich, nicht
    problematisch, mit der klassischen Hauptmode vertraeglich
    (``|B_res - B_res_klassisch| <= max(FWHM, 2 Feldschritte)``) und deutlich
    besser als der Ein-Moden-Fit im selben Fenster ist (:data:`PHANTOM_FAKTOR`);
    unter mehreren Startwert-Kandidaten gewinnt das kleinste Residuum. Sonst bleibt
    das klassische Ergebnis unveraendert (``moden`` = nur die Hauptmode) -
    so entstehen auf Ein-Moden-Daten keine Phantom-Resonanzen. Liefert das
    Ergebnis am Index.
    """
    klassisch = stapel.ergebnisse[index]
    n_moden = max(1, int(n_moden))
    if (n_moden < 2 or not getattr(klassisch, "gefittet", True) or not klassisch.erfolg
            or not np.isfinite(klassisch.B_res)):
        return klassisch
    ls = stapel.datensatz.linescans[index]
    st_unten, st_oben = stapel.fenster[index]
    unten, oben = fenster if fenster is not None else (st_unten, st_oben)
    unten, oben = min(float(unten), float(st_unten)), max(float(oben), float(st_oben))
    beschnitten = schneide_band(ls, unten, oben)
    if stapel.ausschlusszonen:
        beschnitten = ohne_ausschlusszonen(beschnitten, stapel.ausschlusszonen)
    B = np.asarray(beschnitten.feld, dtype=float)
    if B.size < 4 * n_moden:
        return klassisch
    s21 = beschnitten.s21
    omega = 2.0 * np.pi * float(ls.frequenz)
    B_ref = float(np.mean(B))
    # Untergrund des klassischen Fits bezieht sich auf dessen Fenstermitte.
    B_ref_klassisch = float(np.mean(stapel.zugeschnitten[index].feld))
    untergrund = dict(
        off_re=float(klassisch.off_re + klassisch.slope_re * (B_ref - B_ref_klassisch)),
        off_im=float(klassisch.off_im + klassisch.slope_im * (B_ref - B_ref_klassisch)),
        slope_re=float(klassisch.slope_re), slope_im=float(klassisch.slope_im))
    mode1 = s21_modell_multi(B, [(klassisch.B_res, klassisch.alpha, klassisch.A, klassisch.phi)],
                             0.0, 0.0, 0.0, 0.0, omega, stapel.gamma, B_ref)
    rest = s21 - mode1
    fwhm = float(np.sqrt(3.0) * klassisch.dH) if np.isfinite(klassisch.dH) else 0.0
    schritt = float(np.ptp(B)) / max(B.size - 1, 1)
    toleranz = max(fwhm, 2.0 * schritt)
    maske = np.abs(B - klassisch.B_res) > toleranz
    grenzen = dict(B_min=float(B.min()), B_max=float(B.max()))
    seed = Startwerte(B_res=float(klassisch.B_res), alpha=float(klassisch.alpha),
                      A=float(klassisch.A), phi=float(klassisch.phi), **untergrund, **grenzen)

    # Startwert-Kandidaten fuer die weiteren Moden: (a) Rohdaten ausserhalb der
    # Hauptmode (unverzerrt, findet getrennte Nachbarlinien), (b) Residuum
    # ausserhalb, (c) Residuum im ganzen Fenster (ueberlappende Moden).
    versuche = []
    if np.count_nonzero(maske) >= 4 * (n_moden - 1):
        versuche += [(B[maske], s21[maske]), (B[maske], rest[maske])]
    versuche.append((B, rest))
    kandidaten: list[list[Startwerte]] = []
    for Bk, sk in versuche:
        try:
            weitere = schaetze_startwerte_multi(Bk, sk, omega, stapel.gamma, n_moden - 1,
                                                alpha_max=stapel.alpha_max)
        except Exception:
            continue
        starts = [seed] + [replace(sw, **untergrund, **grenzen) for sw in weitere]
        lage = tuple(round(sw.B_res / max(schritt, 1e-9)) for sw in starts[1:])
        if all(lage != tuple(round(sw.B_res / max(schritt, 1e-9)) for sw in k[1:]) for k in kandidaten):
            kandidaten.append(starts)
    if not kandidaten:
        return klassisch

    # Vergleichsbasis: Ein-Moden-Fit im SELBEN Fenster (Phantom-Filter).
    if (unten, oben) == (float(st_unten), float(st_oben)):
        basis = klassisch
    else:
        basis = fitte_linescan(beschnitten, stapel.gamma, startwerte=seed,
                               alpha_max=stapel.alpha_max, alpha_plausibel=stapel.alpha_plausibel,
                               n_moden=1)
    basis_rmse = float(basis.rmse_norm) if np.isfinite(basis.rmse_norm) else np.inf

    beste = None
    for starts in kandidaten:
        ergebnis = fitte_linescan(beschnitten, stapel.gamma, startwerte=starts,
                                  alpha_max=stapel.alpha_max, alpha_plausibel=stapel.alpha_plausibel,
                                  n_moden=n_moden)
        if not (ergebnis.erfolg and not ergebnis.problematisch and np.isfinite(ergebnis.B_res)
                and abs(ergebnis.B_res - klassisch.B_res) <= toleranz):
            continue
        if not (np.isfinite(ergebnis.rmse_norm) and ergebnis.rmse_norm <= PHANTOM_FAKTOR * basis_rmse):
            continue   # keine echte Verbesserung gegenueber einer Mode -> Phantom
        if beste is None or ergebnis.rmse_norm < beste.rmse_norm:
            beste = ergebnis
    if beste is None:
        return klassisch
    stapel.fenster[index] = (unten, oben)
    stapel.zugeschnitten[index] = beschnitten
    stapel.ergebnisse[index] = beste
    return beste


def leerer_stapel(
    datensatz: Messdatensatz,
    gamma: float = GAMMA_STANDARD,
    r2_schwelle: float = 0.9,
    alpha_max: float = ALPHA_MAX,
    nachfenster_faktor: float = NACHFENSTER_FAKTOR_STANDARD,
    alpha_plausibel: float | None = None,
    n_moden: int = 1,
    nachfit_bestaetigen: bool = True,
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
        alpha_plausibel=alpha_plausibel, n_moden=max(1, int(n_moden)),
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
    n_moden: int | None = None,
    bereiche: list | None = None,
) -> FitErgebnis:
    """Fittet einen einzelnen Datensatz neu (manuelles Nachfitten).

    Optional mit neuen Bandgrenzen, expliziten Startwerten oder nur neuem
    Resonanzfeld. Aktualisiert den Stapel an Position ``index`` und gibt das
    neue Ergebnis zurueck.

    ``bestaetigen``: das Ergebnis als "gut - vom Nutzer bestaetigt" bewerten
    (nur wenn der Fit ein Ergebnis liefert). ``None`` = Stapel-Einstellung
    ``nachfit_bestaetigen`` (Standard an: ein gezielter Eingriff an EINER
    Frequenz - Grenzen ziehen, Nochmal fitten - gilt als Freigabe des Nutzers;
    die Kriterien bleiben in ``problematisch_auto`` einsehbar). Bereichs-/
    Grenzgeraden-Fits ueber viele Frequenzen, Zonen-Nachrechnungen und das
    Wiederherstellen einer Sitzung uebergeben ``False``. ``n_moden``: Anzahl Resonanzen fuer diesen Fit
    (``None`` = Stapel-Einstellung). ``bereiche``: je Mode ``(lo, hi)``/``None`` -
    Feldbereich der jeweiligen Resonanz (Grenzgeraden-Baender je Mode).
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
        alpha_max=stapel.alpha_max, alpha_plausibel=stapel.alpha_plausibel,
        n_moden=stapel.n_moden if n_moden is None else max(1, int(n_moden)),
        bereiche=bereiche,
    )
    ergebnis.nachbearbeitet = True
    if bestaetigen is None:
        bestaetigen = bool(stapel.nachfit_bestaetigen)
    if bestaetigen:
        ergebnis = setze_bewertung(ergebnis, "bestaetigt")
    stapel.zugeschnitten[index] = beschnitten
    stapel.ergebnisse[index] = ergebnis
    return ergebnis

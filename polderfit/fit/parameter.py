# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Einstellbare physikalische Parameter der Auswertung (Datenklasse, GUI-frei).

Die Konventionen folgen Kap. 2 der Dissertation M. Mueller (2023) und dem
Protokoll: Felder als mu0*H in Tesla, ``gamma = g*mu_B/hbar`` in rad/(s*T)
(Gl. 2.24/2.26: Kittel; Gl. 2.28: Linienbreite). Der Nutzer stellt den
**g-Faktor** ein; gamma wird daraus abgeleitet und ueberall verwendet:
Einzelfits (Suszeptibilitaet, dH = 2*omega*alpha/gamma), Fenstersuche und
als Startwert (oder Festwert) des Kittel-Fits.

Die Klasse ist JSON-serialisierbar (:meth:`PhysikParameter.als_dict` /
:meth:`PhysikParameter.aus_dict`) und damit Teil der speicherbaren
Voreinstellungen (:mod:`polderfit.persistenz.einstellungen`) und der
Projektdatei. Der Dialog dazu: :mod:`polderfit.gui.parameter_dialog`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from .batch import NACHFENSTER_FAKTOR_STANDARD
from .kriterien import ALPHA_MAX
from ..physik.konstanten import G_FAKTOR_STANDARD, gamma_aus_g

#: Waehlbare Kittel-Geometrien.
GEOMETRIEN = ("oop", "ip")


@dataclass
class PhysikParameter:
    """Vom Nutzer einstellbare Parameter fuer Fit und Auswertung."""

    #: Lande-g-Faktor; ``gamma = g*mu_B/hbar`` folgt daraus.
    g_faktor: float = G_FAKTOR_STANDARD
    #: gamma im Kittel-Fit festhalten (nur mu0Meff fitten; oop).
    gamma_fest: bool = False
    #: Vorgabe der Kittel-Geometrie im Auswertungsfenster.
    geometrie: str = "oop"
    #: Fensterbreite der Automatik: Fenster = faktor * lokale FWHM.
    breite_faktor: float = 8.0
    #: R2-Schwelle der Einzelfit-Bewertung (sekundaeres Guetemass).
    r2_schwelle: float = 0.9
    #: R2-Mindestwert fuer die Punktauswahl der Kittel-/LLG-Auswertung.
    r2_min: float = 0.9
    #: Erwartete Daempfung alpha (Fensterbreite bei vorgegebener Trasse,
    #: Skript-API ``fitte_alle(zentren=...)``); in der GUI nicht mehr abgefragt.
    alpha_erwartet: float = 0.01
    #: Kittel-/LLG-Fits mit den 1-sigma-Einzelunsicherheiten gewichten
    #: (GUM/ABW: w = 1/u^2). Standard ``False`` = ungewichtete Ausgleichsrechnung
    #: (wie das LabVIEW-FTF; Benchmark-Ergebnis) – Gewichtung ist optional.
    gewichtet: bool = False
    #: Harte obere Schranke der Gilbert-Daempfung im Einzelfit. Standard 0.1;
    #: fuer sehr breite Resonanzen (z. B. FeCr2S4, alpha ~ 0.2-0.5) anheben.
    alpha_max: float = ALPHA_MAX
    #: Plausibilitaetsgrenze des Kriteriums "alpha unphysikalisch"; 0 = Automatik
    #: (= alpha_max/2). Fuer Proben mit real breiten Linien anheben.
    alpha_plausibel: float = 0.0
    #: Zweiter Fit-Durchgang: Fitfenster = B_res +/- Faktor * Linienbreite des
    #: ersten Durchgangs (0 = aus). Macht die Linienbreite fensterunabhaengig.
    nachfenster_faktor: float = NACHFENSTER_FAKTOR_STANDARD
    #: Anzahl simultan gefitteter Resonanzen je Linescan (1 = Standard;
    #: 2 = Doppel-Dip, z. B. nanostrukturiertes CoFe).
    n_moden: int = 1
    #: Auto-Fit bei n_moden > 1 zweistufig: erst klassischer Ein-Moden-Fit
    #: (robuste Fenstersuche, Hauptmode), dann weitere Resonanzen ergaenzen.
    auto_fit_zweistufig: bool = False
    #: Gezielte Einzel-Nachfits (Grenzen ziehen, Nochmal fitten) automatisch als
    #: "gut – vom Nutzer bestaetigt" bewerten (Bereichs-/Grenzgeraden-Fits ueber
    #: viele Frequenzen nicht - dort entscheiden die Kriterien).
    nachfit_bestaetigen: bool = True

    @property
    def gamma(self) -> float:
        """Gyromagnetisches Verhaeltnis in rad/(s*T) zum eingestellten g-Faktor."""
        return gamma_aus_g(self.g_faktor)

    @property
    def alpha_plausibel_wirksam(self) -> float | None:
        """Eingestellte Plausibilitaetsgrenze oder ``None`` (= Automatik)."""
        return float(self.alpha_plausibel) if self.alpha_plausibel > 0 else None

    def beschreibung(self) -> str:
        fest = ", γ fest" if self.gamma_fest else ""
        plausibel = (f"{self.alpha_plausibel:g}" if self.alpha_plausibel > 0
                     else f"auto ({self.alpha_max / 2:g})")
        moden = f", {self.n_moden} Moden" if self.n_moden > 1 else ""
        return (f"g={self.g_faktor:.4f} (γ={self.gamma:.4e} rad/(s·T)){fest}, "
                f"Geometrie {self.geometrie}, Fensterfaktor {self.breite_faktor:g}, "
                f"R²-Schwelle {self.r2_schwelle:g}, R²-Min (Kittel) {self.r2_min:g}, "
                f"α max {self.alpha_max:g}, α plausibel {plausibel}, "
                f"Nachfenster ±{self.nachfenster_faktor:g}·ΔH{moden}, "
                f"Kittel/LLG {'gewichtet' if self.gewichtet else 'ungewichtet'}, "
                f"Nachfits {'bestätigen' if self.nachfit_bestaetigen else 'automatisch bewerten'}")

    # --- Serialisierung -------------------------------------------------------
    def als_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def aus_dict(cls, daten: dict | None) -> "PhysikParameter":
        """Robust gegen fehlende/unbekannte Schluessel (aeltere Dateien)."""
        daten = dict(daten or {})
        erlaubt = {f.name: f.type for f in fields(cls)}
        werte = {}
        for name in erlaubt:
            if name in daten and daten[name] is not None:
                werte[name] = daten[name]
        p = cls(**werte)
        p.n_moden = max(1, int(p.n_moden))
        if p.geometrie not in GEOMETRIEN:
            p.geometrie = "oop"
        return p

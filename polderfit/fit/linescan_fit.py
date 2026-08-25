# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Einzel-Fit eines Linescans an die Polder-Suszeptibilitaet (Re+Im simultan).

Verwendet ``lmfit`` (nichtlineares Least-Squares, Levenberg-Marquardt) mit
datengetriebenen Startwerten und physikalisch sinnvollen Schranken. Liefert alle
Fitparameter samt Unsicherheiten, mehrere Guetemasse (normiertes Residuum,
reduziertes Chi-Quadrat, R²) sowie die automatische Problem-Einstufung.

Zusaetzlich zur automatischen Einstufung traegt jedes Ergebnis eine vom
Nutzer setzbare **Bewertung** (:func:`setze_bewertung`): ``"auto"`` (Kriterien
entscheiden), ``"bestaetigt"`` (gilt als gut - Standard nach jedem manuellen
Nachfit) oder ``"verworfen"`` (gilt als problematisch). ``problematisch`` ist
immer der WIRKSAME Zustand; ``problematisch_auto`` das reine Kriterienergebnis.

Mehrere Resonanzen je Linescan (``n_moden > 1``, z. B. zwei nahe Dips bei
nanostrukturiertem CoFe) werden simultan gefittet; die Hauptmode (groesste
Signalhoehe) fuellt die Felder des Ergebnisses, alle Moden stehen in ``moden``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
from lmfit import Parameters, minimize

from ..io.datensatz import Linescan
from ..physik.konstanten import GAMMA_STANDARD
from ..physik.fitmodell import (
    Startwerte,
    moden_aus_params,
    residuum,
    residuum_multi,
    s21_modell,
    s21_modell_multi,
    schaetze_startwerte,
    schaetze_startwerte_multi,
)
from ..physik.suszeptibilitaet import chi_oop
from .kriterien import (
    ALPHA_MAX,
    ALPHA_MIN,
    GRUND_NICHT_GEFITTET,
    PHI_MAX,
    PHI_MIN,
    bewerte_fit,
)

#: Zulaessige Nutzer-Bewertungen eines Fits.
BEWERTUNGEN = ("auto", "bestaetigt", "verworfen")
#: Klartexte der Bewertungen (GUI, Export).
BEWERTUNG_TEXTE = {
    "auto": "automatisch (Kriterien)",
    "bestaetigt": "gut – vom Nutzer bestätigt",
    "verworfen": "problematisch – vom Nutzer markiert",
}
#: Namen der Moden-Parameter (je Mode k: ``<name>_k``).
_MODEN_PARAMETER = ("B_res", "alpha", "A", "phi")


@dataclass
class FitErgebnis:
    """Ergebnis eines Linescan-Fits (alle Felder SI/Tesla).

    ``B_res``, ``alpha``, ``dH``, ``A``, ``phi`` (+ Fehler) gehoeren zur
    **Hauptmode**; bei ``n_moden > 1`` enthaelt ``moden`` je Mode ein dict mit
    denselben Schluesseln (Hauptmode zuerst).
    """

    frequenz: float
    erfolg: bool
    B_res: float = np.nan
    B_res_err: float = np.nan
    alpha: float = np.nan
    alpha_err: float = np.nan
    dH: float = np.nan          # mu0*DeltaH (Tesla)
    dH_err: float = np.nan      # 1-sigma von dH; dH = 2*omega*alpha/gamma ist
                                # linear in alpha -> dH_err = 2*omega*alpha_err/gamma
    A: float = np.nan
    A_err: float = np.nan
    phi: float = np.nan
    phi_err: float = np.nan
    off_re: float = np.nan
    off_im: float = np.nan
    slope_re: float = np.nan
    slope_im: float = np.nan
    # Guetemasse
    R2: float = np.nan
    rmse_norm: float = np.nan       # primaeres Mass: RMSE/Signalhub (kombiniert)
    rmse_norm_re: float = np.nan
    rmse_norm_im: float = np.nan
    chi2_red: float = np.nan        # reduziertes Chi-Quadrat
    signalhub: float = np.nan       # Signalhub nach Offset-/Gradient-Abzug
    # Fenster und Konvergenz
    B_fenster_min: float = np.nan
    B_fenster_max: float = np.nan
    kovarianz_ok: bool = False
    # Problem-Einstufung (wirksam) und Bewertung
    problematisch: bool = True
    problem_gruende: list = field(default_factory=list)
    #: Reines Kriterienergebnis (unabhaengig von der Nutzer-Bewertung).
    problematisch_auto: bool = True
    #: ``"auto"`` | ``"bestaetigt"`` | ``"verworfen"`` (siehe :func:`setze_bewertung`).
    bewertung: str = "auto"
    nachbearbeitet: bool = False
    #: ``False`` fuer Platzhalter (Frequenz noch nicht gefittet).
    gefittet: bool = True
    meldung: str = ""
    feld: np.ndarray = field(default=None, repr=False)
    fitkurve: np.ndarray = field(default=None, repr=False)
    temperatur: float | None = None
    # Mehrere Resonanzen
    n_moden: int = 1
    #: Je Mode: dict(B_res, B_res_err, alpha, alpha_err, dH, dH_err, A, A_err,
    #: phi, phi_err, hoehe); Hauptmode zuerst.
    moden: list = field(default_factory=list)
    #: Je Mode die Modellkurve (nur diese Mode + Untergrund), Hauptmode zuerst.
    fitkurven_moden: list = field(default=None, repr=False)

    # --- abgeleitete Groessen (Anzeige in mT) ------------------------------
    @property
    def dH_mT(self) -> float:
        """Linienbreite µ0ΔH in Millitesla (Anzeige/Export)."""
        return float(self.dH * 1e3) if np.isfinite(self.dH) else np.nan

    @property
    def dH_err_mT(self) -> float:
        return float(self.dH_err * 1e3) if np.isfinite(self.dH_err) else np.nan

    @property
    def B_res_mT(self) -> float:
        return float(self.B_res * 1e3) if np.isfinite(self.B_res) else np.nan

    @property
    def A_komplex(self) -> complex:
        """Komplexe Amplitude ``A·exp(iφ)`` der Hauptmode."""
        if not (np.isfinite(self.A) and np.isfinite(self.phi)):
            return complex(np.nan, np.nan)
        return complex(self.A * np.exp(1j * self.phi))

    @property
    def problem_text(self) -> str:
        """Kurzbegruendung fuer die Statuszeile (z. B. 'alpha an Grenze, ...')."""
        if self.bewertung == "bestaetigt" and not self.problematisch:
            return "vom Nutzer als gut bestätigt"
        if self.bewertung == "verworfen":
            return "vom Nutzer als problematisch markiert" + (
                f" ({', '.join(self.problem_gruende)})" if self.problem_gruende else "")
        return ", ".join(self.problem_gruende) if self.problem_gruende else "OK"

    @property
    def bewertung_text(self) -> str:
        return BEWERTUNG_TEXTE.get(self.bewertung, self.bewertung)

    @classmethod
    def platzhalter(cls, frequenz: float, feld: np.ndarray | None = None) -> "FitErgebnis":
        """Nicht gefittete Frequenz (z. B. ausserhalb des Grenzgeraden-Bereichs).

        Erscheint nirgends als Punkt, zaehlt weder als Problemfit noch geht
        sie in Kittel/LLG ein; Export kennzeichnet sie als 'nicht gefittet'.
        """
        erg = cls(frequenz=float(frequenz), erfolg=False, gefittet=False,
                  problematisch=True, problematisch_auto=True,
                  problem_gruende=[GRUND_NICHT_GEFITTET], meldung=GRUND_NICHT_GEFITTET,
                  feld=feld)
        if feld is not None and np.size(feld) >= 2:
            erg.B_fenster_min = float(np.min(feld))
            erg.B_fenster_max = float(np.max(feld))
        return erg

    def als_zeile(self, hauptmode_nur: bool = False) -> dict:
        """Flache dict-Darstellung fuer den Tabellen-/Excel-Export.

        Enthaelt alle Fitparameter (Hauptmode) in SI und zusaetzlich die
        Feldgroessen in **mT**, die komplexe Amplitude (Re/Im), Guetemasse,
        Fenster, Status/Bewertung und - bei ``n_moden > 1`` - die Parameter
        aller weiteren Moden (``*_2``, ``*_3``, …).
        """
        A_k = self.A_komplex
        zeile = {
            "frequenz_Hz": self.frequenz,
            "frequenz_GHz": self.frequenz / 1e9,
            "B_res_T": self.B_res,
            "B_res_err_T": self.B_res_err,
            "B_res_mT": self.B_res_mT,
            "alpha": self.alpha,
            "alpha_err": self.alpha_err,
            "mu0_dH_T": self.dH,
            "mu0_dH_err_T": self.dH_err,
            "mu0_dH_mT": self.dH_mT,
            "mu0_dH_err_mT": self.dH_err_mT,
            "A": self.A,
            "A_err": self.A_err,
            "phi_rad": self.phi,
            "phi_err_rad": self.phi_err,
            "phi_deg": float(np.degrees(self.phi)) if np.isfinite(self.phi) else np.nan,
            "A_komplex_re": A_k.real,
            "A_komplex_im": A_k.imag,
            "offset_re": self.off_re,
            "offset_im": self.off_im,
            "slope_re": self.slope_re,
            "slope_im": self.slope_im,
            "rmse_norm": self.rmse_norm,
            "rmse_norm_re": self.rmse_norm_re,
            "rmse_norm_im": self.rmse_norm_im,
            "chi2_red": self.chi2_red,
            "signalhub": self.signalhub,
            "R2": self.R2,
            "eins_minus_R2": 1.0 - self.R2 if np.isfinite(self.R2) else np.nan,
            "B_fenster_min_T": self.B_fenster_min,
            "B_fenster_max_T": self.B_fenster_max,
            "kovarianz_ok": self.kovarianz_ok,
            "temperatur_K": self.temperatur if self.temperatur is not None else np.nan,
            "nachbearbeitet": self.nachbearbeitet,
            "bewertung": self.bewertung,
            "gefittet": self.gefittet,
            "erfolg": self.erfolg,
            "problematisch": self.problematisch,
            "problematisch_auto": self.problematisch_auto,
            "problem_gruende": ", ".join(self.problem_gruende) if self.problem_gruende else "OK",
            "meldung": self.meldung,
            "n_moden": self.n_moden,
        }
        if not hauptmode_nur:
            for k, mode in enumerate(self.moden[1:], start=2):
                for name in ("B_res", "B_res_err", "alpha", "alpha_err", "dH", "dH_err",
                             "A", "A_err", "phi", "phi_err"):
                    wert = mode.get(name, np.nan)
                    if name.startswith("dH"):
                        spalte = f"mu0_{name}_{k}_T"
                        zeile[spalte] = wert
                        zeile[f"mu0_{name}_{k}_mT"] = wert * 1e3 if np.isfinite(wert) else np.nan
                    elif name.startswith("B_res"):
                        zeile[f"{name}_{k}_T"] = wert
                    elif name.startswith("phi"):
                        zeile[f"{name}_{k}_rad"] = wert
                    else:
                        zeile[f"{name}_{k}"] = wert
        return zeile


def setze_bewertung(erg: FitErgebnis, bewertung: str) -> FitErgebnis:
    """Liefert eine KOPIE des Ergebnisses mit neuer Nutzer-Bewertung.

    * ``"auto"``       – Kriterien entscheiden (``problematisch = problematisch_auto``)
    * ``"bestaetigt"`` – gilt als guter Fit (nur moeglich, wenn ueberhaupt ein
      Ergebnis mit endlichem ``B_res`` vorliegt; sonst bleibt "auto")
    * ``"verworfen"``  – gilt als problematisch

    Eine Kopie (statt Mutation), damit Undo-Schnappschuesse gueltig bleiben.
    """
    if bewertung not in BEWERTUNGEN:
        raise ValueError(f"Unbekannte Bewertung {bewertung!r} (erlaubt: {BEWERTUNGEN}).")
    if bewertung == "bestaetigt" and not (erg.gefittet and erg.erfolg and np.isfinite(erg.B_res)):
        bewertung = "auto"
    if bewertung == "auto":
        problematisch = bool(erg.problematisch_auto)
    else:
        problematisch = bewertung == "verworfen"
    return replace(erg, bewertung=bewertung, problematisch=problematisch)


def _rausch_sigma(werte: np.ndarray) -> float:
    """Robuste, fit-unabhaengige Rauschschaetzung aus zweiten Differenzen (MAD).

    Zweite Differenzen unterdruecken glatte Anteile (Offset, Gradient, breite
    Resonanz) und lassen vorwiegend das Messrauschen uebrig.
    """
    werte = np.asarray(werte, dtype=float)
    if werte.size < 5:
        return float(np.std(werte)) or 1.0
    d2 = werte[2:] - 2.0 * werte[1:-1] + werte[:-2]
    mad = np.median(np.abs(d2 - np.median(d2)))
    sigma = 1.4826 * mad / np.sqrt(6.0)  # Normierung der zweiten Differenz
    if sigma <= 0:
        sigma = float(np.std(werte)) or 1.0
    return float(sigma)


def _guetemasse(B, s21, kurve, p, B_ref, n_param):
    """Berechnet normiertes Residuum, reduziertes Chi² und R².

    Der Signalhub wird NACH Abzug von Offset und feldabhaengigem Gradienten
    bestimmt, damit die dominante Untergrund-Rampe das Mass nicht verfaelscht.
    """
    bg_re = p["off_re"].value + p["slope_re"].value * (B - B_ref)
    bg_im = p["off_im"].value + p["slope_im"].value * (B - B_ref)

    mess_re = s21.real - bg_re
    mess_im = s21.imag - bg_im
    res_re = kurve.real - s21.real
    res_im = kurve.imag - s21.imag

    def _norm(mess_ohne_bg, res):
        hub = float(np.max(mess_ohne_bg) - np.min(mess_ohne_bg))
        rmse = float(np.sqrt(np.mean(res ** 2)))
        return (rmse / hub) if hub > 0 else np.inf, hub

    rmse_norm_re, hub_re = _norm(mess_re, res_re)
    rmse_norm_im, hub_im = _norm(mess_im, res_im)

    mess_bg = np.concatenate([mess_re, mess_im])
    res = np.concatenate([res_re, res_im])
    signalhub = float(np.max(mess_bg) - np.min(mess_bg))
    rmse = float(np.sqrt(np.mean(res ** 2)))
    rmse_norm = (rmse / signalhub) if signalhub > 0 else np.inf

    # Reduziertes Chi²: Rauschen fit-unabhaengig aus den Rohdaten schaetzen.
    # Re und Im GETRENNT schaetzen und quadratisch mitteln – ein gemeinsamer
    # concatenate-Block wuerde an der Re/Im-Naht zwei kuenstliche zweite
    # Differenzen erzeugen (verschiedene Offsets/Steigungen von Re und Im).
    sigma_re = _rausch_sigma(s21.real)
    sigma_im = _rausch_sigma(s21.imag)
    sigma = float(np.sqrt(0.5 * (sigma_re ** 2 + sigma_im ** 2)))
    dof = max(res.size - n_param, 1)
    chi2_red = float(np.sum(res ** 2) / (sigma ** 2) / dof)

    # R² (sekundaer) ueber Re+Im gemeinsam.
    mess = np.concatenate([s21.real, s21.imag])
    modell = np.concatenate([kurve.real, kurve.imag])
    ss_res = float(np.sum((mess - modell) ** 2))
    ss_tot = float(np.sum((mess - np.mean(mess)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return dict(
        rmse_norm=rmse_norm, rmse_norm_re=rmse_norm_re, rmse_norm_im=rmse_norm_im,
        chi2_red=chi2_red, signalhub=signalhub, R2=r2,
    )


def _abschliessen(erg: FitErgebnis, alpha_max: float,
                  alpha_plausibel: float | None) -> FitErgebnis:
    """Kriterien anwenden; ``problematisch_auto`` = reines Kriterienergebnis."""
    erg.problematisch, erg.problem_gruende = bewerte_fit(
        erg, alpha_max=alpha_max, alpha_plausibel=alpha_plausibel)
    erg.problematisch_auto = erg.problematisch
    erg.bewertung = "auto"
    return erg


def fitte_linescan(
    linescan: Linescan,
    gamma: float = GAMMA_STANDARD,
    startwerte: Startwerte | None = None,
    B_res_vorgabe: float | None = None,
    alpha_max: float = ALPHA_MAX,
    alpha_plausibel: float | None = None,
    n_moden: int = 1,
) -> FitErgebnis:
    """Fittet einen (i. d. R. bereits zugeschnittenen) Linescan.

    ``startwerte`` koennen vorgegeben werden (manuelles Nachfitten); sonst werden
    sie aus den Daten geschaetzt. ``B_res_vorgabe`` setzt nur das Resonanzfeld.
    Schranken sind physikalisch begrenzt (siehe :mod:`polderfit.fit.kriterien`);
    insbesondere MUSS ``B_res`` innerhalb des ausgeschnittenen Feldfensters liegen.
    ``alpha_max`` ist die harte obere alpha-Schranke (Standard ``ALPHA_MAX`` =
    0.1; fuer sehr breite Resonanzen wie FeCr2S4 mit alpha ~ 0.2-0.5 anhebbar –
    Benchmark gegen das LabVIEW-FTF: auf gleichem Fenster identische Ergebnisse,
    sobald die Schranke nicht mehr greift). ``alpha_plausibel`` (optional)
    ersetzt die Plausibilitaetsgrenze ``alpha_max/2`` des Kriteriums
    "alpha unphysikalisch". ``n_moden > 1`` fittet mehrere Resonanzen simultan
    (:func:`fitte_linescan_multi`).
    """
    if not np.isfinite(alpha_max) or alpha_max <= ALPHA_MIN:
        alpha_max = ALPHA_MAX
    if int(n_moden) > 1:
        return fitte_linescan_multi(linescan, gamma, n_moden=int(n_moden),
                                    alpha_max=alpha_max, alpha_plausibel=alpha_plausibel)
    omega = 2.0 * np.pi * linescan.frequenz
    B = linescan.feld
    s21 = linescan.s21
    B_ref = float(np.mean(B))
    B_min, B_max = float(B.min()), float(B.max())

    if startwerte is None:
        startwerte = schaetze_startwerte(B, s21, omega, gamma, B_res_vorgabe,
                                         alpha_max=alpha_max)

    sw = startwerte
    temperatur = linescan.temperatur_mittel()

    # Startwerte in die Schranken zwingen (kein Start exakt auf einer Grenze).
    b_res_start = float(np.clip(sw.B_res, B_min, B_max))
    alpha_start = float(np.clip(sw.alpha, ALPHA_MIN * 1.1, alpha_max * 0.9))
    phi_start = float(np.clip(sw.phi, PHI_MIN + 1e-6, PHI_MAX - 1e-6))

    def _minimiere(phi_wert: float):
        params = Parameters()
        # B_res MUSS im Feldfenster liegen (Defekt 1).
        params.add("B_res", value=b_res_start, min=B_min, max=B_max)
        params.add("alpha", value=alpha_start, min=ALPHA_MIN, max=alpha_max)
        params.add("A", value=sw.A)
        params.add("phi", value=phi_wert, min=PHI_MIN, max=PHI_MAX)
        params.add("off_re", value=sw.off_re)
        params.add("off_im", value=sw.off_im)
        params.add("slope_re", value=sw.slope_re)
        params.add("slope_im", value=sw.slope_im)
        return minimize(
            residuum, params, method="leastsq",
            args=(B, s21, omega, gamma, B_ref),
        )

    def _hat_unsicherheiten(mini) -> bool:
        return bool(getattr(mini, "errorbars", False)) and \
            mini.params["B_res"].stderr is not None

    try:
        ergebnis = _minimiere(phi_start)
    except Exception as exc:  # numerisch fehlgeschlagen
        erg = FitErgebnis(
            frequenz=linescan.frequenz, erfolg=False, meldung=f"Fit-Fehler: {exc}",
            B_fenster_min=B_min, B_fenster_max=B_max, kovarianz_ok=False,
            feld=B, temperatur=temperatur,
        )
        return _abschliessen(erg, alpha_max, alpha_plausibel)

    # phi-Nebenminimum-Ausweg: Der phi-Startwert aus der Schaetzung kann um pi
    # daneben liegen; der Fit landet dann in einem Nebenminimum, dessen
    # Jacobi-Matrix singulaer wird (lmfit liefert keine Unsicherheiten). In dem
    # Fall einmal mit um pi verschobenem phi-Start neu starten und das bessere
    # Ergebnis behalten (Unsicherheiten vorhanden > kleineres Chi-Quadrat).
    if not _hat_unsicherheiten(ergebnis):
        phi_alternative = phi_start - np.pi if phi_start > 0 else phi_start + np.pi
        try:
            zweite = _minimiere(phi_alternative)
        except Exception:
            zweite = None
        if zweite is not None and (
            _hat_unsicherheiten(zweite)
            or getattr(zweite, "chisqr", np.inf) < getattr(ergebnis, "chisqr", np.inf)
        ):
            ergebnis = zweite

    p = ergebnis.params
    kurve = s21_modell(
        B, p["B_res"].value, p["alpha"].value, p["A"].value, p["phi"].value,
        p["off_re"].value, p["off_im"].value, p["slope_re"].value, p["slope_im"].value,
        omega, gamma, B_ref,
    )

    masse = _guetemasse(B, s21, kurve, p, B_ref, n_param=len(p))

    def _err(name):
        par = p[name]
        return float(par.stderr) if par.stderr is not None else np.nan

    # Kovarianz/Unsicherheiten vorhanden? (lmfit setzt errorbars).
    kovarianz_ok = bool(getattr(ergebnis, "errorbars", False)) and p["B_res"].stderr is not None

    erg = FitErgebnis(
        frequenz=linescan.frequenz,
        erfolg=bool(ergebnis.success),
        B_res=float(p["B_res"].value), B_res_err=_err("B_res"),
        alpha=float(p["alpha"].value), alpha_err=_err("alpha"),
        dH=2.0 * omega * float(p["alpha"].value) / gamma,
        dH_err=2.0 * omega * _err("alpha") / gamma,
        A=float(p["A"].value), A_err=_err("A"),
        phi=float(p["phi"].value), phi_err=_err("phi"),
        off_re=float(p["off_re"].value), off_im=float(p["off_im"].value),
        slope_re=float(p["slope_re"].value), slope_im=float(p["slope_im"].value),
        B_fenster_min=B_min, B_fenster_max=B_max,
        kovarianz_ok=kovarianz_ok,
        meldung=ergebnis.message if hasattr(ergebnis, "message") else "",
        feld=B, fitkurve=kurve, temperatur=temperatur,
        **masse,
    )
    erg.moden = [{
        "B_res": erg.B_res, "B_res_err": erg.B_res_err, "alpha": erg.alpha,
        "alpha_err": erg.alpha_err, "dH": erg.dH, "dH_err": erg.dH_err,
        "A": erg.A, "A_err": erg.A_err, "phi": erg.phi, "phi_err": erg.phi_err,
        "hoehe": float(abs(erg.A) * abs(chi_oop(np.array([erg.B_res]), erg.B_res,
                                                    erg.alpha, omega, gamma))[0]),
    }]
    erg.fitkurven_moden = [kurve]
    return _abschliessen(erg, alpha_max, alpha_plausibel)


def fitte_linescan_multi(
    linescan: Linescan,
    gamma: float = GAMMA_STANDARD,
    n_moden: int = 2,
    alpha_max: float = ALPHA_MAX,
    alpha_plausibel: float | None = None,
    startwerte: list[Startwerte] | None = None,
) -> FitErgebnis:
    """Fittet ``n_moden`` Resonanzen SIMULTAN in einem Linescan.

    Parametrisierung: ``B_res_1`` frei im Fenster, ``B_res_k = B_res_(k-1) +
    dB_k`` mit ``dB_k >= 2 Feldschritte`` (verhindert das Zusammenfallen und
    Vertauschen der Moden). Untergrund (Offset, Steigung) ist gemeinsam.
    Die Hauptmode (groesste Signalhoehe |A|·|χ(B_res)|) fuellt die Felder
    des :class:`FitErgebnis`; ``moden`` enthaelt alle Moden, Hauptmode zuerst,
    ``fitkurven_moden`` je Mode die Kurve "diese Mode + Untergrund".
    """
    n_moden = int(n_moden)
    if n_moden < 1:
        raise ValueError("n_moden muss >= 1 sein.")
    if not np.isfinite(alpha_max) or alpha_max <= ALPHA_MIN:
        alpha_max = ALPHA_MAX
    omega = 2.0 * np.pi * linescan.frequenz
    B = np.asarray(linescan.feld, dtype=float)
    s21 = linescan.s21
    B_ref = float(np.mean(B))
    B_min, B_max = float(B.min()), float(B.max())
    temperatur = linescan.temperatur_mittel()
    schritt = float(np.ptp(B)) / max(B.size - 1, 1)
    min_abstand = max(2.0 * schritt, 1e-6)

    def _fehlschlag(text: str) -> FitErgebnis:
        erg = FitErgebnis(frequenz=linescan.frequenz, erfolg=False, meldung=text,
                          B_fenster_min=B_min, B_fenster_max=B_max, feld=B,
                          temperatur=temperatur, n_moden=n_moden)
        return _abschliessen(erg, alpha_max, alpha_plausibel)

    try:
        starts = (sorted(startwerte, key=lambda sw: sw.B_res) if startwerte
                  else schaetze_startwerte_multi(B, s21, omega, gamma, n_moden,
                                                 alpha_max=alpha_max))
    except Exception as exc:
        return _fehlschlag(f"Startwerte: {exc}")
    if len(starts) != n_moden:
        return _fehlschlag(f"{len(starts)} Startwerte fuer {n_moden} Moden.")

    def _params(phi_offsets):
        params = Parameters()
        vorher = None
        for k, sw in enumerate(starts, start=1):
            b = float(np.clip(sw.B_res, B_min, B_max))
            if k == 1:
                params.add("B_res_1", value=b, min=B_min, max=B_max)
            else:
                d = max(b - vorher, min_abstand * 1.5)
                params.add(f"dB_{k}", value=d, min=min_abstand, max=max(B_max - B_min, min_abstand * 2))
                params.add(f"B_res_{k}", expr=f"B_res_{k-1} + dB_{k}")
            vorher = b if k == 1 else vorher + max(b - vorher, min_abstand * 1.5)
            params.add(f"alpha_{k}", value=float(np.clip(sw.alpha, ALPHA_MIN * 1.1, alpha_max * 0.9)),
                       min=ALPHA_MIN, max=alpha_max)
            params.add(f"A_{k}", value=sw.A)
            params.add(f"phi_{k}", value=float(np.clip(sw.phi + phi_offsets[k - 1],
                                                       PHI_MIN + 1e-6, PHI_MAX - 1e-6)),
                       min=PHI_MIN, max=PHI_MAX)
        sw0 = starts[0]
        params.add("off_re", value=sw0.off_re)
        params.add("off_im", value=sw0.off_im)
        params.add("slope_re", value=sw0.slope_re)
        params.add("slope_im", value=sw0.slope_im)
        return params

    def _minimiere(phi_offsets):
        return minimize(residuum_multi, _params(phi_offsets), method="leastsq",
                        args=(B, s21, omega, gamma, B_ref, n_moden))

    def _hat_unsicherheiten(mini) -> bool:
        return bool(getattr(mini, "errorbars", False)) and \
            mini.params["B_res_1"].stderr is not None

    try:
        ergebnis = _minimiere([0.0] * n_moden)
    except Exception as exc:
        return _fehlschlag(f"Fit-Fehler: {exc}")
    if not _hat_unsicherheiten(ergebnis):
        # phi-Nebenminimum (wie im Ein-Moden-Fall): alle Phasen um pi drehen.
        try:
            zweite = _minimiere([np.pi] * n_moden)
        except Exception:
            zweite = None
        if zweite is not None and (
            _hat_unsicherheiten(zweite)
            or getattr(zweite, "chisqr", np.inf) < getattr(ergebnis, "chisqr", np.inf)
        ):
            ergebnis = zweite

    p = ergebnis.params
    moden_tupel = moden_aus_params(p, n_moden)
    off = (float(p["off_re"]), float(p["off_im"]), float(p["slope_re"]), float(p["slope_im"]))
    kurve = s21_modell_multi(B, moden_tupel, *off, omega, gamma, B_ref)
    n_frei = sum(1 for q in p.values() if q.vary)
    masse = _guetemasse(B, s21, kurve, p, B_ref, n_param=n_frei)

    def _err(name):
        par = p[name]
        return float(par.stderr) if par.stderr is not None else np.nan

    moden = []
    kurven = []
    for k, (b_res, alpha, A, phi) in enumerate(moden_tupel, start=1):
        hoehe = float(abs(A) * abs(chi_oop(np.array([b_res]), b_res, alpha, omega, gamma))[0])
        moden.append({
            "B_res": b_res, "B_res_err": _err(f"B_res_{k}"),
            "alpha": alpha, "alpha_err": _err(f"alpha_{k}"),
            "dH": 2.0 * omega * alpha / gamma, "dH_err": 2.0 * omega * _err(f"alpha_{k}") / gamma,
            "A": A, "A_err": _err(f"A_{k}"), "phi": phi, "phi_err": _err(f"phi_{k}"),
            "hoehe": hoehe,
        })
        kurven.append(s21_modell_multi(B, [(b_res, alpha, A, phi)], *off, omega, gamma, B_ref))
    # Hauptmode = groesste Signalhoehe; Reihenfolge danach nach B_res.
    haupt = int(np.argmax([m["hoehe"] for m in moden]))
    reihenfolge = [haupt] + [i for i in range(n_moden) if i != haupt]
    moden = [moden[i] for i in reihenfolge]
    kurven = [kurven[i] for i in reihenfolge]
    h = moden[0]
    kovarianz_ok = _hat_unsicherheiten(ergebnis)
    erg = FitErgebnis(
        frequenz=linescan.frequenz, erfolg=bool(ergebnis.success),
        B_res=h["B_res"], B_res_err=h["B_res_err"], alpha=h["alpha"], alpha_err=h["alpha_err"],
        dH=h["dH"], dH_err=h["dH_err"], A=h["A"], A_err=h["A_err"], phi=h["phi"], phi_err=h["phi_err"],
        off_re=off[0], off_im=off[1], slope_re=off[2], slope_im=off[3],
        B_fenster_min=B_min, B_fenster_max=B_max, kovarianz_ok=kovarianz_ok,
        meldung=ergebnis.message if hasattr(ergebnis, "message") else "",
        feld=B, fitkurve=kurve, temperatur=temperatur, n_moden=n_moden,
        moden=moden, fitkurven_moden=kurven, **masse,
    )
    return _abschliessen(erg, alpha_max, alpha_plausibel)


def hauptmode_wechseln(erg: FitErgebnis, index: int) -> FitErgebnis:
    """Kopie des Ergebnisses, in der Mode ``index`` (Position in ``erg.moden``)
    zur Hauptmode wird (fuellt B_res/alpha/dH/A/phi; Reihenfolge rotiert)."""
    if not erg.moden or not (0 <= index < len(erg.moden)) or index == 0:
        return erg
    reihenfolge = [index] + [i for i in range(len(erg.moden)) if i != index]
    moden = [dict(erg.moden[i]) for i in reihenfolge]
    kurven = ([erg.fitkurven_moden[i] for i in reihenfolge]
              if erg.fitkurven_moden is not None else None)
    h = moden[0]
    return replace(erg, moden=moden, fitkurven_moden=kurven,
                   B_res=h["B_res"], B_res_err=h["B_res_err"], alpha=h["alpha"],
                   alpha_err=h["alpha_err"], dH=h["dH"], dH_err=h["dH_err"],
                   A=h["A"], A_err=h["A_err"], phi=h["phi"], phi_err=h["phi_err"])

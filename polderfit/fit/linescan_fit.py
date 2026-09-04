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

Mehrere Resonanzen je Linescan werden NICHT als Summe gefittet, sondern je
Mode als Einzelfit auf den Messpunkten ihres Korridors
(:mod:`polderfit.fit.korridor`); ``mode`` nennt die Mode des Ergebnisses.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
from lmfit import Parameters, minimize

from ..io.datensatz import Linescan
from ..physik.konstanten import GAMMA_STANDARD
from ..physik.fitmodell import (Startwerte, moden_aus_params, residuum, residuum_multi,
                                s21_modell, s21_modell_multi, schaetze_startwerte)
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
@dataclass
class FitErgebnis:
    """Ergebnis eines Linescan-Fits (alle Felder SI/Tesla) fuer EINE Mode."""

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
    #: Mode (Korridor-Nummer) dieses Ergebnisses; 1 = Hauptmode.
    mode: int = 1
    #: Nur Summenfit: Einzelbeitraege ``[(mode, kurve_nur_diese_Linie_plus_Untergrund)]``
    #: aller Dips des Korridors (Anzeige gestrichelt im Linescan-Panel).
    beitraege: list = field(default=None, repr=False)

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
    def platzhalter(cls, frequenz: float, feld: np.ndarray | None = None,
                    mode: int = 1) -> "FitErgebnis":
        """Nicht gefittete Frequenz (z. B. ausserhalb des Grenzgeraden-Bereichs).

        Erscheint nirgends als Punkt, zaehlt weder als Problemfit noch geht
        sie in Kittel/LLG ein; Export kennzeichnet sie als 'nicht gefittet'.
        """
        erg = cls(frequenz=float(frequenz), erfolg=False, gefittet=False,
                  problematisch=True, problematisch_auto=True,
                  problem_gruende=[GRUND_NICHT_GEFITTET], meldung=GRUND_NICHT_GEFITTET,
                  feld=feld, mode=max(1, int(mode)))
        if feld is not None and np.size(feld) >= 2:
            erg.B_fenster_min = float(np.min(feld))
            erg.B_fenster_max = float(np.max(feld))
        return erg

    def als_zeile(self, hauptmode_nur: bool = False) -> dict:
        """Flache dict-Darstellung fuer den Tabellen-/Excel-Export.

        Enthaelt alle Fitparameter in SI und zusaetzlich die Feldgroessen in
        **mT**, die komplexe Amplitude (Re/Im), Guetemasse, Fenster,
        Status/Bewertung und die Mode-Nummer. ``hauptmode_nur`` wird aus
        Kompatibilitaet akzeptiert und ignoriert.
        """
        A_k = self.A_komplex
        zeile = {
            "frequenz_Hz": self.frequenz,
            "frequenz_GHz": self.frequenz / 1e9,
            "B_res_T": self.B_res,
            "B_res_err_T": self.B_res_err,
            "B_res_err_mT": float(self.B_res_err * 1e3) if np.isfinite(self.B_res_err) else np.nan,
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
            "mode": int(self.mode),
        }
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
    mode: int = 1,
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
    "alpha unphysikalisch". ``mode``: Mode-Nummer, die das Ergebnis traegt.
    """
    if not np.isfinite(alpha_max) or alpha_max <= ALPHA_MIN:
        alpha_max = ALPHA_MAX
    mode = max(1, int(mode))
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
            feld=B, temperatur=temperatur, mode=mode,
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
        feld=B, fitkurve=kurve, temperatur=temperatur, mode=mode,
        **masse,
    )
    return _abschliessen(erg, alpha_max, alpha_plausibel)


def fitte_linescan_summe(
    linescan: Linescan,
    gamma: float,
    segmente: list,
    starts: list,
    moden: list,
    alpha_max: float = ALPHA_MAX,
    alpha_plausibel: float | None = None,
) -> list:
    """Summenfit von ``n = len(segmente)`` Polder-Linien auf dem (bereits auf den
    Korridor beschnittenen) Linescan mit HARTEN Schranken: ``B_res_k`` darf nur
    innerhalb seines Segments ``segmente[k]`` liegen (Hard Crop aus
    :func:`polderfit.fit.korridor.dip_segmente`), ``alpha_k`` in
    ``[ALPHA_MIN, alpha_max]``; gemeinsamer linearer Untergrund. Startwerte
    ``starts[k]`` = :class:`FitErgebnis` der Einzelfits je Segment (oder None).

    Liefert je Mode ein :class:`FitErgebnis` (``mode = moden[k]``) mit den
    Parametern dieser Linie, der Summenkurve als ``fitkurve`` und den Guetemassen
    des Gesamtfits; ``B_fenster_min/max`` = Segmentgrenzen. Im Gegensatz zum
    freien Summenfit ueber den ganzen Sweep ist das Problem durch Korridor und
    Segment-Schranken gut konditioniert.
    """
    if not np.isfinite(alpha_max) or alpha_max <= ALPHA_MIN:
        alpha_max = ALPHA_MAX
    n = len(segmente)
    omega = 2.0 * np.pi * linescan.frequenz
    B = np.asarray(linescan.feld, dtype=float)
    s21 = np.asarray(linescan.s21)
    B_ref = float(np.mean(B))
    temperatur = linescan.temperatur_mittel()

    params = Parameters()
    off_re = off_im = slope_re = slope_im = None
    for k, (lo, hi) in enumerate(segmente, start=1):
        st = starts[k - 1] if k - 1 < len(starts) else None
        if st is not None and st.gefittet and np.isfinite(st.B_res):
            b0, a0, A0, phi0 = float(st.B_res), float(st.alpha), float(st.A), float(st.phi)
            if off_re is None and np.isfinite(st.off_re):
                off_re, off_im, slope_re, slope_im = st.off_re, st.off_im, st.slope_re, st.slope_im
        else:
            sw = schaetze_startwerte(B[(B >= lo) & (B <= hi)], s21[(B >= lo) & (B <= hi)],
                                     omega, gamma, None, alpha_max=alpha_max)
            b0, a0, A0, phi0 = sw.B_res, sw.alpha, sw.A, sw.phi
        params.add(f"B_res_{k}", value=float(np.clip(b0, lo, hi)), min=lo, max=hi)
        params.add(f"alpha_{k}", value=float(np.clip(a0, ALPHA_MIN * 1.1, alpha_max * 0.9)),
                   min=ALPHA_MIN, max=alpha_max)
        params.add(f"A_{k}", value=float(A0))
        params.add(f"phi_{k}", value=float(np.clip(phi0, PHI_MIN + 1e-6, PHI_MAX - 1e-6)),
                   min=PHI_MIN, max=PHI_MAX)
    if off_re is None:
        sw = schaetze_startwerte(B, s21, omega, gamma, None, alpha_max=alpha_max)
        off_re, off_im, slope_re, slope_im = sw.off_re, sw.off_im, sw.slope_re, sw.slope_im
    params.add("off_re", value=float(off_re))
    params.add("off_im", value=float(off_im))
    params.add("slope_re", value=float(slope_re))
    params.add("slope_im", value=float(slope_im))

    ergebnis = minimize(residuum_multi, params, method="leastsq",
                        args=(B, s21, omega, gamma, B_ref, n))
    p = ergebnis.params
    kurve = s21_modell_multi(B, moden_aus_params(p, n), p["off_re"].value, p["off_im"].value,
                             p["slope_re"].value, p["slope_im"].value, omega, gamma, B_ref)
    masse = _guetemasse(B, s21, kurve, p, B_ref, n_param=len(p))
    kovarianz_ok = bool(getattr(ergebnis, "errorbars", False)) and p["B_res_1"].stderr is not None

    def _err(name):
        par = p[name]
        return float(par.stderr) if par.stderr is not None else np.nan

    untergrund = kurve - s21_modell_multi(B, moden_aus_params(p, n), 0.0, 0.0, 0.0, 0.0,
                                          omega, gamma, B_ref)
    beitraege = []
    for k, (b_k, a_k, A_k, phi_k) in enumerate(moden_aus_params(p, n), start=1):
        einzel = s21_modell_multi(B, [(b_k, a_k, A_k, phi_k)], 0.0, 0.0, 0.0, 0.0,
                                  omega, gamma, B_ref) + untergrund
        beitraege.append((int(moden[k - 1]), einzel))
    resultate = []
    for k, (lo, hi) in enumerate(segmente, start=1):
        erg = FitErgebnis(
            frequenz=linescan.frequenz, erfolg=bool(ergebnis.success),
            B_res=float(p[f"B_res_{k}"].value), B_res_err=_err(f"B_res_{k}"),
            alpha=float(p[f"alpha_{k}"].value), alpha_err=_err(f"alpha_{k}"),
            dH=2.0 * omega * float(p[f"alpha_{k}"].value) / gamma,
            dH_err=2.0 * omega * _err(f"alpha_{k}") / gamma,
            A=float(p[f"A_{k}"].value), A_err=_err(f"A_{k}"),
            phi=float(p[f"phi_{k}"].value), phi_err=_err(f"phi_{k}"),
            off_re=float(p["off_re"].value), off_im=float(p["off_im"].value),
            slope_re=float(p["slope_re"].value), slope_im=float(p["slope_im"].value),
            B_fenster_min=float(lo), B_fenster_max=float(hi), kovarianz_ok=kovarianz_ok,
            meldung=getattr(ergebnis, "message", ""), feld=B, fitkurve=kurve,
            temperatur=temperatur, mode=int(moden[k - 1]), beitraege=beitraege, **masse,
        )
        resultate.append(_abschliessen(erg, alpha_max, alpha_plausibel))
    return resultate

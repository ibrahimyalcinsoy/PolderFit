"""Linescan-Fitmodell: komplexes S21-Signal als Funktion des Feldes.

Pro Frequenz (festes ``omega = 2*pi*f``) wird das komplexe S21-Signal ueber das
gewaehlte Feldband modelliert::

    S21(B) = A*exp(i*phi) * chi_oop(B; B_res, alpha, omega, gamma)
             + (off_re + i*off_im)
             + (slope_re + i*slope_im) * (B - B_ref)

mit:

* ``A``, ``phi``     – komplexer Vorfaktor (Amplitude + Phase); faengt das
                        frequenzabhaengige Peak/Dip-Verhalten ab.
* ``off_re/off_im``  – konstante Offsets fuer Real- und Imaginaerteil.
* ``slope_re/slope_im`` – feldabhaengiger linearer Gradient (Hintergrund).
* ``B_ref``          – Bandmitte (zur Entkopplung von Offset und Steigung).

Re und Im werden simultan gefittet (gestapeltes Residuum).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .suszeptibilitaet import chi_oop


@dataclass
class Startwerte:
    """Startwerte/Grenzen fuer einen Linescan-Fit (alle Felder in SI/Tesla)."""

    B_res: float
    alpha: float
    A: float
    phi: float
    off_re: float
    off_im: float
    slope_re: float
    slope_im: float
    B_min: float
    B_max: float


def s21_modell(
    mu0H: np.ndarray,
    B_res: float,
    alpha: float,
    A: float,
    phi: float,
    off_re: float,
    off_im: float,
    slope_re: float,
    slope_im: float,
    omega: float,
    gamma: float,
    B_ref: float,
) -> np.ndarray:
    """Komplexes Modell-S21 (siehe Modulbeschreibung)."""
    chi = chi_oop(mu0H, B_res, alpha, omega, gamma)
    vorfaktor = A * np.exp(1j * phi)
    untergrund = (off_re + 1j * off_im) + (slope_re + 1j * slope_im) * (
        np.asarray(mu0H, dtype=float) - B_ref
    )
    return vorfaktor * chi + untergrund


def residuum(
    params: dict,
    mu0H: np.ndarray,
    s21_mess: np.ndarray,
    omega: float,
    gamma: float,
    B_ref: float,
) -> np.ndarray:
    """Reell gestapeltes Residuum (Re zuerst, dann Im) fuer Least-Squares.

    ``s21_mess`` ist komplex (Re + i*Im). ``params`` ist ein dict-aehnliches
    Objekt mit den Modellparametern (kompatibel zu lmfit ``Parameters``).
    """
    modell = s21_modell(
        mu0H,
        params["B_res"],
        params["alpha"],
        params["A"],
        params["phi"],
        params["off_re"],
        params["off_im"],
        params["slope_re"],
        params["slope_im"],
        omega,
        gamma,
        B_ref,
    )
    diff = modell - np.asarray(s21_mess)
    return np.concatenate([diff.real, diff.imag])


def schaetze_startwerte(
    mu0H: np.ndarray,
    s21_mess: np.ndarray,
    omega: float,
    gamma: float,
    B_res_vorgabe: float | None = None,
) -> Startwerte:
    """Schaetzt Startwerte aus den Daten (Basis fuer AutoWindows).

    * ``B_res``  aus dem Magnituden-Extremum (Peak ODER Dip), bzw. Vorgabe.
    * ``alpha``  aus der Halbwertsbreite (FWHM) der Magnitude.
    * ``A``      aus (max - min) der Magnitude.
    * ``phi``    aus dem Phasenwinkel des untergrundbereinigten Signals am
                 Resonanzpunkt – je Frequenz, KEIN globaler Festwert
                 (verhindert Peak/Dip-Verwechslung / lokale Minima).
    * Offsets/Steigungen aus den Bandraendern.
    """
    mu0H = np.asarray(mu0H, dtype=float)
    s21 = np.asarray(s21_mess)
    if mu0H.size < 4:
        raise ValueError("Linescan zu kurz fuer eine Startwertschaetzung.")

    # Nach Feld sortieren (Feld kann monoton fallend vorliegen).
    ordnung = np.argsort(mu0H)
    B = mu0H[ordnung]
    sig = s21[ordnung]

    betrag = np.abs(sig)

    # Untergrund linear aus den Randbereichen (je 15 % der Punkte) schaetzen.
    n = B.size
    rand = max(2, n // 7)
    idx_rand = np.concatenate([np.arange(rand), np.arange(n - rand, n)])
    A_design = np.vstack([B[idx_rand], np.ones(idx_rand.size)]).T
    koeff_re, *_ = np.linalg.lstsq(A_design, sig.real[idx_rand], rcond=None)
    koeff_im, *_ = np.linalg.lstsq(A_design, sig.imag[idx_rand], rcond=None)
    slope_re, b_re = koeff_re
    slope_im, b_im = koeff_im
    B_ref = float(np.mean(B))
    off_re = float(slope_re * B_ref + b_re)
    off_im = float(slope_im * B_ref + b_im)

    # Untergrundbereinigtes Signal -> Resonanz als groesste Abweichung.
    untergrund = (b_re + 1j * b_im) + (slope_re + 1j * slope_im) * B
    rein = sig - untergrund
    betrag_rein = np.abs(rein)

    if B_res_vorgabe is not None:
        i_res = int(np.argmin(np.abs(B - B_res_vorgabe)))
        B_res = float(B_res_vorgabe)
    else:
        i_res = int(np.argmax(betrag_rein))
        B_res = float(B[i_res])

    amplitude = float(betrag_rein.max() - betrag_rein.min())
    if amplitude <= 0:
        amplitude = float(np.ptp(betrag)) or 1.0

    # Phase aus dem komplexen Signal am Resonanzpunkt; chi'' ist dort ~ -i,
    # (Phasen-/Amplituden-Skalierung weiter unten, nach alpha-Schaetzung).
    # daher Phase des Vorfaktors ~ arg(rein) + pi/2.
    phi = float(np.angle(rein[i_res]) + np.pi / 2.0)

    # Linienbreite (FWHM) der untergrundbereinigten Magnitude -> alpha.
    halb = betrag_rein.max() / 2.0
    ueber = np.where(betrag_rein >= halb)[0]
    if ueber.size >= 2:
        fwhm = float(abs(B[ueber[-1]] - B[ueber[0]]))
    else:
        fwhm = float(abs(B[-1] - B[0]) / 10.0)
    fwhm = max(fwhm, 1e-4)
    # mu0*DeltaH (Gl. 2.27) ist die FWHM der ABSORPTION (Imaginaerteil chi''),
    # nicht der Magnitude. Fuer die oop-Lorentzform gilt |chi| ~ 1/sqrt(1+x^2),
    # chi'' ~ 1/(1+x^2): die Magnitude faellt erst bei x=+-sqrt(3) auf die Haelfte,
    # die Absorption schon bei x=+-1. Die hier gemessene Magnituden-FWHM ist daher
    # um den Faktor sqrt(3) groesser als mu0*DeltaH. Mit mu0*DeltaH = 2*omega*alpha/gamma
    # folgt fuer den Startwert:  alpha = gamma*fwhm / (2*sqrt(3)*omega).
    alpha = float(gamma * fwhm / (2.0 * np.sqrt(3.0) * omega))
    # Auf den physikalisch plausiblen Bereich begrenzen (vgl. ananas.fit.kriterien).
    alpha = float(np.clip(alpha, 1e-5, 0.1))

    # Amplituden-Startwert auf die tatsaechliche chi-Skala umrechnen, damit
    # A*|chi| ~ gemessene Amplitude (chi traegt grosse Vorfaktoren in sich).
    chi_start = chi_oop(B, B_res, alpha, omega, gamma)
    chi_skala = float(np.max(np.abs(chi_start)))
    A = amplitude / chi_skala if chi_skala > 0 else amplitude

    return Startwerte(
        B_res=B_res,
        alpha=alpha,
        A=A,
        phi=phi,
        off_re=off_re,
        off_im=off_im,
        slope_re=float(slope_re),
        slope_im=float(slope_im),
        B_min=float(B.min()),
        B_max=float(B.max()),
    )

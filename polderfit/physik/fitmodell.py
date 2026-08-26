# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
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

**Mehrere Resonanzen je Linescan** (z. B. nanostrukturiertes CoFe mit zwei
nahe beieinander liegenden Dips): :func:`s21_modell_multi` summiert ``n``
Polder-Linien mit je eigenem ``B_res``, ``alpha``, ``A`` und ``phi`` ueber
einem GEMEINSAMEN Untergrund (Offset + Gradient)::

    S21(B) = sum_k A_k*exp(i*phi_k) * chi_oop(B; B_res_k, alpha_k, omega, gamma)
             + (off_re + i*off_im) + (slope_re + i*slope_im) * (B - B_ref)

Die Startwerte der ``n`` Moden liefert :func:`schaetze_startwerte_multi`
(n prominenteste Peaks des untergrundbereinigten Betrags). Fuer ``n = 1`` ist
das exakt das Ein-Moden-Modell oben.
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


def _untergrund_und_rein(mu0H: np.ndarray, s21_mess: np.ndarray):
    """Sortiert nach Feld, schaetzt den linearen Untergrund aus den Raendern
    und liefert ``(B, sig, rein, (slope_re, slope_im, off_re, off_im, B_ref))``
    mit ``rein`` = untergrundbereinigtes komplexes Signal."""
    mu0H = np.asarray(mu0H, dtype=float)
    s21 = np.asarray(s21_mess)
    # Nach Feld sortieren (Feld kann monoton fallend vorliegen).
    ordnung = np.argsort(mu0H)
    B = mu0H[ordnung]
    sig = s21[ordnung]
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
    untergrund = (b_re + 1j * b_im) + (slope_re + 1j * slope_im) * B
    rein = sig - untergrund
    return B, sig, rein, (float(slope_re), float(slope_im), off_re, off_im, B_ref)


def schaetze_startwerte(
    mu0H: np.ndarray,
    s21_mess: np.ndarray,
    omega: float,
    gamma: float,
    B_res_vorgabe: float | None = None,
    alpha_max: float = 0.1,
) -> Startwerte:
    """Schaetzt Startwerte aus den Daten (Basis fuer AutoWindows).

    ``alpha_max``: obere Schranke, auf die der alpha-Startwert begrenzt wird
    (identisch mit der harten Fit-Schranke, siehe :mod:`polderfit.fit.kriterien`).

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

    B, sig, rein, (slope_re, slope_im, off_re, off_im, B_ref) = _untergrund_und_rein(mu0H, s21)
    betrag = np.abs(sig)
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
    # Auf den physikalisch plausiblen Bereich begrenzen (vgl. polderfit.fit.kriterien).
    alpha = float(np.clip(alpha, 1e-5, alpha_max))

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


# --- Mehrere Resonanzen je Linescan --------------------------------------------
def s21_modell_multi(
    mu0H: np.ndarray,
    moden,
    off_re: float,
    off_im: float,
    slope_re: float,
    slope_im: float,
    omega: float,
    gamma: float,
    B_ref: float,
) -> np.ndarray:
    """Komplexes Modell-S21 mit ``n`` Resonanzen (siehe Modulbeschreibung).

    ``moden`` ist eine Folge von ``(B_res, alpha, A, phi)``-Tupeln.
    """
    mu0H = np.asarray(mu0H, dtype=float)
    summe = np.zeros(mu0H.shape, dtype=complex)
    for B_res, alpha, A, phi in moden:
        summe = summe + A * np.exp(1j * phi) * chi_oop(mu0H, B_res, alpha, omega, gamma)
    untergrund = (off_re + 1j * off_im) + (slope_re + 1j * slope_im) * (mu0H - B_ref)
    return summe + untergrund


def moden_aus_params(params, n_moden: int) -> list[tuple[float, float, float, float]]:
    """``[(B_res_k, alpha_k, A_k, phi_k)]`` aus (lmfit-)Parametern ``B_res_1`` … ``phi_n``."""
    return [
        (float(params[f"B_res_{k}"]), float(params[f"alpha_{k}"]),
         float(params[f"A_{k}"]), float(params[f"phi_{k}"]))
        for k in range(1, n_moden + 1)
    ]


def residuum_multi(
    params,
    mu0H: np.ndarray,
    s21_mess: np.ndarray,
    omega: float,
    gamma: float,
    B_ref: float,
    n_moden: int,
) -> np.ndarray:
    """Gestapeltes Residuum (Re, Im) des Mehr-Moden-Modells fuer Least-Squares."""
    modell = s21_modell_multi(
        mu0H, moden_aus_params(params, n_moden),
        float(params["off_re"]), float(params["off_im"]),
        float(params["slope_re"]), float(params["slope_im"]),
        omega, gamma, B_ref,
    )
    diff = modell - np.asarray(s21_mess)
    return np.concatenate([diff.real, diff.imag])


def _fwhm_lokal(B: np.ndarray, betrag: np.ndarray, i0: int, grund: float) -> float:
    """Halbwertsbreite des Peaks bei Index ``i0`` (Laufen nach links/rechts, bis
    der Betrag unter die Haelfte von (Peak - Grund) faellt)."""
    halb = grund + 0.5 * (float(betrag[i0]) - grund)
    links = i0
    while links > 0 and betrag[links - 1] >= halb:
        links -= 1
    rechts = i0
    while rechts < betrag.size - 1 and betrag[rechts + 1] >= halb:
        rechts += 1
    breite = float(abs(B[rechts] - B[links]))
    if breite <= 0.0:
        schritt = float(np.ptp(B)) / max(B.size - 1, 1)
        breite = 2.0 * schritt
    return breite


def schaetze_startwerte_multi(
    mu0H: np.ndarray,
    s21_mess: np.ndarray,
    omega: float,
    gamma: float,
    n_moden: int,
    alpha_max: float = 0.1,
) -> list[Startwerte]:
    """Startwerte fuer ``n_moden`` Resonanzen in EINEM Linescan.

    Vorgehen: untergrundbereinigter Betrag -> die ``n`` prominentesten lokalen
    Maxima (``scipy.signal.find_peaks``; reichen die nicht, wird um bereits
    gefundene Peaks maskiert und das naechste Maximum genommen). Je Peak:
    ``B_res`` an der Peakposition, ``alpha`` aus der lokalen Halbwertsbreite
    (Magnitude → Absorption: Faktor sqrt(3), wie im Ein-Moden-Fall), ``phi``
    aus der Phase am Peak, ``A`` aus der lokalen Hoehe. Die Liste ist nach
    ``B_res`` aufsteigend sortiert (Fit-Parametrisierung ueber positive
    Abstaende). Untergrund (Offset/Steigung) ist fuer alle Moden identisch.
    """
    from scipy.signal import find_peaks

    n_moden = int(n_moden)
    if n_moden < 1:
        raise ValueError("n_moden muss >= 1 sein.")
    if n_moden == 1:
        return [schaetze_startwerte(mu0H, s21_mess, omega, gamma, alpha_max=alpha_max)]
    mu0H = np.asarray(mu0H, dtype=float)
    if mu0H.size < 4 * n_moden:
        raise ValueError("Linescan zu kurz fuer die Startwertschaetzung mehrerer Moden.")
    B, sig, rein, (slope_re, slope_im, off_re, off_im, B_ref) = _untergrund_und_rein(
        mu0H, np.asarray(s21_mess))
    betrag_rein = np.abs(rein)
    grund = float(np.median(betrag_rein))
    hoehe_max = float(betrag_rein.max() - grund) or 1.0

    # Kandidaten: prominenteste lokale Maxima.
    gipfel, eigenschaften = find_peaks(betrag_rein, prominence=0.05 * hoehe_max)
    reihenfolge = np.argsort(-eigenschaften["prominences"]) if gipfel.size else np.array([], int)
    gewaehlt: list[int] = [int(gipfel[i]) for i in reihenfolge[:n_moden]]
    # Auffuellen: um gefundene Peaks maskieren, naechstes Maximum nehmen.
    maske = np.ones(B.size, dtype=bool)
    for i0 in gewaehlt:
        fwhm = _fwhm_lokal(B, betrag_rein, i0, grund)
        maske &= ~((B >= B[i0] - 1.5 * fwhm) & (B <= B[i0] + 1.5 * fwhm))
    while len(gewaehlt) < n_moden:
        if not maske.any():
            # Notloesung: gleichmaessig ueber das Fenster verteilen.
            fehlend = n_moden - len(gewaehlt)
            for q in np.linspace(0.25, 0.75, fehlend):
                gewaehlt.append(int(round(q * (B.size - 1))))
            break
        kand = np.where(maske, betrag_rein, -np.inf)
        i0 = int(np.argmax(kand))
        gewaehlt.append(i0)
        fwhm = _fwhm_lokal(B, betrag_rein, i0, grund)
        maske &= ~((B >= B[i0] - 1.5 * fwhm) & (B <= B[i0] + 1.5 * fwhm))

    gewaehlt = sorted(set(gewaehlt))[:n_moden]
    while len(gewaehlt) < n_moden:      # Duplikate entfernt -> auffuellen
        gewaehlt.append(min(B.size - 1, gewaehlt[-1] + max(2, B.size // (2 * n_moden))))
    starts = _startwerte_aus_indizes(B, rein, betrag_rein, grund, hoehe_max, gewaehlt,
                                     omega, gamma, alpha_max,
                                     (off_re, off_im, slope_re, slope_im))
    starts.sort(key=lambda sw: sw.B_res)
    return starts


def _startwerte_aus_indizes(B, rein, betrag_rein, grund, hoehe_max, indizes,
                            omega, gamma, alpha_max, untergrund) -> list[Startwerte]:
    """Startwerte an den Peak-Indizes ``indizes`` (Reihenfolge bleibt erhalten)."""
    off_re, off_im, slope_re, slope_im = untergrund
    starts: list[Startwerte] = []
    for i0 in indizes:
        i0 = int(np.clip(i0, 0, B.size - 1))
        fwhm = max(_fwhm_lokal(B, betrag_rein, i0, grund), 1e-4)
        alpha = float(gamma * fwhm / (2.0 * np.sqrt(3.0) * omega))
        alpha = float(np.clip(alpha, 1e-5, alpha_max))
        B_res = float(B[i0])
        phi = float(np.angle(rein[i0]) + np.pi / 2.0)
        amplitude = max(float(betrag_rein[i0]) - grund, 1e-3 * hoehe_max)
        chi_skala = float(np.max(np.abs(chi_oop(B, B_res, alpha, omega, gamma))))
        A = amplitude / chi_skala if chi_skala > 0 else amplitude
        starts.append(Startwerte(
            B_res=B_res, alpha=alpha, A=A, phi=phi,
            off_re=off_re, off_im=off_im, slope_re=slope_re, slope_im=slope_im,
            B_min=float(B.min()), B_max=float(B.max()),
        ))
    return starts


def startwerte_in_bereichen(
    mu0H: np.ndarray,
    s21_mess: np.ndarray,
    omega: float,
    gamma: float,
    bereiche: list,
    alpha_max: float = 0.1,
) -> list[Startwerte]:
    """Startwerte fuer ``len(bereiche)`` Moden mit je einem Feldbereich.

    ``bereiche[k]`` = ``(lo, hi)`` in Tesla oder ``None`` (frei); die Rueckgabe
    hat dieselbe Reihenfolge (Mode 1, 2, ...). Je Bereich wird das Maximum des
    untergrundbereinigten Betrags genommen; freie Moden bekommen das staerkste
    Maximum ausserhalb der belegten Bereiche. Grundlage der Grenzgeraden-
    Baender je Mode (:func:`polderfit.fit.fenster_steuerung.fitte_geraden_bereich`).
    """
    n = len(bereiche)
    if n < 1:
        raise ValueError("Mindestens ein Bereich noetig.")
    mu0H = np.asarray(mu0H, dtype=float)
    if mu0H.size < 4 * n:
        raise ValueError("Linescan zu kurz fuer die Startwertschaetzung mehrerer Moden.")
    B, sig, rein, (slope_re, slope_im, off_re, off_im, B_ref) = _untergrund_und_rein(
        mu0H, np.asarray(s21_mess))
    betrag_rein = np.abs(rein)
    grund = float(np.median(betrag_rein))
    hoehe_max = float(betrag_rein.max() - grund) or 1.0
    frei = np.ones(B.size, dtype=bool)
    gewaehlt: list = [None] * n
    for k, bereich in enumerate(bereiche):
        if bereich is None:
            continue
        lo, hi = float(bereich[0]), float(bereich[1])
        maske = (B >= lo) & (B <= hi)
        if not maske.any():
            maske = np.zeros(B.size, dtype=bool)
            maske[int(np.argmin(np.abs(B - 0.5 * (lo + hi))))] = True
        gewaehlt[k] = int(np.argmax(np.where(maske, betrag_rein, -np.inf)))
        frei &= ~maske
    for k in range(n):
        if gewaehlt[k] is not None:
            continue
        kand = np.where(frei, betrag_rein, -np.inf) if frei.any() else betrag_rein
        i0 = int(np.argmax(kand))
        gewaehlt[k] = i0
        fwhm = _fwhm_lokal(B, betrag_rein, i0, grund)
        frei &= ~((B >= B[i0] - 1.5 * fwhm) & (B <= B[i0] + 1.5 * fwhm))
    return _startwerte_aus_indizes(B, rein, betrag_rein, grund, hoehe_max, gewaehlt,
                                   omega, gamma, alpha_max,
                                   (off_re, off_im, slope_re, slope_im))

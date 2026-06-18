"""AutoWindows: automatische Resonanzsuche und Fenstervorschlag.

Je Frequenz wird die Resonanz gesucht und ein Feldfenster um sie gelegt. Die
Resonanz ist oft nur eine schmale, schwache Struktur auf einem starken, ueber den
breiten Feldsweep gekruemmten Untergrund. Eine reine *lineare* Untergrund-
schaetzung greift dann zu kurz (das groesste Residuum liegt dort, wo der lineare
Fit am staerksten von der Kruemmung abweicht – nicht an der Resonanz). Daher:

1. Untergrund je Linescan mit einem *glatten Polynom* abziehen (Grad an die
   Feldbreite gekoppelt) und die Resonanz als groesste lokale Abweichung nehmen.
2. Da die Resonanz mit der Frequenz *glatt* wandert (Kittel-Dispersion), wird aus
   den vertrauenswuerdigen Kandidaten eine robuste Trasse ``B_res(f)`` gefittet
   (Polynom Grad ≤ 2, iterative Ausreisser-Verwerfung). Diese Trasse legt die
   Fenstermitte fuer ALLE Frequenzen fest – auch dort, wo die Einzeldetektion bei
   schwacher Resonanz (hohe Frequenzen) oder fehlender Resonanz (tiefe Frequenzen)
   versagt.

Die Grenzen sind in der GUI je Frequenz weiterhin manuell verschiebbar.
"""

from __future__ import annotations

import numpy as np

from ..io.datensatz import Linescan, Messdatensatz
from ..physik.konstanten import GAMMA_STANDARD

#: Obergrenze der halben Fensterbreite (Tesla) – schuetzt gegen Ausreisser der
#: Linienbreiten-Schaetzung bei schwachen/verrauschten Resonanzen.
_HALB_MAX: float = 0.4
#: Mindest-Prominenz (in MAD-Sigma), ab der ein Kandidat als verlaesslich gilt.
_PROMINENZ_MIN: float = 4.0


def _detrend_residuum(feld: np.ndarray, s21: np.ndarray) -> np.ndarray:
    """Betrag des Signals nach Abzug eines glatten (polynomiellen) Untergrunds."""
    B = np.asarray(feld, dtype=float)
    sig = np.asarray(s21)
    n = B.size
    if n < 6:
        return np.abs(sig - np.mean(sig))
    span = float(B.max() - B.min()) or 1.0
    # Grad an die Feldbreite koppeln (~1 Grad je 0.5 T), aber moderat halten,
    # damit das Polynom dem Untergrund folgt, ohne die Resonanz zu verschlucken.
    deg = int(np.clip(round(span / 0.5), 2, 6))
    deg = min(deg, max(1, n // 3))
    cre = np.polyfit(B, sig.real, deg)
    cim = np.polyfit(B, sig.imag, deg)
    rest = (sig.real - np.polyval(cre, B)) + 1j * (sig.imag - np.polyval(cim, B))
    return np.abs(rest)


def _kandidat(feld: np.ndarray, rein: np.ndarray) -> tuple[float, float]:
    """Liefert ``(B_res, prominenz)`` aus dem untergrundbereinigten Residuum."""
    i = int(np.argmax(rein))
    med = float(np.median(rein))
    mad = float(np.median(np.abs(rein - med))) or 1e-12
    prominenz = (float(rein[i]) - med) / (1.4826 * mad)
    return float(feld[i]), float(prominenz)


def _fwhm_um(feld: np.ndarray, rein: np.ndarray, b0: float, fallback: float) -> float:
    """Halbwertsbreite des Residuum-Peaks in der Umgebung von ``b0`` (sonst ``fallback``)."""
    nah = (feld >= b0 - 0.4) & (feld <= b0 + 0.4)
    if nah.sum() < 5:
        nah = np.ones(feld.size, dtype=bool)
    Bn = feld[nah]
    rn = rein[nah]
    halb = (float(rn.max()) + float(np.median(rn))) / 2.0
    ueber = np.where(rn >= halb)[0]
    if ueber.size >= 2:
        w = abs(float(Bn[ueber[-1]]) - float(Bn[ueber[0]]))
        if w > 0:
            return w
    return fallback


def _robuste_trasse(frequenzen, bres, prominenz):
    """Robuste Trasse ``B_res(f)`` (Polynom ≤ Grad 2) aus verlaesslichen Kandidaten.

    Gibt ein Array mit der Vorhersage je Frequenz zurueck – oder ``None``, wenn zu
    wenige verlaessliche Kandidaten fuer einen Trend vorhanden sind (Fallback auf
    Einzeldetektion).
    """
    f = np.asarray(frequenzen, dtype=float)
    b = np.asarray(bres, dtype=float)
    s = np.asarray(prominenz, dtype=float)
    gut = s >= _PROMINENZ_MIN
    if gut.sum() < 5:
        return None
    idx = np.where(gut)[0]
    deg = 2 if idx.size >= 8 else 1
    sel = idx.copy()
    koeff = None
    for _ in range(6):
        koeff = np.polyfit(f[sel], b[sel], deg)
        res = b[sel] - np.polyval(koeff, f[sel])
        med = float(np.median(res))
        mad = float(np.median(np.abs(res - med))) or 1e-9
        behalten = np.abs(res - med) <= 3.0 * 1.4826 * mad
        if behalten.all() or sel[behalten].size < deg + 2:
            break
        sel = sel[behalten]
    if koeff is None:
        return None
    return np.polyval(koeff, f)


def _fenster_um(feld: np.ndarray, rein: np.ndarray, b_res: float,
                breite_faktor: float) -> tuple[float, float]:
    """Symmetrisches Feldfenster um ``b_res`` (Breite an die lokale FWHM gekoppelt)."""
    B = np.asarray(feld, dtype=float)
    b_res = float(np.clip(b_res, B.min(), B.max()))
    spacing = float(np.ptp(B)) / B.size if B.size else 0.01
    fwhm = _fwhm_um(B, rein, b_res, fallback=10.0 * spacing)
    halb = max(breite_faktor * fwhm / 2.0, 6.0 * spacing)
    halb = min(halb, _HALB_MAX)
    unten = max(b_res - halb, float(B.min()))
    oben = min(b_res + halb, float(B.max()))
    if oben <= unten:
        return float(B.min()), float(B.max())
    return unten, oben


def auto_fenster(
    linescan: Linescan,
    gamma: float = GAMMA_STANDARD,
    breite_faktor: float = 8.0,
) -> tuple[float, float]:
    """Schlaegt (Feld_unten, Feld_oben) um die Resonanz EINES Linescans vor.

    Einzeldetektion ueber den glatten Untergrundabzug. Fuer einen ganzen Datensatz
    bevorzugt :func:`auto_fenster_alle` nutzen (robuste Dispersionstrasse).
    """
    B = linescan.feld
    rein = _detrend_residuum(B, linescan.s21)
    b_res, _ = _kandidat(B, rein)
    return _fenster_um(B, rein, b_res, breite_faktor)


def auto_fenster_alle(
    datensatz: Messdatensatz,
    gamma: float = GAMMA_STANDARD,
    breite_faktor: float = 8.0,
) -> list[tuple[float, float]]:
    """AutoWindows fuer alle Linescans – mit globaler, robuster Dispersionstrasse."""
    reins: list[np.ndarray] = []
    kand_b: list[float] = []
    kand_s: list[float] = []
    for ls in datensatz.linescans:
        rein = _detrend_residuum(ls.feld, ls.s21)
        reins.append(rein)
        b, s = _kandidat(ls.feld, rein)
        kand_b.append(b)
        kand_s.append(s)

    trasse = _robuste_trasse(datensatz.frequenzen, kand_b, kand_s)

    fenster: list[tuple[float, float]] = []
    for k, ls in enumerate(datensatz.linescans):
        try:
            b_pred = float(trasse[k]) if trasse is not None else kand_b[k]
            fenster.append(_fenster_um(ls.feld, reins[k], b_pred, breite_faktor))
        except Exception:
            fenster.append((float(ls.feld.min()), float(ls.feld.max())))
    return fenster


def schneide_band(linescan: Linescan, feld_unten: float, feld_oben: float) -> Linescan:
    """Liefert einen neuen Linescan, der auf [feld_unten, feld_oben] beschnitten ist."""
    maske = (linescan.feld >= feld_unten) & (linescan.feld <= feld_oben)
    if maske.sum() < 4:  # zu wenig Punkte -> Original behalten
        return linescan

    def _schnitt(arr):
        return arr[maske] if arr is not None else None

    return Linescan(
        frequenz=linescan.frequenz,
        feld=linescan.feld[maske],
        re=linescan.re[maske],
        im=linescan.im[maske],
        feld_before=_schnitt(linescan.feld_before),
        feld_after=_schnitt(linescan.feld_after),
        temperatur=_schnitt(linescan.temperatur),
    )

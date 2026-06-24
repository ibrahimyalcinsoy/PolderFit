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


def _stationaeren_untergrund_abziehen(reins: list[np.ndarray]) -> list[np.ndarray]:
    """Entfernt den FELD-STATIONAEREN Anteil aus den Residuen (nur bei gemeinsamem
    Feldgitter, d. h. unsortierten Daten).

    Hintergrund: Die echte Resonanz WANDERT mit der Frequenz (Kittel-Dispersion) –
    bei einem festen Feldwert taucht sie also nur fuer wenige Frequenzen auf. Stoer-
    features dagegen (periodische Untergrund-Ripples z. B. bei Gitter-Proben, kleine
    apparative Artefakte) sitzen bei FESTEN Feldwerten ueber (fast) alle Frequenzen.
    Der Median ueber die Frequenzachse je Feldpunkt schaetzt genau diesen
    stationaeren Untergrund; nach Abzug bleibt vorwiegend die wandernde Resonanz –
    die Einzeldetektion verirrt sich dann nicht mehr an einem festen Stoerfeature.
    """
    R = np.asarray(reins)
    stationaer = np.median(R, axis=0)
    return [np.clip(r - stationaer, 0.0, None) for r in reins]


def _glatte_lokale_trasse(frequenzen: np.ndarray, kand_b: np.ndarray,
                          kand_s: np.ndarray, fenster_punkte: int = 31):
    """Glatte Resonanztrasse als gleitende ROBUSTE GERADE ueber die prominenten
    Kandidaten.

    Liefert je Linescan einen robusten Schaetzwert ``B_res(f)`` – oder ``None``,
    wenn es zu wenige prominente Kandidaten gibt. In einem gleitenden Fenster wird
    eine Gerade an die prominenten Kandidaten gefittet (eine MAD-Ausreisser-
    Verwerfung), und der Wert an der Stelle ``k`` vorhergesagt. Die LOKALE Gerade
    folgt der (glatten, monoton steigenden) Kittel-Dispersion – auch wenn diese
    schnell mit der Frequenz wandert – und unterdrueckt zugleich einzelne
    Ausreisser-Kandidaten (Sprung eines Linescans auf ein Stoerfeature). Ein
    gleitender *Median* wuerde dagegen einer schnell wandernden Resonanz nach-
    hinken; ein *globales* Polynom verbiegt sich an Hebelpunkten der Frequenzenden.
    """
    f = np.asarray(frequenzen, dtype=float)
    b = np.asarray(kand_b, dtype=float)
    s = np.asarray(kand_s, dtype=float)
    n = b.size
    gut = s >= _PROMINENZ_MIN
    if gut.sum() < 5:
        return None
    half = max(3, fenster_punkte // 2)
    guide = np.empty(n)
    for k in range(n):
        a = max(0, k - half)
        z = min(n, k + half + 1)
        maske = gut[a:z]
        if maske.sum() < 3:
            # zu wenige verlaessliche Kandidaten im Fenster -> naechste guten nehmen
            idx = np.where(gut)[0]
            j = idx[int(np.argmin(np.abs(idx - k)))]
            guide[k] = b[j]
            continue
        ff = f[a:z][maske]
        bb = b[a:z][maske]
        if np.ptp(ff) <= 0:
            guide[k] = float(np.median(bb))
            continue
        koeff = np.polyfit(ff, bb, 1)
        res = bb - np.polyval(koeff, ff)
        mad = float(np.median(np.abs(res - np.median(res)))) or 1e-12
        behalten = np.abs(res - np.median(res)) <= 3.0 * 1.4826 * mad
        if behalten.sum() >= 3 and not behalten.all() and np.ptp(ff[behalten]) > 0:
            koeff = np.polyfit(ff[behalten], bb[behalten], 1)
        guide[k] = float(np.polyval(koeff, f[k]))
    return guide


def _verfeinere_zentrum(feld: np.ndarray, rein: np.ndarray, b_pred: float,
                        such_radius: float) -> float:
    """Schnappt ``b_pred`` auf den naechsten prominenten Residuum-Peak im Umkreis.

    Korrigiert kleine Trassen-Offsets (eine scharfe Resonanz, die sonst an den
    Fensterrand oder knapp daneben fiele), springt aber wegen des begrenzten
    Radius nicht auf weiter entfernte Stoerfeatures.
    """
    B = np.asarray(feld, dtype=float)
    nah = (B >= b_pred - such_radius) & (B <= b_pred + such_radius)
    if nah.sum() < 3:
        return b_pred
    idx = np.where(nah)[0]
    j = idx[int(np.argmax(rein[idx]))]
    med = float(np.median(rein))
    mad = float(np.median(np.abs(rein - med))) or 1e-12
    if (float(rein[j]) - med) / (1.4826 * mad) >= _PROMINENZ_MIN:
        return float(B[j])
    return b_pred


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
    """AutoWindows fuer alle Linescans.

    Strategie (robust gegen Stoerfeatures und schwache Resonanzen):

    1. Residuum je Linescan ueber den glatten Untergrundabzug; bei gemeinsamem
       Feldgitter zusaetzlich den feld-stationaeren Untergrund abziehen
       (:func:`_stationaeren_untergrund_abziehen`) – das entfernt periodische
       Ripples/Artefakte, die nicht mit der Frequenz wandern.
    2. Pro Linescan einen lokalen Resonanzkandidaten suchen. Ist er **prominent**,
       wird IHM vertraut – die einzelne Detektion ist nach dem Stationaer-Abzug
       sehr zuverlaessig und genauer als jede globale Glaettung.
    3. Nur fuer **schwache** Linescans (keine verlaessliche Einzeldetektion, z. B.
       sehr hohe Frequenzen oder Felder ohne Resonanz) dient die glatte
       Dispersionstrasse als Rueckfall; ihr Zentrum wird noch auf einen nahen
       Peak verfeinert.

    Frueher legte die Trasse die Fenstermitte fuer ALLE Frequenzen fest und konnte
    so gute Einzeldetektionen mit einem schlecht gefitteten globalen Polynom
    ueberschreiben (Hebelpunkt-Ausreisser bei tiefen Frequenzen ohne Resonanz).
    """
    linescans = datensatz.linescans
    n = len(linescans)
    reins: list[np.ndarray] = [_detrend_residuum(ls.feld, ls.s21) for ls in linescans]

    # Feld-stationaeren Untergrund abziehen, falls gemeinsames Feldgitter vorliegt
    # (unsortierte Daten: jeder Linescan hat dieselbe Feldachse).
    groessen = {ls.feld.size for ls in linescans}
    gemeinsam = len(groessen) == 1 and n >= 8 and linescans[0].feld.size >= 8
    if gemeinsam:
        feld0 = linescans[0].feld
        if not all(np.array_equal(linescans[k].feld, feld0) for k in (0, n // 2, n - 1)):
            gemeinsam = False
    if gemeinsam:
        reins = _stationaeren_untergrund_abziehen(reins)

    kand_b = np.empty(n)
    kand_s = np.empty(n)
    for k, ls in enumerate(linescans):
        b, s = _kandidat(ls.feld, reins[k])
        kand_b[k] = b
        kand_s[k] = s

    # Glatte LOKALE Trasse (gleitender Median ueber die prominenten Kandidaten).
    # Die Linescans sind nach Frequenz sortiert; die echte Resonanz wandert glatt
    # (Kittel-Dispersion). Ein gleitender Median folgt dieser Kurve, ist aber
    # immun gegen einzelne Ausreisser-Kandidaten (Sprung auf ein Stoerfeature/
    # Rauschen in einem Linescan) – anders als ein globales Polynom verbiegt er
    # sich nicht durch Hebelpunkte und folgt auch gekruemmten Dispersionen.
    guide = _glatte_lokale_trasse(datensatz.frequenzen, kand_b, kand_s)

    # Rueckfall-Trasse fuer den seltenen Fall, dass es ueberhaupt keine
    # verlaesslichen Kandidaten fuer einen lokalen Median gibt.
    trasse = _robuste_trasse(datensatz.frequenzen, kand_b, kand_s) if guide is None else None

    fenster: list[tuple[float, float]] = []
    for k, ls in enumerate(linescans):
        try:
            spacing = float(np.ptp(ls.feld)) / ls.feld.size if ls.feld.size else 0.01
            tol = max(0.08, 12.0 * spacing)
            fuehrung = guide[k] if guide is not None else (
                float(trasse[k]) if trasse is not None else kand_b[k])
            if kand_s[k] >= _PROMINENZ_MIN and abs(kand_b[k] - fuehrung) <= tol:
                # Verlaessliche Einzeldetektion, konsistent mit der glatten Trasse.
                b_pred = kand_b[k]
            else:
                # Sprung-Kandidat oder schwacher Linescan: an der glatten Trasse
                # ausrichten und auf einen nahen Peak verfeinern.
                b_pred = _verfeinere_zentrum(ls.feld, reins[k], fuehrung, tol)
            fenster.append(_fenster_um(ls.feld, reins[k], b_pred, breite_faktor))
        except Exception:
            fenster.append((float(ls.feld.min()), float(ls.feld.max())))
    return fenster


def fenster_aus_trasse(
    datensatz: Messdatensatz,
    zentren,
    gamma: float = GAMMA_STANDARD,
    breite_faktor: float = 8.0,
) -> list[tuple[float, float]]:
    """Feldfenster um VORGEGEBENE Zentren ``B_res(f)`` (manueller Dispersions-Seed).

    Wird genutzt, wenn die Automatik an einem festen Stoerfeature haengenbleibt: der
    Nutzer gibt die Resonanz-Dispersion vor (z. B. zwei Klicks in der Uebersicht ->
    Kittel-Gerade), und die Fenster folgen ihr. Die Breite ist eng an die erwartete
    Linienbreite gekoppelt – ein schmales Band um die vorgegebene Resonanz liefert
    auch bei schwacher Resonanz neben Stoerfeatures die robustesten Fits.
    """
    z = np.asarray(zentren, dtype=float)
    fenster: list[tuple[float, float]] = []
    for k, ls in enumerate(datensatz.linescans):
        B = ls.feld
        c = float(np.clip(z[k], float(B.min()), float(B.max())))
        # erwartete Linienbreite mu0*DeltaH = 2*omega*alpha/gamma (alpha ~ 0.01),
        # eng gedeckelt:
        dB = 2.0 * (2.0 * np.pi * ls.frequenz) * 0.01 / gamma
        halb = float(np.clip(breite_faktor * dB / 2.0, 0.04, 0.08))
        unten = max(c - halb, float(B.min()))
        oben = min(c + halb, float(B.max()))
        fenster.append((unten, oben) if oben > unten else (float(B.min()), float(B.max())))
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

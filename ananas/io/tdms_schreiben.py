"""Ausgabe der zugeschnittenen Rohdaten und Fitkurven als TDMS.

Struktur der Ausgabedatei (im schlanken sorted-Stil, gut weiterverarbeitbar):

* Gruppe ``Rohdaten_zugeschnitten`` – ``frequency``, ``Field-before``,
  ``Field-after``, ``ReS21``, ``ImS21`` (alle Punkte aller Linescans aneinander).
* Gruppe ``Fit`` – ``frequency``, ``Field``, ``FitRe``, ``FitIm``.
* Gruppe ``Fenster`` – je Linescan ``frequency``, ``Feld_unten``, ``Feld_oben``.

So bleiben "vorher/nachher" (before/after), Frequenz, Re und Im erhalten und die
Fitkurven liegen direkt zum jeweiligen Feld vor.
"""

from __future__ import annotations

import numpy as np
from nptdms import ChannelObject, TdmsWriter

from .datensatz import Linescan


def schreibe_ergebnis_tdms(
    pfad: str,
    linescans: list[Linescan],
    fitkurven: list[np.ndarray] | None = None,
) -> None:
    """Schreibt zugeschnittene Linescans (und optional Fitkurven) als TDMS.

    ``fitkurven[i]`` ist das komplexe Modell-S21 zu ``linescans[i]`` (gleiche
    Laenge wie dessen Feldachse) oder ``None`` fuer einzelne Eintraege.
    """
    roh_freq, roh_fb, roh_fa, roh_re, roh_im = [], [], [], [], []
    fit_freq, fit_feld, fit_re, fit_im = [], [], [], []
    fen_freq, fen_unten, fen_oben = [], [], []

    for i, ls in enumerate(linescans):
        n = ls.feld.size
        roh_freq.append(np.full(n, ls.frequenz))
        roh_fb.append(ls.feld_before if ls.feld_before is not None else ls.feld)
        roh_fa.append(ls.feld_after if ls.feld_after is not None else ls.feld)
        roh_re.append(ls.re)
        roh_im.append(ls.im)

        fen_freq.append(ls.frequenz)
        fen_unten.append(float(np.min(ls.feld)))
        fen_oben.append(float(np.max(ls.feld)))

        if fitkurven is not None and i < len(fitkurven) and fitkurven[i] is not None:
            kurve = np.asarray(fitkurven[i])
            fit_freq.append(np.full(kurve.size, ls.frequenz))
            fit_feld.append(ls.feld)
            fit_re.append(kurve.real)
            fit_im.append(kurve.imag)

    def _verb(teile):
        return np.concatenate(teile) if teile else np.array([], dtype=float)

    with TdmsWriter(pfad) as writer:
        roh = "Rohdaten_zugeschnitten"
        writer.write_segment([
            ChannelObject(roh, "frequency", _verb(roh_freq)),
            ChannelObject(roh, "Field-before", _verb(roh_fb)),
            ChannelObject(roh, "Field-after", _verb(roh_fa)),
            ChannelObject(roh, "ReS21", _verb(roh_re)),
            ChannelObject(roh, "ImS21", _verb(roh_im)),
        ])
        if fit_freq:
            writer.write_segment([
                ChannelObject("Fit", "frequency", _verb(fit_freq)),
                ChannelObject("Fit", "Field", _verb(fit_feld)),
                ChannelObject("Fit", "FitRe", _verb(fit_re)),
                ChannelObject("Fit", "FitIm", _verb(fit_im)),
            ])
        writer.write_segment([
            ChannelObject("Fenster", "frequency", np.asarray(fen_freq, dtype=float)),
            ChannelObject("Fenster", "Feld_unten", np.asarray(fen_unten, dtype=float)),
            ChannelObject("Fenster", "Feld_oben", np.asarray(fen_oben, dtype=float)),
        ])

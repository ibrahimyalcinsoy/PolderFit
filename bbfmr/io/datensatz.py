"""Gemeinsame interne Datenstruktur fuer sortierte und unsortierte Messungen.

Beide TDMS-Formate werden auf dieselbe Struktur abgebildet: eine Liste von
:class:`Linescan` (ein Feldsweep je Frequenz) plus optionale Anzeige-Matrix.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Linescan:
    """Ein Feldsweep bei fester Frequenz (Real- und Imaginaerteil von S21).

    Felder in Tesla, Frequenz in Hz. ``feld`` ist aufsteigend sortiert.
    """

    frequenz: float
    feld: np.ndarray
    re: np.ndarray
    im: np.ndarray
    feld_before: np.ndarray | None = None
    feld_after: np.ndarray | None = None
    temperatur: np.ndarray | None = None

    @property
    def s21(self) -> np.ndarray:
        """Komplexes Signal ``Re + i*Im``."""
        return self.re + 1j * self.im

    @property
    def magnitude(self) -> np.ndarray:
        """Betrag ``|S21|``."""
        return np.abs(self.s21)

    def temperatur_mittel(self) -> float | None:
        """Mittlere Temperatur dieses Linescans (falls vorhanden)."""
        if self.temperatur is None or len(self.temperatur) == 0:
            return None
        return float(np.nanmean(self.temperatur))


@dataclass
class Messdatensatz:
    """Vollstaendige Messung: viele Linescans, plus Metadaten.

    ``format_typ`` ist ``"unsortiert"`` oder ``"sortiert"``.
    """

    quelle: str
    format_typ: str
    linescans: list[Linescan] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    @property
    def frequenzen(self) -> np.ndarray:
        """Aufsteigend sortierte Frequenzachse (Hz)."""
        return np.array([ls.frequenz for ls in self.linescans], dtype=float)

    def __len__(self) -> int:
        return len(self.linescans)

    def feld_bereich(self) -> tuple[float, float]:
        """Globaler (min, max) Feldbereich ueber alle Linescans (Tesla)."""
        mins = [float(np.min(ls.feld)) for ls in self.linescans if ls.feld.size]
        maxs = [float(np.max(ls.feld)) for ls in self.linescans if ls.feld.size]
        return (min(mins), max(maxs)) if mins else (0.0, 0.0)

    def anzeige_matrix(self, n_feld: int = 400) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Magnituden-Matrix fuer die 2D-Darstellung (Frequenz vs. Feld).

        Liefert ``(feld_achse, frequenz_achse, magnitude)`` mit
        ``magnitude.shape == (n_frequenzen, n_feld)``. Bei unregelmaessigen
        (sortierten) Daten wird je Frequenz auf ein gemeinsames Feldgitter
        interpoliert; ausserhalb des gemessenen Bereichs steht NaN.
        """
        b_min, b_max = self.feld_bereich()
        feld_achse = np.linspace(b_min, b_max, n_feld)
        freq_achse = self.frequenzen
        matrix = np.full((len(self.linescans), n_feld), np.nan)
        for i, ls in enumerate(self.linescans):
            if ls.feld.size < 2:
                continue
            ordnung = np.argsort(ls.feld)
            b = ls.feld[ordnung]
            mag = ls.magnitude[ordnung]
            innerhalb = (feld_achse >= b[0]) & (feld_achse <= b[-1])
            matrix[i, innerhalb] = np.interp(feld_achse[innerhalb], b, mag)
        return feld_achse, freq_achse, matrix

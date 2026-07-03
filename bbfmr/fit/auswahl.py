"""Auswertungsauswahl: Unterabtastung und Bereichseinschraenkung vor dem Fit.

Vor der Auswertung kann der Nutzer festlegen (Frequenz-/Feld-"Jumper"):

* nur jeden n-ten **Linescan** (Frequenzachse) auswerten,
* je Linescan nur jeden n-ten **Feldpunkt** verwenden,
* den auszuwertenden Bereich einschraenken (Feld- und Frequenzfenster) und
* Frequenz-Ausschlussbereiche definieren (z. B. der zur Feldachse parallele
  Abschnitt bei 3-5 GHz in Out-of-plane-Duennschicht-Messungen, der nicht
  ausgewertet werden soll).

Die Auswahl erzeugt einen **reduzierten** :class:`Messdatensatz`; alles
Nachgelagerte (AutoWindows, Fits, Kittel/LLG, Export) arbeitet unveraendert
auf dem reduzierten Datensatz. Der Ursprung wird in ``meta`` festgehalten.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..io.datensatz import Linescan, Messdatensatz


def parse_bereiche(text: str, einheit: float = 1.0) -> list[tuple[float, float]]:
    """Parst Bereichsangaben wie ``"3-5; 10.2-11"`` zu ``[(min, max), ...]``.

    Trennzeichen zwischen Bereichen: ``;`` oder ``,``; innerhalb eines
    Bereichs ``-`` (auch mit Leerzeichen). ``einheit`` skaliert die Zahlen
    (z. B. ``1e9`` fuer GHz-Eingabe -> Hz). Leerer Text ergibt ``[]``;
    unlesbare Angaben werfen ``ValueError`` mit klarer Meldung.
    """
    bereiche: list[tuple[float, float]] = []
    for teil in text.replace(",", ";").split(";"):
        teil = teil.strip()
        if not teil:
            continue
        stuecke = teil.split("-")
        if len(stuecke) != 2:
            raise ValueError(
                f"Bereich {teil!r} nicht lesbar - erwartet 'min-max', z. B. '3-5'.")
        try:
            lo, hi = float(stuecke[0]), float(stuecke[1])
        except ValueError:
            raise ValueError(f"Bereich {teil!r} enthaelt keine Zahlen.") from None
        if hi < lo:
            lo, hi = hi, lo
        bereiche.append((lo * einheit, hi * einheit))
    return bereiche


@dataclass
class Auswertungsauswahl:
    """Unterabtastung + Bereichseinschraenkung fuer die Stapelauswertung.

    ``n_frequenz``/``n_feld`` = 1 bedeutet "alle Punkte"; Bereichsgrenzen
    ``None`` bedeuten "keine Einschraenkung". ``frequenz_ausschluss`` sind
    ``(min, max)``-Baender in Hz, die von der Auswertung ausgenommen werden.
    """

    n_frequenz: int = 1
    n_feld: int = 1
    frequenz_min_hz: float | None = None
    frequenz_max_hz: float | None = None
    feld_min_t: float | None = None
    feld_max_t: float | None = None
    frequenz_ausschluss: list[tuple[float, float]] = field(default_factory=list)

    def __post_init__(self):
        if int(self.n_frequenz) < 1 or int(self.n_feld) < 1:
            raise ValueError("n_frequenz und n_feld muessen >= 1 sein.")
        self.n_frequenz = int(self.n_frequenz)
        self.n_feld = int(self.n_feld)

    @property
    def ist_neutral(self) -> bool:
        """True, wenn die Auswahl nichts einschraenkt (alles auswerten)."""
        return (self.n_frequenz == 1 and self.n_feld == 1
                and self.frequenz_min_hz is None and self.frequenz_max_hz is None
                and self.feld_min_t is None and self.feld_max_t is None
                and not self.frequenz_ausschluss)

    # --- Auswahl anwenden ----------------------------------------------------
    def waehle_indizes(self, datensatz: Messdatensatz) -> np.ndarray:
        """Indizes der auszuwertenden Linescans (Bereiche zuerst, dann jeder n-te).

        Reihenfolge bewusst: erst Frequenzfenster und Ausschlussbaender
        anwenden, dann aus den verbleibenden jeden ``n_frequenz``-ten nehmen -
        so bleibt die Schrittweite auch neben einem Ausschlussband konstant.
        """
        frequenzen = datensatz.frequenzen
        maske = np.ones(frequenzen.size, dtype=bool)
        if self.frequenz_min_hz is not None:
            maske &= frequenzen >= self.frequenz_min_hz
        if self.frequenz_max_hz is not None:
            maske &= frequenzen <= self.frequenz_max_hz
        for lo, hi in self.frequenz_ausschluss:
            maske &= ~((frequenzen >= lo) & (frequenzen <= hi))
        indizes = np.flatnonzero(maske)
        return indizes[:: self.n_frequenz]

    def reduziere_linescan(self, ls: Linescan) -> Linescan:
        """Feldbereich einschraenken und jeden ``n_feld``-ten Punkt behalten."""
        maske = np.ones(ls.feld.size, dtype=bool)
        if self.feld_min_t is not None:
            maske &= ls.feld >= self.feld_min_t
        if self.feld_max_t is not None:
            maske &= ls.feld <= self.feld_max_t
        indizes = np.flatnonzero(maske)[:: self.n_feld]

        def _teil(arr: np.ndarray | None) -> np.ndarray | None:
            return None if arr is None else arr[indizes]

        return Linescan(
            frequenz=ls.frequenz,
            feld=ls.feld[indizes],
            re=ls.re[indizes],
            im=ls.im[indizes],
            feld_before=_teil(ls.feld_before),
            feld_after=_teil(ls.feld_after),
            temperatur=_teil(ls.temperatur),
        )

    def reduziere(self, datensatz: Messdatensatz) -> tuple[Messdatensatz, np.ndarray]:
        """Reduzierten Datensatz + gewaehlte Original-Indizes liefern.

        Der reduzierte Datensatz traegt in ``meta`` die Auswahl
        (``auswertungsauswahl``) und die Original-Indizes
        (``quell_indizes``) zur Nachvollziehbarkeit.
        """
        indizes = self.waehle_indizes(datensatz)
        linescans = [self.reduziere_linescan(datensatz.linescans[i]) for i in indizes]
        meta = dict(datensatz.meta)
        meta["auswertungsauswahl"] = self.als_dict()
        meta["quell_indizes"] = [int(i) for i in indizes]
        return (
            Messdatensatz(quelle=datensatz.quelle, format_typ=datensatz.format_typ,
                          linescans=linescans, meta=meta),
            indizes,
        )

    def beschreibung(self, datensatz: Messdatensatz | None = None) -> str:
        """Kurztext fuer Protokoll/Dialog, z. B. ``jede 10. Frequenz, Feld 2.5-4 T``."""
        teile: list[str] = []
        if self.n_frequenz > 1:
            teile.append(f"jede {self.n_frequenz}. Frequenz")
        if self.n_feld > 1:
            teile.append(f"jeder {self.n_feld}. Feldpunkt")
        if self.frequenz_min_hz is not None or self.frequenz_max_hz is not None:
            lo = "…" if self.frequenz_min_hz is None else f"{self.frequenz_min_hz/1e9:g}"
            hi = "…" if self.frequenz_max_hz is None else f"{self.frequenz_max_hz/1e9:g}"
            teile.append(f"Frequenz {lo}-{hi} GHz")
        for lo, hi in self.frequenz_ausschluss:
            teile.append(f"ohne {lo/1e9:g}-{hi/1e9:g} GHz")
        if self.feld_min_t is not None or self.feld_max_t is not None:
            lo = "…" if self.feld_min_t is None else f"{self.feld_min_t:g}"
            hi = "…" if self.feld_max_t is None else f"{self.feld_max_t:g}"
            teile.append(f"Feld {lo}-{hi} T")
        text = ", ".join(teile) if teile else "alles auswerten"
        if datensatz is not None:
            text += f" -> {self.waehle_indizes(datensatz).size} von {len(datensatz)} Linescans"
        return text

    # --- Serialisierung (JSON-faehig, fuer Projektsitzungen) -------------------
    def als_dict(self) -> dict:
        return {
            "n_frequenz": self.n_frequenz,
            "n_feld": self.n_feld,
            "frequenz_min_hz": self.frequenz_min_hz,
            "frequenz_max_hz": self.frequenz_max_hz,
            "feld_min_t": self.feld_min_t,
            "feld_max_t": self.feld_max_t,
            "frequenz_ausschluss": [list(b) for b in self.frequenz_ausschluss],
        }

    @classmethod
    def aus_dict(cls, daten: dict) -> "Auswertungsauswahl":
        return cls(
            n_frequenz=int(daten.get("n_frequenz", 1)),
            n_feld=int(daten.get("n_feld", 1)),
            frequenz_min_hz=daten.get("frequenz_min_hz"),
            frequenz_max_hz=daten.get("frequenz_max_hz"),
            feld_min_t=daten.get("feld_min_t"),
            feld_max_t=daten.get("feld_max_t"),
            frequenz_ausschluss=[tuple(b) for b in daten.get("frequenz_ausschluss", [])],
        )

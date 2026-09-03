# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""Korridore: je Mode ein Feldband entlang der Resonanz im (Feld, Frequenz)-Plot.

Ein :class:`Korridor` gehoert zu genau einer Mode (``M1 … Mn``) und besteht aus
wenigen **Ankerpunkten** (Frequenz, linke Grenze, rechte Grenze). Zwischen den
Ankern werden beide Grenzen linear ueber der Frequenz interpoliert, ausserhalb
des Ankerbereichs linear fortgesetzt (die Resonanz verlaeuft praktisch als
Gerade; zwei Anker = zwei Grenzgeraden). Der Fit einer Mode benutzt
AUSSCHLIESSLICH die Messpunkte im Korridor dieser Mode; das Programm trennt
nahe Moden nicht selbst - der Mensch legt die Korridore eng.

Die Korridorliste im Hauptfenster ist die EINZIGE Quelle des Moden-Zustands:
Zahl der Moden = Zahl der Korridore (Mode 1 ohne Korridor = AutoWindow-Fenster).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Anker:
    """Ankerpunkt eines Korridors: Frequenz (Hz), linke und rechte Grenze (T)."""

    f: float
    b_links: float
    b_rechts: float

    def __post_init__(self) -> None:
        self.f = float(self.f)
        lo, hi = sorted((float(self.b_links), float(self.b_rechts)))
        self.b_links, self.b_rechts = lo, hi

    def als_dict(self) -> dict:
        return {"f": self.f, "b_links": self.b_links, "b_rechts": self.b_rechts}


@dataclass
class Korridor:
    """Feldband einer Mode entlang der Frequenz (siehe Modulkopf)."""

    mode: int = 1
    anker: list[Anker] = field(default_factory=list)
    #: Vom Nutzer vorgegebene Zahl der Resonanzen (Dips) IM Korridor. Bei > 1
    #: wird der Korridor je Frequenz zwischen den n prominentesten Dips hart
    #: getrennt ("hard crop") und jedes Stueck einzeln gefittet - kein Summenfit.
    n_dips: int = 1
    #: Mode-Nummern dieses Korridors: ``moden[0] == mode`` (Dip 1), danach die
    #: Nummern der weiteren Dips (vom Hauptfenster vergeben).
    moden: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.mode = max(1, int(self.mode))
        self.anker = [a if isinstance(a, Anker) else Anker(**a) for a in self.anker]
        self.n_dips = max(1, int(self.n_dips))
        self.moden = [int(m) for m in self.moden]
        if not self.moden or self.moden[0] != self.mode:
            self.moden = [self.mode] + [m for m in self.moden if m != self.mode]
        self._sortieren()

    def mode_von_dip(self, j: int) -> int | None:
        """Mode-Nummer des ``j``-ten Dips (0-basiert) oder ``None``."""
        return self.moden[j] if 0 <= j < len(self.moden) else None

    def enthaelt_mode(self, mode: int) -> bool:
        return int(mode) in self.moden

    # --- Anker pflegen --------------------------------------------------------
    def _sortieren(self) -> None:
        self.anker.sort(key=lambda a: a.f)

    def anker_setzen(self, f: float, b_links: float, b_rechts: float,
                     toleranz_hz: float = 0.0) -> int:
        """Setzt den Anker bei ``f`` (ersetzt einen Anker innerhalb
        ``toleranz_hz``); liefert den Index des Ankers."""
        neu = Anker(f, b_links, b_rechts)
        for k, a in enumerate(self.anker):
            if abs(a.f - neu.f) <= toleranz_hz:
                self.anker[k] = neu
                self._sortieren()
                return self.anker.index(neu)
        self.anker.append(neu)
        self._sortieren()
        return self.anker.index(neu)

    def anker_entfernen(self, index: int) -> None:
        if 0 <= index < len(self.anker):
            del self.anker[index]

    def anker_verschieben(self, index: int, seite: str, b: float) -> None:
        """Eine Grenze (``"links"``/``"rechts"``) eines Ankers im Feld verschieben."""
        if not (0 <= index < len(self.anker)):
            return
        a = self.anker[index]
        if seite == "links":
            a.b_links = float(b)
        else:
            a.b_rechts = float(b)
        lo, hi = sorted((a.b_links, a.b_rechts))
        a.b_links, a.b_rechts = lo, hi

    def naechster_anker(self, f: float) -> int | None:
        if not self.anker:
            return None
        return int(np.argmin([abs(a.f - f) for a in self.anker]))

    # --- Auswertung -----------------------------------------------------------
    @property
    def definiert(self) -> bool:
        return len(self.anker) >= 1

    def grenzen(self, f: float) -> tuple[float, float] | None:
        """Linke/rechte Grenze (T) bei Frequenz ``f`` (Hz) oder ``None``.

        Ein Anker: konstante Grenzen. Mehrere: lineare Interpolation, ausserhalb
        lineare Fortsetzung ueber die beiden aeussersten Anker.
        """
        n = len(self.anker)
        if n == 0:
            return None
        if n == 1:
            a = self.anker[0]
            return (a.b_links, a.b_rechts) if a.b_rechts > a.b_links else None
        fs = np.array([a.f for a in self.anker], dtype=float)
        links = np.array([a.b_links for a in self.anker], dtype=float)
        rechts = np.array([a.b_rechts for a in self.anker], dtype=float)
        f = float(f)
        if f <= fs[0]:
            i0, i1 = 0, 1
        elif f >= fs[-1]:
            i0, i1 = n - 2, n - 1
        else:
            i1 = int(np.searchsorted(fs, f))
            i0 = i1 - 1
        df = fs[i1] - fs[i0]
        t = (f - fs[i0]) / df if df else 0.0
        lo = float(links[i0] + t * (links[i1] - links[i0]))
        hi = float(rechts[i0] + t * (rechts[i1] - rechts[i0]))
        return (lo, hi) if hi > lo else None

    def mitte(self, f: float) -> float | None:
        g = self.grenzen(f)
        return None if g is None else 0.5 * (g[0] + g[1])

    def gilt(self, f: float, feld_min: float | None = None,
             feld_max: float | None = None) -> bool:
        """Korridor bei ``f`` nicht leer (und innerhalb des Datenbereichs)."""
        g = self.grenzen(f)
        if g is None:
            return False
        if feld_min is not None and g[1] <= feld_min:
            return False
        if feld_max is not None and g[0] >= feld_max:
            return False
        return True

    def grenzen_im_bereich(self, f: float, feld_min: float,
                           feld_max: float) -> tuple[float, float] | None:
        g = self.grenzen(f)
        if g is None:
            return None
        lo, hi = max(g[0], float(feld_min)), min(g[1], float(feld_max))
        return (lo, hi) if hi > lo else None

    def frequenzbereich(self) -> tuple[float, float] | None:
        if not self.anker:
            return None
        return self.anker[0].f, self.anker[-1].f

    # --- Serialisierung -------------------------------------------------------
    def als_dict(self) -> dict:
        return {"mode": int(self.mode), "anker": [a.als_dict() for a in self.anker],
                "n_dips": int(self.n_dips), "moden": [int(m) for m in self.moden]}

    @classmethod
    def aus_dict(cls, daten: dict) -> "Korridor":
        return cls(mode=int(daten.get("mode", 1)),
                   anker=[Anker(float(a["f"]), float(a["b_links"]), float(a["b_rechts"]))
                          for a in daten.get("anker", [])],
                   n_dips=int(daten.get("n_dips", 1)),
                   moden=[int(m) for m in daten.get("moden", [])])

    def kopie(self) -> "Korridor":
        return Korridor(mode=self.mode,
                        anker=[Anker(a.f, a.b_links, a.b_rechts) for a in self.anker],
                        n_dips=self.n_dips, moden=list(self.moden))


def korridor_aus_linie(mode: int, b1: float, f1: float, b2: float, f2: float,
                       halbbreite: float) -> Korridor:
    """Korridor um die Linie ``(b1, f1)-(b2, f2)`` (f in Hz) mit ``+-halbbreite``
    (T): zwei Anker an den Klick-Frequenzen (Werkzeug "Korridor anlegen")."""
    if f1 == f2:
        raise ValueError("Die Korridorlinie braucht zwei verschiedene Frequenzen.")
    h = abs(float(halbbreite))
    return Korridor(mode=mode, anker=[Anker(f1, b1 - h, b1 + h), Anker(f2, b2 - h, b2 + h)])


def korridore_aus_grenzgeraden(geraden: list[dict], feld_min: float,
                               feld_max: float) -> list[Korridor]:
    """Migration von Projektdateien der Version 3 (Grenzgeraden-Paare je Mode).

    Je Mode werden die gruenen Halbebenen aller Geraden bei den Frequenzen ihrer
    Endpunkte geschnitten; nicht-leere Schnitte werden Anker. Geraden ohne
    Gegenstueck (offene Halbebene) ergeben den Schnitt mit dem Datenbereich.
    """
    def _intervall(g: dict, f: float, lo: float, hi: float):
        b1, f1, b2, f2 = g["b1"], g["f1"], g["b2"], g["f2"]
        gruen_positiv = bool(g.get("gruen_positiv", True))
        db, df = b2 - b1, f2 - f1
        if df == 0.0:
            cross = -(f - f1) * db
            ok = (cross >= 0.0) == gruen_positiv or cross == 0.0
            return (lo, hi) if ok else None
        b_grenze = b1 + (f - f1) * db / df
        if gruen_positiv == (df > 0.0):
            a, b = max(lo, b_grenze), hi
        else:
            a, b = lo, min(hi, b_grenze)
        return (a, b) if b > a else None

    je_mode: dict[int, list[dict]] = {}
    for g in geraden:
        je_mode.setdefault(max(1, int(g.get("mode", 1))), []).append(g)
    korridore: list[Korridor] = []
    for mode in sorted(je_mode):
        gm = je_mode[mode]
        frequenzen = sorted({float(g["f1"]) for g in gm} | {float(g["f2"]) for g in gm})
        anker = []
        for f in frequenzen:
            erlaubt: tuple[float, float] | None = (float(feld_min), float(feld_max))
            for g in gm:
                if erlaubt is None:
                    break
                erlaubt = _intervall(g, f, erlaubt[0], erlaubt[1])
            if erlaubt is not None:
                anker.append(Anker(f, erlaubt[0], erlaubt[1]))
        if anker:
            korridore.append(Korridor(mode=mode, anker=anker))
    for k, kor in enumerate(korridore, start=1):   # luecken­los nummerieren
        kor.mode = k
    return korridore


def dip_segmente(feld: np.ndarray, s21: np.ndarray, n: int,
                 min_punkte: int = 6) -> list[tuple[float, float]]:
    """Harte Trennung eines Korridor-Ausschnitts in bis zu ``n`` Feldsegmente,
    eines je Resonanz (Dip): Segmentgrenzen liegen im Minimum des
    untergrundbereinigten Signalbetrags zwischen benachbarten Dips (die ``n``
    prominentesten Maxima des Betrags). Liefert ``[(lo, hi), …]`` aufsteigend
    im Feld; weniger Eintraege, wenn weniger Dips gefunden werden.
    """
    from scipy.signal import find_peaks
    from .autowindows import _detrend_residuum

    B = np.asarray(feld, dtype=float)
    n = max(1, int(n))
    if B.size < 2:
        return []
    lo, hi = float(B.min()), float(B.max())
    if n == 1 or B.size < 2 * min_punkte:
        return [(lo, hi)]
    rein = _detrend_residuum(B, np.asarray(s21))
    reihenfolge = np.argsort(B)
    Bs, rs = B[reihenfolge], rein[reihenfolge]
    spitzen, eig = find_peaks(rs, distance=max(2, min_punkte // 2), prominence=0.0)
    if spitzen.size == 0:
        return [(lo, hi)]
    prominenz = eig.get("prominences", np.zeros(spitzen.size))
    beste = spitzen[np.argsort(prominenz)[::-1][:n]]
    beste = np.sort(beste)
    segmente = []
    start = 0
    for k in range(len(beste)):
        if k + 1 < len(beste):
            a, b = int(beste[k]), int(beste[k + 1])
            trenn = a + int(np.argmin(rs[a:b + 1]))
            ende = trenn
        else:
            ende = Bs.size - 1
        if ende - start + 1 >= min_punkte:
            segmente.append((float(Bs[start]), float(Bs[ende])))
        start = ende
    return segmente if segmente else [(lo, hi)]

"""Verkettbare Verarbeitungskette fuer die 2D-Matrix des Farbplots.

Die Kette haelt eine feste Reihenfolge von Schritten (Konvention des
Projekts: 1. divide-slice, 2. derivative-divide, 3. relation-amplitude),
von denen jeder einzeln zu-/abschaltbar und parametrisierbar ist. Sie wird
immer auf die **unveraenderte komplexe Rohmatrix** angewendet – ein Schritt
veraendert also nie die Eingangsdaten der anderen, und jede Aenderung der
Parameter spielt die Kette komplett neu ab (Muster aus pybbfmr
``Measurement.process()``).

Die Kette ist JSON-serialisierbar (``als_dict``/``aus_dict``), damit sie in
Projektsitzungen gespeichert werden kann.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import operationen

#: Registrierte Operationen: Name -> Funktion. Reihenfolge = Standard-Kette.
OPERATIONEN = {
    "divide_slice": operationen.divide_slice,
    "derivative_divide": operationen.derivative_divide,
    "relation_amplitude": operationen.relation_amplitude,
}

#: Anzeige-Transformationen des (komplexen) Ergebnisses fuer den Farbplot.
ANZEIGE_MODI = {
    "betrag": "Betrag |Z|",
    "db": "Betrag in dB (20·log10)",
    "real": "Realteil",
    "imag": "Imaginaerteil",
    "phase": "Phase (Grad)",
}


def anzeige_transform(Z: np.ndarray, modus: str = "betrag") -> np.ndarray:
    """Reelle Darstellungsgroesse aus dem komplexen Ergebnis der Kette."""
    if modus == "betrag":
        return np.abs(Z)
    if modus == "db":
        with np.errstate(divide="ignore", invalid="ignore"):
            return 20.0 * np.log10(np.abs(Z))
    if modus == "real":
        return np.real(Z)
    if modus == "imag":
        return np.imag(Z)
    if modus == "phase":
        return np.degrees(np.angle(Z))
    raise ValueError(f"Unbekannter Anzeige-Modus {modus!r} (erlaubt: {list(ANZEIGE_MODI)}).")


@dataclass
class KettenSchritt:
    """Ein Schritt der Verarbeitungskette (Operation + Parameter + an/aus)."""

    operation: str
    aktiv: bool = False
    parameter: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.operation not in OPERATIONEN:
            raise ValueError(
                f"Unbekannte Operation {self.operation!r} (erlaubt: {list(OPERATIONEN)}).")


@dataclass
class Verarbeitungskette:
    """Geordnete Liste von :class:`KettenSchritt`, anwendbar auf (feld, freq, Z)."""

    schritte: list[KettenSchritt] = field(default_factory=list)

    @classmethod
    def standard(cls) -> "Verarbeitungskette":
        """Standard-Kette in Projektreihenfolge.

        derivative-divide ist aktiv (Δn=4, mit Fenstermittelung – die
        pybbfmr-Defaults der Loader), divide-slice und relation-amplitude
        sind aus, aber vorkonfiguriert.
        """
        return cls(schritte=[
            KettenSchritt("divide_slice", aktiv=False,
                          parameter={"achse": "feld", "index": 0}),
            KettenSchritt("derivative_divide", aktiv=True,
                          parameter={"delta_n": 4, "mitteln": True, "achse": "feld"}),
            KettenSchritt("relation_amplitude", aktiv=False,
                          parameter={"delta_n": 1, "achse": "feld"}),
        ])

    def anwenden(self, feld: np.ndarray, frequenz: np.ndarray, Z: np.ndarray
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Spielt alle aktiven Schritte in Reihenfolge auf (feld, frequenz, Z) ab."""
        for schritt in self.schritte:
            if not schritt.aktiv:
                continue
            funktion = OPERATIONEN[schritt.operation]
            feld, frequenz, Z = funktion(feld, frequenz, Z, **schritt.parameter)
        return feld, frequenz, Z

    def aktive_schritte(self) -> list[KettenSchritt]:
        return [s for s in self.schritte if s.aktiv]

    def beschreibung(self) -> str:
        """Kurztext der aktiven Schritte fuer Titel/Protokoll, z. B.
        ``divide_slice(index=0) → derivative_divide(Δn=4)``."""
        teile = []
        for s in self.aktive_schritte():
            params = dict(s.parameter)
            delta_n = params.pop("delta_n", None)
            kurz = ", ".join(
                ([f"Δn={delta_n}"] if delta_n is not None else [])
                + [f"{k}={v}" for k, v in params.items() if k != "achse"])
            teile.append(f"{s.operation}({kurz})" if kurz else s.operation)
        return " → ".join(teile) if teile else "roh"

    # --- Serialisierung (JSON-faehig) ---------------------------------------
    def als_dict(self) -> dict:
        return {
            "bbfmr_verarbeitungskette": 1,
            "schritte": [
                {"operation": s.operation, "aktiv": s.aktiv, "parameter": dict(s.parameter)}
                for s in self.schritte
            ],
        }

    @classmethod
    def aus_dict(cls, daten: dict) -> "Verarbeitungskette":
        return cls(schritte=[
            KettenSchritt(operation=s["operation"], aktiv=bool(s.get("aktiv", False)),
                          parameter=dict(s.get("parameter", {})))
            for s in daten.get("schritte", [])
        ])

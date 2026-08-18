# Copyright (c) 2026 Ibrahim Yalcinsoy. Alle Rechte vorbehalten.
"""PolderFit – Breitband-FMR-Auswertung (Portierung von LabVIEW nach Python).

Das Paket gliedert sich in klar getrennte Schichten:

* :mod:`polderfit.io`         – Einlesen/Schreiben von TDMS, interne Datenstruktur
* :mod:`polderfit.physik`     – Konstanten, Polder-Suszeptibilitaet, Fitmodell, Kittel/LLG
* :mod:`polderfit.fit`        – AutoWindows, Einzel-Linescan-Fit, Stapelverarbeitung
* :mod:`polderfit.persistenz` – Export der Fitparameter, Sitzungszustand
* :mod:`polderfit.auswertung` – uebergreifende Plots (Resonanz vs. T / f, Kittel, LLG)
* :mod:`polderfit.gui`        – interaktive PySide6-Oberflaeche
"""



def _pyproject() -> dict:
    """``pyproject.toml`` neben dem Paket (Entwicklungs-Checkout) oder ``{}``."""
    from pathlib import Path
    pfad = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        import tomllib
        with open(pfad, "rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}


_PYPROJECT = _pyproject()


def _version_ermitteln() -> str:
    """Version aus ``pyproject.toml`` ([project] version), sonst Paket-Metadaten, sonst 0.0.0."""
    try:
        return str(_PYPROJECT["project"]["version"])
    except KeyError:
        pass
    try:
        from importlib.metadata import version
        return version("polderfit")
    except Exception:
        return "0.0.0"


#: Versionsnummer – EINE Quelle: ``pyproject.toml``.
__version__: str = _version_ermitteln()

#: Anzeigename ohne Version – EINE Quelle: ``pyproject.toml`` ``[tool.polderfit] name``.
NAME: str = str(_PYPROJECT.get("tool", {}).get("polderfit", {}).get("name", "PolderFit"))

#: Vollstaendiger Programmname, z. B. ``"PolderFit V0.1.0"``. Umbenennen oder
#: Versionssprung = nur ``pyproject.toml`` aendern; alle Anzeigen folgen.
PROGRAMMNAME: str = f"{NAME} V{__version__}"

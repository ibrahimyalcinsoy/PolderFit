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



def _version_ermitteln() -> str:
    """Versionsnummer aus EINER Quelle: ``pyproject.toml`` (Feld ``version``).

    Reihenfolge: (1) ``pyproject.toml`` neben dem Paket (Entwicklungs-Checkout,
    immer aktuell), (2) installierte Paket-Metadaten, (3) ``"0.0.0"``.
    Ein Versionssprung erfordert damit nur das Aendern von ``pyproject.toml``;
    Programmname, Fenstertitel, Hilfe und Projektdateien folgen automatisch.
    """
    from pathlib import Path
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        import tomllib
        with open(pyproject, "rb") as fh:
            return str(tomllib.load(fh)["project"]["version"])
    except Exception:  # keine Datei / kein Checkout
        pass
    try:
        from importlib.metadata import version
        return version("polderfit")
    except Exception:
        return "0.0.0"


#: Versionsnummer (siehe :func:`_version_ermitteln`).
__version__: str = _version_ermitteln()

#: Anzeigename des Programms; folgt stets der aktuellen Version,
#: z. B. ``"PolderFit V0.1.0"``. Ueberall zu verwenden, wo der Name erscheint.
PROGRAMMNAME: str = f"PolderFit V{__version__}"

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

__version__ = "0.1.0"
